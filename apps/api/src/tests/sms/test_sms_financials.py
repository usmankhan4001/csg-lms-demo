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
    reverse_journal_entry_endpoint,
)


def _ledger_principal(campus_id=None):
    """A resolved SCHOOL_ADMIN principal for direct handler calls."""
    from types import SimpleNamespace

    return SimpleNamespace(
        is_superadmin=False,
        campus_id=campus_id,
        has_any_role=lambda wanted: "SCHOOL_ADMIN" in wanted,
        has_role=lambda r: r == "SCHOOL_ADMIN",
        raw_claims={"lh_user_id": 1},
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
        session=db, principal=_ledger_principal())
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
        session=db, principal=_ledger_principal())

    rev_acc = await create_chart_of_account(
        payload=ChartOfAccountsCreate(
            account_code="4001",
            account_name="Tuition Fee Revenue",
            account_type=AccountType.REVENUE,
            campus_id=1,
            initial_balance=0.0,
        ),
        session=db, principal=_ledger_principal())

    exp_acc = await create_chart_of_account(
        payload=ChartOfAccountsCreate(
            account_code="5001",
            account_name="Faculty Salary Expense",
            account_type=AccountType.EXPENSE,
            campus_id=1,
            initial_balance=0.0,
        ),
        session=db, principal=_ledger_principal())

    accounts = await list_chart_of_accounts(campus_id=1, session=db, principal=_ledger_principal())
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
        await create_journal_entry(payload=unbalanced_entry, session=db, principal=_ledger_principal())
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
    entry1 = await create_journal_entry(payload=fee_entry_payload, session=db, principal=_ledger_principal())
    assert entry1.id is not None
    assert entry1.total_debit == 5000.0
    assert entry1.total_credit == 5000.0
    assert len(entry1.lines) == 2

    # Verify updated balances
    updated_cash = await get_chart_of_account(account_id=cash_acc.id, session=db, principal=_ledger_principal())
    assert updated_cash.balance == 15000.0  # 10000 initial + 5000 debit

    updated_rev = await get_chart_of_account(account_id=rev_acc.id, session=db, principal=_ledger_principal())
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
    entry2 = await create_journal_entry(payload=salary_entry_payload, session=db, principal=_ledger_principal())
    assert entry2.id is not None
    assert entry2.reference_no.startswith("JE-20260905-")
    assert entry2.total_debit == 3000.0
    assert entry2.total_credit == 3000.0

    # Verify cash decreased by 3000 credit
    updated_cash2 = await get_chart_of_account(account_id=cash_acc.id, session=db, principal=_ledger_principal())
    assert updated_cash2.balance == 12000.0

    # 5. List and Get Journal Entries
    all_entries = await list_journal_entries(campus_id=1, session=db, principal=_ledger_principal())
    assert len(all_entries) == 2

    single_entry = await get_journal_entry(entry_id=entry1.id, session=db, principal=_ledger_principal())
    assert single_entry.reference_no == "JE-20260901-001"
    assert len(single_entry.lines) == 2

    # 6. Trial Balance Verification
    # Cash: 12000 (Debit), Exp: 3000 (Debit) -> Total Debit = 15000
    # Rev: 5000 (Credit) + (Initial Cash equity offset if modeled or asset balance)
    tb = await get_trial_balance(campus_id=1, session=db, principal=_ledger_principal())
    assert len(tb.items) == 4
    assert tb.total_debit == 15000.0  # 12000 cash + 3000 expense
    assert tb.total_credit == 5000.0  # 5000 revenue


# ── Ledger Reversals (M09) ──
#
# These call the router coroutine directly rather than over HTTP, so FastAPI
# never resolves the `reason` Query() default — it must be passed explicitly
# or the raw Query object leaks into the entry description.

async def _seed_accounts(db: AsyncSession, code_prefix: str):
    """Cash (ASSET) + Tuition Revenue (REVENUE), the minimum pair for a
    balanced entry."""
    cash = await create_chart_of_account(
        payload=ChartOfAccountsCreate(
            account_code=f"{code_prefix}1",
            account_name="Cash",
            account_type=AccountType.ASSET,
        ),
        session=db, principal=_ledger_principal())
    revenue = await create_chart_of_account(
        payload=ChartOfAccountsCreate(
            account_code=f"{code_prefix}2",
            account_name="Tuition Revenue",
            account_type=AccountType.REVENUE,
        ),
        session=db, principal=_ledger_principal())
    return cash, revenue


async def _post_entry(db: AsyncSession, cash_id: int, revenue_id: int, amount: float = 500.0):
    return await create_journal_entry(
        payload=JournalEntryCreate(
            entry_date=datetime.date(2026, 5, 1),
            description="Tuition collected",
            lines=[
                JournalEntryLineCreate(account_id=cash_id, debit_amount=amount, credit_amount=0.0),
                JournalEntryLineCreate(account_id=revenue_id, debit_amount=0.0, credit_amount=amount),
            ],
        ),
        session=db, principal=_ledger_principal())


@pytest.mark.asyncio
async def test_reversal_restores_account_balances_exactly(db: AsyncSession):
    """The whole point of a reversal: balances return to their pre-entry state."""
    cash, revenue = await _seed_accounts(db, "90")
    cash_before = (await get_chart_of_account(account_id=cash.id, session=db, principal=_ledger_principal())).balance
    rev_before = (await get_chart_of_account(account_id=revenue.id, session=db, principal=_ledger_principal())).balance

    entry = await _post_entry(db, cash.id, revenue.id, amount=500.0)
    assert (await get_chart_of_account(account_id=cash.id, session=db, principal=_ledger_principal())).balance == cash_before + 500.0
    assert (await get_chart_of_account(account_id=revenue.id, session=db, principal=_ledger_principal())).balance == rev_before + 500.0

    reversal = await reverse_journal_entry_endpoint(
        entry_id=entry.id, reason="Posted to the wrong term", session=db, principal=_ledger_principal())

    assert reversal.reverses_entry_id == entry.id
    assert reversal.reference_no.startswith(f"REV-{entry.reference_no}")
    # Debits and credits are swapped, so the reversal is itself balanced.
    assert reversal.total_debit == entry.total_credit
    assert reversal.total_credit == entry.total_debit

    assert (await get_chart_of_account(account_id=cash.id, session=db, principal=_ledger_principal())).balance == cash_before
    assert (await get_chart_of_account(account_id=revenue.id, session=db, principal=_ledger_principal())).balance == rev_before


@pytest.mark.asyncio
async def test_entry_cannot_be_reversed_twice(db: AsyncSession):
    """Double-reversing would double-count the correction."""
    cash, revenue = await _seed_accounts(db, "91")
    entry = await _post_entry(db, cash.id, revenue.id)
    await reverse_journal_entry_endpoint(entry_id=entry.id, reason=None, session=db, principal=_ledger_principal())

    with pytest.raises(HTTPException) as exc:
        await reverse_journal_entry_endpoint(entry_id=entry.id, reason=None, session=db, principal=_ledger_principal())
    assert exc.value.status_code == 400
    assert "already reversed" in str(exc.value.detail).lower()


@pytest.mark.asyncio
async def test_a_reversal_cannot_itself_be_reversed(db: AsyncSession):
    """Reversing a reversal would silently re-apply the original mistake."""
    cash, revenue = await _seed_accounts(db, "92")
    entry = await _post_entry(db, cash.id, revenue.id)
    reversal = await reverse_journal_entry_endpoint(entry_id=entry.id, reason=None, session=db, principal=_ledger_principal())

    with pytest.raises(HTTPException) as exc:
        await reverse_journal_entry_endpoint(entry_id=reversal.id, reason=None, session=db, principal=_ledger_principal())
    assert exc.value.status_code == 400
    assert "is itself a reversal" in str(exc.value.detail).lower()


@pytest.mark.asyncio
async def test_reversing_unknown_entry_is_404(db: AsyncSession):
    with pytest.raises(HTTPException) as exc:
        await reverse_journal_entry_endpoint(entry_id=987654, reason=None, session=db, principal=_ledger_principal())
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_reversal_keeps_trial_balance_balanced(db: AsyncSession):
    """A reversal must never break the double-entry invariant."""
    cash, revenue = await _seed_accounts(db, "93")
    entry = await _post_entry(db, cash.id, revenue.id, amount=750.0)
    await reverse_journal_entry_endpoint(entry_id=entry.id, reason=None, session=db, principal=_ledger_principal())

    tb = await get_trial_balance(session=db, principal=_ledger_principal())
    assert abs(tb.total_debit - tb.total_credit) < 0.01
    assert tb.is_balanced is True
