"""
Leads held back for a human to look at before the funnel acts on them.

Why a separate table rather than a column on `AdmissionsLead`: `create_all`
creates missing TABLES but never ALTERs an existing one, so a new column on
`sms_admissions_lead` would silently fail to appear in every environment that
already has that table -- including the running dev database. A new table lands
automatically. This is the same reasoning the grade-history trail used.

Why this exists at all: the AI agents advanced every lead regardless of whether
they had understood the enquiry. A message the intent matcher could make no
sense of was answered with a generic reply anyway. Flagging it instead means a
real person reads it before the school's first words to that family go out.

Rows are append-only in spirit: `resolved_at` is set when a human deals with
it, but the flag itself is never deleted, so "how often is the robot unsure?"
stays answerable.
"""

import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy import Enum as SAEnum
from sqlmodel import Field, SQLModel


class ReviewReason(str, Enum):
    """Why the funnel stopped and asked for a person."""

    # The intent matcher understood too little of the message to answer it.
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    # No channel this deployment can send on reaches this family.
    UNCONTACTABLE = "UNCONTACTABLE"
    # The automated acknowledgement raised; the lead was kept regardless.
    ACKNOWLEDGEMENT_FAILED = "ACKNOWLEDGEMENT_FAILED"


class LeadReviewFlag(SQLModel, table=True):
    """One 'a human should look at this' marker against a lead."""

    __tablename__ = "sms_lead_review_flag"
    __table_args__ = (
        # Composite for the queue read ("open flags, newest first"), which is
        # the only access path that matters. No `index=True` on the columns
        # themselves: SQLAlchemy auto-names a column index
        # `ix_<table>_<column>`, and declaring both forms for one column makes
        # create_all emit CREATE INDEX twice, which takes the whole API down at
        # startup. That has happened in this codebase.
        Index("ix_sms_lead_review_open", "resolved_at", "created_at"),
        Index("ix_sms_lead_review_lead", "lead_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    lead_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("sms_admissions_lead.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    reason: ReviewReason = Field(
        sa_column=Column(
            SAEnum(ReviewReason, name="sms_lead_review_reason", native_enum=False),
            nullable=False,
        )
    )
    # Operator-facing sentence saying what the system could not do and why.
    detail: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    # The heuristic score that triggered a LOW_CONFIDENCE hold, when relevant.
    # Stored so a school can tune the threshold against real traffic instead of
    # guessing.
    confidence: Optional[str] = Field(default=None, sa_column=Column(String(16), nullable=True))
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.datetime.now(datetime.timezone.utc),
        ),
    )
    resolved_at: Optional[datetime.datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    resolved_by_user_id: Optional[int] = Field(
        default=None, sa_column=Column(Integer, nullable=True)
    )
