import datetime
import logging
import uuid
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy import and_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_hr import StaffProfile
from src.db.sms_payroll import SalaryPaymentStatus, SalarySlip, SalaryStructure
from src.schemas.sms_payroll import (
    BatchSalarySlipGenerateRequest,
    ProcessSalaryPaymentRequest,
)

logger = logging.getLogger(__name__)


async def generate_batch_salary_slips(
    session: AsyncSession,
    payload: BatchSalarySlipGenerateRequest,
) -> List[SalarySlip]:
    """
    Batch monthly salary slip generation engine for faculty and staff.
    """
    staff_query = select(StaffProfile).where(StaffProfile.is_active == True)
    if isinstance(payload.campus_id, int):
        staff_query = staff_query.where(StaffProfile.campus_id == payload.campus_id)
    if payload.staff_ids and isinstance(payload.staff_ids, list):
        staff_query = staff_query.where(StaffProfile.id.in_(payload.staff_ids))

    staff_members = (await session.execute(staff_query)).scalars().all()
    if not staff_members:
        return []

    created_slips: List[SalarySlip] = []

    for staff in staff_members:
        # Check if slip already exists for this staff/month/year
        existing_stmt = select(SalarySlip).where(
            and_(
                SalarySlip.staff_id == staff.id,
                SalarySlip.month == payload.month,
                SalarySlip.year == payload.year,
                SalarySlip.payment_status != SalaryPaymentStatus.CANCELLED,
            )
        )
        existing_slip = (await session.execute(existing_stmt)).scalar_one_or_none()
        if existing_slip:
            created_slips.append(existing_slip)
            continue

        # Look up salary structure
        struct_stmt = select(SalaryStructure).where(SalaryStructure.staff_id == staff.id)
        struct = (await session.execute(struct_stmt)).scalar_one_or_none()

        if struct:
            basic = struct.basic
            housing = struct.housing_allowance
            medical = struct.medical_allowance
            other_allow = struct.other_allowances
            tax = struct.tax_deduction
            pf = struct.provident_fund
            other_ded = struct.other_deductions
        else:
            basic = staff.basic_salary or 0.0
            housing = 0.0
            medical = 0.0
            other_allow = 0.0
            tax = 0.0
            pf = 0.0
            other_ded = 0.0

        gross = round(basic + housing + medical + other_allow, 2)
        deductions = round(tax + pf + other_ded, 2)
        net = round(max(0.0, gross - deductions), 2)

        rand_suffix = uuid.uuid4().hex[:6].upper()
        slip_no = f"SLIP-{payload.year}{payload.month:02d}-{staff.id}-{rand_suffix}"

        slip = SalarySlip(
            slip_no=slip_no,
            staff_id=staff.id,
            month=payload.month,
            year=payload.year,
            basic=basic,
            housing_allowance=housing,
            medical_allowance=medical,
            other_allowances=other_allow,
            tax_deduction=tax,
            provident_fund=pf,
            other_deductions=other_ded,
            gross_salary=gross,
            total_deductions=deductions,
            net_salary=net,
            payment_status=SalaryPaymentStatus.PENDING,
            remarks=payload.remarks,
        )
        session.add(slip)
        created_slips.append(slip)

    await session.commit()
    for s in created_slips:
        await session.refresh(s)

    return created_slips


async def process_salary_slip_payment(
    session: AsyncSession,
    slip_id: int,
    payload: ProcessSalaryPaymentRequest,
) -> SalarySlip:
    """
    Marks a salary slip as PAID and records disbursement timestamp & method.
    """
    stmt = select(SalarySlip).where(SalarySlip.id == slip_id)
    slip = (await session.execute(stmt)).scalar_one_or_none()
    if not slip:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Salary slip with ID {slip_id} not found.",
        )

    if slip.payment_status == SalaryPaymentStatus.PAID:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Salary slip '{slip.slip_no}' has already been paid.",
        )

    slip.payment_status = SalaryPaymentStatus.PAID
    slip.payment_date = payload.payment_date
    slip.payment_method = payload.payment_method
    if payload.remarks:
        slip.remarks = f"{slip.remarks + ' | ' if slip.remarks else ''}{payload.remarks}"

    session.add(slip)
    await session.commit()
    await session.refresh(slip)
    return slip
