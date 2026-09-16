import pytest
from datetime import date, timedelta
from fastapi import HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_attendance import (
    AttendanceLeaveRequest,
    AttendanceStatus,
    LeaveRequestStatus,
    PastoralConcern,
    StudentAttendance,
)
from src.db.sms_campus import ClassSection, StudentEnrollment
from src.schemas.sms_attendance import (
    BatchRollCallRequest,
    LeaveRequestCreate,
    LeaveRequestUpdateStatus,
    RollCallStudentEntry,
)
from src.core.keycloak_auth import SUPER_ADMIN, KeycloakUserPrincipal
from src.routers.sms_attendance import (
    get_monthly_student_attendance,
    list_leave_requests,
    submit_batch_roll_call,
    submit_leave_request,
    update_leave_request_status,
)
from src.services.sms.attendance import (
    ABSENCE_STREAK_THRESHOLD,
    get_consecutive_absence_streak,
)


def _superadmin_principal() -> KeycloakUserPrincipal:
    """These tests call the router coroutine directly rather than over HTTP, so
    FastAPI never resolves `principal` — without passing one explicitly the
    parameter stays as the raw `Depends(...)` sentinel and
    `assert_owns_section_or_privileged` fails on it. A superadmin bypasses the
    section-ownership check, keeping these tests focused on roll-call upsert
    behavior; ownership enforcement itself is covered separately in
    src/tests/security/test_school_ownership.py."""
    return KeycloakUserPrincipal(
        sub="test-superadmin-uuid",
        realm_roles=[SUPER_ADMIN],
        roles={SUPER_ADMIN},
        raw_claims={"lh_user_id": 50},
    )


@pytest.mark.asyncio
async def test_batch_roll_call_upsert(db: AsyncSession):
    """Test 1-click batch roll-call attendance submission and upsert behavior."""
    req_date = date(2026, 9, 10)
    entries = [
        RollCallStudentEntry(student_id=101, status=AttendanceStatus.PRESENT, remarks="On time"),
        RollCallStudentEntry(student_id=102, status=AttendanceStatus.ABSENT, remarks="Sick"),
        RollCallStudentEntry(student_id=103, status=AttendanceStatus.LATE, remarks="15 mins late"),
    ]
    payload = BatchRollCallRequest(
        section_id=1,
        date=req_date,
        entries=entries,
        marked_by=50,
    )

    response = await submit_batch_roll_call(payload=payload, session=db, principal=_superadmin_principal())
    assert response.success is True
    assert response.total_submitted == 3
    assert response.total_recorded == 3
    assert len(response.records) == 3

    # Verify in db
    stmt = select(StudentAttendance).where(StudentAttendance.section_id == 1)
    res = await db.execute(stmt)
    records = res.scalars().all()
    assert len(records) == 3

    # Re-submit with update (upsert) for student 102 (ABSENT -> EXCUSED)
    updated_entries = [
        RollCallStudentEntry(student_id=102, status=AttendanceStatus.EXCUSED, remarks="Doctor note provided"),
    ]
    update_payload = BatchRollCallRequest(
        section_id=1,
        date=req_date,
        entries=updated_entries,
        marked_by=50,
    )
    update_res = await submit_batch_roll_call(payload=update_payload, session=db, principal=_superadmin_principal())
    assert update_res.total_recorded == 1
    assert update_res.records[0].status == AttendanceStatus.EXCUSED
    assert update_res.records[0].remarks == "Doctor note provided"


@pytest.mark.asyncio
async def test_monthly_student_attendance_sheet(db: AsyncSession):
    """Test calculating monthly attendance breakdown and percentage."""
    student_id = 201
    section_id = 2
    test_dates = [
        (date(2026, 9, 1), AttendanceStatus.PRESENT),
        (date(2026, 9, 2), AttendanceStatus.PRESENT),
        (date(2026, 9, 3), AttendanceStatus.LATE),     # 0.5 weight
        (date(2026, 9, 4), AttendanceStatus.ABSENT),   # 0.0 weight
        (date(2026, 9, 5), AttendanceStatus.EXCUSED),  # 1.0 weight
    ]

    for d, st in test_dates:
        att = StudentAttendance(
            student_id=student_id,
            section_id=section_id,
            date=d,
            status=st,
            marked_by=1,
        )
        db.add(att)
    await db.commit()

    sheet = await get_monthly_student_attendance(
        student_id=student_id,
        year=2026,
        month=9,
        section_id=section_id,
        session=db,
    )

    assert sheet.student_id == student_id
    assert sheet.stats.total_days == 5
    assert sheet.stats.present_days == 2
    assert sheet.stats.late_days == 1
    assert sheet.stats.absent_days == 1
    assert sheet.stats.excused_days == 1
    # Effective present: 2 + 0.5 + 1.0 = 3.5 / 5.0 * 100 = 70.0%
    assert sheet.stats.attendance_percentage == 70.0
    assert len(sheet.daily_records) == 5


@pytest.mark.asyncio
async def test_leave_requests_lifecycle(db: AsyncSession):
    """Test student leave request creation, listing, and approval."""
    payload = LeaveRequestCreate(
        student_id=301,
        start_date=date(2026, 9, 15),
        end_date=date(2026, 9, 18),
        reason="Family event",
    )
    # Filing is now bound to the caller: a leave request may only be
    # submitted for yourself or your own child, so this acts as staff.
    created = await submit_leave_request(
        payload=payload, session=db, principal=_superadmin_principal()
    )
    assert created.id is not None
    assert created.student_id == 301
    assert created.status == LeaveRequestStatus.PENDING

    # List requests
    requests = await list_leave_requests(student_id=301, session=db)
    assert len(requests) == 1
    assert requests[0].id == created.id

    # Update status to APPROVED
    approver = _superadmin_principal()
    updated = await update_leave_request_status(
        request_id=created.id,
        payload=LeaveRequestUpdateStatus(status=LeaveRequestStatus.APPROVED, approved_by=99),
        session=db,
        principal=approver,
    )
    assert updated.status == LeaveRequestStatus.APPROVED
    # approved_by now follows the AUTHENTICATED approver, not the body's 99 --
    # an approval must not be recordable against someone who never made it.
    assert updated.approved_by == approver.raw_claims["lh_user_id"]


# ── Absence-streak parent notification ──

@pytest.mark.asyncio
async def test_roll_call_emits_absence_streak_at_threshold(db: AsyncSession):
    """3 consecutive absences must actually notify the family.

    UPDATED WITH A DELIBERATE BEHAVIOUR CHANGE (Lane J). This previously
    asserted `bus.emit("student.absence_streak", ...)` on the in-process event
    bus. That bus delivered mail correctly, but it bypassed notification
    preferences, duplicate suppression and the delivery log -- so a parent
    could not switch the message off, re-saving a register re-sent it, and
    nobody could answer "was the family actually told?".

    The streak now goes through the notification fabric instead. The test
    asserts the same guarantee at the new seam: crossing the threshold results
    in exactly one streak notification naming the right student.
    """
    from unittest.mock import AsyncMock, patch
    from src.services.sms.attendance import ABSENCE_STREAK_THRESHOLD

    student_id, section_id = 901, 91
    base_day = 1

    # Pre-seed the first (threshold - 1) absences directly.
    for offset in range(ABSENCE_STREAK_THRESHOLD - 1):
        db.add(
            StudentAttendance(
                student_id=student_id,
                section_id=section_id,
                date=date(2026, 10, base_day + offset),
                status=AttendanceStatus.ABSENT,
                marked_by=1,
            )
        )
    await db.commit()

    # A guardian must exist, or the handler correctly declines to notify
    # anyone and there is nothing to assert.
    from datetime import datetime as _dt

    from src.db.sms_identity import StudentGuardian
    from src.db.users import User

    db.add(
        User(
            id=9901, username="g901", first_name="Parent", last_name="Nine",
            email="g901@test.local", password="x", user_uuid="uuid-9901",
            creation_date=str(_dt.now()), update_date=str(_dt.now()),
        )
    )
    await db.flush()
    db.add(StudentGuardian(guardian_user_id=9901, student_id=student_id))
    await db.commit()

    # The threshold-hitting absence arrives through the real roll-call endpoint.
    with patch(
        "src.routers.sms_attendance.raise_school_event", new=AsyncMock()
    ) as mock_raise:
        await submit_batch_roll_call(
            payload=BatchRollCallRequest(
                section_id=section_id,
                date=date(2026, 10, base_day + ABSENCE_STREAK_THRESHOLD - 1),
                entries=[
                    RollCallStudentEntry(student_id=student_id, status=AttendanceStatus.ABSENT)
                ],
                marked_by=50,
            ),
            session=db,
            principal=_superadmin_principal(),
        )

    mock_raise.assert_awaited_once()
    kwargs = mock_raise.await_args.kwargs
    assert kwargs["event_key"] == "attendance.absence_streak"
    assert kwargs["context"]["streak"] == ABSENCE_STREAK_THRESHOLD
    assert kwargs["related_id"] == student_id
    # The streak message REPLACES the daily one rather than arriving alongside
    # it -- two emails a minute apart saying the same thing is how a school
    # teaches a family to stop reading.
    assert mock_raise.await_count == 1


@pytest.mark.asyncio
async def test_single_absence_does_not_notify(db: AsyncSession):
    """One absent day is normal; alerting on it would train parents to ignore."""
    from unittest.mock import AsyncMock, patch

    with patch("src.core.event_bus.bus.emit", new=AsyncMock()) as mock_emit:
        await submit_batch_roll_call(
            payload=BatchRollCallRequest(
                section_id=92,
                date=date(2026, 10, 5),
                entries=[RollCallStudentEntry(student_id=902, status=AttendanceStatus.ABSENT)],
                marked_by=50,
            ),
            session=db,
            principal=_superadmin_principal(),
        )

    mock_emit.assert_not_awaited()


@pytest.mark.asyncio
async def test_present_students_never_trigger_a_streak_check(db: AsyncSession):
    from unittest.mock import AsyncMock, patch

    with patch("src.core.event_bus.bus.emit", new=AsyncMock()) as mock_emit:
        await submit_batch_roll_call(
            payload=BatchRollCallRequest(
                section_id=93,
                date=date(2026, 10, 6),
                entries=[
                    RollCallStudentEntry(student_id=903, status=AttendanceStatus.PRESENT),
                    RollCallStudentEntry(student_id=904, status=AttendanceStatus.LATE),
                ],
                marked_by=50,
            ),
            session=db,
            principal=_superadmin_principal(),
        )

    mock_emit.assert_not_awaited()


@pytest.mark.asyncio
async def test_notification_failure_never_fails_the_roll_call(db: AsyncSession):
    """A teacher's attendance submission must succeed even if the alert path
    is completely broken -- the attendance record is the source of truth."""
    from unittest.mock import AsyncMock, patch

    with patch(
        "src.core.event_bus.bus.emit",
        new=AsyncMock(side_effect=RuntimeError("subscriber exploded")),
    ):
        response = await submit_batch_roll_call(
            payload=BatchRollCallRequest(
                section_id=94,
                date=date(2026, 10, 7),
                entries=[RollCallStudentEntry(student_id=905, status=AttendanceStatus.ABSENT)],
                marked_by=50,
            ),
            session=db,
            principal=_superadmin_principal(),
        )

    assert response.success is True
    assert response.total_recorded == 1


@pytest.mark.asyncio
async def test_subscriber_emails_every_guardian_of_the_student(engine):
    """Exercises the REAL subscriber end-to-end: guardian lookup -> send_email.
    The tests above patch `bus.emit`, so without this the actual notification
    body/recipients would be entirely unverified."""
    from contextlib import asynccontextmanager
    from datetime import datetime
    from unittest.mock import patch

    from sqlalchemy.ext.asyncio import async_sessionmaker
    from src.db.sms_identity import StudentGuardian
    from src.db.users import User
    from src.services.sms.attendance import _notify_guardians_of_absence_streak

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as setup:
        setup.add(
            User(
                id=950, username="child950", first_name="Ayesha", last_name="Khan",
                email="child950@test.local", password="x", user_uuid="uuid-950",
                creation_date=str(datetime.now()), update_date=str(datetime.now()),
            )
        )
        for gid, email in ((951, "mum@test.local"), (952, "dad@test.local")):
            setup.add(
                User(
                    id=gid, username=f"g{gid}", first_name="Parent", last_name=str(gid),
                    email=email, password="x", user_uuid=f"uuid-{gid}",
                    creation_date=str(datetime.now()), update_date=str(datetime.now()),
                )
            )
            setup.add(StudentGuardian(guardian_user_id=gid, student_id=950))
        await setup.commit()

    @asynccontextmanager
    async def _factory_cm():
        async with factory() as s:
            yield s

    with patch("src.core.events.database._async_session_factory", _factory_cm), \
         patch("src.services.email.utils.send_email") as mock_send:
        await _notify_guardians_of_absence_streak({"student_id": 950, "streak": 3})

    recipients = sorted(call.args[0] for call in mock_send.call_args_list)
    assert recipients == ["dad@test.local", "mum@test.local"]
    # The student's real name should appear, not an opaque "Student #950".
    assert "Ayesha Khan" in mock_send.call_args_list[0].args[1]
    assert "3 consecutive" in mock_send.call_args_list[0].args[2]


@pytest.mark.asyncio
async def test_subscriber_survives_a_guardian_with_a_bad_address(engine):
    """One failing send must not stop the other guardian being notified."""
    from contextlib import asynccontextmanager
    from datetime import datetime
    from unittest.mock import patch

    from sqlalchemy.ext.asyncio import async_sessionmaker
    from src.db.sms_identity import StudentGuardian
    from src.db.users import User
    from src.services.sms.attendance import _notify_guardians_of_absence_streak

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as setup:
        setup.add(
            User(
                id=960, username="child960", first_name="Bilal", last_name="Ahmed",
                email="child960@test.local", password="x", user_uuid="uuid-960",
                creation_date=str(datetime.now()), update_date=str(datetime.now()),
            )
        )
        for gid, email in ((961, "broken@test.local"), (962, "ok@test.local")):
            setup.add(
                User(
                    id=gid, username=f"g{gid}", first_name="Parent", last_name=str(gid),
                    email=email, password="x", user_uuid=f"uuid-{gid}",
                    creation_date=str(datetime.now()), update_date=str(datetime.now()),
                )
            )
            setup.add(StudentGuardian(guardian_user_id=gid, student_id=960))
        await setup.commit()

    @asynccontextmanager
    async def _factory_cm():
        async with factory() as s:
            yield s

    def _fail_first(to, *args, **kwargs):
        if to == "broken@test.local":
            raise RuntimeError("bad address")
        return None

    with patch("src.core.events.database._async_session_factory", _factory_cm), \
         patch("src.services.email.utils.send_email", side_effect=_fail_first) as mock_send:
        # Must not raise.
        await _notify_guardians_of_absence_streak({"student_id": 960, "streak": 4})

    assert sorted(c.args[0] for c in mock_send.call_args_list) == ["broken@test.local", "ok@test.local"]


# ── Enrolment is the roster ──


async def _enrol(
    db: AsyncSession,
    *,
    section_id: int,
    student_id: int,
    status: str = "active",
    academic_year_id: int = 1,
) -> None:
    """Put a student on a section's register -- or take them off it."""
    db.add(
        StudentEnrollment(
            student_id=student_id,
            section_id=section_id,
            academic_year_id=academic_year_id,
            status=status,
        )
    )
    await db.commit()


async def _section_in_year(
    db: AsyncSession, *, section_id: int, academic_year_id: int
) -> None:
    """A section belonging to one academic year, as rollover creates them."""
    db.add(
        ClassSection(
            id=section_id,
            campus_id=1,
            academic_year_id=academic_year_id,
            grade_level="Grade 9",
            section_name=f"Section {section_id}",
        )
    )
    await db.commit()


async def _rows_in(db: AsyncSession, section_id: int) -> list:
    res = await db.execute(
        select(StudentAttendance).where(StudentAttendance.section_id == section_id)
    )
    return res.scalars().all()


@pytest.mark.asyncio
async def test_roll_call_refuses_a_student_who_is_not_on_the_register(db: AsyncSession):
    """THE DEFECT. Authorising the SECTION proved the teacher may take this
    register; it never proved the child was on it. Any id the client sent -- a
    pupil from another school, a member of staff -- was written and then
    counted, and the streak alert went to that family."""
    section_id, on_register, stranger = 9701, 97011, 97012
    await _enrol(db, section_id=section_id, student_id=on_register)

    with pytest.raises(HTTPException) as exc:
        await submit_batch_roll_call(
            payload=BatchRollCallRequest(
                section_id=section_id,
                date=date(2026, 10, 20),
                entries=[
                    RollCallStudentEntry(student_id=stranger, status=AttendanceStatus.PRESENT)
                ],
                marked_by=50,
            ),
            session=db,
            principal=_superadmin_principal(),
        )

    assert exc.value.status_code == 400
    assert str(stranger) in exc.value.detail, "the refusal must name the id to fix"
    assert await _rows_in(db, section_id) == [], "a refused register writes nothing"


@pytest.mark.asyncio
async def test_roll_call_refuses_a_student_who_has_left_the_section(db: AsyncSession):
    """A child who transferred out last month is not on today's register."""
    section_id, withdrawn = 9702, 97021
    await _enrol(db, section_id=section_id, student_id=withdrawn, status="withdrawn")

    with pytest.raises(HTTPException) as exc:
        await submit_batch_roll_call(
            payload=BatchRollCallRequest(
                section_id=section_id,
                date=date(2026, 10, 20),
                entries=[
                    RollCallStudentEntry(student_id=withdrawn, status=AttendanceStatus.PRESENT)
                ],
                marked_by=50,
            ),
            session=db,
            principal=_superadmin_principal(),
        )

    assert exc.value.status_code == 400
    assert await _rows_in(db, section_id) == []


@pytest.mark.asyncio
async def test_one_unenrolled_id_refuses_the_whole_register(db: AsyncSession):
    """Reject the batch rather than skip the id: a register is submitted as a
    unit and the teacher reads the response as 'the class is marked'. Silently
    dropping one child would leave them believing it was recorded."""
    section_id = 9703
    for sid in (97031, 97032):
        await _enrol(db, section_id=section_id, student_id=sid)

    with pytest.raises(HTTPException) as exc:
        await submit_batch_roll_call(
            payload=BatchRollCallRequest(
                section_id=section_id,
                date=date(2026, 10, 21),
                entries=[
                    RollCallStudentEntry(student_id=97031, status=AttendanceStatus.PRESENT),
                    RollCallStudentEntry(student_id=97032, status=AttendanceStatus.PRESENT),
                    RollCallStudentEntry(student_id=97033, status=AttendanceStatus.PRESENT),
                ],
                marked_by=50,
            ),
            session=db,
            principal=_superadmin_principal(),
        )

    assert exc.value.status_code == 400
    assert await _rows_in(db, section_id) == [], "not even the enrolled two were written"


@pytest.mark.asyncio
async def test_a_section_with_no_enrolment_rows_is_still_markable(db: AsyncSession):
    """The deliberate limit of the guard, pinned so it stays a decision rather
    than an accident: no roster on file is not evidence of non-enrolment, so a
    school that has not loaded enrolments can still take a register."""
    response = await submit_batch_roll_call(
        payload=BatchRollCallRequest(
            section_id=9704,
            date=date(2026, 10, 22),
            entries=[
                RollCallStudentEntry(student_id=97041, status=AttendanceStatus.PRESENT)
            ],
            marked_by=50,
        ),
        session=db,
        principal=_superadmin_principal(),
    )
    assert response.total_recorded == 1


# ── A streak is consecutive CALENDAR days ──


@pytest.mark.asyncio
async def test_a_stale_row_from_last_year_does_not_readmit_a_child_who_left(
    db: AsyncSession,
):
    """Enrolment is per ACADEMIC YEAR, so the roster has to be read in the
    section's own year. This child was active on this section last year and
    withdrew for this one; reading the section's rows without the year finds
    last year's 'active' and waves them onto today's register."""
    section_id, student_id = 9708, 97081
    await _section_in_year(db, section_id=section_id, academic_year_id=2026)
    await _enrol(
        db, section_id=section_id, student_id=student_id,
        status="active", academic_year_id=2025,
    )
    await _enrol(
        db, section_id=section_id, student_id=student_id,
        status="withdrawn", academic_year_id=2026,
    )

    with pytest.raises(HTTPException) as exc:
        await submit_batch_roll_call(
            payload=BatchRollCallRequest(
                section_id=section_id,
                date=date(2026, 10, 23),
                entries=[
                    RollCallStudentEntry(student_id=student_id, status=AttendanceStatus.PRESENT)
                ],
                marked_by=50,
            ),
            session=db,
            principal=_superadmin_principal(),
        )

    assert exc.value.status_code == 400
    assert await _rows_in(db, section_id) == []


@pytest.mark.asyncio
async def test_this_years_enrolment_is_what_counts(db: AsyncSession):
    """The mirror image, pinned so year-scoping cannot over-reach: a child
    withdrawn in an EARLIER year but active in the section's current year IS on
    the register. An old row must not veto a current one."""
    section_id, student_id = 9709, 97091
    await _section_in_year(db, section_id=section_id, academic_year_id=2026)
    await _enrol(
        db, section_id=section_id, student_id=student_id,
        status="withdrawn", academic_year_id=2025,
    )
    await _enrol(
        db, section_id=section_id, student_id=student_id,
        status="active", academic_year_id=2026,
    )

    response = await submit_batch_roll_call(
        payload=BatchRollCallRequest(
            section_id=section_id,
            date=date(2026, 10, 24),
            entries=[
                RollCallStudentEntry(student_id=student_id, status=AttendanceStatus.PRESENT)
            ],
            marked_by=50,
        ),
        session=db,
        principal=_superadmin_principal(),
    )
    assert response.total_recorded == 1


@pytest.mark.asyncio
async def test_a_section_rolled_forward_before_its_enrolments_is_still_markable(
    db: AsyncSession,
):
    """The fallback, pinned: the section says 2026 but its enrolments are still
    filed under 2025 (rollover half-applied). Filtering strictly would yield an
    EMPTY roster, and an empty roster is authoritative -- every register for
    that section would be refused. Fall back to the rows we do have."""
    section_id, student_id = 9710, 97101
    await _section_in_year(db, section_id=section_id, academic_year_id=2026)
    await _enrol(
        db, section_id=section_id, student_id=student_id,
        status="active", academic_year_id=2025,
    )

    response = await submit_batch_roll_call(
        payload=BatchRollCallRequest(
            section_id=section_id,
            date=date(2026, 10, 25),
            entries=[
                RollCallStudentEntry(student_id=student_id, status=AttendanceStatus.PRESENT)
            ],
            marked_by=50,
        ),
        session=db,
        principal=_superadmin_principal(),
    )
    assert response.total_recorded == 1


@pytest.mark.asyncio
async def test_isolated_absences_weeks_apart_do_not_form_a_streak(db: AsyncSession):
    """THE DEFECT. Three separate absences with no register taken in between
    (a cover teacher, a school trip) used to read as '3 days running'."""
    student_id, section_id = 97051, 9705
    for day in (date(2026, 9, 4), date(2026, 9, 18), date(2026, 9, 29)):
        db.add(
            StudentAttendance(
                student_id=student_id,
                section_id=section_id,
                date=day,
                status=AttendanceStatus.ABSENT,
                marked_by=1,
            )
        )
    await db.commit()

    streak = await get_consecutive_absence_streak(db, student_id, section_id)
    assert streak == 1, f"three isolated absences counted as a run of {streak}"
    assert streak < ABSENCE_STREAK_THRESHOLD


@pytest.mark.asyncio
async def test_three_consecutive_calendar_days_still_reach_the_threshold(db: AsyncSession):
    """The alert must still fire for a genuine three-day absence."""
    student_id, section_id = 97061, 9706
    for offset in range(ABSENCE_STREAK_THRESHOLD):
        db.add(
            StudentAttendance(
                student_id=student_id,
                section_id=section_id,
                date=date(2026, 9, 1) + timedelta(days=offset),
                status=AttendanceStatus.ABSENT,
                marked_by=1,
            )
        )
    await db.commit()

    assert (
        await get_consecutive_absence_streak(db, student_id, section_id)
        == ABSENCE_STREAK_THRESHOLD
    )


@pytest.mark.asyncio
async def test_isolated_absences_do_not_escalate_to_the_family(db: AsyncSession):
    """The harm, end to end: a third ISOLATED absence must not open a pastoral
    concern or send 'absent 3 days in a row' to the child's family."""
    from datetime import datetime as _dt
    from unittest.mock import AsyncMock, patch

    from src.db.sms_identity import StudentGuardian
    from src.db.users import User

    student_id, section_id = 97071, 9707
    for day in (date(2026, 9, 4), date(2026, 9, 18)):
        db.add(
            StudentAttendance(
                student_id=student_id,
                section_id=section_id,
                date=day,
                status=AttendanceStatus.ABSENT,
                marked_by=1,
            )
        )

    db.add(
        User(
            id=97072, username="g9707", first_name="Parent", last_name="Seven",
            email="g9707@test.local", password="x", user_uuid="uuid-97072",
            creation_date=str(_dt.now()), update_date=str(_dt.now()),
        )
    )
    await db.flush()
    db.add(StudentGuardian(guardian_user_id=97072, student_id=student_id))
    await db.commit()

    with patch(
        "src.routers.sms_attendance.raise_school_event", new=AsyncMock()
    ) as mock_raise:
        await submit_batch_roll_call(
            payload=BatchRollCallRequest(
                section_id=section_id,
                date=date(2026, 9, 29),
                entries=[
                    RollCallStudentEntry(student_id=student_id, status=AttendanceStatus.ABSENT)
                ],
                marked_by=50,
            ),
            session=db,
            principal=_superadmin_principal(),
        )

    # The family is still told about TODAY's absence -- they are just not told
    # the child has been away for three days running.
    mock_raise.assert_awaited_once()
    assert mock_raise.await_args.kwargs["event_key"] == "attendance.absence_recorded"

    concerns = (
        await db.execute(
            select(PastoralConcern).where(PastoralConcern.student_id == student_id)
        )
    ).scalars().all()
    assert concerns == [], "an isolated absence must not open a pastoral concern"
