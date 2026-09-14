"""
Which outbound channels this deployment can actually send on.

Why this exists: the nurture runner read `channel` off each drip stage,
recorded it on the touch row, and then sent by email regardless. A lead with a
phone number and no email address hit `if not lead.email` and was marked
SKIPPED at every stage, forever. The skip was honestly recorded -- but SKIPPED
reads as a *delivery decision* ("nothing to send to"), when the truth was that
the school has no WhatsApp or SMS provider wired up at all. A family that
enquired by WhatsApp was never contacted, and nothing in the CRM said why.

So capability is resolved explicitly, and the two failures are distinguished:

  UNAVAILABLE -- this deployment cannot send on that channel at all. Nobody
                 configured a provider. Every lead on that channel is affected,
                 and it is an operations problem, not a data problem.
  SKIPPED     -- the channel works, but THIS lead has no address/number for it.
                 One lead is affected, and it is a data problem.

A school needs to be able to read "we cannot contact these 40 families at all"
off its own CRM. Collapsing both into SKIPPED made that unreadable.

This module deliberately does NOT integrate a WhatsApp or SMS provider. It
names the seam and reports the gap. Inventing an integration would be the same
class of mistake as the placeholder branding this codebase has already had to
tear out -- code that looks like a capability and is not one.
"""

import logging
from dataclasses import dataclass
from typing import Optional

from src.db.sms_revops import AdmissionsLead

logger = logging.getLogger(__name__)

# Channel tokens the drip engine emits on its stages.
CHANNEL_EMAIL = "email"
CHANNEL_WHATSAPP = "whatsapp"
CHANNEL_SMS = "sms"


@dataclass(frozen=True)
class ChannelCapability:
    """Whether this deployment can send on a channel, and why not."""

    channel: str
    configured: bool
    # Operator-facing sentence. Present only when `configured` is False, and
    # written to be actionable: it names what is missing, not just that
    # something is.
    reason: Optional[str] = None


def _email_configured() -> bool:
    """True when a mail provider is genuinely wired up.

    Mirrors what `send_email` itself checks, rather than assuming: an empty
    provider config means every send fails, and reporting a channel as
    available when every send on it fails is worse than reporting it down.
    """
    try:
        from config.config import get_learnhouse_config

        mailing = get_learnhouse_config().mailing_config
    except Exception:  # pragma: no cover - config import failure
        logger.exception("Could not read mailing config while resolving channel capability")
        return False

    if mailing is None:
        return False

    provider = (getattr(mailing, "email_provider", "") or "").strip().lower()
    if provider == "smtp":
        return bool(getattr(mailing, "smtp_host", None))
    if provider == "resend":
        return bool(getattr(mailing, "resend_api_key", None))
    return False


def resolve_channel_capability(channel: Optional[str]) -> ChannelCapability:
    """Can this deployment send on `channel` at all?"""
    token = (channel or CHANNEL_EMAIL).strip().lower()

    if token == CHANNEL_EMAIL:
        if _email_configured():
            return ChannelCapability(channel=token, configured=True)
        return ChannelCapability(
            channel=token,
            configured=False,
            reason=(
                "Email sending is not configured on this deployment: no mail "
                "provider credentials are set (LEARNHOUSE_RESEND_API_KEY "
                "or LEARNHOUSE_SMTP_HOST). No outbound email can be delivered until one is."
            ),
        )

    if token in (CHANNEL_WHATSAPP, CHANNEL_SMS):
        return ChannelCapability(
            channel=token,
            configured=False,
            reason=(
                f"No {token.upper()} provider is integrated in this deployment. "
                f"Leads who can only be reached by {token} cannot be contacted "
                "until one is connected."
            ),
        )

    return ChannelCapability(
        channel=token,
        configured=False,
        reason=f"Unknown outbound channel '{token}': no sender is registered for it.",
    )


def lead_address_for_channel(lead: AdmissionsLead, channel: Optional[str]) -> Optional[str]:
    """The address/number this lead can be reached on for `channel`.

    Returns None when the lead simply has nothing on file for that channel --
    a per-lead data gap, distinct from the deployment-wide capability gap.
    """
    token = (channel or CHANNEL_EMAIL).strip().lower()
    if token == CHANNEL_EMAIL:
        return (lead.email or "").strip() or None
    if token in (CHANNEL_WHATSAPP, CHANNEL_SMS):
        return (lead.phone or "").strip() or None
    return None


def contactable_channels(lead: AdmissionsLead) -> list:
    """Channels on which this lead could actually be reached today.

    Requires BOTH a configured provider and an address on the lead. Used to
    answer "can we reach this family at all?" -- the question the old SKIPPED
    row could not answer.
    """
    reachable = []
    for token in (CHANNEL_EMAIL, CHANNEL_WHATSAPP, CHANNEL_SMS):
        capability = resolve_channel_capability(token)
        if capability.configured and lead_address_for_channel(lead, token):
            reachable.append(token)
    return reachable


def channel_tokens(channel: Optional[str]) -> list:
    """Split a drip stage's channel string into its ordered legs.

    The drip engine emits COMPOUND tokens -- "email_whatsapp", "phone_whatsapp",
    "email_sms" -- meaning "try these, in this order", not one channel. Matches
    `_consent_gated_channel_tokens` in revops_drip_engine, which splits the
    same way; the two must agree or a stage could be consent-checked on one
    channel and delivered on another.
    """
    raw = (channel or CHANNEL_EMAIL).strip().lower()
    return [t for t in raw.split("_") if t] or [CHANNEL_EMAIL]


@dataclass(frozen=True)
class DeliveryRoute:
    """How a stage will actually be delivered, or why it cannot be."""

    channel: Optional[str]
    address: Optional[str]
    # Set only when no leg worked. Distinguishes the two failure modes the
    # whole module exists to separate.
    unavailable_reason: Optional[str] = None
    missing_address_for: Optional[str] = None

    @property
    def deliverable(self) -> bool:
        return bool(self.channel and self.address)


def resolve_delivery_route(lead: AdmissionsLead, channel: Optional[str]) -> DeliveryRoute:
    """Pick the first leg of a compound channel we can actually send on.

    Returns the winning channel and address, or -- when nothing works -- says
    which of the two problems it hit. A leg the deployment cannot send on at
    all (no provider) is an operations gap; a leg with no address on this lead
    is a data gap. Reporting them as the same thing is what hid WhatsApp-only
    families being silently dropped.
    """
    legs = channel_tokens(channel)
    unavailable_reasons = []
    missing_address = []

    for leg in legs:
        capability = resolve_channel_capability(leg)
        if not capability.configured:
            if capability.reason:
                unavailable_reasons.append(capability.reason)
            continue
        address = lead_address_for_channel(lead, leg)
        if not address:
            missing_address.append(leg)
            continue
        return DeliveryRoute(channel=leg, address=address)

    # Prefer reporting the operations gap: if the school cannot send on ANY leg,
    # that is the actionable fact, and it affects every lead rather than one.
    if unavailable_reasons and not missing_address:
        return DeliveryRoute(
            channel=None, address=None, unavailable_reason=" ".join(unavailable_reasons)
        )
    if missing_address:
        return DeliveryRoute(
            channel=None, address=None, missing_address_for=", ".join(missing_address)
        )
    return DeliveryRoute(
        channel=None,
        address=None,
        unavailable_reason=f"No sender is registered for channel '{channel}'.",
    )
