"""Write endpoints across HR, Library, Timetable and RevOps must authorize.

An audit found 31 write endpoints that accepted a `principal` parameter purely
to force authentication and then never authorized at all. Any signed-in user --
a student, a parent -- could create or edit staff records (which carry
`basic_salary`), approve staff leave, delete library books, rewrite the
timetable, and edit admissions leads including the consent flag that gates
outbound marketing.

These assert the DEPENDENCY WIRING rather than going over HTTP, because the
bug was in the dependency, not in the handler body: a handler can be perfectly
correct and still be reachable by the wrong person. `test_the_assertion_
discriminates` pins that this style of check actually fails on an un-gated
handler, so the suite cannot pass vacuously.
"""

import inspect

import pytest

import src.routers.sms_hr as hr_router
import src.routers.sms_library as library_router
import src.routers.sms_revops as revops_router
import src.routers.sms_timetable as timetable_router


def _dependency_source(func) -> str:
    """Flatten a route handler's dependency defaults into inspectable text."""
    sig = inspect.signature(func)
    return " ".join(repr(p.default) for p in sig.parameters.values())


def _assert_role_gated(module, handler_name: str) -> None:
    handler = getattr(module, handler_name)
    source = _dependency_source(handler)
    assert "get_current_user_principal" not in source, (
        f"{handler_name} is gated by get_current_user_principal, which admits "
        "ANY authenticated user."
    )
    assert "require_roles" in source or "_role_c" in source, (
        f"{handler_name} must be role-gated."
    )


@pytest.mark.parametrize(
    "handler_name",
    ["create_staff_profile", "update_staff_profile", "apply_staff_leave", "update_leave_status"],
)
def test_hr_writes_are_role_gated(handler_name):
    _assert_role_gated(hr_router, handler_name)


@pytest.mark.parametrize(
    "handler_name",
    ["create_book", "update_book", "delete_book", "borrow_book", "return_book",
     "calculate_overdue_fines_endpoint"],
)
def test_library_writes_are_role_gated(handler_name):
    _assert_role_gated(library_router, handler_name)


@pytest.mark.parametrize(
    "handler_name",
    ["create_class_period", "create_timetable_schedule", "check_clashes_endpoint",
     "create_substitution_endpoint", "cancel_substitution_endpoint"],
)
def test_timetable_writes_are_role_gated(handler_name):
    _assert_role_gated(timetable_router, handler_name)


@pytest.mark.parametrize(
    "handler_name",
    ["create_lead_endpoint", "update_lead_endpoint", "update_lead_stage_endpoint",
     "update_lead_consent_endpoint", "log_activity_endpoint", "batch_score_leads_endpoint",
     "generate_offer_endpoint"],
)
def test_revops_writes_are_role_gated(handler_name):
    _assert_role_gated(revops_router, handler_name)


# ── Role-set composition ────────────────────────────────────────────────────

def test_no_write_gate_admits_students_or_parents():
    """The people the school holds records ABOUT are never the people who
    may rewrite them."""
    for const in (
        hr_router._HR_ADMIN,
        hr_router._MAY_REQUEST_LEAVE,
        library_router._LIBRARIAN,
        timetable_router._SCHEDULER,
        timetable_router._SUBSTITUTION_MANAGER,
        revops_router._ADMISSIONS,
        revops_router._CONSENT_MANAGER,
    ):
        assert "STUDENT" not in const
        assert "PARENT" not in const


def test_personnel_files_are_admin_only_not_teacher_wide():
    """Staff profiles carry basic_salary: a colleague must not rewrite it."""
    assert "TEACHER" not in hr_router._HR_ADMIN
    assert "STAFF" not in hr_router._HR_ADMIN
    assert "SCHOOL_ADMIN" in hr_router._HR_ADMIN


def test_consent_is_narrower_than_general_admissions_work():
    """Consent gates outbound contact, so it is not routine CRM editing."""
    assert "STAFF" in revops_router._ADMISSIONS
    assert "STAFF" not in revops_router._CONSENT_MANAGER


def test_a_teacher_may_arrange_cover_but_not_rewrite_the_timetable():
    assert "TEACHER" in timetable_router._SUBSTITUTION_MANAGER
    assert "TEACHER" not in timetable_router._SCHEDULER


def test_librarian_gate_excludes_teachers_who_are_merely_patrons():
    assert "TEACHER" not in library_router._LIBRARIAN


# ── Proof the assertion is not vacuous ──────────────────────────────────────

def test_the_assertion_discriminates():
    """Run the same check against a deliberately un-gated handler.

    Without this, every test above could pass because the assertion never
    fires on anything. `list_staff_profiles` is a READ that is still, by
    design, open to any authenticated user -- so it must FAIL the write check.
    """
    with pytest.raises(AssertionError, match="admits ANY authenticated user"):
        _assert_role_gated(hr_router, "list_staff_profiles")
