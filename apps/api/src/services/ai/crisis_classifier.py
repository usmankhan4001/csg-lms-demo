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


CRISIS_ESCALATION_MESSAGE = (
    "It sounds like you are going through a very difficult time right now, and your wellbeing is our highest priority. "
    "Please know that you do not have to face this alone.\n\n"
    "🆘 **Immediate 24/7 Confidential Crisis Support:**\n"
    "- **National Suicide & Crisis Lifeline:** Call or text **988** (Free & confidential)\n"
    "- **Crisis Text Line:** Text **HOME to 741741**\n"
    "- **The Trevor Project (LGBTQ youth):** Call **1-866-488-7386** or text **START to 678-678**\n"
    "- **International Resources:** Visit [findahelpline.com](https://findahelpline.com)\n\n"
    "Your campus wellbeing and counseling team has been alerted so they can provide confidential support. "
    "If you are in immediate danger, please reach out to emergency services (911) or a trusted adult right away."
)

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
        logger.warning(
            "🚨 CRITICAL COUNSELOR ESCALATION: Student '%s' triggered '%s' alert with severity '%s'.",
            student_id, trigger_category, severity
        )

    return incident
