"""
Parental consent for a minor's AI use (M47).

Two guarantees carry the most weight here.

First, a recorded REFUSED or WITHDRAWN blocks immediately and in every
enforcement mode -- a grace period exists so that schools can collect consent
without locking existing pupils out, NOT so that a parent's explicit "no" can
be deferred.

Second, the crisis-screening decision. A student blocked from tutoring who
then discloses self-harm is still screened and still escalated, because
`classify_prompt_safety` is local regex and withholding it buys the family no
privacy while costing the child their safety net. See
`CONSENT_CRISIS_OVERRIDE_RATIONALE`. Both sides of that are tested, including
the org-level opt-out.
"""

import pytest
from fastapi import HTTPException

from src.db.sms_ai_consent import (
    AIConsentDecision,
    AIConsentEnforcement,
    AIConsentType,
    SchoolAIConsentEvent,
    SchoolAIConsentPolicy,
)
from src.db.sms_identity import StudentGuardian
from src.services.sms.ai_consent import (
    assert_guardian_of,
    consent_history,
    may_screen_for_crisis,
    record_decision,
    resolve_consent,
    students_missing_consent,
)

STUDENT = 501
GUARDIAN = 601
STRANGER = 999
ORG = 1


async def _link_guardian(db, guardian_id=GUARDIAN, student_id=STUDENT):
    db.add(StudentGuardian(guardian_user_id=guardian_id, student_id=student_id))
    await db.commit()


async def _set_policy(db, *, enforcement=AIConsentEnforcement.ADVISORY, crisis_override=True):
    db.add(
        SchoolAIConsentPolicy(
            org_id=ORG, enforcement=enforcement, crisis_override_enabled=crisis_override
        )
    )
    await db.commit()


# ---------------------------------------------------------------------------
# Enforcement modes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_record_is_allowed_under_advisory_default(db):
    """Turning this module on must not lock out every existing pupil."""
    status = await resolve_consent(db, STUDENT, AIConsentType.AI_TUTOR, ORG)
    assert status.decision == AIConsentDecision.PENDING
    assert status.allowed is True


@pytest.mark.asyncio
async def test_no_record_blocks_under_strict(db):
    await _set_policy(db, enforcement=AIConsentEnforcement.STRICT)
    status = await resolve_consent(db, STUDENT, AIConsentType.AI_TUTOR, ORG)
    assert status.decision == AIConsentDecision.PENDING
    assert status.allowed is False
    assert "consent" in (status.reason or "").lower()


@pytest.mark.asyncio
async def test_pending_is_not_the_same_as_refused(db):
    """The whole reason enforcement has two modes."""
    unasked = await resolve_consent(db, STUDENT, AIConsentType.AI_TUTOR, ORG)
    assert unasked.decision == AIConsentDecision.PENDING
    assert unasked.decision != AIConsentDecision.REFUSED
    # And the practical difference: one is allowed through under ADVISORY,
    # the other never is.
    assert unasked.allowed is True


# ---------------------------------------------------------------------------
# Granting, refusing, withdrawing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_granted_consent_allows_tutoring(db):
    await _link_guardian(db)
    await record_decision(
        db,
        student_id=STUDENT,
        consent_type=AIConsentType.AI_TUTOR,
        decision=AIConsentDecision.GRANTED,
        guardian_user_id=GUARDIAN,
        recorded_by_user_id=1,
        org_id=ORG,
    )
    status = await resolve_consent(db, STUDENT, AIConsentType.AI_TUTOR, ORG)
    assert status.allowed is True
    assert status.decision == AIConsentDecision.GRANTED


@pytest.mark.asyncio
async def test_refusal_blocks_even_under_advisory(db):
    """A recorded 'no' is not subject to the grace period."""
    await _set_policy(db, enforcement=AIConsentEnforcement.ADVISORY)
    await _link_guardian(db)
    await record_decision(
        db,
        student_id=STUDENT,
        consent_type=AIConsentType.AI_TUTOR,
        decision=AIConsentDecision.REFUSED,
        guardian_user_id=GUARDIAN,
        recorded_by_user_id=1,
        org_id=ORG,
    )
    status = await resolve_consent(db, STUDENT, AIConsentType.AI_TUTOR, ORG)
    assert status.allowed is False


@pytest.mark.asyncio
async def test_withdrawal_takes_effect_immediately(db):
    await _link_guardian(db)
    for decision in (AIConsentDecision.GRANTED, AIConsentDecision.WITHDRAWN):
        await record_decision(
            db,
            student_id=STUDENT,
            consent_type=AIConsentType.AI_TUTOR,
            decision=decision,
            guardian_user_id=GUARDIAN,
            recorded_by_user_id=1,
            org_id=ORG,
        )
    status = await resolve_consent(db, STUDENT, AIConsentType.AI_TUTOR, ORG)
    assert status.allowed is False
    assert status.decision == AIConsentDecision.WITHDRAWN


@pytest.mark.asyncio
async def test_withdrawal_does_not_erase_that_consent_existed(db):
    """'Was this child covered last March?' must have a truthful answer."""
    await _link_guardian(db)
    for decision in (AIConsentDecision.GRANTED, AIConsentDecision.WITHDRAWN):
        await record_decision(
            db,
            student_id=STUDENT,
            consent_type=AIConsentType.AI_TUTOR,
            decision=decision,
            guardian_user_id=GUARDIAN,
            recorded_by_user_id=1,
            org_id=ORG,
        )
    history = await consent_history(db, STUDENT)
    decisions = [AIConsentDecision(e.decision) for e in history]
    assert decisions == [AIConsentDecision.GRANTED, AIConsentDecision.WITHDRAWN]


@pytest.mark.asyncio
async def test_consent_types_are_independent(db):
    """A guardian may allow tutoring but refuse a permanent transcript."""
    await _link_guardian(db)
    await record_decision(
        db,
        student_id=STUDENT,
        consent_type=AIConsentType.AI_TUTOR,
        decision=AIConsentDecision.GRANTED,
        guardian_user_id=GUARDIAN,
        recorded_by_user_id=1,
        org_id=ORG,
    )
    await record_decision(
        db,
        student_id=STUDENT,
        consent_type=AIConsentType.TRANSCRIPT_RETENTION,
        decision=AIConsentDecision.REFUSED,
        guardian_user_id=GUARDIAN,
        recorded_by_user_id=1,
        org_id=ORG,
    )
    assert (await resolve_consent(db, STUDENT, AIConsentType.AI_TUTOR, ORG)).allowed is True
    assert (
        await resolve_consent(db, STUDENT, AIConsentType.TRANSCRIPT_RETENTION, ORG)
    ).allowed is False


# ---------------------------------------------------------------------------
# Who may decide
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_non_guardian_cannot_grant_consent_for_a_child(db):
    await _link_guardian(db)
    with pytest.raises(HTTPException) as exc:
        await record_decision(
            db,
            student_id=STUDENT,
            consent_type=AIConsentType.AI_TUTOR,
            decision=AIConsentDecision.GRANTED,
            guardian_user_id=STRANGER,
            recorded_by_user_id=1,
            org_id=ORG,
        )
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_guardian_link_is_required_not_assumed(db):
    with pytest.raises(HTTPException):
        await assert_guardian_of(db, GUARDIAN, STUDENT)
    await _link_guardian(db)
    await assert_guardian_of(db, GUARDIAN, STUDENT)


@pytest.mark.asyncio
async def test_pending_cannot_be_recorded_as_a_decision(db):
    """Otherwise a school could erase a refusal by 'resetting' it."""
    await _link_guardian(db)
    with pytest.raises(HTTPException) as exc:
        await record_decision(
            db,
            student_id=STUDENT,
            consent_type=AIConsentType.AI_TUTOR,
            decision=AIConsentDecision.PENDING,
            guardian_user_id=GUARDIAN,
            recorded_by_user_id=1,
            org_id=ORG,
        )
    assert exc.value.status_code == 400


# ---------------------------------------------------------------------------
# The crisis-screening decision -- both ways
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_crisis_screening_survives_a_refusal_by_default(db):
    """A refused family still gets their child screened. The default, and the
    reason is in CONSENT_CRISIS_OVERRIDE_RATIONALE: the screen is local regex,
    so withholding it protects nobody's privacy."""
    await _link_guardian(db)
    await record_decision(
        db,
        student_id=STUDENT,
        consent_type=AIConsentType.WELLBEING_MONITORING,
        decision=AIConsentDecision.REFUSED,
        guardian_user_id=GUARDIAN,
        recorded_by_user_id=1,
        org_id=ORG,
    )
    assert await may_screen_for_crisis(db, STUDENT, ORG) is True


@pytest.mark.asyncio
async def test_an_org_can_turn_the_crisis_override_off(db):
    """The owner's escape hatch if their jurisdiction requires it."""
    await _set_policy(db, crisis_override=False)
    await _link_guardian(db)
    await record_decision(
        db,
        student_id=STUDENT,
        consent_type=AIConsentType.WELLBEING_MONITORING,
        decision=AIConsentDecision.REFUSED,
        guardian_user_id=GUARDIAN,
        recorded_by_user_id=1,
        org_id=ORG,
    )
    assert await may_screen_for_crisis(db, STUDENT, ORG) is False


@pytest.mark.asyncio
async def test_override_off_still_screens_when_consent_is_granted(db):
    await _set_policy(db, crisis_override=False)
    await _link_guardian(db)
    await record_decision(
        db,
        student_id=STUDENT,
        consent_type=AIConsentType.WELLBEING_MONITORING,
        decision=AIConsentDecision.GRANTED,
        guardian_user_id=GUARDIAN,
        recorded_by_user_id=1,
        org_id=ORG,
    )
    assert await may_screen_for_crisis(db, STUDENT, ORG) is True


@pytest.mark.asyncio
async def test_crisis_screening_fails_open_with_no_session(db):
    """A lookup failure must never be why a disclosure goes unnoticed."""
    assert await may_screen_for_crisis(None, STUDENT, ORG) is True
    assert await may_screen_for_crisis(db, None, ORG) is True


# ---------------------------------------------------------------------------
# The chase list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_students_missing_consent_excludes_those_already_decided(db):
    from src.db.sms_identity import SchoolRole, SMSUserRole

    for uid in (STUDENT, STUDENT + 1):
        db.add(SMSUserRole(user_id=uid, org_id=ORG, role=SchoolRole.STUDENT, campus_id=1))
    await db.commit()
    await _link_guardian(db)
    await record_decision(
        db,
        student_id=STUDENT,
        consent_type=AIConsentType.AI_TUTOR,
        decision=AIConsentDecision.GRANTED,
        guardian_user_id=GUARDIAN,
        recorded_by_user_id=1,
        org_id=ORG,
    )
    missing = await students_missing_consent(db, org_id=ORG, consent_type=AIConsentType.AI_TUTOR)
    assert STUDENT not in missing
    assert STUDENT + 1 in missing


# ---------------------------------------------------------------------------
# Append-only
# ---------------------------------------------------------------------------


def test_no_code_path_updates_or_deletes_a_consent_event():
    """If history can be rewritten it is not history."""
    import inspect

    import src.services.sms.ai_consent as svc
    import src.routers.sms_ai_consent as router

    for module in (svc, router):
        source = inspect.getsource(module)
        assert "delete(SchoolAIConsentEvent" not in source
        assert ".delete()" not in source
