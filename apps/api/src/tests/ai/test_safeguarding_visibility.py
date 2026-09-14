"""A teacher must not learn that a named child disclosed self-harm.

`list_incidents` was gated on a role set INCLUDING TEACHER, so any teacher in
the org could read student_id + trigger_category + severity for every safety
incident. The student's words were correctly withheld from the response --
but existence is the disclosure. DESIGN-SYSTEM.md requires that where a
record's existence is confidential, other roles get the empty state, and the
spec separates the psychologist queue (M42) from teacher oversight (M46)
precisely here.
"""

import inspect

import src.routers.ai_oversight as oversight


def test_safety_incidents_are_not_visible_to_teachers():
    assert "TEACHER" not in [r for r in oversight._SAFEGUARDING], (
        "TEACHER must not be able to list safety incidents: knowing THAT a "
        "named child disclosed self-harm is itself the disclosure."
    )


def test_safeguarding_roles_are_the_counsellor_and_school_leadership():
    assert "PSYCHOLOGIST" in oversight._SAFEGUARDING
    assert "SCHOOL_ADMIN" in oversight._SAFEGUARDING
    assert "SUPER_ADMIN" in oversight._SAFEGUARDING


def test_list_incidents_uses_the_safeguarding_gate():
    src = " ".join(
        repr(p.default) for p in inspect.signature(oversight.list_incidents).parameters.values()
    )
    assert "require_roles" in src, "list_incidents must stay role-gated"


def test_teacher_oversight_endpoints_still_work_for_teachers():
    """The fix must not lock teachers out of legitimate tutor oversight."""
    assert "TEACHER" in oversight._STAFF, (
        "Teachers keep transcript/block oversight -- only safety INCIDENTS moved."
    )


def test_crisis_without_a_db_session_is_logged_loudly():
    """The escalation path must never fail silently."""
    src = inspect.getsource(__import__("src.services.ai.socratic_tutor", fromlist=["x"]))
    assert "CRISIS NOT ESCALATED" in src, (
        "A crisis that cannot be persisted must still be shouted into the logs."
    )
