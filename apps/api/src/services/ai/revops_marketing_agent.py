"""
Admissions Marketing Agent (M25)
================================
Campaign-level planning: given a pool of leads and some targeting criteria,
work out who the campaign should actually go to, on which channel, when, and
with what angle.

THE CONSENT RULE IS THE POINT OF THIS MODULE
--------------------------------------------
A campaign is the moment a school stops answering inquiries and starts
initiating contact, so consent stops being paperwork and becomes the whole
question. Two decisions follow from that, and both differ from the rest of
the RevOps services:

* **Outbound is opt-IN here.** Elsewhere in this codebase (the SDR agent, the
  drip engine) the rule is "explicit False blocks, unknown is permitted",
  which is right for *replying* to someone who just messaged you. For a bulk
  campaign to a lead who has not asked for it, unknown consent is not a
  green light. A lead is eligible only when consent for that channel is
  explicitly True.

* **Exclusions are counted and returned, never silently dropped.** A segment
  that quietly shrinks from 400 to 12 looks like a targeting choice. The
  caller gets `excluded_no_consent` and a per-reason breakdown so the reason
  is visible, and so someone can go and ask those families for consent.

Everything here is deterministic. Channel and timing come from the lead's
stage and score, not from a language model -- a hallucinated "best send time"
would be indistinguishable from a real one and impossible to audit.
"""

from typing import Any, Dict, Iterable, List, Optional

# Channel a stage's outreach should lead with, and the angle that fits it.
# Keyed on LeadStage values (kept as plain strings so this module does not
# need the DB enum imported at call time).
_STAGE_PLAYBOOK: Dict[str, Dict[str, str]] = {
    "NEW_INQUIRY": {
        "channel": "whatsapp",
        "angle": "Acknowledge the inquiry and offer the admissions pack.",
        "timing": "Within 24 hours — response speed is the single biggest lever at this stage.",
    },
    "CONTACTED": {
        "channel": "email",
        "angle": "Invite to a campus tour; lead with facilities and curriculum.",
        "timing": "2–3 days after first contact.",
    },
    "TOUR_BOOKED": {
        "channel": "whatsapp",
        "angle": "Confirm the tour, set expectations, reduce no-shows.",
        "timing": "Day before the booked tour.",
    },
    "ASSESSMENT_SCHEDULED": {
        "channel": "whatsapp",
        "angle": "Reassure about the assessment format; reduce anxiety for the child.",
        "timing": "48 hours before the assessment.",
    },
    "OFFER_SENT": {
        "channel": "email",
        "angle": "Deadline reminder and a clear next step to accept the seat.",
        "timing": "3 days before the offer expires.",
    },
    "STALLED": {
        "channel": "whatsapp",
        "angle": "Low-pressure re-open: new intake dates, scholarship window.",
        "timing": "At the start of a new intake cycle.",
    },
}

# Stages a campaign must never target.
_NEVER_TARGET = {"ENROLLED", "LOST"}

_CONSENT_FIELD = {"whatsapp": "whatsapp_consent", "email": "email_consent"}


def _stage_of(lead: Dict[str, Any]) -> str:
    raw = lead.get("stage")
    return str(getattr(raw, "value", raw) or "").upper()


def has_explicit_consent(lead: Dict[str, Any], channel: str) -> bool:
    """Opt-IN check for outbound campaigns.

    Deliberately stricter than `revops_sdr_agent.has_channel_consent`: this
    returns True only when the consent field is explicitly True. Unknown
    consent is not consent when the school is the one initiating contact.
    """
    field = _CONSENT_FIELD.get((channel or "").strip().lower())
    if field is None:
        # No consent field exists for this channel (e.g. phone). Campaign
        # targeting only covers channels we can actually evidence consent for.
        return False
    return lead.get(field) is True


def segment_leads(
    leads: Iterable[Dict[str, Any]],
    channel: str,
    stages: Optional[List[str]] = None,
    grades: Optional[List[str]] = None,
    sources: Optional[List[str]] = None,
    min_score: Optional[int] = None,
    max_score: Optional[int] = None,
) -> Dict[str, Any]:
    """Build a campaign segment, reporting every exclusion and its reason.

    Returns `eligible` (leads that may be contacted on `channel`) plus
    `excluded_no_consent`, `excluded_by_stage`, `excluded_by_filter` and a
    `reasons` breakdown, so the shrinkage from pool to segment is always
    explainable.
    """
    channel_key = (channel or "").strip().lower()
    wanted_stages = {s.upper() for s in (stages or [])}
    wanted_grades = {g.strip().lower() for g in (grades or [])}
    wanted_sources = {s.upper() for s in (sources or [])}

    eligible: List[Dict[str, Any]] = []
    no_consent: List[Dict[str, Any]] = []
    excluded_stage = 0
    excluded_filter = 0

    for lead in leads or []:
        if not isinstance(lead, dict):
            continue

        stage = _stage_of(lead)

        # Never market to someone already enrolled or explicitly lost.
        if stage in _NEVER_TARGET:
            excluded_stage += 1
            continue
        if wanted_stages and stage not in wanted_stages:
            excluded_filter += 1
            continue

        grade = str(lead.get("grade_applying_for") or lead.get("grade") or "").strip().lower()
        if wanted_grades and grade not in wanted_grades:
            excluded_filter += 1
            continue

        source = str(getattr(lead.get("source"), "value", lead.get("source")) or "").upper()
        if wanted_sources and source not in wanted_sources:
            excluded_filter += 1
            continue

        score = lead.get("lead_score")
        score_val = score if isinstance(score, (int, float)) else 0
        if min_score is not None and score_val < min_score:
            excluded_filter += 1
            continue
        if max_score is not None and score_val > max_score:
            excluded_filter += 1
            continue

        # Consent last, so the count reflects leads that matched the targeting
        # and were held back *only* by consent -- that is the actionable number.
        if not has_explicit_consent(lead, channel_key):
            no_consent.append(lead)
            continue

        eligible.append(lead)

    return {
        "channel": channel_key,
        "eligible": eligible,
        "eligible_count": len(eligible),
        "excluded_no_consent": len(no_consent),
        "excluded_no_consent_ids": [l.get("id") for l in no_consent],
        "excluded_by_stage": excluded_stage,
        "excluded_by_filter": excluded_filter,
        "reasons": {
            "no_explicit_consent": (
                f"{len(no_consent)} lead(s) matched the targeting but have not "
                f"opted in to {channel_key or 'this channel'}. They are excluded "
                "from outbound, and are the list worth seeking consent from."
            ),
            "not_targetable_stage": (
                f"{excluded_stage} lead(s) are ENROLLED or LOST and are never "
                "included in outreach campaigns."
            ),
            "filtered_out": f"{excluded_filter} lead(s) did not match the campaign filters.",
        },
    }


def plan_campaign(
    leads: Iterable[Dict[str, Any]],
    channel: str,
    stages: Optional[List[str]] = None,
    grades: Optional[List[str]] = None,
    sources: Optional[List[str]] = None,
    min_score: Optional[int] = None,
    max_score: Optional[int] = None,
    campaign_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Propose a campaign: who, which channel, when, and the message angle.

    The plan is a proposal for a human to approve. It sends nothing — delivery
    is the drip engine's job, and keeping proposal separate from send means a
    mis-targeted campaign is caught before it reaches a family.
    """
    segment = segment_leads(
        leads,
        channel=channel,
        stages=stages,
        grades=grades,
        sources=sources,
        min_score=min_score,
        max_score=max_score,
    )

    # The dominant stage in the segment drives the angle; a campaign spanning
    # several stages is reported as mixed rather than given one stage's pitch.
    stage_counts: Dict[str, int] = {}
    for lead in segment["eligible"]:
        stage_counts[_stage_of(lead)] = stage_counts.get(_stage_of(lead), 0) + 1

    dominant_stage = max(stage_counts, key=stage_counts.get) if stage_counts else None
    is_mixed = len(stage_counts) > 1

    playbook = _STAGE_PLAYBOOK.get(dominant_stage or "", None)
    recommended_channel = playbook["channel"] if playbook else (channel or "").strip().lower()

    warnings: List[str] = []
    if segment["eligible_count"] == 0:
        warnings.append(
            "No lead in this pool can be contacted on this channel. Check the "
            "consent exclusions before changing the targeting."
        )
    if playbook and recommended_channel != (channel or "").strip().lower():
        warnings.append(
            f"Leads at the {dominant_stage} stage typically respond better on "
            f"{recommended_channel}; this campaign is set to {channel}."
        )
    if is_mixed:
        warnings.append(
            "The segment spans several funnel stages, so one message will not "
            "fit all of them. Consider splitting by stage."
        )

    return {
        "campaign_name": campaign_name or f"{(dominant_stage or 'MIXED').title()} outreach",
        "channel": (channel or "").strip().lower(),
        "recommended_channel": recommended_channel,
        "dominant_stage": dominant_stage,
        "stage_mix": stage_counts,
        "angle": playbook["angle"] if playbook else "General admissions outreach.",
        "timing": playbook["timing"] if playbook else "No stage-specific timing available.",
        "audience": {
            "eligible_count": segment["eligible_count"],
            "eligible_lead_ids": [l.get("id") for l in segment["eligible"]],
            "excluded_no_consent": segment["excluded_no_consent"],
            "excluded_no_consent_ids": segment["excluded_no_consent_ids"],
            "excluded_by_stage": segment["excluded_by_stage"],
            "excluded_by_filter": segment["excluded_by_filter"],
            "reasons": segment["reasons"],
        },
        "warnings": warnings,
        "status": "PROPOSED",
        "note": (
            "A proposal only. Nothing has been sent and no lead has been "
            "contacted. Delivery is handled separately by the nurture "
            "scheduler after a human approves."
        ),
    }
