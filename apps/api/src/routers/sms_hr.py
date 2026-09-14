import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.events.database import get_db_session
from src.core.keycloak_auth import (
    KeycloakUserPrincipal,
    get_current_user_principal,
    require_roles,
)
from src.db.sms_hr import (
    ContractType,
    LeaveStatus,
    LeaveType,
    StaffLeave,
    StaffProfile,
)
from src.db.sms_hr_extended import (
    AppraisalStatus,
    StaffAppraisal,
    StaffOffboarding,
)
from src.schemas.sms_hr import (
    StaffLeaveActionRequest,
    StaffLeaveCreate,
    StaffLeaveRead,
    StaffProfileCreate,
    StaffProfileRead,
    StaffProfileUpdate,
)
from src.schemas.sms_hr_extended import (
    OffboardingOutcome,
    StaffAppraisalCreate,
    StaffAppraisalRead,
    StaffAppraisalUpdate,
    StaffOffboardingRead,
    StaffOffboardingRequest,
)
from src.services.sms.hr_offboarding import offboard_staff_member
from src.security.features_utils.dependencies import require_sms_hr_payroll_feature
from src.security.school_ownership import (
    assert_campus_allowed,
    resolve_scoped_campus_id,
)

# Personnel files carry `basic_salary`, so creating or editing one is
# compensation data, not directory data. TEACHER is excluded alongside
# STUDENT/PARENT: a colleague must not be able to read or rewrite another
# colleague's salary. STAFF is excluded too -- HR administration is a
# school-admin function, narrower than the back-office bursar role used for
# fees, because the subject of the record is a co-worker.
_HR_ADMIN = ["SUPER_ADMIN", "SCHOOL_ADMIN"]

# Anyone with a staff-side role may REQUEST their own leave; the handler then
# binds the request to the caller. Students and parents have no staff record.
_MAY_REQUEST_LEAVE = ["SUPER_ADMIN", "SCHOOL_ADMIN", "TEACHER", "STAFF", "PSYCHOLOGIST"]


def _is_hr_admin(principal: KeycloakUserPrincipal) -> bool:
    return bool(principal.is_superadmin or principal.has_any_role(_HR_ADMIN))

router = APIRouter(dependencies=[Depends(require_sms_hr_payroll_feature)])


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
    principal: KeycloakUserPrincipal = Depends(require_roles(_HR_ADMIN)),
) -> StaffProfileRead:
    # Check employee code uniqueness
    stmt = select(StaffProfile).where(StaffProfile.employee_code == payload.employee_code)
    existing = (await session.execute(stmt)).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Staff member with employee_code '{payload.employee_code}' already exists.",
        )

    # Fail loudly: silently relocating a new staff record to a different campus
    # than the one requested would be misleading, not helpful.
    assert_campus_allowed(principal, payload.campus_id)
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
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> List[StaffProfileRead]:
    query = select(StaffProfile)
    # Narrow rather than reject: a campus-bound caller listing staff almost
    # always means "my staff", and an omitted filter previously returned every
    # campus in the org.
    campus_id = resolve_scoped_campus_id(principal, campus_id if type(campus_id) is int else None)
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
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
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
    principal: KeycloakUserPrincipal = Depends(require_roles(_HR_ADMIN)),
) -> StaffProfileRead:
    stmt = select(StaffProfile).where(StaffProfile.id == staff_id)
    profile = (await session.execute(stmt)).scalar_one_or_none()
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Staff member with ID {staff_id} not found.",
        )

    # Two separate campus checks, because this endpoint can breach isolation
    # in both directions: the record you are editing, and where you move it to.
    # The blanket setattr below happily writes campus_id, so without the second
    # check a campus-bound admin could transfer any staff member to their own
    # campus -- or push one of their own out of sight.
    assert_campus_allowed(principal, profile.campus_id)
    assert_campus_allowed(principal, payload.model_dump(exclude_unset=True).get("campus_id"))

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
    principal: KeycloakUserPrincipal = Depends(require_roles(_MAY_REQUEST_LEAVE)),
) -> StaffLeaveRead:
    # Verify staff exists
    staff_stmt = select(StaffProfile).where(StaffProfile.id == payload.staff_id)
    staff = (await session.execute(staff_stmt)).scalar_one_or_none()
    if not staff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Staff member with ID {payload.staff_id} not found.",
        )

    # `staff_id` is client-supplied, so without this a teacher could file leave
    # in a colleague's name -- and, since approval is a separate endpoint, get
    # someone else marked absent. You may only apply for yourself; HR admins
    # may file on another person's behalf.
    if not _is_hr_admin(principal):
        caller_user_id = (principal.raw_claims or {}).get("lh_user_id")
        if caller_user_id is None or staff.user_id != caller_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You may only apply for your own leave.",
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
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
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
    principal: KeycloakUserPrincipal = Depends(require_roles(_HR_ADMIN)),
) -> StaffLeaveRead:
    stmt = select(StaffLeave).where(StaffLeave.id == leave_id)
    leave = (await session.execute(stmt)).scalar_one_or_none()
    if not leave:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Staff leave with ID {leave_id} not found.",
        )

    leave.status = payload.status
    # The approver is whoever is authenticated. Taking `approved_by` from the
    # request body let a caller attribute their own approval to someone else,
    # which is exactly the audit trail this column exists to provide.
    approver_id = (principal.raw_claims or {}).get("lh_user_id")
    if approver_id is not None:
        leave.approved_by = approver_id

    session.add(leave)
    await session.commit()
    await session.refresh(leave)
    return StaffLeaveRead.model_validate(leave)


# ── Offboarding ──
#
# `StaffProfile.is_active = False` was previously the whole of "this person has
# left". It revoked nothing: their SMSUserRole grants stayed active so they
# could still sign in and act, they remained `class_section.class_teacher_id`,
# and their timetable slots still named them. Deactivating the row looked like
# offboarding and was not.


@router.post(
    "/staff/{staff_id}/offboard",
    response_model=OffboardingOutcome,
    status_code=status.HTTP_201_CREATED,
    summary="Offboard a staff member",
    description=(
        "Revokes school role grants, reassigns or releases class sections, and "
        "reassigns timetable slots, in ONE transaction. Returns what the "
        "cascade actually did, plus any timetable slots still outstanding -- "
        "those are WORK REMAINING, not a result, so they are reported "
        "separately rather than buried in a success message."
    ),
    responses={403: {"description": "Only school leadership may offboard staff"}},
)
async def offboard_staff(
    staff_id: int,
    payload: StaffOffboardingRequest,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_HR_ADMIN)),
) -> OffboardingOutcome:
    staff = (
        await session.execute(select(StaffProfile).where(StaffProfile.id == staff_id))
    ).scalar_one_or_none()
    if staff is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Staff member with ID {staff_id} not found.",
        )

    # Fail loudly on a cross-campus offboarding: silently acting on another
    # campus's employee is not something to resolve helpfully.
    assert_campus_allowed(principal, staff.campus_id)

    if not staff.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This staff member is already inactive. Re-running offboarding "
                "would record a second departure for the same person."
            ),
        )

    record, outstanding, warnings = await offboard_staff_member(
        session=session,
        staff=staff,
        payload=payload,
        initiated_by_user_id=(principal.raw_claims or {}).get("lh_user_id"),
    )
    return OffboardingOutcome(
        offboarding=StaffOffboardingRead.model_validate(record),
        outstanding_timetable_slot_ids=outstanding,
        warnings=warnings,
    )


@router.get(
    "/offboardings",
    response_model=List[StaffOffboardingRead],
    summary="List offboarding records",
)
async def list_offboardings(
    campus_id: Optional[int] = Query(None, description="Filter by Campus ID"),
    staff_id: Optional[int] = Query(None, description="Filter by Staff ID"),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_HR_ADMIN)),
) -> List[StaffOffboardingRead]:
    query = select(StaffOffboarding)
    # Narrow rather than reject -- an unscoped read by a campus-bound admin
    # means "my campus", and previously returned every campus in the org.
    campus_id = resolve_scoped_campus_id(principal, campus_id if type(campus_id) is int else None)
    if type(campus_id) is int:
        query = query.where(StaffOffboarding.campus_id == campus_id)
    if type(staff_id) is int:
        query = query.where(StaffOffboarding.staff_id == staff_id)
    rows = (await session.execute(query.order_by(StaffOffboarding.id.desc()))).scalars().all()
    return [StaffOffboardingRead.model_validate(r) for r in rows]


# ── Appraisals ──


@router.post(
    "/appraisals",
    response_model=StaffAppraisalRead,
    status_code=status.HTTP_201_CREATED,
    summary="Record a staff appraisal",
    description=(
        "The reviewer is taken from the authenticated caller, never the "
        "payload: an appraisal that could name someone else as its author "
        "would be worthless as evidence of a review having happened."
    ),
)
async def create_appraisal(
    payload: StaffAppraisalCreate,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_HR_ADMIN)),
) -> StaffAppraisalRead:
    staff = (
        await session.execute(select(StaffProfile).where(StaffProfile.id == payload.staff_id))
    ).scalar_one_or_none()
    if staff is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Staff member with ID {payload.staff_id} not found.",
        )
    assert_campus_allowed(principal, staff.campus_id)

    if payload.period_end < payload.period_start:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="period_end cannot fall before period_start.",
        )

    reviewer_user_id = (principal.raw_claims or {}).get("lh_user_id")
    if reviewer_user_id is None:
        # Fail closed. An appraisal with no attributable reviewer cannot serve
        # the purpose it exists for.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not resolve the reviewing user; appraisal not recorded.",
        )

    appraisal = StaffAppraisal(
        staff_id=payload.staff_id,
        campus_id=staff.campus_id,
        period_start=payload.period_start,
        period_end=payload.period_end,
        outcome=payload.outcome,
        strengths=payload.strengths,
        development_areas=payload.development_areas,
        objectives=payload.objectives,
        reviewer_user_id=reviewer_user_id,
    )
    session.add(appraisal)
    await session.commit()
    await session.refresh(appraisal)
    return StaffAppraisalRead.model_validate(appraisal)


@router.get(
    "/appraisals",
    response_model=List[StaffAppraisalRead],
    summary="List staff appraisals",
    description=(
        "HR administrators see the appraisals for their campus. A staff member "
        "sees their OWN appraisals, and only once SHARED -- a draft is the "
        "reviewer's working document, not a disclosure."
    ),
)
async def list_appraisals(
    staff_id: Optional[int] = Query(None, description="Filter by Staff ID"),
    campus_id: Optional[int] = Query(None, description="Filter by Campus ID"),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> List[StaffAppraisalRead]:
    query = select(StaffAppraisal)

    if _is_hr_admin(principal):
        campus_id = resolve_scoped_campus_id(
            principal, campus_id if type(campus_id) is int else None
        )
        if type(campus_id) is int:
            query = query.where(StaffAppraisal.campus_id == campus_id)
        if type(staff_id) is int:
            query = query.where(StaffAppraisal.staff_id == staff_id)
    else:
        caller_user_id = (principal.raw_claims or {}).get("lh_user_id")
        own = None
        if caller_user_id is not None:
            own = (
                await session.execute(
                    select(StaffProfile).where(StaffProfile.user_id == caller_user_id)
                )
            ).scalars().first()
        if own is None or own.id is None:
            # Empty, not 403: whether this person has appraisals is not
            # something to confirm to a caller who may not see them.
            return []
        query = query.where(
            StaffAppraisal.staff_id == own.id,
            StaffAppraisal.status != AppraisalStatus.DRAFT,
        )

    rows = (await session.execute(query.order_by(StaffAppraisal.id.desc()))).scalars().all()
    return [StaffAppraisalRead.model_validate(r) for r in rows]


@router.patch(
    "/appraisals/{appraisal_id}",
    response_model=StaffAppraisalRead,
    summary="Update an appraisal",
)
async def update_appraisal(
    appraisal_id: int,
    payload: StaffAppraisalUpdate,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_HR_ADMIN)),
) -> StaffAppraisalRead:
    appraisal = (
        await session.execute(select(StaffAppraisal).where(StaffAppraisal.id == appraisal_id))
    ).scalar_one_or_none()
    if appraisal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Appraisal with ID {appraisal_id} not found.",
        )
    assert_campus_allowed(principal, appraisal.campus_id)

    if appraisal.status != AppraisalStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This appraisal has already been shared with the staff member "
                "and cannot be edited. Editing a document someone has already "
                "read would rewrite what they were told."
            ),
        )

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(appraisal, field, value)
    session.add(appraisal)
    await session.commit()
    await session.refresh(appraisal)
    return StaffAppraisalRead.model_validate(appraisal)


@router.post(
    "/appraisals/{appraisal_id}/share",
    response_model=StaffAppraisalRead,
    summary="Share an appraisal with the staff member",
    description=(
        "Moves a DRAFT to SHARED and stamps shared_at. Idempotent: sharing an "
        "already-shared appraisal returns it unchanged rather than re-stamping "
        "the date the person was actually told."
    ),
)
async def share_appraisal(
    appraisal_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_HR_ADMIN)),
) -> StaffAppraisalRead:
    appraisal = (
        await session.execute(select(StaffAppraisal).where(StaffAppraisal.id == appraisal_id))
    ).scalar_one_or_none()
    if appraisal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Appraisal with ID {appraisal_id} not found.",
        )
    assert_campus_allowed(principal, appraisal.campus_id)

    if appraisal.status == AppraisalStatus.DRAFT:
        appraisal.status = AppraisalStatus.SHARED
        appraisal.shared_at = datetime.datetime.now(datetime.timezone.utc)
        session.add(appraisal)
        await session.commit()
        await session.refresh(appraisal)
    return StaffAppraisalRead.model_validate(appraisal)
