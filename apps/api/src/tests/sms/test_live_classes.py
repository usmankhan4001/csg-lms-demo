import datetime
import jwt
import pytest
from fastapi import HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession

from src.schemas.sms_live_class import (
    CreateLiveClassSessionRequest,
    LiveClassAttendanceRequest,
    LiveClassTokenRequest,
)
from src.routers.live_classes import (
    create_live_class_session,
    end_live_class_session,
    get_participant_token,
    get_room_attendance_logs,
    list_active_live_rooms,
    record_attendance_log,
)
from src.services.sms.live_class import get_livekit_config


@pytest.mark.asyncio
async def test_live_class_session_lifecycle(db: AsyncSession):
    """Test creating live class sessions, generating tokens, and closing sessions."""
    # 1. Create a session
    req = CreateLiveClassSessionRequest(
        title="Advanced Mathematics Live Lecture",
        teacher_id=101,
        section_id=5,
        course_id=12,
        room_name="math-101-live",
    )
    result = await create_live_class_session(payload=req, session=db)
    assert result.session.id is not None
    assert result.session.room_name == "math-101-live"
    assert result.session.is_active is True
    assert result.token is not None
    assert result.livekit_url is not None

    # Verify teacher token claims
    config = get_livekit_config()
    decoded = jwt.decode(result.token, config["api_secret"], algorithms=["HS256"])
    assert decoded["sub"] == "101"
    assert decoded["video"]["room"] == "math-101-live"
    assert decoded["video"]["roomAdmin"] is True
    assert decoded["video"]["canPublish"] is True

    # 2. Generate participant token for student
    student_token_req = LiveClassTokenRequest(
        participant_id="501",
        participant_name="Alice Student",
        is_teacher=False,
    )
    student_token_res = await get_participant_token(
        room_name="math-101-live",
        payload=student_token_req,
        session=db,
    )
    assert student_token_res.token is not None
    student_decoded = jwt.decode(student_token_res.token, config["api_secret"], algorithms=["HS256"])
    assert student_decoded["sub"] == "501"
    assert student_decoded["name"] == "Alice Student"
    assert student_decoded["video"].get("roomAdmin") is not True

    # 3. List active rooms
    active_rooms = await list_active_live_rooms(section_id=5, session=db)
    assert len(active_rooms) == 1
    assert active_rooms[0].room_name == "math-101-live"

    # Filter by different teacher -> empty
    other_rooms = await list_active_live_rooms(teacher_id=999, session=db)
    assert len(other_rooms) == 0

    # 4. End the session
    ended = await end_live_class_session(
        room_name="math-101-live",
        recording_url="https://s3.amazonaws.com/recordings/math-101.mp4",
        session=db,
    )
    assert ended.is_active is False
    assert ended.recording_url == "https://s3.amazonaws.com/recordings/math-101.mp4"
    assert ended.end_time is not None

    # Verify no active rooms now
    active_after = await list_active_live_rooms(section_id=5, session=db)
    assert len(active_after) == 0

    # Attempting to get token for ended room raises 400
    with pytest.raises(HTTPException) as exc_info:
        await get_participant_token(
            room_name="math-101-live",
            payload=student_token_req,
            session=db,
        )
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_live_class_attendance_tracking(db: AsyncSession):
    """Test student join/leave attendance logging and duration calculation."""
    # 1. Create a live session
    req = CreateLiveClassSessionRequest(
        title="Physics Lab Live Stream",
        teacher_id=102,
        room_name="physics-lab-live",
    )
    await create_live_class_session(payload=req, session=db)

    # 2. Student 701 joins at t0
    join_time = datetime.datetime(2026, 9, 11, 10, 0, 0, tzinfo=datetime.timezone.utc)
    join_log = await record_attendance_log(
        room_name="physics-lab-live",
        payload=LiveClassAttendanceRequest(
            student_id=701,
            action="join",
            timestamp=join_time,
        ),
        session=db,
    )
    assert join_log.id is not None
    assert join_log.student_id == 701
    assert join_log.left_at is None

    # 3. Student 701 leaves at t0 + 45 minutes
    leave_time = datetime.datetime(2026, 9, 11, 10, 45, 0, tzinfo=datetime.timezone.utc)
    leave_log = await record_attendance_log(
        room_name="physics-lab-live",
        payload=LiveClassAttendanceRequest(
            student_id=701,
            action="leave",
            timestamp=leave_time,
        ),
        session=db,
    )
    assert leave_log.id == join_log.id
    assert leave_log.duration_minutes == 45.0
    assert leave_log.left_at is not None
    assert leave_log.left_at.year == leave_time.year
    assert leave_log.left_at.minute == leave_time.minute

    # 4. Fetch room attendance logs
    logs = await get_room_attendance_logs(room_name="physics-lab-live", session=db)
    assert len(logs) == 1
    assert logs[0].duration_minutes == 45.0
