"""Who may be handed a token into a live classroom, and who may read one.

A LiveKit token is admission to a room full of children, so `POST
/live/rooms/{room_name}/token` is the highest-value target in this router:
knowing a room name used to be enough, for any authenticated user at any
school. The rules now enforced are:

  * the caller is the room's host (its teacher, or a school/super admin), or
  * the caller is actively enrolled in the section the room belongs to, and
  * the room belongs to the caller's own org, and their own campus.

An unentitled caller gets 404 -- a room they may not know about is
indistinguishable from one that does not exist.

Most of these call the handlers directly (so FastAPI's DI never runs and the
role gate is not exercised); the two at the bottom go through a real app to
pin the role gate itself.
"""

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.events.database import get_db_session
from src.core.keycloak_auth import KeycloakUserPrincipal, get_current_user_principal
from src.db.sms_campus import AcademicYear, Campus, ClassSection, StudentEnrollment
from src.db.sms_live_class import (
    LiveClassAttendanceLog,
    LiveClassSession,
    LiveClassSessionDetail,
)
from src.routers.live_classes import (
    _to_detail_read,
    create_live_class_session,
    get_class_recording,
    get_live_class,
    get_participant_token,
    get_room_attendance_logs,
    list_active_live_rooms,
    list_class_coursework,
    list_live_classes,
    record_attendance_log,
    router as live_classes_router,
)
from src.schemas.sms_live_class import (
    CreateLiveClassSessionRequest,
    LiveClassAttendanceRequest,
    LiveClassTokenRequest,
)
from types import SimpleNamespace


def _principal(user_id: int, roles=(), org_id=1, campus_id=None):
    """A resolved principal -- see the note in test_live_classes.py."""
    return SimpleNamespace(
        is_superadmin=False,
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
    """A campus, academic year and section for a class to belong to."""
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
    db: AsyncSession, student_id: int, section_id: int = 5, status: str = "active"
) -> None:
    db.add(
        StudentEnrollment(
            student_id=student_id,
            section_id=section_id,
            academic_year_id=1,
            status=status,
        )
    )
    await db.commit()


async def _room(
    db: AsyncSession, room_name: str, section_id=None, teacher_id: int = 101
) -> LiveClassSession:
    live = LiveClassSession(
        title=room_name,
        teacher_id=teacher_id,
        section_id=section_id,
        room_name=room_name,
    )
    db.add(live)
    await db.commit()
    await db.refresh(live)
    return live


def _token_request(participant_id: str = "501") -> LiveClassTokenRequest:
    # is_teacher=True on purpose: asking for host rights must change nothing.
    return LiveClassTokenRequest(
        participant_id=participant_id,
        participant_name="Alice Student",
        is_teacher=True,
    )


# ── Token issuance ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_an_enrolled_student_may_join_their_own_class(db: AsyncSession):
    await _school(db)
    await _enrol(db, 501)
    await _room(db, "math-101", section_id=5)

    res = await get_participant_token(
        room_name="math-101",
        payload=_token_request(),
        session=db,
        principal=_principal(501, roles=("STUDENT",)),
    )
    assert res.participant_id == "501"
    # Asking for host rights in the body still grants none.
    assert res.is_teacher is False


@pytest.mark.asyncio
async def test_the_host_teacher_gets_a_host_token(db: AsyncSession):
    await _school(db)
    await _room(db, "math-101", section_id=5, teacher_id=101)

    res = await get_participant_token(
        room_name="math-101",
        payload=_token_request(participant_id="101"),
        session=db,
        principal=_principal(101, roles=("TEACHER",)),
    )
    assert res.is_teacher is True


@pytest.mark.asyncio
async def test_a_student_at_another_school_is_denied(db: AsyncSession):
    """The headline defect: any authenticated user, any school, any room."""
    await _school(db, campus_id=1, org_id=1, section_id=5)
    await _school(db, campus_id=2, org_id=2, section_id=6, teacher_id=201)
    await _enrol(db, 501, section_id=5)  # enrolled at their own school
    await _room(db, "other-school-math", section_id=6, teacher_id=201)

    with pytest.raises(HTTPException) as exc:
        await get_participant_token(
            room_name="other-school-math",
            payload=_token_request(),
            session=db,
            principal=_principal(501, roles=("STUDENT",), org_id=1),
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_a_student_not_enrolled_in_that_section_is_denied(db: AsyncSession):
    """Same school is not enough: a student is not entitled into every room."""
    await _school(db, campus_id=1, org_id=1, section_id=5)
    await _school(db, campus_id=1, org_id=1, section_id=7)
    await _enrol(db, 501, section_id=5)
    await _room(db, "grade-9b", section_id=7)

    with pytest.raises(HTTPException) as exc:
        await get_participant_token(
            room_name="grade-9b",
            payload=_token_request(),
            session=db,
            principal=_principal(501, roles=("STUDENT",)),
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_a_withdrawn_enrolment_does_not_admit(db: AsyncSession):
    await _school(db)
    await _enrol(db, 501, section_id=5, status="withdrawn")
    await _room(db, "math-101", section_id=5)

    with pytest.raises(HTTPException) as exc:
        await get_participant_token(
            room_name="math-101",
            payload=_token_request(),
            session=db,
            principal=_principal(501, roles=("STUDENT",)),
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_a_room_with_no_section_admits_only_its_host(db: AsyncSession):
    """No section means no roster to test against, so refuse rather than guess."""
    await _room(db, "adhoc", section_id=None, teacher_id=101)

    with pytest.raises(HTTPException) as exc:
        await get_participant_token(
            room_name="adhoc",
            payload=_token_request(),
            session=db,
            principal=_principal(501, roles=("STUDENT",)),
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_a_campus_bound_caller_cannot_reach_another_campus_room(
    db: AsyncSession,
):
    await _school(db, campus_id=1, org_id=1, section_id=5)
    await _school(db, campus_id=2, org_id=1, section_id=8)
    await _room(db, "campus-2-math", section_id=8, teacher_id=101)

    with pytest.raises(HTTPException) as exc:
        await get_participant_token(
            room_name="campus-2-math",
            payload=_token_request(participant_id="101"),
            session=db,
            principal=_principal(101, roles=("TEACHER",), campus_id=1),
        )
    assert exc.value.status_code == 404


# ── Listing and reading ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_active_rooms_from_another_school_are_not_listed(db: AsyncSession):
    await _school(db, campus_id=1, org_id=1, section_id=5)
    await _school(db, campus_id=2, org_id=2, section_id=6, teacher_id=201)
    await _room(db, "our-math", section_id=5, teacher_id=101)
    await _room(db, "their-math", section_id=6, teacher_id=201)

    rooms = await list_active_live_rooms(
        session=db, principal=_principal(101, roles=("TEACHER",), org_id=1)
    )
    assert [r.room_name for r in rooms] == ["our-math"]


@pytest.mark.asyncio
async def test_attendance_reads_are_limited_to_the_callers_own_record(
    db: AsyncSession,
):
    await _school(db)
    await _room(db, "math-101", section_id=5)
    live = (
        await db.execute(
            select(LiveClassSession).where(LiveClassSession.room_name == "math-101")
        )
    ).scalars().first()
    for student_id in (501, 502):
        db.add(
            LiveClassAttendanceLog(session_id=live.id, student_id=student_id)
        )
    await db.commit()

    host_view = await get_room_attendance_logs(
        room_name="math-101", session=db, principal=_principal(101, roles=("TEACHER",))
    )
    assert len(host_view) == 2

    own_view = await get_room_attendance_logs(
        room_name="math-101", session=db, principal=_principal(501, roles=("STUDENT",))
    )
    assert len(own_view) == 1
    assert own_view[0].student_id == 501


@pytest.mark.asyncio
async def test_a_class_at_another_school_is_not_readable_by_id(db: AsyncSession):
    await _school(db, campus_id=2, org_id=2, section_id=6, teacher_id=201)
    other = await _room(db, "their-math", section_id=6, teacher_id=201)

    with pytest.raises(HTTPException) as exc:
        await get_live_class(
            class_id=other.id,
            session=db,
            principal=_principal(101, roles=("TEACHER",), org_id=1),
        )
    assert exc.value.status_code == 404


# ── Room creation ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_room_creation_ignores_a_client_supplied_teacher_id(db: AsyncSession):
    await _school(db)
    res = await create_live_class_session(
        payload=CreateLiveClassSessionRequest(
            title="Maths", teacher_id=999, section_id=5
        ),
        session=db,
        principal=_principal(101, roles=("TEACHER",)),
    )
    assert res.session.teacher_id == 101


@pytest.mark.asyncio
async def test_room_creation_refuses_a_section_the_teacher_does_not_own(
    db: AsyncSession,
):
    await _school(db, section_id=5, teacher_id=101)
    await _school(db, section_id=9, teacher_id=777)

    with pytest.raises(HTTPException) as exc:
        await create_live_class_session(
            payload=CreateLiveClassSessionRequest(
                title="Not my section", teacher_id=101, section_id=9
            ),
            session=db,
            principal=_principal(101, roles=("TEACHER",)),
        )
    assert exc.value.status_code == 403


# ── Attendance writes ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_an_enrolled_student_may_log_their_own_attendance(db: AsyncSession):
    """Positive control, so the three refusals below cannot pass vacuously."""
    await _school(db)
    await _enrol(db, 501)
    await _room(db, "math-101", section_id=5)

    log = await record_attendance_log(
        room_name="math-101",
        payload=LiveClassAttendanceRequest(student_id=501, action="join"),
        session=db,
        principal=_principal(501, roles=("STUDENT",)),
    )
    assert log.student_id == 501


@pytest.mark.asyncio
async def test_attendance_cannot_be_written_into_another_schools_room(
    db: AsyncSession,
):
    """The gap: a student could only write their OWN id -- into any room at
    any school. Writing the register is the write half of being in the room,
    so it now takes the same entitlement as being handed a join token."""
    await _school(db, campus_id=1, org_id=1, section_id=5)
    await _school(db, campus_id=2, org_id=2, section_id=6, teacher_id=201)
    await _enrol(db, 501, section_id=5)
    await _room(db, "other-school-math", section_id=6, teacher_id=201)

    with pytest.raises(HTTPException) as exc:
        await record_attendance_log(
            room_name="other-school-math",
            payload=LiveClassAttendanceRequest(student_id=501, action="join"),
            session=db,
            principal=_principal(501, roles=("STUDENT",), org_id=1),
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_an_unenrolled_student_cannot_log_attendance(db: AsyncSession):
    """Same school is not enough: not being in the class means not being in
    its register, whether you are reading it or writing it."""
    await _school(db, campus_id=1, org_id=1, section_id=5)
    await _school(db, campus_id=1, org_id=1, section_id=7)
    await _enrol(db, 501, section_id=5)
    await _room(db, "grade-9b", section_id=7)

    with pytest.raises(HTTPException) as exc:
        await record_attendance_log(
            room_name="grade-9b",
            payload=LiveClassAttendanceRequest(student_id=501, action="join"),
            session=db,
            principal=_principal(501, roles=("STUDENT",)),
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_a_non_host_cannot_log_attendance_for_somebody_else(
    db: AsyncSession,
):
    """Naming another student in the body must not move their register line."""
    await _school(db)
    await _enrol(db, 501)
    await _room(db, "math-101", section_id=5)

    log = await record_attendance_log(
        room_name="math-101",
        payload=LiveClassAttendanceRequest(student_id=502, action="join"),
        session=db,
        principal=_principal(501, roles=("STUDENT",)),
    )
    assert log.student_id == 501


# ── Listing scheduled classes ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_classes_at_another_school_are_not_listed(db: AsyncSession):
    """The gap: campus-scoped only, so a caller with no campus binding listed
    every org's classes -- room names and teacher ids included."""
    await _school(db, campus_id=1, org_id=1, section_id=5)
    await _school(db, campus_id=2, org_id=2, section_id=6, teacher_id=201)
    await _room(db, "our-math", section_id=5, teacher_id=101)
    await _room(db, "their-math", section_id=6, teacher_id=201)

    classes = await list_live_classes(
        upcoming=True,
        session=db,
        principal=_principal(101, roles=("TEACHER",), org_id=1),
    )
    assert [c.room_name for c in classes] == ["our-math"]


@pytest.mark.asyncio
async def test_a_campus_bound_caller_does_not_list_another_campuss_classes(
    db: AsyncSession,
):
    await _school(db, campus_id=1, org_id=1, section_id=5)
    await _school(db, campus_id=2, org_id=1, section_id=8)
    await _room(db, "campus-1-math", section_id=5, teacher_id=101)
    await _room(db, "campus-2-math", section_id=8, teacher_id=101)

    classes = await list_live_classes(
        upcoming=True,
        session=db,
        principal=_principal(101, roles=("TEACHER",), org_id=1, campus_id=1),
    )
    assert [c.room_name for c in classes] == ["campus-1-math"]


# ── Coursework ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_coursework_of_a_class_at_another_school_is_not_listed(
    db: AsyncSession,
):
    """Coursework had no scope check at all: a class id was enough to read
    another school's activity list."""
    await _school(db, campus_id=2, org_id=2, section_id=6, teacher_id=201)
    other = await _room(db, "their-math", section_id=6, teacher_id=201)

    with pytest.raises(HTTPException) as exc:
        await list_class_coursework(
            class_id=other.id,
            session=db,
            principal=_principal(101, roles=("TEACHER",), org_id=1),
        )
    assert exc.value.status_code == 404


# ── The recording URL is one rule, not two ─────────────────────────────────


@pytest.mark.asyncio
async def test_the_recording_url_reaches_the_host(db: AsyncSession):
    """Positive control for the two refusals below."""
    await _school(db)
    live = await _room(db, "math-101", section_id=5, teacher_id=101)
    live.recording_url = "https://media.example.com/class-1.mp4"
    await db.commit()

    host_view = await get_live_class(
        class_id=live.id, session=db, principal=_principal(101, roles=("TEACHER",))
    )
    assert host_view.recording.url == "https://media.example.com/class-1.mp4"


@pytest.mark.asyncio
async def test_the_recording_url_is_not_returned_to_an_unentitled_reader(
    db: AsyncSession,
):
    """`_to_detail_read` used to hand the URL to anyone who could read the
    class at all, while GET /classes/{id}/recording required shared AND
    enrolled. Both now answer from the same predicate."""
    await _school(db)
    live = await _room(db, "math-101", section_id=5, teacher_id=101)
    live.recording_url = "https://media.example.com/class-1.mp4"
    await db.commit()
    # A colleague: same school, same campus, but not this class's host and not
    # enrolled in it.
    colleague = _principal(999, roles=("TEACHER",))

    with pytest.raises(HTTPException) as exc:
        await get_class_recording(class_id=live.id, session=db, principal=colleague)
    assert exc.value.status_code == 403

    detail = await get_live_class(class_id=live.id, session=db, principal=colleague)
    assert detail.recording.url is None


@pytest.mark.asyncio
async def test_a_shared_recording_url_reaches_an_enrolled_student(
    db: AsyncSession,
):
    """The rule grants as well as refuses: shared, and actually enrolled."""
    await _school(db)
    await _enrol(db, 501)
    live = await _room(db, "math-101", section_id=5, teacher_id=101)
    live.recording_url = "https://media.example.com/class-1.mp4"
    db.add(
        LiveClassSessionDetail(
            session_id=live.id, recording_shared_with_students=True
        )
    )
    await db.commit()

    view = await _to_detail_read(db, live, _principal(501, roles=("STUDENT",)))
    assert view.recording.url == "https://media.example.com/class-1.mp4"


# ── The role gate itself (through a real app, so DI runs) ────────────────────


@pytest.fixture
def app(db):
    application = FastAPI()
    application.include_router(live_classes_router, prefix="/live")
    application.dependency_overrides[get_db_session] = lambda: db
    yield application
    application.dependency_overrides.clear()


def _real_principal(user_id: int, roles, org_id=1, campus_id=None):
    return KeycloakUserPrincipal(
        sub=f"user-{user_id}",
        roles=set(roles),
        org_id=org_id,
        campus_id=campus_id,
        raw_claims={"lh_user_id": user_id},
    )


@pytest.mark.asyncio
async def test_a_student_may_not_list_active_rooms(app):
    app.dependency_overrides[get_current_user_principal] = lambda: _real_principal(
        501, ["STUDENT"]
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        res = await client.get("/live/rooms/active")
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_a_student_may_not_read_a_class_by_id(app, db: AsyncSession):
    await _school(db)
    live = await _room(db, "math-101", section_id=5)
    app.dependency_overrides[get_current_user_principal] = lambda: _real_principal(
        501, ["STUDENT"]
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        res = await client.get(f"/live/classes/{live.id}")
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_a_student_may_not_list_scheduled_classes(app):
    """Listing was open to any authenticated principal of any role."""
    app.dependency_overrides[get_current_user_principal] = lambda: _real_principal(
        501, ["STUDENT"]
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        res = await client.get("/live/classes")
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_a_student_may_not_list_coursework(app, db: AsyncSession):
    await _school(db)
    live = await _room(db, "math-101", section_id=5)
    app.dependency_overrides[get_current_user_principal] = lambda: _real_principal(
        501, ["STUDENT"]
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        res = await client.get(f"/live/classes/{live.id}/coursework")
    assert res.status_code == 403
