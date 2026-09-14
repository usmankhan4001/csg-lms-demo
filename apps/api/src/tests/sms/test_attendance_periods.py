"""Period-level attendance: six registers a day must not overwrite each other.

Before `StudentAttendance.period_id` existed the unique key was
(student_id, section_id, date) and the roll-call handler upserted on it, so in
a school running 6-8 periods taking period 5's register SILENTLY OVERWROTE
period 1's. A student marked absent first thing and present after lunch ended
the day looking present, with no warning and no history.

These tests pin both register models -- per-period and whole-day -- and the
day-collapsing rule that stops six period rows reporting as six days.
"""

import pytest
from datetime import date
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.keycloak_auth import SUPER_ADMIN, KeycloakUserPrincipal
from src.db.sms_attendance import AttendanceStatus, StudentAttendance
from src.db.sms_timetable import ClassPeriod
from src.routers.sms_attendance import (
    get_monthly_student_attendance,
    submit_batch_roll_call,
)
from src.schemas.sms_attendance import BatchRollCallRequest, RollCallStudentEntry
from src.services.sms.attendance import (
    ABSENCE_STREAK_THRESHOLD,
    collapse_to_daily_status,
    get_consecutive_absence_streak,
)


def _principal() -> KeycloakUserPrincipal:
    """Superadmin: these tests exercise register mechanics, not ownership,
    which is covered in src/tests/security/test_school_ownership.py."""
    return KeycloakUserPrincipal(
        sub="test-superadmin-uuid",
        realm_roles=[SUPER_ADMIN],
        roles={SUPER_ADMIN},
        raw_claims={"lh_user_id": 50},
    )


async def _make_periods(db: AsyncSession, count: int = 6) -> list:
    periods = [
        ClassPeriod(
            campus_id=1,
            period_number=n,
            start_time=f"{7 + n:02d}:00",
            end_time=f"{7 + n:02d}:45",
            name=f"Period {n}",
        )
        for n in range(1, count + 1)
    ]
    for p in periods:
        db.add(p)
    await db.commit()
    for p in periods:
        await db.refresh(p)
    return periods


async def _roll_call(db, section_id, when, entries, period_id=None):
    return await submit_batch_roll_call(
        payload=BatchRollCallRequest(
            section_id=section_id,
            date=when,
            entries=entries,
            marked_by=50,
            period_id=period_id,
        ),
        session=db,
        principal=_principal(),
    )


@pytest.mark.asyncio
async def test_taking_period_5_does_not_overwrite_period_1(db: AsyncSession):
    """THE BUG. Absent in period 1, present in period 5 -- both must survive."""
    periods = await _make_periods(db)
    day = date(2026, 9, 14)

    await _roll_call(
        db, 1, day,
        [RollCallStudentEntry(student_id=101, status=AttendanceStatus.ABSENT)],
        period_id=periods[0].id,
    )
    await _roll_call(
        db, 1, day,
        [RollCallStudentEntry(student_id=101, status=AttendanceStatus.PRESENT)],
        period_id=periods[4].id,
    )

    rows = (
        await db.execute(
            select(StudentAttendance).where(
                StudentAttendance.student_id == 101,
                StudentAttendance.date == day,
            )
        )
    ).scalars().all()

    assert len(rows) == 2, (
        "Period 5's register overwrote period 1's -- the exact data loss "
        f"period_id exists to prevent. Rows: {[(r.period_id, r.status) for r in rows]}"
    )
    by_period = {r.period_id: r.status for r in rows}
    assert by_period[periods[0].id] == AttendanceStatus.ABSENT
    assert by_period[periods[4].id] == AttendanceStatus.PRESENT


@pytest.mark.asyncio
async def test_six_periods_in_one_day_all_coexist(db: AsyncSession):
    periods = await _make_periods(db)
    day = date(2026, 9, 14)

    for p in periods:
        await _roll_call(
            db, 1, day,
            [RollCallStudentEntry(student_id=202, status=AttendanceStatus.PRESENT)],
            period_id=p.id,
        )

    rows = (
        await db.execute(
            select(StudentAttendance).where(StudentAttendance.student_id == 202)
        )
    ).scalars().all()
    assert len(rows) == 6
    assert {r.period_id for r in rows} == {p.id for p in periods}


@pytest.mark.asyncio
async def test_resubmitting_the_same_period_updates_in_place(db: AsyncSession):
    """A correction to period 3 must edit period 3, not add a second row."""
    periods = await _make_periods(db)
    day = date(2026, 9, 14)

    await _roll_call(
        db, 1, day,
        [RollCallStudentEntry(student_id=303, status=AttendanceStatus.ABSENT)],
        period_id=periods[2].id,
    )
    await _roll_call(
        db, 1, day,
        [RollCallStudentEntry(student_id=303, status=AttendanceStatus.PRESENT,
                              remarks="arrived late, marked in error")],
        period_id=periods[2].id,
    )

    rows = (
        await db.execute(
            select(StudentAttendance).where(StudentAttendance.student_id == 303)
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].status == AttendanceStatus.PRESENT
    assert rows[0].remarks == "arrived late, marked in error"


@pytest.mark.asyncio
async def test_day_level_register_still_works_with_null_period(db: AsyncSession):
    """A primary school takes one register a day and has no periods."""
    day = date(2026, 9, 14)
    await _roll_call(
        db, 7, day,
        [RollCallStudentEntry(student_id=404, status=AttendanceStatus.PRESENT)],
    )

    rows = (
        await db.execute(
            select(StudentAttendance).where(StudentAttendance.student_id == 404)
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].period_id is None


@pytest.mark.asyncio
async def test_duplicate_day_level_rows_are_still_prevented(db: AsyncSession):
    """NULL != NULL, so the unique constraint cannot protect the day-level
    case -- the handler's read-before-write has to. Resubmitting a day
    register must UPDATE, never insert a second row."""
    day = date(2026, 9, 14)
    for status in (AttendanceStatus.PRESENT, AttendanceStatus.ABSENT, AttendanceStatus.LATE):
        await _roll_call(
            db, 7, day, [RollCallStudentEntry(student_id=505, status=status)]
        )

    rows = (
        await db.execute(
            select(StudentAttendance).where(StudentAttendance.student_id == 505)
        )
    ).scalars().all()
    assert len(rows) == 1, (
        f"Day-level uniqueness leaked: {len(rows)} rows for one student/date. "
        "The unique constraint spans a nullable period_id and cannot catch this."
    )
    assert rows[0].status == AttendanceStatus.LATE


@pytest.mark.asyncio
async def test_a_day_register_and_a_period_register_do_not_collide(db: AsyncSession):
    """Mixing the models is not forbidden; they must not overwrite each other."""
    periods = await _make_periods(db)
    day = date(2026, 9, 14)

    await _roll_call(
        db, 1, day, [RollCallStudentEntry(student_id=606, status=AttendanceStatus.PRESENT)]
    )
    await _roll_call(
        db, 1, day,
        [RollCallStudentEntry(student_id=606, status=AttendanceStatus.ABSENT)],
        period_id=periods[1].id,
    )

    rows = (
        await db.execute(
            select(StudentAttendance).where(StudentAttendance.student_id == 606)
        )
    ).scalars().all()
    assert len(rows) == 2
    assert {r.period_id for r in rows} == {None, periods[1].id}


# ── The streak rule ──

@pytest.mark.asyncio
async def test_absent_all_day_counts_as_one_day_not_six(db: AsyncSession):
    """THE FALSE-ALARM CASE. Six absent periods on day one must not trip a
    three-day threshold and tell parents their child missed six days."""
    periods = await _make_periods(db)
    day = date(2026, 9, 14)

    for p in periods:
        await _roll_call(
            db, 1, day,
            [RollCallStudentEntry(student_id=707, status=AttendanceStatus.ABSENT)],
            period_id=p.id,
        )

    streak = await get_consecutive_absence_streak(db, 707, 1)
    assert streak == 1, f"Six period rows counted as {streak} days"
    assert streak < ABSENCE_STREAK_THRESHOLD


@pytest.mark.asyncio
async def test_one_present_period_means_the_day_is_not_an_absence(db: AsyncSession):
    """Missing period 1 and attending the rest is a late arrival, not a day
    absent -- it must break the streak."""
    periods = await _make_periods(db)

    # One full absent day, then a day with one period attended. Deliberately
    # kept below ABSENCE_STREAK_THRESHOLD so this stays a test of the
    # collapsing rule and does not reach the guardian-notification path.
    for day_offset, statuses in [
        (1, [AttendanceStatus.ABSENT] * 3),
        (2, [AttendanceStatus.ABSENT, AttendanceStatus.ABSENT, AttendanceStatus.PRESENT]),
    ]:
        day = date(2026, 9, 10 + day_offset)
        for p, st in zip(periods[:3], statuses):
            await _roll_call(
                db, 1, day,
                [RollCallStudentEntry(student_id=808, status=st)],
                period_id=p.id,
            )

    # The most recent day had a present period, so the streak is 0 -- one
    # attended period ends it, even though two of three periods were missed.
    assert await get_consecutive_absence_streak(db, 808, 1) == 0


@pytest.mark.asyncio
async def test_three_fully_absent_days_still_reach_the_threshold(db: AsyncSession):
    """The alert must still fire for a genuine three-day absence."""
    periods = await _make_periods(db)
    for offset in range(3):
        day = date(2026, 9, 14 + offset)
        for p in periods[:4]:
            await _roll_call(
                db, 1, day,
                [RollCallStudentEntry(student_id=909, status=AttendanceStatus.ABSENT)],
                period_id=p.id,
            )

    assert await get_consecutive_absence_streak(db, 909, 1) == ABSENCE_STREAK_THRESHOLD


@pytest.mark.asyncio
async def test_day_level_streak_behaviour_is_unchanged(db: AsyncSession):
    """Regression guard: the primary-school path must behave exactly as
    before this column existed."""
    for offset in range(3):
        await _roll_call(
            db, 7, date(2026, 9, 14 + offset),
            [RollCallStudentEntry(student_id=1010, status=AttendanceStatus.ABSENT)],
        )
    assert await get_consecutive_absence_streak(db, 1010, 7) == 3


# ── Day-collapsing used by the reports ──

def test_collapse_takes_the_worst_status_of_the_day():
    class _Rec:
        def __init__(self, d, s):
            self.date, self.status = d, s

    day = date(2026, 9, 14)
    collapsed = collapse_to_daily_status([
        _Rec(day, AttendanceStatus.PRESENT),
        _Rec(day, AttendanceStatus.ABSENT),
        _Rec(day, AttendanceStatus.PRESENT),
    ])
    assert collapsed[day] == AttendanceStatus.ABSENT, (
        "A child who missed a period was reported simply 'present'"
    )


@pytest.mark.asyncio
async def test_reporting_and_streak_rules_are_deliberately_different(db: AsyncSession):
    """A day with one missed period reports as ABSENT (the parent needs to see
    it) but does NOT count toward an absence streak (the child was in school).

    These two rules look like duplication and are not. Collapsing them into one
    would either hide missed periods from parents or fire "absent 3 days in a
    row" at a child who attended every day.
    """
    periods = await _make_periods(db)
    day = date(2026, 9, 14)
    for p, st in zip(periods[:3], [AttendanceStatus.ABSENT,
                                   AttendanceStatus.PRESENT,
                                   AttendanceStatus.PRESENT]):
        await _roll_call(
            db, 1, day,
            [RollCallStudentEntry(student_id=1212, status=st)],
            period_id=p.id,
        )

    rows = (
        await db.execute(
            select(StudentAttendance).where(StudentAttendance.student_id == 1212)
        )
    ).scalars().all()

    # Reporting: worst status wins, so the day surfaces as ABSENT.
    assert collapse_to_daily_status(rows)[day] == AttendanceStatus.ABSENT
    # Streak: not a full absence, so it does not count.
    assert await get_consecutive_absence_streak(db, 1212, 1) == 0


def test_collapse_preserves_input_date_order():
    """The streak counter queries most-recent-first and relies on this."""
    class _Rec:
        def __init__(self, d, s):
            self.date, self.status = d, s

    d3, d2, d1 = date(2026, 9, 16), date(2026, 9, 15), date(2026, 9, 14)
    collapsed = collapse_to_daily_status([
        _Rec(d3, AttendanceStatus.ABSENT),
        _Rec(d2, AttendanceStatus.PRESENT),
        _Rec(d1, AttendanceStatus.ABSENT),
    ])
    assert list(collapsed.keys()) == [d3, d2, d1]


@pytest.mark.asyncio
async def test_monthly_stats_count_days_not_period_rows(db: AsyncSession):
    """A 6-period day must report as one day, not six."""
    periods = await _make_periods(db)
    day = date(2026, 9, 14)
    for p in periods:
        await _roll_call(
            db, 1, day,
            [RollCallStudentEntry(student_id=1111, status=AttendanceStatus.PRESENT)],
            period_id=p.id,
        )

    sheet = await get_monthly_student_attendance(
        student_id=1111, year=2026, month=9, section_id=1,
        session=db, principal=_principal(),
    )
    assert sheet.stats.total_days == 1, (
        f"Six periods reported as {sheet.stats.total_days} days"
    )
    assert sheet.stats.present_days == 1
    # The raw per-period records stay available for drill-down.
    assert len(sheet.daily_records) == 6


@pytest.mark.asyncio
async def test_no_roll_call_reports_absence_not_zero_percent(db):
    """A month with no register taken must NOT report 0% attendance.

    "0%" tells a parent their child attended nothing. The truth is that nobody
    has marked a register yet -- an entirely different fact, and the one the
    school needs to act on. This codebase has torn out the same
    no-data-reads-as-a-real-figure pattern three times: a 4.0 GPA for a student
    with zero grades, an invented parent digest, and a fabricated "F" persisted
    to a report card.
    """
    from src.routers.sms_attendance import get_monthly_student_attendance

    sheet = await get_monthly_student_attendance(
        student_id=999_999,  # nobody has ever marked this student
        year=2026,
        month=9,
        section_id=None,
        session=db,
        principal=_principal(),
    )

    assert sheet.stats.total_days == 0
    assert sheet.stats.attendance_percentage is None, (
        "No roll-call taken must be None, never 0.0 -- absence of data is not "
        "a measured value of zero."
    )
    assert sheet.daily_records == []
