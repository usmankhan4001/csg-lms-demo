"""
Unit & Behavioral Tests for AI Socratic Academic Tutor (M39)
and Crisis / Student Wellbeing Guardrails (M42, M47).

Also covers the client-scoping extensions layered on top of the tutor:
subject-scoping to enrolled courses, content-relevance + grade-based
guardrails, adaptive pacing from the existing mastery DAG, per-grade RAG
segregation, and Redis-backed daily rate limiting.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi import FastAPI, HTTPException, status
from httpx import ASGITransport, AsyncClient

from src.db.ai_models import (
    AISafetyIncident,
    AISafetyCategory,
    AISafetySeverity,
)
from src.db.sms_campus import ClassSection, StudentEnrollment
from src.services.ai.crisis_classifier import (
    classify_prompt_safety,
    log_safety_incident,
    CRISIS_ESCALATION_MESSAGE,
    VIOLENCE_ALERT_MESSAGE,
    CHEATING_REDIRECT_MESSAGE,
)
from src.services.ai.content_guardrails import (
    build_guardrail_context,
    check_content_relevance,
    get_grade_profile,
    infer_subject_from_text,
)
from src.services.ai.socratic_tutor import (
    build_socratic_system_prompt,
    build_tutor_rate_limit_key,
    check_tutor_daily_rate_limit,
    get_adaptive_pacing_directive,
    get_student_enrollment_scope,
    stream_socratic_guidance,
    SOCRATIC_TUTOR_SYSTEM_PROMPT,
    TutorRateLimitResult,
)
from src.services.ai.rag.query_service import (
    MIN_SIMILARITY_THRESHOLD,
    query_course_rag,
)
from src.routers.ai_tutor import (
    SocraticChatRequest,
    api_socratic_tutor_chat,
    api_get_socratic_history,
    api_list_safety_flags,
    router as tutor_router,
)
from src.core.events.database import get_db_session
from src.core.keycloak_auth import (
    KeycloakUserPrincipal,
    PSYCHOLOGIST,
    TEACHER,
    SCHOOL_ADMIN,
    STUDENT,
    SUPER_ADMIN,
    require_roles,
)



def _row(**kwargs):
    """A lightweight stand-in for a SQLAlchemy Row supporting attribute access."""
    return SimpleNamespace(**kwargs)


# ---------------------------------------------------------------------------
# 1. Socratic System Prompt & Progressive Scaffolding Tests
# ---------------------------------------------------------------------------

class TestSocraticPromptBuilder:
    def test_default_system_prompt_rules(self):
        prompt = build_socratic_system_prompt()
        assert "NEVER GIVE DIRECT ANSWERS" in prompt
        assert "SOCRATIC QUESTIONING" in prompt
        assert "PROGRESSIVE HINT SYSTEM" in prompt

    def test_hint_level_1_conceptual_clue(self):
        prompt = build_socratic_system_prompt(hint_level=1)
        assert "Level 1 (Conceptual Clue)" in prompt

    def test_hint_level_2_formula_rule(self):
        prompt = build_socratic_system_prompt(hint_level=2)
        assert "Level 2 (Formula/Rule/Strategy)" in prompt

    def test_hint_level_3_analogous_example(self):
        prompt = build_socratic_system_prompt(hint_level=3)
        assert "Level 3 (Worked Analogous Example)" in prompt

    def test_rag_context_inclusion(self):
        context_text = "Photosynthesis occurs in chloroplasts and produces glucose and oxygen."
        prompt = build_socratic_system_prompt(context=context_text, hint_level=1)
        assert "--- TEXTBOOK & COURSE CONTENT CONTEXT ---" in prompt
        assert context_text in prompt


# ---------------------------------------------------------------------------
# 2. Crisis & Safety Sentiment Classifier Tests
# ---------------------------------------------------------------------------

class TestCrisisClassifier:
    def test_self_harm_trigger(self):
        result = classify_prompt_safety("I want to kill myself and end my life")
        assert result.is_flagged is True
        assert result.category == AISafetyCategory.SELF_HARM
        assert result.severity == AISafetySeverity.CRITICAL
        assert result.counselor_escalation_required is True
        # Was: assert "988" in result.canned_response -- that pinned a
        # HARDCODED US helpline into a system serving a school in Pakistan,
        # where 988 does not connect. The message now carries the school's own
        # resources, or an honest fallback when none are configured. Assert the
        # support is real and no foreign number is implied.
        assert result.canned_response is not None
        assert "findahelpline.com" in result.canned_response
        assert "adult you trust" in result.canned_response
        for foreign in ("988", "911", "741741"):
            assert foreign not in result.canned_response

    def test_violence_trigger(self):
        result = classify_prompt_safety("I'm going to bring a gun to school and shoot up the place")
        assert result.is_flagged is True
        assert result.category == AISafetyCategory.VIOLENCE
        assert result.severity == AISafetySeverity.CRITICAL
        assert result.counselor_escalation_required is True
        assert "Campus safety protocols" in result.canned_response

    def test_severe_distress_trigger(self):
        result = classify_prompt_safety("I can't take this anymore, I am having a severe panic attack and feel hopeless and alone")
        assert result.is_flagged is True
        assert result.category == AISafetyCategory.SEVERE_DISTRESS
        assert result.severity == AISafetySeverity.HIGH
        assert result.counselor_escalation_required is True

    def test_cheating_trigger(self):
        result = classify_prompt_safety("give me the answers to the exam and solve this test question for me")
        assert result.is_flagged is True
        assert result.category == AISafetyCategory.CHEATING
        assert result.severity == AISafetySeverity.LOW
        assert result.counselor_escalation_required is False
        assert "academic integrity" in result.canned_response

    def test_clean_academic_query(self):
        result = classify_prompt_safety("How do I factor the quadratic polynomial 2x^2 + 5x + 2?")
        assert result.is_flagged is False
        assert result.counselor_escalation_required is False
        assert result.canned_response is None


# ---------------------------------------------------------------------------
# 3. Safety Incident DB Logging Tests
# ---------------------------------------------------------------------------

class TestSafetyIncidentLogging:
    @pytest.mark.asyncio
    async def test_log_safety_incident_commits_to_session(self):
        mock_session = AsyncMock()
        incident = await log_safety_incident(
            student_id="student_42",
            severity=AISafetySeverity.CRITICAL.value,
            trigger_category=AISafetyCategory.SELF_HARM.value,
            prompt_snippet="I want to die",
            counselor_notified=True,
            db_session=mock_session,
            org_id=1,
            course_id="course_101",
            details="Self-harm trigger detected",
        )

        assert incident is not None
        assert incident.student_id == "student_42"
        assert incident.severity == "CRITICAL"
        assert incident.counselor_notified is True
        mock_session.add.assert_called_once()
        mock_session.commit.assert_awaited_once()


# ---------------------------------------------------------------------------
# 4. Socratic Guidance Stream Tests
# ---------------------------------------------------------------------------

class TestSocraticGuidanceStream:
    @pytest.mark.asyncio
    async def test_stream_intercepts_crisis_prompt(self):
        mock_session = AsyncMock()
        chunks = []
        with patch("src.services.ai.socratic_tutor.generate_stream") as mock_gen:
            async for chunk in stream_socratic_guidance(
                query="I want to kill myself",
                course_id="c_1",
                user_id="student_123",
                db_session=mock_session,
            ):
                chunks.append(chunk)

            # LLM generation must NOT be called when crisis is intercepted
            mock_gen.assert_not_called()

        full_output = "".join(chunks)
        # Was: assert "988" in full_output. Third test in this file pinning a
        # US-only helpline into a Pakistani deployment. The stream must carry
        # real support, and must not imply a number that will not connect.
        assert "findahelpline.com" in full_output
        assert "adult you trust" in full_output
        assert "988" not in full_output
        mock_session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_stream_intercepts_cheating_prompt(self):
        mock_session = AsyncMock()
        chunks = []
        with patch("src.services.ai.socratic_tutor.generate_stream") as mock_gen:
            async for chunk in stream_socratic_guidance(
                query="give me the answers to the exam",
                course_id="c_1",
                user_id="student_123",
                db_session=mock_session,
            ):
                chunks.append(chunk)

            mock_gen.assert_not_called()

        full_output = "".join(chunks)
        assert "academic integrity" in full_output

    @pytest.mark.asyncio
    async def test_stream_normal_socratic_flow(self):
        mock_session = AsyncMock()

        async def fake_stream(*args, **kwargs):
            yield "What "
            yield "do you notice "
            yield "about the leading coefficient?"

        with patch("src.services.ai.socratic_tutor.generate_stream", side_effect=fake_stream):
            chunks = []
            async for chunk in stream_socratic_guidance(
                query="How do I solve 2x^2 + 5x + 2 = 0?",
                course_id="c_1",
                user_id="student_123",
                db_session=mock_session,
                hint_level=1,
            ):
                chunks.append(chunk)

            full_output = "".join(chunks)
            assert "leading coefficient" in full_output


# ---------------------------------------------------------------------------
# 5. FastAPI Router Tests
# ---------------------------------------------------------------------------

class TestAITutorRouter:
    @pytest.mark.asyncio
    async def test_chat_endpoint_empty_query_raises_400(self):
        mock_session = AsyncMock()
        req = SocraticChatRequest(query="")
        with pytest.raises(HTTPException) as exc_info:
            await api_socratic_tutor_chat(req, principal=None, db_session=mock_session)
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_chat_endpoint_returns_streaming_response(self):
        mock_session = AsyncMock()
        req = SocraticChatRequest(query="Explain Newton's second law", hint_level=1)
        # Rate limiting is Redis-backed (see TestTutorRateLimiting below); mock
        # it here so this test doesn't depend on a real Redis instance.
        allowed = TutorRateLimitResult(is_allowed=True, current_count=1, limit=1000, retry_after_seconds=0)
        with patch("src.routers.ai_tutor.check_tutor_daily_rate_limit", return_value=allowed):
            resp = await api_socratic_tutor_chat(req, principal=None, db_session=mock_session)
        assert resp.media_type == "text/event-stream"

    @pytest.mark.asyncio
    async def test_history_endpoint(self):
        owner = KeycloakUserPrincipal(
            sub="student_1",
            roles=[STUDENT],
            email="student@csg.edu",
            org_id=1,
            raw_claims={"lh_user_id": 42},
        )
        with patch("src.routers.ai_tutor.get_chat_session_history") as mock_hist, patch(
            "src.routers.ai_tutor.chat_session_belongs_to_user", return_value=True
        ):
            mock_hist.return_value = {
                "aichat_uuid": "sess_123",
                "message_history": [{"role": "user", "content": "hello"}],
            }
            resp = await api_get_socratic_history(session_uuid="sess_123", principal=owner)
            assert resp.session_uuid == "sess_123"
            assert len(resp.message_history) == 1

    @pytest.mark.asyncio
    async def test_history_endpoint_404s_for_another_students_session(self):
        """404, never 403: the response must not confirm the session exists."""
        other_student = KeycloakUserPrincipal(
            sub="student_2",
            roles=[STUDENT],
            email="other@csg.edu",
            org_id=1,
            raw_claims={"lh_user_id": 43},
        )
        with patch("src.routers.ai_tutor.chat_session_belongs_to_user", return_value=False):
            with pytest.raises(HTTPException) as exc_info:
                await api_get_socratic_history(
                    session_uuid="sess_123", principal=other_student
                )
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_history_endpoint_allows_a_safeguarding_role(self):
        """A counsellor following up a disclosure is entitled to the transcript."""
        counsellor = KeycloakUserPrincipal(
            sub="counsellor_1",
            roles=[PSYCHOLOGIST],
            email="counsellor@csg.edu",
            org_id=1,
            raw_claims={"lh_user_id": 7},
        )
        with patch("src.routers.ai_tutor.get_chat_session_history") as mock_hist, patch(
            "src.routers.ai_tutor.chat_session_belongs_to_user", return_value=False
        ) as mock_owns:
            mock_hist.return_value = {
                "aichat_uuid": "sess_123",
                "message_history": [{"role": "user", "content": "hello"}],
            }
            resp = await api_get_socratic_history(
                session_uuid="sess_123", principal=counsellor
            )
        assert resp.session_uuid == "sess_123"
        assert not mock_owns.called

    @pytest.mark.asyncio
    async def test_safety_flags_role_protection(self):
        teacher_principal = KeycloakUserPrincipal(
            sub="teacher_1",
            roles=[TEACHER],
            email="teacher@csg.edu",
            org_id=1,
        )
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [
            AISafetyIncident(
                id=1,
                student_id="student_99",
                severity="HIGH",
                trigger_category="BULLYING",
                prompt_snippet="bullying phrase",
                counselor_notified=True,
                org_id=1,
            )
        ]
        mock_session.execute.return_value = mock_result

        incidents = await api_list_safety_flags(
            student_id="student_99",
            db_session=mock_session,
            principal=teacher_principal,
        )
        assert len(incidents) == 1
        assert incidents[0].student_id == "student_99"

    @pytest.mark.asyncio
    async def test_safety_flags_student_role_forbidden(self):
        student_principal = KeycloakUserPrincipal(
            sub="student_1",
            roles=[STUDENT],
            email="student@csg.edu",
        )
        checker = require_roles([TEACHER, SCHOOL_ADMIN, SUPER_ADMIN])
        with pytest.raises(HTTPException) as exc_info:
            await checker(student_principal)
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN


# ---------------------------------------------------------------------------
# 5b. GET /ai/tutor/history access control
#
# The session uuid is the Redis key and is echoed to the client in every SSE
# frame, so holding one was enough to read a named child's whole transcript --
# crisis disclosures included -- with no authentication at all.
# ---------------------------------------------------------------------------

class TestTutorHistoryRequiresAuthentication:
    @pytest.fixture
    def app(self):
        app = FastAPI()
        app.include_router(tutor_router, prefix="/api/v1/ai")
        app.dependency_overrides[get_db_session] = lambda: AsyncMock()
        yield app
        app.dependency_overrides.clear()

    @pytest.fixture
    async def client(self, app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            yield c

    @pytest.mark.asyncio
    async def test_unauthenticated_caller_is_rejected(self, client):
        # No credentials at all: the real get_authenticated_user dependency
        # refuses before the endpoint body runs.
        response = await client.get(
            "/api/v1/ai/tutor/history?session_uuid=sess_123"
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_unauthenticated_caller_never_reaches_redis(self, client):
        """Rejected at the dependency, before the transcript is looked up."""
        with patch("src.routers.ai_tutor.get_chat_session_history") as mock_hist:
            response = await client.get(
                "/api/v1/ai/tutor/history?session_uuid=sess_123"
            )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert not mock_hist.called

# ---------------------------------------------------------------------------
# 6. Content-Relevance & Age/Grade Guardrails (content_guardrails.py)
# ---------------------------------------------------------------------------

class TestContentRelevanceGuardrail:
    def test_off_topic_query_flagged_regardless_of_enrollment(self):
        result = check_content_relevance(
            "Who is going to win the super bowl this year?",
            enrolled_subjects=["mathematics"],
        )
        assert result.is_relevant is False
        assert "coursework" in result.redirect_message.lower() or "tutor" in result.redirect_message.lower()

    def test_query_matching_enrolled_subject_is_relevant(self):
        result = check_content_relevance(
            "Can you help me factor this polynomial equation?",
            enrolled_subjects=["mathematics"],
        )
        assert result.is_relevant is True

    def test_query_for_unenrolled_subject_is_redirected(self):
        result = check_content_relevance(
            "Can you explain how photosynthesis works in plant cells?",
            enrolled_subjects=["mathematics"],
        )
        assert result.is_relevant is False
        assert result.matched_subject == "science"
        assert "Mathematics" in result.redirect_message

    def test_ambiguous_query_without_enrollment_data_is_relevant(self):
        # No enrolled_subjects known (e.g. lookup unavailable) -> only the
        # narrow off-topic list applies; a keyword-sparse legitimate query
        # must not be blocked.
        result = check_content_relevance("What's 5 + 3?", enrolled_subjects=None)
        assert result.is_relevant is True

    def test_infer_subject_from_course_name(self):
        assert infer_subject_from_text("AP Biology") == "science"
        assert infer_subject_from_text("Algebra I Honors") == "mathematics"
        assert infer_subject_from_text("Homeroom") is None


class TestGradeAppropriateGuardrail:
    def test_elementary_grade_uses_simple_vocabulary_guidance(self):
        profile = get_grade_profile("Grade 2")
        assert profile.band == "elementary"
        assert "simple vocabulary" in profile.guidance.lower()

    def test_high_school_grade_uses_academic_vocabulary_guidance(self):
        profile = get_grade_profile("Grade 11")
        assert profile.band == "high"
        assert "academic vocabulary" in profile.guidance.lower()

    def test_middle_school_band_is_distinct_from_elementary_and_high(self):
        elementary = get_grade_profile("Grade 3")
        middle = get_grade_profile("Grade 7")
        high = get_grade_profile("Grade 10")
        assert len({elementary.guidance, middle.guidance, high.guidance}) == 3

    def test_unknown_grade_falls_back_to_general_guidance(self):
        profile = get_grade_profile(None)
        assert profile.band == "unknown"

    def test_build_guardrail_context_includes_subject_scope_when_known(self):
        ctx = build_guardrail_context(enrolled_subjects=["mathematics", "science"], grade_level="Grade 9")
        assert "Mathematics" in ctx
        assert "Science" in ctx
        assert "high school" in ctx.lower()


# ---------------------------------------------------------------------------
# 7. Enrollment-Aware Subject Scoping (item 1)
# ---------------------------------------------------------------------------

class TestEnrollmentScopeResolution:
    @pytest.mark.asyncio
    async def test_returns_empty_scope_without_session_or_student(self):
        result = await get_student_enrollment_scope(None, None)
        assert result["course_ids"] == []
        assert result["grade_level"] is None
        assert result["subjects"] == []

    @pytest.mark.asyncio
    async def test_returns_empty_scope_on_lookup_failure(self):
        """A bare AsyncMock (no configured execute chain) must fail soft, not raise."""
        mock_session = AsyncMock()
        result = await get_student_enrollment_scope("42", mock_session)
        assert result["course_ids"] == []
        assert result["grade_level"] is None

    @pytest.mark.asyncio
    async def test_resolves_course_ids_grade_and_subjects_from_enrollment_join(self):
        mock_session = AsyncMock()

        enrollment = StudentEnrollment(
            id=1, student_id=42, section_id=7, academic_year_id=1, status="active"
        )
        section = ClassSection(id=7, campus_id=1, grade_level="Grade 9", section_name="A")

        res_enrollment = MagicMock()
        res_enrollment.scalars.return_value.all.return_value = [enrollment]

        res_section = MagicMock()
        res_section.scalars.return_value.all.return_value = [section]

        res_course_ids = MagicMock()
        res_course_ids.scalars.return_value.all.return_value = [101]

        res_course_names = MagicMock()
        res_course_names.scalars.return_value.all.return_value = ["Algebra I Honors"]

        mock_session.execute.side_effect = [
            res_enrollment, res_section, res_course_ids, res_course_names,
        ]

        scope = await get_student_enrollment_scope("42", mock_session)

        assert scope["course_ids"] == [101]
        assert scope["grade_level"] == "Grade 9"
        assert scope["subjects"] == ["mathematics"]

    @pytest.mark.asyncio
    async def test_stream_restricts_rag_to_enrolled_courses_when_requested_course_not_enrolled(self):
        """The client's own requested course_id must NOT leak content from a
        course the student isn't enrolled in — the enrolled set wins."""
        mock_session = AsyncMock()
        captured_kwargs = {}

        async def fake_query_course_rag(**kwargs):
            captured_kwargs.update(kwargs)
            return {"context": "", "sources": []}

        async def fake_stream(*args, **kwargs):
            yield "ok"

        enrollment_scope = {
            "course_ids": [101], "grade_level": "Grade 9",
            "subjects": ["mathematics"], "section_ids": [7],
        }

        with patch(
            "src.services.ai.socratic_tutor.get_student_enrollment_scope",
            new=AsyncMock(return_value=enrollment_scope),
        ), patch(
            "src.services.ai.socratic_tutor.query_course_rag", side_effect=fake_query_course_rag
        ), patch(
            "src.services.ai.socratic_tutor.generate_stream", side_effect=fake_stream
        ):
            async for _ in stream_socratic_guidance(
                query="Explain quadratic equations",
                course_id="999",  # NOT one of the student's enrolled courses
                user_id="student_1",
                org_id=1,
                db_session=mock_session,
            ):
                pass

        assert captured_kwargs["course_id"] is None
        assert captured_kwargs["course_ids"] == [101]
        assert captured_kwargs["grade_level"] == "Grade 9"

    @pytest.mark.asyncio
    async def test_stream_scopes_to_single_course_when_requested_course_is_enrolled(self):
        mock_session = AsyncMock()
        captured_kwargs = {}

        async def fake_query_course_rag(**kwargs):
            captured_kwargs.update(kwargs)
            return {"context": "", "sources": []}

        async def fake_stream(*args, **kwargs):
            yield "ok"

        enrollment_scope = {
            "course_ids": [101, 202], "grade_level": "Grade 9",
            "subjects": ["mathematics"], "section_ids": [7],
        }

        with patch(
            "src.services.ai.socratic_tutor.get_student_enrollment_scope",
            new=AsyncMock(return_value=enrollment_scope),
        ), patch(
            "src.services.ai.socratic_tutor.query_course_rag", side_effect=fake_query_course_rag
        ), patch(
            "src.services.ai.socratic_tutor.generate_stream", side_effect=fake_stream
        ):
            async for _ in stream_socratic_guidance(
                query="Explain quadratic equations",
                course_id="101",  # IS one of the student's enrolled courses
                user_id="student_1",
                org_id=1,
                db_session=mock_session,
            ):
                pass

        assert captured_kwargs["course_id"] == 101
        assert captured_kwargs["course_ids"] is None

    @pytest.mark.asyncio
    async def test_stream_redirects_off_topic_query_outside_enrolled_subject(self):
        mock_session = AsyncMock()
        enrollment_scope = {
            "course_ids": [101], "grade_level": "Grade 9",
            "subjects": ["mathematics"], "section_ids": [7],
        }

        with patch(
            "src.services.ai.socratic_tutor.get_student_enrollment_scope",
            new=AsyncMock(return_value=enrollment_scope),
        ), patch("src.services.ai.socratic_tutor.generate_stream") as mock_gen:
            chunks = []
            async for chunk in stream_socratic_guidance(
                query="Can you explain how photosynthesis works in plant cells?",
                user_id="student_1",
                org_id=1,
                db_session=mock_session,
            ):
                chunks.append(chunk)
            mock_gen.assert_not_called()

        full_output = "".join(chunks)
        assert "Mathematics" in full_output

    @pytest.mark.asyncio
    async def test_stream_system_prompt_reflects_elementary_grade(self):
        mock_session = AsyncMock()
        captured = {}

        async def fake_stream(*args, **kwargs):
            captured.update(kwargs)
            yield "ok"

        scope = {"course_ids": [], "grade_level": "Grade 2", "subjects": [], "section_ids": []}
        with patch(
            "src.services.ai.socratic_tutor.get_student_enrollment_scope",
            new=AsyncMock(return_value=scope),
        ), patch("src.services.ai.socratic_tutor.generate_stream", side_effect=fake_stream):
            async for _ in stream_socratic_guidance(
                query="What is 2 + 2?", user_id="student_1", db_session=mock_session,
            ):
                pass

        assert "elementary" in captured["system_prompt"].lower()

    @pytest.mark.asyncio
    async def test_stream_system_prompt_reflects_high_school_grade(self):
        mock_session = AsyncMock()
        captured = {}

        async def fake_stream(*args, **kwargs):
            captured.update(kwargs)
            yield "ok"

        scope = {"course_ids": [], "grade_level": "Grade 11", "subjects": [], "section_ids": []}
        with patch(
            "src.services.ai.socratic_tutor.get_student_enrollment_scope",
            new=AsyncMock(return_value=scope),
        ), patch("src.services.ai.socratic_tutor.generate_stream", side_effect=fake_stream):
            async for _ in stream_socratic_guidance(
                query="What is 2 + 2?", user_id="student_1", db_session=mock_session,
            ):
                pass

        assert "high school" in captured["system_prompt"].lower()


# ---------------------------------------------------------------------------
# 8. Adaptive Pacing — reuses the existing mastery DAG (item 3)
# ---------------------------------------------------------------------------

class TestAdaptivePacing:
    @pytest.mark.asyncio
    async def test_pacing_directive_none_without_session_or_student(self):
        directive = await get_adaptive_pacing_directive(None, None, None)
        assert directive is None

    @pytest.mark.asyncio
    async def test_pacing_directive_none_without_recommendations(self):
        mock_session = AsyncMock()
        with patch(
            "src.services.ai.socratic_tutor.get_recommended_next_concepts",
            new=AsyncMock(return_value=[]),
        ):
            directive = await get_adaptive_pacing_directive("student_1", "Physics", mock_session)
        assert directive is None

    @pytest.mark.asyncio
    async def test_pacing_directive_holds_back_on_in_progress_concept_below_threshold(self):
        mock_session = AsyncMock()
        fake_concept = SimpleNamespace(id=2, title="Newton's Laws", subject="Physics", difficulty_level=2)
        recs = [{
            "concept": fake_concept,
            "current_mastery": 0.40,
            "confidence_level": 0.5,
            "status": "IN_PROGRESS",
            "prerequisites_met": True,
            "readiness_score": 0.8,
            "priority": 0.5,
            "recommendation_reason": "In-progress",
        }]
        with patch(
            "src.services.ai.socratic_tutor.get_recommended_next_concepts",
            new=AsyncMock(return_value=recs),
        ):
            directive = await get_adaptive_pacing_directive("student_1", "Physics", mock_session)

        assert directive is not None
        assert "Newton's Laws" in directive
        assert "IN PROGRESS" in directive
        assert "40%" in directive
        assert "do NOT advance" in directive

    @pytest.mark.asyncio
    async def test_pacing_directive_allows_ready_to_learn_concept(self):
        mock_session = AsyncMock()
        fake_concept = SimpleNamespace(id=3, title="Kinematics", subject="Physics", difficulty_level=1)
        recs = [{
            "concept": fake_concept,
            "current_mastery": 0.0,
            "confidence_level": 0.5,
            "status": "READY_TO_LEARN",
            "prerequisites_met": True,
            "readiness_score": 1.0,
            "priority": 0.9,
            "recommendation_reason": "Foundational concept",
        }]
        with patch(
            "src.services.ai.socratic_tutor.get_recommended_next_concepts",
            new=AsyncMock(return_value=recs),
        ):
            directive = await get_adaptive_pacing_directive("student_1", "Physics", mock_session)

        assert "READY TO LEARN" in directive
        assert "safe to introduce" in directive

    @pytest.mark.asyncio
    async def test_stream_includes_pacing_directive_from_mastery_data_in_system_prompt(self):
        mock_session = AsyncMock()
        captured = {}

        async def fake_stream(*args, **kwargs):
            captured.update(kwargs)
            yield "ok"

        fake_concept = SimpleNamespace(id=2, title="Newton's Laws", subject="Physics", difficulty_level=2)
        recs = [{
            "concept": fake_concept,
            "current_mastery": 0.40,
            "confidence_level": 0.5,
            "status": "IN_PROGRESS",
            "prerequisites_met": True,
            "readiness_score": 0.8,
            "priority": 0.5,
            "recommendation_reason": "In-progress",
        }]

        empty_scope = {"course_ids": [], "grade_level": None, "subjects": [], "section_ids": []}
        with patch(
            "src.services.ai.socratic_tutor.get_student_enrollment_scope",
            new=AsyncMock(return_value=empty_scope),
        ), patch(
            "src.services.ai.socratic_tutor.get_recommended_next_concepts",
            new=AsyncMock(return_value=recs),
        ), patch(
            "src.services.ai.socratic_tutor.generate_stream", side_effect=fake_stream
        ):
            async for _ in stream_socratic_guidance(
                query="What is Newton's second law?", user_id="student_1", db_session=mock_session,
            ):
                pass

        assert "Newton's Laws" in captured["system_prompt"]
        assert "IN PROGRESS" in captured["system_prompt"]


# ---------------------------------------------------------------------------
# 9. Per-Grade Segregated Knowledge Base / RAG Filtering (item 4)
# ---------------------------------------------------------------------------

class TestPerGradeRAGFiltering:
    def test_similarity_threshold_matches_spec(self):
        assert MIN_SIMILARITY_THRESHOLD == 0.82

    @pytest.mark.asyncio
    async def test_query_course_rag_excludes_chunks_from_wrong_grade(self):
        mock_session = AsyncMock()
        rows = [
            _row(
                id=1, chunk_text="Grade 9 algebra content", activity_uuid="a1",
                activity_name="Algebra Intro", chapter_name="Ch1", course_name="Algebra I",
                source_type="dynamic_page", block_uuid=None, course_id=1,
                course_uuid="course-uuid-1", distance=0.05,
            ),
            _row(
                id=2, chunk_text="Grade 11 calculus content", activity_uuid="a2",
                activity_name="Calc Intro", chapter_name="Ch1", course_name="Calculus I",
                source_type="dynamic_page", block_uuid=None, course_id=2,
                course_uuid="course-uuid-2", distance=0.05,
            ),
        ]
        mock_result = MagicMock()
        mock_result.fetchall.return_value = rows
        mock_session.execute.return_value = mock_result

        with patch(
            "src.services.ai.rag.query_service.embed_single_text",
            new=AsyncMock(return_value=[0.1] * 8),
        ), patch(
            "src.services.ai.rag.query_service.resolve_course_ids_for_grade",
            new=AsyncMock(return_value=[1]),  # only course 1 serves "Grade 9"
        ):
            result = await query_course_rag(
                question="Explain factoring",
                org_id=1,
                db_session=mock_session,
                grade_level="Grade 9",
            )

        assert "Grade 9 algebra content" in result["context"]
        assert "Grade 11 calculus content" not in result["context"]
        assert len(result["sources"]) == 1
        assert result["sources"][0]["course_uuid"] == "course-uuid-1"

    @pytest.mark.asyncio
    async def test_query_course_rag_course_ids_allowlist_takes_precedence_over_grade(self):
        mock_session = AsyncMock()
        rows = [
            _row(
                id=1, chunk_text="Course A content", activity_uuid="a1", activity_name="A",
                chapter_name="Ch1", course_name="Course A", source_type="dynamic_page",
                block_uuid=None, course_id=10, course_uuid="uuid-a", distance=0.05,
            ),
            _row(
                id=2, chunk_text="Course B content", activity_uuid="a2", activity_name="B",
                chapter_name="Ch1", course_name="Course B", source_type="dynamic_page",
                block_uuid=None, course_id=20, course_uuid="uuid-b", distance=0.05,
            ),
        ]
        mock_result = MagicMock()
        mock_result.fetchall.return_value = rows
        mock_session.execute.return_value = mock_result

        with patch(
            "src.services.ai.rag.query_service.embed_single_text",
            new=AsyncMock(return_value=[0.1] * 8),
        ), patch(
            "src.services.ai.rag.query_service.resolve_course_ids_for_grade",
            new=AsyncMock(side_effect=AssertionError("should not be called when course_ids is given")),
        ):
            result = await query_course_rag(
                question="Explain factoring",
                org_id=1,
                db_session=mock_session,
                course_ids=[10],
                grade_level="Grade 9",
            )

        assert "Course A content" in result["context"]
        assert "Course B content" not in result["context"]

    @pytest.mark.asyncio
    async def test_query_course_rag_applies_similarity_floor(self):
        mock_session = AsyncMock()
        rows = [
            _row(
                id=1, chunk_text="Highly relevant content", activity_uuid="a1", activity_name="A",
                chapter_name="Ch1", course_name="Course A", source_type="dynamic_page",
                block_uuid=None, course_id=1, course_uuid="uuid-a", distance=0.05,  # sim = 0.95
            ),
            _row(
                id=2, chunk_text="Barely related content", activity_uuid="a2", activity_name="B",
                chapter_name="Ch1", course_name="Course B", source_type="dynamic_page",
                block_uuid=None, course_id=1, course_uuid="uuid-a", distance=0.5,  # sim = 0.50
            ),
        ]
        mock_result = MagicMock()
        mock_result.fetchall.return_value = rows
        mock_session.execute.return_value = mock_result

        with patch(
            "src.services.ai.rag.query_service.embed_single_text",
            new=AsyncMock(return_value=[0.1] * 8),
        ):
            result = await query_course_rag(
                question="Explain factoring", org_id=1, db_session=mock_session,
            )

        assert "Highly relevant content" in result["context"]
        assert "Barely related content" not in result["context"]

    @pytest.mark.asyncio
    async def test_query_course_rag_min_similarity_none_disables_floor(self):
        mock_session = AsyncMock()
        rows = [
            _row(
                id=2, chunk_text="Barely related content", activity_uuid="a2", activity_name="B",
                chapter_name="Ch1", course_name="Course B", source_type="dynamic_page",
                block_uuid=None, course_id=1, course_uuid="uuid-a", distance=0.5,
            ),
        ]
        mock_result = MagicMock()
        mock_result.fetchall.return_value = rows
        mock_session.execute.return_value = mock_result

        with patch(
            "src.services.ai.rag.query_service.embed_single_text",
            new=AsyncMock(return_value=[0.1] * 8),
        ):
            result = await query_course_rag(
                question="Explain factoring", org_id=1, db_session=mock_session,
                min_similarity=None,
            )

        assert "Barely related content" in result["context"]


# ---------------------------------------------------------------------------
# 10. Redis-Backed Daily Rate Limiting (item 5)
# ---------------------------------------------------------------------------

class _FakeTutorRedis:
    """In-memory Redis stand-in, mirroring the pattern used in
    src/tests/services/test_ai_rate_limiting_service.py."""

    def __init__(self):
        self.store: dict[str, tuple[int, int]] = {}

    def get(self, key):
        v = self.store.get(key)
        return v[0] if v else None

    def setex(self, key, ttl, value):
        self.store[key] = (int(value), ttl)

    def incr(self, key):
        current = self.store.get(key, (0, 60))
        new = current[0] + 1
        self.store[key] = (new, current[1])
        return new

    def ttl(self, key):
        v = self.store.get(key)
        return v[1] if v else -2

    def expire(self, key, ttl):
        v = self.store.get(key)
        if v:
            self.store[key] = (v[0], ttl)


@pytest.fixture
def fake_tutor_redis():
    return _FakeTutorRedis()


class TestTutorRateLimiting:
    def test_key_convention_matches_spec(self):
        key = build_tutor_rate_limit_key(org_id=42, student_id="1007")
        assert key == "csg:42:1007:tutor:daily_request_count"

    def test_key_convention_handles_missing_org(self):
        key = build_tutor_rate_limit_key(org_id=None, student_id="anonymous_student")
        assert key == "csg:noorg:anonymous_student:tutor:daily_request_count"

    def test_allows_requests_under_daily_limit(self, fake_tutor_redis):
        with patch("src.services.ai.socratic_tutor.get_redis_client", return_value=fake_tutor_redis):
            for _ in range(3):
                result = check_tutor_daily_rate_limit(student_id="s1", org_id=1, max_requests=3)
                assert result.is_allowed is True

    def test_denies_requests_past_the_threshold(self, fake_tutor_redis):
        with patch("src.services.ai.socratic_tutor.get_redis_client", return_value=fake_tutor_redis):
            for _ in range(3):
                check_tutor_daily_rate_limit(student_id="s1", org_id=1, max_requests=3)
            result = check_tutor_daily_rate_limit(student_id="s1", org_id=1, max_requests=3)

        assert result.is_allowed is False
        assert result.current_count >= 3
        assert result.retry_after_seconds > 0

    def test_separate_students_have_independent_buckets(self, fake_tutor_redis):
        with patch("src.services.ai.socratic_tutor.get_redis_client", return_value=fake_tutor_redis):
            for _ in range(3):
                check_tutor_daily_rate_limit(student_id="s1", org_id=1, max_requests=3)
            capped = check_tutor_daily_rate_limit(student_id="s1", org_id=1, max_requests=3)
            fresh = check_tutor_daily_rate_limit(student_id="s2", org_id=1, max_requests=3)

        assert capped.is_allowed is False
        assert fresh.is_allowed is True

    def test_fails_open_when_redis_unavailable(self):
        with patch("src.services.ai.socratic_tutor.get_redis_client", return_value=None):
            result = check_tutor_daily_rate_limit(student_id="s1", org_id=1, max_requests=3)
        assert result.is_allowed is True

    def test_fails_open_when_redis_raises(self, fake_tutor_redis):
        broken = MagicMock()
        broken.get.side_effect = ConnectionError("redis unreachable")
        with patch("src.services.ai.socratic_tutor.get_redis_client", return_value=broken):
            result = check_tutor_daily_rate_limit(student_id="s1", org_id=1, max_requests=3)
        assert result.is_allowed is True

    @pytest.mark.asyncio
    async def test_router_returns_429_with_plain_language_message_past_threshold(self):
        mock_session = AsyncMock()
        req = SocraticChatRequest(query="Explain fractions")
        denied = TutorRateLimitResult(
            is_allowed=False, current_count=1000, limit=1000, retry_after_seconds=3600,
        )
        with patch("src.routers.ai_tutor.check_tutor_daily_rate_limit", return_value=denied):
            with pytest.raises(HTTPException) as exc_info:
                await api_socratic_tutor_chat(req, principal=None, db_session=mock_session)

        assert exc_info.value.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        detail = exc_info.value.detail
        assert isinstance(detail, dict)
        # Design-system error copy: say what happened and what to do next.
        assert "limit" in detail["message"].lower()
        assert "hour" in detail["message"].lower() or "tomorrow" in detail["message"].lower()
        assert exc_info.value.headers["Retry-After"] == "3600"

    @pytest.mark.asyncio
    async def test_router_allows_request_under_threshold(self, fake_tutor_redis):
        mock_session = AsyncMock()
        req = SocraticChatRequest(query="Explain fractions")
        with patch("src.services.ai.socratic_tutor.get_redis_client", return_value=fake_tutor_redis):
            resp = await api_socratic_tutor_chat(req, principal=None, db_session=mock_session)
        assert resp.media_type == "text/event-stream"
