"""Which rail is in use, and refusing clearly when none is.

Adding JazzCash or Easypaisa means writing one module implementing
`PaymentProvider` and adding one line to `_BUILDERS`. Nothing else in the fee
module changes -- that is the whole point of the seam.
"""

import logging
from typing import Callable, Dict

from config.config import get_learnhouse_config
from src.services.payments.base import PaymentProvider, PaymentProviderError

logger = logging.getLogger(__name__)

DEFAULT_PROVIDER = "stripe"


def _build_stripe() -> PaymentProvider:
    # Imported lazily so a deployment running a different rail never needs the
    # Stripe SDK importable at boot.
    from src.services.payments.stripe_provider import StripePaymentProvider

    config = get_learnhouse_config()
    stripe_config = getattr(getattr(config, "payments_config", None), "stripe", None)
    if stripe_config is None:
        raise PaymentProviderError(
            "Online payment is not configured for this deployment."
        )
    return StripePaymentProvider(
        secret_key=stripe_config.stripe_secret_key or "",
        webhook_secret=stripe_config.stripe_webhook_standard_secret or "",
    )


_BUILDERS: Dict[str, Callable[[], PaymentProvider]] = {
    "stripe": _build_stripe,
}


def get_payment_provider(name: str = DEFAULT_PROVIDER) -> PaymentProvider:
    """Resolve a provider, or raise with something a human can act on.

    Never returns a stub or a no-op provider. A silently inert payment rail
    would let a school believe it was collecting money.
    """
    builder = _BUILDERS.get(name.lower())
    if builder is None:
        raise PaymentProviderError(
            f"No payment provider named {name!r} is available. "
            f"Configured rails: {', '.join(sorted(_BUILDERS)) or 'none'}."
        )
    return builder()
