"""Attendance correction history, absence excuses, the pastoral queue, and bulk marking.

These cover the four things a school needs daily that the module did not have:
a record of who changed a register and why, somewhere for a parent's absence
note to go, a destination for the absence-streak detector that previously fired
into a void, and batch marking for trips and closures.
"""

import datetime
from datetime import date

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.keycloak_auth import (
    SCHOOL_ADMIN,
    SUPER_ADMIN,
    TEACHER,
    KeycloakUserPrincipal,
)
from src.db.sms_attendance import (
    AbsenceExcuse,
    AttendanceChangeAction,
    AttendanceChangeEvent,
    AttendanceStatus,
    ExcuseStatus,
    PastoralConcern,
    PastoralConcernStatus,
    StudentAttendance,
)
from src.db.sms_campus import ClassSection
from src.routers.sms_attendance import (
    bulk_mark_range,
    create_concern_intervention,
    get_student_attendance_history,
    list_pastoral_queue,
    review_absence_excuse,
    submit_batch_roll_call,
)
from src.schemas.sms_attendance import (
    AbsenceExcuseReview,
    BatchRollCallRequest,
    BulkMarkRangeRequest,
    PastoralInterventionCreate,
    RollCallStudentEntry,
)
from src.services.sms.attendance import ABSENCE_STREAK_THRESHOLD


def _admin(user_id: int = 50) -> KeycloakUserPrincipal:
    return KeycloakUserPrincipal(
        sub="test-superadmin-uuid",
        realm_roles=[SUPER_ADMIN],
        roles={SUPER_ADMIN},
        raw_claims={"lh_user_id": user_id},
    )


def _teacher(user_id: int) -> KeycloakUserPrincipal:
    return KeycloakUserPrincipal(
        sub=f"test-teacher-{user_id}",
        realm_roles=[TEACHER],
        roles={TEACHER},
        raw_claims={"lh_user_id": user_id},
    )


async def _roll_call(
    db: AsyncSession,
    *,
    section_id: int,
    on: date,
    entries: list,
    principal=None,
    reason=None,
):
    return await submit_batch_roll_call(
        payload=BatchRollCallRequest(
            section_id=section_id,
            date=on,
            entries=entries,
            reason=reason,
        ),
        session=db,
        principal=principal or _admin(),
    )


# ---------------------------------------------------------------------------
# Correction history
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_original_marking_time_survives_a_correction(db: AsyncSession):
    """The brief claimed `timestamp` was overwritten on update. It is not.

    Verified here rather than taken on trust: there is no `onupdate` on the
    column and the roll-call handler never assigns it, so the first marking
    time survives. Pinning it means a future refactor that DOES clobber it
    fails loudly instead of silently destroying when a register was taken.
    """
    await _roll_call(
        db,
        section_id=910,
        on=date(2026, 3, 2),
        entries=[RollCallStudentEntry(student_id=8101, status=AttendanceStatus.PRESENT)],
    )
    record = (
        await db.execute(
            select(StudentAttendance).where(StudentAttendance.student_id == 8101)
        )
    ).scalars().one()
    original_timestamp = record.timestamp

    await _roll_call(
        db,
        section_id=910,
        on=date(2026, 3, 2),
        entries=[RollCallStudentEntry(student_id=8101, status=AttendanceStatus.ABSENT)],
    )
    await db.refresh(record)

    assert record.status == AttendanceStatus.ABSENT
    assert record.timestamp == original_timestamp, (
        "The original marking time must survive a correction -- it is when the "
        "register was actually taken."
    )


@pytest.mark.asyncio
async def test_a_correction_preserves_the_prior_status_and_its_author(db: AsyncSession):
    await _roll_call(
        db,
        section_id=911,
        on=date(2026, 3, 3),
        entries=[RollCallStudentEntry(student_id=8102, status=AttendanceStatus.PRESENT)],
        principal=_admin(user_id=61),
    )
    await _roll_call(
        db,
        section_id=911,
        on=date(2026, 3, 3),
        entries=[RollCallStudentEntry(student_id=8102, status=AttendanceStatus.ABSENT)],
        principal=_admin(user_id=62),
        reason="Marked in error; child was not in school",
    )

    events = await get_student_attendance_history(
        student_id=8102, section_id=911, date_from=None, date_to=None,
        session=db, principal=_admin(),
    )
    assert len(events) == 2

    correction = [e for e in events if e.action == AttendanceChangeAction.CORRECTED][0]
    assert correction.previous_status == AttendanceStatus.PRESENT
    assert correction.new_status == AttendanceStatus.ABSENT
    assert correction.changed_by_user_id == 62, "attribution follows the caller"
    assert "Marked in error" in (correction.reason or "")

    first = [e for e in events if e.action == AttendanceChangeAction.MARKED][0]
    assert first.previous_status is None, (
        "The first marking has no previous status -- None, not PRESENT, which "
        "is a real status a student can be given."
    )


@pytest.mark.asyncio
async def test_resubmitting_an_unchanged_register_is_not_logged_as_a_correction(
    db: AsyncSession,
):
    """A teacher pressing save twice must not fill the trail with noise."""
    for _ in range(3):
        await _roll_call(
            db,
            section_id=912,
            on=date(2026, 3, 4),
            entries=[RollCallStudentEntry(student_id=8103, status=AttendanceStatus.PRESENT)],
        )

    events = (
        await db.execute(
            select(AttendanceChangeEvent).where(AttendanceChangeEvent.student_id == 8103)
        )
    ).scalars().all()
    assert len(events) == 1
    assert events[0].action == AttendanceChangeAction.MARKED


# ---------------------------------------------------------------------------
# Absence excuses
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_an_approved_excuse_converts_absent_to_excused(db: AsyncSession):
    """The decision: approval CONVERTS the record, so the percentage moves."""
    await _roll_call(
        db,
        section_id=920,
        on=date(2026, 3, 5),
        entries=[RollCallStudentEntry(student_id=8201, status=AttendanceStatus.ABSENT)],
    )
    excuse = AbsenceExcuse(
        student_id=8201, section_id=920, date=date(2026, 3, 5), reason="Fever"
    )
    db.add(excuse)
    await db.commit()
    await db.refresh(excuse)

    response = await review_absence_excuse(
        excuse_id=excuse.id,
        payload=AbsenceExcuseReview(status=ExcuseStatus.APPROVED),
        session=db,
        principal=_admin(user_id=70),
    )

    assert response.records_converted == 1
    record = (
        await db.execute(
            select(StudentAttendance).where(StudentAttendance.student_id == 8201)
        )
    ).scalars().one()
    assert record.status == AttendanceStatus.EXCUSED

    # The original ABSENT must survive in the trail: the conversion is
    # auditable and reversible, not a quiet rewrite.
    events = (
        await db.execute(
            select(AttendanceChangeEvent).where(AttendanceChangeEvent.student_id == 8201)
        )
    ).scalars().all()
    conversion = [e for e in events if e.action == AttendanceChangeAction.CORRECTED][0]
    assert conversion.previous_status == AttendanceStatus.ABSENT
    assert conversion.new_status == AttendanceStatus.EXCUSED
    assert conversion.changed_by_user_id == 70
    assert "Fever" in (conversion.reason or "")


@pytest.mark.asyncio
async def test_an_approved_excuse_leaves_present_and_late_records_alone(db: AsyncSession):
    """An excuse cannot make an attending child more present, and must not
    quietly erase a punctuality record."""
    await _roll_call(
        db,
        section_id=921,
        on=date(2026, 3, 6),
        entries=[
            RollCallStudentEntry(student_id=8202, status=AttendanceStatus.LATE),
            RollCallStudentEntry(student_id=8203, status=AttendanceStatus.PRESENT),
        ],
    )
    for student_id in (8202, 8203):
        excuse = AbsenceExcuse(
            student_id=student_id, section_id=921, date=date(2026, 3, 6), reason="Note"
        )
        db.add(excuse)
        await db.commit()
        await db.refresh(excuse)
        response = await review_absence_excuse(
            excuse_id=excuse.id,
            payload=AbsenceExcuseReview(status=ExcuseStatus.APPROVED),
            session=db,
            principal=_admin(),
        )
        assert response.records_converted == 0, "only ABSENT converts"

    records = (
        await db.execute(
            select(StudentAttendance).where(StudentAttendance.section_id == 921)
        )
    ).scalars().all()
    by_student = {r.student_id: r.status for r in records}
    assert by_student[8202] == AttendanceStatus.LATE
    assert by_student[8203] == AttendanceStatus.PRESENT


@pytest.mark.asyncio
async def test_a_rejected_excuse_changes_nothing(db: AsyncSession):
    await _roll_call(
        db,
        section_id=922,
        on=date(2026, 3, 7),
        entries=[RollCallStudentEntry(student_id=8204, status=AttendanceStatus.ABSENT)],
    )
    excuse = AbsenceExcuse(
        student_id=8204, section_id=922, date=date(2026, 3, 7), reason="Overslept"
    )
    db.add(excuse)
    await db.commit()
    await db.refresh(excuse)

    response = await review_absence_excuse(
        excuse_id=excuse.id,
        payload=AbsenceExcuseReview(
            status=ExcuseStatus.REJECTED, review_note="Not an acceptable reason"
        ),
        session=db,
        principal=_admin(),
    )
    assert response.records_converted == 0
    record = (
        await db.execute(
            select(StudentAttendance).where(StudentAttendance.student_id == 8204)
        )
    ).scalars().one()
    assert record.status == AttendanceStatus.ABSENT


# ---------------------------------------------------------------------------
# Pastoral queue
# ---------------------------------------------------------------------------


async def _absent_for_streak(db: AsyncSession, *, student_id: int, section_id: int):
    """Mark a student absent on enough consecutive days to trip the threshold."""
    for day_offset in range(ABSENCE_STREAK_THRESHOLD):
        await _roll_call(
            db,
            section_id=section_id,
            on=date(2026, 4, 1) + datetime.timedelta(days=day_offset),
            entries=[RollCallStudentEntry(student_id=student_id, status=AttendanceStatus.ABSENT)],
        )


@pytest.mark.asyncio
async def test_a_student_on_a_streak_appears_in_the_pastoral_queue(db: AsyncSession):
    """The detector already worked; before this it escalated to nothing."""
    await _absent_for_streak(db, student_id=8301, section_id=930)

    concerns = await list_pastoral_queue(
        status_filter=None, limit=100, offset=0, session=db, principal=_admin()
    )
    mine = [c for c in concerns if c.student_id == 8301]
    assert len(mine) == 1, "exactly one concern, not one per absent day"
    assert mine[0].magnitude == ABSENCE_STREAK_THRESHOLD
    assert mine[0].status == PastoralConcernStatus.OPEN
    assert "consecutive" in (mine[0].detail or "")


@pytest.mark.asyncio
async def test_a_continuing_streak_escalates_rather_than_duplicating(db: AsyncSession):
    await _absent_for_streak(db, student_id=8302, section_id=931)
    await _roll_call(
        db,
        section_id=931,
        on=date(2026, 4, 1) + datetime.timedelta(days=ABSENCE_STREAK_THRESHOLD),
        entries=[RollCallStudentEntry(student_id=8302, status=AttendanceStatus.ABSENT)],
    )

    rows = (
        await db.execute(
            select(PastoralConcern).where(PastoralConcern.student_id == 8302)
        )
    ).scalars().all()
    assert len(rows) == 1, "a week's absence must not produce five concerns"
    assert rows[0].magnitude == ABSENCE_STREAK_THRESHOLD + 1


@pytest.mark.asyncio
async def test_a_teacher_cannot_see_pastoral_flags_for_a_section_they_do_not_teach(
    db: AsyncSession,
):
    """Role-permitted, section-scoped: a form tutor should know about their own
    tutee, but nobody browses the whole school's at-risk list."""
    taught = ClassSection(
        campus_id=1, grade_level="Grade 9", section_name="T", class_teacher_id=7401
    )
    other = ClassSection(
        campus_id=1, grade_level="Grade 9", section_name="O", class_teacher_id=7402
    )
    db.add(taught)
    db.add(other)
    await db.commit()
    await db.refresh(taught)
    await db.refresh(other)

    await _absent_for_streak(db, student_id=8401, section_id=taught.id)
    await _absent_for_streak(db, student_id=8402, section_id=other.id)

    visible = await list_pastoral_queue(
        status_filter=None, limit=100, offset=0, session=db, principal=_teacher(7401)
    )
    student_ids = {c.student_id for c in visible}
    assert 8401 in student_ids, "a teacher must see their own section's concerns"
    assert 8402 not in student_ids, (
        "a teacher must NOT see concerns for a section they do not teach"
    )


@pytest.mark.asyncio
async def test_a_teacher_with_no_sections_sees_nothing_rather_than_everything(
    db: AsyncSession,
):
    """The empty-scope case: [] means 'no sections', not 'unrestricted'."""
    await _absent_for_streak(db, student_id=8403, section_id=941)

    visible = await list_pastoral_queue(
        status_filter=None, limit=100, offset=0, session=db, principal=_teacher(9999)
    )
    assert visible == []


@pytest.mark.asyncio
async def test_recording_an_intervention_moves_the_concern_off_open(db: AsyncSession):
    """The queue must distinguish 'nobody has looked' from 'a call was made'."""
    await _absent_for_streak(db, student_id=8501, section_id=950)
    concern = (
        await db.execute(
            select(PastoralConcern).where(PastoralConcern.student_id == 8501)
        )
    ).scalars().one()

    intervention = await create_concern_intervention(
        concern_id=concern.id,
        payload=PastoralInterventionCreate(
            action="called_guardian", note="Spoke to mother", outcome="Returning Monday"
        ),
        session=db,
        principal=_admin(user_id=77),
    )
    assert intervention.acted_by_user_id == 77
    await db.refresh(concern)
    assert concern.status == PastoralConcernStatus.IN_PROGRESS


# ---------------------------------------------------------------------------
# Bulk marking
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bulk_marking_does_not_silently_overwrite_a_differing_record(
    db: AsyncSession,
):
    """A trip marked EXCUSED must not quietly erase a teacher's ABSENT."""
    await _roll_call(
        db,
        section_id=960,
        on=date(2026, 5, 5),
        entries=[
            RollCallStudentEntry(student_id=8601, status=AttendanceStatus.ABSENT),
            RollCallStudentEntry(student_id=8602, status=AttendanceStatus.PRESENT),
        ],
    )

    response = await bulk_mark_range(
        payload=BulkMarkRangeRequest(
            section_id=960,
            start_date=date(2026, 5, 5),
            end_date=date(2026, 5, 6),
            status=AttendanceStatus.EXCUSED,
            student_ids=[8601, 8602],
            reason="Field trip",
        ),
        session=db,
        principal=_admin(),
    )

    skipped_students = {(s.student_id, s.existing_status) for s in response.skipped}
    assert (8601, AttendanceStatus.ABSENT) in skipped_students
    assert (8602, AttendanceStatus.PRESENT) in skipped_students
    assert response.records_updated == 0
    # 5 May already existed for both; 6 May is new for both.
    assert response.records_created == 2

    unchanged = (
        await db.execute(
            select(StudentAttendance).where(
                StudentAttendance.student_id == 8601,
                StudentAttendance.date == date(2026, 5, 5),
            )
        )
    ).scalars().one()
    assert unchanged.status == AttendanceStatus.ABSENT


@pytest.mark.asyncio
async def test_bulk_overwrite_is_possible_and_is_recorded_in_the_trail(db: AsyncSession):
    await _roll_call(
        db,
        section_id=961,
        on=date(2026, 5, 7),
        entries=[RollCallStudentEntry(student_id=8603, status=AttendanceStatus.ABSENT)],
    )

    response = await bulk_mark_range(
        payload=BulkMarkRangeRequest(
            section_id=961,
            start_date=date(2026, 5, 7),
            end_date=date(2026, 5, 7),
            status=AttendanceStatus.EXCUSED,
            student_ids=[8603],
            reason="School closure - snow",
            overwrite_existing=True,
        ),
        session=db,
        principal=_admin(user_id=88),
    )
    assert response.records_updated == 1
    assert response.skipped == []

    events = (
        await db.execute(
            select(AttendanceChangeEvent).where(AttendanceChangeEvent.student_id == 8603)
        )
    ).scalars().all()
    correction = [e for e in events if e.action == AttendanceChangeAction.CORRECTED][0]
    assert correction.previous_status == AttendanceStatus.ABSENT
    assert correction.new_status == AttendanceStatus.EXCUSED
    assert correction.changed_by_user_id == 88
    assert "snow" in (correction.reason or "")


@pytest.mark.asyncio
async def test_bulk_marking_refuses_an_absurd_date_range(db: AsyncSession):
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        await bulk_mark_range(
            payload=BulkMarkRangeRequest(
                section_id=962,
                start_date=date(2026, 1, 1),
                end_date=date(2030, 1, 1),
                status=AttendanceStatus.PRESENT,
                student_ids=[8604],
            ),
            session=db,
            principal=_admin(),
        )
    assert exc.value.status_code == 400
    assert "longer than a school year" in exc.value.detail


@pytest.mark.asyncio
async def test_bulk_marking_refuses_when_it_cannot_infer_a_roster(db: AsyncSession):
    """Never invent a roster: no records and no student_ids means refuse."""
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        await bulk_mark_range(
            payload=BulkMarkRangeRequest(
                section_id=963,
                start_date=date(2026, 5, 8),
                end_date=date(2026, 5, 8),
                status=AttendanceStatus.PRESENT,
            ),
            session=db,
            principal=_admin(),
        )
    assert exc.value.status_code == 400
    assert "No students to mark" in exc.value.detail


@pytest.mark.asyncio
async def test_the_concern_survives_a_failing_guardian_notification(db: AsyncSession):
    """The point of the pastoral queue: detection must outlive an unsent email.

    Before this work the ONLY escalation was a guardian email, so with mail
    unconfigured -- the default in this deployment -- a detected streak reached
    nobody and left no trace. Recording the concern in the same try block as
    the notification would have rebuilt that failure exactly: a mail outage
    would take the durable record down with it.

    This forces the notification to raise and asserts the concern is still
    there. It is the regression test for the ordering, not for the email.
    """
    from unittest.mock import AsyncMock, patch

    with patch(
        "src.routers.sms_attendance.bus.emit",
        new=AsyncMock(side_effect=RuntimeError("mail provider down")),
    ) as failing_emit:
        await _absent_for_streak(db, student_id=8701, section_id=970)

    assert failing_emit.await_count >= 1, "the notification really was attempted"

    concerns = (
        await db.execute(
            select(PastoralConcern).where(PastoralConcern.student_id == 8701)
        )
    ).scalars().all()
    assert len(concerns) == 1, (
        "a concern must be recorded even when the guardian notification fails"
    )
    assert concerns[0].magnitude == ABSENCE_STREAK_THRESHOLD
