import pytest
from datetime import date
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_attendance import (
    AttendanceLeaveRequest,
    AttendanceStatus,
    LeaveRequestStatus,
    StudentAttendance,
)
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
    """3 consecutive absences must actually fire the event. Before this was
    wired, the detection existed but was never called from roll-call."""
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

    # The threshold-hitting absence arrives through the real roll-call endpoint.
    with patch("src.core.event_bus.bus.emit", new=AsyncMock()) as mock_emit:
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

    mock_emit.assert_awaited_once()
    event_name, payload = mock_emit.await_args.args
    assert event_name == "student.absence_streak"
    assert payload["student_id"] == student_id
    assert payload["streak"] == ABSENCE_STREAK_THRESHOLD


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
