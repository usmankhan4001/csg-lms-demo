"""
Live-class attendance bridge: turn join/leave telemetry into register marks.

EXPLICIT, NOT AUTOMATIC -- and that is the safety decision, not an
implementation detail. The obvious alternative is to write the register the
moment a session ends (from `end_live_class_session`, or from the LiveKit
`room_finished` webhook). It is rejected for four reasons:

  1. A live class is ONE LESSON; `StudentAttendance` with `period_id` NULL is
     a WHOLE-DAY register. Auto-writing it would mark a child ABSENT for the
     entire day because they missed one forty-minute online lesson -- and
     would do it to every child in the section at once, with nobody asked.
  2. Telemetry can arrive late. A `participant_left` that lands after the room
     finished would be computed against a session already bridged, so an
     automatic trigger at session end can act on incomplete data. An explicit
     trigger happens after the fact, when the logs are final.
  3. It would overwrite, or collide with, the teacher's own daily mark -- the
     exact conflict the `preserved` rule in the service exists to prevent.
  4. A register is a record a school may have to defend. Somebody has to have
     pressed the button, and the audit trail names them.

So: a teacher or admin triggers it, and can preview it first. The preview and
the write run the SAME computation, so what a teacher is shown is exactly what
the write will do.

Mounted under the same "/live" prefix as live_classes.router -- see router.py.
"""

import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.events.database import get_db_session
from src.core.keycloak_auth import KeycloakUserPrincipal, require_roles
from src.db.sms_attendance import AttendanceStatus
from src.db.sms_campus import Campus, ClassSection
from src.db.sms_live_class import LiveClassSession
from src.schemas.sms_attendance import StudentAttendanceRead
from src.security.school_ownership import (
    assert_owns_section_or_privileged,
    get_user_id,
    require_org_id,
    resolve_scoped_campus_id,
)
from src.services.sms import live_class_attendance as bridge

router = APIRouter()

# Same gate live_classes.py applies to running a class: being staff is not
# permission over every class in the school, so ownership is checked per
# section below.
_BRIDGE_STAFF = ["SUPER_ADMIN", "SCHOOL_ADMIN", "TEACHER"]


# ── Response shapes ──────────────────────────────────────────────────────────


class LiveClassAttendanceComputedRead(BaseModel):
    student_id: int
    active_minutes: float
    session_minutes: float
    attended_percentage: float
    status: AttendanceStatus


class LiveClassAttendanceSkippedRead(BaseModel):
    """A student given NO status. The reason is the point of this field."""

    student_id: int
    reason: str


class LiveClassAttendancePreviewRead(BaseModel):
    """What the bridge WOULD write. Nothing has been written."""

    session_id: int
    section_id: Optional[int] = None
    date: Optional[datetime.date] = None
    session_minutes: Optional[float] = None
    session_minutes_note: Optional[str] = None
    computed: List[LiveClassAttendanceComputedRead] = []
    skipped: List[LiveClassAttendanceSkippedRead] = []


class LiveClassAttendancePreservedRead(BaseModel):
    """A register row the bridge refused to overwrite."""

    student_id: int
    status: AttendanceStatus
    reason: str


class LiveClassAttendanceBridgeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    session_id: int
    section_id: Optional[int] = None
    date: Optional[datetime.date] = None
    session_minutes: Optional[float] = None
    session_minutes_note: Optional[str] = None
    computed: List[LiveClassAttendanceComputedRead] = []
    records: List[StudentAttendanceRead] = []
    preserved: List[LiveClassAttendancePreservedRead] = []
    skipped: List[LiveClassAttendanceSkippedRead] = []


# ── Authorisation ────────────────────────────────────────────────────────────


def _not_found() -> HTTPException:
    """A class the caller is not entitled to is indistinguishable from one
    that does not exist -- never 403, which would confirm it is real."""
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="Live class not found"
    )


async def _load_class_or_404(session: AsyncSession, class_id: int) -> LiveClassSession:
    live = (
        await session.execute(
            select(LiveClassSession).where(LiveClassSession.id == class_id)
        )
    ).scalar_one_or_none()
    if live is None:
        raise _not_found()
    return live


async def _assert_class_in_scope(
    session: AsyncSession,
    principal: KeycloakUserPrincipal,
    live: LiveClassSession,
) -> None:
    """Refuse a class belonging to another school, or another campus of it.

    `LiveClassSession` carries no tenant columns of its own, so tenancy is
    derived section -> campus -> org, the same way live_classes.py does it.
    """
    if principal.is_superadmin:
        return
    org_id = require_org_id(principal)
    row = (
        await session.execute(
            select(ClassSection.campus_id, Campus.org_id)
            .join(Campus, Campus.id == ClassSection.campus_id)
            .where(ClassSection.id == live.section_id)
        )
    ).first()
    if row is None:
        raise _not_found()
    campus_id, class_org = row[0], row[1]
    if class_org != org_id:
        raise _not_found()
    if resolve_scoped_campus_id(principal, campus_id) != campus_id:
        raise _not_found()


async def _authorised_class(
    session: AsyncSession,
    principal: KeycloakUserPrincipal,
    class_id: int,
) -> LiveClassSession:
    live = await _load_class_or_404(session, class_id)
    if live.section_id is None:
        # No section means no register to write to and no roster to check
        # against. Refusing beats inventing one.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "This live class is not attached to a section, so there is no "
                "register to bridge attendance into."
            ),
        )
    await _assert_class_in_scope(session, principal, live)
    await assert_owns_section_or_privileged(principal, live.section_id, session)
    return live


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.get(
    "/classes/{class_id}/attendance/preview",
    response_model=LiveClassAttendancePreviewRead,
    summary="Preview Live Class Attendance",
    description=(
        "What the attendance bridge WOULD write into the daily register for "
        "this class: each student's active minutes, their percentage of the "
        "scheduled session, and the status that follows from the 80% "
        "threshold. Writes nothing. Students with no telemetry, or with "
        "incomplete telemetry, are listed as skipped with the reason rather "
        "than being given a percentage."
    ),
)
async def preview_live_class_attendance(
    class_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_BRIDGE_STAFF)),
) -> LiveClassAttendancePreviewRead:
    live = await _authorised_class(session, principal, class_id)
    plan = await bridge.compute_session_attendance(session, live)
    return LiveClassAttendancePreviewRead(
        session_id=plan.session_id,
        section_id=plan.section_id,
        date=plan.date,
        session_minutes=plan.session_minutes,
        session_minutes_note=plan.session_minutes_note,
        computed=[
            LiveClassAttendanceComputedRead(
                student_id=c.student_id,
                active_minutes=c.active_minutes,
                session_minutes=c.session_minutes,
                attended_percentage=c.attended_percentage,
                status=c.status,
            )
            for c in plan.computed
        ],
        skipped=[
            LiveClassAttendanceSkippedRead(student_id=s.student_id, reason=s.reason)
            for s in plan.skipped
        ],
    )


@router.post(
    "/classes/{class_id}/attendance/bridge",
    response_model=LiveClassAttendanceBridgeRead,
    summary="Bridge Live Class Attendance into the Register",
    description=(
        "Writes each attending student's computed status into the daily "
        "attendance register for this class's section and date. Idempotent: "
        "re-running updates the same rows instead of adding new ones. A row "
        "already marked for that student and date by anyone other than this "
        "live class is NEVER overwritten -- it is returned under `preserved`."
    ),
)
async def bridge_live_class_attendance(
    class_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_BRIDGE_STAFF)),
) -> LiveClassAttendanceBridgeRead:
    live = await _authorised_class(session, principal, class_id)
    result = await bridge.bridge_session_attendance(
        session, live, actor_user_id=get_user_id(principal)
    )
    return LiveClassAttendanceBridgeRead(
        session_id=result.session_id,
        section_id=result.section_id,
        date=result.date,
        session_minutes=result.session_minutes,
        session_minutes_note=result.session_minutes_note,
        computed=[
            LiveClassAttendanceComputedRead(
                student_id=c.student_id,
                active_minutes=c.active_minutes,
                session_minutes=c.session_minutes,
                attended_percentage=c.attended_percentage,
                status=c.status,
            )
            for c in result.computed
        ],
        records=[StudentAttendanceRead.model_validate(r) for r in result.records],
        preserved=[
            LiveClassAttendancePreservedRead(
                student_id=p.student_id, status=p.status, reason=p.reason
            )
            for p in result.preserved
        ],
        skipped=[
            LiveClassAttendanceSkippedRead(student_id=s.student_id, reason=s.reason)
            for s in result.skipped
        ],
    )
