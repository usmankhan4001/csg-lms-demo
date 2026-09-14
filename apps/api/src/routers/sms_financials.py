from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.events.database import get_db_session
from src.core.keycloak_auth import (
    KeycloakUserPrincipal,
    get_current_user_principal,
    require_roles,
)
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
from src.security.features_utils.dependencies import require_sms_financials_feature
from src.security.school_ownership import (
    assert_campus_allowed,
    resolve_scoped_campus_id,
)
from src.services.sms.financials import (
    reverse_journal_entry,
    generate_trial_balance,
    validate_and_create_journal_entry,
)

# Writing to the general ledger is bookkeeping work: a STAFF bookkeeper does
# it daily, so STAFF is included here (unlike payroll, where STAFF would be
# setting colleagues' pay). TEACHER/STUDENT/PARENT have no business posting to
# the ledger at all.
_LEDGER = ["SUPER_ADMIN", "SCHOOL_ADMIN", "STAFF"]

# Reversal is the ONE operation that negates a posted record in a ledger that
# is otherwise append-only for audit integrity (the router exposes no
# PATCH/PUT/DELETE). Segregation of duties: a bookkeeper who mis-posts must
# escalate to an admin rather than quietly unwinding their own entry.
_LEDGER_ADMIN = ["SUPER_ADMIN", "SCHOOL_ADMIN"]

def _scoped(principal: KeycloakUserPrincipal, campus_id) -> Optional[int]:
    """Effective campus for a ledger READ.

    Reads NARROW rather than fail: an unscoped request returns the caller's own
    campus instead of the whole org, which is almost always what was meant and
    never leaks another campus's books. `campus_id` is normalised first because
    a direct handler call passes FastAPI's unresolved `Query(...)` default
    rather than None -- the same reason this module already guards with
    `isinstance(campus_id, int)`.
    """
    requested = campus_id if type(campus_id) is int else None
    return resolve_scoped_campus_id(principal, requested)


router = APIRouter(dependencies=[Depends(require_sms_financials_feature)])


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
    principal: KeycloakUserPrincipal = Depends(require_roles(_LEDGER)),
) -> ChartOfAccountsRead:
    # Fail LOUDLY on an explicit cross-campus account, then pin an omitted
    # campus to the caller's own: without the second step a campus-bound admin
    # could create an ORG-LEVEL (campus_id=None) account, which every campus
    # then sees in its trial balance.
    assert_campus_allowed(principal, payload.campus_id)
    scoped_campus_id = resolve_scoped_campus_id(principal, payload.campus_id)

    account = ChartOfAccounts(
        account_code=payload.account_code,
        account_name=payload.account_name,
        account_type=payload.account_type,
        campus_id=scoped_campus_id,
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
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> List[ChartOfAccountsRead]:
    query = select(ChartOfAccounts)
    scoped_campus_id = _scoped(principal, campus_id)
    if scoped_campus_id is not None:
        query = query.where(ChartOfAccounts.campus_id == scoped_campus_id)
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
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> ChartOfAccountsRead:
    stmt = select(ChartOfAccounts).where(ChartOfAccounts.id == account_id)
    account = (await session.execute(stmt)).scalar_one_or_none()
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Account with ID {account_id} not found.",
        )
    assert_campus_allowed(principal, account.campus_id)
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
    principal: KeycloakUserPrincipal = Depends(require_roles(_LEDGER)),
) -> JournalEntryRead:
    # Same two-step as accounts: an entry naming another campus is refused,
    # and an omitted campus lands on the caller's own rather than org-wide.
    assert_campus_allowed(principal, payload.campus_id)
    scoped_payload = payload.model_copy(
        update={"campus_id": resolve_scoped_campus_id(principal, payload.campus_id)}
    )
    entry = await validate_and_create_journal_entry(session=session, payload=scoped_payload)

    # Fetch lines to populate response
    lines_stmt = select(JournalEntryLine).where(JournalEntryLine.entry_id == entry.id)
    lines = (await session.execute(lines_stmt)).scalars().all()

    entry_read = JournalEntryRead.model_validate(entry)
    entry_read.lines = [JournalEntryLineRead.model_validate(ln) for ln in lines]
    return entry_read


@router.post(
    "/journal-entries/{entry_id}/reverse",
    response_model=JournalEntryRead,
    status_code=status.HTTP_201_CREATED,
    summary="Reverse a Posted Journal Entry",
    description=(
        "Posts a NEW entry that exactly negates the given one and links back "
        "to it, which is how a mis-posting is corrected in an append-only "
        "ledger — nothing is ever edited or deleted. An entry can be reversed "
        "at most once, and a reversal cannot itself be reversed."
    ),
    responses={
        400: {"description": "Already reversed, or the entry is itself a reversal"},
        404: {"description": "Journal entry not found"},
    },
)
async def reverse_journal_entry_endpoint(
    entry_id: int,
    reason: Optional[str] = Query(None, description="Why this entry is being reversed"),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_LEDGER_ADMIN)),
) -> JournalEntryRead:
    # The service resolves the entry by id alone. Reversal negates a posted
    # record, so a cross-campus attempt fails loudly rather than being
    # redirected. A missing entry is left to the service's own 404.
    target = (
        await session.execute(select(JournalEntry).where(JournalEntry.id == entry_id))
    ).scalar_one_or_none()
    if target is not None:
        assert_campus_allowed(principal, target.campus_id)

    reversal = await reverse_journal_entry(session=session, entry_id=entry_id, reason=reason)

    lines_stmt = select(JournalEntryLine).where(JournalEntryLine.entry_id == reversal.id)
    lines = (await session.execute(lines_stmt)).scalars().all()

    entry_read = JournalEntryRead.model_validate(reversal)
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
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> List[JournalEntryRead]:
    query = select(JournalEntry)
    scoped_campus_id = _scoped(principal, campus_id)
    if scoped_campus_id is not None:
        query = query.where(JournalEntry.campus_id == scoped_campus_id)

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
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> JournalEntryRead:
    stmt = select(JournalEntry).where(JournalEntry.id == entry_id)
    entry = (await session.execute(stmt)).scalar_one_or_none()
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Journal entry with ID {entry_id} not found.",
        )
    assert_campus_allowed(principal, entry.campus_id)

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
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> TrialBalanceResponse:
    # A trial balance spanning every campus is exactly the cross-campus read
    # this narrowing exists to prevent.
    return await generate_trial_balance(
        session=session, campus_id=_scoped(principal, campus_id)
    )
