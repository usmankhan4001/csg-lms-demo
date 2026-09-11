"""
Socratic AI Academic Tutor (M39)
================================
Implements the Socratic Academic Tutor with pedagogical guardrails,
progressive hint levels, RAG textbook context, and crisis interception.
"""

import logging
from typing import AsyncGenerator, Dict, List, Optional, Any
from sqlmodel.ext.asyncio.session import AsyncSession

from src.services.ai.llm import generate_stream, model_for_tier
from src.services.ai.crisis_classifier import (
    classify_prompt_safety,
    log_safety_incident,
    AISafetyCategory,
    AISafetySeverity,
)
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
) -> str:
    """
    Build the system prompt for the Socratic Tutor with optional textbook context and hint level.
    """
    prompt = SOCRATIC_TUTOR_SYSTEM_PROMPT

    if hint_level:
        if hint_level == 1:
            prompt += "\n\nCURRENT HINT LEVEL: Level 1 (Conceptual Clue). Focus solely on high-level concept clarification and probing questions."
        elif hint_level == 2:
            prompt += "\n\nCURRENT HINT LEVEL: Level 2 (Formula/Rule/Strategy). Provide the relevant formula, rule, or method structure to guide the student."
        elif hint_level >= 3:
            prompt += "\n\nCURRENT HINT LEVEL: Level 3 (Worked Analogous Example). Provide a step-by-step worked analogous example with DIFFERENT numbers, then prompt the student to apply it."

    if context and context.strip():
        prompt += f"\n\n--- TEXTBOOK & COURSE CONTENT CONTEXT ---\n{context.strip()}\n--- END CONTEXT ---"

    return prompt


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
    crisis interception, and RAG context grounding.
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

    # 2. Retrieve Course Textbook / RAG Context
    rag_context = ""
    if db_session and org_id:
        try:
            numeric_course_id = int(course_id) if (course_id and str(course_id).isdigit()) else None
            rag_data = await query_course_rag(
                question=query,
                org_id=org_id,
                db_session=db_session,
                course_id=numeric_course_id,
                top_k=3,
            )
            rag_context = rag_data.get("context", "")
        except Exception as e:
            logger.warning("RAG retrieval failed in Socratic Tutor: %s", e)

    # 3. Assemble Socratic System Prompt
    system_prompt = build_socratic_system_prompt(
        context=rag_context,
        hint_level=hint_level,
    )

    # 4. Stream LLM Response
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
