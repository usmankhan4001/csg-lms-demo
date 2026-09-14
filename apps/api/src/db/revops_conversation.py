"""
RevOps conversation memory, nurture state and outbound delivery records.

Three additive tables that turn the RevOps AI services from request-scoped
text generators into a funnel that remembers and runs on its own:

- `LeadConversationTurn` (M29 Conversation Memory). Until this existed the
  SDR agent answered every message cold: `generate_sdr_response` received only
  the current message, so a parent who had already been told the fee structure
  got told again. Turns are stored per lead, both directions, so the next
  reply can be grounded in what was actually said.

- `LeadNurtureState`. One row per lead tracking which drip stage it is on and
  when the next touch falls due. Without it a "4-stage nurture sequence" was
  a list of strings returned to whoever asked -- nothing recorded that stage 2
  was owed on day 3, so nothing could ever send it.

- `LeadOutboundTouch`. A delivery record per attempted outbound message,
  carrying status and the failure reason. This mirrors the principle in
  `NotificationDelivery` (a failed send must be a visible row, not a swallowed
  log line), but it has to be a separate table: `Notification.recipient_user_id`
  is a non-nullable FK to `user.id`, and a lead is a prospective parent who
  has no user account. Routing lead outbound through the notification service
  is therefore not possible without making that column nullable, which would
  weaken a constraint the internal notification path relies on.

All three are picked up by `SQLModel.metadata.create_all` via
`import_all_models()` walking `src/db`, matching every other sms_*/ai_* table
here. No Alembic.
"""

import datetime
from enum import Enum
from typing import Any, Dict, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy import Enum as SAEnum
from sqlmodel import Field, SQLModel


def get_utc_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


class TurnDirection(str, Enum):
    """Who spoke. INBOUND is the prospective parent, OUTBOUND is us."""

    INBOUND = "INBOUND"
    OUTBOUND = "OUTBOUND"


class TouchStatus(str, Enum):
    """Outcome of one attempted outbound message."""

    SENT = "SENT"
    FAILED = "FAILED"
    # Suppressed before sending because the lead opted out of that channel.
    CONSENT_BLOCKED = "CONSENT_BLOCKED"
    # No usable address/number on the lead for that channel. A DATA gap:
    # this one lead is missing a contact detail.
    SKIPPED = "SKIPPED"
    # This deployment cannot send on that channel at all -- no provider is
    # configured. An OPERATIONS gap: every lead on that channel is affected.
    # Deliberately distinct from SKIPPED, which reads as a delivery decision
    # and hid the fact that WhatsApp-only families were never contacted by
    # anyone, because no WhatsApp sender exists.
    UNAVAILABLE = "UNAVAILABLE"


class LeadConversationTurn(SQLModel, table=True):
    """One message in a lead's admissions conversation (M29)."""

    __tablename__ = "sms_lead_conversation_turn"
    __table_args__ = (
        # Composite for "recent turns for this lead", the only read path that
        # matters. Note: no `index=True` on the columns themselves -- SQLAlchemy
        # auto-names a column index `ix_<table>_<column>`, and declaring both
        # forms for one column makes create_all emit CREATE INDEX twice, which
        # takes the whole API down at startup.
        Index("ix_lead_turn_lead_time", "lead_id", "created_at"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    lead_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("sms_admissions_lead.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    direction: TurnDirection = Field(
        sa_column=Column(
            SAEnum(TurnDirection, name="sms_lead_turn_direction", native_enum=False),
            nullable=False,
        )
    )
    channel: Optional[str] = Field(default=None, sa_column=Column(String(32), nullable=True))
    message: str = Field(sa_column=Column(Text, nullable=False))
    # What the SDR agent understood, kept so a later reply can see the thread's
    # trajectory rather than re-deriving intent from raw text every time.
    detected_intent: Optional[str] = Field(default=None, sa_column=Column(String(64), nullable=True))
    created_at: datetime.datetime = Field(
        default_factory=get_utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False, default=get_utc_now),
    )


class LeadNurtureState(SQLModel, table=True):
    """Where a lead is in its drip sequence, and when the next touch is owed."""

    __tablename__ = "sms_lead_nurture_state"
    __table_args__ = (
        # The scheduled runner's only query: "which leads are due now".
        Index("ix_lead_nurture_due", "is_active", "next_due_at"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    lead_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("sms_admissions_lead.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        )
    )
    # Highest stage number already delivered. 0 means the sequence is enrolled
    # but nothing has gone out yet.
    last_stage_sent: int = Field(default=0, sa_column=Column(Integer, nullable=False, default=0))
    next_due_at: Optional[datetime.datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    is_active: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, default=True))
    # The generated sequence, stored so a later run sends exactly what was
    # approved rather than regenerating copy that may have drifted.
    sequence_json: Optional[Dict[str, Any]] = Field(
        default=None, sa_column=Column(JSON, nullable=True)
    )
    stopped_reason: Optional[str] = Field(default=None, sa_column=Column(String(255), nullable=True))
    created_at: datetime.datetime = Field(
        default_factory=get_utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False, default=get_utc_now),
    )
    updated_at: datetime.datetime = Field(
        default_factory=get_utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False, default=get_utc_now),
    )


class LeadOutboundTouch(SQLModel, table=True):
    """One attempted outbound message to a lead, with its real outcome."""

    __tablename__ = "sms_lead_outbound_touch"
    __table_args__ = (Index("ix_lead_touch_lead_time", "lead_id", "created_at"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    lead_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("sms_admissions_lead.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    stage: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))
    channel: str = Field(sa_column=Column(String(32), nullable=False))
    subject: Optional[str] = Field(default=None, sa_column=Column(String(255), nullable=True))
    status: TouchStatus = Field(
        sa_column=Column(
            SAEnum(TouchStatus, name="sms_lead_touch_status", native_enum=False),
            nullable=False,
        )
    )
    # Why it failed or was suppressed. Kept so "nothing was sent" is always
    # explainable rather than merely observable.
    detail: Optional[str] = Field(default=None, sa_column=Column(String(500), nullable=True))
    created_at: datetime.datetime = Field(
        default_factory=get_utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False, default=get_utc_now),
    )
