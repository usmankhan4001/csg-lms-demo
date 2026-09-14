"""
Parent AI Weekly Digest & Progress Synthesis Router (M48).

Synthesizes student attendance, assignment submissions, cognitive strengths, and AI tutor dialogue
into an actionable, parent-friendly weekly progress narrative.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.events.database import get_db_session
from src.core.keycloak_auth import (
    KeycloakUserPrincipal,
    PARENT,
    SCHOOL_ADMIN,
    SUPER_ADMIN,
    TEACHER,
    get_current_user_principal,
)
from src.security.school_ownership import require_own_student_or_privileged
from src.services.ai.parent_digest import compute_weekly_digest

router = APIRouter()


class ParentWeeklyDigestResponse(BaseModel):
    student_id: int
    week_start: str
    week_end: str
    # Fields removed rather than faked: assignments_completed/pending,
    # average_weekly_score, top_strengths, growth_areas, parent_action_items
    # and teacher_praise had no data source at all. An empty list would still
    # imply "we looked and found none"; absence is the honest signal.
    attendance_rate: str
    classes_attended: int
    total_classes: int
    tutor_sessions: int
    ai_tutor_topics_explored: List[str]
    conversational_summary: str
    generated_at: str


@router.get(
    "/students/{student_id}/digest",
    response_model=ParentWeeklyDigestResponse,
    summary="Generate Parent AI Weekly Digest (M48)",
    description="Compiles weekly student attendance, grades, AI tutor interactions, and highlights into a parent summary.",
)
async def get_parent_weekly_digest(
    student_id: int,
    principal: KeycloakUserPrincipal = Depends(require_own_student_or_privileged()),
    session: AsyncSession = Depends(get_db_session),
) -> ParentWeeklyDigestResponse:
    now = datetime.now(timezone.utc)
    digest = await compute_weekly_digest(session, student_id)

    # Every field below is derived from real rows or omitted. Nothing is
    # defaulted to a flattering value: a week with no attendance recorded
    # reports "not recorded", never a healthy-looking percentage. This
    # endpoint previously returned hardcoded figures -- 96% attendance, a
    # 92% average, even invented teacher praise -- identically for every
    # student, ignoring student_id entirely. Harmless while unshipped;
    # actively harmful the moment a parent reads it about their own child.
    attendance_pct = digest.attendance_rate
    return ParentWeeklyDigestResponse(
        student_id=student_id,
        week_start=digest.week_start.isoformat(),
        week_end=digest.week_end.isoformat(),
        attendance_rate=f"{attendance_pct}%" if attendance_pct is not None else "Not recorded",
        classes_attended=digest.days_present + digest.days_excused,
        total_classes=digest.days_recorded,
        tutor_sessions=digest.tutor_sessions,
        ai_tutor_topics_explored=digest.topics,
        conversational_summary=(
            f"{digest.student_name} has {digest.days_recorded} attendance "
            f"record(s) this week"
            + (f" ({attendance_pct}% attendance)" if attendance_pct is not None else "")
            + (
                f" and {digest.tutor_sessions} AI tutor session(s)."
                if digest.tutor_sessions
                else " and no AI tutor activity."
            )
        ),
        generated_at=now.isoformat(),
    )
