"""In-class polls and Q&A for a live class.

PROJECT_DOCS/09_EXPANDED_SYSTEM_ARCHITECTURE_AND_LIVE_CLASSES.md §5 specifies a
classroom sidebar with "CHAT & Q&A" and "POLLS" -- an active poll with
percentages, and a Q&A thread with upvotes. These five tables are the store
for it. They are additive: `SQLModel.metadata.create_all` at boot creates
missing TABLES but never ALTERs an existing one, so new tables need no
Alembic migration (and must not get one -- see db/sms_live_class.py).

TENANCY. `LiveClassSession` carries no org/campus columns of its own, so
every row here is stamped with the (org_id, campus_id) the router DERIVES
from the session's section -> campus -> org, never with anything a client
sent. Unlike most of the older sms_* tables, both columns are NOT NULL:
a live class with no section has no roster, so there is nobody to poll and
nobody to ask a question, and the router refuses those classes rather than
writing a row whose tenant is unknown.

INDEXES. Every index is declared here with an explicit name and NO column
uses `index=True`. Declaring both forms for one column makes `create_all`
emit CREATE INDEX twice, which has already taken this API down.
"""

import datetime
import enum
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


class LivePollStatus(str, enum.Enum):
    """Lifecycle of an in-class poll.

    DRAFT is distinct from CLOSED on purpose: a draft has never been shown to
    the class, so students must not see it at all, while a closed poll stays
    visible with its results. Collapsing them would either publish a
    half-written poll or hide the answers a class just gave.
    """

    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"


class LiveClassPoll(SQLModel, table=True):
    """A poll the host puts to the class during a live session."""

    __tablename__ = "sms_live_class_poll"
    __table_args__ = (
        Index("ix_lc_poll_session_status", "session_id", "status"),
        Index("ix_lc_poll_org_campus", "org_id", "campus_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("sms_live_class_session.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    org_id: int = Field(sa_column=Column(Integer, nullable=False))
    campus_id: int = Field(sa_column=Column(Integer, nullable=False))

    question: str = Field(sa_column=Column(String(500), nullable=False))
    status: LivePollStatus = Field(
        default=LivePollStatus.DRAFT,
        sa_column=Column(
            SAEnum(LivePollStatus, name="sms_live_poll_status", native_enum=False),
            nullable=False,
            default=LivePollStatus.DRAFT,
        ),
    )
    # Who wrote it. Never taken from the request body -- see the router.
    created_by_user_id: int = Field(sa_column=Column(Integer, nullable=False))

    # Set when the poll is actually put to the class, and when it stops
    # accepting answers. A poll that was never activated has neither, and
    # reporting must not pretend otherwise.
    activated_at: Optional[datetime.datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    closed_at: Optional[datetime.datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )

    created_at: datetime.datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False, default=_utcnow),
    )
    updated_at: datetime.datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(
            DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
        ),
    )


class LiveClassPollOption(SQLModel, table=True):
    """One answer the class may choose."""

    __tablename__ = "sms_live_class_poll_option"
    __table_args__ = (
        # Ordering is part of the poll: the host chose it, and a poll whose
        # options reshuffle between two students' screens is not the same
        # question. One option per position, so the order is stable.
        UniqueConstraint("poll_id", "position", name="uq_lc_poll_option_position"),
        Index("ix_lc_poll_option_org_campus", "org_id", "campus_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    poll_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("sms_live_class_poll.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    org_id: int = Field(sa_column=Column(Integer, nullable=False))
    campus_id: int = Field(sa_column=Column(Integer, nullable=False))

    text: str = Field(sa_column=Column(String(300), nullable=False))
    position: int = Field(sa_column=Column(Integer, nullable=False))

    created_at: datetime.datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False, default=_utcnow),
    )


class LiveClassPollResponse(SQLModel, table=True):
    """One student's answer to one poll.

    `uq_lc_poll_response_once` is the whole point of the table: a poll is a
    show of hands, and a student who can answer twice can move the result on
    their own. The router also reads before writing so the caller gets a 409
    rather than an IntegrityError.
    """

    __tablename__ = "sms_live_class_poll_response"
    __table_args__ = (
        UniqueConstraint("poll_id", "student_user_id", name="uq_lc_poll_response_once"),
        Index("ix_lc_poll_response_option", "option_id"),
        Index("ix_lc_poll_response_org_campus", "org_id", "campus_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    poll_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("sms_live_class_poll.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    option_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("sms_live_class_poll_option.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    org_id: int = Field(sa_column=Column(Integer, nullable=False))
    campus_id: int = Field(sa_column=Column(Integer, nullable=False))

    student_user_id: int = Field(sa_column=Column(Integer, nullable=False))

    created_at: datetime.datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False, default=_utcnow),
    )
    updated_at: datetime.datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(
            DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
        ),
    )


class LiveClassQuestion(SQLModel, table=True):
    """A question asked in the class's Q&A thread.

    `author_user_id` is always stored, even for an anonymous question: a
    school has to be able to find out who posted abuse. It is simply not
    SHOWN to the class -- see the router.
    """

    __tablename__ = "sms_live_class_question"
    __table_args__ = (
        Index("ix_lc_question_session", "session_id"),
        Index("ix_lc_question_org_campus", "org_id", "campus_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("sms_live_class_session.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    org_id: int = Field(sa_column=Column(Integer, nullable=False))
    campus_id: int = Field(sa_column=Column(Integer, nullable=False))

    author_user_id: int = Field(sa_column=Column(Integer, nullable=False))
    body: str = Field(sa_column=Column(Text, nullable=False))

    is_anonymous: bool = Field(
        default=False, sa_column=Column(Boolean, nullable=False, default=False)
    )
    # A resolved question stays in the thread; the flag is how the host says
    # "answered" without deleting what a child asked.
    is_resolved: bool = Field(
        default=False, sa_column=Column(Boolean, nullable=False, default=False)
    )
    resolved_by_user_id: Optional[int] = Field(
        default=None, sa_column=Column(Integer, nullable=True)
    )
    resolved_at: Optional[datetime.datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )

    created_at: datetime.datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False, default=_utcnow),
    )


class LiveClassQuestionUpvote(SQLModel, table=True):
    """One student's upvote on one question.

    `uq_lc_question_upvote_once` is what makes the count mean anything: the
    thread is ordered by it, so a student who could upvote repeatedly would
    decide what the whole class sees at the top.
    """

    __tablename__ = "sms_live_class_question_upvote"
    __table_args__ = (
        UniqueConstraint(
            "question_id", "student_user_id", name="uq_lc_question_upvote_once"
        ),
        Index("ix_lc_question_upvote_org_campus", "org_id", "campus_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    question_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("sms_live_class_question.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    org_id: int = Field(sa_column=Column(Integer, nullable=False))
    campus_id: int = Field(sa_column=Column(Integer, nullable=False))

    student_user_id: int = Field(sa_column=Column(Integer, nullable=False))

    created_at: datetime.datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False, default=_utcnow),
    )
