"""
AI Safety Guardrails & Pedagogical Policy Enforcement
=====================================================
Exposes safety screening, sentiment checks, crisis intervention,
and pedagogical integrity rules for AI services.
"""

from src.services.ai.crisis_classifier import (
    SafetyCheckResult,
    classify_prompt_safety,
    log_safety_incident,
    CRISIS_ESCALATION_MESSAGE,
    VIOLENCE_ALERT_MESSAGE,
    BULLYING_ALERT_MESSAGE,
    CHEATING_REDIRECT_MESSAGE,
)

__all__ = [
    "SafetyCheckResult",
    "classify_prompt_safety",
    "log_safety_incident",
    "CRISIS_ESCALATION_MESSAGE",
    "VIOLENCE_ALERT_MESSAGE",
    "BULLYING_ALERT_MESSAGE",
    "CHEATING_REDIRECT_MESSAGE",
]
