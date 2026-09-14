"""
Admissions Copywriting Agent (M26)
==================================
Writes the actual outreach copy -- subject line, WhatsApp body, email body --
with the tone matched to where the lead sits in the funnel. A cold inquiry and
an expiring offer are not the same conversation, and copy that treats them the
same is why generic drip campaigns get ignored.

EVERYTHING IT RETURNS IS A DRAFT
--------------------------------
`status` is always `DRAFT` and nothing here sends. Scheduled delivery belongs
to the nurture scheduler; a human approves first. That separation is
deliberate: generated copy addressed to a named family is exactly the thing
that should not reach a phone without someone having read it.

ON THE OPTIONAL MODEL CALL
--------------------------
The default path is templated and deterministic, matching
`revops_offer_generator.py`. That is not a placeholder for "real AI later" --
it is what makes the output auditable and the tests meaningful.

`refine_copy_with_model()` additionally runs a draft through the configured
model to loosen the phrasing, metered against the org's monthly RevOps token
budget. If the model is unavailable or the org is over budget it returns the
deterministic draft unchanged with a stated reason, rather than an error or --
worse -- invented copy. The school always gets usable text.

It is a separate async function rather than a `refine=True` flag on the
generator because `llm.client.generate` is async while the model router's
`call_with_budget` is sync: a sync function cannot honestly await a model.
The budget primitives (`check_token_budget` / `record_token_spend`) are used
directly here instead, which is the same accounting, just without the
sync-only convenience wrapper.
"""

import logging
from typing import Any, Dict, List, Optional

from src.services.ai.revops_model_router import (
    DEFAULT_MONTHLY_TOKEN_BUDGET,
    check_token_budget,
    record_token_spend,
    resolve_provider_chain,
)

logger = logging.getLogger(__name__)

# Tone and message shape per funnel stage. Values are plain strings so the
# module stays decoupled from the DB enum.
_STAGE_TONE: Dict[str, Dict[str, str]] = {
    "NEW_INQUIRY": {
        "tone": "warm, brief, no pressure",
        "goal": "acknowledge the inquiry and make the next step easy",
        "cta": "Would you like me to send the admissions pack, or arrange a short visit?",
    },
    "CONTACTED": {
        "tone": "helpful, specific",
        "goal": "move them to a campus visit",
        "cta": "Would a weekday morning or a Saturday suit you better for a visit?",
    },
    "TOUR_BOOKED": {
        "tone": "practical, reassuring",
        "goal": "confirm the visit and reduce no-shows",
        "cta": "Just reply to confirm and we'll have everything ready for you.",
    },
    "ASSESSMENT_SCHEDULED": {
        "tone": "calm, reassuring, child-focused",
        "goal": "lower anxiety about the assessment",
        "cta": "If you have any questions before the day, just reply here.",
    },
    "OFFER_SENT": {
        "tone": "clear, warm, time-aware",
        "goal": "prompt a decision before the offer lapses",
        "cta": "Reply to confirm the seat and we'll take care of the rest.",
    },
    "STALLED": {
        "tone": "light, genuinely no-pressure",
        "goal": "re-open the conversation without nagging",
        "cta": "If the timing is better now, I'm happy to pick this back up.",
    },
}

_DEFAULT_TONE = {
    "tone": "professional, friendly",
    "goal": "keep the admissions conversation moving",
    "cta": "Happy to answer any questions you have.",
}

# WhatsApp copy is read on a phone, often mid-task: short paragraphs, no
# subject line, no letterhead.
_WHATSAPP_MAX_CHARS = 700


def _stage_key(stage: Any) -> str:
    return str(getattr(stage, "value", stage) or "").upper()


def _salutation(parent_name: Optional[str]) -> str:
    name = (parent_name or "").strip()
    return f"Dear {name}," if name else "Hello,"


def _subject_for(stage: str, student: str, grade: str, campus: str) -> str:
    subjects = {
        "NEW_INQUIRY": f"Your enquiry about {grade} at {campus}",
        "CONTACTED": f"Visiting {campus} — a good time for {student}?",
        "TOUR_BOOKED": f"Your visit to {campus} is confirmed",
        "ASSESSMENT_SCHEDULED": f"{student}'s assessment at {campus} — what to expect",
        "OFFER_SENT": f"{student}'s place at {campus} — confirming next steps",
        "STALLED": f"Still considering {campus} for {student}?",
    }
    return subjects.get(stage, f"{campus} — admissions for {student}")


def _body_paragraphs(
    stage: str,
    student: str,
    grade: str,
    campus: str,
    tone_spec: Dict[str, str],
) -> List[str]:
    paras: List[str] = []

    if stage == "NEW_INQUIRY":
        paras.append(
            f"Thank you for getting in touch about a place for {student} in {grade}. "
            f"I'm glad you're considering {campus}."
        )
        paras.append(
            "I can send you the admissions pack with fees, curriculum and term dates, "
            "or if it's easier, you're welcome to come and see the school."
        )
    elif stage == "CONTACTED":
        paras.append(
            f"Following up on your enquiry about {grade} for {student}. "
            "The best way to get a feel for the school is usually to visit."
        )
        paras.append(
            "A visit takes about thirty minutes — you'd see the classrooms, meet the "
            "year lead, and have time to ask whatever you'd like."
        )
    elif stage == "TOUR_BOOKED":
        paras.append(
            f"Your visit to {campus} is confirmed. Please come to the main reception "
            "and ask for the admissions office."
        )
        paras.append(
            f"{student} is very welcome to come along — most families find it helps to "
            "see how their child responds to the place."
        )
    elif stage == "ASSESSMENT_SCHEDULED":
        paras.append(
            f"{student}'s assessment is coming up. It's a relaxed session, not an exam — "
            "we're looking at reading, numeracy and how they approach a problem."
        )
        paras.append(
            "There's nothing to revise. A good night's sleep and breakfast is genuinely "
            "the best preparation."
        )
    elif stage == "OFFER_SENT":
        paras.append(
            f"We're delighted to have offered {student} a place in {grade} at {campus}."
        )
        paras.append(
            "To hold the seat we just need your confirmation. If anything about the "
            "offer needs discussing — timing, fees, anything — do say."
        )
    elif stage == "STALLED":
        paras.append(
            f"I wanted to check in about {student}'s application for {grade}. "
            "I know these decisions take time and circumstances change."
        )
        paras.append(
            "If it's still of interest, I can let you know which intakes have space. "
            "If not, that's completely fine — just let me know and I'll close the file."
        )
    else:
        paras.append(
            f"Getting in touch about {student}'s application for {grade} at {campus}."
        )

    paras.append(tone_spec["cta"])
    return paras


def _truncate_for_whatsapp(text: str) -> str:
    if len(text) <= _WHATSAPP_MAX_CHARS:
        return text
    cut = text[:_WHATSAPP_MAX_CHARS].rsplit("\n\n", 1)[0]
    return cut.rstrip()


def generate_outreach_copy(
    lead: Dict[str, Any],
    channel: str = "email",
    campus_info: Optional[Dict[str, Any]] = None,
    stage_override: Optional[str] = None,
) -> Dict[str, Any]:
    """Draft stage-appropriate outreach copy for one lead. Deterministic.

    Args:
        lead: The `AdmissionsLead` record as a dict.
        channel: "email" or "whatsapp". Email gets a subject line; WhatsApp is
            kept short and subject-less.
        campus_info: Optional campus metadata (campus_name).
        stage_override: Write for a different stage than the lead's current one
            (e.g. drafting the offer follow-up in advance).

    Returns:
        Dict with `subject`, `body`, `channel`, `stage`, `tone`, `status`
        (always DRAFT) and `refined` (always False here -- see
        `refine_copy_with_model`).
    """
    if not isinstance(lead, dict):
        lead = {}
    campus = campus_info if isinstance(campus_info, dict) else {}

    stage = _stage_key(stage_override or lead.get("stage"))
    tone_spec = _STAGE_TONE.get(stage, _DEFAULT_TONE)

    student = (lead.get("student_name") or "").strip() or "your child"
    grade = (lead.get("grade_applying_for") or lead.get("grade") or "").strip() or "the year group"
    campus_name = (campus.get("campus_name") or "").strip() or "our school"
    parent_name = lead.get("parent_name")

    channel_key = (channel or "email").strip().lower()
    paragraphs = _body_paragraphs(stage, student, grade, campus_name, tone_spec)

    if channel_key == "whatsapp":
        # No salutation block on WhatsApp — it reads as a form letter there.
        body = _truncate_for_whatsapp("\n\n".join(paragraphs))
        subject = None
    else:
        body = "\n\n".join([_salutation(parent_name), *paragraphs, "Admissions Office"])
        subject = _subject_for(stage, student, grade, campus_name)

    result: Dict[str, Any] = {
        "lead_id": lead.get("id"),
        "channel": channel_key,
        "stage": stage or None,
        "tone": tone_spec["tone"],
        "goal": tone_spec["goal"],
        "subject": subject,
        "body": body,
        "status": "DRAFT",
        "refined": False,
        "note": (
            "Draft only — nothing has been sent. Review before it goes to the family."
        ),
    }

    return result


async def refine_copy_with_model(
    draft: Dict[str, Any],
    org_id: Optional[int] = None,
    model_name: Optional[str] = None,
    budget_limit: int = DEFAULT_MONTHLY_TOKEN_BUDGET,
) -> Dict[str, Any]:
    """Optionally polish a deterministic draft with the configured model.

    Never raises and never returns a worse result than it was given: on a
    budget breach, an unavailable provider, or an empty completion, the
    original draft comes back with `refined=False` and a `refinement_note`
    explaining why. The instruction forbids adding facts, because the one
    thing a model must not do to admissions copy is invent a date, a fee or
    a promise the school did not make.
    """
    result = dict(draft)
    body = str(result.get("body") or "")
    if not body.strip():
        result["refinement_note"] = "Nothing to refine."
        return result

    budget = check_token_budget(org_id, limit=budget_limit)
    if not budget.is_allowed:
        logger.info("Copy refinement skipped: org %s over monthly token budget", org_id)
        result["refinement_note"] = (
            f"Monthly AI budget for this organisation is used up "
            f"({budget.current_spend} of {budget.limit} tokens). The standard draft was kept."
        )
        return result

    prompt = (
        "Rewrite the following admissions message so it reads naturally and warmly. "
        f"Tone: {result.get('tone', 'professional')}. "
        f"Goal: {result.get('goal', 'keep the conversation moving')}. "
        "Keep it the same length or shorter. Do NOT add any fact, figure, date, "
        "name, fee or promise that is not already present in the text.\n\n"
        f"{body}"
    )

    try:
        chain = resolve_provider_chain(model_name or "")
        candidate = chain[0]

        from src.services.ai.llm.client import generate

        text = await generate(
            model_name=candidate.model_name,
            user_prompt=prompt,
            system_prompt=(
                "You are an admissions officer at a school. You rewrite drafts for "
                "tone only. You never introduce new information."
            ),
        )
    except Exception:
        logger.warning(
            "Copy refinement failed for org %s; keeping deterministic draft", org_id, exc_info=True
        )
        result["refinement_note"] = (
            "The language model was unavailable, so the standard draft was kept."
        )
        return result

    if not isinstance(text, str) or not text.strip():
        result["refinement_note"] = (
            "The language model returned nothing usable, so the standard draft was kept."
        )
        return result

    record_token_spend(org_id, max(1, len(prompt) // 4))
    result["body"] = text.strip()
    result["refined"] = True
    return result
