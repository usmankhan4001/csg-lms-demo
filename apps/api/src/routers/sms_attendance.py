import calendar
import datetime
import logging
from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, extract, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.events.database import get_db_session
from src.core.keycloak_auth import (
    KeycloakUserPrincipal,
    PSYCHOLOGIST,
    SCHOOL_ADMIN,
    SUPER_ADMIN,
    TEACHER,
    get_current_user_principal,
    require_roles,
)
from src.db.sms_attendance import (
    AbsenceExcuse,
    AttendanceChangeAction,
    AttendanceLeaveRequest,
    AttendanceStatus,
    ExcuseStatus,
    LeaveRequestStatus,
    PastoralConcern,
    PastoralConcernStatus,
    PastoralIntervention,
    StudentAttendance,
)
from src.schemas.sms_attendance import (
    AbsenceExcuseCreate,
    AbsenceExcuseRead,
    AbsenceExcuseReview,
    AbsenceExcuseReviewResponse,
    AttendanceChangeEventRead,
    BatchRollCallRequest,
    BulkMarkRangeRequest,
    BulkMarkRangeResponse,
    BulkMarkSkipped,
    PastoralConcernRead,
    PastoralConcernUpdate,
    PastoralInterventionCreate,
    PastoralInterventionRead,
    BatchRollCallResponse,
    LeaveRequestCreate,
    LeaveRequestRead,
    LeaveRequestUpdateStatus,
    MonthlyAttendanceStats,
    MonthlyStudentAttendanceSheet,
    StudentAttendanceRead,
)
from src.security.features_utils.dependencies import require_sms_attendance_feature
from src.security.school_ownership import (
    assert_owns_section_or_privileged,
    get_own_children_ids,
    get_own_teacher_section_ids,
    require_own_student_or_privileged,
)
from src.services.webhooks.dispatch import dispatch_event_task

from src.services.notifications import resolve_guardians_of
from src.services.sms.attendance import (
    ABSENCE_STREAK_THRESHOLD,
    collapse_to_daily_status,
    get_consecutive_absence_streak,
)
from src.services.sms.school_events import (
    ABSENCE_RECORDED,
    ABSENCE_STREAK,
    EXCUSE_REVIEWED,
    raise_school_event,
    student_display_name,
)
from src.services.sms.attendance_pastoral import (
    apply_approved_excuse,
    get_attendance_history,
    list_interventions,
    list_pastoral_concerns,
    raise_absence_concern,
    record_attendance_change,
)

logger = logging.getLogger(__name__)

# Approving or rejecting a leave request is a staff decision. Unguarded, this
# endpoint let a STUDENT approve their own leave.
_LEAVE_APPROVERS = [TEACHER, SCHOOL_ADMIN, SUPER_ADMIN]

# Reviewing a parent's absence note is a staff judgement, and approving one
# CHANGES the child's attendance percentage -- so it is a write, not a
# formality. A teacher may review notes for a section they teach (enforced
# per-section below); admins may review any.
_EXCUSE_REVIEWERS = [TEACHER, SCHOOL_ADMIN, SUPER_ADMIN]

# Pastoral concerns name a child the school is worried about.
#
# THE GATING DECISION, and it differs deliberately from ai_oversight's
# _SAFEGUARDING (which excludes TEACHER entirely). A teacher IS included here,
# but ONLY for sections they actually teach -- enforced by
# `_pastoral_section_scope` below, not by the role list.
#
# The distinction is what the record discloses. An AI safety incident reveals
# something a child typed in private that they never told their teacher; its
# existence is the disclosure, so a teacher learning of it learns something new
# about a child's inner life. An absence streak is the opposite: the teacher
# MARKED those registers. They already know the child has not been in. Hiding
# the pastoral flag from them would withhold the prompt to act from the one
# adult who sees the child daily -- and a form tutor chasing an absent tutee is
# the most basic pastoral duty a school has.
#
# What a teacher must NOT get is the whole school's at-risk list, which is a
# different thing entirely: that is browsing other people's children. Hence
# role-permitted but section-scoped.
_PASTORAL_VIEWERS = [TEACHER, SCHOOL_ADMIN, SUPER_ADMIN, PSYCHOLOGIST]

# Bulk-marking a date range for a whole section is an administrative act (a
# trip, a closure). A teacher may do it for their own section; ownership is
# enforced per-section as with roll-call.
_BULK_MARKERS = [TEACHER, SCHOOL_ADMIN, SUPER_ADMIN]


async def _guardians_for_notification(
    session: AsyncSession, student_id: int, section_id: int
) -> list:
    """The student's guardians, or an empty list if we cannot establish them.

    Separated out so that a lookup failure is logged once, here, rather than
    being conflated with a delivery failure at the call site. An absent child
    with no guardian link is a real data gap a school needs to close -- it is
    logged at warning rather than passed over, because the silent version of
    this is a family who is never told anything and nobody noticing.
    """
    try:
        guardians = await resolve_guardians_of(session, student_id)
    except Exception:
        logger.warning(
            "Could not resolve guardians for student %s in section %s; "
            "no absence notification will be sent.",
            student_id,
            section_id,
            exc_info=True,
        )
        return []
    if not guardians:
        logger.warning(
            "Student %s was marked absent but has no linked guardian, so "
            "nobody can be told.",
            student_id,
        )
    return guardians


async def _pastoral_section_scope(
    principal: KeycloakUserPrincipal,
    session: AsyncSession,
) -> Optional[List[int]]:
    """Which sections' pastoral concerns this caller may see.

    Returns None for "unrestricted" and a list for "these sections only". An
    EMPTY list is meaningful and must not be confused with None: it means a
    teacher who owns no sections, and they must see nothing rather than
    everything. `list_pastoral_concerns` honours that distinction.
    """
    if principal.is_superadmin or principal.has_any_role([SCHOOL_ADMIN, PSYCHOLOGIST]):
        return None

    user_id = (principal.raw_claims or {}).get("lh_user_id")
    if user_id is None:
        return []
    return await get_own_teacher_section_ids(user_id, session)

router = APIRouter(dependencies=[Depends(require_sms_attendance_feature)])


async def _assert_may_file_leave_for(
    principal: KeycloakUserPrincipal,
    student_id: int,
    session: AsyncSession,
) -> None:
    """A leave request may only be filed for yourself or your own child.

    Staff (SCHOOL_ADMIN/SUPER_ADMIN, and a teacher of that student's section)
    may file on a family's behalf; everyone else is limited to their own
    record. Reuses `get_own_children_ids` rather than reimplementing the
    guardian lookup.
    """
    if principal.is_superadmin or principal.has_any_role([SCHOOL_ADMIN, TEACHER]):
        return

    user_id = (principal.raw_claims or {}).get("lh_user_id")
    if user_id is not None:
        if student_id == user_id:
            return
        if student_id in await get_own_children_ids(user_id, session):
            return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You can only submit a leave request for yourself or your own child.",
    )


# ── 1-Click Batch Roll-Call ──

@router.post(
    "/roll-call",
    response_model=BatchRollCallResponse,
    status_code=status.HTTP_200_OK,
    summary="1-Click Batch Roll-Call Attendance",
    description="Record or update attendance for all students in a section on a given date.",
)
async def submit_batch_roll_call(
    payload: BatchRollCallRequest,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> BatchRollCallResponse:
    """
    Submits batch roll-call attendance. Upserts on
    (student_id, section_id, date, period_id).

    `payload.period_id` is the whole point of the period_id column: with it,
    the lookup below matches only rows for THAT period, so taking period 5's
    register leaves period 1's alone. Without it (the day-level model) the
    lookup matches only rows with a NULL period, so a day register never
    collides with a period register either.

    This read-then-write is also what enforces DAY-level uniqueness: the
    table's unique constraint spans the nullable `period_id`, and NULL != NULL
    means PostgreSQL will happily accept two day rows for the same student
    and date. See the note in db/sms_attendance.py.
    """
    if not payload.entries:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Roll-call entries list cannot be empty.",
        )

    # section_id only exists once the body is parsed, so this can't be a
    # plain path/query dependency like require_own_student_or_privileged --
    # see school_ownership.py's module docstring.
    await assert_owns_section_or_privileged(principal, payload.section_id, session)

    student_ids = [entry.student_id for entry in payload.entries]

    # Fetch existing records for this section, date AND period. `.is_(None)`
    # rather than `== None` so the day-level case emits `IS NULL` explicitly.
    period_match = (
        StudentAttendance.period_id.is_(None)
        if payload.period_id is None
        else StudentAttendance.period_id == payload.period_id
    )
    stmt = select(StudentAttendance).where(
        and_(
            StudentAttendance.section_id == payload.section_id,
            StudentAttendance.date == payload.date,
            StudentAttendance.student_id.in_(student_ids),
            period_match,
        )
    )
    result = await session.execute(stmt)
    existing_map = {att.student_id: att for att in result.scalars().all()}

    saved_records: List[StudentAttendance] = []
    absent_student_ids: List[int] = []
    # (record, action, previous_status) -- history rows are built after the
    # flush below, once new rows have their primary keys.
    pending_history: List[tuple] = []

    # Attribution follows the AUTHENTICATED caller. `payload.marked_by` is
    # client-supplied and stays on the live row for display, but the audit
    # trail must not be forgeable -- the same distinction the gradebook trail
    # draws between `graded_by` and `changed_by_user_id`.
    actor_id = (principal.raw_claims or {}).get("lh_user_id")

    for entry in payload.entries:
        if entry.status == AttendanceStatus.ABSENT:
            absent_student_ids.append(entry.student_id)

        if entry.student_id in existing_map:
            # Update existing attendance row
            att = existing_map[entry.student_id]
            previous_status = att.status
            att.status = entry.status
            att.remarks = entry.remarks
            if payload.marked_by is not None:
                att.marked_by = payload.marked_by
            session.add(att)
            saved_records.append(att)
            # Only a genuine change is a correction. Re-submitting an
            # unchanged register (a teacher pressing save twice) must not
            # fill the trail with noise that hides the real corrections.
            if previous_status != entry.status:
                pending_history.append(
                    (att, AttendanceChangeAction.CORRECTED, previous_status)
                )
        else:
            # Insert new attendance row
            new_att = StudentAttendance(
                student_id=entry.student_id,
                section_id=payload.section_id,
                date=payload.date,
                period_id=payload.period_id,
                status=entry.status,
                marked_by=payload.marked_by,
                remarks=entry.remarks,
            )
            session.add(new_att)
            saved_records.append(new_att)
            pending_history.append((new_att, AttendanceChangeAction.MARKED, None))

    # Flush so newly inserted rows have primary keys, then write the trail into
    # the SAME transaction as the registers themselves: a crash cannot leave a
    # register changed with no record of who changed it.
    await session.flush()
    for record, action, previous_status in pending_history:
        record_attendance_change(
            session,
            attendance=record,
            action=action,
            previous_status=previous_status,
            changed_by_user_id=actor_id,
            reason=payload.reason,
        )

    await session.commit()
    for rec in saved_records:
        await session.refresh(rec)

    # Dispatch attendance.recorded webhook
    try:
        org_id = (principal.raw_claims or {}).get("org_id") or 1
        present_cnt = sum(1 for e in payload.entries if e.status == AttendanceStatus.PRESENT)
        absent_cnt = sum(1 for e in payload.entries if e.status == AttendanceStatus.ABSENT)
        tardy_cnt = sum(1 for e in payload.entries if e.status == AttendanceStatus.LATE)
        
        dispatch_event_task(
            org_id=org_id,
            event_name="attendance.recorded",
            data={
                "date": payload.date.isoformat() if hasattr(payload.date, "isoformat") else str(payload.date),
                "campus_id": 1,
                "section_id": payload.section_id,
                "period_number": payload.period_id or 1,
                "total_students": len(payload.entries),
                "present_count": present_cnt,
                "absent_count": absent_cnt,
                "tardy_count": tardy_cnt,
            },
        )
    except Exception as e:
        logger.warning("Failed to dispatch attendance.recorded webhook: %s", e)


    # Absence-streak alerts are supplementary: the attendance record itself is
    # already committed above and is the record of truth. A notification
    # failure (mail provider down, guardian row missing) must never fail the
    # teacher's roll-call submission -- but it must not vanish silently
    # either, or a permanently broken alert path would look healthy.
    for s_id in absent_student_ids:
        # ORDER MATTERS HERE, and it is the whole point of the pastoral queue.
        #
        # The DURABLE record is written first, in its own try block. The
        # guardian email is emitted second, in a separate one. Previously the
        # only escalation was that email, so with mail unconfigured -- the
        # default -- a detected streak reached nobody and left no trace.
        # Recording the concern inside the same try as the emit would have
        # rebuilt exactly that failure: a mail outage would take the durable
        # record down with it.
        streak = 0
        try:
            streak = await get_consecutive_absence_streak(session, s_id, payload.section_id)
            if streak >= ABSENCE_STREAK_THRESHOLD:
                await raise_absence_concern(
                    session,
                    student_id=s_id,
                    section_id=payload.section_id,
                    streak=streak,
                )
                await session.commit()
        except Exception:
            logger.warning(
                "Pastoral concern could not be recorded for student %s in section %s",
                s_id,
                payload.section_id,
                exc_info=True,
            )

        # Tell the family. Every raise below goes through `raise_school_event`,
        # which cannot propagate: the register above is already committed and
        # is the record of truth, so a mail outage must never turn into a 500
        # on a teacher's roll-call.
        #
        # WHY THIS REPLACED `bus.emit("student.absence_streak", ...)`:
        # the in-process bus delivered mail correctly -- its subscriber is
        # registered at import, so every worker has it, and emit and handler
        # share a process. What it could not do is anything the fabric exists
        # for. It bypassed preferences (a parent could not switch it off),
        # duplicate suppression (re-saving a register re-sent it), and the
        # delivery log (nobody could answer "was the family actually told?").
        # It also wrote no in-app copy, so the only record of the message was
        # in the parent's inbox.
        guardians = await _guardians_for_notification(session, s_id, payload.section_id)
        if guardians:
            student_name = await student_display_name(session, s_id)
            # A student absent for several days running gets the streak
            # message INSTEAD of the daily one, not as well as it. Two emails
            # in one minute saying the same thing in different words is how a
            # school teaches a family to stop reading.
            if streak >= ABSENCE_STREAK_THRESHOLD:
                await raise_school_event(
                    session,
                    event_key=ABSENCE_STREAK.key,
                    org_id=principal.org_id,
                    recipients=guardians,
                    context={"student_name": student_name, "streak": streak},
                    campus_id=principal.campus_id,
                    related_kind="student",
                    related_id=s_id,
                )
            else:
                await raise_school_event(
                    session,
                    event_key=ABSENCE_RECORDED.key,
                    org_id=principal.org_id,
                    recipients=guardians,
                    context={
                        "student_name": student_name,
                        "date": payload.date.isoformat(),
                    },
                    campus_id=principal.campus_id,
                    related_kind="student",
                    related_id=s_id,
                )

    return BatchRollCallResponse(
        success=True,
        section_id=payload.section_id,
        date=payload.date,
        period_id=payload.period_id,
        total_submitted=len(payload.entries),
        total_recorded=len(saved_records),
        records=[StudentAttendanceRead.model_validate(rec) for rec in saved_records],
    )


# ── Monthly Student Attendance Sheet ──

@router.get(
    "/student/{student_id}/monthly",
    response_model=MonthlyStudentAttendanceSheet,
    summary="Monthly Student Attendance Sheet",
    description="Calculate aggregated statistics and list daily attendance logs for a student in a specific month.",
)
async def get_monthly_student_attendance(
    student_id: int,
    year: int = Query(..., ge=2000, le=2100, description="Calendar Year (e.g. 2026)"),
    month: int = Query(..., ge=1, le=12, description="Month (1-12)"),
    section_id: Optional[int] = Query(None, description="Optional Section ID filter"),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_own_student_or_privileged()),
) -> MonthlyStudentAttendanceSheet:
    """
    Generates institutional monthly attendance breakdown & weighted attendance percentage.
    """
    conditions = [
        StudentAttendance.student_id == student_id,
        extract("year", StudentAttendance.date) == year,
        extract("month", StudentAttendance.date) == month,
    ]
    if isinstance(section_id, int):
        conditions.append(StudentAttendance.section_id == section_id)

    stmt = (
        select(StudentAttendance)
        .where(and_(*conditions))
        .order_by(StudentAttendance.date.asc())
    )
    result = await session.execute(stmt)
    records = result.scalars().all()

    # Stats are in DAYS, so collapse period records to one verdict per date
    # first -- six periods a day would otherwise report a 30-day month as 180
    # days. `daily_records` below stays raw, so the caller can still see each
    # period; only the totals are per-day.
    daily_statuses = list(collapse_to_daily_status(records).values())

    total_days = len(daily_statuses)
    present_days = sum(1 for s in daily_statuses if s == AttendanceStatus.PRESENT)
    absent_days = sum(1 for s in daily_statuses if s == AttendanceStatus.ABSENT)
    late_days = sum(1 for s in daily_statuses if s == AttendanceStatus.LATE)
    excused_days = sum(1 for s in daily_statuses if s == AttendanceStatus.EXCUSED)

    # Standard SMS Formula: (Present + 0.5 * Late + Excused) / Total * 100
    if total_days > 0:
        effective_present = present_days + (0.5 * late_days) + excused_days
        percentage = round((effective_present / total_days) * 100.0, 2)
    else:
        # None, NOT 0.0. With no roll-call taken, "0%" reads to a parent as
        # "my child attended nothing" -- the opposite of the truth, which is
        # that nobody has marked a register yet. This codebase has torn out
        # the same no-data-reads-as-a-real-figure pattern three times (a 4.0
        # GPA for a student with no grades, an invented parent digest, and a
        # fabricated "F" on a report card). Absence is not zero.
        percentage = None

    stats = MonthlyAttendanceStats(
        total_days=total_days,
        present_days=present_days,
        absent_days=absent_days,
        late_days=late_days,
        excused_days=excused_days,
        attendance_percentage=percentage,
    )

    return MonthlyStudentAttendanceSheet(
        student_id=student_id,
        section_id=section_id,
        year=year,
        month=month,
        stats=stats,
        daily_records=[StudentAttendanceRead.model_validate(r) for r in records],
    )


# ── Leave Requests ──

@router.post(
    "/leave-requests",
    response_model=LeaveRequestRead,
    status_code=status.HTTP_201_CREATED,
    summary="Submit Student Leave Request",
    description="Submit a new student leave request.",
)
async def submit_leave_request(
    payload: LeaveRequestCreate,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> LeaveRequestRead:
    # Submitting is deliberately open to students and parents -- but only for
    # themselves or their own child. `payload.student_id` was previously
    # trusted outright, so any authenticated user could file leave in any
    # student's name.
    await _assert_may_file_leave_for(principal, payload.student_id, session)

    if payload.end_date < payload.start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="end_date cannot be earlier than start_date.",
        )

    leave_request = AttendanceLeaveRequest(
        student_id=payload.student_id,
        start_date=payload.start_date,
        end_date=payload.end_date,
        reason=payload.reason,
        status=LeaveRequestStatus.PENDING,
    )
    session.add(leave_request)
    await session.commit()
    await session.refresh(leave_request)
    return LeaveRequestRead.model_validate(leave_request)


@router.get(
    "/leave-requests",
    response_model=List[LeaveRequestRead],
    summary="List Student Leave Requests",
    description="Retrieve leave requests filtered by student or status.",
)
async def list_leave_requests(
    student_id: Optional[int] = Query(None, description="Filter by Student ID"),
    status_filter: Optional[LeaveRequestStatus] = Query(None, alias="status", description="Filter by status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> List[LeaveRequestRead]:
    conditions = []
    if isinstance(student_id, int):
        conditions.append(AttendanceLeaveRequest.student_id == student_id)
    if isinstance(status_filter, (LeaveRequestStatus, str)):
        conditions.append(AttendanceLeaveRequest.status == status_filter)

    limit_val = limit if isinstance(limit, int) else 50
    offset_val = offset if isinstance(offset, int) else 0

    stmt = (
        select(AttendanceLeaveRequest)
        .where(and_(*conditions))
        .order_by(AttendanceLeaveRequest.created_at.desc())
        .offset(offset_val)
        .limit(limit_val)
    )
    result = await session.execute(stmt)
    records = result.scalars().all()
    return [LeaveRequestRead.model_validate(r) for r in records]


@router.patch(
    "/leave-requests/{request_id}/status",
    response_model=LeaveRequestRead,
    summary="Approve or Reject Leave Request",
    description="Update the lifecycle status of a student leave request.",
)
async def update_leave_request_status(
    request_id: int,
    payload: LeaveRequestUpdateStatus,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_LEAVE_APPROVERS)),
) -> LeaveRequestRead:
    stmt = select(AttendanceLeaveRequest).where(AttendanceLeaveRequest.id == request_id)
    result = await session.execute(stmt)
    leave_request = result.scalar_one_or_none()
    if not leave_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Leave request with ID {request_id} not found.",
        )

    leave_request.status = payload.status
    # Attribution follows the authenticated approver, not the request body:
    # `approved_by` was client-supplied, so an approval could be recorded
    # against someone who never made it.
    approver_id = (principal.raw_claims or {}).get("lh_user_id")
    if approver_id is not None:
        leave_request.approved_by = approver_id
    elif payload.approved_by is not None:
        leave_request.approved_by = payload.approved_by

    session.add(leave_request)
    await session.commit()
    await session.refresh(leave_request)
    return LeaveRequestRead.model_validate(leave_request)


# ── Attendance correction history ──


@router.get(
    "/history/student/{student_id}",
    response_model=List[AttendanceChangeEventRead],
    summary="Attendance Correction History",
    description=(
        "Every recorded change to a student's register: what it was, what it "
        "became, who changed it and when. Append-only -- there is deliberately "
        "no endpoint to edit or delete a trail entry, because a trail that can "
        "be rewritten is not a trail."
    ),
)
async def get_student_attendance_history(
    student_id: int,
    section_id: Optional[int] = Query(None, description="Filter by section"),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_own_student_or_privileged()),
) -> List[AttendanceChangeEventRead]:
    events = await get_attendance_history(
        session,
        student_id=student_id,
        section_id=section_id,
        date_from=date_from,
        date_to=date_to,
    )
    return [AttendanceChangeEventRead.model_validate(e) for e in events]


# ── Absence excuses ──


@router.post(
    "/excuses",
    response_model=AbsenceExcuseRead,
    status_code=status.HTTP_201_CREATED,
    summary="Submit an Absence Note",
    description=(
        "A note explaining an absence that already happened -- distinct from a "
        "leave request, which is planned in advance. Open to a parent for their "
        "own child, or staff filing a paper note on a family's behalf."
    ),
)
async def submit_absence_excuse(
    payload: AbsenceExcuseCreate,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> AbsenceExcuseRead:
    # Same rule as filing leave: yourself, or your own child, or staff.
    await _assert_may_file_leave_for(principal, payload.student_id, session)

    excuse = AbsenceExcuse(
        student_id=payload.student_id,
        section_id=payload.section_id,
        date=payload.date,
        reason=payload.reason,
        submitted_by_user_id=(principal.raw_claims or {}).get("lh_user_id"),
        status=ExcuseStatus.PENDING,
    )
    session.add(excuse)
    await session.commit()
    await session.refresh(excuse)
    return AbsenceExcuseRead.model_validate(excuse)


@router.get(
    "/excuses",
    response_model=List[AbsenceExcuseRead],
    summary="List Absence Notes",
    description="Review queue for parents' absence notes.",
)
async def list_absence_excuses(
    section_id: Optional[int] = Query(None),
    student_id: Optional[int] = Query(None),
    status_filter: Optional[ExcuseStatus] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_EXCUSE_REVIEWERS)),
) -> List[AbsenceExcuseRead]:
    conditions = []
    if isinstance(section_id, int):
        await assert_owns_section_or_privileged(principal, section_id, session)
        conditions.append(AbsenceExcuse.section_id == section_id)
    else:
        # No section named: narrow a teacher to their own sections rather than
        # showing them every family's note in the school.
        scope = await _pastoral_section_scope(principal, session)
        if scope is not None:
            if not scope:
                return []
            conditions.append(AbsenceExcuse.section_id.in_(scope))
    if isinstance(student_id, int):
        conditions.append(AbsenceExcuse.student_id == student_id)
    if isinstance(status_filter, (ExcuseStatus, str)):
        conditions.append(AbsenceExcuse.status == status_filter)

    stmt = select(AbsenceExcuse)
    if conditions:
        stmt = stmt.where(and_(*conditions))
    result = await session.execute(
        stmt.order_by(AbsenceExcuse.created_at.desc()).offset(offset).limit(limit)
    )
    return [AbsenceExcuseRead.model_validate(r) for r in result.scalars().all()]


@router.patch(
    "/excuses/{excuse_id}/review",
    response_model=AbsenceExcuseReviewResponse,
    summary="Approve or Reject an Absence Note",
    description=(
        "Approving CONVERTS that day's ABSENT records to EXCUSED and records "
        "the conversion in the attendance trail, so the change is attributable "
        "and the original status is never lost. Records already PRESENT or LATE "
        "are left alone. The response reports how many records actually changed "
        "-- zero is a legitimate answer."
    ),
)
async def review_absence_excuse(
    excuse_id: int,
    payload: AbsenceExcuseReview,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_EXCUSE_REVIEWERS)),
) -> AbsenceExcuseReviewResponse:
    excuse = (
        await session.execute(select(AbsenceExcuse).where(AbsenceExcuse.id == excuse_id))
    ).scalar_one_or_none()
    if excuse is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Absence note with ID {excuse_id} not found.",
        )

    await assert_owns_section_or_privileged(principal, excuse.section_id, session)

    if payload.status == ExcuseStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A review must approve or reject; it cannot set a note back to pending.",
        )

    reviewer_id = (principal.raw_claims or {}).get("lh_user_id")
    excuse.status = payload.status
    excuse.review_note = payload.review_note
    excuse.reviewed_by_user_id = reviewer_id
    excuse.reviewed_at = datetime.datetime.now(datetime.timezone.utc)
    session.add(excuse)

    converted = 0
    if payload.status == ExcuseStatus.APPROVED:
        converted = await apply_approved_excuse(
            session, excuse=excuse, reviewed_by_user_id=reviewer_id
        )

    await session.commit()
    await session.refresh(excuse)

    # Tell the family the outcome of the note THEY submitted. Best-effort: the
    # review is committed above and stands regardless.
    guardians = await _guardians_for_notification(
        session, excuse.student_id, excuse.section_id
    )
    if guardians:
        await raise_school_event(
            session,
            event_key=EXCUSE_REVIEWED.key,
            org_id=principal.org_id,
            recipients=guardians,
            context={
                "student_name": await student_display_name(session, excuse.student_id),
                "date": excuse.date.isoformat() if excuse.date else None,
                # The reviewer's free-text `review_note` is deliberately NOT
                # sent. It is written for colleagues, not for the family, and
                # may reference other pupils or staff judgements.
                "outcome": "approved"
                if payload.status == ExcuseStatus.APPROVED
                else "rejected",
            },
            campus_id=principal.campus_id,
            related_kind="absence_excuse",
            related_id=excuse.id,
        )

    return AbsenceExcuseReviewResponse(
        excuse=AbsenceExcuseRead.model_validate(excuse),
        records_converted=converted,
    )


# ── Pastoral queue ──


@router.get(
    "/pastoral/concerns",
    response_model=List[PastoralConcernRead],
    summary="At-Risk Student Queue",
    description=(
        "Which students are flagged as at risk right now, and why. A teacher "
        "sees concerns for sections they teach; school leadership and the "
        "counsellor see all. See _PASTORAL_VIEWERS for why a teacher is "
        "included here but excluded from AI safety incidents."
    ),
)
async def list_pastoral_queue(
    status_filter: Optional[PastoralConcernStatus] = Query(None, alias="status"),
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_PASTORAL_VIEWERS)),
) -> List[PastoralConcernRead]:
    scope = await _pastoral_section_scope(principal, session)
    concerns = await list_pastoral_concerns(
        session,
        section_ids=scope,
        status_filter=status_filter,
        limit=limit,
        offset=offset,
    )
    return [PastoralConcernRead.model_validate(c) for c in concerns]


@router.patch(
    "/pastoral/concerns/{concern_id}",
    response_model=PastoralConcernRead,
    summary="Update a Pastoral Concern",
    description=(
        "Move a concern through OPEN -> IN_PROGRESS -> RESOLVED. Resolution is "
        "deliberately a human act: a concern is never auto-closed by a student "
        "returning to school, because a child who missed four days and came "
        "back still warrants a conversation."
    ),
)
async def update_pastoral_concern(
    concern_id: int,
    payload: PastoralConcernUpdate,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_PASTORAL_VIEWERS)),
) -> PastoralConcernRead:
    concern = (
        await session.execute(select(PastoralConcern).where(PastoralConcern.id == concern_id))
    ).scalar_one_or_none()
    if concern is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pastoral concern with ID {concern_id} not found.",
        )

    scope = await _pastoral_section_scope(principal, session)
    if scope is not None and concern.section_id not in scope:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only act on pastoral concerns for sections you teach.",
        )

    concern.status = payload.status
    if payload.status == PastoralConcernStatus.RESOLVED:
        concern.resolution_note = payload.resolution_note
        concern.resolved_by_user_id = (principal.raw_claims or {}).get("lh_user_id")
        concern.resolved_at = datetime.datetime.now(datetime.timezone.utc)
    session.add(concern)
    await session.commit()
    await session.refresh(concern)
    return PastoralConcernRead.model_validate(concern)


@router.get(
    "/pastoral/concerns/{concern_id}/interventions",
    response_model=List[PastoralInterventionRead],
    summary="What Has Been Done About a Concern",
)
async def get_concern_interventions(
    concern_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_PASTORAL_VIEWERS)),
) -> List[PastoralInterventionRead]:
    concern = (
        await session.execute(select(PastoralConcern).where(PastoralConcern.id == concern_id))
    ).scalar_one_or_none()
    if concern is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pastoral concern with ID {concern_id} not found.",
        )
    scope = await _pastoral_section_scope(principal, session)
    if scope is not None and concern.section_id not in scope:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view pastoral concerns for sections you teach.",
        )

    records = await list_interventions(session, concern_id=concern_id)
    return [PastoralInterventionRead.model_validate(r) for r in records]


@router.post(
    "/pastoral/concerns/{concern_id}/interventions",
    response_model=PastoralInterventionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Record a Pastoral Intervention",
    description=(
        "Record something staff actually did -- called a guardian, held a "
        "meeting, referred to the counsellor. Append-only: to correct a "
        "mistake, add another, because an intervention records an action that "
        "happened at a point in time."
    ),
)
async def create_concern_intervention(
    concern_id: int,
    payload: PastoralInterventionCreate,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_PASTORAL_VIEWERS)),
) -> PastoralInterventionRead:
    concern = (
        await session.execute(select(PastoralConcern).where(PastoralConcern.id == concern_id))
    ).scalar_one_or_none()
    if concern is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pastoral concern with ID {concern_id} not found.",
        )
    scope = await _pastoral_section_scope(principal, session)
    if scope is not None and concern.section_id not in scope:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only act on pastoral concerns for sections you teach.",
        )

    intervention = PastoralIntervention(
        concern_id=concern_id,
        action=payload.action,
        note=payload.note,
        outcome=payload.outcome,
        acted_by_user_id=(principal.raw_claims or {}).get("lh_user_id"),
    )
    session.add(intervention)
    # Recording that somebody acted moves the concern out of OPEN -- otherwise
    # the queue cannot distinguish "nobody has looked at this" from "a call was
    # made yesterday", which is the whole point of the queue.
    if concern.status == PastoralConcernStatus.OPEN:
        concern.status = PastoralConcernStatus.IN_PROGRESS
        session.add(concern)
    await session.commit()
    await session.refresh(intervention)
    return PastoralInterventionRead.model_validate(intervention)


# ── Bulk marking ──


@router.post(
    "/bulk-mark",
    response_model=BulkMarkRangeResponse,
    summary="Mark a Section Across a Date Range",
    description=(
        "For a trip, a closure, or a correction applied to a whole section. "
        "Existing records that differ are SKIPPED and reported by default -- a "
        "bulk action must never silently rewrite registers a teacher already "
        "took. Pass overwrite_existing=true to change them, which is recorded "
        "in the attendance trail like any other correction."
    ),
)
async def bulk_mark_range(
    payload: BulkMarkRangeRequest,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_BULK_MARKERS)),
) -> BulkMarkRangeResponse:
    if payload.end_date < payload.start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="end_date cannot be earlier than start_date.",
        )
    await assert_owns_section_or_privileged(principal, payload.section_id, session)

    # A guard rail, not an arbitrary limit: a mistyped year would otherwise
    # write hundreds of thousands of rows before anyone noticed.
    span_days = (payload.end_date - payload.start_date).days + 1
    if span_days > 190:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Date range spans {span_days} days, which is longer than a school "
                "year. Narrow the range."
            ),
        )

    student_ids = payload.student_ids
    if not student_ids:
        # Everyone with an existing record in this section -- the only roster
        # this module can see without reaching into enrolment. If nobody has a
        # record yet there is nothing to infer, and inventing a roster would be
        # exactly the kind of fabrication this codebase has removed elsewhere.
        rows = await session.execute(
            select(StudentAttendance.student_id)
            .where(StudentAttendance.section_id == payload.section_id)
            .distinct()
        )
        student_ids = [r for r in rows.scalars().all()]
    if not student_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "No students to mark: pass student_ids explicitly, or take a "
                "roll-call for this section first."
            ),
        )

    dates = [
        payload.start_date + datetime.timedelta(days=offset) for offset in range(span_days)
    ]

    existing_rows = (
        await session.execute(
            select(StudentAttendance).where(
                and_(
                    StudentAttendance.section_id == payload.section_id,
                    StudentAttendance.student_id.in_(student_ids),
                    StudentAttendance.date >= payload.start_date,
                    StudentAttendance.date <= payload.end_date,
                    StudentAttendance.period_id.is_(None),
                )
            )
        )
    ).scalars().all()
    existing_map = {(r.student_id, r.date): r for r in existing_rows}

    actor_id = (principal.raw_claims or {}).get("lh_user_id")
    created = 0
    updated = 0
    skipped: List[BulkMarkSkipped] = []
    pending_history: List[tuple] = []

    for student_id in student_ids:
        for day in dates:
            record = existing_map.get((student_id, day))
            if record is None:
                new_record = StudentAttendance(
                    student_id=student_id,
                    section_id=payload.section_id,
                    date=day,
                    period_id=None,
                    status=payload.status,
                    marked_by=actor_id,
                    remarks=payload.reason,
                )
                session.add(new_record)
                pending_history.append((new_record, AttendanceChangeAction.MARKED, None))
                created += 1
                continue

            if record.status == payload.status:
                # Already what was asked for: not a change, not a conflict.
                continue

            if not payload.overwrite_existing:
                skipped.append(
                    BulkMarkSkipped(
                        student_id=student_id,
                        date=day,
                        existing_status=record.status,
                    )
                )
                continue

            previous = record.status
            record.status = payload.status
            if payload.reason:
                record.remarks = payload.reason
            session.add(record)
            pending_history.append((record, AttendanceChangeAction.CORRECTED, previous))
            updated += 1

    await session.flush()
    for record, action, previous_status in pending_history:
        record_attendance_change(
            session,
            attendance=record,
            action=action,
            previous_status=previous_status,
            changed_by_user_id=actor_id,
            reason=payload.reason,
        )
    await session.commit()

    return BulkMarkRangeResponse(
        section_id=payload.section_id,
        start_date=payload.start_date,
        end_date=payload.end_date,
        dates_covered=span_days,
        records_created=created,
        records_updated=updated,
        skipped=skipped,
    )
