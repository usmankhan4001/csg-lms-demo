"""
Whether this person gets this message on this channel, now (M35, Lane I).

THE STRUCTURE IS THE GUARANTEE. A safeguarding message cannot be muted, and the
way that is guaranteed is that `resolve_delivery()` returns before it ever
loads a preference row:

    if event.severity is Severity.SAFEGUARDING:
        return Decision(allow=True, ...)          # <- no DB read below this

So a `NotificationPreference` row saying "mute safeguarding.crisis_alert" is not
ignored at delivery time -- it is unreachable. That distinction matters, because
"we check a flag and override it" is one refactor away from "we check a flag",
whereas an early return is visible to anyone reading the function. The same
principle is already stated at the school level in `schemas/sms_settings.py`:
"suppressing a self-harm escalation is not a configuration option".

QUIET HOURS DEFER, THEY DO NOT DROP. A routine message raised at 23:00 is
scheduled for the end of the window, not discarded. A parent who muted nothing
and received nothing has been failed by the system regardless of the hour it
happened at.
"""

from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.notification_prefs import NotificationPreference, NotificationQuietHours
from src.services.notifications.events import NotificationEvent, Severity

logger = logging.getLogger(__name__)

MINUTES_PER_DAY = 24 * 60


@dataclass(frozen=True)
class Decision:
    """Whether to deliver, and if not now, when.

    `reason` is carried into the delivery log so an administrator asking "why
    didn't this parent get it" gets an answer from the record rather than from
    a log file.
    """

    allow: bool
    reason: str
    deferred_until: Optional[datetime.datetime] = None

    @property
    def is_deferred(self) -> bool:
        return self.allow and self.deferred_until is not None


def _resolve_zone(name: str) -> datetime.tzinfo:
    """Never raises. An unrecognised zone falls back to UTC with a warning.

    A school that typed its timezone wrong must not thereby stop every message
    to every family; the window being an hour out is recoverable, silence is
    not.
    """
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, KeyError):
        logger.warning("Unknown timezone %r on quiet hours; treating as UTC.", name)
        return datetime.timezone.utc


def _in_window(minute_of_day: int, start: int, end: int) -> bool:
    """Is this minute inside the window, handling the wrap past midnight?

    A window like 22:00-07:00 (start 1320, end 420) is the ordinary case for
    quiet hours, so it is handled explicitly rather than treated as invalid.
    start == end is read as "no quiet hours", not "all day": the latter would
    silently defer everything forever.
    """
    if start == end:
        return False
    if start < end:
        return start <= minute_of_day < end
    return minute_of_day >= start or minute_of_day < end


def _end_of_window(now_local: datetime.datetime, end_minute: int) -> datetime.datetime:
    """The next moment the window closes, in local time."""
    end_today = now_local.replace(
        hour=end_minute // 60, minute=end_minute % 60, second=0, microsecond=0
    )
    if end_today <= now_local:
        end_today += datetime.timedelta(days=1)
    return end_today


async def _load_preference(
    db_session: AsyncSession,
    user_id: int,
    event: NotificationEvent,
    channel: str,
) -> Optional[bool]:
    """The person's answer, most specific first. None = never expressed one.

    An event-level row beats a category-level row. Absence of both is NOT a
    "no" -- it means unconfigured, and the caller falls back to the event's own
    default rather than guessing.
    """
    rows = (
        await db_session.execute(
            select(NotificationPreference).where(
                NotificationPreference.user_id == user_id,
                NotificationPreference.channel == channel,
            )
        )
    ).scalars().all()

    event_row = next((r for r in rows if r.event_key == event.key), None)
    if event_row is not None:
        return event_row.enabled

    category_row = next(
        (r for r in rows if r.event_key is None and r.category == event.category.value), None
    )
    if category_row is not None:
        return category_row.enabled

    return None


async def resolve_delivery(
    db_session: AsyncSession,
    *,
    user_id: int,
    event: NotificationEvent,
    channel: str,
    now: Optional[datetime.datetime] = None,
) -> Decision:
    """Decide whether to deliver this event to this person on this channel.

    Never raises. A failure to read preferences resolves to DELIVER: the cost of
    an unwanted message is an annoyed parent, the cost of a suppressed one can
    be a child's absence going unreported. Fail toward telling people.
    """
    # ---- The early return that makes safeguarding unmutable. -----------------
    # Nothing below this line runs for a safeguarding event, by design. Do not
    # move preference loading above it.
    if event.severity is Severity.SAFEGUARDING:
        return Decision(allow=True, reason="safeguarding severity cannot be suppressed")

    now = now or datetime.datetime.now(datetime.timezone.utc)

    try:
        preference = await _load_preference(db_session, user_id, event, channel)
    except Exception:
        logger.exception(
            "Could not read notification preferences for user=%s event=%s; delivering.",
            user_id,
            event.key,
        )
        preference = None

    if preference is False:
        return Decision(allow=False, reason=f"recipient muted {event.category.value}")

    if not event.severity.respects_quiet_hours:
        return Decision(allow=True, reason=f"{event.severity.value} severity ignores quiet hours")

    try:
        quiet = (
            await db_session.execute(
                select(NotificationQuietHours).where(NotificationQuietHours.user_id == user_id)
            )
        ).scalars().first()
    except Exception:
        logger.exception(
            "Could not read quiet hours for user=%s; delivering now.", user_id
        )
        quiet = None

    if quiet is None:
        return Decision(allow=True, reason="no quiet hours configured")

    zone = _resolve_zone(quiet.timezone_name)
    now_local = now.astimezone(zone)
    minute_of_day = now_local.hour * 60 + now_local.minute

    start = quiet.start_minute % MINUTES_PER_DAY
    end = quiet.end_minute % MINUTES_PER_DAY

    if not _in_window(minute_of_day, start, end):
        return Decision(allow=True, reason="outside quiet hours")

    deferred_local = _end_of_window(now_local, end)
    return Decision(
        allow=True,
        reason="deferred out of the recipient's quiet hours",
        deferred_until=deferred_local.astimezone(datetime.timezone.utc),
    )


async def set_preference(
    db_session: AsyncSession,
    *,
    user_id: int,
    channel: str,
    enabled: bool,
    event: Optional[NotificationEvent] = None,
    category: Optional[str] = None,
    org_id: Optional[int] = None,
) -> NotificationPreference:
    """Record a person's choice. Refuses to record an ineffective one.

    Writing "muted" against a safeguarding event would leave a row that the
    resolver can never read, and a settings screen would then render a switch
    that does nothing. Refusing the write keeps the stored state and the actual
    behaviour in agreement.
    """
    if event is not None and category is not None:
        raise ValueError("set a preference against an event OR a category, not both")
    if event is None and category is None:
        raise ValueError("a preference needs either an event or a category")

    if event is not None and not event.severity.is_mutable:
        raise ValueError(
            f"{event.key!r} is {event.severity.value} severity and cannot be muted"
        )
    if category is not None and not enabled and category == "safeguarding":
        raise ValueError("safeguarding notifications cannot be muted")

    event_key = event.key if event is not None else None

    existing = (
        await db_session.execute(
            select(NotificationPreference).where(
                NotificationPreference.user_id == user_id,
                NotificationPreference.channel == channel,
                NotificationPreference.event_key == event_key,
                NotificationPreference.category == category,
            )
        )
    ).scalars().first()

    if existing is not None:
        existing.enabled = enabled
        existing.updated_at = datetime.datetime.now(datetime.timezone.utc)
        row = existing
    else:
        row = NotificationPreference(
            user_id=user_id,
            org_id=org_id,
            event_key=event_key,
            category=category,
            channel=channel,
            enabled=enabled,
        )
        db_session.add(row)

    await db_session.commit()
    await db_session.refresh(row)
    return row
