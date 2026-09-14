"""
Autonomous nurture runner for the admissions funnel.

`revops_drip_engine.generate_nurture_sequence` has always produced a real
4-stage sequence -- and nothing ever stored or sent it. The stages carry
`day: 1/3/7/14`, but with no persisted schedule those numbers described an
intention, not a plan: no record said stage 2 was owed on day 3, so no stage 2
ever went out.

This module supplies the missing half:

- `enrol_lead_in_sequence` generates the sequence once and persists it with a
  due time, so a later run sends exactly the copy that was generated rather
  than regenerating text that may have drifted.
- `advance_nurture_sequences` is the arq cron job that actually sends what is
  due.

It is the second autonomous job in this system (after the weekly parent
digest) and follows the same conventions: open its own session, off-load the
synchronous send_email onto a thread, and never let one lead's failure abort
the batch.

Three rules this job holds to, all of which exist because the alternative
would be worse than doing nothing:

1. **Consent gates every send.** `_stage_consent_blocked` already encodes the
   rule; this calls it rather than reimplementing it, and records a
   CONSENT_BLOCKED touch so a suppressed message is visible rather than silent.
2. **A closed lead stops receiving mail.** ENROLLED and LOST deactivate the
   sequence. Continuing to drip "come and see our campus" at a family who
   already enrolled, or who told us no, is the most obvious way an automated
   funnel embarrasses a school.
3. **Every attempt is recorded with its real outcome.** A failed send becomes
   a FAILED touch row carrying the reason, never a swallowed log line.
"""

import asyncio
import datetime
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.revops_conversation import (
    LeadNurtureState,
    LeadOutboundTouch,
    TouchStatus,
    TurnDirection,
)
from src.db.sms_revops import ActivityType, AdmissionsLead, LeadActivityLog, LeadStage
from src.services.ai.revops_conversation import lead_to_context, record_turn
from src.services.sms.revops_channels import resolve_delivery_route
from src.services.ai.revops_drip_engine import (
    MissingSchoolIdentity,
    _stage_consent_blocked,
    generate_nurture_sequence,
)

logger = logging.getLogger(__name__)

# Reaching either of these means the conversation is over; stop nurturing.
TERMINAL_STAGES = {LeadStage.ENROLLED, LeadStage.LOST}


def _utc_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _stage_due_at(anchor: datetime.datetime, day_offset: int) -> datetime.datetime:
    return anchor + datetime.timedelta(days=max(int(day_offset), 0))


async def enrol_lead_in_sequence(
    db_session: AsyncSession,
    lead: AdmissionsLead,
    campus_info: Optional[Dict[str, Any]] = None,
) -> LeadNurtureState:
    """Generate the sequence once and schedule its first touch.

    Idempotent: re-enrolling a lead that already has state refreshes the stored
    sequence but does NOT rewind `last_stage_sent`, so a parent cannot be sent
    the welcome message twice by someone clicking the button again.
    """
    # A lead with no campus cannot be nurtured: the copy would have to invent
    # the school's name, which the drip engine now refuses to do. Raise a
    # legible error here rather than letting the scheduled job die on one
    # unassigned lead -- advance_nurture_sequences catches this per lead and
    # records a SKIPPED touch, so the reason is visible to an officer.
    sequence = generate_nurture_sequence(lead_to_context(lead), campus_info or {})

    existing = (
        await db_session.execute(
            select(LeadNurtureState).where(LeadNurtureState.lead_id == lead.id)
        )
    ).scalar_one_or_none()

    now = _utc_now()
    if existing is not None:
        existing.sequence_json = {"stages": sequence}
        existing.is_active = True
        existing.stopped_reason = None
        if existing.next_due_at is None:
            existing.next_due_at = now
        existing.updated_at = now
        db_session.add(existing)
        await db_session.commit()
        await db_session.refresh(existing)
        return existing

    first_day = int(sequence[0].get("day", 1)) if sequence else 1
    state = LeadNurtureState(
        lead_id=lead.id,
        last_stage_sent=0,
        # Anchor on creation so a lead added three days ago is not made to wait
        # another full day-1 delay before its welcome.
        next_due_at=_stage_due_at(lead.created_at or now, first_day),
        is_active=True,
        sequence_json={"stages": sequence},
    )
    db_session.add(state)
    await db_session.commit()
    await db_session.refresh(state)
    return state


async def _deliver_stage(
    db_session: AsyncSession,
    lead: AdmissionsLead,
    stage: Dict[str, Any],
) -> TouchStatus:
    """Send one stage to one lead and record what actually happened."""
    stage_no = int(stage.get("stage", 0) or 0)
    channel = str(stage.get("channel", "email"))
    subject = str(stage.get("subject", "") or "")[:255]
    content = str(stage.get("content", "") or "")

    blocked, blocked_channels = _stage_consent_blocked(lead_to_context(lead), channel)
    if blocked:
        db_session.add(
            LeadOutboundTouch(
                lead_id=lead.id,
                stage=stage_no,
                channel=channel,
                subject=subject,
                status=TouchStatus.CONSENT_BLOCKED,
                detail=f"Lead opted out of: {', '.join(blocked_channels)}",
            )
        )
        await db_session.commit()
        return TouchStatus.CONSENT_BLOCKED

    # Route on the stage's OWN channel rather than assuming email. This used
    # to read `channel`, record it, and then send by email regardless -- so a
    # WhatsApp-only family hit `if not lead.email` and was marked SKIPPED at
    # every stage, forever. The family was never contacted and the CRM said
    # only "skipped", which reads as a delivery decision rather than the truth:
    # this deployment has no WhatsApp sender at all.
    # The stage's channel is a PREFERENCE LIST ("email_whatsapp"), not one
    # channel -- so resolve which leg we can actually deliver on. This used to
    # ignore the channel entirely and send by email, so a WhatsApp-only family
    # hit `if not lead.email` and was marked SKIPPED at every stage, forever:
    # never contacted, and the CRM said only "skipped", which reads as a
    # delivery decision rather than the truth, that no WhatsApp sender exists.
    route = resolve_delivery_route(lead, channel)
    if not route.deliverable:
        if route.unavailable_reason:
            # Operations gap: nobody can be reached on this channel.
            db_session.add(
                LeadOutboundTouch(
                    lead_id=lead.id,
                    stage=stage_no,
                    channel=channel,
                    subject=subject,
                    status=TouchStatus.UNAVAILABLE,
                    detail=route.unavailable_reason,
                )
            )
            await db_session.commit()
            return TouchStatus.UNAVAILABLE

        # Data gap: the channel works, this lead has nothing on file for it.
        db_session.add(
            LeadOutboundTouch(
                lead_id=lead.id,
                stage=stage_no,
                channel=channel,
                subject=subject,
                status=TouchStatus.SKIPPED,
                detail=f"Lead has no {route.missing_address_for} address/number on record",
            )
        )
        await db_session.commit()
        return TouchStatus.SKIPPED

    try:
        from src.services.email.utils import send_email

        # Same approach as crisis_alerts / parent_digest: send_email is
        # synchronous, so run it off the event loop but still await the real
        # result, so "sent" means sent.
        #
        # Only email reaches a real sender today. A non-email channel cannot
        # get here -- resolve_channel_capability already returned UNAVAILABLE
        # for it above -- so this is the seam a WhatsApp/SMS provider plugs
        # into, not a silent email fallback for every channel.
        await asyncio.to_thread(send_email, route.address, subject or "A message from Admissions", content)
        status = TouchStatus.SENT
        detail = None
    except Exception as exc:
        status = TouchStatus.FAILED
        detail = str(exc)[:500]
        logger.exception("Nurture stage %s failed for lead_id=%s", stage_no, lead.id)

    db_session.add(
        LeadOutboundTouch(
            lead_id=lead.id,
            stage=stage_no,
            channel=channel,
            subject=subject,
            status=status,
            detail=detail,
        )
    )
    await db_session.commit()

    if status == TouchStatus.SENT:
        # Visible in the CRM timeline beside human touches, so an officer can
        # see the automation already reached out before they call.
        db_session.add(
            LeadActivityLog(
                lead_id=lead.id,
                activity_type=ActivityType.EMAIL,
                summary=f"Automated nurture stage {stage_no}: {subject}",
                metadata_json={"stage": stage_no, "channel": channel, "automated": True},
            )
        )
        lead.last_contacted_at = _utc_now()
        db_session.add(lead)
        await db_session.commit()
        await record_turn(
            db_session,
            lead_id=lead.id,
            direction=TurnDirection.OUTBOUND,
            message=content,
            channel=channel,
            detected_intent=f"nurture_stage_{stage_no}",
        )

    return status


async def advance_nurture_sequences(ctx: Optional[dict] = None) -> dict:
    """arq job: send every nurture touch that has fallen due.

    Registered as a cron job in `src/core/worker.py`. Returns a counts dict so
    a run is auditable from the worker log rather than only inferable.
    """
    from src.core.events.database import _async_session_factory

    sent = 0
    blocked = 0
    skipped = 0
    unavailable = 0
    failed = 0
    completed = 0
    stopped = 0

    async with _async_session_factory() as session:
        now = _utc_now()
        due = (
            await session.execute(
                select(LeadNurtureState).where(
                    LeadNurtureState.is_active == True,  # noqa: E712
                    LeadNurtureState.next_due_at != None,  # noqa: E711
                    LeadNurtureState.next_due_at <= now,
                )
            )
        ).scalars().all()

        if not due:
            logger.info("Nurture runner: nothing due")
            return {
                "sent": 0, "blocked": 0, "skipped": 0, "unavailable": 0,
                "failed": 0, "completed": 0, "stopped": 0,
            }

        for state in due:
            try:
                lead = (
                    await session.execute(
                        select(AdmissionsLead).where(AdmissionsLead.id == state.lead_id)
                    )
                ).scalar_one_or_none()

                if lead is None:
                    state.is_active = False
                    state.stopped_reason = "Lead no longer exists"
                    session.add(state)
                    await session.commit()
                    stopped += 1
                    continue

                # A family who enrolled, or who said no, must stop hearing from
                # the funnel.
                if lead.stage in TERMINAL_STAGES:
                    state.is_active = False
                    state.stopped_reason = f"Lead reached {lead.stage.value}"
                    state.updated_at = now
                    session.add(state)
                    await session.commit()
                    stopped += 1
                    continue

                stages: List[Dict[str, Any]] = list((state.sequence_json or {}).get("stages") or [])
                next_stage = next(
                    (s for s in stages if int(s.get("stage", 0) or 0) > state.last_stage_sent), None
                )

                if next_stage is None:
                    state.is_active = False
                    state.stopped_reason = "Sequence complete"
                    state.next_due_at = None
                    state.updated_at = now
                    session.add(state)
                    await session.commit()
                    completed += 1
                    continue

                status = await _deliver_stage(session, lead, next_stage)
                if status == TouchStatus.SENT:
                    sent += 1
                elif status == TouchStatus.CONSENT_BLOCKED:
                    blocked += 1
                elif status == TouchStatus.SKIPPED:
                    skipped += 1
                elif status == TouchStatus.UNAVAILABLE:
                    # NOT a failure: nothing went wrong, there is simply no
                    # sender for that channel. Counting it as failed would hide
                    # an operations gap inside a transient-error number.
                    unavailable += 1
                else:
                    failed += 1

                # Advance regardless of outcome. Retrying a consent-blocked or
                # address-less stage forever would pin the sequence on a touch
                # that can never succeed, and the touch row already records why.
                stage_no = int(next_stage.get("stage", 0) or 0)
                state.last_stage_sent = stage_no
                following = next(
                    (s for s in stages if int(s.get("stage", 0) or 0) > stage_no), None
                )
                if following is None:
                    state.is_active = False
                    state.stopped_reason = "Sequence complete"
                    state.next_due_at = None
                    completed += 1
                else:
                    prior_day = int(next_stage.get("day", 0) or 0)
                    next_day = int(following.get("day", prior_day + 1) or prior_day + 1)
                    state.next_due_at = now + datetime.timedelta(days=max(next_day - prior_day, 0))
                state.updated_at = now
                session.add(state)
                await session.commit()

            except Exception:
                # One bad lead must not stop the rest of the batch.
                logger.exception("Nurture runner failed for lead_id=%s", getattr(state, "lead_id", None))
                failed += 1
                try:
                    await session.rollback()
                except Exception:
                    logger.exception("Rollback failed in nurture runner")

    counts = {
        "sent": sent,
        "blocked": blocked,
        "skipped": skipped,
        "unavailable": unavailable,
        "failed": failed,
        "completed": completed,
        "stopped": stopped,
    }
    logger.info("Nurture runner finished: %s", counts)
    return counts
