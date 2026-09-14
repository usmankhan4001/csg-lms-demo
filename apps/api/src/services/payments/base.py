"""The payment provider seam.

CONTRACT: nothing outside `services/payments/<provider>.py` may import a
provider SDK, reference a provider's types, or assume card semantics. The
school this is built for is in Pakistan, where card-first collection suits the
parent body poorly, so JazzCash or Easypaisa will arrive as a SECOND
implementation of this interface -- not a rewrite of the fee module. Every
value object below is therefore expressed in terms a bank transfer, a mobile
wallet and a card can all satisfy.

Concretely, that rules out three things a card-shaped interface would have
done: there is no "card token", the redirect is a plain URL rather than a
client-side confirmation flow, and `PaymentOutcome` has no "requires 3-D
Secure" state -- an interactive step a provider needs is its own business,
invisible on this side of the seam.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from src.services.payments.money import Money


class PaymentOutcome(str, Enum):
    """What a provider has told us about an attempt.

    PENDING is genuinely distinct from SUCCEEDED: a bank transfer rail may
    accept a payment that settles hours later, and treating that as paid would
    credit a ledger against money that has not arrived.
    """

    PENDING = "PENDING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"
    # An event we verified but that says nothing about this payment's fate.
    IGNORED = "IGNORED"


class PaymentProviderError(RuntimeError):
    """A provider call failed. Carries no key material or raw payload."""


class WebhookVerificationError(PaymentProviderError):
    """Signature missing, malformed, or not ours. Always a rejection, never a
    warning: an unverified webhook is an unauthenticated instruction to move
    money."""


@dataclass(frozen=True)
class CheckoutRequest:
    reference: str
    amount: Money
    description: str
    success_url: str
    cancel_url: str
    customer_email: Optional[str] = None


@dataclass(frozen=True)
class CheckoutSession:
    provider_session_id: str
    redirect_url: str


@dataclass(frozen=True)
class WebhookEvent:
    """A verified provider notification, normalised.

    `reference` is OUR reference round-tripped through the provider. The
    webhook handler keys off this rather than anything else in the payload,
    so a forged body cannot point a real payment at a different voucher.
    """

    event_id: str
    event_type: str
    outcome: PaymentOutcome
    reference: Optional[str] = None
    provider_session_id: Optional[str] = None
    provider_payment_ref: Optional[str] = None
    amount: Optional[Money] = None
    failure_reason: Optional[str] = None


@dataclass(frozen=True)
class RefundResult:
    provider_refund_ref: str
    amount: Money


class PaymentProvider(ABC):
    """Implement this once per rail. See `stripe_provider.py` for the model."""

    #: Stored on every intent, so a school running two rails can tell them
    #: apart in its own records years later.
    name: str = "abstract"

    @abstractmethod
    async def create_checkout(self, request: CheckoutRequest) -> CheckoutSession:
        """Open a payment session and return where to send the payer."""

    @abstractmethod
    def verify_and_parse_webhook(self, payload: bytes, signature: str) -> WebhookEvent:
        """Verify the signature over the RAW body and normalise the event.

        Synchronous by design: verification is a local cryptographic operation
        and must not depend on a network call that could time out and cause a
        provider retry storm. Raises `WebhookVerificationError` on any doubt.
        """

    @abstractmethod
    async def fetch_payment_status(self, provider_session_id: str) -> PaymentOutcome:
        """Ask the provider directly. Used to resolve intents whose webhook
        never arrived, which is the normal case for an abandoned checkout."""

    @abstractmethod
    async def refund(self, provider_payment_ref: str, amount: Money) -> RefundResult:
        """Return money against a captured payment."""
