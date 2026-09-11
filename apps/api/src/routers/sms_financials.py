from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.events.database import get_db_session
from src.db.sms_financials import (
    AccountType,
    ChartOfAccounts,
    JournalEntry,
    JournalEntryLine,
)
from src.schemas.sms_financials import (
    ChartOfAccountsCreate,
    ChartOfAccountsRead,
    JournalEntryCreate,
    JournalEntryLineRead,
    JournalEntryRead,
    TrialBalanceResponse,
)
from src.services.sms.financials import (
    generate_trial_balance,
    validate_and_create_journal_entry,
)

router = APIRouter()


# ── Chart of Accounts ──

@router.post(
    "/accounts",
    response_model=ChartOfAccountsRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create Chart of Account",
)
async def create_chart_of_account(
    payload: ChartOfAccountsCreate,
    session: AsyncSession = Depends(get_db_session),
) -> ChartOfAccountsRead:
    account = ChartOfAccounts(
        account_code=payload.account_code,
        account_name=payload.account_name,
        account_type=payload.account_type,
        campus_id=payload.campus_id,
        balance=payload.initial_balance or 0.0,
        is_active=payload.is_active,
        description=payload.description,
    )
    session.add(account)
    await session.commit()
    await session.refresh(account)
    return ChartOfAccountsRead.model_validate(account)


@router.get(
    "/accounts",
    response_model=List[ChartOfAccountsRead],
    summary="List Chart of Accounts",
)
async def list_chart_of_accounts(
    campus_id: Optional[int] = Query(None, description="Filter by Campus ID"),
    account_type: Optional[AccountType] = Query(None, description="Filter by Account Type"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    session: AsyncSession = Depends(get_db_session),
) -> List[ChartOfAccountsRead]:
    query = select(ChartOfAccounts)
    if isinstance(campus_id, int):
        query = query.where(ChartOfAccounts.campus_id == campus_id)
    if isinstance(account_type, AccountType) or (isinstance(account_type, str) and not hasattr(account_type, "default")):
        query = query.where(ChartOfAccounts.account_type == account_type)
    if isinstance(is_active, bool):
        query = query.where(ChartOfAccounts.is_active == is_active)

    query = query.order_by(ChartOfAccounts.account_code)
    result = await session.execute(query)
    accounts = result.scalars().all()
    return [ChartOfAccountsRead.model_validate(acc) for acc in accounts]


@router.get(
    "/accounts/{account_id}",
    response_model=ChartOfAccountsRead,
    summary="Get Account by ID",
)
async def get_chart_of_account(
    account_id: int,
    session: AsyncSession = Depends(get_db_session),
) -> ChartOfAccountsRead:
    stmt = select(ChartOfAccounts).where(ChartOfAccounts.id == account_id)
    account = (await session.execute(stmt)).scalar_one_or_none()
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Account with ID {account_id} not found.",
        )
    return ChartOfAccountsRead.model_validate(account)


# ── Journal Entries ──

@router.post(
    "/journal-entries",
    response_model=JournalEntryRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create & Post Journal Entry with Double-Entry Validation",
)
async def create_journal_entry(
    payload: JournalEntryCreate,
    session: AsyncSession = Depends(get_db_session),
) -> JournalEntryRead:
    entry = await validate_and_create_journal_entry(session=session, payload=payload)

    # Fetch lines to populate response
    lines_stmt = select(JournalEntryLine).where(JournalEntryLine.entry_id == entry.id)
    lines = (await session.execute(lines_stmt)).scalars().all()

    entry_read = JournalEntryRead.model_validate(entry)
    entry_read.lines = [JournalEntryLineRead.model_validate(ln) for ln in lines]
    return entry_read


@router.get(
    "/journal-entries",
    response_model=List[JournalEntryRead],
    summary="List Journal Entries",
)
async def list_journal_entries(
    campus_id: Optional[int] = Query(None, description="Filter by Campus ID"),
    session: AsyncSession = Depends(get_db_session),
) -> List[JournalEntryRead]:
    query = select(JournalEntry)
    if isinstance(campus_id, int):
        query = query.where(JournalEntry.campus_id == campus_id)

    query = query.order_by(JournalEntry.entry_date.desc(), JournalEntry.id.desc())
    result = await session.execute(query)
    entries = result.scalars().all()

    output: List[JournalEntryRead] = []
    for entry in entries:
        lines_stmt = select(JournalEntryLine).where(JournalEntryLine.entry_id == entry.id)
        lines = (await session.execute(lines_stmt)).scalars().all()
        read_obj = JournalEntryRead.model_validate(entry)
        read_obj.lines = [JournalEntryLineRead.model_validate(ln) for ln in lines]
        output.append(read_obj)

    return output


@router.get(
    "/journal-entries/{entry_id}",
    response_model=JournalEntryRead,
    summary="Get Journal Entry by ID",
)
async def get_journal_entry(
    entry_id: int,
    session: AsyncSession = Depends(get_db_session),
) -> JournalEntryRead:
    stmt = select(JournalEntry).where(JournalEntry.id == entry_id)
    entry = (await session.execute(stmt)).scalar_one_or_none()
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Journal entry with ID {entry_id} not found.",
        )

    lines_stmt = select(JournalEntryLine).where(JournalEntryLine.entry_id == entry.id)
    lines = (await session.execute(lines_stmt)).scalars().all()
    read_obj = JournalEntryRead.model_validate(entry)
    read_obj.lines = [JournalEntryLineRead.model_validate(ln) for ln in lines]
    return read_obj


# ── Trial Balance ──

@router.get(
    "/trial-balance",
    response_model=TrialBalanceResponse,
    summary="Get Trial Balance",
)
async def get_trial_balance(
    campus_id: Optional[int] = Query(None, description="Filter by Campus ID"),
    session: AsyncSession = Depends(get_db_session),
) -> TrialBalanceResponse:
    c_id = campus_id if isinstance(campus_id, int) else None
    return await generate_trial_balance(session=session, campus_id=c_id)
