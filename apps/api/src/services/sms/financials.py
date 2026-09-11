import datetime
import logging
import uuid
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_financials import (
    AccountType,
    ChartOfAccounts,
    JournalEntry,
    JournalEntryLine,
)
from src.schemas.sms_financials import (
    JournalEntryCreate,
    TrialBalanceItemRead,
    TrialBalanceResponse,
)

logger = logging.getLogger(__name__)


async def validate_and_create_journal_entry(
    session: AsyncSession,
    payload: JournalEntryCreate,
) -> JournalEntry:
    """
    Validates double-entry balance equality and posts journal entry lines to the General Ledger,
    adjusting chart of account balances accordingly.
    """
    if not payload.lines or len(payload.lines) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Journal entry must contain at least 2 lines (debit and credit splits).",
        )

    total_debit = round(sum(line.debit_amount for line in payload.lines), 2)
    total_credit = round(sum(line.credit_amount for line in payload.lines), 2)

    if total_debit <= 0.0 or total_credit <= 0.0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Journal entry debit and credit totals must be greater than zero.",
        )

    # Double-entry check
    if abs(total_debit - total_credit) > 0.001:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Double-entry validation failed: Total Debit ({total_debit}) "
                f"does not equal Total Credit ({total_credit})."
            ),
        )

    # Validate accounts existence
    account_ids = [line.account_id for line in payload.lines]
    stmt = select(ChartOfAccounts).where(ChartOfAccounts.id.in_(account_ids))
    accounts_result = await session.execute(stmt)
    accounts = {acc.id: acc for acc in accounts_result.scalars().all()}

    for aid in account_ids:
        if aid not in accounts:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Chart of accounts ID {aid} not found.",
            )

    # Reference number generation if absent
    ref_no = payload.reference_no
    if not ref_no:
        date_str = payload.entry_date.strftime("%Y%m%d")
        rand_suffix = uuid.uuid4().hex[:6].upper()
        ref_no = f"JE-{date_str}-{rand_suffix}"

    # Verify reference_no uniqueness
    ref_stmt = select(JournalEntry).where(JournalEntry.reference_no == ref_no)
    existing_entry = (await session.execute(ref_stmt)).scalar_one_or_none()
    if existing_entry:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Journal entry with reference_no '{ref_no}' already exists.",
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

    # Create lines & apply balance mutation to accounts
    for line_in in payload.lines:
        line_rec = JournalEntryLine(
            entry_id=entry.id,
            account_id=line_in.account_id,
            debit_amount=round(line_in.debit_amount, 2),
            credit_amount=round(line_in.credit_amount, 2),
            description=line_in.description,
        )
        session.add(line_rec)

        account = accounts[line_in.account_id]
        if account.account_type in (AccountType.ASSET, AccountType.EXPENSE):
            # Normal debit balance
            account.balance = round(
                account.balance + line_in.debit_amount - line_in.credit_amount, 2
            )
        else:
            # Normal credit balance (LIABILITY, EQUITY, REVENUE)
            account.balance = round(
                account.balance + line_in.credit_amount - line_in.debit_amount, 2
            )
        session.add(account)

    await session.commit()
    await session.refresh(entry)
    return entry


async def generate_trial_balance(
    session: AsyncSession,
    campus_id: Optional[int] = None,
) -> TrialBalanceResponse:
    """
    Computes Trial Balance ledger across active Chart of Accounts.
    """
    query = select(ChartOfAccounts).where(ChartOfAccounts.is_active == True)
    if isinstance(campus_id, int):
        query = query.where(ChartOfAccounts.campus_id == campus_id)

    query = query.order_by(ChartOfAccounts.account_code)
    result = await session.execute(query)
    accounts = result.scalars().all()

    items: List[TrialBalanceItemRead] = []
    total_debit = 0.0
    total_credit = 0.0

    for acc in accounts:
        if acc.account_type in (AccountType.ASSET, AccountType.EXPENSE):
            if acc.balance >= 0:
                d_bal = acc.balance
                c_bal = 0.0
            else:
                d_bal = 0.0
                c_bal = abs(acc.balance)
        else:
            if acc.balance >= 0:
                d_bal = 0.0
                c_bal = acc.balance
            else:
                d_bal = abs(acc.balance)
                c_bal = 0.0

        d_bal = round(d_bal, 2)
        c_bal = round(c_bal, 2)
        total_debit += d_bal
        total_credit += c_bal

        items.append(
            TrialBalanceItemRead(
                account_id=acc.id,
                account_code=acc.account_code,
                account_name=acc.account_name,
                account_type=acc.account_type,
                debit_balance=d_bal,
                credit_balance=c_bal,
            )
        )

    total_debit = round(total_debit, 2)
    total_credit = round(total_credit, 2)
    is_balanced = abs(total_debit - total_credit) < 0.01

    return TrialBalanceResponse(
        campus_id=campus_id if isinstance(campus_id, int) else None,
        items=items,
        total_debit=total_debit,
        total_credit=total_credit,
        is_balanced=is_balanced,
    )
