import datetime
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, desc, or_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.events.database import get_db_session
from src.core.keycloak_auth import (
    KeycloakUserPrincipal,
    get_current_user_principal,
    require_roles,
)
from src.db.sms_campus import Campus, ClassSection, StudentEnrollment
from src.db.sms_live_class import (
    LiveClassAttendanceLog,
    LiveClassSession,
    LiveClassStatus,
    RecordingStatus,
)
from src.schemas.sms_live_class import (
    AttachCourseworkRequest,
    CancelLiveClassRequest,
    CreateLiveClassSessionRequest,
    LiveClassCourseworkRead,
    LiveClassDetailRead,
    LiveClassRecordingRead,
    ScheduleLiveClassRequest,
    SetRecordingRequest,
    ShareRecordingRequest,
    LiveClassAttendanceLogRead,
    LiveClassAttendanceRequest,
    LiveClassSessionRead,
    LiveClassSessionWithTokenResponse,
    LiveClassTokenRequest,
    LiveClassTokenResponse,
)
from src.security.school_ownership import (
    assert_owns_section_or_privileged,
    get_user_id,
    require_org_id,
    resolve_scoped_campus_id,
)
from src.services.sms import live_class_schedule as lc_schedule
from src.services.sms.live_class import (
    create_room_on_server,
    end_room_on_server,
    generate_livekit_token,
    get_livekit_config,
)

router = APIRouter()


# Who may run a class. TEACHER is included, but a teacher is additionally
# checked against the specific class via `_caller_is_host` -- being a teacher
# is not permission over every other teacher's room, the same distinction
# already applied to live-class host tokens.
_CLASS_STAFF = ["SUPER_ADMIN", "SCHOOL_ADMIN", "TEACHER"]



@router.post(
    "/rooms/create",
    response_model=LiveClassSessionWithTokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Live Class Room Session",
    description="Creates a new virtual classroom session and generates a LiveKit teacher token.",
)
async def create_live_class_session(
    payload: CreateLiveClassSessionRequest,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_CLASS_STAFF)),
) -> LiveClassSessionWithTokenResponse:
    caller_id = get_user_id(principal)
    is_admin = principal.is_superadmin or principal.has_any_role(list(_HOST_ROLES))

    # A teacher opening a room is its host. Honouring payload.teacher_id for
    # them would put a colleague's name on a room they control -- the same
    # shape as `schedule_live_class` below, which already refuses it.
    if is_admin and payload.teacher_id is not None:
        teacher_id = payload.teacher_id
    elif caller_id is not None:
        teacher_id = caller_id
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot resolve the hosting teacher from your session.",
        )

    # The section is not just a label: it is what makes this room somebody's
    # class, and what attendance and enrolment hang off.
    if payload.section_id is not None:
        await assert_owns_section_or_privileged(principal, payload.section_id, session)

    room_name = payload.room_name or f"class-{uuid.uuid4().hex[:10]}"
    start_time = payload.start_time or datetime.datetime.now(datetime.timezone.utc)

    # Ensure unique room_name
    existing_stmt = select(LiveClassSession).where(LiveClassSession.room_name == room_name)
    existing = (await session.execute(existing_stmt)).scalars().first()
    if existing:
        if existing.is_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Live class session with room name '{room_name}' is already active",
            )
        room_name = f"{room_name}-{uuid.uuid4().hex[:6]}"

    live_session = LiveClassSession(
        title=payload.title,
        teacher_id=teacher_id,
        section_id=payload.section_id,
        course_id=payload.course_id,
        room_name=room_name,
        start_time=start_time,
        end_time=payload.end_time,
        is_active=True,
    )
    session.add(live_session)
    await session.commit()
    await session.refresh(live_session)

    # Best-effort real room creation on the LiveKit media server (never
    # raises -- see create_room_on_server's docstring). The DB session
    # record above is the source of truth for the app; this just configures
    # the room ahead of time rather than relying purely on auto-create.
    await create_room_on_server(room_name)

    # Generate teacher host token
    config = get_livekit_config()
    token = generate_livekit_token(
        room_name=room_name,
        participant_id=str(teacher_id),
        participant_name=f"Teacher #{teacher_id}",
        is_teacher=True,
        can_publish=True,
        can_subscribe=True,
    )

    return LiveClassSessionWithTokenResponse(
        session=LiveClassSessionRead.model_validate(live_session),
        token=token,
        livekit_url=config["url"],
    )


# Roles that may host a live class besides the session's own teacher. A school
# needs someone able to step into a room when a teacher cannot.
_HOST_ROLES = ("SUPER_ADMIN", "SCHOOL_ADMIN")


def _caller_is_host(principal: KeycloakUserPrincipal, live_session: LiveClassSession) -> bool:
    """Host rights follow from who the caller IS, never from what they ask for.

    `is_teacher` grants room_admin and room_record, so this must never consult
    the request body. The session already records its teacher; that is the
    authority, plus school/super admins.
    """
    if principal.is_superadmin or principal.has_any_role(list(_HOST_ROLES)):
        return True
    caller_id = (principal.raw_claims or {}).get("lh_user_id")
    return caller_id is not None and caller_id == live_session.teacher_id


def _caller_identity(principal: KeycloakUserPrincipal, payload) -> str:
    """The LiveKit participant identity, bound to the authenticated user.

    Taking this from the body let a caller join as someone else, so anything
    keyed on identity -- attendance, moderation, recordings -- named the wrong
    person. Falls back to the payload only when the principal carries no id.
    """
    caller_id = (principal.raw_claims or {}).get("lh_user_id")
    return str(caller_id) if caller_id is not None else str(payload.participant_id)


# ---------------------------------------------------------------------------
# Who may be in a room at all.
#
# A room is a teacher, a section and a name -- `LiveClassSession` carries no
# tenant columns of its own, so "is this class at my school" has to be derived
# from the section it belongs to. Without it, any authenticated user anywhere
# could name any room and be handed a token into it.
# ---------------------------------------------------------------------------


def _not_found() -> HTTPException:
    """A class the caller is not entitled to is indistinguishable from one
    that does not exist -- never 403, which would confirm it is real."""
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="Live class not found"
    )


async def _session_scope(
    session: AsyncSession, live: LiveClassSession
) -> "tuple[Optional[int], Optional[int]]":
    """The (org_id, campus_id) this class belongs to, or (None, None).

    Derived section -> campus -> org. A class with no section (a course-only
    or ad-hoc room) has no tenant this data can establish, and None here means
    exactly that: unknown, not "every tenant".
    """
    if live.section_id is None:
        return None, None
    row = (
        await session.execute(
            select(ClassSection.campus_id, Campus.org_id)
            .join(Campus, Campus.id == ClassSection.campus_id)
            .where(ClassSection.id == live.section_id)
        )
    ).first()
    if row is None:
        return None, None
    return row[1], row[0]


async def _assert_session_in_scope(
    session: AsyncSession,
    principal: KeycloakUserPrincipal,
    live: LiveClassSession,
) -> None:
    """Refuse a class belonging to another school, or another campus of it."""
    if principal.is_superadmin:
        return
    org_id = require_org_id(principal)
    session_org, session_campus = await _session_scope(session, live)
    if session_org is not None and session_org != org_id:
        raise _not_found()
    if (
        session_campus is not None
        and resolve_scoped_campus_id(principal, session_campus) != session_campus
    ):
        raise _not_found()


async def _caller_is_enrolled(
    session: AsyncSession,
    live: LiveClassSession,
    student_user_id: Optional[int],
) -> bool:
    """Active enrolment in the section this class belongs to.

    Holding the STUDENT role is not membership: a student at this school is
    not entitled into every classroom in it. A class with no section has no
    roster to test against, so this refuses rather than guesses -- the same
    rule `student_may_view_recording` already applies to recordings.
    """
    if live.section_id is None or student_user_id is None:
        return False
    row = (
        await session.execute(
            select(StudentEnrollment.id).where(
                and_(
                    StudentEnrollment.section_id == live.section_id,
                    StudentEnrollment.student_id == student_user_id,
                    StudentEnrollment.status == "active",
                )
            )
        )
    ).first()
    return row is not None


async def _assert_may_enter_room(
    session: AsyncSession,
    principal: KeycloakUserPrincipal,
    live: LiveClassSession,
) -> None:
    """Who may hold a token for a room: its host, or a student enrolled in
    the section it belongs to.

    Nothing else -- not the STUDENT role, not knowing the room name. Everyone
    else gets 404.
    """
    await _assert_session_in_scope(session, principal, live)
    if _caller_is_host(principal, live):
        return
    if await _caller_is_enrolled(session, live, get_user_id(principal)):
        return
    raise _not_found()


@router.post(
    "/rooms/{room_name}/token",
    response_model=LiveClassTokenResponse,
    summary="Generate Participant LiveKit Join Token",
    description="Generates an authenticated LiveKit WebRTC access token for a student or teacher participant.",
)
async def get_participant_token(
    room_name: str,
    payload: LiveClassTokenRequest,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> LiveClassTokenResponse:
    stmt = select(LiveClassSession).where(LiveClassSession.room_name == room_name)
    live_session = (await session.execute(stmt)).scalars().first()
    if not live_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Live class room '{room_name}' not found",
        )

    # A token admits the holder to a room full of children, so it is the
    # tightest check in this file: the caller must be this room's host, or
    # enrolled in the section it belongs to. Being merely authenticated -- at
    # any school -- is not enough, and neither is knowing the room name.
    await _assert_may_enter_room(session, principal, live_session)

    if not live_session.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot join a concluded or inactive live class room",
        )

    config = get_livekit_config()
    token = generate_livekit_token(
        room_name=room_name,
        participant_id=_caller_identity(principal, payload),
        participant_name=payload.participant_name,
        # NEVER payload.is_teacher. `is_teacher` grants room_admin AND
        # room_record (services/sms/live_class.py:63-64), so honouring a
        # client-supplied boolean let any authenticated user mint a host token
        # -- moderate the room, and RECORD a class full of children -- by
        # flipping one field. Host status is the session's own teacher_id, or a
        # school/super admin.
        is_teacher=_caller_is_host(principal, live_session),
        can_publish=payload.can_publish,
        can_subscribe=payload.can_subscribe,
    )

    return LiveClassTokenResponse(
        room_name=room_name,
        token=token,
        livekit_url=config["url"],
        # Echo what was actually GRANTED, not what was requested: a client
        # told is_teacher=true while holding a participant token would render
        # host controls that every action then fails against.
        participant_id=_caller_identity(principal, payload),
        participant_name=payload.participant_name,
        is_teacher=_caller_is_host(principal, live_session),
    )


@router.post(
    "/rooms/{room_name}/attendance",
    response_model=LiveClassAttendanceLogRead,
    summary="Record Live Class Attendance Log",
    description="Auto-records student entry (join) or exit (leave) timestamp and calculates session duration.",
)
async def record_attendance_log(
    room_name: str,
    payload: LiveClassAttendanceRequest,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> LiveClassAttendanceLogRead:
    stmt = select(LiveClassSession).where(LiveClassSession.room_name == room_name)
    live_session = (await session.execute(stmt)).scalars().first()
    if not live_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Live class room '{room_name}' not found",
        )

    # A student may only log their OWN attendance. Taking student_id from the
    # body let any authenticated user mark any student present in any class --
    # the same impersonation shape as the participant_id fix above.
    caller_id = _caller_user_id(principal)
    if _caller_is_host(principal, live_session):
        student_id = payload.student_id
    elif caller_id is not None:
        student_id = caller_id
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot resolve your identity for attendance.",
        )

    event_time = payload.timestamp or datetime.datetime.now(datetime.timezone.utc)
    action = payload.action.strip().lower()

    if action == "join":
        log = LiveClassAttendanceLog(
            session_id=live_session.id,
            student_id=student_id,
            joined_at=event_time,
            left_at=None,
            duration_minutes=0.0,
        )
        session.add(log)
        await session.commit()
        await session.refresh(log)
        return LiveClassAttendanceLogRead.model_validate(log)

    elif action == "leave":
        # Find the most recent unclosed attendance log
        log_stmt = (
            select(LiveClassAttendanceLog)
            .where(
                and_(
                    LiveClassAttendanceLog.session_id == live_session.id,
                    LiveClassAttendanceLog.student_id == student_id,
                    LiveClassAttendanceLog.left_at.is_(None),
                )
            )
            .order_by(desc(LiveClassAttendanceLog.joined_at))
        )
        log = (await session.execute(log_stmt)).scalars().first()

        if not log:
            # Create a log record with immediate leave if no prior join was found
            log = LiveClassAttendanceLog(
                session_id=live_session.id,
                student_id=student_id,
                joined_at=event_time,
                left_at=event_time,
                duration_minutes=0.0,
            )
            session.add(log)
        else:
            log.left_at = event_time
            if log.joined_at:
                # Calculate elapsed minutes
                joined_aware = log.joined_at if log.joined_at.tzinfo else log.joined_at.replace(tzinfo=datetime.timezone.utc)
                event_aware = event_time if event_time.tzinfo else event_time.replace(tzinfo=datetime.timezone.utc)
                diff = (event_aware - joined_aware).total_seconds() / 60.0
                log.duration_minutes = max(round(diff, 2), 0.0)

        await session.commit()
        await session.refresh(log)
        return LiveClassAttendanceLogRead.model_validate(log)

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid action '{payload.action}'. Expected 'join' or 'leave'",
        )


@router.get(
    "/rooms/active",
    response_model=List[LiveClassSessionRead],
    summary="List Active Live Classroom Sessions",
    description="Lists all currently ongoing active live virtual classes with optional filters.",
)
async def list_active_live_rooms(
    section_id: Optional[int] = Query(None, description="Filter by section ID"),
    course_id: Optional[int] = Query(None, description="Filter by course ID"),
    teacher_id: Optional[int] = Query(None, description="Filter by teacher user ID"),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_CLASS_STAFF)),
) -> List[LiveClassSessionRead]:
    conditions = [LiveClassSession.is_active.is_(True)]
    if isinstance(section_id, int):
        conditions.append(LiveClassSession.section_id == section_id)
    if isinstance(course_id, int):
        conditions.append(LiveClassSession.course_id == course_id)
    if isinstance(teacher_id, int):
        conditions.append(LiveClassSession.teacher_id == teacher_id)

    # Tenant scoping. A room has no org of its own, so it is scoped by the
    # section it belongs to -- plus the caller's own rooms, so a teacher still
    # sees an ad-hoc room they opened without a section.
    if not principal.is_superadmin:
        org_id = require_org_id(principal)
        campus_stmt = select(Campus.id).where(Campus.org_id == org_id)
        scoped_campus = resolve_scoped_campus_id(principal, None)
        if scoped_campus is not None:
            campus_stmt = campus_stmt.where(Campus.id == scoped_campus)
        campus_ids = (await session.execute(campus_stmt)).scalars().all()
        section_ids = (
            await session.execute(
                select(ClassSection.id).where(ClassSection.campus_id.in_(campus_ids))
            )
        ).scalars().all()
        conditions.append(
            or_(
                LiveClassSession.section_id.in_(section_ids),
                LiveClassSession.teacher_id == get_user_id(principal),
            )
        )

    stmt = select(LiveClassSession).where(and_(*conditions)).order_by(desc(LiveClassSession.start_time))
    active_sessions = (await session.execute(stmt)).scalars().all()
    return [LiveClassSessionRead.model_validate(s) for s in active_sessions]


@router.post(
    "/rooms/{room_name}/end",
    response_model=LiveClassSessionRead,
    summary="Conclude Live Virtual Class Room",
)
async def end_live_class_session(
    room_name: str,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_CLASS_STAFF)),
) -> LiveClassSessionRead:
    stmt = select(LiveClassSession).where(LiveClassSession.room_name == room_name)
    live_session = (await session.execute(stmt)).scalars().first()
    if not live_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Live class room '{room_name}' not found",
        )

    _assert_can_host(principal, live_session)

    now = datetime.datetime.now(datetime.timezone.utc)
    live_session.is_active = False
    live_session.end_time = now
    # `recording_url` is deliberately NOT accepted from the caller any more. A
    # recording URL must come from the egress pipeline that actually produced a
    # file; accepting one from a request body let anybody attach an arbitrary
    # link to a class and have it presented as that class's recording.
    await lc_schedule.finish_recording(session, live=live_session)

    # Best-effort: force-close the real LiveKit room now instead of waiting
    # for its empty_timeout. Never raises (see end_room_on_server).
    await end_room_on_server(room_name)

    # Auto-close open student attendance logs
    open_logs_stmt = select(LiveClassAttendanceLog).where(
        and_(
            LiveClassAttendanceLog.session_id == live_session.id,
            LiveClassAttendanceLog.left_at.is_(None),
        )
    )
    open_logs = (await session.execute(open_logs_stmt)).scalars().all()
    for log in open_logs:
        log.left_at = now
        joined_aware = log.joined_at if log.joined_at.tzinfo else log.joined_at.replace(tzinfo=datetime.timezone.utc)
        diff = (now - joined_aware).total_seconds() / 60.0
        log.duration_minutes = max(round(diff, 2), 0.0)

    await session.commit()
    await session.refresh(live_session)
    return LiveClassSessionRead.model_validate(live_session)


@router.get(
    "/rooms/{room_name}/attendance",
    response_model=List[LiveClassAttendanceLogRead],
    summary="Get Attendance Logs for a Live Class",
)
async def get_room_attendance_logs(
    room_name: str,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> List[LiveClassAttendanceLogRead]:
    stmt = select(LiveClassSession).where(LiveClassSession.room_name == room_name)
    live_session = (await session.execute(stmt)).scalars().first()
    if not live_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Live class room '{room_name}' not found",
        )

    await _assert_session_in_scope(session, principal, live_session)

    log_stmt = select(LiveClassAttendanceLog).where(
        LiveClassAttendanceLog.session_id == live_session.id
    )

    # Who was in the room, and for how long, is a register of children. A host
    # sees the whole room; anyone else sees only their own line.
    if not _caller_is_host(principal, live_session):
        caller_id = get_user_id(principal)
        if caller_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot resolve your identity for attendance.",
            )
        log_stmt = log_stmt.where(LiveClassAttendanceLog.student_id == caller_id)

    logs = (
        await session.execute(
            log_stmt.order_by(desc(LiveClassAttendanceLog.joined_at))
        )
    ).scalars().all()
    return [LiveClassAttendanceLogRead.model_validate(l) for l in logs]


# ── In-Class AI Live Copilot (M50) ──

@router.post(
    "/rooms/{room_name}/ai-qa",
    summary="In-Class AI Live Lecture Assistant (M50)",
    description="Answers student questions during live lectures using class curriculum and discussion context without interrupting the instructor.",
)
async def live_class_ai_qa(
    room_name: str,
    payload: dict,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    stmt = select(LiveClassSession).where(LiveClassSession.room_name == room_name)
    live_session = (await session.execute(stmt)).scalars().first()
    if not live_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Live class room '{room_name}' not found",
        )

    question = payload.get("question", "").strip()
    if not question:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question cannot be empty.",
        )

    # This endpoint USED TO FABRICATE. It called no model and returned a
    # string template -- a student asking about photosynthesis was told to
    # "verify your boundary conditions" over a signature that read ai_response.
    # It was also ungated and took an untyped dict. Same fabrication class as
    # the GPA endpoint that returned 4.0 for a student with no grades, and the
    # parent digest that invented attendance.
    #
    # Nothing calls it (verified across apps/web and apps/mobile), so rather
    # than delete a route M50 (AI Live Class QA/QC) will want, it now refuses
    # honestly. A real implementation belongs on the existing Socratic tutor
    # with its crisis classification and content guardrails -- NOT a second,
    # unguarded AI path into a room full of children.
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=(
            "In-class AI Q&A is not implemented. This endpoint previously "
            "returned generated-looking text that no model produced; it now "
            "refuses rather than mislead a student."
        ),
    )

# ─────────────────────────────────────────────────────────────────────────────
# Live Classes as a school module (M02): scheduling, recording, coursework.
#
# Everything above this line treats a live class as a room plus a join token.
# A school needs to schedule classes ahead of time, see what is coming up and
# what already happened, record a class when the teacher chooses to, and hand
# students the coursework that goes with it.
# ─────────────────────────────────────────────────────────────────────────────

def _caller_user_id(principal: KeycloakUserPrincipal) -> Optional[int]:
    return (principal.raw_claims or {}).get("lh_user_id")


async def _load_class_or_404(session: AsyncSession, class_id: int) -> LiveClassSession:
    live = (
        await session.execute(select(LiveClassSession).where(LiveClassSession.id == class_id))
    ).scalar_one_or_none()
    if live is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Live class not found"
        )
    return live


def _assert_can_host(principal: KeycloakUserPrincipal, live: LiveClassSession) -> None:
    """Managing a class is for its own teacher, or a school/super admin.

    Derived from who the caller IS -- never from anything in the payload.
    """
    if not _caller_is_host(principal, live):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only this class's teacher or a school administrator may manage it.",
        )


async def _to_detail_read(
    session: AsyncSession,
    live: LiveClassSession,
    principal: KeycloakUserPrincipal,
) -> LiveClassDetailRead:
    detail = await lc_schedule.get_detail(session, live.id)
    coursework = await lc_schedule.list_coursework(session, session_id=live.id)
    return LiveClassDetailRead(
        id=live.id,
        title=live.title,
        description=detail.description if detail else None,
        room_name=live.room_name,
        teacher_id=live.teacher_id,
        section_id=live.section_id,
        course_id=live.course_id,
        start_time=live.start_time,
        end_time=live.end_time,
        status=lc_schedule.derive_status(live, detail),
        cancelled_reason=detail.cancelled_reason if detail else None,
        recording=LiveClassRecordingRead(
            enabled=detail.recording_enabled if detail else False,
            shared_with_students=detail.recording_shared_with_students if detail else False,
            status=detail.recording_status if detail else RecordingStatus.NOT_REQUESTED.value,
            note=detail.recording_note if detail else None,
            # The URL is only ever the one actually stored. Never synthesised.
            url=live.recording_url,
            started_at=detail.recording_started_at if detail else None,
            completed_at=detail.recording_completed_at if detail else None,
            duration_seconds=detail.recording_duration_seconds if detail else None,
        ),
        coursework=[LiveClassCourseworkRead.model_validate(c) for c in coursework],
        can_host=_caller_is_host(principal, live),
    )


@router.post(
    "/classes",
    response_model=LiveClassDetailRead,
    status_code=status.HTTP_201_CREATED,
    summary="Schedule a Live Class",
    description=(
        "Schedules a live class against a section or course. The LiveKit room is "
        "NOT opened until someone starts the class. Recording is OFF unless the "
        "teacher opts in."
    ),
)
async def schedule_live_class(
    payload: ScheduleLiveClassRequest,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_CLASS_STAFF)),
) -> LiveClassDetailRead:
    caller_id = _caller_user_id(principal)
    is_admin = principal.is_superadmin or principal.has_any_role(list(_HOST_ROLES))

    # A teacher schedules their OWN class. Honouring payload.teacher_id for a
    # plain teacher would let them put a colleague's name on a class -- the
    # same class of bug as the client-supplied `approved_by` and `graded_by`
    # fields found elsewhere in this codebase.
    if is_admin and payload.teacher_id is not None:
        teacher_id = payload.teacher_id
    elif caller_id is not None:
        teacher_id = caller_id
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot resolve the scheduling teacher from your session.",
        )

    if payload.section_id is not None:
        await assert_owns_section_or_privileged(principal, payload.section_id, session)

    live, _ = await lc_schedule.schedule_class(
        session,
        title=payload.title,
        teacher_id=teacher_id,
        start_time=payload.start_time,
        end_time=payload.end_time,
        section_id=payload.section_id,
        course_id=payload.course_id,
        description=payload.description,
        recording_enabled=payload.recording_enabled,
    )
    return await _to_detail_read(session, live, principal)


@router.get(
    "/classes",
    response_model=List[LiveClassDetailRead],
    summary="List Upcoming or Past Live Classes",
)
async def list_live_classes(
    upcoming: bool = Query(True, description="True for upcoming/live, False for past"),
    section_id: Optional[int] = Query(None),
    course_id: Optional[int] = Query(None),
    teacher_id: Optional[int] = Query(None),
    campus_id: Optional[int] = Query(None),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> List[LiveClassDetailRead]:
    # Reads narrow rather than fail: a campus-bound caller who asks for
    # everything gets their own campus, not the whole org.
    # `campus_id` is normalised the way the rest of this codebase does it: a
    # direct (non-HTTP) call passes FastAPI's unresolved `Query(...)` default
    # object, which would otherwise reach a WHERE clause as a bind parameter.
    scoped_campus = resolve_scoped_campus_id(
        principal, campus_id if isinstance(campus_id, int) else None
    )
    rows = await lc_schedule.list_classes(
        session,
        upcoming=upcoming,
        section_id=section_id if isinstance(section_id, int) else None,
        course_id=course_id if isinstance(course_id, int) else None,
        teacher_id=teacher_id if isinstance(teacher_id, int) else None,
        campus_id=scoped_campus,
    )
    return [await _to_detail_read(session, live, principal) for live, _ in rows]


@router.get(
    "/classes/{class_id}",
    response_model=LiveClassDetailRead,
    summary="Get One Live Class",
)
async def get_live_class(
    class_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_CLASS_STAFF)),
) -> LiveClassDetailRead:
    live = await _load_class_or_404(session, class_id)
    # The id alone used to be enough to read any class at any school: its room
    # name, teacher, section and recording URL. Scope it to the caller's own.
    await _assert_session_in_scope(session, principal, live)
    return await _to_detail_read(session, live, principal)


@router.post(
    "/classes/{class_id}/cancel",
    response_model=LiveClassDetailRead,
    summary="Cancel a Scheduled Live Class",
)
async def cancel_live_class(
    class_id: int,
    payload: CancelLiveClassRequest,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_CLASS_STAFF)),
) -> LiveClassDetailRead:
    live = await _load_class_or_404(session, class_id)
    _assert_can_host(principal, live)
    await lc_schedule.cancel_class(
        session,
        live=live,
        cancelled_by_user_id=_caller_user_id(principal) or 0,
        reason=payload.reason,
    )
    await session.refresh(live)
    return await _to_detail_read(session, live, principal)


@router.put(
    "/classes/{class_id}/recording",
    response_model=LiveClassDetailRead,
    summary="Turn Class Recording On or Off",
    description=(
        "Recording is opt-in per class. If the deployment has no object storage "
        "configured, this reports UNAVAILABLE with the reason rather than "
        "appearing to succeed."
    ),
)
async def set_class_recording(
    class_id: int,
    payload: SetRecordingRequest,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_CLASS_STAFF)),
) -> LiveClassDetailRead:
    live = await _load_class_or_404(session, class_id)
    _assert_can_host(principal, live)
    await lc_schedule.set_recording_enabled(session, live=live, enabled=payload.enabled)
    return await _to_detail_read(session, live, principal)


@router.put(
    "/classes/{class_id}/recording/share",
    response_model=LiveClassDetailRead,
    summary="Share a Finished Recording With Students",
    description=(
        "A separate, deliberate decision from recording. A class may be recorded "
        "for the teacher's own review and never shared."
    ),
)
async def share_class_recording(
    class_id: int,
    payload: ShareRecordingRequest,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_CLASS_STAFF)),
) -> LiveClassDetailRead:
    live = await _load_class_or_404(session, class_id)
    _assert_can_host(principal, live)
    await lc_schedule.set_recording_shared(session, live=live, shared=payload.shared)
    return await _to_detail_read(session, live, principal)


@router.get(
    "/classes/{class_id}/recording",
    response_model=LiveClassRecordingRead,
    summary="Get a Class Recording",
    description=(
        "Hosts always see the recording state. A student sees it only if the "
        "teacher shared it AND the student was enrolled in that section."
    ),
    responses={403: {"description": "Not shared, or you were not in this class"}},
)
async def get_class_recording(
    class_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> LiveClassRecordingRead:
    live = await _load_class_or_404(session, class_id)
    detail = await lc_schedule.get_detail(session, live.id)

    if not _caller_is_host(principal, live):
        caller_id = _caller_user_id(principal)
        allowed = caller_id is not None and await lc_schedule.student_may_view_recording(
            session, live=live, student_user_id=caller_id
        )
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "This recording has not been shared with students, or you were "
                    "not enrolled in this class."
                ),
            )

    return LiveClassRecordingRead(
        enabled=detail.recording_enabled if detail else False,
        shared_with_students=detail.recording_shared_with_students if detail else False,
        status=detail.recording_status if detail else RecordingStatus.NOT_REQUESTED.value,
        note=detail.recording_note if detail else None,
        url=live.recording_url,
        started_at=detail.recording_started_at if detail else None,
        completed_at=detail.recording_completed_at if detail else None,
        duration_seconds=detail.recording_duration_seconds if detail else None,
    )


@router.post(
    "/classes/{class_id}/coursework",
    response_model=LiveClassCourseworkRead,
    status_code=status.HTTP_201_CREATED,
    summary="Attach Coursework to a Live Class",
    description=(
        "References an existing Learnhouse activity. The class is a place where "
        "existing coursework is used, not a second place where it is authored."
    ),
)
async def attach_class_coursework(
    class_id: int,
    payload: AttachCourseworkRequest,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_CLASS_STAFF)),
) -> LiveClassCourseworkRead:
    live = await _load_class_or_404(session, class_id)
    _assert_can_host(principal, live)
    row = await lc_schedule.attach_coursework(
        session,
        live=live,
        activity_id=payload.activity_id,
        attached_by_user_id=_caller_user_id(principal) or 0,
        note=payload.note,
    )
    return LiveClassCourseworkRead.model_validate(row)


@router.get(
    "/classes/{class_id}/coursework",
    response_model=List[LiveClassCourseworkRead],
    summary="List Coursework Attached to a Live Class",
)
async def list_class_coursework(
    class_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> List[LiveClassCourseworkRead]:
    live = await _load_class_or_404(session, class_id)
    rows = await lc_schedule.list_coursework(session, session_id=live.id)
    return [LiveClassCourseworkRead.model_validate(r) for r in rows]


@router.delete(
    "/classes/{class_id}/coursework/{activity_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Detach Coursework From a Live Class",
)
async def detach_class_coursework(
    class_id: int,
    activity_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_CLASS_STAFF)),
) -> None:
    live = await _load_class_or_404(session, class_id)
    _assert_can_host(principal, live)
    await lc_schedule.detach_coursework(
        session, session_id=live.id, activity_id=activity_id
    )
    return None


@router.post(
    "/classes/{class_id}/start",
    response_model=LiveClassSessionWithTokenResponse,
    summary="Start a Scheduled Live Class",
    description=(
        "Opens the LiveKit room, starts recording if the teacher opted in, and "
        "returns the host's join token."
    ),
)
async def start_live_class(
    class_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_CLASS_STAFF)),
) -> LiveClassSessionWithTokenResponse:
    live = await _load_class_or_404(session, class_id)
    _assert_can_host(principal, live)

    detail = await lc_schedule.get_detail(session, live.id)
    if detail is not None and detail.status == LiveClassStatus.CANCELLED.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This class was cancelled and cannot be started.",
        )
    if not live.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This class has already ended.",
        )

    await create_room_on_server(live.room_name)
    # Never blocks the class: a recording failure is recorded on the class and
    # surfaced to the teacher, but the lesson still runs.
    await lc_schedule.begin_recording_if_requested(session, live=live)

    config = get_livekit_config()
    caller_id = _caller_user_id(principal)
    token = generate_livekit_token(
        room_name=live.room_name,
        participant_id=str(caller_id if caller_id is not None else live.teacher_id),
        participant_name=f"Teacher #{live.teacher_id}",
        is_teacher=True,
        can_publish=True,
        can_subscribe=True,
    )
    return LiveClassSessionWithTokenResponse(
        session=LiveClassSessionRead.model_validate(live),
        token=token,
        livekit_url=config["url"],
    )
