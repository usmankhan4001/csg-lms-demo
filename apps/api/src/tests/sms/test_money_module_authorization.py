"""Authorization on the payroll and general-ledger write endpoints.

Every write in both routers was gated only by `get_current_user_principal`,
which admits ANY authenticated user, and none of the service functions behind
them take a principal at all. So a signed-in student could set staff salary
structures, generate salary slips, record salary disbursements, create ledger
accounts, post journal entries, and reverse posted entries.

These assert the DEPENDENCY WIRING rather than going over HTTP, because the
bug lives in the dependency and not in the handler body: a handler can be
perfectly correct and still be reachable by the wrong person.

`test_the_assertion_discriminates` is the guard against this whole file
passing vacuously -- it runs the same check against a handler that is still
deliberately open and requires it to FAIL.
"""

import inspect

import pytest

import src.routers.sms_financials as financials_router
import src.routers.sms_payroll as payroll_router


def _dependency_source(func) -> str:
    """Flatten a route handler's dependency defaults into inspectable text."""
    sig = inspect.signature(func)
    return " ".join(repr(p.default) for p in sig.parameters.values())


def _assert_role_gated(handler, label: str) -> None:
    source = _dependency_source(handler)
    assert "get_current_user_principal" not in source, (
        f"{label} is gated by get_current_user_principal, which admits ANY "
        "authenticated user -- including a student."
    )
    assert "require_roles" in source, f"{label} must be role-gated."


# ── Payroll ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "handler_name",
    [
        "create_or_update_salary_structure",
        "generate_salary_slips_batch",
        "record_salary_payment",
    ],
)
def test_payroll_writes_are_role_gated(handler_name):
    _assert_role_gated(getattr(payroll_router, handler_name), handler_name)


def test_payroll_excludes_generic_staff_to_prevent_self_dealing():
    """Narrower than fees' _BURSAR on purpose.

    A back-office STAFF member with payroll write access could raise their own
    salary structure and then mark their own slip paid.
    """
    roles = payroll_router._PAYROLL_ADMIN
    for excluded in ("STAFF", "TEACHER", "STUDENT", "PARENT", "PSYCHOLOGIST"):
        assert excluded not in roles, f"{excluded} must not be able to write payroll"
    assert "SCHOOL_ADMIN" in roles


# ── General ledger ─────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "handler_name",
    ["create_chart_of_account", "create_journal_entry", "reverse_journal_entry_endpoint"],
)
def test_ledger_writes_are_role_gated(handler_name):
    _assert_role_gated(getattr(financials_router, handler_name), handler_name)


def test_ledger_writes_exclude_families_and_teachers():
    for excluded in ("TEACHER", "STUDENT", "PARENT"):
        assert excluded not in financials_router._LEDGER
    assert "STAFF" in financials_router._LEDGER, "a bookkeeper posts entries daily"


def test_reversal_is_gated_more_narrowly_than_posting():
    """The ledger is append-only for audit integrity; reversal is the one
    operation that negates a posted record, so it requires an admin."""
    assert "STAFF" not in financials_router._LEDGER_ADMIN
    assert set(financials_router._LEDGER_ADMIN) < set(financials_router._LEDGER)


def test_reversal_handler_uses_the_narrow_constant():
    source = _dependency_source(financials_router.reverse_journal_entry_endpoint)
    assert "_LEDGER_ADMIN" in source or "require_roles" in source


# ── The guard against vacuous passes ───────────────────────────────────────

def test_the_assertion_discriminates():
    """Proof this file can fail.

    `list_journal_entries` is a READ and is still deliberately gated only by
    `get_current_user_principal`. The same assertion used above must reject
    it; if this stops raising, _assert_role_gated has gone blind.
    """
    with pytest.raises(AssertionError):
        _assert_role_gated(financials_router.list_journal_entries, "list_journal_entries")


# ---------------------------------------------------------------------------
# Salary READS. The writes were gated first, but every GET stayed open to any
# authenticated user while taking an arbitrary `staff_id` -- so a signed-in
# student could walk the id range and read every employee's salary, allowances
# and deductions. Pay is among the most sensitive data a school holds.
# ---------------------------------------------------------------------------

import pytest
from fastapi import HTTPException

from src.routers.sms_payroll import _assert_may_read_salary


class _P:
    def __init__(self, user_id=None, roles=(), superadmin=False):
        self.is_superadmin = superadmin
        self._roles = roles
        self.raw_claims = {"lh_user_id": user_id} if user_id is not None else {}

    def has_any_role(self, wanted):
        return any(r in self._roles for r in wanted)


@pytest.mark.asyncio
async def test_student_cannot_list_all_payroll(db):
    """A bare listing has no 'filtered to me' reading -- it is admin-only."""
    with pytest.raises(HTTPException) as exc:
        await _assert_may_read_salary(_P(user_id=42, roles=("STUDENT",)), None, db)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_student_cannot_read_another_persons_salary(db):
    with pytest.raises(HTTPException) as exc:
        await _assert_may_read_salary(_P(user_id=42, roles=("STUDENT",)), 1, db)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_hr_admin_may_read_payroll(db):
    await _assert_may_read_salary(_P(user_id=3, roles=("SCHOOL_ADMIN",)), None, db)
    await _assert_may_read_salary(_P(user_id=3, roles=("SCHOOL_ADMIN",)), 1, db)


@pytest.mark.asyncio
async def test_a_caller_with_no_identity_is_refused(db):
    """Fail closed: no resolvable user id must not read as 'it's mine'."""
    with pytest.raises(HTTPException):
        await _assert_may_read_salary(_P(user_id=None, roles=("TEACHER",)), 1, db)
