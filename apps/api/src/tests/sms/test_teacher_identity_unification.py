"""Teacher identity was stored two incompatible ways and could not be joined.

`LessonPlan.teacher_id` and both counselling `psychologist_id` columns held a
`user_uuid` STRING, while `sms_timetable_schedule.teacher_id`,
`sms_live_class_session.teacher_id` and `class_section.class_teacher_id` held
the integer `user.id`. So a teacher's lesson plans and their timetable were,
at the database level, about two different people -- "what is this teacher doing
today" had no answer in SQL, and `sms_timetable.py`'s own docstring recorded the
split as a known obstacle.

Migration b7e2d41a9c38 adds the integer column beside each string one and
backfills it. These tests pin the three properties that make that safe:

  1. New writes carry BOTH identities, so the join now works.
  2. A row carrying only the legacy string is still found by its author --
     otherwise the migration would silently hide a psychologist's own records
     from them, which under the 404-never-403 rule is indistinguishable from
     the records not existing.
  3. Confidentiality is unchanged: another clinician still sees nothing.

Property 3 is the one worth breaking the build over. `_authored_by` widened a
WHERE clause from one arm to two; if either arm is wrong, a psychologist could
read another's clinical records.
"""

import pytest
from fastapi import HTTPException

from src.core.keycloak_auth import KeycloakUserPrincipal
from src.db.sms_counseling import CounselingActivityLog, CounselingSession
from src.db.sms_teacher_tools import LessonPlan
from src.security.school_ownership import get_user_id, require_user_id
from src.services.sms.counseling import _authored_by, _owned_by


def _principal(sub: str, user_id, roles=("PSYCHOLOGIST",)) -> KeycloakUserPrincipal:
    raw = {} if user_id is None else {"lh_user_id": user_id}
    return KeycloakUserPrincipal(
        sub=sub, org_id=1, roles=set(roles), realm_roles=sorted(roles), raw_claims=raw
    )


class TestRequireUserId:
    """The canonical accessor. Ten call sites open-coded this lookup; the
    failure mode being prevented is one of them defaulting to a wrong person."""

    def test_returns_the_integer_user_id(self):
        assert require_user_id(_principal("user_aaa", 11)) == 11

    def test_refuses_rather_than_defaulting_when_absent(self):
        """An unidentifiable caller is unknown -- never user 1. This repo has
        already had 18 sites silently defaulting an absent tenant to org 1."""
        with pytest.raises(HTTPException) as exc:
            require_user_id(_principal("user_aaa", None))
        assert exc.value.status_code == 403

    def test_refuses_a_non_integer_identity(self):
        """`sub` is the uuid string; it must never be mistaken for the id."""
        with pytest.raises(HTTPException) as exc:
            require_user_id(_principal("user_aaa", "user_aaa"))
        assert exc.value.status_code == 403


class TestOwnershipAcrossBothIdentities:
    """`_owned_by` decides whether a clinician may open one loaded record."""

    def test_author_is_recognised_by_the_legacy_string_alone(self):
        """A record written before the migration has no integer. Its author
        must still reach it, or the migration hides their own work from them."""
        rec = CounselingSession(
            student_id=1,
            psychologist_id="user_aaa",
            psychologist_user_id=None,
            session_date="2026-01-01",
            duration_minutes=30,
            notes="n",
        )
        assert _owned_by(rec, _principal("user_aaa", 11)) is True

    def test_author_is_recognised_by_the_integer_alone(self):
        """The forward case: the string may be dropped by a later migration."""
        rec = CounselingSession(
            student_id=1,
            psychologist_id="stale-or-rotated",
            psychologist_user_id=11,
            session_date="2026-01-01",
            duration_minutes=30,
            notes="n",
        )
        assert _owned_by(rec, _principal("user_aaa", 11)) is True

    def test_a_different_clinician_is_refused_under_both_identities(self):
        """The confidentiality guarantee. Neither arm may match a stranger."""
        rec = CounselingSession(
            student_id=1,
            psychologist_id="user_aaa",
            psychologist_user_id=11,
            session_date="2026-01-01",
            duration_minutes=30,
            notes="n",
        )
        assert _owned_by(rec, _principal("user_zzz", 99)) is False

    def test_an_unresolved_row_does_not_match_on_a_null_integer(self):
        """NULL means "not yet resolved", never "belongs to whoever asks".
        A None == None comparison here would expose every unbackfilled record."""
        rec = CounselingActivityLog(
            student_id=1,
            psychologist_id="somebody-else",
            psychologist_user_id=None,
            signal_type="x",
            description="d",
            severity="low",
        )
        # The caller's own integer is present; the record's is not.
        assert _owned_by(rec, _principal("user_zzz", 99)) is False


class TestAuthoredByPredicateShape:
    """`_authored_by` is the SQL twin of `_owned_by`. They must not drift --
    a mismatch means a record a clinician can list but cannot open, or the
    reverse, which is worse."""

    def test_predicate_references_both_columns(self):
        compiled = str(
            _authored_by(CounselingSession, _principal("user_aaa", 11)).compile(
                compile_kwargs={"literal_binds": True}
            )
        )
        assert "psychologist_id" in compiled
        assert "psychologist_user_id" in compiled

    def test_predicate_requires_the_integer_to_be_non_null(self):
        """Guards the same NULL hole as the in-memory twin, in SQL."""
        compiled = str(
            _authored_by(CounselingSession, _principal("user_aaa", 11)).compile(
                compile_kwargs={"literal_binds": True}
            )
        ).upper()
        assert "IS NOT NULL" in compiled


class TestLessonPlanCarriesBothIdentities:
    def test_model_accepts_the_integer_identity(self):
        """The whole point: a plan can now be joined to its author's timetable,
        which keys the teacher on the same integer."""
        plan = LessonPlan(
            teacher_id="user_aaa",
            teacher_user_id=11,
            subject="Maths",
            topic="Quadratics",
            grade_level="9",
            duration_minutes=40,
        )
        assert plan.teacher_id == "user_aaa"
        assert plan.teacher_user_id == 11

    def test_integer_identity_is_optional_for_legacy_rows(self):
        """Rows predating the migration, and rows whose string matched no user,
        legitimately have no integer. That is 'unresolved', not 'invalid'."""
        plan = LessonPlan(
            teacher_id="dev-user-ghost",
            subject="Maths",
            topic="Quadratics",
            grade_level="9",
            duration_minutes=40,
        )
        assert plan.teacher_user_id is None


class TestCallerWithoutAnIntegerIdentity:
    """Not every principal carries `lh_user_id` -- and during the migration a
    record is still fully attributable by its string column. A missing integer
    must therefore degrade to string-only matching, never refuse a valid write
    and never match everything."""

    def test_lenient_accessor_returns_none_rather_than_raising(self):
        assert get_user_id(_principal("user_aaa", None)) is None

    def test_author_still_recognised_by_string_when_caller_has_no_integer(self):
        rec = CounselingSession(
            student_id=1,
            psychologist_id="user_aaa",
            psychologist_user_id=11,
            session_date="2026-01-01",
            duration_minutes=30,
            notes="n",
        )
        assert _owned_by(rec, _principal("user_aaa", None)) is True

    def test_stranger_without_integer_is_still_refused(self):
        """The dangerous case: a caller with no integer identity must not fall
        through into matching a record whose integer is also unset."""
        rec = CounselingSession(
            student_id=1,
            psychologist_id="user_aaa",
            psychologist_user_id=None,
            session_date="2026-01-01",
            duration_minutes=30,
            notes="n",
        )
        assert _owned_by(rec, _principal("user_zzz", None)) is False

    def test_sql_predicate_falls_back_to_string_only(self):
        """If the integer arm were kept while NULL, the WHERE clause would
        return every unbackfilled row in the table to any caller."""
        compiled = str(
            _authored_by(CounselingSession, _principal("user_aaa", None)).compile(
                compile_kwargs={"literal_binds": True}
            )
        )
        assert "psychologist_user_id" not in compiled
        assert "psychologist_id" in compiled
