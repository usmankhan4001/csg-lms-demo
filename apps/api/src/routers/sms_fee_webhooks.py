"""Inbound payment-provider webhooks.

WHY THIS IS A SEPARATE ROUTER. `sms_fees.router` carries
`Depends(require_sms_fees_feature)` at router level, which in turn depends on
`get_current_user_principal`. A provider webhook has no user and no session --
it authenticates by a cryptographic signature over the raw request body. Hung
on the fees router it would be rejected before the signature was ever checked,
so it lives here, mounted without those dependencies.

That makes this one of the very few unauthenticated write paths in the system,
so the rules are strict:

* The signature is verified against the RAW bytes before anything is parsed.
  An unverified request is rejected with 400 and nothing is written -- never
  logged-and-accepted.
* Verification failure returns no detail about why. A caller probing for the
  difference between "no signature", "bad signature" and "wrong secret" learns
  nothing from the response.
* The endpoint is idempotent by database constraint, not by convention: see
  `services/sms/fee_checkout.handle_provider_webhook`.
"""

import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.events.database import get_db_session
from src.schemas.sms_fee_payments import WebhookAck
from src.services.payments import PaymentProviderError, WebhookVerificationError
from src.services.sms.fee_checkout import handle_provider_webhook

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/{provider}/webhook",
    response_model=WebhookAck,
    summary="Receive A Payment Provider Webhook",
    description=(
        "Signature-verified provider callback. Unauthenticated by design — the "
        "signature over the raw body is the authentication. Idempotent: a "
        "replayed delivery is recognised and credits nothing a second time."
    ),
    responses={
        400: {"description": "Signature missing or invalid — nothing was written"},
        503: {"description": "No such payment provider is configured"},
    },
)
async def receive_payment_webhook(
    provider: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    stripe_signature: str | None = Header(default=None, alias="Stripe-Signature"),
) -> WebhookAck:
    raw_body = await request.body()

    # Each rail signs a different header. Resolved here rather than inside the
    # provider so the provider interface stays transport-agnostic.
    signature = stripe_signature or request.headers.get("X-Payment-Signature") or ""

    try:
        outcome = await handle_provider_webhook(
            session=session,
            provider_name=provider,
            payload=raw_body,
            signature=signature,
        )
    except WebhookVerificationError:
        # No detail, deliberately. Also not logged at error level with the
        # body: an attacker who can make us log arbitrary bytes has a foothold.
        logger.warning("Rejected an unverified %s payment webhook.", provider)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Webhook rejected.",
        )
    except PaymentProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    return WebhookAck(received=True, status=outcome)
