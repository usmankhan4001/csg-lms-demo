"""
Teacher oversight of AI tutoring (M46).

Lets a teacher or school admin see what students are asking the AI tutor,
review flagged safety incidents, and switch AI tutoring off for a student or
a whole section.

Access is gated to TEACHER/SCHOOL_ADMIN/SUPER_ADMIN throughout: transcripts
are a window onto what children write, so they are staff-only by
construction. Counsellors (PSYCHOLOGIST) are included on the incident view
because crisis follow-up is their job.
"""

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlmodel import SQLModel, col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.events.database import get_db_session
from src.core.keycloak_auth import (
    KeycloakUserPrincipal,
    PSYCHOLOGIST,
    SCHOOL_ADMIN,
    SUPER_ADMIN,
    TEACHER,
    require_roles,
)
from src.db.ai_models import AISafetyIncident
from src.db.ai_oversight import AITutorAccessBlock, AITutorTranscript

router = APIRouter()

_STAFF = [SUPER_ADMIN, SCHOOL_ADMIN, TEACHER]
# Safety incidents are a SAFEGUARDING record, not tutor-quality oversight.
# TEACHER is deliberately excluded: DESIGN-SYSTEM.md requires that where a
# record's EXISTENCE is confidential, other roles get the empty state rather
# than "access denied", and the spec separates the psychologist queue (M42)
# from teacher oversight (M46) precisely here. The student's words were
# already withheld from this response, but listing student_id +
# trigger_category told every teacher in the org THAT a named child had
# disclosed self-harm. Existence is the disclosure.
_SAFEGUARDING = [SUPER_ADMIN, SCHOOL_ADMIN, PSYCHOLOGIST]


class TranscriptRead(SQLModel):
    id: int
    student_id: int
    section_id: Optional[int] = None
    course_id: Optional[str] = None
    prompt: str
    outcome: str
    detail: Optional[str] = None
    created_at: datetime


class AccessBlockRead(SQLModel):
    id: int
    student_id: Optional[int] = None
    section_id: Optional[int] = None
    blocked_by_user_id: int
    reason: Optional[str] = None
    is_active: bool
    created_at: datetime
    lifted_by_user_id: Optional[int] = None
    lifted_at: Optional[datetime] = None


class SafetyIncidentRead(SQLModel):
    id: int
    student_id: str
    severity: str
    trigger_category: str
    counselor_notified: bool
    created_at: str


class CreateBlockRequest(SQLModel):
    student_id: Optional[int] = None
    section_id: Optional[int] = None
    reason: Optional[str] = None


@router.get(
    "/transcripts",
    response_model=List[TranscriptRead],
    summary="List AI Tutor Transcripts",
    description="What students asked the AI tutor, and what the tutor did with it. Staff only.",
)
async def list_transcripts(
    student_id: Optional[int] = Query(None),
    section_id: Optional[int] = Query(None),
    outcome: Optional[str] = Query(None, description="e.g. 'answered', 'blocked_safety'"),
    limit: int = Query(100, le=500),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_STAFF)),
) -> List[AITutorTranscript]:
    query = select(AITutorTranscript)
    if student_id is not None:
        query = query.where(col(AITutorTranscript.student_id) == student_id)
    if section_id is not None:
        query = query.where(col(AITutorTranscript.section_id) == section_id)
    if outcome:
        query = query.where(col(AITutorTranscript.outcome) == outcome)
    if principal.org_id and not principal.is_superadmin:
        query = query.where(col(AITutorTranscript.org_id) == principal.org_id)
    query = query.order_by(col(AITutorTranscript.created_at).desc()).limit(limit)
    result = await session.execute(query)
    return list(result.scalars().all())


@router.get(
    "/incidents",
    response_model=List[SafetyIncidentRead],
    summary="List AI Safety Incidents",
    description="Messages the safety classifier blocked before they reached the model.",
)
async def list_incidents(
    limit: int = Query(100, le=500),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_SAFEGUARDING)),
) -> List[AISafetyIncident]:
    query = select(AISafetyIncident)
    if principal.org_id and not principal.is_superadmin:
        query = query.where(col(AISafetyIncident.org_id) == principal.org_id)
    query = query.order_by(col(AISafetyIncident.created_at).desc()).limit(limit)
    result = await session.execute(query)
    return list(result.scalars().all())


@router.get(
    "/blocks",
    response_model=List[AccessBlockRead],
    summary="List AI Access Blocks",
)
async def list_blocks(
    active_only: bool = Query(True),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_STAFF)),
) -> List[AITutorAccessBlock]:
    query = select(AITutorAccessBlock)
    if active_only:
        query = query.where(col(AITutorAccessBlock.is_active) == True)  # noqa: E712
    if principal.org_id and not principal.is_superadmin:
        query = query.where(col(AITutorAccessBlock.org_id) == principal.org_id)
    result = await session.execute(query.order_by(col(AITutorAccessBlock.created_at).desc()))
    return list(result.scalars().all())


@router.post(
    "/blocks",
    response_model=AccessBlockRead,
    status_code=status.HTTP_201_CREATED,
    summary="Switch AI Tutoring Off (Kill Switch)",
    description=(
        "Blocks AI tutoring for one student or a whole section. Crisis-support "
        "responses are deliberately NOT affected: a blocked student who writes "
        "something alarming still receives hotline resources."
    ),
    responses={400: {"description": "Exactly one of student_id or section_id is required"}},
)
async def create_block(
    payload: CreateBlockRequest = Body(...),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_STAFF)),
) -> AITutorAccessBlock:
    if (payload.student_id is None) == (payload.section_id is None):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide exactly one of student_id or section_id.",
        )

    actor = principal.raw_claims.get("lh_user_id")
    if actor is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not resolve the acting user.",
        )

    block = AITutorAccessBlock(
        org_id=principal.org_id,
        student_id=payload.student_id,
        section_id=payload.section_id,
        blocked_by_user_id=actor,
        reason=payload.reason,
    )
    session.add(block)
    await session.commit()
    await session.refresh(block)
    return block


@router.delete(
    "/blocks/{block_id}",
    response_model=AccessBlockRead,
    summary="Restore AI Tutoring",
    description="Lifts a block. The row is kept and marked inactive so the history of who blocked and who restored survives.",
    responses={404: {"description": "Block not found"}},
)
async def lift_block(
    block_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_STAFF)),
) -> AITutorAccessBlock:
    block = await session.get(AITutorAccessBlock, block_id)
    if block is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Block not found")

    block.is_active = False
    block.lifted_by_user_id = principal.raw_claims.get("lh_user_id")
    block.lifted_at = datetime.now(timezone.utc)
    session.add(block)
    await session.commit()
    await session.refresh(block)
    return block
