"""
Student Wellbeing & Crisis Sentiment Classifier (M42, M47)
===========================================================
Detects real-time safety, crisis, self-harm, severe distress, bullying,
violence, and academic dishonesty triggers with immediate counselor escalation.
"""

import re
import logging
from dataclasses import dataclass
from typing import Optional, Tuple
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.ai_models import (
    AISafetyIncident,
    AISafetyCategory,
    AISafetySeverity,
)

logger = logging.getLogger(__name__)

# Pre-compiled safety regex patterns for fast synchronous screening
SELF_HARM_PATTERNS = [
    r"\b(suicide|suicidal|kill myself|want to die|end my life|ending it all|hang myself|slit my wrist|overdose|swallow pills|take my own life)\b",
    r"\b(cutting myself|burn myself|harm myself|hurting myself|self[-\s]?harm|bleed to death|jump off (a bridge|a roof|the building))\b",
    r"\b(better off dead|no reason to live|don't want to live anymore|wish i were dead|goodbye world)\b",
]

SEVERE_DISTRESS_PATTERNS = [
    r"\b(can'?t take this anymore|unbearable pain|having a breakdown|severe panic attack|hopeless and alone|nobody cares about me)\b",
    r"\b(crying uncontrollably|completely lost my mind|suffocating in anxiety|feel trapped)\b",
]

VIOLENCE_WEAPONS_PATTERNS = [
    r"\b(shoot up the school|bring a gun to school|bomb the school|kill (everyone|the teacher|them all|my classmates))\b",
    r"\b(pipe bomb|mass shooting|stab someone|murder|homemade explosive|attack the campus)\b",
]

BULLYING_PATTERNS = [
    r"\b(kill yourself|kys|nobody likes you|go die|worthless piece of|ugly freak|target (him|her|them))\b",
    r"\b(beat (him|her|them) up after school|spread (his|her|their) nudes|ruin (his|her|their) life)\b",
]

CHEATING_PATTERNS = [
    r"\b(give me the answers? to (the|my) (exam|quiz|test|midterm|final))\b",
    r"\b(solve this (exam|test) question for me|tell me the answer key|write my entire (essay|homework|assignment))\b",
    r"\b(do my homework for me|cheat on (this|the) (test|exam))\b",
]


@dataclass
class SafetyCheckResult:
    is_flagged: bool
    category: AISafetyCategory
    severity: AISafetySeverity
    reason: str
    counselor_escalation_required: bool
    canned_response: Optional[str] = None


# The supportive wording is deliberately constant; only the RESOURCE LIST
# varies by school. See `compose_crisis_message`.
_CRISIS_OPENING = (
    "It sounds like you are going through a very difficult time right now, and your wellbeing is our highest priority. "
    "Please know that you do not have to face this alone.\n\n"
)

_CRISIS_CLOSING = (
    "\nYour campus wellbeing and counseling team has been alerted so they can provide confidential support. "
    "If you are in immediate danger, please tell a teacher, a parent, or another adult you trust right now."
)

# What a school that has configured nothing sees.
#
# This used to list 988, the Crisis Text Line, the Trevor Project and
# "emergency services (911)" -- all US-only, in a deployment serving a school
# in Pakistan. A child in crisis was handed numbers that do not connect.
#
# The fix is NOT to swap in another country's numbers. The software cannot know
# them, and a wrong helpline is worse than none: a child dials it at the worst
# moment of their life and reaches nothing. So the fallback carries only what
# is true everywhere -- an international directory, and the instruction to tell
# a trusted adult -- and states plainly that the school has not configured its
# local lines, which is how an administrator finds out before a child does.
_UNCONFIGURED_RESOURCES = (
    "\U0001F198 **Support available to you right now:**\n"
    "- **Tell a teacher, a parent, or another adult you trust.** Say what you told me. "
    "You do not have to explain it perfectly.\n"
    "- **Find a helpline in your country:** [findahelpline.com](https://findahelpline.com)\n\n"
    "_Your school has not yet added its local crisis helpline numbers to this system. "
    "Please also speak to someone at school as soon as you can._\n"
)

CRISIS_ESCALATION_MESSAGE = _CRISIS_OPENING + _UNCONFIGURED_RESOURCES + _CRISIS_CLOSING


def compose_crisis_message(resources: Optional[object] = None) -> str:
    """The crisis message, using the school's own helplines when it has them.

    `resources` is a `CrisisResourcesSettings` (schemas/sms_settings.py), or
    None when no school context is available. It is typed loosely and
    duck-checked so this module stays importable without the settings layer --
    a crisis path that dies on an import is worse than one with generic
    resources.

    NEVER RAISES. Malformed configuration falls back to the unconfigured
    message rather than propagating: a student in distress must receive
    something, always.
    """
    if resources is None:
        return CRISIS_ESCALATION_MESSAGE

    try:
        contacts = list(getattr(resources, "resources", None) or [])
        emergency = getattr(resources, "emergency_number", None)
        extra = getattr(resources, "extra_guidance", None)

        if not contacts and not emergency:
            return CRISIS_ESCALATION_MESSAGE

        lines = ["\U0001F198 **Immediate confidential support:**\n"]
        for c in contacts:
            label = str(getattr(c, "label", "") or "").strip()
            contact = str(getattr(c, "contact", "") or "").strip()
            if not label or not contact:
                # A half-filled row is skipped rather than rendered as a
                # dangling bullet a child might try to act on.
                continue
            desc = str(getattr(c, "description", "") or "").strip()
            suffix = (" -- " + desc) if desc else ""
            lines.append("- **" + label + ":** " + contact + suffix + "\n")

        if emergency:
            lines.append("- **Emergency services:** " + str(emergency).strip() + "\n")

        if len(lines) == 1:
            # Every contact row was malformed and there is no emergency number.
            return CRISIS_ESCALATION_MESSAGE

        lines.append(
            "- **Find a helpline in your country:** [findahelpline.com](https://findahelpline.com)\n"
        )

        if extra:
            lines.append("\n" + str(extra).strip() + "\n")

        return _CRISIS_OPENING + "".join(lines) + _CRISIS_CLOSING
    except Exception:  # pragma: no cover - defensive
        logger.exception("compose_crisis_message failed; using unconfigured fallback")
        return CRISIS_ESCALATION_MESSAGE


VIOLENCE_ALERT_MESSAGE = (
    "I cannot assist with queries involving violence, weapons, or threats of harm. "
    "Campus safety protocols have been activated. If you or someone you know is in danger, "
    "please contact campus security or emergency services immediately."
)

BULLYING_ALERT_MESSAGE = (
    "Harassment, intimidation, and bullying violate our community safety standards. "
    "If you are experiencing bullying or harassment, please reach out to a campus counselor, teacher, "
    "or trusted administrator who can help protect your safety."
)

CHEATING_REDIRECT_MESSAGE = (
    "I cannot provide direct exam answers, completed test solutions, or write your homework for you, "
    "as that violates academic integrity standards.\n\n"
    "However, as your Socratic tutor, I am eager to help you understand the concepts step-by-step! "
    "Let's break down the problem together: what part of the concept feels most challenging, or what have you tried so far?"
)


def classify_prompt_safety(prompt: str) -> SafetyCheckResult:
    """
    Classify a student prompt against safety, crisis, and pedagogical guardrails.
    """
    prompt_clean = prompt.lower().strip()

    # 1. Critical Self-Harm / Crisis
    for pattern in SELF_HARM_PATTERNS:
        if re.search(pattern, prompt_clean, re.IGNORECASE):
            return SafetyCheckResult(
                is_flagged=True,
                category=AISafetyCategory.SELF_HARM,
                severity=AISafetySeverity.CRITICAL,
                reason="Self-harm or suicidal ideation detected",
                counselor_escalation_required=True,
                canned_response=CRISIS_ESCALATION_MESSAGE,
            )

    # 2. Violence / Weapons
    for pattern in VIOLENCE_WEAPONS_PATTERNS:
        if re.search(pattern, prompt_clean, re.IGNORECASE):
            return SafetyCheckResult(
                is_flagged=True,
                category=AISafetyCategory.VIOLENCE,
                severity=AISafetySeverity.CRITICAL,
                reason="Threats of violence, weapons, or mass harm detected",
                counselor_escalation_required=True,
                canned_response=VIOLENCE_ALERT_MESSAGE,
            )

    # 3. Severe Emotional Distress
    for pattern in SEVERE_DISTRESS_PATTERNS:
        if re.search(pattern, prompt_clean, re.IGNORECASE):
            return SafetyCheckResult(
                is_flagged=True,
                category=AISafetyCategory.SEVERE_DISTRESS,
                severity=AISafetySeverity.HIGH,
                reason="Severe emotional distress or mental health crisis detected",
                counselor_escalation_required=True,
                canned_response=CRISIS_ESCALATION_MESSAGE,
            )

    # 4. Bullying / Harassment
    for pattern in BULLYING_PATTERNS:
        if re.search(pattern, prompt_clean, re.IGNORECASE):
            return SafetyCheckResult(
                is_flagged=True,
                category=AISafetyCategory.BULLYING,
                severity=AISafetySeverity.HIGH,
                reason="Bullying, hate speech, or harassment pattern detected",
                counselor_escalation_required=True,
                canned_response=BULLYING_ALERT_MESSAGE,
            )

    # 5. Academic Dishonesty / Direct Cheating
    for pattern in CHEATING_PATTERNS:
        if re.search(pattern, prompt_clean, re.IGNORECASE):
            return SafetyCheckResult(
                is_flagged=True,
                category=AISafetyCategory.CHEATING,
                severity=AISafetySeverity.LOW,
                reason="Direct request for test/exam solution or homework completion",
                counselor_escalation_required=False,
                canned_response=CHEATING_REDIRECT_MESSAGE,
            )

    # Clean
    return SafetyCheckResult(
        is_flagged=False,
        category=AISafetyCategory.OTHER,
        severity=AISafetySeverity.LOW,
        reason="No safety policy violation detected",
        counselor_escalation_required=False,
        canned_response=None,
    )


async def log_safety_incident(
    student_id: str,
    severity: str,
    trigger_category: str,
    prompt_snippet: str,
    counselor_notified: bool,
    db_session: Optional[AsyncSession] = None,
    org_id: Optional[int] = None,
    course_id: Optional[str] = None,
    details: Optional[str] = None,
) -> Optional[AISafetyIncident]:
    """
    Log an AI safety or crisis incident into the database and notify counselor.
    """
    snippet = prompt_snippet[:500] if prompt_snippet else ""
    incident = AISafetyIncident(
        student_id=str(student_id),
        severity=severity,
        trigger_category=trigger_category,
        prompt_snippet=snippet,
        counselor_notified=counselor_notified,
        details=details,
        course_id=str(course_id) if course_id else None,
        org_id=org_id,
    )

    if db_session:
        try:
            add_res = db_session.add(incident)
            if hasattr(add_res, "__await__"):
                await add_res
            await db_session.commit()
            if hasattr(db_session, "refresh"):
                ref_res = db_session.refresh(incident)
                if hasattr(ref_res, "__await__"):
                    await ref_res
            logger.info(
                "Logged AISafetyIncident id=%s student_id=%s severity=%s trigger=%s counselor_notified=%s",
                incident.id, student_id, severity, trigger_category, counselor_notified
            )
        except Exception as e:
            logger.error("Failed to persist AISafetyIncident to db: %s", e, exc_info=True)
            await db_session.rollback()

    if counselor_notified:
        # Actually tell someone. Until this call existed, `counselor_notified`
        # recorded an INTENTION and the only "escalation" was a log line no
        # human was watching -- see src/services/ai/crisis_alerts.py.
        # Dispatch never raises, so a mail outage cannot stop the student from
        # receiving the crisis-support response.
        from src.services.ai.crisis_alerts import dispatch_crisis_alert

        delivered = await dispatch_crisis_alert(
            db_session=db_session,
            org_id=org_id,
            student_label=str(student_id),
            category=trigger_category,
            severity=severity,
            occurred_at=incident.created_at,
            incident_id=incident.id,
        )

        # Persist what actually happened, not what was requested. An incident
        # row claiming `counselor_notified=True` when every send failed would
        # make an undelivered crisis alert look handled in the counseling UI.
        if not delivered and db_session and incident.id is not None:
            try:
                incident.counselor_notified = False
                db_session.add(incident)
                await db_session.commit()
            except Exception:
                logger.exception(
                    "Failed to downgrade counselor_notified on incident id=%s", incident.id
                )
                await db_session.rollback()

    return incident
