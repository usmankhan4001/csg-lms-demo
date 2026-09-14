"""Campus isolation across the academic and operations modules.

`require_campus_access` (core/keycloak_auth.py) is weaker than its name
suggests: it reads only path/query params, so a campus_id in the request BODY
is never seen, and it rejects only an EXPLICIT mismatch -- an unscoped request
returned the principal untouched, handing a campus-bound admin org-wide reach
simply by omitting the field.

These tests pin the two shared helpers and the endpoints that use them. The
source-level assertions target the DEPENDENCY/CALL wiring rather than handler
behaviour, because that is where the bug lived: a handler can compute a
perfectly correct answer over the wrong campus's rows.
"""

import inspect
import linecache

import pytest
from fastapi import HTTPException

import src.routers.sms_hr as hr_router
import src.routers.sms_library as library_router
import src.routers.sms_revops as revops_router
import src.routers.sms_timetable as timetable_router
from src.security.school_ownership import (
    assert_campus_allowed,
    resolve_scoped_campus_id,
)


class _P:
    """A resolved principal. Handlers are called directly in these suites, so
    FastAPI's DI never runs and the real dependency default would arrive as an
    unresolved `Depends`."""

    def __init__(self, campus_id=None, superadmin=False, roles=()):
        self.campus_id = campus_id
        self.is_superadmin = superadmin
        self._roles = roles
        self.raw_claims = {"lh_user_id": 1}

    def has_role(self, role):
        return role in self._roles

    def has_any_role(self, wanted):
        return any(r in self._roles for r in wanted)


# --------------------------------------------------------------------------
# The helpers themselves.
# --------------------------------------------------------------------------


def test_omitting_campus_does_not_grant_org_wide_reach():
    """The headline hole: no campus named == every campus, previously."""
    assert resolve_scoped_campus_id(_P(campus_id=2), None) == 2


def test_requesting_another_campus_is_pinned_back():
    assert resolve_scoped_campus_id(_P(campus_id=2), 9) == 2


def test_superadmin_may_operate_org_wide():
    assert resolve_scoped_campus_id(_P(superadmin=True), None) is None
    assert resolve_scoped_campus_id(_P(superadmin=True), 9) == 9


def test_org_level_admin_without_a_campus_is_not_pinned():
    """An admin with no campus of their own is org-level by definition."""
    assert resolve_scoped_campus_id(_P(campus_id=None), 9) == 9


def test_explicit_cross_campus_write_is_refused():
    with pytest.raises(HTTPException) as exc:
        assert_campus_allowed(_P(campus_id=2), 9)
    assert exc.value.status_code == 403


def test_own_campus_write_is_allowed():
    assert_campus_allowed(_P(campus_id=2), 2)
    assert_campus_allowed(_P(campus_id=2), None)
    assert_campus_allowed(_P(superadmin=True), 9)


# --------------------------------------------------------------------------
# Endpoint wiring.
# --------------------------------------------------------------------------


def _body(func) -> str:
    """Source of a handler, read FRESH from disk.

    `inspect.getsource` goes through `linecache`, which caches by filename and
    only re-reads when it thinks the file changed. That made these assertions
    unstable during long runs while the routers were still being edited: the
    same test passed standalone and failed in-suite against stale cached
    lines. Invalidate first so we are always asserting against what is
    actually on disk.
    """
    linecache.checkcache(inspect.getsourcefile(func))
    return inspect.getsource(func)


@pytest.mark.parametrize(
    "module,handler",
    [
        (hr_router, "list_staff_profiles"),
        (library_router, "list_books"),
        (timetable_router, "list_class_periods"),
        (revops_router, "list_leads_endpoint"),
        (revops_router, "get_pipeline_endpoint"),
    ],
)
def test_reads_narrow_to_the_callers_campus(module, handler):
    src = _body(getattr(module, handler))
    assert "resolve_scoped_campus_id" in src, (
        f"{handler} does not narrow by campus, so an unscoped call spans the org."
    )


@pytest.mark.parametrize(
    "module,handler",
    [
        (hr_router, "create_staff_profile"),
        (hr_router, "update_staff_profile"),
        (library_router, "create_book"),
        (library_router, "update_book"),
        (library_router, "delete_book"),
        (timetable_router, "create_class_period"),
        (revops_router, "create_lead_endpoint"),
    ],
)
def test_writes_naming_a_campus_fail_loudly(module, handler):
    src = _body(getattr(module, handler))
    assert "assert_campus_allowed" in src, (
        f"{handler} accepts a campus without checking the caller is entitled to it."
    )


def test_record_moving_writes_check_both_directions():
    """A transfer breaches isolation twice: the record edited, and where it
    lands. Guarding only one still lets a campus-bound admin pull another
    campus's record across, or push their own out of sight."""
    for module, handler in ((hr_router, "update_staff_profile"), (library_router, "update_book")):
        src = _body(getattr(module, handler))
        assert src.count("assert_campus_allowed") >= 2, f"{handler} guards only one direction"


def test_overdue_fines_are_scoped_to_one_campus():
    """Unscoped, this levied fines on overdue families at every campus."""
    src = _body(library_router.calculate_overdue_fines_endpoint)
    assert "campus_id=resolve_scoped_campus_id" in src


# --------------------------------------------------------------------------
# Discrimination. Without this the file could pass vacuously.
# --------------------------------------------------------------------------


def test_the_assertions_discriminate():
    """Run the same checks against endpoints deliberately left unscoped.

    `get_book` and `list_loans` have no campus narrowing, by design -- they are
    single-record / loan-desk reads. If the assertions above were blind, these
    would pass too.
    """
    src = _body(library_router.get_book)
    with pytest.raises(AssertionError):
        assert "resolve_scoped_campus_id" in src, "would be a false pass"

    src = _body(library_router.list_loans)
    with pytest.raises(AssertionError):
        assert "assert_campus_allowed" in src, "would be a false pass"
