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
from src.db.sms_hr import StaffProfile
from src.db.sms_hr_extended import PayrollAction, PayrollActionType
from src.db.sms_payroll import SalaryPaymentStatus, SalarySlip, SalaryStructure
from src.schemas.sms_hr_extended import (
    PayrollActionRead,
    PayrollApprovalRequest,
    PayrollApprovalOutcome,
    PayrollApprovalResponse,
)
from src.schemas.sms_payroll import (
    BatchSalarySlipGenerateRequest,
    ProcessSalaryPaymentRequest,
    SalarySlipRead,
    SalaryStructureCreate,
    SalaryStructureRead,
)
from src.security.ems_rbac import require_permission
from src.security.features_utils.dependencies import require_sms_hr_payroll_feature
from src.security.school_ownership import (
    assert_campus_allowed,
    resolve_scoped_campus_id,
)
from src.services.sms.payroll import (
    generate_batch_salary_slips,
    process_salary_slip_payment,
)
from src.services.sms.payroll_approval import (
    approve_slips,
    assert_payable,
    record_prepared_actions,
)

# Payroll is staff COMPENSATION, so it is gated harder than the rest of the
# back office. Deliberately narrower than sms_fees.py's _BURSAR, which admits
# STAFF: a generic back-office employee (librarian, admissions clerk) holding
# payroll write access could raise their own salary structure and then mark
# their own slip paid. That self-dealing path is the reason STAFF is excluded
# here but allowed for student fees. TEACHER/STUDENT/PARENT are excluded for
# the obvious reason.
#
# require_roles() grants SUPER_ADMIN an automatic bypass; it is listed anyway
# so the intended audience is readable at the call site.
_PAYROLL_ADMIN = ["SUPER_ADMIN", "SCHOOL_ADMIN"]

# --- Dynamic RBAC (src/security/ems_rbac.py) -------------------------------
#
# Fine-grained second gate behind the coarse `require_roles(_PAYROLL_ADMIN)`.
# Payroll is the `hr` domain of `ResourceDomain` (src/db/ems_roles.py);
# disbursement and approval use that model's `approve` action because paying
# out is the accountable act, not an edit.
PAYROLL = "hr.payroll"


async def _assert_may_read_salary(
    principal: KeycloakUserPrincipal,
    staff_id: Optional[int],
    session: AsyncSession,
) -> None:
    """Salary data is HR-admin, or the staff member's own.

    These reads were open to ANY authenticated user and take an arbitrary
    `staff_id`, so a signed-in student could walk the id range and read every
    staff member's salary, allowances and deductions. Pay is among the most
    sensitive data a school holds about its employees.

    A bare listing (no staff_id) is admin-only: there is no "everyone's slips,
    filtered to me" reading of that request.
    """
    # Callers that invoke this handler directly (tests, internal reuse) pass
    # FastAPI's unresolved `Query(...)` default rather than None, which is why
    # the rest of this module guards with `type(x) is int`. Normalise here so
    # a non-int never reaches a WHERE clause as a bind parameter.
    if type(staff_id) is not int:
        staff_id = None

    if principal.is_superadmin:
        return

    is_admin = principal.has_any_role(_PAYROLL_ADMIN)
    if is_admin and staff_id is None:
        # Admin listing everyone: the caller's campus narrows the query itself
        # (see list_salary_slips), so there is nothing to assert here.
        return
    if not is_admin and staff_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only HR administrators may list payroll across staff.",
        )

    profile = (
        await session.execute(
            select(StaffProfile).where(StaffProfile.id == staff_id)
        )
    ).scalar_one_or_none()

    # Campus isolation applies to admins too: an HR admin bound to one campus
    # has no business reading another campus's payroll. Checked before the
    # ownership branch so it covers both audiences.
    if profile is not None:
        assert_campus_allowed(principal, profile.campus_id)

    if is_admin:
        return

    caller_user_id = (principal.raw_claims or {}).get("lh_user_id")
    if (
        caller_user_id is None
        or profile is None
        or profile.user_id is None
        or profile.user_id != caller_user_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You may only view your own salary information.",
        )

async def _assert_slip_in_campus_scope(
    principal: KeycloakUserPrincipal,
    slip_id: int,
    session: AsyncSession,
) -> None:
    """A salary slip belongs to the campus of the staff member it pays.

    `process_salary_slip_payment` looks the slip up by id alone, so without
    this a campus-bound admin could disburse against any slip in the org.
    A missing slip is left to the service's own 404 rather than duplicated
    here, so the error surface does not change.
    """
    slip = (
        await session.execute(select(SalarySlip).where(SalarySlip.id == slip_id))
    ).scalar_one_or_none()
    if slip is None:
        return
    profile = (
        await session.execute(
            select(StaffProfile).where(StaffProfile.id == slip.staff_id)
        )
    ).scalar_one_or_none()
    if profile is not None:
        assert_campus_allowed(principal, profile.campus_id)


router = APIRouter(dependencies=[Depends(require_sms_hr_payroll_feature)])


# ── Salary Structures ──

@router.post(
    "/structures",
    response_model=SalaryStructureRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create or Update Staff Salary Structure",
    dependencies=[Depends(require_permission(PAYROLL, "create"))],
)
async def create_or_update_salary_structure(
    payload: SalaryStructureCreate,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_PAYROLL_ADMIN)),
) -> SalaryStructureRead:
    # Verify staff profile exists
    staff_stmt = select(StaffProfile).where(StaffProfile.id == payload.staff_id)
    staff = (await session.execute(staff_stmt)).scalar_one_or_none()
    if not staff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Staff member with ID {payload.staff_id} not found.",
        )

    # Fail LOUDLY: this write names a specific staff member, and silently
    # redirecting it to a different campus's employee would be far worse than
    # refusing. A campus-bound admin must not set pay at another campus.
    assert_campus_allowed(principal, staff.campus_id)

    gross = round(
        payload.basic
        + payload.housing_allowance
        + payload.medical_allowance
        + payload.other_allowances,
        2,
    )
    total_deductions = round(
        payload.tax_deduction + payload.provident_fund + payload.other_deductions,
        2,
    )
    net = round(max(0.0, gross - total_deductions), 2)

    # Check existing structure for staff
    stmt = select(SalaryStructure).where(SalaryStructure.staff_id == payload.staff_id)
    struct = (await session.execute(stmt)).scalar_one_or_none()

    if struct:
        struct.basic = payload.basic
        struct.housing_allowance = payload.housing_allowance
        struct.medical_allowance = payload.medical_allowance
        struct.other_allowances = payload.other_allowances
        struct.tax_deduction = payload.tax_deduction
        struct.provident_fund = payload.provident_fund
        struct.other_deductions = payload.other_deductions
        struct.gross_salary = gross
        struct.total_deductions = total_deductions
        struct.net_salary = net
        struct.updated_at = datetime.datetime.now(datetime.timezone.utc)
    else:
        struct = SalaryStructure(
            staff_id=payload.staff_id,
            basic=payload.basic,
            housing_allowance=payload.housing_allowance,
            medical_allowance=payload.medical_allowance,
            other_allowances=payload.other_allowances,
            tax_deduction=payload.tax_deduction,
            provident_fund=payload.provident_fund,
            other_deductions=payload.other_deductions,
            gross_salary=gross,
            total_deductions=total_deductions,
            net_salary=net,
        )
        session.add(struct)

    await session.commit()
    await session.refresh(struct)
    return SalaryStructureRead.model_validate(struct)


@router.get(
    "/structures/{staff_id}",
    response_model=SalaryStructureRead,
    summary="Get Staff Salary Structure",
    dependencies=[Depends(require_permission(PAYROLL, "read"))],
)
async def get_staff_salary_structure(
    staff_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> SalaryStructureRead:
    await _assert_may_read_salary(principal, staff_id, session)
    stmt = select(SalaryStructure).where(SalaryStructure.staff_id == staff_id)
    struct = (await session.execute(stmt)).scalar_one_or_none()
    if not struct:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Salary structure for staff ID {staff_id} not found.",
        )
    return SalaryStructureRead.model_validate(struct)


# ── Salary Slips ──

@router.post(
    "/slips/generate",
    response_model=List[SalarySlipRead],
    status_code=status.HTTP_201_CREATED,
    summary="Generate Batch Monthly Salary Slips",
    dependencies=[Depends(require_permission(PAYROLL, "create"))],
)
async def generate_salary_slips_batch(
    payload: BatchSalarySlipGenerateRequest,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_PAYROLL_ADMIN)),
) -> List[SalarySlipRead]:
    # THE headline campus bug. The service filters on `payload.campus_id`,
    # which arrives in the request BODY -- somewhere `require_campus_access`
    # never looks. Omitting it meant "every active staff member at every
    # campus", so a campus-bound admin could generate the whole org's payroll.
    #
    # Two guards, deliberately: assert_campus_allowed refuses an explicit
    # cross-campus request outright (a write naming a campus must fail loudly,
    # not quietly land elsewhere), and resolve_scoped_campus_id then pins an
    # OMITTED campus to the caller's own so absence cannot mean "everyone".
    assert_campus_allowed(principal, payload.campus_id)
    scoped_payload = payload.model_copy(
        update={"campus_id": resolve_scoped_campus_id(principal, payload.campus_id)}
    )
    slips = await generate_batch_salary_slips(session=session, payload=scoped_payload)

    # Record WHO prepared these. sms_salary_slip has no created_by column, so
    # without this the system cannot identify the preparer -- and separation
    # of duties has nothing to check an approver against.
    await record_prepared_actions(
        session=session,
        slips=slips,
        actor_user_id=(principal.raw_claims or {}).get("lh_user_id"),
    )
    await session.commit()
    return [SalarySlipRead.model_validate(s) for s in slips]


@router.get(
    "/slips",
    response_model=List[SalarySlipRead],
    summary="List Salary Slips",
    dependencies=[Depends(require_permission(PAYROLL, "read"))],
)
async def list_salary_slips(
    staff_id: Optional[int] = Query(None, description="Filter by Staff ID"),
    month: Optional[int] = Query(None, ge=1, le=12, description="Filter by Month"),
    year: Optional[int] = Query(None, ge=2000, le=2100, description="Filter by Year"),
    payment_status: Optional[SalaryPaymentStatus] = Query(None, description="Filter by Payment Status"),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> List[SalarySlipRead]:
    query = select(SalarySlip)
    await _assert_may_read_salary(principal, staff_id, session)

    # Reads NARROW rather than fail: an unscoped listing should return the
    # caller's own campus, not the whole org and not a 403. Slips carry no
    # campus of their own, so this scopes through the staff member they pay.
    scoped_campus_id = resolve_scoped_campus_id(principal, None)
    if scoped_campus_id is not None:
        query = query.where(
            SalarySlip.staff_id.in_(
                select(StaffProfile.id).where(
                    StaffProfile.campus_id == scoped_campus_id
                )
            )
        )

    if type(staff_id) is int:
        query = query.where(SalarySlip.staff_id == staff_id)
    if type(month) is int:
        query = query.where(SalarySlip.month == month)
    if type(year) is int:
        query = query.where(SalarySlip.year == year)
    if (isinstance(payment_status, SalaryPaymentStatus) or type(payment_status) is str) and not hasattr(payment_status, "default"):
        query = query.where(SalarySlip.payment_status == payment_status)

    query = query.order_by(SalarySlip.year.desc(), SalarySlip.month.desc(), SalarySlip.id.desc())
    result = await session.execute(query)
    slips = result.scalars().all()
    return [SalarySlipRead.model_validate(s) for s in slips]


@router.get(
    "/slips/{slip_id}",
    response_model=SalarySlipRead,
    summary="Get Salary Slip by ID",
    dependencies=[Depends(require_permission(PAYROLL, "read"))],
)
async def get_salary_slip(
    slip_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> SalarySlipRead:
    stmt = select(SalarySlip).where(SalarySlip.id == slip_id)
    slip = (await session.execute(stmt)).scalar_one_or_none()
    if not slip:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Salary slip with ID {slip_id} not found.",
        )
    # Checked AFTER the lookup because the slip carries the staff_id this has
    # to be judged against; the 404 above leaks nothing beyond slip existence.
    await _assert_may_read_salary(principal, slip.staff_id, session)
    return SalarySlipRead.model_validate(slip)


@router.post(
    "/slips/{slip_id}/pay",
    response_model=SalarySlipRead,
    summary="Record Salary Slip Disbursement Payment",
    dependencies=[Depends(require_permission(PAYROLL, "approve"))],
)
async def record_salary_payment(
    slip_id: int,
    payload: ProcessSalaryPaymentRequest,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_PAYROLL_ADMIN)),
) -> SalarySlipRead:
    # The service looks a slip up by id with no campus filter at all, so this
    # resolves the slip's owning campus first. Loud failure again: paying out
    # against another campus's slip is not something to silently reinterpret.
    await _assert_slip_in_campus_scope(principal, slip_id, session)

    # Separation of duties. A slip must have been approved by someone other
    # than the person who prepared it. Refused rather than warned: money that
    # has gone out cannot be recalled, so refusing is the recoverable
    # direction.
    await assert_payable(session, slip_id)

    slip = await process_salary_slip_payment(session=session, slip_id=slip_id, payload=payload)

    from src.services.sms.payroll_approval import record_payroll_action

    profile = (
        await session.execute(
            select(StaffProfile).where(StaffProfile.id == slip.staff_id)
        )
    ).scalar_one_or_none()
    await record_payroll_action(
        session=session,
        slip=slip,
        action=PayrollActionType.PAID,
        actor_user_id=(principal.raw_claims or {}).get("lh_user_id"),
        campus_id=profile.campus_id if profile is not None else None,
    )
    await session.commit()
    return SalarySlipRead.model_validate(slip)


# ── Payroll approval (separation of duties) ──


@router.post(
    "/slips/approve",
    response_model=PayrollApprovalResponse,
    summary="Approve Salary Slips for Payment",
    description=(
        "Approve slips so they can be paid. A slip cannot be approved by the "
        "person who prepared it. Takes explicit slip ids rather than a filter: "
        "a payroll batch is a moving target, and approving by filter could "
        "sweep in a slip generated after the reviewer last looked."
    ),
    dependencies=[Depends(require_permission(PAYROLL, "approve"))],
)
async def approve_salary_slips(
    payload: PayrollApprovalRequest,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_PAYROLL_ADMIN)),
) -> PayrollApprovalResponse:
    for slip_id in payload.slip_ids:
        await _assert_slip_in_campus_scope(principal, slip_id, session)

    results = await approve_slips(
        session=session,
        slip_ids=payload.slip_ids,
        actor_user_id=(principal.raw_claims or {}).get("lh_user_id"),
        note=payload.note,
        reject=False,
    )
    return PayrollApprovalResponse(
        results=[PayrollApprovalOutcome(**r) for r in results]
    )


@router.post(
    "/slips/reject",
    response_model=PayrollApprovalResponse,
    summary="Reject Salary Slips",
    description="Send slips back rather than approving them. The preparer may reject their own.",
    dependencies=[Depends(require_permission(PAYROLL, "approve"))],
)
async def reject_salary_slips(
    payload: PayrollApprovalRequest,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_PAYROLL_ADMIN)),
) -> PayrollApprovalResponse:
    for slip_id in payload.slip_ids:
        await _assert_slip_in_campus_scope(principal, slip_id, session)

    results = await approve_slips(
        session=session,
        slip_ids=payload.slip_ids,
        actor_user_id=(principal.raw_claims or {}).get("lh_user_id"),
        note=payload.note,
        reject=True,
    )
    return PayrollApprovalResponse(
        results=[PayrollApprovalOutcome(**r) for r in results]
    )


@router.get(
    "/slips/{slip_id}/actions",
    response_model=List[PayrollActionRead],
    summary="Salary Slip Action Trail",
    description=(
        "Append-only history of every step taken on this slip: who prepared "
        "it, who approved or rejected it, who paid it, and the net figure at "
        "each point."
    ),
    dependencies=[Depends(require_permission(PAYROLL, "read"))],
)
async def list_slip_actions(
    slip_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> List[PayrollActionRead]:
    slip = (
        await session.execute(select(SalarySlip).where(SalarySlip.id == slip_id))
    ).scalar_one_or_none()
    if not slip:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Salary slip with ID {slip_id} not found.",
        )
    # Same gate as reading the slip itself: an employee may see the trail on
    # their own pay, nobody browses a colleague's.
    await _assert_may_read_salary(principal, slip.staff_id, session)

    rows = (
        await session.execute(
            select(PayrollAction)
            .where(PayrollAction.slip_id == slip_id)
            .order_by(PayrollAction.id.asc())
        )
    ).scalars().all()
    return [PayrollActionRead.model_validate(r) for r in rows]
