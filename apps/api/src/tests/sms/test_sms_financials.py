import datetime
import pytest
from fastapi import HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_financials import AccountType
from src.schemas.sms_financials import (
    ChartOfAccountsCreate,
    JournalEntryCreate,
    JournalEntryLineCreate,
)
from src.routers.sms_financials import (
    create_chart_of_account,
    create_journal_entry,
    get_chart_of_account,
    get_journal_entry,
    get_trial_balance,
    list_chart_of_accounts,
    list_journal_entries,
)


@pytest.mark.asyncio
async def test_financial_general_ledger_and_double_entry(db: AsyncSession):
    """Test Chart of Accounts creation, journal entries with double-entry validation, and trial balance."""
    # 1. Create Chart of Accounts: Cash (ASSET), Accounts Receivable (ASSET), Tuition Revenue (REVENUE), Salary Expense (EXPENSE)
    cash_acc = await create_chart_of_account(
        payload=ChartOfAccountsCreate(
            account_code="1001",
            account_name="Cash at Bank",
            account_type=AccountType.ASSET,
            campus_id=1,
            initial_balance=10000.0,
        ),
        session=db,
    )
    assert cash_acc.id is not None
    assert cash_acc.balance == 10000.0

    ar_acc = await create_chart_of_account(
        payload=ChartOfAccountsCreate(
            account_code="1002",
            account_name="Accounts Receivable",
            account_type=AccountType.ASSET,
            campus_id=1,
            initial_balance=0.0,
        ),
        session=db,
    )

    rev_acc = await create_chart_of_account(
        payload=ChartOfAccountsCreate(
            account_code="4001",
            account_name="Tuition Fee Revenue",
            account_type=AccountType.REVENUE,
            campus_id=1,
            initial_balance=0.0,
        ),
        session=db,
    )

    exp_acc = await create_chart_of_account(
        payload=ChartOfAccountsCreate(
            account_code="5001",
            account_name="Faculty Salary Expense",
            account_type=AccountType.EXPENSE,
            campus_id=1,
            initial_balance=0.0,
        ),
        session=db,
    )

    accounts = await list_chart_of_accounts(campus_id=1, session=db)
    assert len(accounts) == 4

    # 2. Test Unbalanced Journal Entry: Debit 5000 vs Credit 4000 (Should raise HTTPException 400)
    unbalanced_entry = JournalEntryCreate(
        campus_id=1,
        entry_date=datetime.date(2026, 9, 1),
        reference_no="JE-TEST-UNBALANCED",
        description="Invalid Unbalanced Entry",
        lines=[
            JournalEntryLineCreate(account_id=cash_acc.id, debit_amount=5000.0, credit_amount=0.0),
            JournalEntryLineCreate(account_id=rev_acc.id, debit_amount=0.0, credit_amount=4000.0),
        ],
    )
    with pytest.raises(HTTPException) as exc_info:
        await create_journal_entry(payload=unbalanced_entry, session=db)
    assert exc_info.value.status_code == 400
    assert "Double-entry validation failed" in exc_info.value.detail

    # 3. Post Balanced Entry 1: Fee Collection (Debit Cash 5000, Credit Revenue 5000)
    fee_entry_payload = JournalEntryCreate(
        campus_id=1,
        entry_date=datetime.date(2026, 9, 1),
        reference_no="JE-20260901-001",
        description="Term 1 Fee Inflow",
        lines=[
            JournalEntryLineCreate(account_id=cash_acc.id, debit_amount=5000.0, credit_amount=0.0, description="Cash received"),
            JournalEntryLineCreate(account_id=rev_acc.id, debit_amount=0.0, credit_amount=5000.0, description="Tuition recognized"),
        ],
    )
    entry1 = await create_journal_entry(payload=fee_entry_payload, session=db)
    assert entry1.id is not None
    assert entry1.total_debit == 5000.0
    assert entry1.total_credit == 5000.0
    assert len(entry1.lines) == 2

    # Verify updated balances
    updated_cash = await get_chart_of_account(account_id=cash_acc.id, session=db)
    assert updated_cash.balance == 15000.0  # 10000 initial + 5000 debit

    updated_rev = await get_chart_of_account(account_id=rev_acc.id, session=db)
    assert updated_rev.balance == 5000.0  # Revenue increased by 5000 credit

    # 4. Post Balanced Entry 2: Salary Disbursement (Debit Expense 3000, Credit Cash 3000)
    salary_entry_payload = JournalEntryCreate(
        campus_id=1,
        entry_date=datetime.date(2026, 9, 5),
        description="September Faculty Salary Payout",
        lines=[
            JournalEntryLineCreate(account_id=exp_acc.id, debit_amount=3000.0, credit_amount=0.0, description="Salary expense"),
            JournalEntryLineCreate(account_id=cash_acc.id, debit_amount=0.0, credit_amount=3000.0, description="Disbursed via bank"),
        ],
    )
    entry2 = await create_journal_entry(payload=salary_entry_payload, session=db)
    assert entry2.id is not None
    assert entry2.reference_no.startswith("JE-20260905-")
    assert entry2.total_debit == 3000.0
    assert entry2.total_credit == 3000.0

    # Verify cash decreased by 3000 credit
    updated_cash2 = await get_chart_of_account(account_id=cash_acc.id, session=db)
    assert updated_cash2.balance == 12000.0

    # 5. List and Get Journal Entries
    all_entries = await list_journal_entries(campus_id=1, session=db)
    assert len(all_entries) == 2

    single_entry = await get_journal_entry(entry_id=entry1.id, session=db)
    assert single_entry.reference_no == "JE-20260901-001"
    assert len(single_entry.lines) == 2

    # 6. Trial Balance Verification
    # Cash: 12000 (Debit), Exp: 3000 (Debit) -> Total Debit = 15000
    # Rev: 5000 (Credit) + (Initial Cash equity offset if modeled or asset balance)
    tb = await get_trial_balance(campus_id=1, session=db)
    assert len(tb.items) == 4
    assert tb.total_debit == 15000.0  # 12000 cash + 3000 expense
    assert tb.total_credit == 5000.0  # 5000 revenue
