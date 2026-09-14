"""
Parental consent for a minor's AI use.

Why this exists: children were using an LLM tutor -- one that sends what they
type to a third-party AI provider, stores transcripts readable by staff, and
screens their messages for crisis indicators -- with NO recorded guardian
approval anywhere in the system. Before this module, the only consent in the
entire codebase was RevOps *marketing* consent on sales leads
(`AdmissionsLead.whatsapp_consent`). That is a compliance gap, not a missing
feature, and the wiki never mentions it.

APPEND-ONLY BY DESIGN. Consent is a sequence of events, not a boolean. A
withdrawal must not erase the fact that consent was previously given: a school
asked "was this child covered last March?" needs a truthful answer, and a
mutable flag cannot give one. `SchoolAIConsentEvent` rows are therefore only
ever INSERTed; current state is the newest row per (student, consent type).

THREE SEPARATE CONSENT TYPES, not one flag, because a guardian can reasonably
allow one and refuse another and these are genuinely different processing:

  AI_TUTOR              The child's words are sent to a third-party LLM.
                        This is the one that leaves the building.
  TRANSCRIPT_RETENTION  What the child typed is stored durably and is readable
                        by teacher oversight. A guardian may accept live
                        tutoring but object to a permanent record.
  WELLBEING_MONITORING  Crisis/self-harm screening and escalation to a
                        counsellor. Note this one is LOCAL REGEX
                        (`services/ai/crisis_classifier.classify_prompt_safety`
                        is pure `re.search`, verified -- no model call, no
                        network), so refusing it buys a family no privacy from
                        any third party. See CONSENT_CRISIS_OVERRIDE below.

Adding a fourth type is one enum member plus one row in the defaults map.

Purely additive, like every other sms_* model here: picked up by
`SQLModel.metadata.create_all` at startup, never through Alembic.
"""

import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlmodel import Field, SQLModel


def get_utc_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


class AIConsentType(str, Enum):
    """What a guardian is being asked to permit. See module docstring."""

    AI_TUTOR = "AI_TUTOR"
    TRANSCRIPT_RETENTION = "TRANSCRIPT_RETENTION"
    WELLBEING_MONITORING = "WELLBEING_MONITORING"


class AIConsentDecision(str, Enum):
    """A guardian's recorded answer.

    PENDING is never stored -- it is what `resolve_consent` returns when no
    event exists. It is deliberately distinct from REFUSED: "nobody has asked
    this family yet" and "this family said no" are different facts and must
    not be collapsed, which is the whole reason enforcement has two modes.
    """

    PENDING = "PENDING"
    GRANTED = "GRANTED"
    REFUSED = "REFUSED"
    WITHDRAWN = "WITHDRAWN"


class AIConsentEnforcement(str, Enum):
    """How an org treats a student with no recorded decision.

    ADVISORY  PENDING is allowed through, but recorded and reportable. This is
              the default so that turning this module on does not lock every
              existing student out of the tutor overnight while the school is
              still collecting forms.
    STRICT    PENDING blocks. A school flips to this once its consent register
              is complete.

    An explicit REFUSED or WITHDRAWN blocks in BOTH modes. A recorded refusal
    is honoured immediately and is not subject to a grace period.
    """

    ADVISORY = "ADVISORY"
    STRICT = "STRICT"


class SchoolAIConsentEvent(SQLModel, table=True):
    """One guardian decision about one consent type for one student.

    Append-only: a withdrawal is a new row, never an UPDATE. Nothing in this
    codebase should ever UPDATE or DELETE one of these.
    """

    __tablename__ = "sms_ai_consent_event"
    __table_args__ = (
        # Lookup index only. Named explicitly and with NO `index=True` on any
        # column: SQLAlchemy auto-names a column index identically and
        # `create_all` would then emit CREATE INDEX twice, which has already
        # taken this API down once.
        Index("ix_sms_ai_consent_student_type", "student_id", "consent_type", "id"),
        Index("ix_sms_ai_consent_org", "org_id"),
        {"extend_existing": True},
    )

    id: Optional[int] = Field(default=None, primary_key=True)

    student_id: int = Field(
        sa_column=Column(Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    )
    org_id: int = Field(sa_column=Column(Integer, nullable=False))
    campus_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))

    consent_type: AIConsentType = Field(sa_column=Column(String(32), nullable=False))
    decision: AIConsentDecision = Field(sa_column=Column(String(16), nullable=False))

    # The guardian whose decision this is. Resolved server-side through
    # StudentGuardian -- NEVER taken from a request payload.
    guardian_user_id: int = Field(
        sa_column=Column(Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    )
    # Who keyed it in. Differs from guardian_user_id when a school records a
    # decision a parent gave on paper or by phone, which is how most consent
    # is actually collected.
    recorded_by_user_id: int = Field(
        sa_column=Column(Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    )
    # "form", "phone", "in_person", "portal" -- how the school obtained it.
    source: Optional[str] = Field(default=None, sa_column=Column(String(32), nullable=True))
    note: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))

    created_at: datetime.datetime = Field(
        default_factory=get_utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class SchoolAIConsentPolicy(SQLModel, table=True):
    """Per-org enforcement settings. One row per org; absent means defaults."""

    __tablename__ = "sms_ai_consent_policy"
    __table_args__ = (
        Index("ix_sms_ai_consent_policy_org", "org_id"),
        {"extend_existing": True},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    org_id: int = Field(sa_column=Column(Integer, nullable=False))

    enforcement: AIConsentEnforcement = Field(
        default=AIConsentEnforcement.ADVISORY,
        sa_column=Column(String(16), nullable=False, server_default="ADVISORY"),
    )

    # Whether crisis screening still runs for a student whose guardian has
    # refused or withdrawn WELLBEING_MONITORING. Defaults to True -- see
    # `CONSENT_CRISIS_OVERRIDE_RATIONALE` in services/sms/ai_consent.py for the
    # full reasoning and the trade-off. A school whose jurisdiction requires
    # otherwise can set this False.
    crisis_override_enabled: bool = Field(
        default=True,
        sa_column=Column(Boolean, nullable=False, server_default="true"),
    )

    updated_at: datetime.datetime = Field(
        default_factory=get_utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
