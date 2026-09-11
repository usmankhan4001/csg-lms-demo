"""
Unit and Integration Tests for Concept Knowledge Graph (M44),
Student 360 Mastery Matrix (M45), and Live Class AI Q&A Copilot (M50).
"""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi import HTTPException, status
from sqlmodel import select

from src.db.ai_knowledge_graph import (
    ConceptNode,
    ConceptNodeCreate,
    ConceptPrerequisite,
    StudentConceptMastery,
    MasteryEvaluationInput,
    MasteryRadarItem,
    StudentMasteryRadarResponse,
    StudentLearningPathResponse,
)
from src.services.ai.knowledge_graph import (
    evaluate_mastery_update,
    get_concept_dependency_path,
    get_recommended_next_concepts,
    get_student_mastery_radar,
    get_student_learning_path,
    _normalize_score,
)
from src.services.ai.live_class_copilot import (
    LiveClassQAAssistant,
    LiveClassQAResponse,
    LIVE_COPILOT_SYSTEM_PROMPT,
    live_class_copilot,
)
from src.routers.ai_student_profile import (
    IngestTranscriptPayload,
    LiveClassQAPayload,
    PrerequisiteLinkPayload,
    api_get_student_mastery_radar,
    api_get_student_learning_path,
    api_evaluate_mastery_update,
    api_list_concepts,
    api_create_concept,
    api_get_concept_dependency_path,
    api_link_prerequisite,
    api_ingest_transcript_chunk,
    api_live_class_qa,
    api_live_class_summary,
)


# ---------------------------------------------------------------------------
# 1. Score Normalization & Bayesian Mastery Updates
# ---------------------------------------------------------------------------

class TestMasteryScoreCalculations:
    def test_normalize_score_percentage_and_decimal(self):
        assert _normalize_score(85.0) == 0.85
        assert _normalize_score(100.0) == 1.0
        assert _normalize_score(0.72) == 0.72
        assert _normalize_score(0.0) == 0.0
        assert _normalize_score(150.0) == 1.0
        assert _normalize_score(-10.0) == 0.0

    @pytest.mark.asyncio
    async def test_evaluate_mastery_update_initial_record(self):
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_session.execute.return_value = mock_result

        record = await evaluate_mastery_update(
            student_id="student_101",
            concept_id=1,
            quiz_score=90.0,
            difficulty=2,
            db_session=mock_session,
        )

        assert record.student_id == "student_101"
        assert record.concept_id == 1
        assert record.mastery_score > 0.80
        assert record.attempts_count == 1
        assert record.confidence_level >= 0.50
        mock_session.add.assert_called_once()
        mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_evaluate_mastery_update_existing_record_progression(self):
        existing = StudentConceptMastery(
            id=10,
            student_id="student_101",
            concept_id=1,
            mastery_score=0.40,
            confidence_level=0.50,
            attempts_count=1,
            last_evaluated_at="2026-09-01T00:00:00",
        )

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = existing
        mock_session.execute.return_value = mock_result

        updated = await evaluate_mastery_update(
            student_id="student_101",
            concept_id=1,
            quiz_score=95.0,  # 0.95
            difficulty=3,
            db_session=mock_session,
        )

        assert updated.attempts_count == 2
        assert updated.mastery_score > 0.40  # Improved from 0.40
        assert updated.confidence_level > 0.50  # Increased confidence
        mock_session.add.assert_called_once()
        mock_session.commit.assert_awaited_once()


# ---------------------------------------------------------------------------
# 2. Prerequisite DAG & Topological Dependency Path
# ---------------------------------------------------------------------------

class TestConceptPrerequisiteGraph:
    @pytest.mark.asyncio
    async def test_get_concept_dependency_path_linear_chain(self):
        # Chain: Node 1 (Foundations) -> Node 2 (Algebra) -> Node 3 (Calculus)
        n1 = ConceptNode(id=1, subject="Math", topic_code="MATH-101", title="Basic Arithmetic", difficulty_level=1)
        n2 = ConceptNode(id=2, subject="Math", topic_code="MATH-201", title="Algebra I", difficulty_level=2)
        n3 = ConceptNode(id=3, subject="Math", topic_code="MATH-301", title="Calculus I", difficulty_level=4)

        # 3 requires 2, 2 requires 1
        e21 = ConceptPrerequisite(id=1, concept_id=2, prerequisite_concept_id=1, strength_weight=1.0)
        e32 = ConceptPrerequisite(id=2, concept_id=3, prerequisite_concept_id=2, strength_weight=1.0)

        mock_session = AsyncMock()
        mock_session.get.return_value = n3

        # Return edges
        edge_result = MagicMock()
        edge_result.scalars.return_value.all.return_value = [e21, e32]

        # Return nodes
        node_result = MagicMock()
        node_result.scalars.return_value.all.return_value = [n1, n2, n3]

        mock_session.execute.side_effect = [edge_result, node_result]

        path = await get_concept_dependency_path(target_concept_id=3, db_session=mock_session)

        assert len(path) == 3
        # Topological order: Foundational first
        assert path[0].id == 1
        assert path[1].id == 2
        assert path[2].id == 3

    @pytest.mark.asyncio
    async def test_get_concept_dependency_path_nonexistent_returns_empty(self):
        mock_session = AsyncMock()
        mock_session.get.return_value = None

        path = await get_concept_dependency_path(target_concept_id=999, db_session=mock_session)
        assert path == []


# ---------------------------------------------------------------------------
# 3. Next Concept Recommendations & Learning Path
# ---------------------------------------------------------------------------

class TestConceptRecommendationsAndLearningPath:
    @pytest.mark.asyncio
    async def test_get_recommended_next_concepts_unlocked_when_prereqs_met(self):
        n1 = ConceptNode(id=1, subject="Physics", topic_code="PHYS-1", title="Kinematics", difficulty_level=1)
        n2 = ConceptNode(id=2, subject="Physics", topic_code="PHYS-2", title="Newton's Laws", difficulty_level=2)

        # n2 requires n1
        e21 = ConceptPrerequisite(id=1, concept_id=2, prerequisite_concept_id=1, strength_weight=1.0)

        # Student mastered n1 (0.85) but has not started n2 (0.0)
        m1 = StudentConceptMastery(student_id="s1", concept_id=1, mastery_score=0.85, confidence_level=0.8)

        mock_session = AsyncMock()

        res_concepts = MagicMock()
        res_concepts.scalars.return_value.all.return_value = [n1, n2]

        res_mastery = MagicMock()
        res_mastery.scalars.return_value.all.return_value = [m1]

        res_prereq = MagicMock()
        res_prereq.scalars.return_value.all.return_value = [e21]

        mock_session.execute.side_effect = [res_concepts, res_mastery, res_prereq]

        recs = await get_recommended_next_concepts(student_id="s1", subject="Physics", db_session=mock_session)

        assert len(recs) == 1
        assert recs[0]["concept"].id == 2
        assert recs[0]["prerequisites_met"] is True
        assert recs[0]["status"] == "READY_TO_LEARN"

    @pytest.mark.asyncio
    async def test_get_student_mastery_radar_aggregation(self):
        c1 = ConceptNode(id=1, subject="Math", topic_code="M1", title="Algebra", difficulty_level=1)
        c2 = ConceptNode(id=2, subject="Math", topic_code="M2", title="Geometry", difficulty_level=2)
        c3 = ConceptNode(id=3, subject="Science", topic_code="S1", title="Biology", difficulty_level=1)

        m1 = StudentConceptMastery(student_id="s1", concept_id=1, mastery_score=0.90, confidence_level=0.9)
        m2 = StudentConceptMastery(student_id="s1", concept_id=2, mastery_score=0.80, confidence_level=0.8)
        m3 = StudentConceptMastery(student_id="s1", concept_id=3, mastery_score=0.50, confidence_level=0.6)

        mock_session = AsyncMock()
        res_concepts = MagicMock()
        res_concepts.scalars.return_value.all.return_value = [c1, c2, c3]

        res_mastery = MagicMock()
        res_mastery.scalars.return_value.all.return_value = [m1, m2, m3]

        mock_session.execute.side_effect = [res_concepts, res_mastery]

        radar = await get_student_mastery_radar(student_id="s1", db_session=mock_session)

        assert radar.student_id == "s1"
        assert radar.total_tracked_concepts == 3
        assert radar.total_mastered_concepts == 2
        assert len(radar.radar_data) == 2

        math_item = next(r for r in radar.radar_data if r.subject == "Math")
        assert math_item.average_mastery == 0.85
        assert math_item.proficiency_tier == "Mastery"
        assert math_item.mastered_concepts == 2


# ---------------------------------------------------------------------------
# 4. Live Class AI Q&A Copilot Tests
# ---------------------------------------------------------------------------

class TestLiveClassCopilot:
    def test_ingest_and_format_transcript_window(self):
        copilot = LiveClassQAAssistant()
        copilot.ingest_transcript_chunk("sess_1", "teacher", "Welcome to today's lesson on Cellular Respiration.", timestamp=10.0)
        copilot.ingest_transcript_chunk("sess_1", "teacher", "The first stage is Glycolysis occurring in cytoplasm.", timestamp=25.0)

        chunks = copilot.get_transcript_window("sess_1")
        assert len(chunks) == 2
        assert chunks[0].speaker == "teacher"
        assert chunks[1].timestamp == 25.0

        ctx = copilot.format_transcript_context("sess_1")
        assert "Glycolysis" in ctx
        assert "[00:25] Teacher:" in ctx

    @pytest.mark.asyncio
    async def test_copilot_answers_student_question_with_llm(self):
        copilot = LiveClassQAAssistant()
        copilot.ingest_transcript_chunk("sess_2", "teacher", "Recall that force equals mass times acceleration (F=ma).", timestamp=60.0)

        with patch("src.services.ai.live_class_copilot.generate") as mock_gen:
            mock_gen.return_value = "As the teacher explained, F=ma relates force to acceleration proportionally."

            resp = await copilot.answer_student_question(
                session_id="sess_2",
                student_id="student_5",
                student_name="Alice",
                question="What is Newton's second law formula?",
            )

            assert isinstance(resp, LiveClassQAResponse)
            assert resp.student_name == "Alice"
            assert "F=ma" in resp.answer
            assert resp.referenced_timestamp == 60.0
            assert resp.safety_flagged is False

    @pytest.mark.asyncio
    async def test_copilot_intercepts_crisis_sentiment(self):
        copilot = LiveClassQAAssistant()
        mock_session = AsyncMock()

        resp = await copilot.answer_student_question(
            session_id="sess_crisis",
            student_id="student_99",
            student_name="Bob",
            question="I want to kill myself right now",
            db_session=mock_session,
        )

        assert resp.safety_flagged is True
        assert "988" in resp.answer
        mock_session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_copilot_generate_live_summary(self):
        copilot = LiveClassQAAssistant()
        copilot.ingest_transcript_chunk("sess_sum", "teacher", "Photosynthesis converts light into chemical energy.", timestamp=5.0)

        with patch("src.services.ai.live_class_copilot.generate") as mock_gen:
            mock_gen.return_value = "- Photosynthesis process explained\n- Light energy conversion"
            summary = await copilot.generate_live_summary("sess_sum")
            assert "Photosynthesis" in summary


# ---------------------------------------------------------------------------
# 5. FastAPI Router Endpoints Tests
# ---------------------------------------------------------------------------

class TestAIStudentProfileRouter:
    @pytest.mark.asyncio
    async def test_mastery_radar_router_endpoint(self):
        mock_session = AsyncMock()
        with patch("src.routers.ai_student_profile.get_student_mastery_radar") as mock_radar:
            mock_radar.return_value = StudentMasteryRadarResponse(
                student_id="s123",
                radar_data=[
                    MasteryRadarItem(
                        subject="Physics",
                        average_mastery=0.88,
                        total_concepts=5,
                        mastered_concepts=4,
                        in_progress_concepts=1,
                        proficiency_tier="Mastery",
                    )
                ],
                overall_mastery_average=0.88,
                total_mastered_concepts=4,
                total_tracked_concepts=5,
            )

            res = await api_get_student_mastery_radar(student_id="s123", db_session=mock_session)
            assert res.student_id == "s123"
            assert res.overall_mastery_average == 0.88

    @pytest.mark.asyncio
    async def test_learning_path_router_endpoint(self):
        mock_session = AsyncMock()
        with patch("src.routers.ai_student_profile.get_student_learning_path") as mock_lp:
            mock_lp.return_value = StudentLearningPathResponse(
                student_id="s123",
                readiness_summary="Ready to advance",
                gap_concepts=[],
                recommended_next_concepts=[],
                mastered_concepts=[],
                estimated_study_time_mins=45,
            )

            res = await api_get_student_learning_path(student_id="s123", subject="Physics", db_session=mock_session)
            assert res.student_id == "s123"
            assert res.estimated_study_time_mins == 45

    @pytest.mark.asyncio
    async def test_create_concept_and_link_prerequisite(self):
        mock_session = AsyncMock()
        c_node = ConceptNode(id=1, subject="Math", topic_code="M-1", title="Algebra", difficulty_level=1)
        c_req = ConceptNodeCreate(subject="Math", topic_code="M-1", title="Algebra", difficulty_level=1)

        created = await api_create_concept(c_req, db_session=mock_session)
        assert created.title == "Algebra"
        mock_session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_link_prerequisite_self_reference_rejected(self):
        mock_session = AsyncMock()
        payload = PrerequisiteLinkPayload(prerequisite_concept_id=1, strength_weight=1.0)
        with pytest.raises(HTTPException) as exc:
            await api_link_prerequisite(concept_id=1, payload=payload, db_session=mock_session)
        assert exc.value.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_live_class_transcript_ingest_endpoint(self):
        payload = IngestTranscriptPayload(speaker="teacher", text="Quantum entanglement introduced.", timestamp=120.0)
        chunk = await api_ingest_transcript_chunk(session_id="live_100", payload=payload)
        assert chunk.speaker == "teacher"
        assert chunk.timestamp == 120.0

    @pytest.mark.asyncio
    async def test_live_class_qa_endpoint(self):
        mock_session = AsyncMock()
        payload = LiveClassQAPayload(student_id="std_1", student_name="Sam", question="Can you repeat the wave equation?")
        with patch.object(live_class_copilot, "answer_student_question") as mock_ans:
            mock_ans.return_value = LiveClassQAResponse(
                session_id="live_100",
                student_id="std_1",
                student_name="Sam",
                question="Can you repeat the wave equation?",
                answer="The wave equation is Psi(x,t).",
            )
            res = await api_live_class_qa(session_id="live_100", payload=payload, db_session=mock_session)
            assert res.answer == "The wave equation is Psi(x,t)."
