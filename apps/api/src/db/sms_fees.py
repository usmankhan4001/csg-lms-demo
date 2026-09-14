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


class VoucherStatus(str, Enum):
    """Lifecycle status of a student fee voucher."""
    UNPAID = "UNPAID"
    PARTIAL = "PARTIAL"
    PAID = "PAID"
    CANCELLED = "CANCELLED"


class PaymentMethod(str, Enum):
    """Payment method for fee collection."""
    CASH = "CASH"
    BANK_TRANSFER = "BANK_TRANSFER"
    ONLINE = "ONLINE"
    CHEQUE = "CHEQUE"


class FeeStructure(SQLModel, table=True):
    """
    Template for institutional fee breakdown applicable to sections/classes.
    """
    __tablename__ = "sms_fee_structure"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(sa_column=Column(String(150), nullable=False))
    campus_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True, index=True))
    section_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True, index=True))
    academic_term_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True, index=True))
    tuition_fee: float = Field(default=0.0, sa_column=Column(Float, nullable=False))
    transport_fee: float = Field(default=0.0, sa_column=Column(Float, nullable=False))
    lab_fee: float = Field(default=0.0, sa_column=Column(Float, nullable=False))
    other_fee: float = Field(default=0.0, sa_column=Column(Float, nullable=False))
    total_amount: float = Field(default=0.0, sa_column=Column(Float, nullable=False))


class StudentFeeVoucher(SQLModel, table=True):
    """
    Issued monthly or term student fee voucher invoice.
    """
    __tablename__ = "sms_student_fee_voucher"
    __table_args__ = (
        UniqueConstraint("voucher_no", name="uq_sms_voucher_no"),
        Index("ix_sms_voucher_student_status", "student_id", "status"),
        Index("ix_sms_voucher_due_date", "due_date"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    student_id: int = Field(sa_column=Column(Integer, nullable=False, index=True))
    fee_structure_id: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("sms_fee_structure.id", ondelete="SET NULL"), nullable=True),
    )
    # Instalment membership. NULL for an ordinary one-off voucher, which is
    # every voucher that existed before instalment plans -- so nothing about
    # the existing billing path changes.
    #
    # Each instalment IS a voucher rather than a schedule row on one big
    # voucher, because late-fee accrual reads `due_date` per voucher: a family
    # that misses instalment 2 must be charged on instalment 2, not on the
    # whole year's fee. See db/sms_fees_extended.py:FeeInstallmentPlan.
    #
    # A plain Integer, NOT a ForeignKey, and that is deliberate. This column is
    # delivered to existing databases by an Alembic migration, but
    # `sms_fee_installment_plan` is created by SQLModel's create_all when the
    # app boots -- which happens AFTER migrations run. A real FK would
    # therefore exist on a freshly-created database and be absent on a migrated
    # one, so the two deployment paths would diverge. Declaring it as an
    # integer keeps model and migration honest about the same thing.
    # Deleting a plan consequently leaves its vouchers standing, which is the
    # behaviour wanted anyway: removing a schedule must never delete the money
    # a family owes.
    installment_plan_id: Optional[int] = Field(
        default=None, sa_column=Column(Integer, nullable=True, index=True)
    )
    # 1-based position in the plan, so a parent sees "2 of 3" rather than a
    # date they have to interpret. NULL iff installment_plan_id is NULL.
    installment_number: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))
    voucher_no: str = Field(sa_column=Column(String(50), nullable=False, unique=True, index=True))
    issue_date: datetime.date = Field(sa_column=Column(Date, nullable=False))
    due_date: datetime.date = Field(sa_column=Column(Date, nullable=False, index=True))
    tuition_fee: float = Field(default=0.0, sa_column=Column(Float, nullable=False))
    transport_fee: float = Field(default=0.0, sa_column=Column(Float, nullable=False))
    lab_fee: float = Field(default=0.0, sa_column=Column(Float, nullable=False))
    other_fee: float = Field(default=0.0, sa_column=Column(Float, nullable=False))
    discount: float = Field(default=0.0, sa_column=Column(Float, nullable=False))
    fine: float = Field(default=0.0, sa_column=Column(Float, nullable=False))
    # Portion of `fine` that the late-fee accrual engine charged, as opposed to
    # a fine an administrator set by hand at voucher-generation time. Tracked
    # separately so accrual is IDEMPOTENT: re-running it recomputes the target
    # late fee and charges only the difference, instead of stacking a fresh
    # charge onto the voucher every time the job runs. It is also the base
    # exclusion that stops late fees from compounding on late fees.
    late_fee_applied: float = Field(default=0.0, sa_column=Column(Float, nullable=False, default=0.0))
    # Audit trail: when accrual last changed this voucher. Nullable because a
    # voucher that was never overdue has never accrued.
    late_fee_last_accrued_on: Optional[datetime.date] = Field(
        default=None, sa_column=Column(Date, nullable=True)
    )
    total_amount: float = Field(default=0.0, sa_column=Column(Float, nullable=False))
    paid_amount: float = Field(default=0.0, sa_column=Column(Float, nullable=False))
    balance_amount: float = Field(default=0.0, sa_column=Column(Float, nullable=False))
    status: VoucherStatus = Field(
        default=VoucherStatus.UNPAID,
        sa_column=Column(
            SAEnum(VoucherStatus, name="sms_voucher_status", native_enum=False),
            nullable=False,
            default=VoucherStatus.UNPAID,
        ),
    )
    remarks: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.datetime.now(datetime.timezone.utc),
        ),
    )


class FeePaymentReceipt(SQLModel, table=True):
    """
    Receipt generated whenever a fee payment is recorded against a voucher.
    """
    __tablename__ = "sms_fee_payment_receipt"
    __table_args__ = (
        UniqueConstraint("receipt_no", name="uq_sms_receipt_no"),
        Index("ix_sms_receipt_voucher", "voucher_id"),
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
    receipt_no: str = Field(sa_column=Column(String(50), nullable=False, unique=True, index=True))
    payment_date: datetime.date = Field(sa_column=Column(Date, nullable=False))
    amount_paid: float = Field(sa_column=Column(Float, nullable=False))
    payment_method: PaymentMethod = Field(
        default=PaymentMethod.CASH,
        sa_column=Column(
            SAEnum(PaymentMethod, name="sms_payment_method", native_enum=False),
            nullable=False,
            default=PaymentMethod.CASH,
        ),
    )
    transaction_ref: Optional[str] = Field(default=None, sa_column=Column(String(100), nullable=True))
    collected_by: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))
    remarks: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.datetime.now(datetime.timezone.utc),
        ),
    )
