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
from src.routers.sms_attendance import (
    get_monthly_student_attendance,
    list_leave_requests,
    submit_batch_roll_call,
    submit_leave_request,
    update_leave_request_status,
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

    response = await submit_batch_roll_call(payload=payload, session=db)
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
    update_res = await submit_batch_roll_call(payload=update_payload, session=db)
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
    created = await submit_leave_request(payload=payload, session=db)
    assert created.id is not None
    assert created.student_id == 301
    assert created.status == LeaveRequestStatus.PENDING

    # List requests
    requests = await list_leave_requests(student_id=301, session=db)
    assert len(requests) == 1
    assert requests[0].id == created.id

    # Update status to APPROVED
    updated = await update_leave_request_status(
        request_id=created.id,
        payload=LeaveRequestUpdateStatus(status=LeaveRequestStatus.APPROVED, approved_by=99),
        session=db,
    )
    assert updated.status == LeaveRequestStatus.APPROVED
    assert updated.approved_by == 99
