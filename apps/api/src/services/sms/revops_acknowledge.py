"""
Answering an inbound enquiry the moment it arrives.

The break this closes: `inbound_lead_webhook` de-duplicated and persisted a
lead, then returned. It called no SDR agent and enrolled nobody in a nurture
sequence -- `enrol_lead_in_sequence` was only ever reached from the manual
endpoint, and the cron only advances sequences that already exist. So a 9pm
WhatsApp enquiry sat untouched until a human opened the CRM the next morning.
For a family choosing between schools, overnight silence is the whole decision.

Two rules this module holds to, both learned the hard way in this codebase:

1. **Capture is the thing you cannot lose.** Every AI step here is isolated: if
   the agent raises, the provider is down, or the copy generator refuses, the
   lead still persists and the failure becomes a visible review flag. A webhook
   that 500s because a generator threw would drop the enquiry entirely, which
   is far worse than answering it late.

2. **Never fabricate.** If the intent matcher understood too little, the lead is
   held for a person rather than answered with generic filler. If no channel can
   reach the family, that is recorded as an operations problem, not papered over
   with a send that silently goes nowhere.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.revops_conversation import TurnDirection
from src.db.revops_review import LeadReviewFlag, ReviewReason
from src.db.sms_revops import AdmissionsLead
from src.services.sms.revops_channels import (
    contactable_channels,
    resolve_channel_capability,
)

logger = logging.getLogger(__name__)


@dataclass
class AcknowledgementOutcome:
    """What the automated acknowledgement actually managed to do."""

    acknowledged: bool = False
    nurture_enrolled: bool = False
    held_for_review: bool = False
    review_reason: Optional[str] = None
    detail: Optional[str] = None
    contactable_on: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "acknowledged": self.acknowledged,
            "nurture_enrolled": self.nurture_enrolled,
            "held_for_review": self.held_for_review,
            "review_reason": self.review_reason,
            "detail": self.detail,
            "contactable_on": list(self.contactable_on),
        }


def estimate_intent_confidence(sdr_result: Dict[str, Any], message: str) -> float:
    """A deterministic heuristic for how much of the enquiry was understood.

    THIS IS NOT A MODEL PROBABILITY. `detect_inquiry_intent` is regex pattern
    matching and emits no confidence at all; inventing a float that looked like
    one would be exactly the fabrication this codebase has torn out three times.

    What it measures is what is genuinely knowable: how many intents actually
    matched, and how much usable contact detail the message carried. A message
    that matched nothing scores low, which is the real signal -- "we did not
    understand this, do not answer it automatically."
    """
    matched = sdr_result.get("all_intents") or []
    score = 0.0

    # Something in the message was recognised as a real admissions intent.
    if matched:
        score += 0.5
        if len(matched) > 1:
            score += 0.1

    # Entities extracted from the message body, not merged in from the CRM row,
    # indicate the text itself was parseable.
    entities = sdr_result.get("extracted_entities") or {}
    for key in ("grade", "student_age", "student_name"):
        if entities.get(key):
            score += 0.1
            break

    # A message with no words in it tells us nothing whatever.
    if not (message or "").strip():
        return 0.0

    # A substantive message is weak evidence on its own, but a one-word
    # "hi" should not clear the bar.
    if len((message or "").split()) >= 5:
        score += 0.2

    return round(min(score, 1.0), 2)


async def _org_id_for_lead(session: AsyncSession, lead: AdmissionsLead) -> int:
    """The org this lead belongs to, resolved through its campus.

    AdmissionsLead carries campus_id but no org_id (verified against the
    model), and settings are keyed on (org_id, campus_id). A lead with no
    campus yet resolves to 0, which matches no settings row and therefore
    falls through to the code defaults -- the correct behaviour for an
    enquiry that has not been assigned to a campus.
    """
    if not lead.campus_id:
        return 0
    from sqlalchemy import select as _select

    from src.db.sms_campus import Campus

    campus = (
        await session.execute(_select(Campus).where(Campus.id == lead.campus_id))
    ).scalar_one_or_none()
    return int(campus.org_id) if campus and campus.org_id else 0


async def flag_for_review(
    session: AsyncSession,
    lead: AdmissionsLead,
    reason: ReviewReason,
    detail: str,
    confidence: Optional[float] = None,
) -> LeadReviewFlag:
    """Record that a person needs to look at this lead before the funnel acts."""
    flag = LeadReviewFlag(
        lead_id=lead.id,
        reason=reason,
        detail=detail[:1000],
        confidence=None if confidence is None else f"{confidence:.2f}",
    )
    session.add(flag)
    await session.commit()
    await session.refresh(flag)
    return flag


async def acknowledge_new_lead(
    session: AsyncSession,
    lead: AdmissionsLead,
    *,
    channel: str,
    message: Optional[str] = None,
    campus_info: Optional[Dict[str, Any]] = None,
) -> AcknowledgementOutcome:
    """Answer a freshly captured enquiry, or say why we did not.

    NEVER raises. Every failure path returns an outcome and, where a human
    should intervene, leaves a review flag behind. The caller is a webhook
    whose first duty is not to lose the lead.
    """
    outcome = AcknowledgementOutcome()

    try:
        outcome.contactable_on = contactable_channels(lead)
    except Exception:  # pragma: no cover - defensive
        logger.exception("Could not resolve contactable channels for lead_id=%s", lead.id)
        outcome.contactable_on = []

    # A family nobody can reach is an operations problem the school must see.
    # Recording it here means the CRM can answer "who can we not contact?"
    # instead of leaving a trail of SKIPPED rows that read like a choice.
    if not outcome.contactable_on:
        capability = resolve_channel_capability(channel)
        detail = capability.reason or (
            "No configured channel can reach this lead with the contact details on file."
        )
        outcome.held_for_review = True
        outcome.review_reason = ReviewReason.UNCONTACTABLE.value
        outcome.detail = detail
        try:
            await flag_for_review(session, lead, ReviewReason.UNCONTACTABLE, detail)
        except Exception:  # pragma: no cover - defensive
            logger.exception("Could not flag uncontactable lead_id=%s", lead.id)
        return outcome

    # Settings decide how much the funnel may do unsupervised.
    try:
        from src.services.sms.settings import get_admissions_policy

        org_id = await _org_id_for_lead(session, lead)
        policy = await get_admissions_policy(session, org_id, lead.campus_id)
    except Exception:
        logger.exception("Could not read admissions policy for lead_id=%s; holding for review", lead.id)
        detail = "Admissions automation policy could not be read; enquiry held for a person."
        outcome.held_for_review = True
        outcome.review_reason = ReviewReason.ACKNOWLEDGEMENT_FAILED.value
        outcome.detail = detail
        try:
            await flag_for_review(session, lead, ReviewReason.ACKNOWLEDGEMENT_FAILED, detail)
        except Exception:  # pragma: no cover - defensive
            logger.exception("Could not flag lead_id=%s after policy read failure", lead.id)
        return outcome

    if not policy.auto_acknowledge_inbound:
        outcome.detail = "Automatic acknowledgement is switched off for this school."
        return outcome

    try:
        outcome = await _run_acknowledgement(
            session,
            lead,
            channel=channel,
            message=message,
            campus_info=campus_info,
            policy=policy,
            outcome=outcome,
        )
    except Exception as exc:
        # The lead is already committed by the caller. Losing the enquiry
        # because a generator threw would be the worse outcome by far.
        logger.exception("Automated acknowledgement failed for lead_id=%s", lead.id)
        detail = f"Automated acknowledgement failed: {str(exc)[:400]}"
        outcome.held_for_review = True
        outcome.review_reason = ReviewReason.ACKNOWLEDGEMENT_FAILED.value
        outcome.detail = detail
        try:
            await flag_for_review(session, lead, ReviewReason.ACKNOWLEDGEMENT_FAILED, detail)
        except Exception:  # pragma: no cover - defensive
            logger.exception("Could not flag lead_id=%s after acknowledgement failure", lead.id)

    return outcome


async def _run_acknowledgement(
    session: AsyncSession,
    lead: AdmissionsLead,
    *,
    channel: str,
    message: Optional[str],
    campus_info: Optional[Dict[str, Any]],
    policy: Any,
    outcome: AcknowledgementOutcome,
) -> AcknowledgementOutcome:
    """The acknowledgement proper. Raises; the caller isolates it."""
    from src.services.ai.revops_conversation import lead_to_context, record_turn
    from src.services.ai.revops_sdr_agent import handle_admissions_inquiry

    inbound_text = (message or "").strip()

    # Keep the family's own words, so a later reply is not answered cold and an
    # officer can see what was actually asked.
    if inbound_text:
        await record_turn(
            session,
            lead_id=lead.id,
            direction=TurnDirection.INBOUND,
            message=inbound_text,
            channel=channel,
            detected_intent=None,
        )

    sdr_result = handle_admissions_inquiry(
        message=inbound_text,
        lead_context=lead_to_context(lead),
        channel=channel,
    )

    # Consent is enforced inside the agent; respect its verdict rather than
    # re-deriving it here, so the two cannot drift apart.
    if sdr_result.get("consent_blocked"):
        outcome.detail = (
            f"No acknowledgement sent: the family has opted out of {channel}."
        )
        return outcome

    confidence = estimate_intent_confidence(sdr_result, inbound_text)
    threshold = float(getattr(policy, "auto_acknowledge_min_confidence", 0.4))

    if confidence < threshold:
        detail = (
            f"Enquiry held for human review: only {confidence:.2f} of it was "
            f"understood (threshold {threshold:.2f}). Intents matched: "
            f"{sdr_result.get('all_intents') or 'none'}."
        )
        outcome.held_for_review = True
        outcome.review_reason = ReviewReason.LOW_CONFIDENCE.value
        outcome.detail = detail
        await flag_for_review(session, lead, ReviewReason.LOW_CONFIDENCE, detail, confidence)
        return outcome

    reply = sdr_result.get("response")
    if reply:
        await record_turn(
            session,
            lead_id=lead.id,
            direction=TurnDirection.OUTBOUND,
            message=str(reply),
            channel=channel,
            detected_intent=str(sdr_result.get("intent") or ""),
        )
        outcome.acknowledged = True
        outcome.detail = f"Acknowledgement drafted for {channel}."

    if policy.auto_enrol_in_nurture:
        from src.services.ai.revops_nurture_runner import enrol_lead_in_sequence

        try:
            await enrol_lead_in_sequence(session, lead, campus_info=campus_info)
            outcome.nurture_enrolled = True
        except Exception as exc:
            # A missing campus stops the drip engine generating copy -- that is
            # the engine refusing to invent a school name, which is correct.
            # Record it rather than failing the whole acknowledgement.
            logger.warning(
                "Could not enrol lead_id=%s in nurture sequence: %s", lead.id, exc
            )
            outcome.detail = (
                f"{outcome.detail or ''} Nurture enrolment skipped: {str(exc)[:200]}"
            ).strip()

    return outcome
