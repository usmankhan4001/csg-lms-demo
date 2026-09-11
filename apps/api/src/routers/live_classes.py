import datetime
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, desc, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.events.database import get_db_session
from src.db.sms_live_class import LiveClassAttendanceLog, LiveClassSession
from src.schemas.sms_live_class import (
    CreateLiveClassSessionRequest,
    LiveClassAttendanceLogRead,
    LiveClassAttendanceRequest,
    LiveClassSessionRead,
    LiveClassSessionWithTokenResponse,
    LiveClassTokenRequest,
    LiveClassTokenResponse,
)
from src.services.sms.live_class import generate_livekit_token, get_livekit_config

router = APIRouter()


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
) -> LiveClassSessionWithTokenResponse:
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
        teacher_id=payload.teacher_id,
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

    # Generate teacher host token
    config = get_livekit_config()
    token = generate_livekit_token(
        room_name=room_name,
        participant_id=str(payload.teacher_id),
        participant_name=f"Teacher #{payload.teacher_id}",
        is_teacher=True,
        can_publish=True,
        can_subscribe=True,
    )

    return LiveClassSessionWithTokenResponse(
        session=LiveClassSessionRead.model_validate(live_session),
        token=token,
        livekit_url=config["url"],
    )


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
) -> LiveClassTokenResponse:
    stmt = select(LiveClassSession).where(LiveClassSession.room_name == room_name)
    live_session = (await session.execute(stmt)).scalars().first()
    if not live_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Live class room '{room_name}' not found",
        )

    if not live_session.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot join a concluded or inactive live class room",
        )

    config = get_livekit_config()
    token = generate_livekit_token(
        room_name=room_name,
        participant_id=payload.participant_id,
        participant_name=payload.participant_name,
        is_teacher=payload.is_teacher,
        can_publish=payload.can_publish,
        can_subscribe=payload.can_subscribe,
    )

    return LiveClassTokenResponse(
        room_name=room_name,
        token=token,
        livekit_url=config["url"],
        participant_id=payload.participant_id,
        participant_name=payload.participant_name,
        is_teacher=payload.is_teacher,
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
) -> LiveClassAttendanceLogRead:
    stmt = select(LiveClassSession).where(LiveClassSession.room_name == room_name)
    live_session = (await session.execute(stmt)).scalars().first()
    if not live_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Live class room '{room_name}' not found",
        )

    event_time = payload.timestamp or datetime.datetime.now(datetime.timezone.utc)
    action = payload.action.strip().lower()

    if action == "join":
        log = LiveClassAttendanceLog(
            session_id=live_session.id,
            student_id=payload.student_id,
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
                    LiveClassAttendanceLog.student_id == payload.student_id,
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
                student_id=payload.student_id,
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
) -> List[LiveClassSessionRead]:
    conditions = [LiveClassSession.is_active.is_(True)]
    if isinstance(section_id, int):
        conditions.append(LiveClassSession.section_id == section_id)
    if isinstance(course_id, int):
        conditions.append(LiveClassSession.course_id == course_id)
    if isinstance(teacher_id, int):
        conditions.append(LiveClassSession.teacher_id == teacher_id)

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
    recording_url: Optional[str] = None,
    session: AsyncSession = Depends(get_db_session),
) -> LiveClassSessionRead:
    stmt = select(LiveClassSession).where(LiveClassSession.room_name == room_name)
    live_session = (await session.execute(stmt)).scalars().first()
    if not live_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Live class room '{room_name}' not found",
        )

    now = datetime.datetime.now(datetime.timezone.utc)
    live_session.is_active = False
    live_session.end_time = now
    if recording_url:
        live_session.recording_url = recording_url

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
) -> List[LiveClassAttendanceLogRead]:
    stmt = select(LiveClassSession).where(LiveClassSession.room_name == room_name)
    live_session = (await session.execute(stmt)).scalars().first()
    if not live_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Live class room '{room_name}' not found",
        )

    log_stmt = (
        select(LiveClassAttendanceLog)
        .where(LiveClassAttendanceLog.session_id == live_session.id)
        .order_by(desc(LiveClassAttendanceLog.joined_at))
    )
    logs = (await session.execute(log_stmt)).scalars().all()
    return [LiveClassAttendanceLogRead.model_validate(l) for l in logs]
