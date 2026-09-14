"""
The one way this system tells a person something (M35).

Before this, three paths each did it their own way -- crisis alerts, the
absence-streak subscriber, and the weekly parent digest -- and none of them
left a trace. `notify()` is the single entry point they now share:

    resolve recipients -> persist a Notification per person -> attempt
    delivery -> persist what each attempt actually did

Conventions are lifted from `services/ai/crisis_alerts.py`, which got this
right first and is worth reading:

* **It never raises.** Notification is always a side effect of something more
  important -- a student in crisis, a teacher submitting roll-call, a cron
  job. A mail outage must not turn any of those into a 500. Every failure is
  caught, recorded, and reported through the return value.
* **It records what happened, not what was intended.** `NotifyResult.delivered`
  counts sends the provider actually accepted. Callers that store a
  "notified" flag (AISafetyIncident.counselor_notified) can therefore store
  the truth instead of their own optimism.

In-app delivery is recorded as its own channel and always succeeds once the
row is committed -- that is the point of persisting: even when email is
broken, the notification still reaches the person next time they open the
app, and the failed email is visible beside it rather than lost.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Sequence

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.notifications import Notification, NotificationDelivery
from src.db.sms_identity import SchoolRole, SMSUserRole
from src.db.users import User

logger = logging.getLogger(__name__)

CHANNEL_IN_APP = "in_app"
CHANNEL_EMAIL = "email"


@dataclass
class NotifyResult:
    """What actually happened. `delivered` is email sends the provider
    accepted; `created` is notifications persisted (and therefore readable
    in-app even if every email failed)."""

    created: int = 0
    delivered: int = 0
    failed: int = 0
    notification_ids: List[int] = field(default_factory=list)

    @property
    def any_delivered(self) -> bool:
        return self.delivered > 0


async def resolve_users_by_school_role(
    db_session: AsyncSession,
    org_id: int,
    roles: Sequence[SchoolRole],
) -> List[User]:
    """Active holders of any of `roles` in this org, de-duplicated by user.

    A person holding two of the requested roles must not be notified twice,
    so results are keyed by user id rather than by grant.
    """
    role_values = [r.value if isinstance(r, SchoolRole) else str(r) for r in roles]
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
        if user.id not in seen:
            seen[user.id] = user
    return list(seen.values())


async def notify(
    db_session: AsyncSession,
    *,
    recipients: Iterable[User],
    kind: str,
    title: str,
    body_html: str,
    org_id: Optional[int] = None,
    related_kind: Optional[str] = None,
    related_id: Optional[int] = None,
    send_email_channel: bool = True,
) -> NotifyResult:
    """Persist and deliver one notification to each recipient.

    Never raises. Returns a `NotifyResult` describing what genuinely
    happened so callers can record reality rather than intent.
    """
    result = NotifyResult()
    recipient_list = [r for r in recipients if r is not None]
    if not recipient_list:
        logger.warning("notify(kind=%s) called with no recipients -- nothing to do", kind)
        return result

    for user in recipient_list:
        notification: Optional[Notification] = None
        try:
            notification = Notification(
                org_id=org_id,
                recipient_user_id=user.id,
                kind=kind,
                title=title,
                body=body_html,
                related_kind=related_kind,
                related_id=related_id,
            )
            db_session.add(notification)
            await db_session.commit()
            await db_session.refresh(notification)
            result.created += 1
            result.notification_ids.append(notification.id)

            # The in-app copy exists the moment the row is committed.
            db_session.add(
                NotificationDelivery(
                    notification_id=notification.id, channel=CHANNEL_IN_APP, status="sent"
                )
            )
            await db_session.commit()
        except Exception:
            logger.exception(
                "Failed to persist notification kind=%s for user_id=%s", kind, getattr(user, "id", None)
            )
            try:
                await db_session.rollback()
            except Exception:
                logger.exception("Rollback failed after notification persist error")
            result.failed += 1
            continue

        if not send_email_channel:
            continue

        email = getattr(user, "email", None)
        if not email:
            await _record_delivery(
                db_session, notification.id, CHANNEL_EMAIL, "skipped", "recipient has no email address"
            )
            continue

        try:
            # send_email() is synchronous (resend SDK / smtplib). Off-loading
            # to a thread keeps the event loop free while still awaiting real
            # completion, so a caller that needs to know whether the message
            # got out actually finds out. Same approach crisis_alerts.py uses.
            from src.services.email.utils import send_email

            await asyncio.to_thread(send_email, email, title, body_html)
            result.delivered += 1
            await _record_delivery(db_session, notification.id, CHANNEL_EMAIL, "sent", None)
        except Exception as exc:
            result.failed += 1
            logger.exception(
                "Notification email failed (kind=%s, user_id=%s)", kind, getattr(user, "id", None)
            )
            await _record_delivery(
                db_session, notification.id, CHANNEL_EMAIL, "failed", str(exc)[:500]
            )

    logger.info(
        "notify(kind=%s): %d created, %d emailed, %d failed",
        kind, result.created, result.delivered, result.failed,
    )
    return result


async def _record_delivery(
    db_session: AsyncSession,
    notification_id: int,
    channel: str,
    status: str,
    error: Optional[str],
) -> None:
    """Persist a delivery attempt. Swallows its own errors: failing to record
    a failure must not escalate into breaking the caller."""
    try:
        db_session.add(
            NotificationDelivery(
                notification_id=notification_id, channel=channel, status=status, error=error
            )
        )
        await db_session.commit()
    except Exception:
        logger.exception(
            "Could not record %s delivery (%s) for notification %s", channel, status, notification_id
        )
        try:
            await db_session.rollback()
        except Exception:
            pass
