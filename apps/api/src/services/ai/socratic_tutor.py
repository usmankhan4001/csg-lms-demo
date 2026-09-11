"""
Socratic AI Academic Tutor (M39)
================================
Implements the Socratic Academic Tutor with pedagogical guardrails,
progressive hint levels, RAG textbook context, and crisis interception.

Client scoping requirements layered on top of the original implementation:
  1. Subject-scoping: context (and RAG retrieval) is bounded to the courses
     the student is actually enrolled in (src.db.sms_campus.StudentEnrollment).
  2. Content-relevance + age/grade guardrails: see content_guardrails.py.
  3. Adaptive pacing: reuses the existing Concept Knowledge Graph mastery
     data (src.services.ai.knowledge_graph) rather than a new signal.
  5. Rate limiting: a Redis-backed daily request ceiling per student,
     enforced by the router before the LLM is ever called (see
     src/routers/ai_tutor.py and check_tutor_daily_rate_limit below).
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.redis import get_redis_client
from src.db.courses.courses import Course
from src.db.sms_campus import ClassSection, StudentEnrollment
from src.db.sms_timetable import TimetableSchedule
from src.services.ai.content_guardrails import (
    build_guardrail_context,
    check_content_relevance,
)
from src.services.ai.crisis_classifier import (
    classify_prompt_safety,
    log_safety_incident,
    AISafetyCategory,
    AISafetySeverity,
)
from src.services.ai.knowledge_graph import (
    PASSING_PREREQUISITE_THRESHOLD,
    get_recommended_next_concepts,
)
from src.services.ai.llm import generate_stream, model_for_tier
from src.services.ai.rag.query_service import query_course_rag

logger = logging.getLogger(__name__)

SOCRATIC_TUTOR_SYSTEM_PROMPT = """You are the CSG-LMS Socratic AI Academic Tutor, an expert pedagogical guide dedicated to fostering deep conceptual understanding, critical thinking, and student autonomy.

STRICT PEDAGOGICAL GUARDRAILS:
1. NEVER GIVE DIRECT ANSWERS: Under no circumstances should you provide the final solution, complete homework answer, or write an entire essay/code for the student.
2. SOCRATIC QUESTIONING: Always guide the student step-by-step using targeted, open-ended questions. Break complex problems into smaller, manageable milestones. Prompt the student to explain what they understand and what they have attempted so far.
3. PROGRESSIVE HINT SYSTEM:
   - Level 1 (Conceptual Clue): Probe foundational concepts, definitions, and high-level relationships without giving away formulas or steps.
   - Level 2 (Formula / Rule / Strategy): Direct the student's attention to applicable theorems, mathematical formulas, algorithms, or structural rules.
   - Level 3 (Worked Analogous Example): Provide a step-by-step worked solution to a PARALLEL / ANALOGOUS problem with different numbers or variables. Then, invite the student to apply the same strategy to their original problem.
4. GROWTH MINDSET & ENCOURAGEMENT: Praise effort, curiosity, and persistence. Treat mistakes as valuable learning opportunities.
5. ACADEMIC INTEGRITY: If the student asks you to solve an exam question or do their work, politely explain your role as a Socratic tutor and ask a guiding question to get started.

Format your responses cleanly with markdown. Keep responses concise and focused on the immediate next reasoning step."""


def build_socratic_system_prompt(
    context: Optional[str] = None,
    hint_level: Optional[int] = None,
    guardrail_directives: Optional[str] = None,
    pacing_directive: Optional[str] = None,
) -> str:
    """
    Build the system prompt for the Socratic Tutor with optional textbook
    context, hint level, subject/grade guardrail directives, and adaptive
    pacing guidance.
    """
    prompt = SOCRATIC_TUTOR_SYSTEM_PROMPT

    if hint_level:
        if hint_level == 1:
            prompt += "\n\nCURRENT HINT LEVEL: Level 1 (Conceptual Clue). Focus solely on high-level concept clarification and probing questions."
        elif hint_level == 2:
            prompt += "\n\nCURRENT HINT LEVEL: Level 2 (Formula/Rule/Strategy). Provide the relevant formula, rule, or method structure to guide the student."
        elif hint_level >= 3:
            prompt += "\n\nCURRENT HINT LEVEL: Level 3 (Worked Analogous Example). Provide a step-by-step worked analogous example with DIFFERENT numbers, then prompt the student to apply it."

    if guardrail_directives and guardrail_directives.strip():
        prompt += f"\n\n--- SUBJECT & GRADE GUARDRAILS ---\n{guardrail_directives.strip()}"

    if pacing_directive and pacing_directive.strip():
        prompt += f"\n\n--- ADAPTIVE PACING ---\n{pacing_directive.strip()}"

    if context and context.strip():
        prompt += f"\n\n--- TEXTBOOK & COURSE CONTENT CONTEXT ---\n{context.strip()}\n--- END CONTEXT ---"

    return prompt


# ---------------------------------------------------------------------------
# 1. Enrollment-aware subject scoping
# ---------------------------------------------------------------------------

async def get_student_enrollment_scope(
    student_id: Optional[str],
    db_session: Optional[AsyncSession],
) -> Dict[str, Any]:
    """
    Resolve a student's ACTIVE enrollment scope: the LMS course IDs they are
    actually enrolled in (via the SMS class-section timetable join), their
    grade level, and a best-effort list of enrolled subjects — so the
    tutor's context (and RAG retrieval, see query_course_rag) can be bounded
    to courses the student is actually enrolled in, per the client's "paired
    with a dedicated agent scoped to the student's enrolled subjects"
    requirement.

    Join path: StudentEnrollment (student_id, status='active') -> section_id
    -> ClassSection (grade_level) -> TimetableSchedule (section_id ->
    course_id) gives the set of LMS course_ids taught to that student's
    section(s) this term.

    Fails soft (returns the empty scope) on any lookup error or when the
    student_id isn't a resolvable numeric user id — callers must treat an
    empty scope as "unknown enrollment", not "enrolled in nothing forever".
    """
    empty_scope: Dict[str, Any] = {
        "course_ids": [],
        "grade_level": None,
        "section_ids": [],
        "subjects": [],
    }

    if db_session is None or not student_id:
        return empty_scope

    try:
        student_id_int = int(student_id)
    except (TypeError, ValueError):
        return empty_scope

    try:
        enrollment_res = await db_session.execute(
            select(StudentEnrollment).where(
                col(StudentEnrollment.student_id) == student_id_int,
                col(StudentEnrollment.status) == "active",
            )
        )
        enrollments = enrollment_res.scalars().all()
        section_ids = [e.section_id for e in enrollments if e.section_id is not None]
        if not section_ids:
            return empty_scope

        section_res = await db_session.execute(
            select(ClassSection).where(col(ClassSection.id).in_(section_ids))
        )
        sections = section_res.scalars().all()
        grade_levels = [s.grade_level for s in sections if s.grade_level]
        grade_level = grade_levels[0] if grade_levels else None

        course_res = await db_session.execute(
            select(TimetableSchedule.course_id)
            .where(col(TimetableSchedule.section_id).in_(section_ids))
            .distinct()
        )
        course_ids = [c for c in course_res.scalars().all() if c is not None]

        subjects: List[str] = []
        if course_ids:
            # Local import avoids a hard dependency for callers that only
            # need enrollment/grade data without the subject-relevance layer.
            from src.services.ai.content_guardrails import infer_subject_from_text

            course_name_res = await db_session.execute(
                select(Course.name).where(col(Course.id).in_(course_ids))
            )
            course_names = [n for n in course_name_res.scalars().all() if n]
            seen = set()
            for name in course_names:
                subj = infer_subject_from_text(name)
                if subj and subj not in seen:
                    seen.add(subj)
                    subjects.append(subj)

        return {
            "course_ids": course_ids,
            "grade_level": grade_level,
            "section_ids": section_ids,
            "subjects": subjects,
        }
    except Exception as e:
        logger.warning("Enrollment scope lookup failed for student '%s': %s", student_id, e)
        return empty_scope


# ---------------------------------------------------------------------------
# 3. Adaptive pacing — reuses the existing mastery-tracking DAG
# ---------------------------------------------------------------------------

async def get_adaptive_pacing_directive(
    student_id: Optional[str],
    subject: Optional[str],
    db_session: Optional[AsyncSession],
) -> Optional[str]:
    """
    Reuses the EXISTING Concept Knowledge Graph mastery data
    (src.services.ai.knowledge_graph.get_recommended_next_concepts) to pace
    the tutor: a concept that is still IN_PROGRESS (below
    PASSING_PREREQUISITE_THRESHOLD) is called out so the tutor holds back
    Level 3 (worked analogous example) hints and dependent/advanced topics
    until that same threshold — already used elsewhere in the knowledge
    graph for prerequisite gating — is crossed. No new pacing signal or
    mastery table is introduced.
    """
    if db_session is None or not student_id:
        return None

    try:
        recommendations = await get_recommended_next_concepts(
            student_id=student_id,
            subject=subject,
            db_session=db_session,
            limit=3,
        )
    except Exception as e:
        logger.warning("Adaptive pacing lookup failed for student '%s': %s", student_id, e)
        return None

    if not recommendations:
        return None

    threshold_pct = int(PASSING_PREREQUISITE_THRESHOLD * 100)
    lines = ["Based on this student's current mastery in the Concept Knowledge Graph:"]
    for rec in recommendations:
        concept = rec["concept"]
        mastery_pct = int(rec["current_mastery"] * 100)
        if rec["status"] == "IN_PROGRESS":
            lines.append(
                f"- '{concept.title}' is IN PROGRESS at {mastery_pct}% mastery (needs "
                f"{threshold_pct}% to safely build on it). Stay at Level 1-2 hints and reinforce "
                "this concept — do NOT advance to a worked example on a concept that depends on it."
            )
        else:
            lines.append(
                f"- '{concept.title}' is READY TO LEARN ({mastery_pct}% mastery, prerequisites "
                "already satisfied). It's safe to introduce this concept's foundational ideas."
            )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 5. Redis-backed daily rate limiting
# ---------------------------------------------------------------------------

# ~1000 requests/day per student per the client spec.
TUTOR_DAILY_REQUEST_LIMIT = 1000

# Key convention (proposed project default, pending formal confirmation):
#   csg:{org_id}:{student_id}:{module}:{key}
# e.g. csg:42:1007:tutor:daily_request_count
_TUTOR_RATE_LIMIT_MODULE = "tutor"
_TUTOR_RATE_LIMIT_KEY_NAME = "daily_request_count"


def build_tutor_rate_limit_key(org_id: Optional[int], student_id: str) -> str:
    """csg:{org_id}:{student_id}:tutor:daily_request_count"""
    org_part = str(org_id) if org_id is not None else "noorg"
    return f"csg:{org_part}:{student_id}:{_TUTOR_RATE_LIMIT_MODULE}:{_TUTOR_RATE_LIMIT_KEY_NAME}"


def _seconds_until_utc_midnight() -> int:
    """
    Design choice: fixed UTC-midnight reset rather than a rolling 24h
    window, so a student's daily quota always resets at the same
    predictable wall-clock time (useful for support/ops explaining "come
    back at midnight UTC") instead of 24h after their first request of the
    day, which would drift with usage patterns.
    """
    now = datetime.now(timezone.utc)
    tomorrow_midnight = (now + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return max(1, int((tomorrow_midnight - now).total_seconds()))


@dataclass
class TutorRateLimitResult:
    is_allowed: bool
    current_count: int
    limit: int
    retry_after_seconds: int


def check_tutor_daily_rate_limit(
    student_id: str,
    org_id: Optional[int] = None,
    max_requests: int = TUTOR_DAILY_REQUEST_LIMIT,
) -> TutorRateLimitResult:
    """
    Redis-backed daily request ceiling for the Socratic Tutor.

    Fails OPEN (allows the request) when Redis is not configured/reachable:
    this is a cost/UX guardrail, not an auth security boundary, so a cache
    outage should not take tutoring down for every student.
    """
    key = build_tutor_rate_limit_key(org_id, student_id)
    r = get_redis_client()
    if r is None:
        return TutorRateLimitResult(
            is_allowed=True, current_count=0, limit=max_requests, retry_after_seconds=0
        )

    try:
        window_seconds = _seconds_until_utc_midnight()
        current = r.get(key)

        if current is None:
            r.setex(key, window_seconds, 1)
            return TutorRateLimitResult(True, 1, max_requests, window_seconds)

        current_count = int(current)
        if current_count >= max_requests:
            ttl = r.ttl(key)
            retry_after = ttl if ttl and ttl > 0 else window_seconds
            return TutorRateLimitResult(False, current_count, max_requests, retry_after)

        new_count = r.incr(key)
        ttl = r.ttl(key)
        if ttl is None or ttl < 0:
            r.expire(key, window_seconds)
            ttl = window_seconds
        return TutorRateLimitResult(True, new_count, max_requests, ttl)
    except Exception as e:
        logger.warning("Tutor rate limit check failed for '%s', failing open: %s", key, e)
        return TutorRateLimitResult(True, 0, max_requests, 0)


# ---------------------------------------------------------------------------
# Main streaming entry point
# ---------------------------------------------------------------------------

async def stream_socratic_guidance(
    query: str,
    course_id: Optional[str] = None,
    history: Optional[List[Dict[str, Any]]] = None,
    user_id: Optional[str] = None,
    org_id: Optional[int] = None,
    db_session: Optional[AsyncSession] = None,
    hint_level: Optional[int] = None,
    model_name: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """
    Stream Socratic guidance tokens with real-time safety screening,
    crisis interception, subject/grade guardrails, enrollment-scoped RAG
    context grounding, and mastery-based adaptive pacing.
    """
    student_id = user_id or "anonymous_student"

    # 1. Safety & Crisis Classification
    safety_result = classify_prompt_safety(query)

    if safety_result.is_flagged:
        # If crisis / self-harm / violence / severe distress / bullying is triggered
        if safety_result.counselor_escalation_required:
            logger.warning(
                "Socratic Tutor intercepted prompt for student '%s' due to safety trigger: %s",
                student_id, safety_result.category.value
            )
            # Log incident to AISafetyIncident table
            if db_session:
                await log_safety_incident(
                    student_id=student_id,
                    severity=safety_result.severity.value,
                    trigger_category=safety_result.category.value,
                    prompt_snippet=query,
                    counselor_notified=True,
                    db_session=db_session,
                    org_id=org_id,
                    course_id=str(course_id) if course_id else None,
                    details=safety_result.reason,
                )

            # Immediately yield canned crisis / safety escalation message
            yield safety_result.canned_response or "Your message triggered safety protocols. A counselor has been notified."
            return

        elif safety_result.category == AISafetyCategory.CHEATING:
            # Pedagogical redirect for direct cheating attempts
            yield safety_result.canned_response or "Let's explore this step-by-step rather than jumping directly to the answer."
            return

    # 2. Resolve enrollment scope: enrolled course IDs, grade level, subjects
    enrollment_scope = await get_student_enrollment_scope(student_id, db_session)
    enrolled_course_ids: List[int] = enrollment_scope.get("course_ids") or []
    enrolled_subjects: List[str] = enrollment_scope.get("subjects") or []
    grade_level: Optional[str] = enrollment_scope.get("grade_level")

    # 3. Content-relevance guardrail: redirect confidently off-topic prompts
    relevance = check_content_relevance(query, enrolled_subjects=enrolled_subjects or None)
    if not relevance.is_relevant:
        logger.info(
            "Socratic Tutor redirected off-topic prompt for student '%s': %s",
            student_id, relevance.reason,
        )
        yield relevance.redirect_message or "Let's keep our focus on your coursework — what are you working on?"
        return

    # 4. Retrieve Course Textbook / RAG Context — bounded to enrolled courses
    #    and segregated by grade level (falls back to unrestricted search
    #    when enrollment data isn't available, e.g. anonymous/demo usage).
    rag_context = ""
    if db_session and org_id:
        try:
            numeric_course_id = int(course_id) if (course_id and str(course_id).isdigit()) else None

            effective_course_id: Optional[int] = None
            effective_course_ids: Optional[List[int]] = None
            if enrolled_course_ids:
                if numeric_course_id is not None and numeric_course_id in enrolled_course_ids:
                    # Requested course is one the student is actually enrolled in.
                    effective_course_id = numeric_course_id
                else:
                    # Either no course was requested, or the requested course is
                    # NOT one of the student's enrollments — never leak another
                    # course's content; scope to what they're actually enrolled in.
                    effective_course_ids = enrolled_course_ids
            else:
                # No enrollment data available — preserve prior behavior.
                effective_course_id = numeric_course_id

            rag_data = await query_course_rag(
                question=query,
                org_id=org_id,
                db_session=db_session,
                course_id=effective_course_id,
                course_ids=effective_course_ids,
                grade_level=grade_level,
                top_k=3,
            )
            rag_context = rag_data.get("context", "")
        except Exception as e:
            logger.warning("RAG retrieval failed in Socratic Tutor: %s", e)

    # 5. Adaptive pacing — reuse existing mastery DAG, don't invent a new signal
    pacing_directive = await get_adaptive_pacing_directive(
        student_id=student_id,
        subject=enrolled_subjects[0] if enrolled_subjects else None,
        db_session=db_session,
    )

    # 6. Subject-scope + grade-appropriate depth directives
    guardrail_directives = build_guardrail_context(
        enrolled_subjects=enrolled_subjects or None,
        grade_level=grade_level,
    )

    # 7. Assemble Socratic System Prompt
    system_prompt = build_socratic_system_prompt(
        context=rag_context,
        hint_level=hint_level,
        guardrail_directives=guardrail_directives,
        pacing_directive=pacing_directive,
    )

    # 8. Stream LLM Response
    selected_model = model_name or model_for_tier("standard")
    try:
        async for chunk in generate_stream(
            model_name=selected_model,
            user_prompt=query,
            system_prompt=system_prompt,
            history=history,
        ):
            yield chunk
    except Exception as e:
        logger.error("Error generating Socratic tutor stream: %s", e, exc_info=True)
        yield f"\n[Socratic Tutor error: {str(e)}]"
