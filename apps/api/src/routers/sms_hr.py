from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.events.database import get_db_session
from src.db.sms_hr import (
    ContractType,
    LeaveStatus,
    LeaveType,
    StaffLeave,
    StaffProfile,
)
from src.schemas.sms_hr import (
    StaffLeaveActionRequest,
    StaffLeaveCreate,
    StaffLeaveRead,
    StaffProfileCreate,
    StaffProfileRead,
    StaffProfileUpdate,
)

router = APIRouter()


# ── Staff Directory ──

@router.post(
    "/staff",
    response_model=StaffProfileRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register Staff Profile",
)
async def create_staff_profile(
    payload: StaffProfileCreate,
    session: AsyncSession = Depends(get_db_session),
) -> StaffProfileRead:
    # Check employee code uniqueness
    stmt = select(StaffProfile).where(StaffProfile.employee_code == payload.employee_code)
    existing = (await session.execute(stmt)).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Staff member with employee_code '{payload.employee_code}' already exists.",
        )

    profile = StaffProfile(
        employee_code=payload.employee_code,
        full_name=payload.full_name,
        designation=payload.designation,
        department=payload.department,
        joining_date=payload.joining_date,
        contract_type=payload.contract_type,
        basic_salary=payload.basic_salary,
        user_id=payload.user_id,
        campus_id=payload.campus_id,
        email=payload.email,
        phone=payload.phone,
        is_active=payload.is_active,
    )
    session.add(profile)
    await session.commit()
    await session.refresh(profile)
    return StaffProfileRead.model_validate(profile)


@router.get(
    "/staff",
    response_model=List[StaffProfileRead],
    summary="List Staff Directory",
)
async def list_staff_profiles(
    campus_id: Optional[int] = Query(None, description="Filter by Campus ID"),
    department: Optional[str] = Query(None, description="Filter by Department"),
    contract_type: Optional[ContractType] = Query(None, description="Filter by Contract Type"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    session: AsyncSession = Depends(get_db_session),
) -> List[StaffProfileRead]:
    query = select(StaffProfile)
    if type(campus_id) is int:
        query = query.where(StaffProfile.campus_id == campus_id)
    if type(department) is str and not hasattr(department, "default"):
        query = query.where(StaffProfile.department == department)
    if (isinstance(contract_type, ContractType) or type(contract_type) is str) and not hasattr(contract_type, "default"):
        query = query.where(StaffProfile.contract_type == contract_type)
    if type(is_active) is bool:
        query = query.where(StaffProfile.is_active == is_active)

    query = query.order_by(StaffProfile.full_name)
    result = await session.execute(query)
    staff = result.scalars().all()
    return [StaffProfileRead.model_validate(s) for s in staff]


@router.get(
    "/staff/{staff_id}",
    response_model=StaffProfileRead,
    summary="Get Staff Profile by ID",
)
async def get_staff_profile(
    staff_id: int,
    session: AsyncSession = Depends(get_db_session),
) -> StaffProfileRead:
    stmt = select(StaffProfile).where(StaffProfile.id == staff_id)
    profile = (await session.execute(stmt)).scalar_one_or_none()
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Staff member with ID {staff_id} not found.",
        )
    return StaffProfileRead.model_validate(profile)


@router.patch(
    "/staff/{staff_id}",
    response_model=StaffProfileRead,
    summary="Update Staff Profile",
)
async def update_staff_profile(
    staff_id: int,
    payload: StaffProfileUpdate,
    session: AsyncSession = Depends(get_db_session),
) -> StaffProfileRead:
    stmt = select(StaffProfile).where(StaffProfile.id == staff_id)
    profile = (await session.execute(stmt)).scalar_one_or_none()
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Staff member with ID {staff_id} not found.",
        )

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)

    session.add(profile)
    await session.commit()
    await session.refresh(profile)
    return StaffProfileRead.model_validate(profile)


# ── Staff Leaves ──

@router.post(
    "/leaves",
    response_model=StaffLeaveRead,
    status_code=status.HTTP_201_CREATED,
    summary="Submit Staff Leave Application",
)
async def apply_staff_leave(
    payload: StaffLeaveCreate,
    session: AsyncSession = Depends(get_db_session),
) -> StaffLeaveRead:
    # Verify staff exists
    staff_stmt = select(StaffProfile).where(StaffProfile.id == payload.staff_id)
    staff = (await session.execute(staff_stmt)).scalar_one_or_none()
    if not staff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Staff member with ID {payload.staff_id} not found.",
        )

    if payload.end_date < payload.start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Leave end_date cannot be earlier than start_date.",
        )

    leave = StaffLeave(
        staff_id=payload.staff_id,
        leave_type=payload.leave_type,
        start_date=payload.start_date,
        end_date=payload.end_date,
        reason=payload.reason,
        status=LeaveStatus.PENDING,
    )
    session.add(leave)
    await session.commit()
    await session.refresh(leave)
    return StaffLeaveRead.model_validate(leave)


@router.get(
    "/leaves",
    response_model=List[StaffLeaveRead],
    summary="List Staff Leaves",
)
async def list_staff_leaves(
    staff_id: Optional[int] = Query(None, description="Filter by Staff ID"),
    leave_type: Optional[LeaveType] = Query(None, description="Filter by Leave Type"),
    status_filter: Optional[LeaveStatus] = Query(None, alias="status", description="Filter by Leave Status"),
    session: AsyncSession = Depends(get_db_session),
) -> List[StaffLeaveRead]:
    query = select(StaffLeave)
    if isinstance(staff_id, int):
        query = query.where(StaffLeave.staff_id == staff_id)
    if (isinstance(leave_type, LeaveType) or isinstance(leave_type, str)) and not hasattr(leave_type, "default"):
        query = query.where(StaffLeave.leave_type == leave_type)
    if (isinstance(status_filter, LeaveStatus) or isinstance(status_filter, str)) and not hasattr(status_filter, "default"):
        query = query.where(StaffLeave.status == status_filter)

    query = query.order_by(StaffLeave.start_date.desc(), StaffLeave.id.desc())
    result = await session.execute(query)
    leaves = result.scalars().all()
    return [StaffLeaveRead.model_validate(l) for l in leaves]


@router.patch(
    "/leaves/{leave_id}/status",
    response_model=StaffLeaveRead,
    summary="Approve or Reject Staff Leave",
)
async def update_leave_status(
    leave_id: int,
    payload: StaffLeaveActionRequest,
    session: AsyncSession = Depends(get_db_session),
) -> StaffLeaveRead:
    stmt = select(StaffLeave).where(StaffLeave.id == leave_id)
    leave = (await session.execute(stmt)).scalar_one_or_none()
    if not leave:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Staff leave with ID {leave_id} not found.",
        )

    leave.status = payload.status
    if payload.approved_by is not None:
        leave.approved_by = payload.approved_by

    session.add(leave)
    await session.commit()
    await session.refresh(leave)
    return StaffLeaveRead.model_validate(leave)
