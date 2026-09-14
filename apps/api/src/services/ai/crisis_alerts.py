"""
Real counselor/principal dispatch for AI safety crisis incidents (M47).

Before this module, a CRITICAL self-harm or violence detection in
`crisis_classifier.py` wrote an `AISafetyIncident` row with
`counselor_notified=True` and emitted a `logger.warning()` -- and that was
the entire "notification". Nobody was actually told. `counselor_notified`
recorded an intention, not an event.

This dispatches a real email to the humans who can act: every active
PSYCHOLOGIST (counselor) and SCHOOL_ADMIN (principal) in the student's org,
resolved from `SMSUserRole` (src/db/sms_identity.py), via the existing
`send_email()` used for every other transactional mail in this codebase.

Two deliberate design rules, both safety-driven:

1. **This must never break the student's response.** A student in crisis
   gets shown the hotline/resources message; an SMTP outage or a missing
   counselor must not turn that into a 500. Every failure path here is
   caught and logged, and the caller is told dispatch failed rather than
   being allowed to raise.

2. **The alert carries triage metadata, not the student's words.** The
   counselor gets who/what/when/severity and a link to follow up -- not the
   raw prompt text. Crisis disclosures are exactly the confidential
   psychologist-record class that sms_counseling.py already protects with
   its 404-never-403 rule; copying that content into an inbox (and into
   mail-server logs, backups and phones) would undo that. The full snippet
   stays in `AISafetyIncident.prompt_snippet`, readable in-app by those
   authorized to see it.

"SLA" here means dispatch is attempted synchronously, inline with
detection, before the request returns -- not queued for a worker that may
be backed up. The incident row's `created_at` is therefore also the
notification time to within the send round-trip, so time-to-notify is
auditable from existing data. There is no breach-monitoring alarm; that
would need a monitoring system this deployment does not have, and is not
claimed here.
"""

import asyncio
import logging
from typing import List, Optional, Sequence

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_identity import SchoolRole, SMSUserRole
from src.db.users import User

logger = logging.getLogger(__name__)

# Roles that receive a crisis alert. PSYCHOLOGIST is the clinical responder;
# SCHOOL_ADMIN is included because a school is accountable for duty-of-care
# and a counselor may be off-shift when a 2am message arrives.
CRISIS_ALERT_ROLES: Sequence[SchoolRole] = (SchoolRole.PSYCHOLOGIST, SchoolRole.SCHOOL_ADMIN)


async def _resolve_alert_recipients(db_session: AsyncSession, org_id: int) -> List[User]:
    """Active counselors + school admins for this org, de-duplicated.

    A user holding both roles must not be mailed twice, so results are keyed
    by user id rather than by grant.
    """
    role_values = [r.value for r in CRISIS_ALERT_ROLES]
    result = await db_session.execute(
        select(User)
        .join(SMSUserRole, SMSUserRole.user_id == User.id)
        .where(
            SMSUserRole.org_id == org_id,
            SMSUserRole.is_active == True,  # noqa: E712
            SMSUserRole.role.in_(role_values),  # type: ignore[attr-defined]
        )
    )
    seen: dict = {}
    for user in result.scalars().all():
        if user.id not in seen and getattr(user, "email", None):
            seen[user.id] = user
    return list(seen.values())


def _build_alert_body(
    *,
    student_label: str,
    category: str,
    severity: str,
    occurred_at: str,
    incident_id: Optional[int],
) -> str:
    """Triage-metadata-only alert body. Deliberately excludes the student's
    own words -- see this module's docstring."""
    incident_ref = f"#{incident_id}" if incident_id is not None else "(unsaved)"
    return f"""
    <div style="font-family:system-ui,-apple-system,Segoe UI,sans-serif;line-height:1.5">
      <h2 style="color:#b91c1c;margin-bottom:4px">Student wellbeing alert</h2>
      <p style="margin-top:0;color:#444">
        An AI tutor conversation triggered a <strong>{severity}</strong> safety
        escalation and was stopped before reaching the model. The student was
        shown crisis support resources immediately.
      </p>
      <table style="border-collapse:collapse;margin:16px 0">
        <tr><td style="padding:4px 12px 4px 0;color:#666">Student</td><td><strong>{student_label}</strong></td></tr>
        <tr><td style="padding:4px 12px 4px 0;color:#666">Category</td><td><strong>{category}</strong></td></tr>
        <tr><td style="padding:4px 12px 4px 0;color:#666">Severity</td><td><strong>{severity}</strong></td></tr>
        <tr><td style="padding:4px 12px 4px 0;color:#666">Detected</td><td>{occurred_at}</td></tr>
        <tr><td style="padding:4px 12px 4px 0;color:#666">Incident</td><td>{incident_ref}</td></tr>
      </table>
      <p style="color:#444">
        The message that triggered this is deliberately not included in this
        email. Open the counseling module in CSG-LMS to review the full
        incident record and follow up with the student.
      </p>
      <p style="color:#888;font-size:12px">
        If you believe this student is in immediate danger, follow your
        school's emergency protocol now rather than waiting for an in-app
        response.
      </p>
    </div>
    """


async def dispatch_crisis_alert(
    *,
    db_session: Optional[AsyncSession],
    org_id: Optional[int],
    student_label: str,
    category: str,
    severity: str,
    occurred_at: str,
    incident_id: Optional[int] = None,
) -> bool:
    """Email every counselor/principal in the org. Returns True only if at
    least one alert was actually accepted by the mail provider.

    Never raises: a crisis-path failure here must not stop the student from
    receiving support resources (see module docstring). Callers use the
    return value to record whether anyone was genuinely notified, so
    `AISafetyIncident.counselor_notified` reflects reality instead of intent.
    """
    if db_session is None or org_id is None:
        logger.error(
            "Crisis alert NOT dispatched (no db_session/org_id): student=%s category=%s severity=%s",
            student_label, category, severity,
        )
        return False

    try:
        recipients = await _resolve_alert_recipients(db_session, org_id)
    except Exception:
        logger.exception("Crisis alert recipient lookup failed for org_id=%s", org_id)
        return False

    if not recipients:
        # Loud: an org with no counselor or admin provisioned means crisis
        # detections land nowhere, which someone needs to fix.
        logger.error(
            "CRISIS ALERT UNDELIVERABLE: org_id=%s has no active PSYCHOLOGIST or "
            "SCHOOL_ADMIN to notify (student=%s category=%s severity=%s)",
            org_id, student_label, category, severity,
        )
        return False

    subject = f"[URGENT] Student wellbeing alert — {category} ({severity})"
    body = _build_alert_body(
        student_label=student_label,
        category=category,
        severity=severity,
        occurred_at=occurred_at,
        incident_id=incident_id,
    )

    # Routed through the shared notification service (M35) rather than
    # emailing directly: the alert is now also persisted, so a counsellor
    # sees it in-app even when mail is down, and a failed send is a visible
    # NotificationDelivery row instead of only a log line. The body above is
    # unchanged -- triage metadata only, never the student's own words.
    from src.services.notifications.service import notify

    result = await notify(
        db_session,
        recipients=recipients,
        kind="crisis_alert",
        title=subject,
        body_html=body,
        org_id=org_id,
        related_kind="safety_incident",
        related_id=incident_id,
    )

    if not result.any_delivered:
        logger.error(
            "CRISIS ALERT UNDELIVERED: all %d recipient sends failed for org_id=%s",
            len(recipients), org_id,
        )
        return False

    logger.warning(
        "Crisis alert dispatched to %d/%d recipients for org_id=%s category=%s severity=%s",
        result.delivered, len(recipients), org_id, category, severity,
    )
    return True
