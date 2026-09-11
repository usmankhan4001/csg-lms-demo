import calendar
from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, extract, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.events.database import get_db_session
from src.db.sms_attendance import (
    AttendanceLeaveRequest,
    AttendanceStatus,
    LeaveRequestStatus,
    StudentAttendance,
)
from src.schemas.sms_attendance import (
    BatchRollCallRequest,
    BatchRollCallResponse,
    LeaveRequestCreate,
    LeaveRequestRead,
    LeaveRequestUpdateStatus,
    MonthlyAttendanceStats,
    MonthlyStudentAttendanceSheet,
    StudentAttendanceRead,
)

router = APIRouter()


# ── 1-Click Batch Roll-Call ──

@router.post(
    "/roll-call",
    response_model=BatchRollCallResponse,
    status_code=status.HTTP_200_OK,
    summary="1-Click Batch Roll-Call Attendance",
    description="Record or update attendance for all students in a section on a given date.",
)
async def submit_batch_roll_call(
    payload: BatchRollCallRequest,
    session: AsyncSession = Depends(get_db_session),
) -> BatchRollCallResponse:
    """
    Submits batch roll-call attendance. Performs upsert on (student_id, section_id, date).
    """
    if not payload.entries:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Roll-call entries list cannot be empty.",
        )

    student_ids = [entry.student_id for entry in payload.entries]

    # Fetch existing records for this section and date
    stmt = select(StudentAttendance).where(
        and_(
            StudentAttendance.section_id == payload.section_id,
            StudentAttendance.date == payload.date,
            StudentAttendance.student_id.in_(student_ids),
        )
    )
    result = await session.execute(stmt)
    existing_map = {att.student_id: att for att in result.scalars().all()}

    saved_records: List[StudentAttendance] = []

    for entry in payload.entries:
        if entry.student_id in existing_map:
            # Update existing attendance row
            att = existing_map[entry.student_id]
            att.status = entry.status
            att.remarks = entry.remarks
            if payload.marked_by is not None:
                att.marked_by = payload.marked_by
            session.add(att)
            saved_records.append(att)
        else:
            # Insert new attendance row
            new_att = StudentAttendance(
                student_id=entry.student_id,
                section_id=payload.section_id,
                date=payload.date,
                status=entry.status,
                marked_by=payload.marked_by,
                remarks=entry.remarks,
            )
            session.add(new_att)
            saved_records.append(new_att)

    await session.commit()
    for rec in saved_records:
        await session.refresh(rec)

    return BatchRollCallResponse(
        success=True,
        section_id=payload.section_id,
        date=payload.date,
        total_submitted=len(payload.entries),
        total_recorded=len(saved_records),
        records=[StudentAttendanceRead.model_validate(rec) for rec in saved_records],
    )


# ── Monthly Student Attendance Sheet ──

@router.get(
    "/student/{student_id}/monthly",
    response_model=MonthlyStudentAttendanceSheet,
    summary="Monthly Student Attendance Sheet",
    description="Calculate aggregated statistics and list daily attendance logs for a student in a specific month.",
)
async def get_monthly_student_attendance(
    student_id: int,
    year: int = Query(..., ge=2000, le=2100, description="Calendar Year (e.g. 2026)"),
    month: int = Query(..., ge=1, le=12, description="Month (1-12)"),
    section_id: Optional[int] = Query(None, description="Optional Section ID filter"),
    session: AsyncSession = Depends(get_db_session),
) -> MonthlyStudentAttendanceSheet:
    """
    Generates institutional monthly attendance breakdown & weighted attendance percentage.
    """
    conditions = [
        StudentAttendance.student_id == student_id,
        extract("year", StudentAttendance.date) == year,
        extract("month", StudentAttendance.date) == month,
    ]
    if isinstance(section_id, int):
        conditions.append(StudentAttendance.section_id == section_id)

    stmt = (
        select(StudentAttendance)
        .where(and_(*conditions))
        .order_by(StudentAttendance.date.asc())
    )
    result = await session.execute(stmt)
    records = result.scalars().all()

    total_days = len(records)
    present_days = sum(1 for r in records if r.status == AttendanceStatus.PRESENT)
    absent_days = sum(1 for r in records if r.status == AttendanceStatus.ABSENT)
    late_days = sum(1 for r in records if r.status == AttendanceStatus.LATE)
    excused_days = sum(1 for r in records if r.status == AttendanceStatus.EXCUSED)

    # Standard SMS Formula: (Present + 0.5 * Late + Excused) / Total * 100
    if total_days > 0:
        effective_present = present_days + (0.5 * late_days) + excused_days
        percentage = round((effective_present / total_days) * 100.0, 2)
    else:
        percentage = 0.0

    stats = MonthlyAttendanceStats(
        total_days=total_days,
        present_days=present_days,
        absent_days=absent_days,
        late_days=late_days,
        excused_days=excused_days,
        attendance_percentage=percentage,
    )

    return MonthlyStudentAttendanceSheet(
        student_id=student_id,
        section_id=section_id,
        year=year,
        month=month,
        stats=stats,
        daily_records=[StudentAttendanceRead.model_validate(r) for r in records],
    )


# ── Leave Requests ──

@router.post(
    "/leave-requests",
    response_model=LeaveRequestRead,
    status_code=status.HTTP_201_CREATED,
    summary="Submit Student Leave Request",
    description="Submit a new student leave request.",
)
async def submit_leave_request(
    payload: LeaveRequestCreate,
    session: AsyncSession = Depends(get_db_session),
) -> LeaveRequestRead:
    if payload.end_date < payload.start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="end_date cannot be earlier than start_date.",
        )

    leave_request = AttendanceLeaveRequest(
        student_id=payload.student_id,
        start_date=payload.start_date,
        end_date=payload.end_date,
        reason=payload.reason,
        status=LeaveRequestStatus.PENDING,
    )
    session.add(leave_request)
    await session.commit()
    await session.refresh(leave_request)
    return LeaveRequestRead.model_validate(leave_request)


@router.get(
    "/leave-requests",
    response_model=List[LeaveRequestRead],
    summary="List Student Leave Requests",
    description="Retrieve leave requests filtered by student or status.",
)
async def list_leave_requests(
    student_id: Optional[int] = Query(None, description="Filter by Student ID"),
    status_filter: Optional[LeaveRequestStatus] = Query(None, alias="status", description="Filter by status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db_session),
) -> List[LeaveRequestRead]:
    conditions = []
    if isinstance(student_id, int):
        conditions.append(AttendanceLeaveRequest.student_id == student_id)
    if isinstance(status_filter, (LeaveRequestStatus, str)):
        conditions.append(AttendanceLeaveRequest.status == status_filter)

    limit_val = limit if isinstance(limit, int) else 50
    offset_val = offset if isinstance(offset, int) else 0

    stmt = (
        select(AttendanceLeaveRequest)
        .where(and_(*conditions))
        .order_by(AttendanceLeaveRequest.created_at.desc())
        .offset(offset_val)
        .limit(limit_val)
    )
    result = await session.execute(stmt)
    records = result.scalars().all()
    return [LeaveRequestRead.model_validate(r) for r in records]


@router.patch(
    "/leave-requests/{request_id}/status",
    response_model=LeaveRequestRead,
    summary="Approve or Reject Leave Request",
    description="Update the lifecycle status of a student leave request.",
)
async def update_leave_request_status(
    request_id: int,
    payload: LeaveRequestUpdateStatus,
    session: AsyncSession = Depends(get_db_session),
) -> LeaveRequestRead:
    stmt = select(AttendanceLeaveRequest).where(AttendanceLeaveRequest.id == request_id)
    result = await session.execute(stmt)
    leave_request = result.scalar_one_or_none()
    if not leave_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Leave request with ID {request_id} not found.",
        )

    leave_request.status = payload.status
    if payload.approved_by is not None:
        leave_request.approved_by = payload.approved_by

    session.add(leave_request)
    await session.commit()
    await session.refresh(leave_request)
    return LeaveRequestRead.model_validate(leave_request)
