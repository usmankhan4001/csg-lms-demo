"""Money as integer minor units, and the one place floats are allowed near it.

The existing fee ledger stores amounts as `float`. Payment providers, without
exception, take integers in the currency's smallest unit -- and they are right
to: 0.1 + 0.2 is not 0.3 in binary floating point, and a rounding error in a
fee ledger is somebody's money.

This module is the boundary. Everything above it (providers, intents,
webhooks) works in integer minor units. Conversion to and from the ledger's
float happens here, explicitly, in two named functions -- so when the ledger is
eventually migrated to a decimal type there is exactly one file to change.
"""

from dataclasses import dataclass

# Currencies with no minor unit at all. Sending 1000 to a provider for a
# zero-decimal currency means 1000, not 10.00, and multiplying by 100 there
# overcharges the payer by a hundred times. This list is the ISO-4217
# zero-decimal set as the major providers define it.
_ZERO_DECIMAL_CURRENCIES = frozenset(
    {
        "BIF", "CLP", "DJF", "GNF", "JPY", "KMF", "KRW", "MGA",
        "PYG", "RWF", "UGX", "VND", "VUV", "XAF", "XOF", "XPF",
    }
)

# Currencies whose minor unit is a thousandth. Providers expect these amounts
# to be a multiple of 10.
_THREE_DECIMAL_CURRENCIES = frozenset({"BHD", "IQD", "JOD", "KWD", "OMR", "TND"})


class MoneyError(ValueError):
    """Raised when an amount cannot be represented exactly. Never swallowed."""


def minor_unit_exponent(currency: str) -> int:
    code = currency.upper()
    if code in _ZERO_DECIMAL_CURRENCIES:
        return 0
    if code in _THREE_DECIMAL_CURRENCIES:
        return 3
    return 2


@dataclass(frozen=True)
class Money:
    """An exact amount. Immutable, and never constructed from a bare float
    without going through `from_ledger_amount`, which states its rounding."""

    minor_units: int
    currency: str

    def __post_init__(self) -> None:
        if not isinstance(self.minor_units, int) or isinstance(self.minor_units, bool):
            raise MoneyError("minor_units must be an int -- never a float.")
        if self.minor_units < 0:
            raise MoneyError("A payment amount cannot be negative.")
        if not self.currency or len(self.currency) != 3:
            raise MoneyError(f"{self.currency!r} is not a 3-letter currency code.")
        object.__setattr__(self, "currency", self.currency.upper())

    @property
    def as_ledger_amount(self) -> float:
        """Back to the float the existing ledger stores. Lossless in this
        direction: an integer scaled down by a power of ten is exactly
        representable at the magnitudes a school fee ever reaches."""
        return self.minor_units / (10 ** minor_unit_exponent(self.currency))

    def __str__(self) -> str:
        exp = minor_unit_exponent(self.currency)
        return f"{self.currency} {self.minor_units / (10 ** exp):.{exp}f}"


def from_ledger_amount(amount: float, currency: str) -> Money:
    """Convert a ledger float to exact minor units, refusing anything that
    would silently lose or invent a fraction of a unit.

    A voucher balance of 1500.005 is not a real amount of money in a 2-decimal
    currency; rounding it quietly would charge a payer something different
    from what the invoice says. Refusing is the honest behaviour -- the same
    principle this codebase applies to unsourced figures elsewhere.
    """
    if amount is None:
        raise MoneyError("No amount to charge.")
    if amount < 0:
        raise MoneyError("A payment amount cannot be negative.")

    exp = minor_unit_exponent(currency)
    scaled = amount * (10 ** exp)
    nearest = round(scaled)

    # Tolerance accommodates float representation error (1500.10 * 100 lands
    # on 150009.99999...), while still rejecting a genuinely sub-unit amount.
    if abs(scaled - nearest) > 1e-6:
        raise MoneyError(
            f"{amount} {currency.upper()} cannot be charged exactly: it is not a "
            f"whole number of minor units."
        )
    return Money(minor_units=int(nearest), currency=currency)
