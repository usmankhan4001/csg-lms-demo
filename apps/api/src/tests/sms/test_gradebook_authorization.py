"""Authorization on the academic-integrity endpoints.

Every write covered here previously accepted a `principal` parameter and then
never referenced it -- the parameter forced authentication but authorized
nothing. The headline case: a STUDENT could call `batch_enter_grades` and
enter marks for any assessment plan, including their own.

These assert the DEPENDENCY WIRING rather than going over HTTP, because the
bug was in the dependency: a handler body can be perfectly correct and still
be reachable by the wrong person. `test_the_assertions_discriminate` proves
these are not passing vacuously.
"""

import inspect

import pytest

from src.routers import sms_attendance, sms_gradebook


def _deps(func) -> str:
    return " ".join(repr(p.default) for p in inspect.signature(func).parameters.values())


# --- the role gate is actually attached -------------------------------------

@pytest.mark.parametrize(
    "module, handler_name",
    [
        (sms_gradebook, "create_grading_scale"),
        (sms_gradebook, "create_assessment_plan"),
        (sms_gradebook, "batch_enter_grades"),
        (sms_attendance, "update_leave_request_status"),
    ],
)
def test_write_is_role_gated(module, handler_name):
    source = _deps(getattr(module, handler_name))
    assert "get_current_user_principal" not in source, (
        f"{handler_name} is gated by get_current_user_principal, which admits "
        "ANY authenticated user -- including the student being graded."
    )
    assert "require_roles" in source, f"{handler_name} must be role-gated."


def test_the_assertions_discriminate():
    """Proof the test above is not vacuous.

    `list_grading_scales` is deliberately left open (it is a read of school-wide
    config). Running the same assertion against it must FAIL -- if it passed,
    the check above would be meaningless.
    """
    open_handler = _deps(sms_gradebook.list_grading_scales)
    assert "get_current_user_principal" in open_handler
    assert "require_roles" not in open_handler


# --- who is allowed ---------------------------------------------------------

def test_students_and_parents_cannot_author_grades():
    """The headline finding: a student could enter their own marks."""
    for role in ("STUDENT", "PARENT"):
        assert role not in sms_gradebook._GRADING_STAFF
        assert role not in sms_gradebook._GRADING_CONFIG
        assert role not in sms_attendance._LEAVE_APPROVERS


def test_teachers_may_grade_but_not_reconfigure_the_scale():
    """A grading scale reletters every grade in the school."""
    assert "TEACHER" in sms_gradebook._GRADING_STAFF
    assert "TEACHER" not in sms_gradebook._GRADING_CONFIG


def test_grade_entry_also_checks_section_ownership():
    """Role alone is not enough: TEACHER is not a blanket permission over
    every section, so the handler must consult the section too."""
    src = inspect.getsource(sms_gradebook.batch_enter_grades)
    assert "_assert_may_grade_section" in src


def test_leave_filing_is_bound_to_the_caller():
    """`payload.student_id` was trusted, so anyone could file leave in any
    student's name."""
    src = inspect.getsource(sms_attendance.submit_leave_request)
    assert "_assert_may_file_leave_for" in src


def test_grader_attribution_comes_from_the_principal_not_the_body():
    src = inspect.getsource(sms_gradebook.batch_enter_grades)
    assert "grader_id" in src
    assert "graded_by=payload.graded_by" not in src
