"""Staff lifecycle: offboarding, appraisal, and payroll separation of duties.

Three gaps this closes, all confirmed absent before writing:

1. `StaffProfile.is_active` was a bare flag. Setting it False revoked nothing:
   the departed employee kept their `SMSUserRole` grants, stayed
   `ClassSection.class_teacher_id`, and remained on every `TimetableSchedule`
   row. "Deactivated" meant nothing operationally.

2. No appraisal record at all, so a school could not evidence that a review
   ever happened.

3. No payroll approval. The three payroll endpoints compose into a
   self-dealing path -- prepare your own structure, generate your own slip,
   mark it paid -- with no second party. Narrowing the role to SCHOOL_ADMIN
   reduced who could do it; it did not introduce a control.

DELIBERATELY NO NEW COLUMNS on `sms_staff_profile` or `sms_salary_slip`.
`create_all` never ALTERs an existing table, so a column would need a
migration and would then disagree with every database that already has the
table. Each of these is a new table instead, which `create_all` lands
everywhere. The offboarding row carries the termination date itself, and the
payroll action log carries who prepared a slip -- neither needs the parent
table to change.
"""

import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Enum as SAEnum,
    Float,
    Index,
    Integer,
    String,
    Text,
)
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


class OffboardingReason(str, Enum):
    """Why the employment ended. Recorded, never inferred."""

    RESIGNATION = "RESIGNATION"
    END_OF_CONTRACT = "END_OF_CONTRACT"
    RETIREMENT = "RETIREMENT"
    DISMISSAL = "DISMISSAL"
    OTHER = "OTHER"


class StaffOffboarding(SQLModel, table=True):
    """The termination record for one staff member.

    This row IS the termination date -- `StaffProfile` has no such column and
    adding one would need a migration. `StaffProfile.is_active=False` remains
    the flag; this carries when, why, who decided, and what the cascade
    actually released.

    Append-only: there is no update or delete endpoint. Re-employing someone
    is a new profile or a reactivation, not a rewrite of the record that they
    once left.
    """

    __tablename__ = "sms_staff_offboarding"
    __table_args__ = (
        Index("ix_sms_offboarding_staff", "staff_id", "effective_date"),
        Index("ix_sms_offboarding_campus", "campus_id", "effective_date"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)

    # Plain integers, snapshotted, not FKs. `sms_staff_profile` cascades on
    # delete, and a termination record destroyed by deleting the profile is
    # useless precisely when somebody asks what happened.
    staff_id: int = Field(sa_column=Column(Integer, nullable=False))
    staff_user_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))
    campus_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))

    effective_date: datetime.date = Field(sa_column=Column(Date, nullable=False))
    reason: OffboardingReason = Field(
        sa_column=Column(
            SAEnum(OffboardingReason, name="sms_offboarding_reason", native_enum=False),
            nullable=False,
        )
    )
    notes: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))

    # What the cascade released, captured at the time. Counts rather than a
    # blob: enough to answer "was this actually actioned?" without becoming a
    # second copy of the records themselves.
    roles_revoked: int = Field(default=0, sa_column=Column(Integer, nullable=False, default=0))
    sections_released: int = Field(default=0, sa_column=Column(Integer, nullable=False, default=0))
    sections_reassigned: int = Field(default=0, sa_column=Column(Integer, nullable=False, default=0))

    # TimetableSchedule.teacher_id is NOT NULL, so a slot cannot be released to
    # nobody. Unreassigned slots are counted here and reported to the caller as
    # outstanding work -- a departed teacher silently left on a live timetable
    # is exactly the failure this record exists to surface.
    timetable_slots_reassigned: int = Field(
        default=0, sa_column=Column(Integer, nullable=False, default=0)
    )
    timetable_slots_outstanding: int = Field(
        default=0, sa_column=Column(Integer, nullable=False, default=0)
    )

    # The authenticated caller, never a client-supplied field.
    initiated_by_user_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))
    created_at: datetime.datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False, default=_utcnow),
    )


class AppraisalOutcome(str, Enum):
    """The review's overall conclusion. No numeric score is invented."""

    EXCEEDS = "EXCEEDS"
    MEETS = "MEETS"
    DEVELOPING = "DEVELOPING"
    BELOW = "BELOW"


class AppraisalStatus(str, Enum):
    DRAFT = "DRAFT"
    SHARED = "SHARED"
    ACKNOWLEDGED = "ACKNOWLEDGED"


class StaffAppraisal(SQLModel, table=True):
    """A performance review of one staff member for one period.

    DRAFT is the reviewer's working document and is not visible to the subject;
    SHARED means the employee may read it; ACKNOWLEDGED records that they have.
    That three-step shape mirrors the report-card draft/send lifecycle, for the
    same reason: a half-written assessment must not reach the person it is
    about.

    `reviewer_user_id` is the authenticated caller. An appraisal whose author
    can be set by the request body is not evidence of anything.
    """

    __tablename__ = "sms_staff_appraisal"
    __table_args__ = (
        Index("ix_sms_appraisal_staff_period", "staff_id", "period_end"),
        Index("ix_sms_appraisal_reviewer", "reviewer_user_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    staff_id: int = Field(sa_column=Column(Integer, nullable=False))
    campus_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))

    period_start: datetime.date = Field(sa_column=Column(Date, nullable=False))
    period_end: datetime.date = Field(sa_column=Column(Date, nullable=False))

    outcome: Optional[AppraisalOutcome] = Field(
        default=None,
        sa_column=Column(
            SAEnum(AppraisalOutcome, name="sms_appraisal_outcome", native_enum=False),
            nullable=True,
        ),
    )
    strengths: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    development_areas: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    objectives: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))

    status: AppraisalStatus = Field(
        default=AppraisalStatus.DRAFT,
        sa_column=Column(
            SAEnum(AppraisalStatus, name="sms_appraisal_status", native_enum=False),
            nullable=False,
            default=AppraisalStatus.DRAFT,
        ),
    )

    reviewer_user_id: int = Field(sa_column=Column(Integer, nullable=False))
    shared_at: Optional[datetime.datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    acknowledged_at: Optional[datetime.datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    created_at: datetime.datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False, default=_utcnow),
    )


class PayrollActionType(str, Enum):
    """Steps in the payroll control. PREPARED is written when a slip is
    generated, so the log knows who produced it without `sms_salary_slip`
    needing a `created_by` column it does not have."""

    PREPARED = "PREPARED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    PAID = "PAID"


class PayrollAction(SQLModel, table=True):
    """Append-only trail of every step taken on a salary slip.

    Same shape as ``sms_fee_change_event``, ``sms_grade_change_event`` and
    ``AttendanceChangeEvent`` deliberately -- a fourth audit idiom would mean
    four places to look when somebody asks what happened to a payment.

    This table is also the ENFORCEMENT point for separation of duties, not
    merely its record: `PREPARED` names the person who generated the slip, so
    approval can refuse the same actor. Without it there is no way to know who
    prepared a slip at all.

    No endpoint updates or deletes a row here.
    """

    __tablename__ = "sms_payroll_action"
    __table_args__ = (
        Index("ix_sms_payroll_action_slip", "slip_id", "created_at"),
        Index("ix_sms_payroll_action_actor", "actor_user_id", "created_at"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)

    # Snapshotted plain integers: sms_salary_slip cascades from the staff
    # profile, and a payment trail deleted with its slip proves nothing.
    slip_id: int = Field(sa_column=Column(Integer, nullable=False))
    staff_id: int = Field(sa_column=Column(Integer, nullable=False))
    campus_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))

    action: PayrollActionType = Field(
        sa_column=Column(
            SAEnum(PayrollActionType, name="sms_payroll_action_type", native_enum=False),
            nullable=False,
        )
    )

    # The net figure as it stood when the action was taken. A slip whose
    # amount changed between approval and payment is the thing an auditor
    # most wants to see, and `None` where there was no figure is distinct
    # from 0.0, which is a real amount.
    net_salary_at_action: Optional[float] = Field(
        default=None, sa_column=Column(Float, nullable=True)
    )

    note: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    actor_user_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))
    actor_label: Optional[str] = Field(default=None, sa_column=Column(String(150), nullable=True))
    created_at: datetime.datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False, default=_utcnow),
    )
