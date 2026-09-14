import datetime
import logging
import uuid
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy import and_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_hr import LeaveStatus, LeaveType, StaffLeave, StaffProfile
from src.db.sms_payroll import SalaryPaymentStatus, SalarySlip, SalaryStructure
from src.schemas.sms_payroll import (
    BatchSalarySlipGenerateRequest,
    ProcessSalaryPaymentRequest,
)

logger = logging.getLogger(__name__)

# Payroll convention: a month is treated as 30 days for daily-rate purposes,
# so an unpaid day costs basic/30 regardless of whether the month has 28 or 31
# days. Using the real day count instead would pay staff differently for the
# same absence depending on the month, which is the kind of thing that ends up
# in a grievance.
PAYROLL_DAYS_PER_MONTH = 30


def _mask_amount(value: Optional[float]) -> str:
    """Redact a salary figure for logs/audit trails.

    Payroll rows are among the most sensitive data a school holds — an exact
    salary leaking into a log aggregator is a real privacy incident, and logs
    are far more widely readable than the payroll screen itself. Order of
    magnitude is kept because it is what makes a log line useful for debugging
    ("did we compute 5k or 500k?") without disclosing the actual figure.
    """
    if value is None:
        return "***"
    try:
        magnitude = len(str(int(abs(float(value)))))
    except (TypeError, ValueError):
        return "***"
    return f"***(~1e{max(0, magnitude - 1)})"


async def _count_unpaid_leave_days(
    session: AsyncSession,
    staff_id: int,
    month: int,
    year: int,
) -> int:
    """Approved UNPAID leave days for this staff member falling inside the
    pay month.

    Only APPROVED counts: a PENDING request has not been granted, and
    docking pay for a request that may yet be rejected would be wrong.
    Only UNPAID counts: ANNUAL/SICK/CASUAL/MATERNITY are paid leave by
    definition, so deducting for them would silently convert the school's
    paid-leave policy into an unpaid one.

    Leave spanning a month boundary is clipped to the part inside this pay
    period, so a 10-day leave straddling month-end is not charged twice.
    """
    period_start = datetime.date(year, month, 1)
    if month == 12:
        period_end = datetime.date(year, 12, 31)
    else:
        period_end = datetime.date(year, month + 1, 1) - datetime.timedelta(days=1)

    stmt = select(StaffLeave).where(
        and_(
            StaffLeave.staff_id == staff_id,
            StaffLeave.leave_type == LeaveType.UNPAID,
            StaffLeave.status == LeaveStatus.APPROVED,
            StaffLeave.start_date <= period_end,
            StaffLeave.end_date >= period_start,
        )
    )
    leaves = (await session.execute(stmt)).scalars().all()

    total_days = 0
    for leave in leaves:
        overlap_start = max(leave.start_date, period_start)
        overlap_end = min(leave.end_date, period_end)
        if overlap_end >= overlap_start:
            total_days += (overlap_end - overlap_start).days + 1

    # Cannot dock more than the whole month.
    return min(total_days, PAYROLL_DAYS_PER_MONTH)


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

        # Unpaid leave is a deduction against the BASIC daily rate, not
        # against gross: allowances (housing, medical) are generally not
        # pro-rated for absence, and docking them would over-penalise.
        unpaid_days = await _count_unpaid_leave_days(
            session, staff_id=staff.id, month=payload.month, year=payload.year
        )
        unpaid_leave_deduction = 0.0
        if unpaid_days > 0 and basic > 0:
            daily_rate = basic / PAYROLL_DAYS_PER_MONTH
            unpaid_leave_deduction = round(daily_rate * unpaid_days, 2)

        deductions = round(tax + pf + other_ded + unpaid_leave_deduction, 2)
        net = round(max(0.0, gross - deductions), 2)

        if unpaid_days > 0:
            # Masked: see _mask_amount — an exact salary must not reach logs.
            logger.info(
                "Payroll %s/%s staff_id=%s: %d unpaid leave day(s), deduction=%s, net=%s",
                payload.month, payload.year, staff.id, unpaid_days,
                _mask_amount(unpaid_leave_deduction), _mask_amount(net),
            )

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
            unpaid_leave_days=unpaid_days,
            unpaid_leave_deduction=unpaid_leave_deduction,
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
