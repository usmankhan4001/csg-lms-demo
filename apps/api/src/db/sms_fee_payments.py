"""Online fee payment records.

WHY THIS EXISTS: every one of the 18 endpoints in `routers/sms_fees.py`
assumed a human had already taken money somewhere else and was now typing it
in. For a school whose families are not physically present, that is the
revenue path missing entirely -- a parent could be shown a balance and had no
way to settle it.

TWO TABLES, AND WHY EACH IS SEPARATE:

`FeePaymentIntent` is OUR record of an attempt to pay, created before the
parent is redirected to the provider. It exists so that an abandoned checkout
is a visible, queryable state rather than silence. The overwhelming majority
of payments that go wrong go QUIET -- the parent closes the tab -- and without
a row written up front there is nothing to reconcile against later.

`PaymentWebhookEvent` is an insert-first idempotency guard. Providers retry
webhooks, sometimes for days, and a replayed `checkout.session.completed` that
credits a voucher twice is a refund and an apology. The unique constraint on
(provider, event_id) makes the double-credit impossible at the DATABASE level
rather than at the application level: a replay loses the insert race and the
whole transaction -- event row and ledger write together -- rolls back.

NOTE ON MONEY. The existing fee ledger stores amounts as `float`
(`StudentFeeVoucher.total_amount` and friends). That is a real defect -- money
in binary floating point accumulates error -- but correcting it means altering
several columns across two modules and is deliberately NOT attempted here.
These tables store minor units as an integer, which is what payment providers
require anyway, and conversion happens once at the boundary in
`services/payments/money.py`. See the report accompanying this work.
"""

import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import (
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


class PaymentIntentStatus(str, Enum):
    """Lifecycle of one attempt to pay a voucher online.

    ABANDONED is distinct from FAILED on purpose: FAILED means the provider
    told us the payment was declined, ABANDONED means the provider never told
    us anything and the session expired. A school chasing unpaid fees needs to
    treat those two differently -- one parent tried and their card was
    refused, the other never got that far.
    """

    CREATED = "CREATED"
    PENDING = "PENDING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    ABANDONED = "ABANDONED"


class FeePaymentIntent(SQLModel, table=True):
    """One attempt by a parent or student to settle a voucher online."""

    __tablename__ = "sms_fee_payment_intent"
    __table_args__ = (
        # A provider session maps to exactly one intent. This is what lets the
        # webhook find its intent without trusting anything in the payload
        # body beyond the session id the provider itself signed.
        UniqueConstraint(
            "provider", "provider_session_id", name="uq_sms_fee_intent_provider_session"
        ),
        UniqueConstraint("reference", name="uq_sms_fee_intent_reference"),
        Index("ix_sms_fee_intent_voucher_status", "voucher_id", "status"),
        Index("ix_sms_fee_intent_org", "org_id"),
        Index("ix_sms_fee_intent_student", "student_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)

    # Our own opaque reference, round-tripped through the provider so a
    # webhook can be tied back to an intent without trusting client input.
    reference: str = Field(sa_column=Column(String(64), nullable=False))

    voucher_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("sms_student_fee_voucher.id", ondelete="RESTRICT"),
            nullable=False,
        )
    )
    # Denormalised from the voucher so that authorisation and "show me this
    # family's attempts" do not need a join. RESTRICT above keeps the voucher
    # alive: a payment attempt is a financial record and must outlive tidying.
    student_id: int = Field(sa_column=Column(Integer, nullable=False))

    # NOT NULL and never defaulted. Eighteen call sites in this codebase fall
    # back to organisation 1 when a principal carries no org, which silently
    # writes one school's data into another's. Money must never do that, so
    # this column refuses to be written without a real tenant.
    org_id: int = Field(sa_column=Column(Integer, nullable=False))

    provider: str = Field(sa_column=Column(String(32), nullable=False))
    provider_session_id: Optional[str] = Field(
        default=None, sa_column=Column(String(255), nullable=True)
    )
    # The provider's id for the money itself, as opposed to the checkout
    # session. Refunds are issued against this, not the session.
    provider_payment_ref: Optional[str] = Field(
        default=None, sa_column=Column(String(255), nullable=True)
    )

    amount_minor: int = Field(sa_column=Column(Integer, nullable=False))
    currency: str = Field(sa_column=Column(String(3), nullable=False))

    status: PaymentIntentStatus = Field(
        default=PaymentIntentStatus.CREATED,
        sa_column=Column(String(16), nullable=False, default=PaymentIntentStatus.CREATED.value),
    )

    initiated_by_user_id: Optional[int] = Field(
        default=None, sa_column=Column(Integer, nullable=True)
    )
    # Set once the webhook has credited the ledger, so an intent can be traced
    # to the receipt it produced and vice versa.
    receipt_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))
    failure_reason: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))

    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class PaymentWebhookEvent(SQLModel, table=True):
    """Append-only log of provider webhook deliveries, and the replay guard.

    The row is inserted in the SAME transaction that credits the ledger. A
    provider redelivering an event loses the unique-constraint race, the
    transaction rolls back whole, and the voucher is credited exactly once.
    Doing this in the database rather than in Redis means an idempotency
    guarantee that survives a cache eviction or a Redis outage.
    """

    __tablename__ = "sms_payment_webhook_event"
    __table_args__ = (
        UniqueConstraint("provider", "event_id", name="uq_sms_payment_webhook_event"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    provider: str = Field(sa_column=Column(String(32), nullable=False))
    event_id: str = Field(sa_column=Column(String(255), nullable=False))
    event_type: str = Field(sa_column=Column(String(128), nullable=False))
    intent_reference: Optional[str] = Field(
        default=None, sa_column=Column(String(64), nullable=True)
    )
    received_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
