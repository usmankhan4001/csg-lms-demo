"""Every endpoint in ai_student_profile.py was UNAUTHENTICATED.

Not weakly gated. Three handlers used `get_optional_user_principal`, which
returns None rather than refusing, and the other eight took no principal at
all. Probed against the running API with no Authorization header:

    GET  /api/v1/ai/concepts                        -> 200  (leaked)
    GET  /api/v1/ai/student/1/recommended-concepts  -> 200  (leaked a named
                                                             child's learning
                                                             profile)
    POST /api/v1/ai/concepts                        -> 422  (validation
                                                             reached: an
                                                             anonymous WRITE)
    GET  /api/v1/ai/knowledge-graph/graph           -> 401  (sibling router,
                                                             correctly gated)
    bogus path                                      -> 404  (probe
                                                             discriminates)

These assert the DEPENDENCY WIRING rather than going over HTTP, because the
fault was in the dependency: a handler body can be perfectly correct and still
be reachable by anyone on the network.
"""

import inspect

import pytest

import src.routers.ai_student_profile as profile


def _deps(fn) -> str:
    """Flatten a handler's dependency defaults into inspectable text."""
    return " ".join(repr(p.default) for p in inspect.signature(fn).parameters.values())


ALL_HANDLERS = [n for n in dir(profile) if n.startswith("api_")]


def test_the_router_exposes_the_handlers_we_think_it_does():
    """Guard against this file silently testing nothing if handlers are renamed."""
    assert len(ALL_HANDLERS) >= 11, ALL_HANDLERS


@pytest.mark.parametrize("handler_name", ALL_HANDLERS)
def test_no_endpoint_is_reachable_without_authentication(handler_name):
    deps = _deps(getattr(profile, handler_name))
    assert (
        "require_roles" in deps
        or "require_own_student_or_privileged" in deps
        or "RoleChecker" in deps
        or "get_current_user_principal" in deps
        or "_student_ownership_checker" in deps
    ), f"{handler_name} has no authentication dependency -- it is open to the internet"


@pytest.mark.parametrize("handler_name", ALL_HANDLERS)
def test_no_endpoint_uses_the_optional_principal_crutch(handler_name):
    """`get_optional_user_principal` returns None instead of refusing, so it
    authenticates nothing. Three handlers here used it and read as gated."""
    assert "get_optional_user_principal" not in _deps(getattr(profile, handler_name))


@pytest.mark.parametrize(
    "handler_name",
    ["api_evaluate_mastery_update", "api_create_concept", "api_link_prerequisite"],
)
def test_curriculum_and_assessment_writes_are_staff_only(handler_name):
    """Writing a mastery score is an assessment judgement about a child, and a
    curriculum edit changes what every student is taught."""
    assert "require_roles" in _deps(getattr(profile, handler_name))


def test_staff_role_set_excludes_students_and_parents():
    assert "STUDENT" not in profile._STAFF
    assert "PARENT" not in profile._STAFF
    assert "TEACHER" in profile._STAFF


@pytest.mark.parametrize(
    "handler_name",
    [
        "api_get_student_mastery_radar",
        "api_get_student_learning_path",
        "api_get_recommended_concepts",
    ],
)
def test_one_students_profile_is_not_readable_by_another(handler_name):
    """These reuse require_own_student_or_privileged rather than a new rule:
    the student, their guardian via StudentGuardian, or staff."""
    deps = _deps(getattr(profile, handler_name))
    assert "require_own_student_or_privileged" in deps or "_student_ownership_checker" in deps, deps


def test_the_assertion_discriminates():
    """If the gate check ever goes blind this file would pass vacuously, so
    prove it fails on a function that genuinely has no auth dependency."""

    def unguarded(db_session=None):  # no principal at all
        return None

    with pytest.raises(AssertionError):
        deps = _deps(unguarded)
        assert (
            "require_roles" in deps
            or "require_own_student_or_privileged" in deps
            or "get_current_user_principal" in deps
        ), "unguarded"
