"""
Student 360 Mastery Profile & Concept Knowledge Graph Router (M44, M45, M50)
=============================================================================
Provides endpoints for Student 360 Mastery Radar, dynamic personalized learning paths,
Bayesian mastery evaluation, Concept Knowledge Graph DAG traversal, and Live Class Copilot.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlmodel import select, col
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.events.database import get_db_session
from src.core.keycloak_auth import (
    KeycloakUserPrincipal,
    TEACHER,
    SCHOOL_ADMIN,
    SUPER_ADMIN,
    STUDENT,
    get_optional_user_principal,
    require_roles,
)
from src.db.ai_knowledge_graph import (
    ConceptNode,
    ConceptNodeCreate,
    ConceptNodeRead,
    ConceptPrerequisite,
    ConceptPrerequisiteCreate,
    ConceptPrerequisiteRead,
    StudentConceptMastery,
    StudentConceptMasteryRead,
    MasteryEvaluationInput,
    StudentMasteryRadarResponse,
    StudentLearningPathResponse,
)
from src.services.ai.knowledge_graph import (
    evaluate_mastery_update,
    get_concept_dependency_path,
    get_recommended_next_concepts,
    get_student_mastery_radar,
    get_student_learning_path,
)
from src.services.ai.live_class_copilot import (
    live_class_copilot,
    LiveClassQAResponse,
)

router = APIRouter(tags=["student-profile", "ai-knowledge-graph"])


# ---------------------------------------------------------------------------
# Live Class Copilot Payload Schemas
# ---------------------------------------------------------------------------

class IngestTranscriptPayload(BaseModel):
    speaker: str = Field(default="teacher", description="Speaker name or role (e.g. teacher, student)")
    text: str = Field(..., description="Transcribed speech text")
    timestamp: Optional[float] = Field(default=None, description="Playback timestamp in seconds")
    course_id: Optional[str] = Field(default=None, description="Course ID or UUID")


class LiveClassQAPayload(BaseModel):
    student_id: str
    student_name: str = "Student"
    question: str
    course_id: Optional[str] = None
    model_name: Optional[str] = None


class PrerequisiteLinkPayload(BaseModel):
    prerequisite_concept_id: int
    strength_weight: float = Field(default=1.0, ge=0.0, le=1.0)


# ---------------------------------------------------------------------------
# 1. Student 360 Mastery Radar & Learning Path (M45)
# ---------------------------------------------------------------------------

@router.get(
    "/student/{student_id}/mastery-radar",
    response_model=StudentMasteryRadarResponse,
    summary="Student 360 Subject Mastery Radar",
    description="Returns aggregated radar chart mastery metrics across all academic subjects.",
)
async def api_get_student_mastery_radar(
    student_id: str,
    db_session: AsyncSession = Depends(get_db_session),
    principal: Optional[KeycloakUserPrincipal] = Depends(get_optional_user_principal),
):
    """
    GET /api/v1/ai/student/{student_id}/mastery-radar
    """
    return await get_student_mastery_radar(student_id=student_id, db_session=db_session)


@router.get(
    "/student/{student_id}/learning-path",
    response_model=StudentLearningPathResponse,
    summary="Dynamic Personalized Learning Path & Gap Analysis",
    description="Identifies mastery deficits, foundational gaps, and unlocked next concepts.",
)
async def api_get_student_learning_path(
    student_id: str,
    subject: Optional[str] = Query(None, description="Optional subject filter"),
    db_session: AsyncSession = Depends(get_db_session),
    principal: Optional[KeycloakUserPrincipal] = Depends(get_optional_user_principal),
):
    """
    GET /api/v1/ai/student/{student_id}/learning-path
    """
    return await get_student_learning_path(
        student_id=student_id,
        db_session=db_session,
        subject=subject,
    )


@router.post(
    "/student/{student_id}/mastery-evaluation",
    response_model=StudentConceptMasteryRead,
    summary="Evaluate and Update Student Concept Mastery",
    description="Applies Bayesian/EMA update to student mastery score following a quiz or assessment.",
)
async def api_evaluate_mastery_update(
    student_id: str,
    payload: MasteryEvaluationInput,
    db_session: AsyncSession = Depends(get_db_session),
    principal: Optional[KeycloakUserPrincipal] = Depends(get_optional_user_principal),
):
    """
    POST /api/v1/ai/student/{student_id}/mastery-evaluation
    """
    updated_mastery = await evaluate_mastery_update(
        student_id=student_id,
        concept_id=payload.concept_id,
        quiz_score=payload.quiz_score,
        difficulty=payload.difficulty,
        db_session=db_session,
    )
    return updated_mastery


@router.get(
    "/student/{student_id}/recommended-concepts",
    summary="Get Recommended Next Concepts for Student",
    description="Returns top unlocked concepts where all prerequisites are satisfied.",
)
async def api_get_recommended_concepts(
    student_id: str,
    subject: Optional[str] = Query(None, description="Optional subject filter"),
    limit: int = Query(5, ge=1, le=20),
    db_session: AsyncSession = Depends(get_db_session),
):
    """
    GET /api/v1/ai/student/{student_id}/recommended-concepts
    """
    return await get_recommended_next_concepts(
        student_id=student_id,
        subject=subject,
        db_session=db_session,
        limit=limit,
    )


# ---------------------------------------------------------------------------
# 2. Concept Knowledge Graph Endpoints (M44)
# ---------------------------------------------------------------------------

@router.get(
    "/concepts",
    response_model=List[ConceptNodeRead],
    summary="List Knowledge Graph Concept Nodes",
    description="List all registered concept nodes with optional subject and difficulty filters.",
)
async def api_list_concepts(
    subject: Optional[str] = Query(None, description="Filter by subject"),
    topic_code: Optional[str] = Query(None, description="Filter by topic code"),
    difficulty: Optional[int] = Query(None, ge=1, le=5, description="Filter by difficulty level"),
    db_session: AsyncSession = Depends(get_db_session),
):
    stmt = select(ConceptNode)
    if subject:
        stmt = stmt.where(col(ConceptNode.subject) == subject)
    if topic_code:
        stmt = stmt.where(col(ConceptNode.topic_code) == topic_code)
    if difficulty:
        stmt = stmt.where(col(ConceptNode.difficulty_level) == difficulty)

    stmt = stmt.order_by(col(ConceptNode.id))
    result = await db_session.execute(stmt)
    return result.scalars().all()


@router.post(
    "/concepts",
    response_model=ConceptNodeRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create Concept Knowledge Graph Node",
    description="Register a new academic concept in the knowledge graph.",
)
async def api_create_concept(
    payload: ConceptNodeCreate,
    db_session: AsyncSession = Depends(get_db_session),
):
    node = ConceptNode(
        subject=payload.subject,
        topic_code=payload.topic_code,
        title=payload.title,
        description=payload.description,
        difficulty_level=payload.difficulty_level,
        embedding=payload.embedding,
    )
    db_session.add(node)
    await db_session.commit()
    await db_session.refresh(node)
    return node


@router.get(
    "/concepts/{concept_id}/dependency-path",
    response_model=List[ConceptNodeRead],
    summary="Get Concept Dependency & Prerequisite Path",
    description="Returns topologically ordered prerequisite graph path required to master this concept.",
)
async def api_get_concept_dependency_path(
    concept_id: int,
    db_session: AsyncSession = Depends(get_db_session),
):
    path = await get_concept_dependency_path(target_concept_id=concept_id, db_session=db_session)
    return path


@router.post(
    "/concepts/{concept_id}/prerequisites",
    response_model=ConceptPrerequisiteRead,
    status_code=status.HTTP_201_CREATED,
    summary="Link Prerequisite Concept",
    description="Creates a directed prerequisite dependency edge between two concepts.",
)
async def api_link_prerequisite(
    concept_id: int,
    payload: PrerequisiteLinkPayload,
    db_session: AsyncSession = Depends(get_db_session),
):
    if concept_id == payload.prerequisite_concept_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A concept cannot be a prerequisite of itself.",
        )

    # Check existence
    c1 = await db_session.get(ConceptNode, concept_id)
    c2 = await db_session.get(ConceptNode, payload.prerequisite_concept_id)
    if not c1 or not c2:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or both concept IDs do not exist.",
        )

    edge = ConceptPrerequisite(
        concept_id=concept_id,
        prerequisite_concept_id=payload.prerequisite_concept_id,
        strength_weight=payload.strength_weight,
    )
    db_session.add(edge)
    await db_session.commit()
    await db_session.refresh(edge)
    return edge


# ---------------------------------------------------------------------------
# 3. Live Class AI Q&A Copilot Endpoints (M50)
# ---------------------------------------------------------------------------

@router.post(
    "/live-class/{session_id}/transcript",
    summary="Ingest Live Speech Transcript Chunk",
    description="Appends transcribed teacher or student speech into the active live class buffer.",
)
async def api_ingest_transcript_chunk(
    session_id: str,
    payload: IngestTranscriptPayload,
):
    chunk = live_class_copilot.ingest_transcript_chunk(
        session_id=session_id,
        speaker=payload.speaker,
        text=payload.text,
        timestamp=payload.timestamp,
        course_id=payload.course_id,
    )
    return chunk


@router.post(
    "/live-class/{session_id}/qa",
    response_model=LiveClassQAResponse,
    summary="Ask Live Class AI Copilot",
    description="Answers student in-stream questions grounded in the teacher's recent live explanations.",
)
async def api_live_class_qa(
    session_id: str,
    payload: LiveClassQAPayload,
    db_session: AsyncSession = Depends(get_db_session),
):
    response = await live_class_copilot.answer_student_question(
        session_id=session_id,
        student_id=payload.student_id,
        student_name=payload.student_name,
        question=payload.question,
        course_id=payload.course_id,
        db_session=db_session,
        model_name=payload.model_name,
    )
    return response


@router.get(
    "/live-class/{session_id}/summary",
    summary="Generate Live Class Recap Summary",
    description="Provides real-time bullet points summarizing key concepts covered so far.",
)
async def api_live_class_summary(
    session_id: str,
):
    summary = await live_class_copilot.generate_live_summary(session_id=session_id)
    return {"session_id": session_id, "summary": summary}
