"""
Resolving and recording parental consent for a minor's AI use.

See `src/db/sms_ai_consent.py` for the data model and why it is append-only.
This module answers two questions: "may this student use this AI feature right
now?" and "who has not been asked yet?".
"""

import logging
from typing import Dict, List, Optional, Sequence

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_ai_consent import (
    AIConsentDecision,
    AIConsentEnforcement,
    AIConsentType,
    SchoolAIConsentEvent,
    SchoolAIConsentPolicy,
)
from src.db.sms_identity import StudentGuardian

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# THE CRISIS OVERRIDE DECISION
# ---------------------------------------------------------------------------

CONSENT_CRISIS_OVERRIDE_RATIONALE = """
When a guardian has refused or withdrawn WELLBEING_MONITORING and the child
then types something matching a self-harm or violence pattern, there are three
possible behaviours:

  (a) refuse before classification  -- nothing is detected, nobody is told
  (b) classify and escalate anyway  -- the refusal is overridden
  (c) refuse the TUTORING, but still screen and still show crisis resources

This implementation does (c), and treats escalation to the counsellor as part
of (c) when `crisis_override_enabled` is on (the default).

The reasoning, and it rests on a fact worth checking rather than assuming:
`classify_prompt_safety()` in services/ai/crisis_classifier.py is PURE LOCAL
REGEX -- `re.search` against compiled patterns, no model call, no network, no
third-party processor. The child's words do not leave the server to be
screened.

That changes the balance completely. A guardian refusing "AI" is refusing the
LLM tutoring, which genuinely ships their child's words to an external
provider. Switching off a local pattern match buys that family no privacy from
anyone -- and costs the child the one mechanism that would notice them saying
they want to die. The alert itself carries triage metadata only, never the
student's words (verified in services/ai/crisis_alerts.py, which documents
that rule explicitly).

THE COST, stated plainly: this does override an explicit parental decision. A
guardian who ticked "no wellbeing monitoring" will still have a counsellor
contacted if their child discloses self-harm. That is a real override of a
real refusal, justified on a vital-interests / safeguarding basis, which most
data-protection regimes permit precisely because a child's safety is not a
thing a form can waive. Reasonable people and some jurisdictions may disagree.

THIS IS OVERRIDABLE. `SchoolAIConsentPolicy.crisis_override_enabled = False`
turns it off for an org, in which case a refusal means no screening and no
escalation -- behaviour (a). The owner should make that call deliberately.
"""


# Per-type default when an org has no policy row. AI_TUTOR is the one that
# ships a child's words to a third party, so it is the one a school most needs
# to be able to enforce strictly.
_DEFAULT_ENFORCEMENT = AIConsentEnforcement.ADVISORY


class ConsentStatus:
    """Resolved consent for one student and one type."""

    def __init__(
        self,
        consent_type: AIConsentType,
        decision: AIConsentDecision,
        allowed: bool,
        reason: Optional[str] = None,
        event: Optional[SchoolAIConsentEvent] = None,
    ):
        self.consent_type = consent_type
        self.decision = decision
        self.allowed = allowed
        self.reason = reason
        self.event = event

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<ConsentStatus {self.consent_type.value}={self.decision.value} allowed={self.allowed}>"


async def get_org_policy(
    db_session: AsyncSession, org_id: Optional[int]
) -> SchoolAIConsentPolicy:
    """The org's policy row, or an unsaved default. Never raises."""
    if org_id is None:
        return SchoolAIConsentPolicy(org_id=0, enforcement=_DEFAULT_ENFORCEMENT)
    try:
        result = await db_session.execute(
            select(SchoolAIConsentPolicy).where(SchoolAIConsentPolicy.org_id == org_id)
        )
        row = result.scalars().first()
    except Exception:
        logger.exception("AI consent policy lookup failed for org %s; using defaults", org_id)
        row = None
    return row or SchoolAIConsentPolicy(org_id=org_id, enforcement=_DEFAULT_ENFORCEMENT)


async def _latest_event(
    db_session: AsyncSession, student_id: int, consent_type: AIConsentType
) -> Optional[SchoolAIConsentEvent]:
    """Newest event for this (student, type). Append-only, so newest wins."""
    result = await db_session.execute(
        select(SchoolAIConsentEvent)
        .where(SchoolAIConsentEvent.student_id == student_id)
        .where(SchoolAIConsentEvent.consent_type == consent_type.value)
        .order_by(SchoolAIConsentEvent.id.desc())
        .limit(1)
    )
    return result.scalars().first()


async def resolve_consent(
    db_session: AsyncSession,
    student_id: int,
    consent_type: AIConsentType,
    org_id: Optional[int] = None,
) -> ConsentStatus:
    """Whether `student_id` may use `consent_type` right now.

    A recorded REFUSED/WITHDRAWN always blocks. PENDING (no event at all)
    blocks only under STRICT enforcement -- see AIConsentEnforcement.
    """
    event = await _latest_event(db_session, student_id, consent_type)

    if event is not None:
        decision = AIConsentDecision(event.decision)
        if decision == AIConsentDecision.GRANTED:
            return ConsentStatus(consent_type, decision, allowed=True, event=event)
        # An explicit no is honoured immediately, in every enforcement mode.
        return ConsentStatus(
            consent_type,
            decision,
            allowed=False,
            reason=(
                f"A parent or guardian has {decision.value.lower()} consent for "
                f"{_HUMAN[consent_type]}."
            ),
            event=event,
        )

    policy = await get_org_policy(db_session, org_id)
    if policy.enforcement == AIConsentEnforcement.STRICT:
        return ConsentStatus(
            consent_type,
            AIConsentDecision.PENDING,
            allowed=False,
            reason=(
                f"No parent or guardian consent has been recorded for "
                f"{_HUMAN[consent_type]}. Ask the school office to record it."
            ),
        )

    # ADVISORY: allow, but this student shows up in the missing-consent report.
    return ConsentStatus(
        consent_type,
        AIConsentDecision.PENDING,
        allowed=True,
        reason="No consent recorded; org policy is advisory.",
    )


_HUMAN: Dict[AIConsentType, str] = {
    AIConsentType.AI_TUTOR: "AI tutoring",
    AIConsentType.TRANSCRIPT_RETENTION: "storing AI conversation transcripts",
    AIConsentType.WELLBEING_MONITORING: "wellbeing and safety monitoring",
}


async def may_screen_for_crisis(
    db_session: Optional[AsyncSession],
    student_id: Optional[int],
    org_id: Optional[int] = None,
) -> bool:
    """Whether crisis screening runs for this student.

    Returns True unless the org has disabled the override AND the guardian
    has explicitly refused/withdrawn WELLBEING_MONITORING. Read
    CONSENT_CRISIS_OVERRIDE_RATIONALE before changing this.

    Fails OPEN on any error: a lookup failure must never be the reason a
    child's disclosure goes unnoticed.
    """
    if db_session is None or student_id is None:
        return True
    try:
        policy = await get_org_policy(db_session, org_id)
        if policy.crisis_override_enabled:
            return True
        status_ = await resolve_consent(
            db_session, student_id, AIConsentType.WELLBEING_MONITORING, org_id
        )
        return status_.allowed
    except Exception:
        logger.exception(
            "Crisis-screening consent check failed for student %s; screening anyway", student_id
        )
        return True


async def assert_guardian_of(
    db_session: AsyncSession, guardian_user_id: int, student_id: int
) -> None:
    """403 unless `guardian_user_id` is a recorded guardian of `student_id`."""
    result = await db_session.execute(
        select(StudentGuardian)
        .where(StudentGuardian.guardian_user_id == guardian_user_id)
        .where(StudentGuardian.student_id == student_id)
    )
    if result.scalars().first() is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only a recorded parent or guardian of this student may decide their AI consent.",
        )


async def record_decision(
    db_session: AsyncSession,
    *,
    student_id: int,
    consent_type: AIConsentType,
    decision: AIConsentDecision,
    guardian_user_id: int,
    recorded_by_user_id: int,
    org_id: int,
    campus_id: Optional[int] = None,
    source: Optional[str] = None,
    note: Optional[str] = None,
) -> SchoolAIConsentEvent:
    """Append one decision. Never updates or deletes an earlier row.

    PENDING is a resolved state, not a decision anyone can record -- allowing
    it would let a school erase a refusal by "resetting" it.
    """
    if decision == AIConsentDecision.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "PENDING is not a recordable decision -- it means no decision exists. "
                "Record GRANTED, REFUSED or WITHDRAWN."
            ),
        )

    await assert_guardian_of(db_session, guardian_user_id, student_id)

    event = SchoolAIConsentEvent(
        student_id=student_id,
        org_id=org_id,
        campus_id=campus_id,
        consent_type=consent_type,
        decision=decision,
        guardian_user_id=guardian_user_id,
        recorded_by_user_id=recorded_by_user_id,
        source=source,
        note=note,
    )
    db_session.add(event)
    await db_session.commit()
    await db_session.refresh(event)
    return event


async def consent_history(
    db_session: AsyncSession, student_id: int
) -> Sequence[SchoolAIConsentEvent]:
    """Every decision ever recorded for this student, oldest first."""
    result = await db_session.execute(
        select(SchoolAIConsentEvent)
        .where(SchoolAIConsentEvent.student_id == student_id)
        .order_by(SchoolAIConsentEvent.id.asc())
    )
    return result.scalars().all()


async def consent_summary(
    db_session: AsyncSession, student_id: int, org_id: Optional[int] = None
) -> List[ConsentStatus]:
    """Current resolved state for every consent type."""
    return [
        await resolve_consent(db_session, student_id, ct, org_id)
        for ct in AIConsentType
    ]


async def students_missing_consent(
    db_session: AsyncSession,
    org_id: int,
    consent_type: AIConsentType = AIConsentType.AI_TUTOR,
    campus_id: Optional[int] = None,
) -> List[int]:
    """Students holding the STUDENT role who have no recorded decision.

    This is what makes ADVISORY mode defensible rather than just permissive:
    a school can see exactly who it still has to ask before flipping to
    STRICT.
    """
    from src.db.sms_identity import SchoolRole, SMSUserRole

    stmt = (
        select(SMSUserRole.user_id)
        .where(SMSUserRole.org_id == org_id)
        .where(SMSUserRole.role == SchoolRole.STUDENT.value)
        .where(SMSUserRole.is_active == True)  # noqa: E712
    )
    if campus_id is not None:
        stmt = stmt.where(SMSUserRole.campus_id == campus_id)
    student_ids = list((await db_session.execute(stmt)).scalars().all())
    if not student_ids:
        return []

    decided = (
        await db_session.execute(
            select(SchoolAIConsentEvent.student_id)
            .where(SchoolAIConsentEvent.student_id.in_(student_ids))
            .where(SchoolAIConsentEvent.consent_type == consent_type.value)
        )
    ).scalars().all()
    decided_set = set(decided)
    return [sid for sid in student_ids if sid not in decided_set]
