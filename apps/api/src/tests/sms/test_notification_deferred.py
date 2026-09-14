"""
Deferred delivery: the half of the notification fabric that must survive
WORKERS=4 (M35, Lane I).

WHY THIS FILE EXISTS. The first cut of this fabric recorded a quiet-hours
message as 'queued' and nothing ever sent it. A parent whose quiet hours ran
22:00-07:00 would never have received anything raised overnight, while the
delivery log said "queued" indefinitely -- which reads exactly like "on its
way". These tests exist so that defect cannot silently return.

WHY THE RACE TESTS. The API runs with WORKERS=4 in production and arq can
overlap a slow cron run with the next one, so two drains can genuinely reach
the same row at the same moment. The claim is a conditional UPDATE and the row
count decides the winner; a read-then-write would let both workers decide they
were the original and email the same parent twice.
"""

import datetime
from datetime import datetime as dt
from unittest.mock import patch

import pytest
from sqlmodel import select

from src.db.notification_prefs import NotificationDeferred, NotificationQuietHours
from src.db.notifications import Notification
from src.db.sms_identity import SchoolRole, SMSUserRole
from src.db.users import User
from src.services.notifications.deferred_runner import (
    MAX_ATTEMPTS,
    _claim,
    drain_deferred_notifications,
)
from src.services.notifications.dispatch import notify_event

# Reuse the events and templates registered by the fabric test module. Importing
# it is what registers them, so the import is load-bearing rather than stylistic.
from src.tests.sms.test_notification_fabric import ROUTINE_EVENT  # noqa: F401

_UNSET = object()


async def _user(db, id_: int, email=_UNSET) -> User:
    u = User(
        id=id_,
        username=f"df_user{id_}",
        first_name="Test",
        last_name=f"User{id_}",
        email=(f"df_user{id_}@test.com" if email is _UNSET else email),
        password="hashed",
        user_uuid=f"df-uuid-{id_}",
        creation_date=str(dt.now()),
        update_date=str(dt.now()),
    )
    db.add(u)
    await db.commit()
    return u


async def _grant(db, user_id: int, org_id: int, role: SchoolRole) -> None:
    db.add(SMSUserRole(user_id=user_id, org_id=org_id, role=role))
    await db.commit()


async def _held_row(db, org, user, *, due_hour: int = 7) -> NotificationDeferred:
    """A message already sitting in the quiet-hours queue.

    Built through real rows rather than a factory so the shape matches what
    `notify_event()` actually writes.
    """
    notif = Notification(
        org_id=org.id,
        recipient_user_id=user.id,
        kind=ROUTINE_EVENT.key,
        title="Held",
        body="<p>Held.</p>",
    )
    db.add(notif)
    await db.commit()
    await db.refresh(notif)

    row = NotificationDeferred(
        notification_id=notif.id,
        recipient_user_id=user.id,
        org_id=org.id,
        event_key=ROUTINE_EVENT.key,
        channel="email",
        subject="Held message",
        body_html="<p>Held.</p>",
        due_at=datetime.datetime(
            2026, 9, 15, due_hour, 0, tzinfo=datetime.timezone.utc
        ),
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


AFTER_WINDOW = datetime.datetime(2026, 9, 15, 8, 0, tzinfo=datetime.timezone.utc)


class TestDeferralEnqueues:
    @pytest.mark.asyncio
    async def test_deferring_writes_a_real_queue_row_not_just_a_log_line(self, db, org):
        user = await _user(db, 9060)
        await _grant(db, user.id, org.id, SchoolRole.PARENT)
        db.add(
            NotificationQuietHours(
                user_id=user.id, start_minute=22 * 60, end_minute=7 * 60, timezone_name="UTC"
            )
        )
        await db.commit()

        at_2300 = datetime.datetime(2026, 9, 14, 23, 0, tzinfo=datetime.timezone.utc)
        with patch("src.services.email.utils.send_email") as mock_send:
            result = await notify_event(
                db,
                event_key=ROUTINE_EVENT.key,
                org_id=org.id,
                recipients=[user],
                context={"student_name": "Ayesha"},
                now=at_2300,
            )

        assert result.deferred == 1
        mock_send.assert_not_called()

        held = (await db.execute(select(NotificationDeferred))).scalars().all()
        assert len(held) == 1, "a 'queued' delivery needs a queue row behind it"
        assert held[0].sent_at is None
        assert held[0].due_at.hour == 7
        # Rendered at raise time, not at send time: re-rendering tomorrow would
        # describe tomorrow's data in a message about tonight's event.
        assert "Ayesha" in held[0].body_html


class TestDrain:
    @pytest.mark.asyncio
    async def test_nothing_goes_out_before_the_window_closes(self, db, org):
        user = await _user(db, 9061)
        await _held_row(db, org, user, due_hour=7)

        with patch("src.services.email.utils.send_email") as early:
            stats = await drain_deferred_notifications(
                db, now=datetime.datetime(2026, 9, 15, 3, 0, tzinfo=datetime.timezone.utc)
            )
        early.assert_not_called()
        assert stats["sent"] == 0

    @pytest.mark.asyncio
    async def test_the_message_arrives_once_the_window_closes(self, db, org):
        user = await _user(db, 9062, email="parent9062@test.com")
        await _held_row(db, org, user)

        with patch("src.services.email.utils.send_email") as later:
            stats = await drain_deferred_notifications(db, now=AFTER_WINDOW)

        assert stats["sent"] == 1
        assert later.call_count == 1
        assert later.call_args[0][0] == "parent9062@test.com"

    @pytest.mark.asyncio
    async def test_a_drained_message_is_never_sent_twice(self, db, org):
        """arq retries jobs, and a slow cron run can overlap the next one."""
        user = await _user(db, 9063)
        await _held_row(db, org, user)

        with patch("src.services.email.utils.send_email") as mock_send:
            first = await drain_deferred_notifications(db, now=AFTER_WINDOW)
            second = await drain_deferred_notifications(db, now=AFTER_WINDOW)

        assert first["sent"] == 1
        assert second["sent"] == 0
        assert mock_send.call_count == 1

    @pytest.mark.asyncio
    async def test_a_claimed_row_cannot_be_claimed_by_a_second_worker(self, db, org):
        """WORKERS=4: the database decides the winner, not either process."""
        user = await _user(db, 9064)
        row = await _held_row(db, org, user)

        assert await _claim(db, row.id, AFTER_WINDOW) is True
        assert await _claim(db, row.id, AFTER_WINDOW) is False

    @pytest.mark.asyncio
    async def test_a_send_failure_is_retried_rather_than_lost(self, db, org):
        user = await _user(db, 9065)
        await _held_row(db, org, user)

        with patch(
            "src.services.email.utils.send_email", side_effect=RuntimeError("smtp down")
        ):
            stats = await drain_deferred_notifications(db, now=AFTER_WINDOW)
        assert stats["failed"] == 1

        held = (await db.execute(select(NotificationDeferred))).scalars().all()
        assert held[0].sent_at is None
        assert held[0].attempts == 1
        assert held[0].claimed_at is None, "released so a later run retries it"
        assert "smtp down" in (held[0].last_error or "")

        with patch("src.services.email.utils.send_email") as ok:
            stats = await drain_deferred_notifications(db, now=AFTER_WINDOW)
        assert stats["sent"] == 1
        assert ok.call_count == 1

    @pytest.mark.asyncio
    async def test_a_permanently_failing_message_stops_being_retried_but_is_kept(
        self, db, org
    ):
        """'We gave up, and here is why' is information an administrator needs.
        A deleted row is not."""
        user = await _user(db, 9066)
        await _held_row(db, org, user)

        with patch(
            "src.services.email.utils.send_email", side_effect=RuntimeError("bad address")
        ) as mock_send:
            for _ in range(MAX_ATTEMPTS + 3):
                await drain_deferred_notifications(db, now=AFTER_WINDOW)

        assert mock_send.call_count == MAX_ATTEMPTS, "retries are capped"

        held = (await db.execute(select(NotificationDeferred))).scalars().all()
        assert len(held) == 1, "the row survives as the record of the failure"
        assert held[0].sent_at is None
        assert held[0].attempts == MAX_ATTEMPTS
        assert held[0].last_error

    @pytest.mark.asyncio
    async def test_a_recipient_with_no_address_is_skipped_not_retried_forever(
        self, db, org
    ):
        user = await _user(db, 9067, email="")
        await _held_row(db, org, user)

        with patch("src.services.email.utils.send_email") as mock_send:
            stats = await drain_deferred_notifications(db, now=AFTER_WINDOW)

        mock_send.assert_not_called()
        assert stats["skipped"] == 1

    @pytest.mark.asyncio
    async def test_one_bad_message_does_not_cost_the_rest_of_the_batch(self, db, org):
        """The whole point of a queue is that one bad address does not stop
        everyone else's morning mail."""
        bad = await _user(db, 9068, email="")
        good = await _user(db, 9069, email="good9069@test.com")
        await _held_row(db, org, bad)
        await _held_row(db, org, good)

        with patch("src.services.email.utils.send_email") as mock_send:
            stats = await drain_deferred_notifications(db, now=AFTER_WINDOW)

        assert stats["sent"] == 1
        assert stats["skipped"] == 1
        assert mock_send.call_count == 1

    @pytest.mark.asyncio
    async def test_an_empty_queue_is_a_quiet_no_op(self, db, org):
        stats = await drain_deferred_notifications(db)
        assert stats["considered"] == 0
        assert stats["sent"] == 0
