"""Stripe implementation of `PaymentProvider`.

This is the only module in the fee-payment path that imports `stripe`. It is
first because it is the easiest to exercise end to end without a commercial
onboarding process, NOT because cards are the right instrument for this
school's families -- see `base.py`.

Credentials come from `config.payments_config.stripe`, which already existed
in this codebase (populated in `config/config.py`) for the enterprise course-
sales module. Reusing it means no new environment variables and nothing new to
set on a deployment that is already configured.
"""

import logging
from typing import Any, Dict, Optional

import stripe

from src.services.payments.base import (
    CheckoutRequest,
    CheckoutSession,
    PaymentOutcome,
    PaymentProvider,
    PaymentProviderError,
    RefundResult,
    WebhookEvent,
    WebhookVerificationError,
)
from src.services.payments.money import Money

logger = logging.getLogger(__name__)

# Our reference travels in metadata under this key and comes back on the
# event, so a webhook is tied to an intent by something Stripe signed rather
# than by anything a caller supplied.
_REFERENCE_KEY = "csg_fee_intent_reference"

_TERMINAL_SUCCESS_EVENTS = {"checkout.session.completed", "checkout.session.async_payment_succeeded"}
_TERMINAL_FAILURE_EVENTS = {"checkout.session.async_payment_failed"}
_EXPIRY_EVENTS = {"checkout.session.expired"}


class StripePaymentProvider(PaymentProvider):
    name = "stripe"

    def __init__(self, secret_key: str, webhook_secret: str) -> None:
        if not secret_key or not webhook_secret:
            # Refusing here rather than at call time means a misconfigured
            # deployment fails when payments are switched on, not when a
            # parent is halfway through paying.
            raise PaymentProviderError(
                "Stripe is not configured: a secret key and a webhook signing "
                "secret are both required before online payment can be enabled."
            )
        self._secret_key = secret_key
        self._webhook_secret = webhook_secret

    # -- outbound ---------------------------------------------------------

    async def create_checkout(self, request: CheckoutRequest) -> CheckoutSession:
        try:
            session = await stripe.checkout.Session.create_async(
                api_key=self._secret_key,
                mode="payment",
                line_items=[
                    {
                        "quantity": 1,
                        "price_data": {
                            "currency": request.amount.currency.lower(),
                            "unit_amount": request.amount.minor_units,
                            "product_data": {"name": request.description},
                        },
                    }
                ],
                success_url=request.success_url,
                cancel_url=request.cancel_url,
                customer_email=request.customer_email,
                metadata={_REFERENCE_KEY: request.reference},
                # Stripe echoes this onto the PaymentIntent too, so the
                # reference survives even if we later reconcile from the
                # payment rather than the session.
                payment_intent_data={"metadata": {_REFERENCE_KEY: request.reference}},
                # Our own idempotency: a double-submitted "Pay now" button
                # returns the same session instead of opening a second one.
                idempotency_key=f"csg-checkout-{request.reference}",
            )
        except stripe.StripeError as exc:
            # `user_message` is Stripe's payer-safe text; the raw exception can
            # carry request details we do not want in a log.
            logger.error("Stripe checkout creation failed: %s", exc.user_message or type(exc).__name__)
            raise PaymentProviderError("Could not open a payment session.") from exc

        url = getattr(session, "url", None)
        session_id = getattr(session, "id", None)
        if not url or not session_id:
            raise PaymentProviderError("Stripe returned a session without a redirect URL.")
        return CheckoutSession(provider_session_id=session_id, redirect_url=url)

    # -- inbound ----------------------------------------------------------

    def verify_and_parse_webhook(self, payload: bytes, signature: str) -> WebhookEvent:
        if not signature:
            raise WebhookVerificationError("Webhook rejected: no signature header.")
        try:
            event = stripe.Webhook.construct_event(
                payload=payload, sig_header=signature, secret=self._webhook_secret
            )
        except Exception as exc:
            # Deliberately broad: a malformed payload raises ValueError and a
            # bad signature raises SignatureVerificationError, and both mean
            # exactly one thing here -- do not act on this.
            raise WebhookVerificationError("Webhook rejected: signature verification failed.") from exc

        event_id = self._get(event, "id")
        event_type = self._get(event, "type") or ""
        obj = self._event_object(event)

        reference = None
        metadata = (obj.get("metadata") or {}) if isinstance(obj, dict) else {}
        if isinstance(metadata, dict):
            reference = metadata.get(_REFERENCE_KEY)

        amount: Optional[Money] = None
        raw_amount = obj.get("amount_total") if isinstance(obj, dict) else None
        raw_currency = obj.get("currency") if isinstance(obj, dict) else None
        if isinstance(raw_amount, int) and raw_currency:
            amount = Money(minor_units=raw_amount, currency=str(raw_currency))

        payment_ref = obj.get("payment_intent") if isinstance(obj, dict) else None
        if isinstance(payment_ref, dict):
            payment_ref = payment_ref.get("id")

        outcome = PaymentOutcome.IGNORED
        failure_reason = None
        if event_type in _TERMINAL_SUCCESS_EVENTS:
            # A completed session whose payment is still processing (some bank
            # rails) must NOT credit the ledger yet.
            paid = obj.get("payment_status") if isinstance(obj, dict) else None
            outcome = PaymentOutcome.SUCCEEDED if paid == "paid" else PaymentOutcome.PENDING
        elif event_type in _TERMINAL_FAILURE_EVENTS:
            outcome = PaymentOutcome.FAILED
            failure_reason = "The payment was not completed by the payer's bank."
        elif event_type in _EXPIRY_EVENTS:
            outcome = PaymentOutcome.EXPIRED

        return WebhookEvent(
            event_id=str(event_id),
            event_type=str(event_type),
            outcome=outcome,
            reference=reference,
            provider_session_id=self._get(obj, "id") if isinstance(obj, dict) else None,
            provider_payment_ref=str(payment_ref) if payment_ref else None,
            amount=amount,
            failure_reason=failure_reason,
        )

    async def fetch_payment_status(self, provider_session_id: str) -> PaymentOutcome:
        try:
            session = await stripe.checkout.Session.retrieve_async(
                provider_session_id, api_key=self._secret_key
            )
        except stripe.StripeError as exc:
            raise PaymentProviderError("Could not read the payment session.") from exc

        status = self._get(session, "status")
        payment_status = self._get(session, "payment_status")
        if payment_status == "paid":
            return PaymentOutcome.SUCCEEDED
        if status == "expired":
            return PaymentOutcome.EXPIRED
        if status == "complete":
            return PaymentOutcome.PENDING
        return PaymentOutcome.PENDING

    async def refund(self, provider_payment_ref: str, amount: Money) -> RefundResult:
        try:
            refund = await stripe.Refund.create_async(
                api_key=self._secret_key,
                payment_intent=provider_payment_ref,
                amount=amount.minor_units,
            )
        except stripe.StripeError as exc:
            logger.error("Stripe refund failed: %s", exc.user_message or type(exc).__name__)
            raise PaymentProviderError("Could not issue the refund.") from exc

        refund_id = self._get(refund, "id")
        if not refund_id:
            raise PaymentProviderError("Stripe accepted the refund but returned no reference.")
        return RefundResult(provider_refund_ref=str(refund_id), amount=amount)

    # -- helpers ----------------------------------------------------------

    @staticmethod
    def _get(obj: Any, key: str) -> Any:
        """Stripe objects behave as both attribute holders and mappings, and
        the test doubles in this repo use plain namespaces. Read either."""
        if isinstance(obj, dict):
            return obj.get(key)
        return getattr(obj, key, None)

    @classmethod
    def _event_object(cls, event: Any) -> Dict[str, Any]:
        data = cls._get(event, "data")
        obj = cls._get(data, "object") if data is not None else None
        if obj is None:
            return {}
        if isinstance(obj, dict):
            return obj
        to_dict = getattr(obj, "to_dict", None)
        if callable(to_dict):
            result = to_dict()
            return result if isinstance(result, dict) else {}
        return {}
