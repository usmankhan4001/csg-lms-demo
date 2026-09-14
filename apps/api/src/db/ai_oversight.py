"""
Teacher oversight of AI tutoring (M46).

Two additive tables, picked up by `SQLModel.metadata.create_all` at app
startup (`src/core/events/database.py`) exactly like every other sms_*/ai_*
model in this codebase -- never through Alembic.

`AITutorAccessBlock` is the kill switch: a durable, auditable record that a
named teacher/admin switched AI tutoring off for one student or a whole
section. It is deliberately a ROW rather than a boolean column on some
existing table, because "who turned this off, when, and why" is the part a
school actually needs when a parent asks.

`AITutorTranscript` is the chat audit log. Nothing in this codebase persisted
tutor conversations before it -- `AISafetyIncident` stores a prompt snippet,
but ONLY for messages that tripped the safety classifier, so a teacher had no
way to see ordinary sessions. Confirmed by grep: no AIChat/transcript/message
table existed anywhere in src/db/.
"""

import datetime
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlmodel import Field, SQLModel


def get_utc_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


class AITutorAccessBlock(SQLModel, table=True):
    """An active row = AI tutoring is switched OFF for that student/section.

    Scope is expressed by which column is set: `student_id` for one learner,
    `section_id` for a whole class. A block is lifted by setting
    `is_active=False` rather than deleting the row, so the history of who
    blocked and who restored survives -- the same soft-revoke convention
    `SMSUserRole` uses.
    """

    __tablename__ = "ai_tutor_access_block"
    __table_args__ = (
        Index("ix_ai_block_student_active", "student_id", "is_active"),
        Index("ix_ai_block_section_active", "section_id", "is_active"),
        {"extend_existing": True},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    org_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True, index=True))
    # Exactly one of these is set. Enforced in the service layer rather than a
    # CHECK constraint, so the rule lives next to the error message a user sees.
    student_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True, index=True))
    section_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True, index=True))

    blocked_by_user_id: int = Field(sa_column=Column(Integer, nullable=False))
    reason: Optional[str] = Field(default=None, sa_column=Column(String(500), nullable=True))
    is_active: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, default=True))

    created_at: datetime.datetime = Field(
        default_factory=get_utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False, default=get_utc_now),
    )
    lifted_by_user_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))
    lifted_at: Optional[datetime.datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )


class AITutorTranscript(SQLModel, table=True):
    """One student turn plus what the tutor did with it.

    Stores the student's message and an outcome marker rather than the full
    streamed reply: the reply is reconstructable pedagogy, whereas what a
    teacher reviewing oversight actually needs is what was asked, whether it
    was blocked, and why.
    """

    __tablename__ = "ai_tutor_transcript"
    __table_args__ = (
        Index("ix_ai_transcript_student_time", "student_id", "created_at"),
        Index("ix_ai_transcript_section", "section_id"),
        {"extend_existing": True},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    org_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True, index=True))
    student_id: int = Field(sa_column=Column(Integer, nullable=False, index=True))
    section_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True, index=True))
    course_id: Optional[str] = Field(default=None, sa_column=Column(String(255), nullable=True))

    prompt: str = Field(sa_column=Column(Text, nullable=False))
    # 'answered' | 'blocked_safety' | 'blocked_offtopic' | 'blocked_disabled'
    # | 'blocked_rate_limit' | 'blocked_session_limit'
    outcome: str = Field(sa_column=Column(String(40), nullable=False, index=True))
    detail: Optional[str] = Field(default=None, sa_column=Column(String(255), nullable=True))

    created_at: datetime.datetime = Field(
        default_factory=get_utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False, default=get_utc_now),
    )
