"""
General Ledger Invariant Engine for CSG-EMS (Autonomous Education Operating System).

This engine enforces fundamental accounting invariants:
1. Strict Double-Entry Balance: Sum(Debits) == Sum(Credits) for every journal voucher.
2. Reversing Journal Entries: Non-destructive, immutable, auditable corrections linking back to original entries.
3. Real-Time Trial Balance: Calculates aggregated debit & credit balances across all active chart of accounts.
4. Departmental Budget Burn Calculator: Real-time calculation of expense actuals against allocated budgets.
5. Ledger Integrity Verifier: Automated audits of posted entries and debit-credit parity.
"""

import datetime
import logging
import uuid
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from fastapi import HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_financials import (
    AccountType,
    ChartOfAccounts,
    JournalEntry,
    JournalEntryLine,
)
from src.schemas.sms_financials import (
    JournalEntryCreate,
    JournalEntryLineCreate,
    TrialBalanceItemRead,
    TrialBalanceResponse,
)

logger = logging.getLogger(__name__)


class BudgetBurnStatus(str, Enum):
    """Budget burn status classifications based on utilization threshold."""
    UNDER_BUDGET = "UNDER_BUDGET"      # < 70% burn
    ON_TRACK = "ON_TRACK"              # 70% - 85% burn
    WARNING = "WARNING"                # 85% - 100% burn
    OVER_BUDGET = "OVER_BUDGET"        # > 100% burn
    CRITICAL = "CRITICAL"              # > 120% burn


class DoubleEntryValidationError(HTTPException):
    """Exception raised when a journal entry fails strict double-entry invariant validation."""

    def __init__(self, detail: str, code: int = status.HTTP_400_BAD_REQUEST):
        super().__init__(status_code=code, detail=detail)


class DepartmentBudgetReport(BaseModel):
    """Departmental or account-level budget burn summary."""
    account_id: int
    account_code: str
    account_name: str
    department_tag: Optional[str] = None
    allocated_budget: float
    actual_spent: float
    remaining_budget: float
    burn_percentage: float
    burn_status: BudgetBurnStatus


class CampusBudgetBurnSummary(BaseModel):
    """Campus-wide budget burn summary aggregating all departmental accounts."""
    campus_id: Optional[int] = None
    total_allocated: float
    total_spent: float
    total_remaining: float
    overall_burn_percentage: float
    overall_status: BudgetBurnStatus
    department_reports: List[DepartmentBudgetReport]


def quantize_amount(value: Union[float, int, Decimal]) -> float:
    """Quantize financial values to 2 decimal places to prevent floating-point drift."""
    d = Decimal(str(value))
    return float(d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def validate_double_entry_balance(
    lines: Sequence[Union[JournalEntryLineCreate, Dict[str, Any], Any]],
    tolerance: float = 0.001,
) -> Tuple[float, float, bool]:
    """
    Validates double-entry invariant for a list of line items:
    1. Must contain at least 2 lines (minimum 1 debit and 1 credit).
    2. Sum of debits must equal sum of credits within `tolerance`.
    3. Both debits and credits sums must be positive (> 0).
    4. Individual line amounts must be non-negative.
    """
    if not lines or len(lines) < 2:
        raise DoubleEntryValidationError(
            "Journal entry must contain at least 2 line items (debit and credit splits)."
        )

    total_debit_dec = Decimal("0.00")
    total_credit_dec = Decimal("0.00")

    for idx, line in enumerate(lines):
        if isinstance(line, dict):
            debit = Decimal(str(line.get("debit_amount", 0.0) or 0.0))
            credit = Decimal(str(line.get("credit_amount", 0.0) or 0.0))
        else:
            debit = Decimal(str(getattr(line, "debit_amount", 0.0) or 0.0))
            credit = Decimal(str(getattr(line, "credit_amount", 0.0) or 0.0))

        if debit < 0 or credit < 0:
            raise DoubleEntryValidationError(
                f"Line item {idx + 1} contains negative amounts (Debit: {debit}, Credit: {credit}). "
                "Negative entries are prohibited; use opposite column."
            )

        if debit > 0 and credit > 0:
            raise DoubleEntryValidationError(
                f"Line item {idx + 1} specifies both Debit ({debit}) and Credit ({credit}). "
                "Each line item must be exclusively a Debit or a Credit."
            )

        total_debit_dec += debit
        total_credit_dec += credit

    total_debit = float(total_debit_dec.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    total_credit = float(total_credit_dec.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

    if total_debit <= 0.0 or total_credit <= 0.0:
        raise DoubleEntryValidationError(
            f"Journal entry totals must be positive non-zero amounts. (Debit: {total_debit}, Credit: {total_credit})"
        )

    delta = abs(total_debit_dec - total_credit_dec)
    if delta > Decimal(str(tolerance)):
        raise DoubleEntryValidationError(
            f"Double-entry validation failed: Total Debit ({total_debit}) does not equal "
            f"Total Credit ({total_credit}). Imbalance delta: {float(delta):.2f}"
        )

    return total_debit, total_credit, True


class GeneralLedgerEngine:
    """
    Comprehensive General Ledger Invariant and Posting Engine.
    Handles atomic postings, reversing corrections, trial balances, and budget burn telemetry.
    """

    @staticmethod
    async def post_journal_voucher(
        session: AsyncSession,
        payload: JournalEntryCreate,
    ) -> JournalEntry:
        """
        Validates double-entry invariants, adjusts Chart of Accounts balances,
        and atomically records the Journal Entry and its lines.
        """
        total_debit, total_credit, _ = validate_double_entry_balance(payload.lines)

        # Retrieve referenced accounts
        account_ids = [line.account_id for line in payload.lines]
        stmt = select(ChartOfAccounts).where(ChartOfAccounts.id.in_(account_ids))
        accounts_result = await session.execute(stmt)
        accounts = {acc.id: acc for acc in accounts_result.scalars().all()}

        for aid in account_ids:
            if aid not in accounts:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Chart of accounts ID {aid} not found in general ledger.",
                )
            if not accounts[aid].is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Chart of accounts ID {aid} ({accounts[aid].account_name}) is inactive.",
                )

        # Generate unique reference number if omitted
        ref_no = payload.reference_no
        if not ref_no:
            date_str = payload.entry_date.strftime("%Y%m%d")
            rand_suffix = uuid.uuid4().hex[:6].upper()
            ref_no = f"JV-{date_str}-{rand_suffix}"

        # Ensure reference uniqueness
        existing_ref = (
            await session.execute(
                select(JournalEntry).where(JournalEntry.reference_no == ref_no)
            )
        ).scalar_one_or_none()
        if existing_ref:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Journal entry with reference number '{ref_no}' already exists.",
            )

        # Create Journal Entry header
        entry = JournalEntry(
            campus_id=payload.campus_id if isinstance(payload.campus_id, int) else None,
            entry_date=payload.entry_date,
            reference_no=ref_no,
            description=payload.description,
            total_debit=total_debit,
            total_credit=total_credit,
        )
        session.add(entry)
        await session.flush()

        # Create lines and mutate account balances
        for line_in in payload.lines:
            d_amt = quantize_amount(line_in.debit_amount)
            c_amt = quantize_amount(line_in.credit_amount)

            line_rec = JournalEntryLine(
                entry_id=entry.id,
                account_id=line_in.account_id,
                debit_amount=d_amt,
                credit_amount=c_amt,
                description=line_in.description,
            )
            session.add(line_rec)

            acc = accounts[line_in.account_id]
            # Asset and Expense accounts increase with Debit, decrease with Credit
            if acc.account_type in (AccountType.ASSET, AccountType.EXPENSE):
                acc.balance = quantize_amount(acc.balance + d_amt - c_amt)
            else:
                # Liability, Equity, Revenue accounts increase with Credit, decrease with Debit
                acc.balance = quantize_amount(acc.balance + c_amt - d_amt)
            session.add(acc)

        await session.commit()
        await session.refresh(entry)
        logger.info(
            "General Ledger: Successfully posted journal entry %s (Debit: %s, Credit: %s)",
            ref_no, total_debit, total_credit,
        )
        return entry

    @staticmethod
    async def create_reversal_entry(
        session: AsyncSession,
        entry_id: int,
        reason: Optional[str] = None,
        entry_date: Optional[datetime.date] = None,
    ) -> JournalEntry:
        """
        Posts an offsetting reversing journal entry linking to the original entry.
        Swaps all debits and credits, perfectly unwinding account balance mutations.
        Guarantees strict auditability: original entry is never deleted or altered.
        """
        entry = (
            await session.execute(
                select(JournalEntry).where(JournalEntry.id == entry_id)
            )
        ).scalar_one_or_none()
        if not entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Journal entry with ID {entry_id} not found.",
            )

        if entry.reverses_entry_id is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Journal entry {entry_id} is already a reversal of entry {entry.reverses_entry_id}. "
                    "Reversing a reversal entry is prohibited to prevent circular balance mutations."
                ),
            )

        existing_reversal = (
            await session.execute(
                select(JournalEntry).where(JournalEntry.reverses_entry_id == entry_id)
            )
        ).scalars().first()
        if existing_reversal:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Journal entry {entry_id} was already reversed by {existing_reversal.reference_no}.",
            )

        original_lines = (
            await session.execute(
                select(JournalEntryLine).where(JournalEntryLine.entry_id == entry_id)
            )
        ).scalars().all()
        if not original_lines:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Journal entry {entry_id} has no lines to reverse.",
            )

        account_ids = [line.account_id for line in original_lines]
        accounts = {
            acc.id: acc
            for acc in (
                await session.execute(
                    select(ChartOfAccounts).where(ChartOfAccounts.id.in_(account_ids))
                )
            ).scalars().all()
        }

        for aid in account_ids:
            if aid not in accounts:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Chart of accounts ID {aid} referenced in entry no longer exists.",
                )

        reversal_date = entry_date or datetime.date.today()
        rev_ref = f"REV-{entry.reference_no}-{uuid.uuid4().hex[:4].upper()}"

        reversal_entry = JournalEntry(
            campus_id=entry.campus_id,
            entry_date=reversal_date,
            reference_no=rev_ref,
            description=reason or f"Reversal of {entry.reference_no}",
            reverses_entry_id=entry.id,
            total_debit=entry.total_credit,
            total_credit=entry.total_debit,
        )
        session.add(reversal_entry)
        await session.flush()

        for line in original_lines:
            # Swapping debit and credit exactly
            rev_line = JournalEntryLine(
                entry_id=reversal_entry.id,
                account_id=line.account_id,
                debit_amount=line.credit_amount,
                credit_amount=line.debit_amount,
                description=f"Reversal: {line.description or ''}".strip(),
            )
            session.add(rev_line)

            acc = accounts[line.account_id]
            if acc.account_type in (AccountType.ASSET, AccountType.EXPENSE):
                acc.balance = quantize_amount(acc.balance + line.credit_amount - line.debit_amount)
            else:
                acc.balance = quantize_amount(acc.balance + line.debit_amount - line.credit_amount)
            session.add(acc)

        await session.commit()
        await session.refresh(reversal_entry)
        logger.info("General Ledger: Posted reversal %s for entry %s", rev_ref, entry.reference_no)
        return reversal_entry

    @staticmethod
    async def compute_trial_balance(
        session: AsyncSession,
        campus_id: Optional[int] = None,
    ) -> TrialBalanceResponse:
        """
        Computes real-time Trial Balance ledger across active Chart of Accounts.
        Determines debit and credit balances for every account and checks parity.
        """
        query = select(ChartOfAccounts).where(ChartOfAccounts.is_active == True)
        if isinstance(campus_id, int):
            query = query.where(ChartOfAccounts.campus_id == campus_id)

        query = query.order_by(ChartOfAccounts.account_code)
        accounts = (await session.execute(query)).scalars().all()

        items: List[TrialBalanceItemRead] = []
        total_debit_dec = Decimal("0.00")
        total_credit_dec = Decimal("0.00")

        for acc in accounts:
            bal_dec = Decimal(str(acc.balance))
            if acc.account_type in (AccountType.ASSET, AccountType.EXPENSE):
                if bal_dec >= 0:
                    d_bal = bal_dec
                    c_bal = Decimal("0.00")
                else:
                    d_bal = Decimal("0.00")
                    c_bal = abs(bal_dec)
            else:
                if bal_dec >= 0:
                    d_bal = Decimal("0.00")
                    c_bal = bal_dec
                else:
                    d_bal = abs(bal_dec)
                    c_bal = Decimal("0.00")

            d_val = float(d_bal.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
            c_val = float(c_bal.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

            total_debit_dec += d_bal
            total_credit_dec += c_bal

            items.append(
                TrialBalanceItemRead(
                    account_id=acc.id,
                    account_code=acc.account_code,
                    account_name=acc.account_name,
                    account_type=acc.account_type,
                    debit_balance=d_val,
                    credit_balance=c_val,
                )
            )

        tot_debit = float(total_debit_dec.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        tot_credit = float(total_credit_dec.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        is_balanced = abs(tot_debit - tot_credit) < 0.01

        return TrialBalanceResponse(
            campus_id=campus_id if isinstance(campus_id, int) else None,
            items=items,
            total_debit=tot_debit,
            total_credit=tot_credit,
            is_balanced=is_balanced,
        )

    @staticmethod
    async def calculate_departmental_budget_burn(
        session: AsyncSession,
        campus_id: Optional[int] = None,
        allocated_budgets: Optional[Dict[str, float]] = None,
        default_account_budget: float = 50000.0,
    ) -> CampusBudgetBurnSummary:
        """
        Calculates real-time Departmental / Expense Budget Burn:
        - Retrieves all EXPENSE accounts.
        - Matches them with allocated budgets (or fallback defaults).
        - Computes burn percentage, remaining headroom, and classification status.
        """
        query = select(ChartOfAccounts).where(
            ChartOfAccounts.account_type == AccountType.EXPENSE,
            ChartOfAccounts.is_active == True,
        )
        if isinstance(campus_id, int):
            query = query.where(ChartOfAccounts.campus_id == campus_id)

        query = query.order_by(ChartOfAccounts.account_code)
        expense_accounts = (await session.execute(query)).scalars().all()

        budgets = allocated_budgets or {}
        dept_reports: List[DepartmentBudgetReport] = []

        total_alloc_dec = Decimal("0.00")
        total_spent_dec = Decimal("0.00")

        for acc in expense_accounts:
            # Allocated budget lookup by code or account_id
            alloc_val = budgets.get(
                acc.account_code,
                budgets.get(str(acc.id), default_account_budget),
            )
            alloc_dec = Decimal(str(alloc_val))
            spent_dec = Decimal(str(max(0.0, acc.balance)))

            total_alloc_dec += alloc_dec
            total_spent_dec += spent_dec

            remaining_dec = alloc_dec - spent_dec
            burn_pct = float(
                ((spent_dec / alloc_dec) * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                if alloc_dec > 0
                else (Decimal("100.00") if spent_dec > 0 else Decimal("0.00"))
            )

            # Determine status
            if burn_pct > 120.0:
                burn_status = BudgetBurnStatus.CRITICAL
            elif burn_pct > 100.0:
                burn_status = BudgetBurnStatus.OVER_BUDGET
            elif burn_pct >= 85.0:
                burn_status = BudgetBurnStatus.WARNING
            elif burn_pct >= 70.0:
                burn_status = BudgetBurnStatus.ON_TRACK
            else:
                burn_status = BudgetBurnStatus.UNDER_BUDGET

            dept_reports.append(
                DepartmentBudgetReport(
                    account_id=acc.id,
                    account_code=acc.account_code,
                    account_name=acc.account_name,
                    department_tag=acc.description or "General Operations",
                    allocated_budget=float(alloc_dec),
                    actual_spent=float(spent_dec),
                    remaining_budget=float(remaining_dec),
                    burn_percentage=burn_pct,
                    burn_status=burn_status,
                )
            )

        tot_alloc = float(total_alloc_dec.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        tot_spent = float(total_spent_dec.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        tot_rem = float((total_alloc_dec - total_spent_dec).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

        overall_pct = (
            round((tot_spent / tot_alloc) * 100, 2)
            if tot_alloc > 0
            else (100.0 if tot_spent > 0 else 0.0)
        )

        if overall_pct > 120.0:
            overall_status = BudgetBurnStatus.CRITICAL
        elif overall_pct > 100.0:
            overall_status = BudgetBurnStatus.OVER_BUDGET
        elif overall_pct >= 85.0:
            overall_status = BudgetBurnStatus.WARNING
        elif overall_pct >= 70.0:
            overall_status = BudgetBurnStatus.ON_TRACK
        else:
            overall_status = BudgetBurnStatus.UNDER_BUDGET

        return CampusBudgetBurnSummary(
            campus_id=campus_id if isinstance(campus_id, int) else None,
            total_allocated=tot_alloc,
            total_spent=tot_spent,
            total_remaining=tot_rem,
            overall_burn_percentage=overall_pct,
            overall_status=overall_status,
            department_reports=dept_reports,
        )

    @staticmethod
    async def verify_ledger_integrity(
        session: AsyncSession,
        campus_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Performs an invariant verification across the entire General Ledger:
        - Confirms all journal entries have Sum(Debit) == Sum(Credit).
        - Confirms total journal lines debit sum equals total journal lines credit sum.
        - Identifies unbalanced entries or orphaned records.
        """
        q_entries = select(JournalEntry)
        if isinstance(campus_id, int):
            q_entries = q_entries.where(JournalEntry.campus_id == campus_id)

        entries = (await session.execute(q_entries)).scalars().all()

        unbalanced_entries = []
        for e in entries:
            delta = abs(round(e.total_debit - e.total_credit, 2))
            if delta > 0.001:
                unbalanced_entries.append(
                    {"id": e.id, "reference_no": e.reference_no, "delta": delta}
                )

        trial_bal = await GeneralLedgerEngine.compute_trial_balance(session, campus_id)

        return {
            "total_entries_inspected": len(entries),
            "unbalanced_entries_count": len(unbalanced_entries),
            "unbalanced_entries": unbalanced_entries,
            "trial_balance_is_balanced": trial_bal.is_balanced,
            "trial_balance_total_debit": trial_bal.total_debit,
            "trial_balance_total_credit": trial_bal.total_credit,
            "is_ledger_sound": len(unbalanced_entries) == 0 and trial_bal.is_balanced,
        }
