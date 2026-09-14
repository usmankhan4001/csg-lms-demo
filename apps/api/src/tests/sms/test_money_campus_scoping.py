"""Campus isolation on the money modules.

Role was enforced on these endpoints; SCOPE was not. `require_campus_access`
(core/keycloak_auth.py) is weaker than its name suggests in two ways that
mattered here:

  1. It reads only `request.path_params` and `request.query_params`, so a
     `campus_id` carried in the request BODY is never checked at all.
  2. It rejects only an EXPLICIT mismatch. An unscoped request -- no campus
     anywhere -- returned the principal untouched, so a campus-bound admin got
     org-wide reach simply by omitting the field.

The headline consequence: `generate_batch_salary_slips` filters on
`payload.campus_id`, so omitting it generated salary slips for every active
staff member at every campus in the organisation.

The behavioural test below proves the router guard is what prevents that, by
running the same assertion against the SERVICE called directly -- which still
crosses campuses, exactly as the router did before the fix.
"""

import datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_hr import ContractType, StaffProfile
from src.routers.sms_financials import create_journal_entry
from src.routers.sms_payroll import generate_salary_slips_batch
from src.schemas.sms_payroll import BatchSalarySlipGenerateRequest
from src.services.sms.payroll import generate_batch_salary_slips


def _principal(campus_id=None, superadmin=False, role="SCHOOL_ADMIN"):
    return SimpleNamespace(
        is_superadmin=superadmin,
        campus_id=campus_id,
        has_any_role=lambda wanted: role in wanted,
        has_role=lambda r: r == role,
        raw_claims={"lh_user_id": 1},
    )


async def _staff_at(db: AsyncSession, campus_id: int, code: str) -> StaffProfile:
    staff = StaffProfile(
        employee_code=code,
        full_name=f"Staff {code}",
        designation="Teacher",
        department="Science",
        joining_date=datetime.date(2026, 1, 1),
        contract_type=ContractType.PERMANENT,
        basic_salary=30000.0,
        campus_id=campus_id,
        is_active=True,
    )
    db.add(staff)
    await db.commit()
    await db.refresh(staff)
    return staff


# ---------------------------------------------------------------------------
# THE HEADLINE, tested behaviourally.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_omitted_campus_does_not_bill_the_whole_org(db: AsyncSession):
    """A campus-bound admin omitting campus_id must not reach other campuses."""
    await _staff_at(db, campus_id=2, code="C2-A")
    await _staff_at(db, campus_id=9, code="C9-A")

    slips = await generate_salary_slips_batch(
        payload=BatchSalarySlipGenerateRequest(month=9, year=2026),  # NO campus_id
        session=db,
        principal=_principal(campus_id=2),
    )

    campuses = set()
    for slip in slips:
        staff = await db.get(StaffProfile, slip.staff_id)
        campuses.add(staff.campus_id)
    assert campuses == {2}, f"leaked into campuses {campuses - {2}}"


@pytest.mark.asyncio
async def test_the_service_alone_still_crosses_campuses(db: AsyncSession):
    """Discrimination control.

    The service is deliberately unscoped -- it is the router guard that closes
    the hole. If this ever stops crossing campuses the test above has become
    vacuous and would pass whether or not the guard exists.
    """
    await _staff_at(db, campus_id=2, code="X2-A")
    await _staff_at(db, campus_id=9, code="X9-A")

    slips = await generate_batch_salary_slips(
        session=db,
        payload=BatchSalarySlipGenerateRequest(month=11, year=2026),  # NO campus_id
    )

    campuses = set()
    for slip in slips:
        staff = await db.get(StaffProfile, slip.staff_id)
        campuses.add(staff.campus_id)
    assert campuses == {2, 9}, "service is no longer the unscoped control"


@pytest.mark.asyncio
async def test_explicit_cross_campus_batch_is_refused(db: AsyncSession):
    """A write that NAMES a campus fails loudly rather than being redirected."""
    await _staff_at(db, campus_id=9, code="R9-A")
    with pytest.raises(HTTPException) as exc:
        await generate_salary_slips_batch(
            payload=BatchSalarySlipGenerateRequest(month=9, year=2026, campus_id=9),
            session=db,
            principal=_principal(campus_id=2),
        )
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_org_level_admin_may_still_run_every_campus(db: AsyncSession):
    """The fix must not break a genuinely org-wide payroll run."""
    await _staff_at(db, campus_id=2, code="O2-A")
    await _staff_at(db, campus_id=9, code="O9-A")

    slips = await generate_salary_slips_batch(
        payload=BatchSalarySlipGenerateRequest(month=10, year=2026),
        session=db,
        principal=_principal(campus_id=None),
    )
    campuses = set()
    for slip in slips:
        staff = await db.get(StaffProfile, slip.staff_id)
        campuses.add(staff.campus_id)
    assert campuses == {2, 9}


# ---------------------------------------------------------------------------
# General ledger. Accounts and entries both carry an OPTIONAL campus_id, so an
# omitted campus previously created an ORG-LEVEL record that every campus then
# saw in its own trial balance.
# ---------------------------------------------------------------------------

from src.db.sms_financials import AccountType, ChartOfAccounts, JournalEntry
from src.routers.sms_financials import (
    create_chart_of_account,
    get_trial_balance,
    list_journal_entries,
)
from src.schemas.sms_financials import (
    ChartOfAccountsCreate,
    JournalEntryCreate,
    JournalEntryLineCreate,
)


@pytest.mark.asyncio
async def test_omitted_campus_account_is_pinned_not_org_level(db: AsyncSession):
    account = await create_chart_of_account(
        payload=ChartOfAccountsCreate(
            account_code="SCOPE-1",
            account_name="Scoped Cash",
            account_type=AccountType.ASSET,
        ),  # NO campus_id
        session=db,
        principal=_principal(campus_id=2),
    )
    assert account.campus_id == 2, "an omitted campus must not create an org-level account"


@pytest.mark.asyncio
async def test_explicit_cross_campus_account_is_refused(db: AsyncSession):
    with pytest.raises(HTTPException) as exc:
        await create_chart_of_account(
            payload=ChartOfAccountsCreate(
                account_code="SCOPE-2",
                account_name="Other Campus Cash",
                account_type=AccountType.ASSET,
                campus_id=9,
            ),
            session=db,
            principal=_principal(campus_id=2),
        )
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_explicit_cross_campus_journal_entry_is_refused(db: AsyncSession):
    with pytest.raises(HTTPException) as exc:
        await create_journal_entry(
            payload=JournalEntryCreate(
                campus_id=9,
                entry_date=datetime.date(2026, 9, 1),
                lines=[
                    JournalEntryLineCreate(account_id=1, debit_amount=100.0),
                    JournalEntryLineCreate(account_id=2, credit_amount=100.0),
                ],
            ),
            session=db,
            principal=_principal(campus_id=2),
        )
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_ledger_reads_narrow_to_the_callers_campus(db: AsyncSession):
    """Reads NARROW rather than 403 -- asking broadly returns what you may see."""
    db.add(JournalEntry(
        campus_id=2, entry_date=datetime.date(2026, 9, 1), reference_no="JE-C2",
        total_debit=10.0, total_credit=10.0,
    ))
    db.add(JournalEntry(
        campus_id=9, entry_date=datetime.date(2026, 9, 1), reference_no="JE-C9",
        total_debit=10.0, total_credit=10.0,
    ))
    await db.commit()

    entries = await list_journal_entries(
        campus_id=None, session=db, principal=_principal(campus_id=2)
    )
    assert entries, "narrowing must not empty a legitimate read"
    assert {e.campus_id for e in entries} == {2}


@pytest.mark.asyncio
async def test_trial_balance_does_not_span_campuses(db: AsyncSession):
    db.add(ChartOfAccounts(
        account_code="TB-C2", account_name="C2 Asset",
        account_type=AccountType.ASSET, campus_id=2, balance=500.0, is_active=True,
    ))
    db.add(ChartOfAccounts(
        account_code="TB-C9", account_name="C9 Asset",
        account_type=AccountType.ASSET, campus_id=9, balance=900.0, is_active=True,
    ))
    await db.commit()

    tb = await get_trial_balance(
        campus_id=None, session=db, principal=_principal(campus_id=2)
    )
    codes = {item.account_code for item in tb.items}
    assert "TB-C2" in codes
    assert "TB-C9" not in codes, "trial balance leaked another campus's books"
