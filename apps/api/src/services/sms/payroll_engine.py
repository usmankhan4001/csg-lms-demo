"""
Progressive Payroll Engine for CSG-EMS (Autonomous Education Operating System).

This engine enforces progressive payroll invariants and organizational controls:
1. Progressive Tax Calculation: Multi-tiered marginal tax bracket evaluation.
2. Pension & Statutory Deductions: Employee & employer contributions calculation.
3. Non-Negative Clamped Net Salary: Clamps net compensation >= 0.0 with full breakdown auditability.
4. Unpaid Leave Pro-rating: Pro-rated salary docking based on approved unpaid absences.
5. Segregation of Duties (Dual Authorization): Strictly prevents a payroll preparer from approving their own payroll batch.
"""

import datetime
import logging
import uuid
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from fastapi import HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_hr import LeaveStatus, LeaveType, StaffLeave, StaffProfile
from src.db.sms_hr_extended import PayrollAction, PayrollActionType
from src.db.sms_payroll import SalaryPaymentStatus, SalarySlip, SalaryStructure
from src.schemas.sms_payroll import BatchSalarySlipGenerateRequest

logger = logging.getLogger(__name__)

PAYROLL_DAYS_PER_MONTH = 30


class SegregationOfDutiesViolation(HTTPException):
    """Exception raised when an actor attempts to approve or disburse a payroll run they prepared."""

    def __init__(
        self,
        detail: str = "Segregation of Duties Violation: You prepared this payroll slip and cannot approve or self-authorize it.",
        code: int = status.HTTP_409_CONFLICT,
    ):
        super().__init__(status_code=code, detail=detail)


class TaxBracket(BaseModel):
    """Progressive tax bracket definition."""
    bracket_name: str
    lower_threshold: float = Field(..., ge=0.0)
    upper_threshold: Optional[float] = None  # None indicates infinity / highest bracket
    rate: float = Field(..., ge=0.0, le=1.0)  # Decimal percentage e.g. 0.10 for 10%


class TaxBracketBreakdownItem(BaseModel):
    """Breakdown of tax computed within a specific marginal bracket."""
    bracket_name: str
    lower_threshold: float
    upper_threshold: Optional[float]
    rate: float
    taxable_amount_in_bracket: float
    tax_amount: float


class ProgressiveTaxResult(BaseModel):
    """Result of progressive tax computation."""
    taxable_income: float
    total_tax: float
    effective_tax_rate: float
    bracket_breakdowns: List[TaxBracketBreakdownItem]


class PensionResult(BaseModel):
    """Result of pension and statutory deduction calculation."""
    pensionable_base: float
    employee_rate: float
    employer_rate: float
    employee_contribution: float
    employer_contribution: float
    total_pension_fund: float


class ProgressivePayslipBreakdown(BaseModel):
    """Comprehensive progressive payslip computation result with non-negative clamping."""
    staff_id: int
    staff_name: Optional[str] = None
    month: int
    year: int
    basic_salary: float
    housing_allowance: float
    medical_allowance: float
    other_allowances: float
    gross_salary: float
    unpaid_leave_days: int
    unpaid_leave_deduction: float
    pension: PensionResult
    tax: ProgressiveTaxResult
    other_deductions: float
    total_deductions: float
    raw_net_salary: float
    clamped_net_salary: float
    was_clamped: bool


# Default Progressive Tax Schedule for Education Sector Staff
DEFAULT_TAX_BRACKETS: List[TaxBracket] = [
    TaxBracket(bracket_name="Tax-Exempt Allowance Tier", lower_threshold=0.0, upper_threshold=1000.0, rate=0.0),
    TaxBracket(bracket_name="Standard Base Tier (10%)", lower_threshold=1000.0, upper_threshold=3000.0, rate=0.10),
    TaxBracket(bracket_name="Mid-Income Bracket (15%)", lower_threshold=3000.0, upper_threshold=6000.0, rate=0.15),
    TaxBracket(bracket_name="Upper-Mid Bracket (20%)", lower_threshold=6000.0, upper_threshold=10000.0, rate=0.20),
    TaxBracket(bracket_name="Executive / Top Tier (25%)", lower_threshold=10000.0, upper_threshold=None, rate=0.25),
]


def quantize_currency(value: Union[float, int, Decimal]) -> float:
    """Rounds currency amounts to exactly 2 decimal places."""
    d = Decimal(str(value))
    return float(d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def calculate_progressive_tax(
    taxable_income: float,
    brackets: Optional[List[TaxBracket]] = None,
) -> ProgressiveTaxResult:
    """
    Computes progressive marginal tax over tiered income brackets.
    Each dollar within a bracket is taxed only at that bracket's marginal rate.
    """
    tax_brackets = brackets or DEFAULT_TAX_BRACKETS
    income_dec = Decimal(str(max(0.0, taxable_income)))

    total_tax_dec = Decimal("0.00")
    breakdowns: List[TaxBracketBreakdownItem] = []

    for bracket in tax_brackets:
        lower_dec = Decimal(str(bracket.lower_threshold))
        upper_dec = Decimal(str(bracket.upper_threshold)) if bracket.upper_threshold is not None else None
        rate_dec = Decimal(str(bracket.rate))

        if income_dec <= lower_dec:
            # Income does not reach this bracket
            breakdowns.append(
                TaxBracketBreakdownItem(
                    bracket_name=bracket.bracket_name,
                    lower_threshold=bracket.lower_threshold,
                    upper_threshold=bracket.upper_threshold,
                    rate=bracket.rate,
                    taxable_amount_in_bracket=0.0,
                    tax_amount=0.0,
                )
            )
            continue

        # Calculate portion of income that sits in this bracket
        if upper_dec is not None:
            bracket_cap = min(income_dec, upper_dec)
        else:
            bracket_cap = income_dec

        taxable_in_bracket = bracket_cap - lower_dec
        tax_in_bracket = taxable_in_bracket * rate_dec

        total_tax_dec += tax_in_bracket

        breakdowns.append(
            TaxBracketBreakdownItem(
                bracket_name=bracket.bracket_name,
                lower_threshold=bracket.lower_threshold,
                upper_threshold=bracket.upper_threshold,
                rate=bracket.rate,
                taxable_amount_in_bracket=quantize_currency(taxable_in_bracket),
                tax_amount=quantize_currency(tax_in_bracket),
            )
        )

    tot_tax = quantize_currency(total_tax_dec)
    taxable_inc = quantize_currency(income_dec)
    effective_rate = (
        quantize_currency((Decimal(str(tot_tax)) / Decimal(str(taxable_inc))) * Decimal("100.00"))
        if taxable_inc > 0
        else 0.0
    )

    return ProgressiveTaxResult(
        taxable_income=taxable_inc,
        total_tax=tot_tax,
        effective_tax_rate=effective_rate,
        bracket_breakdowns=breakdowns,
    )


def calculate_pension_deductions(
    basic_salary: float,
    employee_rate: float = 0.05,
    employer_rate: float = 0.05,
) -> PensionResult:
    """
    Computes employee and employer retirement/provident fund contributions.
    """
    base_dec = Decimal(str(max(0.0, basic_salary)))
    ee_rate_dec = Decimal(str(employee_rate))
    er_rate_dec = Decimal(str(employer_rate))

    ee_contrib = base_dec * ee_rate_dec
    er_contrib = base_dec * er_rate_dec
    tot_pension = ee_contrib + er_contrib

    return PensionResult(
        pensionable_base=quantize_currency(base_dec),
        employee_rate=employee_rate,
        employer_rate=employer_rate,
        employee_contribution=quantize_currency(ee_contrib),
        employer_contribution=quantize_currency(er_contrib),
        total_pension_fund=quantize_currency(tot_pension),
    )


def compute_progressive_payslip(
    staff_id: int,
    basic: float,
    housing_allowance: float = 0.0,
    medical_allowance: float = 0.0,
    other_allowances: float = 0.0,
    other_deductions: float = 0.0,
    unpaid_leave_days: int = 0,
    month: int = 1,
    year: int = 2026,
    staff_name: Optional[str] = None,
    tax_brackets: Optional[List[TaxBracket]] = None,
    pension_employee_rate: float = 0.05,
    pension_employer_rate: float = 0.05,
    days_per_month: int = PAYROLL_DAYS_PER_MONTH,
) -> ProgressivePayslipBreakdown:
    """
    Computes a progressive payslip with all deductions and non-negative clamping:
    - Gross Salary = Basic + Allowances
    - Unpaid Leave Docking = (Basic / 30) * unpaid_leave_days
    - Adjusted Basic = max(0, Basic - Unpaid Leave Docking)
    - Pension = 5% of Adjusted Basic
    - Taxable Income = max(0, Gross Salary - Unpaid Leave Docking - Pension)
    - Progressive Tax = tiered marginal computation
    - Total Deductions = Unpaid Leave + Pension + Progressive Tax + Other Deductions
    - Clamped Net Salary = max(0.0, Gross - Total Deductions)
    """
    basic_val = max(0.0, basic)
    housing_val = max(0.0, housing_allowance)
    medical_val = max(0.0, medical_allowance)
    other_allow_val = max(0.0, other_allowances)
    other_ded_val = max(0.0, other_deductions)

    gross = quantize_currency(basic_val + housing_val + medical_val + other_allow_val)

    # Unpaid leave calculation
    unpaid_days = min(max(0, unpaid_leave_days), days_per_month)
    unpaid_deduction = 0.0
    if unpaid_days > 0 and basic_val > 0:
        daily_rate = basic_val / days_per_month
        unpaid_deduction = quantize_currency(daily_rate * unpaid_days)

    adjusted_basic = max(0.0, basic_val - unpaid_deduction)

    # Pension calculation
    pension_res = calculate_pension_deductions(
        basic_salary=adjusted_basic,
        employee_rate=pension_employee_rate,
        employer_rate=pension_employer_rate,
    )

    # Taxable income base
    taxable_base = max(
        0.0,
        gross - unpaid_deduction - pension_res.employee_contribution,
    )
    tax_res = calculate_progressive_tax(taxable_base, tax_brackets)

    total_ded = quantize_currency(
        unpaid_deduction
        + pension_res.employee_contribution
        + tax_res.total_tax
        + other_ded_val
    )

    raw_net = quantize_currency(gross - total_ded)
    clamped_net = max(0.0, raw_net)
    was_clamped = raw_net < 0.0

    return ProgressivePayslipBreakdown(
        staff_id=staff_id,
        staff_name=staff_name,
        month=month,
        year=year,
        basic_salary=quantize_currency(basic_val),
        housing_allowance=quantize_currency(housing_val),
        medical_allowance=quantize_currency(medical_val),
        other_allowances=quantize_currency(other_allow_val),
        gross_salary=gross,
        unpaid_leave_days=unpaid_days,
        unpaid_leave_deduction=unpaid_deduction,
        pension=pension_res,
        tax=tax_res,
        other_deductions=quantize_currency(other_ded_val),
        total_deductions=total_ded,
        raw_net_salary=raw_net,
        clamped_net_salary=clamped_net,
        was_clamped=was_clamped,
    )


class ProgressivePayrollEngine:
    """
    High-level orchestrator for progressive payroll runs, tax schedules, and separation of duties.
    """

    @staticmethod
    def enforce_segregation_of_duties(
        preparer_user_id: Optional[int],
        approver_user_id: Optional[int],
        action_name: str = "approve",
    ) -> None:
        """
        Enforces Segregation of Duties:
        A user who prepared a payroll entry/batch cannot authorize, approve, or disburse it.
        """
        if (
            preparer_user_id is not None
            and approver_user_id is not None
            and preparer_user_id == approver_user_id
        ):
            raise SegregationOfDutiesViolation(
                f"Segregation of Duties Violation: User {approver_user_id} prepared this payroll run "
                f"and is strictly prohibited from executing '{action_name}'. A distinct authorized reviewer is required."
            )

    @staticmethod
    async def generate_progressive_batch_slips(
        session: AsyncSession,
        payload: BatchSalarySlipGenerateRequest,
        preparer_user_id: Optional[int] = None,
        tax_brackets: Optional[List[TaxBracket]] = None,
        pension_rate: float = 0.05,
    ) -> List[SalarySlip]:
        """
        Executes a monthly batch payroll run applying progressive taxation and pension calculations,
        persisting salary slips and recording the preparer in the audit trail.
        """
        from src.services.sms.payroll import _count_unpaid_leave_days
        from src.services.sms.payroll_approval import record_prepared_actions

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
            # Check existing slip
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

            struct_stmt = select(SalaryStructure).where(SalaryStructure.staff_id == staff.id)
            struct = (await session.execute(struct_stmt)).scalar_one_or_none()

            basic = struct.basic if struct else (staff.basic_salary or 0.0)
            housing = struct.housing_allowance if struct else 0.0
            medical = struct.medical_allowance if struct else 0.0
            other_allow = struct.other_allowances if struct else 0.0
            other_ded = struct.other_deductions if struct else 0.0

            unpaid_days = await _count_unpaid_leave_days(
                session, staff_id=staff.id, month=payload.month, year=payload.year
            )

            # Progressive calculation
            calc = compute_progressive_payslip(
                staff_id=staff.id,
                basic=basic,
                housing_allowance=housing,
                medical_allowance=medical,
                other_allowances=other_allow,
                other_deductions=other_ded,
                unpaid_leave_days=unpaid_days,
                month=payload.month,
                year=payload.year,
                tax_brackets=tax_brackets,
                pension_employee_rate=pension_rate,
            )

            rand_suffix = uuid.uuid4().hex[:6].upper()
            slip_no = f"SLIP-PROG-{payload.year}{payload.month:02d}-{staff.id}-{rand_suffix}"

            slip = SalarySlip(
                slip_no=slip_no,
                staff_id=staff.id,
                month=payload.month,
                year=payload.year,
                basic=calc.basic_salary,
                housing_allowance=calc.housing_allowance,
                medical_allowance=calc.medical_allowance,
                other_allowances=calc.other_allowances,
                tax_deduction=calc.tax.total_tax,
                provident_fund=calc.pension.employee_contribution,
                other_deductions=calc.other_deductions,
                unpaid_leave_days=calc.unpaid_leave_days,
                unpaid_leave_deduction=calc.unpaid_leave_deduction,
                gross_salary=calc.gross_salary,
                total_deductions=calc.total_deductions,
                net_salary=calc.clamped_net_salary,
                payment_status=SalaryPaymentStatus.PENDING,
                remarks=payload.remarks,
            )
            session.add(slip)
            created_slips.append(slip)

        await session.flush()
        # Record preparer action
        await record_prepared_actions(
            session=session,
            slips=created_slips,
            actor_user_id=preparer_user_id,
        )
        await session.commit()

        for s in created_slips:
            await session.refresh(s)

        # Dispatch payroll.processed webhook
        try:
            from src.services.webhooks.dispatch import dispatch_event_task
            total_gross = sum(s.gross_salary for s in created_slips)
            total_tax = sum(s.tax_deduction for s in created_slips)
            total_net = sum(s.net_salary for s in created_slips)
            dispatch_event_task(
                org_id=1,
                event_name="payroll.processed",
                data={
                    "payroll_period": f"{payload.year}-{payload.month:02d}",
                    "total_employees": len(created_slips),
                    "gross_amount": float(total_gross),
                    "tax_withheld": float(total_tax),
                    "net_disbursement": float(total_net),
                },
            )
        except Exception as we:
            logger.warning("Failed to dispatch payroll.processed webhook: %s", we)

        return created_slips

