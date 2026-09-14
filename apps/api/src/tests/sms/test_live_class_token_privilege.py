"""A student must not be able to mint a host token by asking for one.

`generate_livekit_token(is_teacher=True)` grants `room_admin` AND
`room_record` (services/sms/live_class.py:63-64). The token endpoint used to
pass `is_teacher=payload.is_teacher` straight from the request body, so any
authenticated user could moderate a room -- and record a class full of
children -- by flipping one boolean. It also took `participant_id` from the
body, so a caller could join under someone else's identity and misattribute
attendance and moderation.

These test the derivation helpers directly: that is where the decision is
made, and a handler can be perfectly correct while still trusting the wrong
input.
"""

from types import SimpleNamespace

from src.routers.live_classes import _caller_identity, _caller_is_host


def _principal(user_id=None, roles=(), superadmin=False):
    return SimpleNamespace(
        is_superadmin=superadmin,
        has_any_role=lambda wanted: any(r in roles for r in wanted),
        raw_claims={"lh_user_id": user_id} if user_id is not None else {},
    )


def _session(teacher_id=7):
    return SimpleNamespace(teacher_id=teacher_id)


def test_student_cannot_claim_host_rights():
    student = _principal(user_id=42, roles=("STUDENT",))
    assert _caller_is_host(student, _session(teacher_id=7)) is False


def test_the_sessions_own_teacher_is_host():
    teacher = _principal(user_id=7, roles=("TEACHER",))
    assert _caller_is_host(teacher, _session(teacher_id=7)) is True


def test_a_different_teacher_is_not_host_of_someone_elses_room():
    """TEACHER is not a blanket host role: it must be THIS session's teacher."""
    other = _principal(user_id=9, roles=("TEACHER",))
    assert _caller_is_host(other, _session(teacher_id=7)) is False


def test_school_admin_may_host():
    admin = _principal(user_id=3, roles=("SCHOOL_ADMIN",))
    assert _caller_is_host(admin, _session(teacher_id=7)) is True


def test_superadmin_may_host():
    assert _caller_is_host(_principal(user_id=1, superadmin=True), _session()) is True


def test_identity_comes_from_the_caller_not_the_body():
    """Joining as someone else would misattribute attendance and moderation."""
    student = _principal(user_id=42)
    spoofed = SimpleNamespace(participant_id="99")
    assert _caller_identity(student, spoofed) == "42"


def test_host_decision_ignores_any_is_teacher_field_on_the_payload():
    """The whole bug: the body asked, and the server agreed."""
    student = _principal(user_id=42, roles=("STUDENT",))
    assert _caller_is_host(student, _session(teacher_id=7)) is False
