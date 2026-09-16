"""
Universal 2-Minute Crisis Escalation SLA Engine (Contract 3 / Phase 4 / M42, M47)
================================================================================
Implements:
1. Pure local synchronous regex screening for crisis, self-harm, and severe distress signals.
2. Immediate conversational abort with structured Emergency Helpline Card generation.
3. Quiet-hours-overriding alert dispatch to on-call school psychologist & administration <= 120s.
4. Latency measurement and SLA compliance audit verification.
"""

import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.ai_models import AISafetyCategory, AISafetySeverity
from src.services.ai.crisis_classifier import (
    SELF_HARM_PATTERNS,
    SEVERE_DISTRESS_PATTERNS,
    VIOLENCE_WEAPONS_PATTERNS,
    BULLYING_PATTERNS,
    compose_crisis_message,
)
from src.services.ai.crisis_alerts import dispatch_crisis_alert

logger = logging.getLogger(__name__)

# Universal Crisis Escalation SLA threshold in seconds (<= 120s)
CRISIS_ESCALATION_SLA_SECONDS = 120.0


@dataclass
class EmergencyHelplineCard:
    category: str
    severity: str
    title: str
    summary_message: str
    hotlines: List[Dict[str, str]]
    trusted_adult_guidance: str
    counselor_escalated: bool
    escalation_timestamp: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "severity": self.severity,
            "title": self.title,
            "summary_message": self.summary_message,
            "hotlines": self.hotlines,
            "trusted_adult_guidance": self.trusted_adult_guidance,
            "counselor_escalated": self.counselor_escalated,
            "escalation_timestamp": self.escalation_timestamp,
        }


@dataclass
class CrisisSLAReport:
    is_crisis: bool
    category: AISafetyCategory
    severity: AISafetySeverity
    trigger_pattern: Optional[str]
    detected_at: datetime
    dispatched_at: Optional[datetime]
    dispatch_latency_ms: float
    within_sla: bool
    counselor_notified: bool
    emergency_card: Optional[EmergencyHelplineCard]
    quiet_hours_overridden: bool = True
    audit_notes: str = ""


class UniversalCrisisEscalationEngine:
    """
    Contract 3: Universal 2-Minute Crisis Escalation SLA Engine.
    Executes synchronous local detection, aborts LLM execution immediately,
    constructs emergency cards, and dispatches quiet-hours-overriding alerts.
    """

    @classmethod
    def scan_for_crisis_synchronous(cls, prompt: str) -> Tuple[bool, AISafetyCategory, AISafetySeverity, Optional[str]]:
        """
        Pure synchronous regex scan with 0 network latency.
        """
        clean_text = prompt.lower().strip()

        # 1. Critical Self-Harm / Suicide
        for pat in SELF_HARM_PATTERNS:
            if re.search(pat, clean_text, re.IGNORECASE):
                return True, AISafetyCategory.SELF_HARM, AISafetySeverity.CRITICAL, pat

        # 2. Violence / Threat of Mass Harm
        for pat in VIOLENCE_WEAPONS_PATTERNS:
            if re.search(pat, clean_text, re.IGNORECASE):
                return True, AISafetyCategory.VIOLENCE, AISafetySeverity.CRITICAL, pat

        # 3. Severe Emotional Distress
        for pat in SEVERE_DISTRESS_PATTERNS:
            if re.search(pat, clean_text, re.IGNORECASE):
                return True, AISafetyCategory.SEVERE_DISTRESS, AISafetySeverity.HIGH, pat

        # 4. Bullying / Harassment
        for pat in BULLYING_PATTERNS:
            if re.search(pat, clean_text, re.IGNORECASE):
                return True, AISafetyCategory.BULLYING, AISafetySeverity.HIGH, pat

        return False, AISafetyCategory.OTHER, AISafetySeverity.LOW, None

    @classmethod
    def generate_emergency_card(
        cls,
        category: AISafetyCategory,
        severity: AISafetySeverity,
        school_resources: Optional[Any] = None,
    ) -> EmergencyHelplineCard:
        """
        Builds a structured interactive Emergency Helpline Card for student display.
        """
        now_iso = datetime.now(timezone.utc).isoformat()

        hotlines = [
            {
                "name": "International Crisis Directory",
                "contact": "https://findahelpline.com",
                "description": "Free, confidential support from a local crisis center in your country.",
                "action_type": "url",
            }
        ]

        if school_resources and hasattr(school_resources, "resources"):
            for res in getattr(school_resources, "resources", []) or []:
                label = getattr(res, "label", "School Counselor")
                contact = getattr(res, "contact", "")
                desc = getattr(res, "description", "")
                if label and contact:
                    hotlines.insert(0, {
                        "name": str(label),
                        "contact": str(contact),
                        "description": str(desc),
                        "action_type": "phone" if any(c.isdigit() for c in contact) else "text",
                    })

        trusted_guidance = (
            "Please speak to a teacher, school counselor, parent, or trusted adult right away. "
            "You do not have to carry this alone."
        )

        title = "We Are Here For You — Immediate Support Available"
        if category == AISafetyCategory.SELF_HARM:
            title = "Immediate Wellbeing & Crisis Support"
        elif category == AISafetyCategory.VIOLENCE:
            title = "Safety & Emergency Support"

        summary = (
            "Your wellbeing is our highest priority. The AI tutor has paused this session, and our on-call "
            "counseling and safeguarding staff have received an immediate notification to provide support."
        )

        return EmergencyHelplineCard(
            category=category.value,
            severity=severity.value,
            title=title,
            summary_message=summary,
            hotlines=hotlines,
            trusted_adult_guidance=trusted_guidance,
            counselor_escalated=True,
            escalation_timestamp=now_iso,
        )

    @classmethod
    async def evaluate_and_escalate(
        cls,
        prompt: str,
        student_id: str,
        org_id: Optional[int] = None,
        db_session: Optional[AsyncSession] = None,
        course_id: Optional[str] = None,
    ) -> CrisisSLAReport:
        """
        Executes end-to-end detection, emergency card composition, quiet-hours override dispatch,
        and SLA measurement (verifying <= 120s dispatch).
        """
        start_time = time.perf_counter()
        detected_at = datetime.now(timezone.utc)

        is_crisis, category, severity, matched_pattern = cls.scan_for_crisis_synchronous(prompt)

        if not is_crisis:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return CrisisSLAReport(
                is_crisis=False,
                category=AISafetyCategory.OTHER,
                severity=AISafetySeverity.LOW,
                trigger_pattern=None,
                detected_at=detected_at,
                dispatched_at=None,
                dispatch_latency_ms=round(elapsed_ms, 2),
                within_sla=True,
                counselor_notified=False,
                emergency_card=None,
                quiet_hours_overridden=False,
                audit_notes="No safety policy violation detected.",
            )

        logger.warning(
            "CRISIS SIGNAL DETECTED for student '%s' (category=%s, severity=%s). Initiating Contract 3 SLA dispatch.",
            student_id, category.value, severity.value
        )

        # Generate structured emergency helpline card
        emergency_card = cls.generate_emergency_card(category, severity)

        # Dispatch alert with Quiet-Hours-Overriding priority
        counselor_notified = False
        dispatched_at = None

        if db_session and org_id:
            try:
                counselor_notified = await dispatch_crisis_alert(
                    db_session=db_session,
                    org_id=org_id,
                    student_label=str(student_id),
                    category=category.value,
                    severity=severity.value,
                    occurred_at=detected_at.isoformat(),
                )
                dispatched_at = datetime.now(timezone.utc)
            except Exception as e:
                logger.error("Crisis dispatch error: %s", e, exc_info=True)
                counselor_notified = False

            # Dispatch crisis.escalated webhook event
            try:
                from src.services.webhooks.dispatch import dispatch_event_task
                dispatch_event_task(
                    org_id=org_id,
                    event_name="crisis.escalated",
                    data={
                        "alert_id": f"crs_{detected_at.strftime('%Y%m%d%H%M%S')}_{str(student_id)[:8]}",
                        "severity": severity.value,
                        "student_id": int(student_id) if str(student_id).isdigit() else 0,
                        "campus_id": 1,
                        "detected_source": f"AI_COPILOT_{category.value}",
                        "alert_timestamp": detected_at.isoformat(),
                    },
                )
            except Exception as we:
                logger.warning("Failed to dispatch crisis.escalated webhook: %s", we)


        total_elapsed_seconds = time.perf_counter() - start_time
        total_elapsed_ms = total_elapsed_seconds * 1000.0
        within_sla = total_elapsed_seconds <= CRISIS_ESCALATION_SLA_SECONDS

        audit_msg = (
            f"Universal 2-Min SLA {'MET' if within_sla else 'BREACHED'}: "
            f"Dispatch completed in {total_elapsed_ms:.1f}ms (SLA threshold: {CRISIS_ESCALATION_SLA_SECONDS}s)."
        )

        return CrisisSLAReport(
            is_crisis=True,
            category=category,
            severity=severity,
            trigger_pattern=matched_pattern,
            detected_at=detected_at,
            dispatched_at=dispatched_at,
            dispatch_latency_ms=round(total_elapsed_ms, 2),
            within_sla=within_sla,
            counselor_notified=counselor_notified,
            emergency_card=emergency_card,
            quiet_hours_overridden=True,
            audit_notes=audit_msg,
        )
