"""Live Classes as a school module (M02): scheduling, recording, coursework.

The recording tests matter most. Before this module, `recording_url` was set
only if a caller PASSED one to the end-session endpoint -- there was no egress
pipeline at all, so the field advertised a capability that did not exist. These
pin the two rules that replaced it: recording is opt-in, and a recording
reaches a student only if the teacher shared it AND that student was actually
enrolled in the class.
"""

import datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_campus import ClassSection, StudentEnrollment
from src.db.sms_live_class import LiveClassStatus, RecordingStatus
from src.routers.live_classes import (
    attach_class_coursework,
    cancel_live_class,
    get_class_recording,
    list_live_classes,
    schedule_live_class,
    set_class_recording,
    share_class_recording,
)
from src.schemas.sms_live_class import (
    AttachCourseworkRequest,
    CancelLiveClassRequest,
    ScheduleLiveClassRequest,
    SetRecordingRequest,
    ShareRecordingRequest,
)
from src.services.sms import live_class_schedule as lc_schedule


def _principal(user_id: int, roles=(), superadmin: bool = False, org_id=1, campus_id=None):
    """A resolved principal. These call handlers directly, so FastAPI's DI
    never runs and the default would arrive as an unresolved `Depends`.

    `org_id` is part of the principal because listing classes is now scoped to
    the caller's organisation, not just their campus.
    """
    return SimpleNamespace(
        is_superadmin=superadmin,
        org_id=org_id,
        campus_id=campus_id,
        has_role=lambda r: r in roles,
        has_any_role=lambda wanted: any(r in roles for r in wanted),
        raw_claims={"lh_user_id": user_id},
    )


def _future(hours: int = 2) -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=hours)


async def _section(db, section_id=77, teacher_id=301, campus_id=1) -> int:
    """A real section owned by the teacher.

    Scheduling runs `assert_owns_section_or_privileged`, so a teacher must
    genuinely teach the section -- these tests exercise that path rather than
    bypassing it with an admin principal.
    """
    existing = await db.get(ClassSection, section_id)
    if existing is not None:
        return existing.id
    row = ClassSection(
        id=section_id,
        campus_id=campus_id,
        grade_level="Grade 9",
        section_name="A",
        class_teacher_id=teacher_id,
    )
    db.add(row)
    await db.commit()
    return row.id


async def _schedule(db, teacher_id=301, section_id=77, recording=False, roles=("TEACHER",)):
    await _section(db, section_id=section_id, teacher_id=teacher_id)
    return await schedule_live_class(
        payload=ScheduleLiveClassRequest(
            title="Photosynthesis",
            start_time=_future(),
            end_time=_future(3),
            section_id=section_id,
            description="Chapter 4",
            recording_enabled=recording,
        ),
        session=db,
        principal=_principal(teacher_id, roles=roles),
    )


# ── Scheduling ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_scheduled_class_is_scheduled_not_live(db: AsyncSession):
    """A class scheduled for later must not read as already running."""
    result = await _schedule(db)
    assert result.status == LiveClassStatus.SCHEDULED.value
    assert result.title == "Photosynthesis"
    assert result.can_host is True


@pytest.mark.asyncio
async def test_a_teacher_cannot_schedule_in_a_colleagues_name(db: AsyncSession):
    """payload.teacher_id is ignored for a plain teacher.

    Honouring it would let a teacher put a colleague's name on a class -- the
    same shape as the client-supplied `approved_by` and `graded_by` fields
    found elsewhere in this codebase.
    """
    await _section(db)
    result = await schedule_live_class(
        payload=ScheduleLiveClassRequest(
            title="Not mine",
            start_time=_future(),
            section_id=77,
            teacher_id=999,  # trying to schedule as someone else
        ),
        session=db,
        principal=_principal(301, roles=("TEACHER",)),
    )
    assert result.teacher_id == 301


@pytest.mark.asyncio
async def test_an_admin_may_schedule_on_a_teachers_behalf(db: AsyncSession):
    await _section(db)
    result = await schedule_live_class(
        payload=ScheduleLiveClassRequest(
            title="Cover lesson",
            start_time=_future(),
            section_id=77,
            teacher_id=888,
        ),
        session=db,
        principal=_principal(1, roles=("SCHOOL_ADMIN",)),
    )
    assert result.teacher_id == 888


@pytest.mark.asyncio
async def test_a_class_must_belong_to_a_section_or_course(db: AsyncSession):
    with pytest.raises(HTTPException) as exc:
        await schedule_live_class(
            payload=ScheduleLiveClassRequest(title="Orphan", start_time=_future()),
            session=db,
            principal=_principal(301, roles=("TEACHER",)),
        )
    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_cancelled_classes_leave_the_upcoming_list(db: AsyncSession):
    result = await _schedule(db)
    principal = _principal(301, roles=("TEACHER",))

    upcoming = await list_live_classes(upcoming=True, session=db, principal=principal)
    assert any(c.id == result.id for c in upcoming)

    await cancel_live_class(
        class_id=result.id,
        payload=CancelLiveClassRequest(reason="Teacher unwell"),
        session=db,
        principal=principal,
    )
    upcoming_after = await list_live_classes(upcoming=True, session=db, principal=principal)
    assert not any(c.id == result.id for c in upcoming_after)


@pytest.mark.asyncio
async def test_another_teacher_cannot_cancel_my_class(db: AsyncSession):
    """TEACHER is not blanket permission over every other teacher's class."""
    result = await _schedule(db, teacher_id=301)
    with pytest.raises(HTTPException) as exc:
        await cancel_live_class(
            class_id=result.id,
            payload=CancelLiveClassRequest(),
            session=db,
            principal=_principal(999, roles=("TEACHER",)),
        )
    assert exc.value.status_code == 403


# ── Recording ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_recording_is_off_unless_the_teacher_opts_in(db: AsyncSession):
    """These are rooms full of children. Recording is never implicit."""
    result = await _schedule(db, recording=False)
    assert result.recording.enabled is False
    assert result.recording.status == RecordingStatus.NOT_REQUESTED.value
    assert result.recording.url is None


@pytest.mark.asyncio
async def test_requesting_recording_without_storage_says_why(db: AsyncSession):
    """S3 is unset in this environment, so recording must report UNAVAILABLE
    with a reason -- never silently accept and produce nothing."""
    result = await _schedule(db, recording=True)
    assert result.recording.enabled is True
    assert result.recording.status == RecordingStatus.UNAVAILABLE.value
    assert result.recording.note is not None
    assert "not available" in result.recording.note.lower()
    # And emphatically no invented URL.
    assert result.recording.url is None


@pytest.mark.asyncio
async def test_unavailable_is_not_reported_as_failed(db: AsyncSession):
    """Telling a teacher their recording FAILED, when nobody ever configured
    storage, sends them chasing the wrong problem."""
    result = await _schedule(db, recording=True)
    assert result.recording.status != RecordingStatus.FAILED.value


@pytest.mark.asyncio
async def test_toggling_recording_off_clears_the_state(db: AsyncSession):
    result = await _schedule(db, recording=True)
    principal = _principal(301, roles=("TEACHER",))
    off = await set_class_recording(
        class_id=result.id,
        payload=SetRecordingRequest(enabled=False),
        session=db,
        principal=principal,
    )
    assert off.recording.enabled is False
    assert off.recording.status == RecordingStatus.NOT_REQUESTED.value
    assert off.recording.note is None


@pytest.mark.asyncio
async def test_an_unshared_recording_is_not_reachable_by_a_student(db: AsyncSession):
    result = await _schedule(db, recording=True)
    # Enrolled, but the teacher has not shared it.
    db.add(StudentEnrollment(student_id=555, section_id=77, academic_year_id=1))
    await db.commit()

    with pytest.raises(HTTPException) as exc:
        await get_class_recording(
            class_id=result.id,
            session=db,
            principal=_principal(555, roles=("STUDENT",)),
        )
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_a_student_not_enrolled_cannot_fetch_the_recording(db: AsyncSession):
    """Sharing is not enough: the student must have actually been in the class.

    Otherwise any student in the school could watch any other class.
    """
    result = await _schedule(db, recording=True)
    principal = _principal(301, roles=("TEACHER",))
    await share_class_recording(
        class_id=result.id,
        payload=ShareRecordingRequest(shared=True),
        session=db,
        principal=principal,
    )

    with pytest.raises(HTTPException) as exc:
        await get_class_recording(
            class_id=result.id,
            session=db,
            principal=_principal(4242, roles=("STUDENT",)),  # never enrolled
        )
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_a_shared_recording_reaches_an_enrolled_student(db: AsyncSession):
    result = await _schedule(db, recording=True)
    db.add(StudentEnrollment(student_id=556, section_id=77, academic_year_id=1))
    await db.commit()
    await share_class_recording(
        class_id=result.id,
        payload=ShareRecordingRequest(shared=True),
        session=db,
        principal=_principal(301, roles=("TEACHER",)),
    )

    rec = await get_class_recording(
        class_id=result.id,
        session=db,
        principal=_principal(556, roles=("STUDENT",)),
    )
    assert rec.shared_with_students is True
    # Storage is unconfigured here, so there is genuinely no file. The point is
    # that access was granted without a URL being invented to fill the gap.
    assert rec.url is None


@pytest.mark.asyncio
async def test_the_host_always_sees_recording_state(db: AsyncSession):
    result = await _schedule(db, recording=True)
    rec = await get_class_recording(
        class_id=result.id,
        session=db,
        principal=_principal(301, roles=("TEACHER",)),
    )
    assert rec.status == RecordingStatus.UNAVAILABLE.value


# ── Coursework ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_coursework_attaches_once_and_is_listed(db: AsyncSession):
    result = await _schedule(db)
    principal = _principal(301, roles=("TEACHER",))
    first = await attach_class_coursework(
        class_id=result.id,
        payload=AttachCourseworkRequest(activity_id=42, note="Read first"),
        session=db,
        principal=principal,
    )
    again = await attach_class_coursework(
        class_id=result.id,
        payload=AttachCourseworkRequest(activity_id=42),
        session=db,
        principal=principal,
    )
    assert first.id == again.id  # idempotent, not a duplicate row

    rows = await lc_schedule.list_coursework(db, session_id=result.id)
    assert [r.activity_id for r in rows] == [42]


@pytest.mark.asyncio
async def test_another_teacher_cannot_attach_to_my_class(db: AsyncSession):
    result = await _schedule(db, teacher_id=301)
    with pytest.raises(HTTPException) as exc:
        await attach_class_coursework(
            class_id=result.id,
            payload=AttachCourseworkRequest(activity_id=42),
            session=db,
            principal=_principal(999, roles=("TEACHER",)),
        )
    assert exc.value.status_code == 403


# ── The assertions must discriminate ────────────────────────────────────────


@pytest.mark.asyncio
async def test_the_host_check_discriminates(db: AsyncSession):
    """If `_assert_can_host` ever stopped rejecting, the 403 tests above would
    pass vacuously. This proves the same call SUCCEEDS for the real host, so a
    failure there means the check works rather than everything being blocked.
    """
    result = await _schedule(db, teacher_id=301)
    ok = await attach_class_coursework(
        class_id=result.id,
        payload=AttachCourseworkRequest(activity_id=7),
        session=db,
        principal=_principal(301, roles=("TEACHER",)),
    )
    assert ok.activity_id == 7
