"""Live-class attendance: percentage, the 80% threshold, and the register bridge.

The cases that matter here are the ones where the honest answer is NOTHING.
A session with no measurable length, a child with no telemetry, a child whose
join was never closed by a leave -- each of those must produce no row at all,
never a 0% and never an automatic ABSENT. These are classes full of children
and the output is a register a school may have to defend, so a fabricated
number is worse than a gap.

Handlers are called directly, so FastAPI's dependency injection never runs and
`require_roles` is not exercised -- the same trade-off as
test_live_class_module.py. Per-section ownership IS exercised, because that is
where the real authorisation lives.
"""

import datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_attendance import (
    AttendanceChangeEvent,
    AttendanceStatus,
    StudentAttendance,
)
from src.db.sms_campus import Campus, ClassSection, StudentEnrollment
from src.db.sms_live_class import LiveClassAttendanceLog, LiveClassSession
from src.routers.sms_live_class_attendance import (
    bridge_live_class_attendance,
    preview_live_class_attendance,
)
from src.services.sms import live_class_attendance as bridge

SECTION_ID = 77
TEACHER_ID = 301
CAMPUS_ID = 1
ORG_ID = 1

START = datetime.datetime(2026, 3, 2, 9, 0, tzinfo=datetime.timezone.utc)


def _principal(
    user_id: int,
    roles=("TEACHER",),
    superadmin: bool = False,
    campus_id=None,
    org_id=ORG_ID,
):
    return SimpleNamespace(
        is_superadmin=superadmin,
        campus_id=campus_id,
        org_id=org_id,
        has_role=lambda r: r in roles,
        has_any_role=lambda wanted: any(r in roles for r in wanted),
        raw_claims={"lh_user_id": user_id},
    )


async def _school(db: AsyncSession, student_ids=(501, 502)) -> None:
    """A campus, a section owned by TEACHER_ID, and an active roster."""
    if await db.get(Campus, CAMPUS_ID) is None:
        db.add(Campus(id=CAMPUS_ID, org_id=ORG_ID, name="Main", code="MAIN"))
    if await db.get(ClassSection, SECTION_ID) is None:
        db.add(
            ClassSection(
                id=SECTION_ID,
                campus_id=CAMPUS_ID,
                grade_level="Grade 9",
                section_name="A",
                class_teacher_id=TEACHER_ID,
            )
        )
    for student_id in student_ids:
        db.add(
            StudentEnrollment(
                student_id=student_id,
                section_id=SECTION_ID,
                academic_year_id=1,
                status="active",
            )
        )
    await db.commit()


async def _class(
    db: AsyncSession,
    *,
    minutes=60,
    room_name="room-bridge-1",
    section_id=SECTION_ID,
) -> LiveClassSession:
    """A finished class. `minutes=None` leaves end_time unset."""
    live = LiveClassSession(
        teacher_id=TEACHER_ID,
        section_id=section_id,
        title="Photosynthesis",
        room_name=room_name,
        start_time=START,
        end_time=None if minutes is None else START + datetime.timedelta(minutes=minutes),
        is_active=False,
    )
    db.add(live)
    await db.commit()
    await db.refresh(live)
    return live


async def _log(
    db: AsyncSession,
    live: LiveClassSession,
    student_id: int,
    minutes: float,
    *,
    open_ended: bool = False,
) -> LiveClassAttendanceLog:
    """One join/leave pair, as the LiveKit webhook would have written it."""
    joined = START + datetime.timedelta(minutes=5)
    row = LiveClassAttendanceLog(
        session_id=live.id,
        student_id=student_id,
        joined_at=joined,
        left_at=None if open_ended else joined + datetime.timedelta(minutes=minutes),
        duration_minutes=0.0 if open_ended else float(minutes),
    )
    db.add(row)
    await db.commit()
    return row


async def _register_rows(db: AsyncSession) -> list:
    return (
        await db.execute(
            select(StudentAttendance).where(
                StudentAttendance.section_id == SECTION_ID
            )
        )
    ).scalars().all()


async def _audit_events(db: AsyncSession) -> list:
    return (await db.execute(select(AttendanceChangeEvent))).scalars().all()


# ── The threshold ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_at_or_above_threshold_is_present(db: AsyncSession):
    await _school(db)
    live = await _class(db, minutes=60)
    await _log(db, live, 501, 54)  # 90%

    result = await bridge_live_class_attendance(
        class_id=live.id, session=db, principal=_principal(TEACHER_ID)
    )

    assert len(result.records) == 1
    record = result.records[0]
    assert record.student_id == 501
    assert record.status == AttendanceStatus.PRESENT
    assert result.computed[0].attended_percentage == 90.0
    assert record.date == START.date()
    assert record.period_id is None  # a day-level register row


@pytest.mark.asyncio
async def test_exactly_at_the_threshold_is_present(db: AsyncSession):
    """80% is Present, not Present-minus-one-minute: the threshold is >=."""
    await _school(db)
    live = await _class(db, minutes=60)
    await _log(db, live, 501, 48)  # exactly 80%

    result = await bridge_live_class_attendance(
        class_id=live.id, session=db, principal=_principal(TEACHER_ID)
    )
    assert result.records[0].status == AttendanceStatus.PRESENT


@pytest.mark.asyncio
async def test_below_threshold_with_no_active_minutes_is_absent(db: AsyncSession):
    """A measured zero is a real measurement, not missing data: they joined
    and left, and were in the room for no time at all."""
    await _school(db)
    live = await _class(db, minutes=60)
    await _log(db, live, 501, 0)

    result = await bridge_live_class_attendance(
        class_id=live.id, session=db, principal=_principal(TEACHER_ID)
    )
    assert result.records[0].status == AttendanceStatus.ABSENT
    assert result.computed[0].attended_percentage == 0.0


@pytest.mark.asyncio
async def test_partial_attendance_below_threshold_is_late(db: AsyncSession):
    """Twelve minutes of a sixty minute class is not 'never came'.

    LATE is the existing AttendanceStatus for partial attendance; inventing a
    PARTIAL the rest of the register does not understand would be worse.
    """
    await _school(db)
    live = await _class(db, minutes=60)
    await _log(db, live, 501, 30)  # 50%

    result = await bridge_live_class_attendance(
        class_id=live.id, session=db, principal=_principal(TEACHER_ID)
    )
    assert result.records[0].status == AttendanceStatus.LATE
    assert result.computed[0].attended_percentage == 50.0


@pytest.mark.asyncio
async def test_overlong_telemetry_is_capped_at_100_not_reported_as_150(db: AsyncSession):
    """A class that ran past its scheduled end must not produce 150%."""
    await _school(db)
    live = await _class(db, minutes=60)
    await _log(db, live, 501, 90)

    result = await bridge_live_class_attendance(
        class_id=live.id, session=db, principal=_principal(TEACHER_ID)
    )
    assert result.computed[0].attended_percentage == 100.0
    assert result.records[0].status == AttendanceStatus.PRESENT


@pytest.mark.asyncio
async def test_reconnecting_students_minutes_are_summed(db: AsyncSession):
    """A dropped connection produces two logs; the child was there for both."""
    await _school(db)
    live = await _class(db, minutes=60)
    await _log(db, live, 501, 25)
    await _log(db, live, 501, 25)  # 50 minutes total -> 83.33%

    result = await bridge_live_class_attendance(
        class_id=live.id, session=db, principal=_principal(TEACHER_ID)
    )
    assert result.computed[0].attended_percentage == pytest.approx(83.33, abs=0.01)
    assert result.records[0].status == AttendanceStatus.PRESENT


# ── No result, never a fabricated one ────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_session_with_no_end_time_yields_no_result(db: AsyncSession):
    """The denominator is unknown, so there is no percentage: not 0%, not
    100%, and no register rows for anybody."""
    await _school(db)
    live = await _class(db, minutes=None)
    await _log(db, live, 501, 45)

    result = await bridge_live_class_attendance(
        class_id=live.id, session=db, principal=_principal(TEACHER_ID)
    )

    assert result.session_minutes is None
    assert result.session_minutes_note is not None
    assert result.records == []
    assert await _register_rows(db) == []


@pytest.mark.asyncio
async def test_a_zero_length_session_yields_no_result(db: AsyncSession):
    await _school(db)
    live = await _class(db, minutes=0)
    await _log(db, live, 501, 45)

    result = await bridge_live_class_attendance(
        class_id=live.id, session=db, principal=_principal(TEACHER_ID)
    )
    assert result.session_minutes is None
    assert result.records == []
    assert await _register_rows(db) == []


@pytest.mark.asyncio
async def test_a_student_with_no_telemetry_gets_no_record(db: AsyncSession):
    """The standing rule: no telemetry means no row -- not a 0% and not an
    automatic Absent."""
    await _school(db, student_ids=(501, 502))
    live = await _class(db, minutes=60)
    await _log(db, live, 501, 54)  # only 501 was in the room

    result = await bridge_live_class_attendance(
        class_id=live.id, session=db, principal=_principal(TEACHER_ID)
    )

    assert [r.student_id for r in result.records] == [501]
    rows = await _register_rows(db)
    assert [r.student_id for r in rows] == [501]
    assert 502 not in [s.student_id for s in result.skipped]  # simply not present


@pytest.mark.asyncio
async def test_incomplete_telemetry_is_not_counted_as_zero(db: AsyncSession):
    """A join with no leave means we do not know how long they stayed.

    Counting it as zero would mark a child ABSENT on missing data.
    """
    await _school(db)
    live = await _class(db, minutes=60)
    await _log(db, live, 501, 0, open_ended=True)

    result = await bridge_live_class_attendance(
        class_id=live.id, session=db, principal=_principal(TEACHER_ID)
    )

    assert result.records == []
    assert await _register_rows(db) == []
    assert len(result.skipped) == 1
    assert "no leave recorded" in result.skipped[0].reason


@pytest.mark.asyncio
async def test_a_student_not_on_the_roster_is_skipped(db: AsyncSession):
    """Enrolment is the register. Telemetry from somebody not enrolled in the
    section must not be written onto it."""
    await _school(db, student_ids=(501,))
    live = await _class(db, minutes=60)
    await _log(db, live, 501, 54)
    await _log(db, live, 999, 54)  # not enrolled

    result = await bridge_live_class_attendance(
        class_id=live.id, session=db, principal=_principal(TEACHER_ID)
    )

    assert [r.student_id for r in result.records] == [501]
    assert [s.student_id for s in result.skipped] == [999]
    assert "not actively enrolled" in result.skipped[0].reason.lower()


@pytest.mark.asyncio
async def test_the_teacher_in_the_room_is_not_marked_as_a_student(db: AsyncSession):
    await _school(db)
    live = await _class(db, minutes=60)
    await _log(db, live, TEACHER_ID, 60)

    result = await bridge_live_class_attendance(
        class_id=live.id, session=db, principal=_principal(TEACHER_ID)
    )
    assert result.records == []


# ── Idempotency ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_bridging_twice_is_idempotent(db: AsyncSession):
    """Same rows, same statuses, and no second audit event: pressing the
    button twice must not double-write or fill the trail with noise."""
    await _school(db, student_ids=(501, 502))
    live = await _class(db, minutes=60)
    await _log(db, live, 501, 54)  # PRESENT
    await _log(db, live, 502, 12)  # LATE
    principal = _principal(TEACHER_ID)

    first = await bridge_live_class_attendance(
        class_id=live.id, session=db, principal=principal
    )
    second = await bridge_live_class_attendance(
        class_id=live.id, session=db, principal=principal
    )

    rows = await _register_rows(db)
    assert len(rows) == 2  # still two rows, not four
    assert {r.student_id: r.status for r in rows} == {
        501: AttendanceStatus.PRESENT,
        502: AttendanceStatus.LATE,
    }
    assert [r.id for r in second.records] == [r.id for r in first.records]

    events = await _audit_events(db)
    assert len(events) == 2  # one MARKED per student, and no CORRECTED
    assert all(e.action.value == "marked" for e in events)


@pytest.mark.asyncio
async def test_a_changed_computation_is_recorded_as_a_correction(db: AsyncSession):
    """Late-arriving telemetry that changes the verdict must be visible as a
    correction, not silently applied."""
    await _school(db)
    live = await _class(db, minutes=60)
    await _log(db, live, 501, 12)  # 20% -> LATE
    principal = _principal(TEACHER_ID)

    await bridge_live_class_attendance(class_id=live.id, session=db, principal=principal)

    # The rest of their session lands late.
    await _log(db, live, 501, 50)
    second = await bridge_live_class_attendance(
        class_id=live.id, session=db, principal=principal
    )

    rows = await _register_rows(db)
    assert len(rows) == 1
    assert rows[0].status == AttendanceStatus.PRESENT
    assert second.records[0].status == AttendanceStatus.PRESENT

    events = await _audit_events(db)
    assert [e.action.value for e in events] == ["marked", "corrected"]
    assert events[-1].previous_status == AttendanceStatus.LATE


# ── Never overwrite a human's mark ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_teachers_manual_mark_is_preserved(db: AsyncSession):
    """The whole risk of this feature: a row this bridge did not write is
    left alone, and the caller is told rather than silently overridden."""
    await _school(db)
    live = await _class(db, minutes=60)
    await _log(db, live, 501, 54)  # telemetry says PRESENT

    db.add(
        StudentAttendance(
            student_id=501,
            section_id=SECTION_ID,
            date=START.date(),
            period_id=None,
            status=AttendanceStatus.ABSENT,
            marked_by=TEACHER_ID,
            remarks="Marked by hand: left early for a medical appointment.",
        )
    )
    await db.commit()

    result = await bridge_live_class_attendance(
        class_id=live.id, session=db, principal=_principal(TEACHER_ID)
    )

    assert result.records == []
    assert [p.student_id for p in result.preserved] == [501]
    assert result.preserved[0].status == AttendanceStatus.ABSENT

    rows = await _register_rows(db)
    assert len(rows) == 1
    assert rows[0].status == AttendanceStatus.ABSENT
    assert "medical appointment" in rows[0].remarks
    assert await _audit_events(db) == []


@pytest.mark.asyncio
async def test_an_excused_absence_is_preserved(db: AsyncSession):
    """An approved excuse is a human decision about a note from home; a
    percentage cannot conclude it and must not overwrite it."""
    await _school(db)
    live = await _class(db, minutes=60)
    await _log(db, live, 501, 54)

    db.add(
        StudentAttendance(
            student_id=501,
            section_id=SECTION_ID,
            date=START.date(),
            status=AttendanceStatus.EXCUSED,
            remarks="Parent note approved.",
        )
    )
    await db.commit()

    result = await bridge_live_class_attendance(
        class_id=live.id, session=db, principal=_principal(TEACHER_ID)
    )
    assert result.records == []
    assert result.preserved[0].status == AttendanceStatus.EXCUSED


# ── Authorisation ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_another_teacher_cannot_bridge_my_class(db: AsyncSession):
    await _school(db)
    live = await _class(db, minutes=60)
    await _log(db, live, 501, 54)

    with pytest.raises(HTTPException) as exc:
        await bridge_live_class_attendance(
            class_id=live.id, session=db, principal=_principal(999)
        )
    assert exc.value.status_code == 403
    assert await _register_rows(db) == []


@pytest.mark.asyncio
async def test_a_student_cannot_bridge_a_class(db: AsyncSession):
    await _school(db)
    live = await _class(db, minutes=60)
    await _log(db, live, 501, 54)

    with pytest.raises(HTTPException) as exc:
        await bridge_live_class_attendance(
            class_id=live.id,
            session=db,
            principal=_principal(501, roles=("STUDENT",)),
        )
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_a_campus_bound_admin_cannot_bridge_another_campus(db: AsyncSession):
    """A SCHOOL_ADMIN bypasses 'must teach it' but NOT campus isolation."""
    await _school(db)
    live = await _class(db, minutes=60)
    await _log(db, live, 501, 54)

    with pytest.raises(HTTPException) as exc:
        await bridge_live_class_attendance(
            class_id=live.id,
            session=db,
            principal=_principal(1, roles=("SCHOOL_ADMIN",), campus_id=2),
        )
    assert exc.value.status_code == 404
    assert await _register_rows(db) == []


@pytest.mark.asyncio
async def test_the_owning_teacher_is_allowed(db: AsyncSession):
    """Discrimination check: if the 403/404 tests above ever passed because
    everything is blocked, this fails."""
    await _school(db)
    live = await _class(db, minutes=60)
    await _log(db, live, 501, 54)

    result = await bridge_live_class_attendance(
        class_id=live.id, session=db, principal=_principal(TEACHER_ID)
    )
    assert len(result.records) == 1


@pytest.mark.asyncio
async def test_a_school_admin_of_the_same_campus_may_bridge(db: AsyncSession):
    await _school(db)
    live = await _class(db, minutes=60)
    await _log(db, live, 501, 54)

    result = await bridge_live_class_attendance(
        class_id=live.id,
        session=db,
        principal=_principal(1, roles=("SCHOOL_ADMIN",), campus_id=CAMPUS_ID),
    )
    assert len(result.records) == 1


@pytest.mark.asyncio
async def test_a_class_with_no_section_cannot_be_bridged(db: AsyncSession):
    """No section means no register and no roster. Refuse rather than invent."""
    await _school(db)
    live = await _class(db, minutes=60, section_id=None)
    await _log(db, live, 501, 54)

    with pytest.raises(HTTPException) as exc:
        await bridge_live_class_attendance(
            class_id=live.id, session=db, principal=_principal(TEACHER_ID)
        )
    assert exc.value.status_code == 400


# ── Preview ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_the_preview_writes_nothing(db: AsyncSession):
    await _school(db, student_ids=(501, 502))
    live = await _class(db, minutes=60)
    await _log(db, live, 501, 54)
    await _log(db, live, 502, 12, open_ended=True)

    preview = await preview_live_class_attendance(
        class_id=live.id, session=db, principal=_principal(TEACHER_ID)
    )

    assert preview.session_minutes == 60.0
    assert [c.student_id for c in preview.computed] == [501]
    assert preview.computed[0].status == AttendanceStatus.PRESENT
    assert [s.student_id for s in preview.skipped] == [502]
    assert await _register_rows(db) == []


@pytest.mark.asyncio
async def test_the_preview_and_the_write_agree(db: AsyncSession):
    """The preview is only worth having if it is the same computation."""
    await _school(db)
    live = await _class(db, minutes=60)
    await _log(db, live, 501, 42)  # 70% -> LATE

    preview = await preview_live_class_attendance(
        class_id=live.id, session=db, principal=_principal(TEACHER_ID)
    )
    result = await bridge_live_class_attendance(
        class_id=live.id, session=db, principal=_principal(TEACHER_ID)
    )

    assert preview.computed[0].status == result.records[0].status
    assert (
        preview.computed[0].attended_percentage
        == result.computed[0].attended_percentage
    )


# ── The constants are the policy ─────────────────────────────────────────────


def test_the_threshold_is_eighty_percent():
    assert bridge.PRESENT_THRESHOLD_PERCENT == 80.0


def test_status_for_percentage_is_monotonic():
    assert bridge.status_for_percentage(0.0) == AttendanceStatus.ABSENT
    assert bridge.status_for_percentage(0.1) == AttendanceStatus.LATE
    assert bridge.status_for_percentage(79.9) == AttendanceStatus.LATE
    assert bridge.status_for_percentage(80.0) == AttendanceStatus.PRESENT
    assert bridge.status_for_percentage(100.0) == AttendanceStatus.PRESENT
