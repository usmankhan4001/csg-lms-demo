import datetime
import jwt
import pytest
from fastapi import HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_campus import AcademicYear, Campus, ClassSection, StudentEnrollment
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
from types import SimpleNamespace


def _principal(user_id: int, roles=(), superadmin: bool = False, org_id=1, campus_id=None):
    """A resolved principal.

    These tests call the handlers directly, so FastAPI's DI never runs and the
    `principal` default would arrive as an unresolved `Depends`. Host status is
    now derived from the caller (it grants room_admin and room_record, so it
    can never come from the request body), which means the caller has to be
    real here -- and so does their school, since a room is scoped by the org
    and campus of the section it belongs to.
    """
    return SimpleNamespace(
        is_superadmin=superadmin,
        org_id=org_id,
        campus_id=campus_id,
        has_role=lambda r: r in roles,
        has_any_role=lambda wanted: any(r in roles for r in wanted),
        raw_claims={"lh_user_id": user_id},
    )


async def _school(
    db: AsyncSession,
    campus_id: int = 1,
    org_id: int = 1,
    section_id: int = 5,
    teacher_id: int = 101,
) -> None:
    """A campus, academic year and section for a class to belong to.

    Room access is scoped by the section a class belongs to, so a test that
    hands out a token needs a section that really exists, in a real org.
    """
    if await db.get(Campus, campus_id) is None:
        db.add(
            Campus(
                id=campus_id,
                org_id=org_id,
                name=f"Campus {campus_id}",
                code=f"C{campus_id}",
            )
        )
    if await db.get(AcademicYear, campus_id) is None:
        db.add(AcademicYear(id=campus_id, campus_id=campus_id, name="2026-2027"))
    if await db.get(ClassSection, section_id) is None:
        db.add(
            ClassSection(
                id=section_id,
                campus_id=campus_id,
                grade_level="Grade 9",
                section_name="A",
                class_teacher_id=teacher_id,
            )
        )
    await db.commit()


async def _enrol(
    db: AsyncSession,
    student_id: int,
    section_id: int = 5,
    academic_year_id: int = 1,
    status: str = "active",
) -> None:
    db.add(
        StudentEnrollment(
            student_id=student_id,
            section_id=section_id,
            academic_year_id=academic_year_id,
            status=status,
        )
    )
    await db.commit()


@pytest.mark.asyncio
async def test_live_class_session_lifecycle(db: AsyncSession):
    """Test creating live class sessions, generating tokens, and closing sessions."""
    await _school(db)
    await _enrol(db, 501)

    # 1. Create a session
    req = CreateLiveClassSessionRequest(
        title="Advanced Mathematics Live Lecture",
        teacher_id=101,
        section_id=5,
        course_id=12,
        room_name="math-101-live",
    )
    result = await create_live_class_session(
        payload=req, session=db, principal=_principal(101, roles=("TEACHER",))
    )
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
        principal=_principal(501, roles=("STUDENT",)),
    )
    assert student_token_res.token is not None
    student_decoded = jwt.decode(student_token_res.token, config["api_secret"], algorithms=["HS256"])
    assert student_decoded["sub"] == "501"
    assert student_decoded["name"] == "Alice Student"
    assert student_decoded["video"].get("roomAdmin") is not True

    # 3. List active rooms
    active_rooms = await list_active_live_rooms(
        section_id=5, session=db, principal=_principal(101, roles=("TEACHER",))
    )
    assert len(active_rooms) == 1
    assert active_rooms[0].room_name == "math-101-live"

    # Filter by different teacher -> empty
    other_rooms = await list_active_live_rooms(
        teacher_id=999, session=db, principal=_principal(101, roles=("TEACHER",))
    )
    assert len(other_rooms) == 0

    # 4. End the session
    ended = await end_live_class_session(
        room_name="math-101-live",
        session=db,
        principal=_principal(101, roles=("TEACHER",)),
    )
    assert ended.is_active is False
    # No recording was requested for this class, so there is no URL. The
    # endpoint no longer accepts one from the caller -- it previously did,
    # which let anybody attach an arbitrary link to a class and have it
    # presented as that class's recording.
    assert ended.recording_url is None
    assert ended.end_time is not None

    # Verify no active rooms now
    active_after = await list_active_live_rooms(
        section_id=5, session=db, principal=_principal(101, roles=("TEACHER",))
    )
    assert len(active_after) == 0

    # Attempting to get token for ended room raises 400
    with pytest.raises(HTTPException) as exc_info:
        await get_participant_token(
            room_name="math-101-live",
            payload=student_token_req,
            session=db,
            principal=_principal(501, roles=("STUDENT",)),
        )
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_live_class_attendance_tracking(db: AsyncSession):
    """Test student join/leave attendance logging and duration calculation."""
    # 1. Create a live session. It needs a real section, and the student a real
    # enrolment in it: attendance is the write half of being in the room, so it
    # now takes the same entitlement as being handed a join token for it.
    await _school(db, teacher_id=202)
    await _enrol(db, 701)
    req = CreateLiveClassSessionRequest(
        title="Physics Lab Live Stream",
        teacher_id=102,
        section_id=5,
        room_name="physics-lab-live",
    )
    await create_live_class_session(
        payload=req, session=db, principal=_principal(202, roles=("TEACHER",))
    )

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
        principal=_principal(701, roles=("STUDENT",)),
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
        principal=_principal(701, roles=("STUDENT",)),
    )
    assert leave_log.id == join_log.id
    assert leave_log.duration_minutes == 45.0
    assert leave_log.left_at is not None
    assert leave_log.left_at.year == leave_time.year
    assert leave_log.left_at.minute == leave_time.minute

    # 4. Fetch room attendance logs. A student sees their own line only.
    logs = await get_room_attendance_logs(
        room_name="physics-lab-live",
        session=db,
        principal=_principal(701, roles=("STUDENT",)),
    )
    assert len(logs) == 1
    assert logs[0].duration_minutes == 45.0
