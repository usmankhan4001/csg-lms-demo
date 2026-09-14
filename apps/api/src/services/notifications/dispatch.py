"""
The one call a feature makes to tell people something (M35, Lane I).

    await notify_event(session, event_key="attendance.absence_recorded",
                       org_id=org_id, recipients=guardians,
                       context={"student_name": ..., "date": ...},
                       related_kind="student", related_id=student.id)

Everything between that call and a message arriving -- catalogue lookup,
per-school wording, per-person preferences, quiet hours, duplicate suppression,
delivery recording -- happens here so that a feature adding a notification does
not have to get any of it right a second time.

WHAT THIS ADDS OVER `service.notify()`: `notify()` is the delivery primitive and
stays exactly as it is; it persists a notification and attempts an email and
never raises. It knows nothing about events, preferences or duplicates, and
every caller of it would otherwise have had to. `notify_event()` is the layer
that knows, and it calls `notify()` to do the sending.

TWO PROPERTIES CALLERS DEPEND ON:

* **It never raises.** A register must save even when the mail provider is
  down, a fee must post even when Redis is unreachable. Every failure is caught
  and reported through the return value, matching `notify()` and
  `crisis_alerts.py`.
* **It records what happened, not what was attempted.** `suppressed` counts
  people who asked not to be told; `duplicate` counts people already told.
  Neither is a failure, and conflating either with "sent" would make the
  delivery log useless for answering "why didn't this parent hear from us".
"""

from __future__ import annotations

import datetime
import hashlib
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.notification_prefs import NotificationDeferred, NotificationDispatch
from src.db.notifications import NotificationDelivery
from src.db.sms_identity import SchoolRole, SMSUserRole, StudentGuardian
from src.db.users import User
from src.services.notifications import templates
from src.services.notifications.events import NotificationEvent, Severity, get_event
from src.services.notifications.preferences import resolve_delivery
from src.services.notifications.service import (
    CHANNEL_EMAIL,
    CHANNEL_IN_APP,
    notify,
)

logger = logging.getLogger(__name__)

# Delivery-log vocabulary. 'sent' | 'failed' | 'skipped' already exist in
# db/notifications.py; these two are additions, and both fit the String(16)
# column (the longest is 10 characters).
STATUS_SUPPRESSED = "suppressed"
STATUS_QUEUED = "queued"


@dataclass
class EventResult:
    """What genuinely happened, per outcome.

    `delivered` is email the provider accepted. `created` is notifications
    readable in-app even if every email failed. The rest are reasons a person
    did not receive one, kept distinct because they need different responses:
    suppressed is working as intended, duplicate is working as intended, failed
    is not.
    """

    created: int = 0
    delivered: int = 0
    failed: int = 0
    suppressed: int = 0
    duplicate: int = 0
    deferred: int = 0
    notification_ids: List[int] = field(default_factory=list)
    omitted_fields: List[str] = field(default_factory=list)

    @property
    def any_delivered(self) -> bool:
        return self.delivered > 0

    @property
    def reached_anyone(self) -> bool:
        """In-app counts as reaching someone; email is not the only channel."""
        return self.created > 0


def compose_idempotency_key(
    *,
    event_key: str,
    recipient_user_id: int,
    related_kind: Optional[str],
    related_id: Optional[int],
    dedupe_window_seconds: int,
    now: Optional[datetime.datetime] = None,
) -> str:
    """A stable key for "this message, to this person, about this thing, now-ish".

    The window is bucketed rather than compared against a timestamp so two
    workers racing produce the *same* key and one of them loses the unique
    insert. Comparing "has one been sent in the last 24h" would let both read
    "no" before either wrote.

    With `dedupe_window_seconds = 0` the bucket is the raise itself, so repeated
    raises are all distinct -- correct for something like a message reply, wrong
    for a nightly reminder, which is why the event declares it.
    """
    now = now or datetime.datetime.now(datetime.timezone.utc)
    if dedupe_window_seconds > 0:
        bucket = int(now.timestamp() // dedupe_window_seconds)
    else:
        bucket = now.timestamp()
    raw = f"{event_key}|{recipient_user_id}|{related_kind or ''}|{related_id or ''}|{bucket}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:64]


async def _claim_dispatch(
    db_session: AsyncSession,
    *,
    key: str,
    event_key: str,
    org_id: int,
    recipient_user_id: int,
) -> bool:
    """Try to be the one that sends this. True = you are, False = someone was.

    The insert is attempted first and a unique violation is the proof of a
    duplicate. A read-then-write would let two workers both read "not sent".
    """
    row = NotificationDispatch(
        idempotency_key=key,
        event_key=event_key,
        org_id=org_id,
        recipient_user_id=recipient_user_id,
    )
    try:
        db_session.add(row)
        await db_session.commit()
        return True
    except Exception:
        # Unique violation is the expected path here, not an error worth a
        # stack trace. Anything else that lands here also means "do not send",
        # which is the safe direction for a duplicate check.
        await db_session.rollback()
        logger.debug(
            "Dispatch key already claimed for event=%s user=%s", event_key, recipient_user_id
        )
        return False


async def resolve_guardians_of(
    db_session: AsyncSession, student_user_id: int
) -> List[User]:
    """The guardians linked to one student.

    This resolution is currently open-coded in six places (attendance,
    fee_reminders, parent_digest, ai_consent, messaging, people_provisioning).
    Lane J should use this one so a change to guardian semantics -- say,
    honouring `is_primary_contact` -- happens once.
    """
    links = (
        await db_session.execute(
            select(StudentGuardian).where(StudentGuardian.student_id == student_user_id)
        )
    ).scalars().all()
    if not links:
        return []
    guardian_ids = [link.guardian_user_id for link in links]
    users = (
        await db_session.execute(select(User).where(User.id.in_(guardian_ids)))  # type: ignore[attr-defined]
    ).scalars().all()
    return list(users)


async def resolve_audience(
    db_session: AsyncSession,
    *,
    org_id: int,
    roles: Sequence[SchoolRole],
) -> List[User]:
    """Active holders of any of these roles in this org, de-duplicated.

    Thin wrapper over `service.resolve_users_by_school_role` kept here so Lane J
    has one import surface for recipient resolution.
    """
    from src.services.notifications.service import resolve_users_by_school_role

    return await resolve_users_by_school_role(db_session, org_id, roles)


async def _record(
    db_session: AsyncSession,
    notification_id: Optional[int],
    channel: str,
    status: str,
    error: Optional[str],
) -> None:
    """Record an outcome that `notify()` will not, because it never happened.

    A suppressed or deferred message has no notification row of its own when it
    was stopped before creation, so this is skipped in that case rather than
    inventing a parent row to hang it from.
    """
    if notification_id is None:
        return
    try:
        db_session.add(
            NotificationDelivery(
                notification_id=notification_id, channel=channel, status=status, error=error
            )
        )
        await db_session.commit()
    except Exception:
        logger.exception("Could not record %s delivery for notification %s", status, notification_id)
        try:
            await db_session.rollback()
        except Exception:
            pass


async def _enqueue_deferred(
    db_session: AsyncSession,
    *,
    notification_id: Optional[int],
    recipient_user_id: int,
    org_id: int,
    event_key: str,
    subject: str,
    body_html: str,
    due_at: Optional[datetime.datetime],
) -> bool:
    """Hold a message in the database until its quiet-hours window closes.

    Returns False if it could not be held, so the caller can send it now rather
    than lose it. The subject and body are stored as rendered: re-rendering at
    send time would describe today's data in a message about yesterday's event.
    """
    if notification_id is None or due_at is None:
        return False
    try:
        db_session.add(
            NotificationDeferred(
                notification_id=notification_id,
                recipient_user_id=recipient_user_id,
                org_id=org_id,
                event_key=event_key,
                channel=CHANNEL_EMAIL,
                subject=subject,
                body_html=body_html,
                due_at=due_at,
            )
        )
        await db_session.commit()
        return True
    except Exception:
        logger.exception(
            "Could not enqueue deferred notification %s for user=%s",
            notification_id,
            recipient_user_id,
        )
        try:
            await db_session.rollback()
        except Exception:
            pass
        return False


async def _send_now(
    db_session: AsyncSession,
    notification_id: Optional[int],
    user: User,
    subject: str,
    body_html: str,
) -> bool:
    """Last-resort immediate send. Never raises."""
    email = getattr(user, "email", None)
    if not email:
        await _record(db_session, notification_id, CHANNEL_EMAIL, "skipped", "no email address")
        return False
    try:
        import asyncio

        from src.services.email.utils import send_email

        await asyncio.to_thread(send_email, email, subject, body_html)
        await _record(db_session, notification_id, CHANNEL_EMAIL, "sent", None)
        return True
    except Exception as exc:
        logger.exception("Immediate send failed for notification %s", notification_id)
        await _record(db_session, notification_id, CHANNEL_EMAIL, "failed", str(exc)[:500])
        return False


async def _role_of(
    db_session: AsyncSession, user_id: int, org_id: int
) -> Optional[SchoolRole]:
    """The role to word this message for. First active grant wins.

    A person holding two roles gets the first; templates are addressed to a
    relationship ("your child", "your class") and any of their roles is a true
    relationship. Picking deterministically beats sending two copies.
    """
    try:
        row = (
            await db_session.execute(
                select(SMSUserRole).where(
                    SMSUserRole.user_id == user_id,
                    SMSUserRole.org_id == org_id,
                    SMSUserRole.is_active == True,  # noqa: E712
                )
            )
        ).scalars().first()
    except Exception:
        logger.exception("Could not resolve role for user=%s org=%s", user_id, org_id)
        return None
    if row is None:
        return None
    try:
        return SchoolRole(row.role)
    except ValueError:
        return None


async def notify_event(
    db_session: AsyncSession,
    *,
    event_key: str,
    org_id: int,
    recipients: Optional[Iterable[User]] = None,
    context: Optional[Mapping[str, Any]] = None,
    campus_id: Optional[int] = None,
    related_kind: Optional[str] = None,
    related_id: Optional[int] = None,
    now: Optional[datetime.datetime] = None,
) -> EventResult:
    """Raise one school event to the people who should hear about it.

    `org_id` is REQUIRED and is not defaulted. The pattern `principal.org_id or 1`
    exists eighteen times elsewhere in this codebase and silently writes one
    school's data into another's; a notification carries a child's name to a
    stranger if it gets that wrong, so this raises instead.

    `recipients` may be omitted, in which case the event's `default_audience`
    roles are resolved within `org_id`.

    Never raises.
    """
    result = EventResult()

    if org_id is None:
        # Deliberately loud. See the docstring.
        raise ValueError(
            "notify_event() requires an explicit org_id; there is no safe default "
            "tenant for a message that may name a child"
        )

    try:
        event = get_event(event_key)
    except KeyError:
        logger.exception("Refusing to send unregistered notification event %r", event_key)
        return result

    try:
        recipient_list = (
            [r for r in recipients if r is not None]
            if recipients is not None
            else await resolve_audience(db_session, org_id=org_id, roles=event.default_audience)
        )
    except Exception:
        logger.exception("Could not resolve recipients for event=%s org=%s", event_key, org_id)
        return result

    if not recipient_list:
        logger.warning(
            "notify_event(%s) resolved no recipients for org=%s -- nobody will be told.",
            event_key,
            org_id,
        )
        return result

    ctx: Dict[str, Any] = dict(context or {})
    seen_user_ids: set = set()

    for user in recipient_list:
        user_id = getattr(user, "id", None)
        if user_id is None or user_id in seen_user_ids:
            continue
        seen_user_ids.add(user_id)

        try:
            # ---- duplicate suppression, before any work is done -------------
            key = compose_idempotency_key(
                event_key=event.key,
                recipient_user_id=user_id,
                related_kind=related_kind,
                related_id=related_id,
                dedupe_window_seconds=event.dedupe_window_seconds,
                now=now,
            )
            if event.dedupe_window_seconds > 0:
                claimed = await _claim_dispatch(
                    db_session,
                    key=key,
                    event_key=event.key,
                    org_id=org_id,
                    recipient_user_id=user_id,
                )
                if not claimed:
                    result.duplicate += 1
                    continue

            # ---- may we, and may we now -------------------------------------
            #
            # SCOPE, STATED PLAINLY: preferences and quiet hours currently gate
            # the EMAIL channel only. The in-app copy is always created, on the
            # reasoning that the app is pulled open by the person rather than
            # pushed at them -- muting email is not the same as asking the
            # school to keep a record from you, and an in-app history a parent
            # can scroll back through is the thing that makes a muted email
            # safe to mute.
            #
            # The schema already keys preferences by channel, so gating in-app
            # later is a change here rather than a migration. Until then, do not
            # describe this to a user as "notification preferences" without
            # qualification -- it is email preferences.
            decision = await resolve_delivery(
                db_session, user_id=user_id, event=event, channel=CHANNEL_EMAIL, now=now
            )

            role = await _role_of(db_session, user_id, org_id)
            rendered = await templates.render(
                db_session,
                event,
                org_id=org_id,
                role=role,
                campus_id=campus_id,
                context=ctx,
            )
            for name in rendered.omitted_fields:
                if name not in result.omitted_fields:
                    result.omitted_fields.append(name)

            # ---- send, or record precisely why we did not -------------------
            send_email = decision.allow and not decision.is_deferred

            one = await notify(
                db_session,
                recipients=[user],
                kind=event.key,
                title=rendered.subject,
                body_html=rendered.body_html,
                org_id=org_id,
                related_kind=related_kind,
                related_id=related_id,
                send_email_channel=send_email,
            )

            result.created += one.created
            result.delivered += one.delivered
            result.failed += one.failed
            result.notification_ids.extend(one.notification_ids)

            notification_id = one.notification_ids[0] if one.notification_ids else None

            if not decision.allow:
                result.suppressed += 1
                await _record(
                    db_session, notification_id, CHANNEL_EMAIL, STATUS_SUPPRESSED, decision.reason
                )
            elif decision.is_deferred:
                result.deferred += 1
                # Enqueue FIRST, then record. If the enqueue fails there is
                # nothing to drain later, and a delivery log reading "queued"
                # with no queue row behind it is a message that will never
                # arrive while appearing to be on its way.
                enqueued = await _enqueue_deferred(
                    db_session,
                    notification_id=notification_id,
                    recipient_user_id=user_id,
                    org_id=org_id,
                    event_key=event.key,
                    subject=rendered.subject,
                    body_html=rendered.body_html,
                    due_at=decision.deferred_until,
                )
                if enqueued:
                    await _record(
                        db_session,
                        notification_id,
                        CHANNEL_EMAIL,
                        STATUS_QUEUED,
                        f"{decision.reason}; due {decision.deferred_until.isoformat()}"
                        if decision.deferred_until
                        else decision.reason,
                    )
                else:
                    # Could not hold it for later, so send it now. A routine
                    # message arriving at an awkward hour beats one that never
                    # arrives at all.
                    logger.warning(
                        "Could not defer %s for user=%s; sending immediately rather "
                        "than dropping it.",
                        event.key,
                        user_id,
                    )
                    result.deferred -= 1
                    sent = await _send_now(
                        db_session, notification_id, user, rendered.subject, rendered.body_html
                    )
                    if sent:
                        result.delivered += 1
                    else:
                        result.failed += 1

        except Exception:
            # One recipient's failure must never abort the rest of the family,
            # the class, or the school.
            logger.exception(
                "notify_event(%s) failed for user=%s; continuing with the rest.",
                event_key,
                user_id,
            )
            result.failed += 1
            try:
                await db_session.rollback()
            except Exception:
                pass

    logger.info(
        "notify_event(%s) org=%s: %d created, %d emailed, %d suppressed, %d duplicate, "
        "%d deferred, %d failed",
        event_key,
        org_id,
        result.created,
        result.delivered,
        result.suppressed,
        result.duplicate,
        result.deferred,
        result.failed,
    )

    if event.severity is Severity.SAFEGUARDING and not result.reached_anyone:
        logger.error(
            "SAFEGUARDING NOTIFICATION REACHED NOBODY: event=%s org=%s recipients=%d",
            event_key,
            org_id,
            len(recipient_list),
        )

    return result
