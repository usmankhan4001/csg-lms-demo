"""
Delivering the messages that quiet hours held back (M35, Lane I).

WHY THIS FILE EXISTS AT ALL -- and it is the correction to a real defect in the
first cut of this fabric: `notify_event()` recorded a deferred message as
`queued` and nothing ever sent it. A parent with quiet hours of 22:00-07:00
would never have received anything raised overnight, and the delivery log would
have said "queued" indefinitely, which reads exactly like "on its way". A
message that is silently never sent is worse than one sent at an awkward hour,
and the delivery log claiming otherwise is worse still.

WHY IT IS A CRON JOB AND NOT A TIMER. The API runs with **WORKERS=4** in
production. Anything held inside a process -- an `asyncio.sleep` task, an
in-memory heap, the in-process event bus in `core/events` -- lives in one worker
of four and dies on the next deploy. Three quarters of the deferred mail would
simply never be attempted, and which quarter survived would depend on which
worker happened to serve the request. The queue is therefore a database table
and the drain is an arq cron job, both of which every worker shares.

CLAIMING, NOT LOCKING. arq's own scheduler can overlap a slow run with the next
one, and there is no guarantee only one worker drains. So a row is claimed with
a conditional UPDATE (`WHERE claimed_at IS NULL`) and the row count decides the
winner: whoever's UPDATE affected the row sends it. A read-then-write would let
two workers both read "unclaimed" and both email the same parent, which is the
duplicate this fabric exists to prevent.
"""

from __future__ import annotations

import asyncio
import datetime
import logging
from typing import Dict, List, Optional

from sqlalchemy import update
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.notification_prefs import NotificationDeferred
from src.db.users import User

logger = logging.getLogger(__name__)

# A message whose send fails this many times stops being retried. It stays in
# the table with its last_error rather than being deleted, because "we gave up"
# is information an administrator needs and a missing row is not.
MAX_ATTEMPTS = 5

# Cap per run so one enormous backlog cannot monopolise the worker.
BATCH_LIMIT = 200


async def _claim(db_session: AsyncSession, row_id: int, now: datetime.datetime) -> bool:
    """Claim one row for sending. True = it is ours, False = someone else's.

    The WHERE clause carries the precondition, so the database decides the
    winner rather than this process's view of a moment ago.
    """
    try:
        result = await db_session.execute(
            update(NotificationDeferred)
            .where(
                NotificationDeferred.id == row_id,
                NotificationDeferred.claimed_at.is_(None),  # type: ignore[union-attr]
                NotificationDeferred.sent_at.is_(None),  # type: ignore[union-attr]
            )
            .values(claimed_at=now)
        )
        await db_session.commit()
        return (result.rowcount or 0) > 0
    except Exception:
        logger.exception("Could not claim deferred notification %s", row_id)
        try:
            await db_session.rollback()
        except Exception:
            pass
        return False


async def _release(db_session: AsyncSession, row_id: int, error: Optional[str]) -> None:
    """Hand a failed row back so a later run can retry it."""
    try:
        row = await db_session.get(NotificationDeferred, row_id)
        if row is None:
            return
        row.attempts += 1
        row.last_error = (error or "")[:500] or None
        # Released only while retries remain. At the cap it stays claimed so the
        # drain stops picking it up, and the row survives as the record of why.
        row.claimed_at = None if row.attempts < MAX_ATTEMPTS else row.claimed_at
        await db_session.commit()
    except Exception:
        logger.exception("Could not release deferred notification %s", row_id)
        try:
            await db_session.rollback()
        except Exception:
            pass


async def drain_deferred_notifications(
    db_session: AsyncSession,
    *,
    now: Optional[datetime.datetime] = None,
    limit: int = BATCH_LIMIT,
) -> Dict[str, int]:
    """Send every held message whose quiet-hours window has now closed.

    Never raises. One recipient's failure never aborts the batch -- the whole
    point of a queue is that a single bad address does not cost everyone else
    their morning mail.
    """
    now = now or datetime.datetime.now(datetime.timezone.utc)
    stats = {"considered": 0, "sent": 0, "failed": 0, "skipped": 0, "claimed_by_other": 0}

    try:
        due: List[NotificationDeferred] = (
            (
                await db_session.execute(
                    select(NotificationDeferred)
                    .where(
                        NotificationDeferred.due_at <= now,
                        NotificationDeferred.sent_at.is_(None),  # type: ignore[union-attr]
                        NotificationDeferred.claimed_at.is_(None),  # type: ignore[union-attr]
                        NotificationDeferred.attempts < MAX_ATTEMPTS,
                    )
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )
    except Exception:
        logger.exception("Could not load deferred notifications; skipping this run.")
        return stats

    for row in due:
        stats["considered"] += 1
        row_id = row.id
        if row_id is None:
            continue

        if not await _claim(db_session, row_id, now):
            stats["claimed_by_other"] += 1
            continue

        try:
            user = await db_session.get(User, row.recipient_user_id)
            email = getattr(user, "email", None) if user else None
            if not email:
                stats["skipped"] += 1
                await _release(db_session, row_id, "recipient has no email address")
                continue

            from src.services.email.utils import send_email

            await asyncio.to_thread(send_email, email, row.subject, row.body_html)

            fresh = await db_session.get(NotificationDeferred, row_id)
            if fresh is not None:
                fresh.sent_at = datetime.datetime.now(datetime.timezone.utc)
                fresh.attempts += 1
                await db_session.commit()
            stats["sent"] += 1

        except Exception as exc:
            stats["failed"] += 1
            logger.exception(
                "Deferred notification %s failed to send; will retry.", row_id
            )
            try:
                await db_session.rollback()
            except Exception:
                pass
            await _release(db_session, row_id, str(exc))

    if stats["considered"]:
        logger.info(
            "drain_deferred_notifications: %d considered, %d sent, %d failed, "
            "%d skipped, %d already claimed",
            stats["considered"],
            stats["sent"],
            stats["failed"],
            stats["skipped"],
            stats["claimed_by_other"],
        )
    return stats


async def deliver_deferred_notifications(ctx: Optional[dict] = None) -> Dict[str, int]:
    """arq job: drain the quiet-hours queue.

    Registered as a cron in `src/core/worker.py`. Opens its own session because
    jobs run outside request scope, matching `send_fee_reminders`.
    """
    from src.core.events.database import _async_session_factory

    async with _async_session_factory() as session:
        return await drain_deferred_notifications(session)
