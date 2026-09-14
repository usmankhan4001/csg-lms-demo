"""Fee module extensions: instalments, concessions, refunds, reconciliation, audit.

All five live here rather than in `sms_fees.py` so the original module keeps
its shape, but they are one domain and share one rule:

    `StudentFeeVoucher.balance_amount` REMAINS THE ONLY SOURCE OF TRUTH FOR
    WHAT A FAMILY OWES.

Nothing in this file recomputes a balance. An instalment plan's figures are
SUMS of its vouchers' stored fields; a concession's effect is realised into
`voucher.discount` at generation time; a refund adjusts `paid_amount` and
recomputes `balance_amount` with the same `total_amount - paid_amount`
expression `process_fee_payment` uses. A second balance calculation that could
disagree with the first is how a school ends up telling two different families
two different numbers for the same voucher.

Money must never be invented: a voucher with no payment has NO payment, and a
figure that cannot be computed is omitted rather than defaulted to zero.
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
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlmodel import Field, SQLModel


# ── Instalment plans ────────────────────────────────────────────────────────


class InstallmentPlanStatus(str, Enum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class FeeInstallmentPlan(SQLModel, table=True):
    """A term/year fee split into scheduled instalments.

    EACH INSTALMENT IS A REAL VOUCHER, linked back by
    ``StudentFeeVoucher.installment_plan_id``. That is the whole design
    decision, and it was taken over the alternative (one voucher plus a
    separate schedule table) for three reasons:

    1. **Late fees already work per voucher due-date.** With one voucher per
       instalment, a family that misses instalment 2 is charged on instalment 2
       only. Modelled as one voucher with a schedule, accrual would read the
       single ``due_date`` and charge late fees on the whole year's fee the day
       the first instalment slipped.
    2. **Payments already work against vouchers.** ``process_fee_payment``,
       receipts, and the ledger need no changes at all.
    3. **No second balance calculation.** "Paid 2 of 3" is a count of child
       vouchers, and the plan total is a sum of their stored ``total_amount``.
       Nothing here can drift from what the voucher says.

    The plan row therefore holds SCHEDULE and PROVENANCE, never money that is
    computed a second way.
    """

    __tablename__ = "sms_fee_installment_plan"
    __table_args__ = (
        Index("ix_sms_inst_plan_student", "student_id", "status"),
        Index("ix_sms_inst_plan_campus", "campus_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    student_id: int = Field(sa_column=Column(Integer, nullable=False, index=True))
    campus_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))
    fee_structure_id: Optional[int] = Field(
        default=None,
        sa_column=Column(
            Integer, ForeignKey("sms_fee_structure.id", ondelete="SET NULL"), nullable=True
        ),
    )
    academic_term_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))

    name: str = Field(sa_column=Column(String(150), nullable=False))
    installment_count: int = Field(sa_column=Column(Integer, nullable=False))

    status: InstallmentPlanStatus = Field(
        default=InstallmentPlanStatus.ACTIVE,
        sa_column=Column(
            SAEnum(InstallmentPlanStatus, name="sms_inst_plan_status", native_enum=False),
            nullable=False,
            default=InstallmentPlanStatus.ACTIVE,
        ),
    )

    created_by_user_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.datetime.now(datetime.timezone.utc),
        ),
    )


# ── Concessions ─────────────────────────────────────────────────────────────


class ConcessionKind(str, Enum):
    """Why a family is paying less. A flat ``discount`` float could express the
    amount but never the reason, which is precisely what a bursar is asked to
    justify."""

    SIBLING = "SIBLING"
    SCHOLARSHIP = "SCHOLARSHIP"
    HARDSHIP = "HARDSHIP"
    STAFF_CHILD = "STAFF_CHILD"
    OTHER = "OTHER"


class FeeConcession(SQLModel, table=True):
    """An authorised, reasoned reduction in what one student is billed.

    Deliberately attached to ONE named student rather than derived. A sibling
    discount in particular is tempting to infer from ``StudentGuardian`` links,
    but "which child is the second child" is a school policy question (eldest?
    most recently enrolled? highest fee?) and guessing it would quietly award
    or withhold money from a real family. The bursar names the student; the
    system records who decided and why.

    Either ``percentage`` or ``fixed_amount`` is set, never both -- a
    concession that is both 20% and 5000 has no single meaning.
    """

    __tablename__ = "sms_fee_concession"
    __table_args__ = (
        Index("ix_sms_concession_student", "student_id", "is_active"),
        Index("ix_sms_concession_campus", "campus_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    student_id: int = Field(sa_column=Column(Integer, nullable=False, index=True))
    campus_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))

    kind: ConcessionKind = Field(
        sa_column=Column(
            SAEnum(ConcessionKind, name="sms_concession_kind", native_enum=False), nullable=False
        )
    )
    percentage: Optional[float] = Field(default=None, sa_column=Column(Float, nullable=True))
    fixed_amount: Optional[float] = Field(default=None, sa_column=Column(Float, nullable=True))

    # NOT nullable. A concession with no stated reason is the thing this table
    # exists to prevent.
    reason: str = Field(sa_column=Column(Text, nullable=False))

    # The AUTHENTICATED caller who approved it, never a client-supplied id.
    authorised_by_user_id: Optional[int] = Field(
        default=None, sa_column=Column(Integer, nullable=True)
    )

    valid_from: Optional[datetime.date] = Field(default=None, sa_column=Column(Date, nullable=True))
    valid_until: Optional[datetime.date] = Field(default=None, sa_column=Column(Date, nullable=True))
    is_active: bool = Field(default=True, sa_column=Column(Integer, nullable=False, default=1))

    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.datetime.now(datetime.timezone.utc),
        ),
    )


class FeeConcessionApplication(SQLModel, table=True):
    """Append-only: this concession took this much off that voucher.

    The money itself lives in ``StudentFeeVoucher.discount`` -- this explains
    where that number came from, so a family asking "why is my bill lower than
    my neighbour's" gets an answer that matches the ledger.
    """

    __tablename__ = "sms_fee_concession_application"
    __table_args__ = (
        Index("ix_sms_conc_app_voucher", "voucher_id"),
        Index("ix_sms_conc_app_concession", "concession_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    # Plain integers, snapshot style: the trail must survive deletion of the
    # concession or voucher it describes. Same reasoning as
    # sms_grade_change_event.
    concession_id: int = Field(sa_column=Column(Integer, nullable=False))
    voucher_id: int = Field(sa_column=Column(Integer, nullable=False))
    student_id: int = Field(sa_column=Column(Integer, nullable=False))
    kind: str = Field(sa_column=Column(String(32), nullable=False))
    amount_applied: float = Field(sa_column=Column(Float, nullable=False))
    reason: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))

    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.datetime.now(datetime.timezone.utc),
        ),
    )


# ── Refunds ─────────────────────────────────────────────────────────────────


class FeeRefund(SQLModel, table=True):
    """Money returned to a family.

    Reduces ``voucher.paid_amount`` and recomputes ``balance_amount`` with the
    SAME expression payment uses, so a refunded voucher reads exactly like one
    that was never paid that much. Total refunded can never exceed total paid;
    that is enforced in the service, not merely documented here.
    """

    __tablename__ = "sms_fee_refund"
    __table_args__ = (
        UniqueConstraint("refund_no", name="uq_sms_refund_no"),
        Index("ix_sms_refund_voucher", "voucher_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    voucher_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("sms_student_fee_voucher.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    refund_no: str = Field(sa_column=Column(String(50), nullable=False, unique=True, index=True))
    refund_date: datetime.date = Field(sa_column=Column(Date, nullable=False))
    amount: float = Field(sa_column=Column(Float, nullable=False))
    method: str = Field(sa_column=Column(String(32), nullable=False))
    reason: str = Field(sa_column=Column(Text, nullable=False))
    authorised_by_user_id: Optional[int] = Field(
        default=None, sa_column=Column(Integer, nullable=True)
    )
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.datetime.now(datetime.timezone.utc),
        ),
    )


# ── Bank reconciliation ─────────────────────────────────────────────────────


class BankTransferStatus(str, Enum):
    UNMATCHED = "UNMATCHED"
    MATCHED = "MATCHED"
    IGNORED = "IGNORED"


class BankTransferRecord(SQLModel, table=True):
    """One line off a bank statement, before anyone knows whose it is.

    This is the piece that made reconciliation impossible. Today a payment can
    only be recorded if the office ALREADY knows which voucher it belongs to --
    but a bank transfer arrives as an amount, a date and whatever reference the
    payer typed. Forty of those on a Monday morning cannot be matched to
    families by guesswork.

    So an unmatched transfer is a first-class record that exists BEFORE it is
    attributed. Matching it creates the ordinary FeePaymentReceipt through the
    ordinary payment path -- this table never moves money on its own.

    Deliberately NOT built: parsing any specific bank's statement format. That
    is per-bank, per-country and unknowable here; a CSV importer belongs above
    this API, which accepts already-parsed rows.
    """

    __tablename__ = "sms_bank_transfer_record"
    __table_args__ = (
        Index("ix_sms_bank_xfer_status", "status", "transfer_date"),
        Index("ix_sms_bank_xfer_campus", "campus_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    campus_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))

    transfer_date: datetime.date = Field(sa_column=Column(Date, nullable=False))
    amount: float = Field(sa_column=Column(Float, nullable=False))

    # What the bank gave us. `payer_note` is the free-text reference a family
    # typed, which in practice is where the student's name or voucher number
    # actually appears.
    bank_reference: Optional[str] = Field(default=None, sa_column=Column(String(120), nullable=True))
    payer_name: Optional[str] = Field(default=None, sa_column=Column(String(150), nullable=True))
    payer_note: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))

    status: BankTransferStatus = Field(
        default=BankTransferStatus.UNMATCHED,
        sa_column=Column(
            SAEnum(BankTransferStatus, name="sms_bank_xfer_status", native_enum=False),
            nullable=False,
            default=BankTransferStatus.UNMATCHED,
        ),
    )
    # Set only once matched. Plain integer: the trail should survive a receipt
    # being deleted, and reading "matched to a receipt that no longer exists"
    # is more useful than the row silently reverting to unmatched.
    matched_receipt_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))
    matched_voucher_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))
    matched_by_user_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))
    matched_at: Optional[datetime.datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    ignored_reason: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))

    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.datetime.now(datetime.timezone.utc),
        ),
    )


# ── Reminders ───────────────────────────────────────────────────────────────


class FeeReminderKind(str, Enum):
    UPCOMING = "UPCOMING"
    DUE_TODAY = "DUE_TODAY"
    OVERDUE = "OVERDUE"


class FeeReminderLog(SQLModel, table=True):
    """Append-only record of every reminder this system tried to send.

    Exists for two reasons, both about not harassing families: it stops the
    daily job re-sending the same reminder to the same voucher, and it lets a
    school answer "were we actually chasing this balance, or did it grow
    silently?" -- which until now it could not, because nothing told the family
    at all while late fees accrued.
    """

    __tablename__ = "sms_fee_reminder_log"
    __table_args__ = (
        Index("ix_sms_fee_reminder_voucher", "voucher_id", "sent_on"),
        Index("ix_sms_fee_reminder_kind", "kind", "sent_on"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    voucher_id: int = Field(sa_column=Column(Integer, nullable=False))
    student_id: int = Field(sa_column=Column(Integer, nullable=False))
    kind: FeeReminderKind = Field(
        sa_column=Column(
            SAEnum(FeeReminderKind, name="sms_fee_reminder_kind", native_enum=False), nullable=False
        )
    )
    sent_on: datetime.date = Field(sa_column=Column(Date, nullable=False))

    # What the notification service actually achieved, not what we hoped.
    # `recipients` is guardians we found; `delivered` is emails the provider
    # accepted. They differ whenever mail is unconfigured, and that difference
    # is the point -- an in-app notification still exists, and the failure is
    # visible rather than swallowed.
    recipients: int = Field(default=0, sa_column=Column(Integer, nullable=False, default=0))
    delivered: int = Field(default=0, sa_column=Column(Integer, nullable=False, default=0))
    balance_at_send: float = Field(sa_column=Column(Float, nullable=False))

    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.datetime.now(datetime.timezone.utc),
        ),
    )


# ── Audit ───────────────────────────────────────────────────────────────────


class FeeChangeAction(str, Enum):
    VOUCHER_CREATED = "VOUCHER_CREATED"
    PAYMENT_RECORDED = "PAYMENT_RECORDED"
    REFUND_ISSUED = "REFUND_ISSUED"
    CONCESSION_APPLIED = "CONCESSION_APPLIED"
    TRANSFER_MATCHED = "TRANSFER_MATCHED"


class FeeChangeEvent(SQLModel, table=True):
    """Append-only trail of every money mutation on a voucher.

    Same shape as ``sms_grade_change_event`` and ``AttendanceChangeEvent``
    deliberately -- a third audit idiom would mean three places to look when
    somebody asks what happened to an account. Snapshot columns, plain
    integers, and the actor resolved from the AUTHENTICATED principal rather
    than any client-supplied field.

    No endpoint updates or deletes a row here. A trail that can be rewritten is
    not a trail.
    """

    __tablename__ = "sms_fee_change_event"
    __table_args__ = (
        Index("ix_sms_fee_change_voucher", "voucher_id", "created_at"),
        Index("ix_sms_fee_change_student", "student_id", "created_at"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    voucher_id: int = Field(sa_column=Column(Integer, nullable=False))
    student_id: int = Field(sa_column=Column(Integer, nullable=False))
    action: FeeChangeAction = Field(
        sa_column=Column(
            SAEnum(FeeChangeAction, name="sms_fee_change_action", native_enum=False), nullable=False
        )
    )

    # None where there was no previous figure -- distinct from 0.0, which is a
    # real amount a voucher can legitimately hold.
    previous_paid_amount: Optional[float] = Field(default=None, sa_column=Column(Float, nullable=True))
    new_paid_amount: Optional[float] = Field(default=None, sa_column=Column(Float, nullable=True))
    previous_balance: Optional[float] = Field(default=None, sa_column=Column(Float, nullable=True))
    new_balance: Optional[float] = Field(default=None, sa_column=Column(Float, nullable=True))
    amount: Optional[float] = Field(default=None, sa_column=Column(Float, nullable=True))

    changed_by_user_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))
    reason: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))

    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.datetime.now(datetime.timezone.utc),
        ),
    )
