"""Request and response shapes for online fee payment.

Money crosses this boundary twice over: `amount_minor` is the exact integer
the provider was asked for, and `amount_display` is the human figure. Both are
returned so a client never has to divide by a hundred and guess the exponent
for the school's currency.
"""

import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from src.db.sms_fee_payments import PaymentIntentStatus


class StartCheckoutRequest(BaseModel):
    """Where to send the payer back to. Supplied by the client because only
    the client knows which screen it launched from."""

    success_url: str = Field(..., description="Where the provider returns a payer who completed payment")
    cancel_url: str = Field(..., description="Where the provider returns a payer who backed out")


class StartCheckoutResponse(BaseModel):
    intent_id: int
    reference: str
    voucher_id: int
    amount_minor: int
    amount_display: float
    currency: str
    provider: str
    # Single-use and short-lived, so it is returned and never stored.
    redirect_url: str


class FeePaymentIntentRead(BaseModel):
    id: int
    reference: str
    voucher_id: int
    student_id: int
    provider: str
    amount_minor: int
    amount_display: float
    currency: str
    status: PaymentIntentStatus
    provider_payment_ref: Optional[str] = None
    receipt_id: Optional[int] = None
    # Carries the amount-mismatch and already-settled cases that need a human,
    # so they are visible in the UI rather than only in the logs.
    failure_reason: Optional[str] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = {"from_attributes": True}


class VoucherPaymentAttempts(BaseModel):
    voucher_id: int
    attempts: List[FeePaymentIntentRead]


class WebhookAck(BaseModel):
    """Acknowledgement body. `status` names what actually happened, so a
    delivery log is readable without cross-referencing the ledger."""

    received: bool = True
    status: str
