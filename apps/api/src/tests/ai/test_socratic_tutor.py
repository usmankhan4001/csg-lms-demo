"""
Unit & Behavioral Tests for AI Socratic Academic Tutor (M39)
and Crisis / Student Wellbeing Guardrails (M42, M47).
"""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi import HTTPException, status

from src.db.ai_models import (
    AISafetyIncident,
    AISafetyCategory,
    AISafetySeverity,
)
from src.services.ai.crisis_classifier import (
    classify_prompt_safety,
    log_safety_incident,
    CRISIS_ESCALATION_MESSAGE,
    VIOLENCE_ALERT_MESSAGE,
    CHEATING_REDIRECT_MESSAGE,
)
from src.services.ai.socratic_tutor import (
    build_socratic_system_prompt,
    stream_socratic_guidance,
    SOCRATIC_TUTOR_SYSTEM_PROMPT,
)
from src.routers.ai_tutor import (
    SocraticChatRequest,
    api_socratic_tutor_chat,
    api_get_socratic_history,
    api_list_safety_flags,
)
from src.core.keycloak_auth import (
    KeycloakUserPrincipal,
    TEACHER,
    SCHOOL_ADMIN,
    STUDENT,
    SUPER_ADMIN,
    require_roles,
)


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
        assert "988" in result.canned_response

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
        assert "988" in full_output
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
        resp = await api_socratic_tutor_chat(req, principal=None, db_session=mock_session)
        assert resp.media_type == "text/event-stream"

    @pytest.mark.asyncio
    async def test_history_endpoint(self):
        with patch("src.routers.ai_tutor.get_chat_session_history") as mock_hist:
            mock_hist.return_value = {
                "aichat_uuid": "sess_123",
                "message_history": [{"role": "user", "content": "hello"}],
            }
            resp = await api_get_socratic_history(session_uuid="sess_123")
            assert resp.session_uuid == "sess_123"
            assert len(resp.message_history) == 1

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
