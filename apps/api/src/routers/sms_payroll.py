import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.events.database import get_db_session
from src.core.keycloak_auth import KeycloakUserPrincipal, get_current_user_principal
from src.db.sms_hr import StaffProfile
from src.db.sms_payroll import SalaryPaymentStatus, SalarySlip, SalaryStructure
from src.schemas.sms_payroll import (
    BatchSalarySlipGenerateRequest,
    ProcessSalaryPaymentRequest,
    SalarySlipRead,
    SalaryStructureCreate,
    SalaryStructureRead,
)
from src.security.features_utils.dependencies import require_sms_hr_payroll_feature
from src.services.sms.payroll import (
    generate_batch_salary_slips,
    process_salary_slip_payment,
)

router = APIRouter(dependencies=[Depends(require_sms_hr_payroll_feature)])


# ── Salary Structures ──

@router.post(
    "/structures",
    response_model=SalaryStructureRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create or Update Staff Salary Structure",
)
async def create_or_update_salary_structure(
    payload: SalaryStructureCreate,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> SalaryStructureRead:
    # Verify staff profile exists
    staff_stmt = select(StaffProfile).where(StaffProfile.id == payload.staff_id)
    staff = (await session.execute(staff_stmt)).scalar_one_or_none()
    if not staff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Staff member with ID {payload.staff_id} not found.",
        )

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
)
async def get_staff_salary_structure(
    staff_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> SalaryStructureRead:
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
)
async def generate_salary_slips_batch(
    payload: BatchSalarySlipGenerateRequest,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> List[SalarySlipRead]:
    slips = await generate_batch_salary_slips(session=session, payload=payload)
    return [SalarySlipRead.model_validate(s) for s in slips]


@router.get(
    "/slips",
    response_model=List[SalarySlipRead],
    summary="List Salary Slips",
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
    return SalarySlipRead.model_validate(slip)


@router.post(
    "/slips/{slip_id}/pay",
    response_model=SalarySlipRead,
    summary="Record Salary Slip Disbursement Payment",
)
async def record_salary_payment(
    slip_id: int,
    payload: ProcessSalaryPaymentRequest,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> SalarySlipRead:
    slip = await process_salary_slip_payment(session=session, slip_id=slip_id, payload=payload)
    return SalarySlipRead.model_validate(slip)
