"""
Notifications & Alerting (M35) + Communication Hub (M13).

Additive tables, picked up by `SQLModel.metadata.create_all` at app startup
via `import_all_models()` walking `src/db` -- never Alembic, matching every
other sms_*/ai_* model here.

WHY M35 EXISTS: three independent code paths already emailed people --
`services/ai/crisis_alerts.py` (counsellors), the absence-streak subscriber
in `services/sms/attendance.py` (guardians), and `services/ai/parent_digest.py`
(weekly digest). Each re-implemented "resolve recipients, render HTML, send,
never raise", and none of them PERSISTED anything. So nobody could see what
the school had sent, none of it was readable in-app, and a failed send
existed only as a log line on a server nobody reads. `Notification` makes the
message a record; `NotificationDelivery` makes the *attempt* a record, which
is the part that turns a silent failure into something a person can see.

M13 is deliberately in this same module: a message is just a notification
with a reply, and threading them separately would have meant two unread
counts a user has to reconcile.
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
)
from sqlmodel import Field, SQLModel


def get_utc_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


# ---------------------------------------------------------------- M35


class Notification(SQLModel, table=True):
    """One notification addressed to one person.

    Fan-out is modelled as one row per recipient rather than one row with a
    recipient list: unread state, and the moment someone read it, are
    per-person facts. A shared row would need a side table to express them
    anyway.
    """

    __tablename__ = "sms_notification"
    __table_args__ = (
        Index("ix_notification_recipient_read", "recipient_user_id", "is_read"),
        Index("ix_notification_recipient_time", "recipient_user_id", "created_at"),
        {"extend_existing": True},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    org_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True, index=True))
    recipient_user_id: int = Field(
        sa_column=Column(Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    )

    # Free-form rather than an enum on purpose: new alert kinds get added by
    # feature work, and a migration-free string keeps that from becoming a
    # schema change on a table that is append-heavy.
    kind: str = Field(sa_column=Column(String(64), nullable=False, index=True))
    title: str = Field(sa_column=Column(String(255), nullable=False))
    body: str = Field(sa_column=Column(Text, nullable=False))

    # What this is about, so the UI can deep-link without a join table per
    # kind. e.g. ("student", 42) or ("message_thread", 7).
    related_kind: Optional[str] = Field(default=None, sa_column=Column(String(64), nullable=True))
    related_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))

    is_read: bool = Field(default=False, sa_column=Column(Boolean, nullable=False, default=False))
    read_at: Optional[datetime.datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    created_at: datetime.datetime = Field(
        default_factory=get_utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False, default=get_utc_now, index=True),
    )


class NotificationDelivery(SQLModel, table=True):
    """One attempt to deliver a notification over one channel.

    Separate from `Notification` because in-app delivery always succeeds (the
    row IS the delivery) while email can fail, and a failure needs somewhere
    to live other than a log file. `error` is truncated rather than omitted:
    "Resend rejected the recipient address" is the difference between a typo
    and an outage, and an admin should be able to tell which without shell
    access.
    """

    __tablename__ = "sms_notification_delivery"
    __table_args__ = (
        Index("ix_notification_delivery_notification", "notification_id"),
        Index("ix_notification_delivery_status", "status"),
        {"extend_existing": True},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    notification_id: int = Field(
        sa_column=Column(
            Integer, ForeignKey("sms_notification.id", ondelete="CASCADE"), nullable=False, index=True
        )
    )
    channel: str = Field(sa_column=Column(String(32), nullable=False))  # 'in_app' | 'email'
    status: str = Field(sa_column=Column(String(16), nullable=False))  # 'sent' | 'failed' | 'skipped'
    error: Optional[str] = Field(default=None, sa_column=Column(String(500), nullable=True))
    attempted_at: datetime.datetime = Field(
        default_factory=get_utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False, default=get_utc_now),
    )


# ---------------------------------------------------------------- M13


class MessageThread(SQLModel, table=True):
    """A conversation, optionally *about* a particular student.

    `about_student_id` is the safeguarding anchor, not decoration: a
    parent-teacher thread exists because of a specific child, and recording
    which one is what lets the access rule be re-checked later rather than
    only at creation time.
    """

    __tablename__ = "sms_message_thread"
    __table_args__ = (
        Index("ix_message_thread_org", "org_id"),
        Index("ix_message_thread_student", "about_student_id"),
        {"extend_existing": True},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    org_id: int = Field(sa_column=Column(Integer, nullable=False, index=True))
    subject: str = Field(sa_column=Column(String(255), nullable=False))
    created_by_user_id: int = Field(
        sa_column=Column(Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    )
    about_student_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))
    created_at: datetime.datetime = Field(
        default_factory=get_utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False, default=get_utc_now),
    )
    last_message_at: datetime.datetime = Field(
        default_factory=get_utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False, default=get_utc_now, index=True),
    )


class ThreadParticipant(SQLModel, table=True):
    """Membership. Unread count is derived from `last_read_at` vs message
    timestamps rather than stored, so it cannot drift out of sync with the
    messages themselves."""

    __tablename__ = "sms_thread_participant"
    __table_args__ = (
        Index("ix_thread_participant_user", "user_id"),
        Index("ix_thread_participant_thread", "thread_id"),
        {"extend_existing": True},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    thread_id: int = Field(
        sa_column=Column(
            Integer, ForeignKey("sms_message_thread.id", ondelete="CASCADE"), nullable=False, index=True
        )
    )
    user_id: int = Field(
        sa_column=Column(Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    last_read_at: Optional[datetime.datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )


class Message(SQLModel, table=True):
    __tablename__ = "sms_message"
    __table_args__ = (
        Index("ix_message_thread_time", "thread_id", "created_at"),
        {"extend_existing": True},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    thread_id: int = Field(
        sa_column=Column(
            Integer, ForeignKey("sms_message_thread.id", ondelete="CASCADE"), nullable=False, index=True
        )
    )
    sender_user_id: int = Field(
        sa_column=Column(Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    )
    body: str = Field(sa_column=Column(Text, nullable=False))
    created_at: datetime.datetime = Field(
        default_factory=get_utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False, default=get_utc_now),
    )
