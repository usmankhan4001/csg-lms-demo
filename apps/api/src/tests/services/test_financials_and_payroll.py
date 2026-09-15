"""
Comprehensive Unit Tests for Financial Ledger Invariant Engine and Progressive Payroll Engine.
"""

import datetime
import pytest
from fastapi import HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_financials import AccountType, ChartOfAccounts, JournalEntry
from src.db.sms_hr import ContractType, StaffProfile
from src.db.sms_payroll import SalaryStructure
from src.schemas.sms_financials import (
    ChartOfAccountsCreate,
    JournalEntryCreate,
    JournalEntryLineCreate,
)
from src.schemas.sms_payroll import BatchSalarySlipGenerateRequest
from src.services.sms.financials_engine import (
    BudgetBurnStatus,
    DoubleEntryValidationError,
    GeneralLedgerEngine,
    quantize_amount,
    validate_double_entry_balance,
)
from src.services.sms.payroll_engine import (
    DEFAULT_TAX_BRACKETS,
    ProgressivePayrollEngine,
    SegregationOfDutiesViolation,
    TaxBracket,
    calculate_pension_deductions,
    calculate_progressive_tax,
    compute_progressive_payslip,
    quantize_currency,
)


# =========================================================================
# 1. Financial Ledger Invariant Engine Unit Tests
# =========================================================================

def test_quantize_amount():
    """Verify precision floating point quantization."""
    assert quantize_amount(100.004) == 100.00
    assert quantize_amount(100.006) == 100.01
    assert quantize_amount(0) == 0.0


def test_validate_double_entry_balance_success():
    """Test valid balanced multi-line journal entry."""
    lines = [
        JournalEntryLineCreate(account_id=1, debit_amount=1500.0, credit_amount=0.0),
        JournalEntryLineCreate(account_id=2, debit_amount=500.0, credit_amount=0.0),
        JournalEntryLineCreate(account_id=3, debit_amount=0.0, credit_amount=2000.0),
    ]
    tot_debit, tot_credit, is_balanced = validate_double_entry_balance(lines)
    assert tot_debit == 2000.0
    assert tot_credit == 2000.0
    assert is_balanced is True


def test_validate_double_entry_balance_imbalance_fails():
    """Test unbalanced entry fails validation."""
    lines = [
        JournalEntryLineCreate(account_id=1, debit_amount=1500.0, credit_amount=0.0),
        JournalEntryLineCreate(account_id=2, debit_amount=0.0, credit_amount=1400.0),
    ]
    with pytest.raises(DoubleEntryValidationError) as exc_info:
        validate_double_entry_balance(lines)
    assert "Double-entry validation failed" in str(exc_info.value.detail)


def test_validate_double_entry_single_line_fails():
    """Test entry with fewer than 2 lines fails."""
    lines = [
        JournalEntryLineCreate(account_id=1, debit_amount=100.0, credit_amount=0.0)
    ]
    with pytest.raises(DoubleEntryValidationError) as exc_info:
        validate_double_entry_balance(lines)
    assert "at least 2 line items" in str(exc_info.value.detail)


def test_validate_double_entry_both_debit_credit_same_line_fails():
    """Test specifying both debit and credit on a single line fails."""
    lines = [
        JournalEntryLineCreate(account_id=1, debit_amount=100.0, credit_amount=50.0),
        JournalEntryLineCreate(account_id=2, debit_amount=0.0, credit_amount=50.0),
    ]
    with pytest.raises(DoubleEntryValidationError) as exc_info:
        validate_double_entry_balance(lines)
    assert "exclusively a Debit or a Credit" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_general_ledger_posting_and_reversal(db: AsyncSession):
    """Test end-to-end GL posting, balance mutation, reversal, and trial balance."""
    # 1. Setup balanced accounts: Cash (Asset 0.0), Tuition Revenue (Revenue 0.0), Expense (Expense 0.0)
    cash = ChartOfAccounts(
        account_code="1010",
        account_name="Cash at Bank",
        account_type=AccountType.ASSET,
        campus_id=1,
        balance=0.0,
        is_active=True,
    )
    revenue = ChartOfAccounts(
        account_code="4010",
        account_name="Tuition Revenue",
        account_type=AccountType.REVENUE,
        campus_id=1,
        balance=0.0,
        is_active=True,
    )
    expense = ChartOfAccounts(
        account_code="5010",
        account_name="Lab Supplies Expense",
        account_type=AccountType.EXPENSE,
        campus_id=1,
        balance=0.0,
        is_active=True,
        description="Science Department",
    )
    db.add_all([cash, revenue, expense])
    await db.commit()
    await db.refresh(cash)
    await db.refresh(revenue)
    await db.refresh(expense)

    # 2. Post Journal Voucher: Debit Cash 5000, Credit Revenue 5000
    entry_payload = JournalEntryCreate(
        campus_id=1,
        entry_date=datetime.date(2026, 9, 1),
        reference_no="JV-2026-TEST01",
        description="Term tuition fee receipt",
        lines=[
            JournalEntryLineCreate(account_id=cash.id, debit_amount=5000.0, credit_amount=0.0),
            JournalEntryLineCreate(account_id=revenue.id, debit_amount=0.0, credit_amount=5000.0),
        ],
    )
    posted_entry = await GeneralLedgerEngine.post_journal_voucher(db, entry_payload)
    assert posted_entry.id is not None
    assert posted_entry.total_debit == 5000.0
    assert posted_entry.total_credit == 5000.0

    await db.refresh(cash)
    await db.refresh(revenue)
    assert cash.balance == 5000.0  # Asset increases on debit
    assert revenue.balance == 5000.0  # Revenue increases on credit

    # 3. Test Trial Balance
    tb = await GeneralLedgerEngine.compute_trial_balance(db, campus_id=1)
    assert tb.is_balanced is True
    assert tb.total_debit == 5000.0
    assert tb.total_credit == 5000.0

    # 4. Reverse Journal Entry
    reversal = await GeneralLedgerEngine.create_reversal_entry(
        db,
        entry_id=posted_entry.id,
        reason="Erroneous deposit reversal",
    )
    assert reversal.reverses_entry_id == posted_entry.id
    assert reversal.total_debit == 5000.0
    assert reversal.total_credit == 5000.0

    await db.refresh(cash)
    await db.refresh(revenue)
    assert cash.balance == 0.0  # Unwound
    assert revenue.balance == 0.0    # Unwound

    # 5. Prevent Reversing a Reversal
    with pytest.raises(HTTPException) as exc_info:
        await GeneralLedgerEngine.create_reversal_entry(db, entry_id=reversal.id)
    assert "already a reversal" in str(exc_info.value.detail)

    # 6. Prevent Double Reversal of Original Entry
    with pytest.raises(HTTPException) as exc_info2:
        await GeneralLedgerEngine.create_reversal_entry(db, entry_id=posted_entry.id)
    assert "already reversed" in str(exc_info2.value.detail)


@pytest.mark.asyncio
async def test_departmental_budget_burn_calculator(db: AsyncSession):
    """Test Departmental Budget Burn calculations and status classification."""
    expense_dept = ChartOfAccounts(
        account_code="5050",
        account_name="STEM Lab Supplies",
        account_type=AccountType.EXPENSE,
        campus_id=1,
        balance=45000.0,
        is_active=True,
        description="Robotics & AI Department",
    )
    db.add(expense_dept)
    await db.commit()
    await db.refresh(expense_dept)

    budgets = {"5050": 50000.0}
    summary = await GeneralLedgerEngine.calculate_departmental_budget_burn(
        db,
        campus_id=1,
        allocated_budgets=budgets,
    )
    assert summary.total_allocated >= 50000.0
    assert summary.total_spent >= 45000.0

    dept_report = next(r for r in summary.department_reports if r.account_code == "5050")
    assert dept_report.allocated_budget == 50000.0
    assert dept_report.actual_spent == 45000.0
    assert dept_report.burn_percentage == 90.0
    assert dept_report.burn_status == BudgetBurnStatus.WARNING


# =========================================================================
# 2. Progressive Payroll Engine Unit Tests
# =========================================================================

def test_progressive_tax_brackets_calculation():
    """Test tiered marginal calculation against progressive brackets."""
    # Test $500 (below 1000 tax free threshold)
    res_low = calculate_progressive_tax(500.0)
    assert res_low.total_tax == 0.0
    assert res_low.effective_tax_rate == 0.0

    # Test $2500:
    # 0 - 1000: $0 (0%)
    # 1000 - 2500: $1500 * 10% = $150
    res_mid = calculate_progressive_tax(2500.0)
    assert res_mid.total_tax == 150.0
    assert res_mid.effective_tax_rate == 6.0

    # Test $8000:
    # 0 - 1000: $0 (0%)
    # 1000 - 3000: $2000 * 10% = $200
    # 3000 - 6000: $3000 * 15% = $450
    # 6000 - 8000: $2000 * 20% = $400
    # Total = 200 + 450 + 400 = $1050
    res_high = calculate_progressive_tax(8000.0)
    assert res_high.total_tax == 1050.0
    assert res_high.effective_tax_rate == 13.13


def test_pension_deductions_calculation():
    """Test 5% employee and 5% employer retirement contributions."""
    pension = calculate_pension_deductions(basic_salary=6000.0, employee_rate=0.05, employer_rate=0.05)
    assert pension.pensionable_base == 6000.0
    assert pension.employee_contribution == 300.0
    assert pension.employer_contribution == 300.0
    assert pension.total_pension_fund == 6000.0 * 0.10


def test_compute_progressive_payslip_breakdown_and_clamping():
    """Test full payslip calculation with allowances, unpaid leave, pension, tax, and non-negative clamping."""
    # Standard Case
    payslip = compute_progressive_payslip(
        staff_id=1,
        basic=5000.0,
        housing_allowance=1000.0,
        medical_allowance=500.0,
        other_allowances=200.0,
        unpaid_leave_days=0,
        pension_employee_rate=0.05,
    )
    assert payslip.gross_salary == 6700.0
    assert payslip.pension.employee_contribution == 250.0  # 5% of 5000
    # Taxable base = 6700 - 250 = 6450
    # Tax: 0-1000: 0, 1000-3000: 200, 3000-6000: 450, 6000-6450: 450 * 0.20 = 90 => Total = 740.0
    assert payslip.tax.total_tax == 740.0
    assert payslip.total_deductions == 250.0 + 740.0
    assert payslip.clamped_net_salary == 6700.0 - 990.0
    assert payslip.was_clamped is False

    # Extreme Deductions Clamping Case: Deductions exceed Gross
    clamped_payslip = compute_progressive_payslip(
        staff_id=2,
        basic=1000.0,
        housing_allowance=0.0,
        other_deductions=5000.0,  # massive custom deduction
    )
    assert clamped_payslip.gross_salary == 1000.0
    assert clamped_payslip.raw_net_salary < 0.0
    assert clamped_payslip.clamped_net_salary == 0.0
    assert clamped_payslip.was_clamped is True


def test_segregation_of_duties_enforcement():
    """Test that a preparer cannot approve their own payroll run."""
    # Same user trying to approve -> Violation
    with pytest.raises(SegregationOfDutiesViolation) as exc_info:
        ProgressivePayrollEngine.enforce_segregation_of_duties(
            preparer_user_id=42,
            approver_user_id=42,
        )
    assert "Segregation of Duties Violation" in str(exc_info.value.detail)

    # Distinct user approving -> Succeeds without exception
    ProgressivePayrollEngine.enforce_segregation_of_duties(
        preparer_user_id=42,
        approver_user_id=99,
    )


@pytest.mark.asyncio
async def test_progressive_batch_payroll_generation(db: AsyncSession):
    """Test generating batch salary slips with progressive tax and action tracking."""
    # Create Staff Profile & Salary Structure
    staff = StaffProfile(
        employee_code="EMP-2026-001",
        full_name="Eleanor Vance",
        designation="Lead Professor",
        department="STEM",
        joining_date=datetime.date(2026, 1, 1),
        contract_type=ContractType.PERMANENT,
        email="eleanor.vance@example.edu",
        campus_id=1,
        basic_salary=6000.0,
        is_active=True,
    )
    db.add(staff)
    await db.commit()
    await db.refresh(staff)

    struct = SalaryStructure(
        staff_id=staff.id,
        basic=6000.0,
        housing_allowance=1000.0,
        medical_allowance=500.0,
        other_allowances=0.0,
        tax_deduction=0.0,
        provident_fund=0.0,
        other_deductions=0.0,
        gross_salary=7500.0,
        total_deductions=0.0,
        net_salary=7500.0,
    )
    db.add(struct)
    await db.commit()

    req = BatchSalarySlipGenerateRequest(
        month=9,
        year=2026,
        campus_id=1,
        staff_ids=[staff.id],
        remarks="September 2026 Academic Payroll",
    )
    slips = await ProgressivePayrollEngine.generate_progressive_batch_slips(
        session=db,
        payload=req,
        preparer_user_id=10,  # User 10 prepared
    )

    assert len(slips) == 1
    slip = slips[0]
    assert slip.basic == 6000.0
    assert slip.gross_salary == 7500.0
    assert slip.provident_fund == 300.0  # 5% of 6000
    assert slip.tax_deduction > 0.0      # Computed via progressive tiers
    assert slip.net_salary > 0.0
    assert slip.net_salary == round(slip.gross_salary - slip.total_deductions, 2)
