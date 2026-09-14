"""
Notification preferences, template overrides and dispatch ledger (M35, Lane I).

Additive tables, picked up by `SQLModel.metadata.create_all` at app startup via
`import_all_models()` walking `src/db` -- never Alembic, matching `db/notifications.py`
and every other sms_*/ai_* model here. No column is added to an existing table,
so no migration is required.

WHY THESE EXIST: `db/notifications.py` records what was SENT. It has nowhere to
record what a person asked NOT to be sent, what a school wants its own messages
to SAY, or whether we have already told someone this exact thing. Without those
three, wiring the school's events to the notification service (Lane J) would
mean either spamming families with everything or hard-coding one voice for every
school -- and a retried background job would mail a parent twice about one
absence.

THE ONE RULE THAT SHAPES ALL OF THIS: a person can mute routine noise and can
never mute a safeguarding message. That is enforced in
`services/notifications/preferences.py` by checking severity BEFORE these rows
are ever loaded, so a mute row for a safeguarding event is not "ignored at
delivery time" -- it is unreachable. `NotificationSettings` in
schemas/sms_settings.py already states the same principle for the school-level
switches ("suppressing a self-harm escalation is not a configuration option");
this is the per-user half of it.
"""

import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlmodel import Field, SQLModel


def get_utc_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


class NotificationPreference(SQLModel, table=True):
    """One person's answer to "do you want this kind of message on this channel".

    Absence of a row means "not configured", which resolves to the event's own
    default rather than to a guess -- the same reason
    `services/sms/settings.py` distinguishes an unset group from an empty one.
    A row is only ever written when someone actually expresses a preference.

    `event_key` is the specific event (`attendance.absence_recorded`). A row
    with `event_key = NULL` applies to the whole `category` instead, so a parent
    can mute "attendance" without enumerating every attendance event that will
    ever exist. The specific row wins over the category row.
    """

    __tablename__ = "sms_notification_preference"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "event_key",
            "category",
            "channel",
            name="uq_sms_notification_preference_scope",
        ),
        {"extend_existing": True},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(
        sa_column=Column(
            Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True
        )
    )
    # Kept for scoping and audit. A preference is a per-person fact, but which
    # school it was expressed at matters when someone holds a role at two.
    org_id: Optional[int] = Field(
        default=None, sa_column=Column(Integer, nullable=True, index=True)
    )

    # Exactly one of these is set. Enforced in the service rather than by a DB
    # constraint, because the unique key above already has to include both
    # columns and a CHECK across them differs between SQLite and Postgres.
    event_key: Optional[str] = Field(default=None, sa_column=Column(String(64), nullable=True))
    category: Optional[str] = Field(default=None, sa_column=Column(String(32), nullable=True))

    channel: str = Field(sa_column=Column(String(32), nullable=False))  # 'in_app' | 'email'
    enabled: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, default=True))

    updated_at: datetime.datetime = Field(
        default_factory=get_utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False, default=get_utc_now),
    )


class NotificationQuietHours(SQLModel, table=True):
    """When this person would rather not be disturbed.

    Stored as minutes-from-midnight in a named IANA zone rather than as a UTC
    window, because "don't wake me at 10pm" is a statement about the recipient's
    own clock and must survive both a server in another region and a daylight
    saving change.

    A window that wraps past midnight (start 1320 = 22:00, end 420 = 07:00) is
    the normal case, not an edge case, and is handled explicitly in
    `preferences.py`.

    Quiet hours DELAY a routine message to the end of the window; they never
    drop it. Silently discarding a message a parent expected is worse than
    delivering it late, and a safeguarding message ignores the window entirely.
    """

    __tablename__ = "sms_notification_quiet_hours"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_sms_notification_quiet_hours_user"),
        {"extend_existing": True},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(
        sa_column=Column(
            Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True
        )
    )
    start_minute: int = Field(sa_column=Column(Integer, nullable=False))
    end_minute: int = Field(sa_column=Column(Integer, nullable=False))
    # IANA name, e.g. "Asia/Karachi". Resolved with stdlib zoneinfo; an
    # unrecognised zone falls back to UTC with a warning rather than raising,
    # because a bad timezone string must not stop a message reaching a family.
    timezone_name: str = Field(default="UTC", sa_column=Column(String(64), nullable=False))

    updated_at: datetime.datetime = Field(
        default_factory=get_utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False, default=get_utc_now),
    )


class NotificationTemplateOverride(SQLModel, table=True):
    """A school's own wording for one event, for one role.

    A school's voice is its own: the built-in templates are a starting point,
    not a house style every school must adopt. An override is resolved
    campus-first then org, mirroring exactly how `services/sms/settings.py`
    resolves a settings group, so the two behave the same way for an
    administrator who has learned one of them.

    Storing subject and body separately rather than one blob keeps a school
    from having to re-author the body to fix a subject line typo.
    """

    __tablename__ = "sms_notification_template"
    __table_args__ = (
        UniqueConstraint(
            "org_id", "campus_id", "event_key", "role", name="uq_sms_notification_template_scope"
        ),
        Index("ix_sms_notification_template_lookup", "org_id", "event_key"),
        {"extend_existing": True},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    org_id: int = Field(sa_column=Column(Integer, nullable=False))
    # NULL = applies to the whole organisation. A campus row overrides it.
    campus_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))
    event_key: str = Field(sa_column=Column(String(64), nullable=False))
    # NULL = applies to every role that has no more specific row.
    role: Optional[str] = Field(default=None, sa_column=Column(String(32), nullable=True))

    subject: str = Field(sa_column=Column(String(255), nullable=False))
    body_html: str = Field(sa_column=Column(Text, nullable=False))

    updated_by_user_id: Optional[int] = Field(
        default=None, sa_column=Column(Integer, nullable=True)
    )
    updated_at: datetime.datetime = Field(
        default_factory=get_utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False, default=get_utc_now),
    )


class NotificationDeferred(SQLModel, table=True):
    """A message held until the end of someone's quiet hours.

    WHY A TABLE AND NOT A TIMER: the API runs with WORKERS=4 in production, so
    anything held in a process -- an asyncio task, an in-memory heap, the
    in-process event bus -- exists in one worker out of four and dies with it on
    the next deploy. A parent whose quiet hours run 22:00-07:00 would simply
    never hear about anything raised overnight, and the delivery log would say
    "queued" forever, which reads as working.

    The row is the queue, and the arq cron job `deliver_deferred_notifications`
    is the only thing that drains it. Both of those are shared across every
    worker because both are backed by the database rather than by a process.

    `claimed_at` exists so two workers draining the same minute cannot both send
    the same message: the drain claims rows before sending, and the claim is a
    conditional UPDATE rather than a read-then-write.
    """

    __tablename__ = "sms_notification_deferred"
    __table_args__ = (
        Index("ix_sms_notification_deferred_due", "due_at", "sent_at"),
        {"extend_existing": True},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    notification_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("sms_notification.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    recipient_user_id: int = Field(
        sa_column=Column(
            Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True
        )
    )
    org_id: int = Field(sa_column=Column(Integer, nullable=False, index=True))
    event_key: str = Field(sa_column=Column(String(64), nullable=False))
    channel: str = Field(sa_column=Column(String(32), nullable=False))

    # Denormalised rather than re-rendered at send time. Re-rendering would use
    # tomorrow's data to describe yesterday's event -- "your child was absent"
    # could silently become a different sentence between raising and sending.
    subject: str = Field(sa_column=Column(String(255), nullable=False))
    body_html: str = Field(sa_column=Column(Text, nullable=False))

    due_at: datetime.datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    claimed_at: Optional[datetime.datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    sent_at: Optional[datetime.datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    attempts: int = Field(default=0, sa_column=Column(Integer, nullable=False, default=0))
    last_error: Optional[str] = Field(default=None, sa_column=Column(String(500), nullable=True))

    created_at: datetime.datetime = Field(
        default_factory=get_utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False, default=get_utc_now),
    )


class NotificationDispatch(SQLModel, table=True):
    """Proof that this exact message has already been raised for this person.

    The reason this table exists rather than a Redis key: arq retries a failed
    job, a cron job can overlap a slow previous run, and a teacher can submit
    roll-call twice. Any of those would otherwise email a parent twice about one
    absence. A cache that expires would make the guarantee depend on how long
    the retry took; a row with a unique key does not.

    The unique constraint is the mechanism, not a safety net: the insert is
    attempted FIRST and a collision is what proves the duplicate, so two workers
    racing on the same event cannot both decide they are the original.
    """

    __tablename__ = "sms_notification_dispatch"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_sms_notification_dispatch_key"),
        {"extend_existing": True},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    # Deterministic hash of (event, recipient, subject-of-the-event, window).
    # Composed in services/notifications/dispatch.py.
    idempotency_key: str = Field(sa_column=Column(String(128), nullable=False, index=True))
    event_key: str = Field(sa_column=Column(String(64), nullable=False))
    org_id: int = Field(sa_column=Column(Integer, nullable=False, index=True))
    recipient_user_id: int = Field(
        sa_column=Column(
            Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True
        )
    )
    notification_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))
    created_at: datetime.datetime = Field(
        default_factory=get_utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False, default=get_utc_now, index=True),
    )
