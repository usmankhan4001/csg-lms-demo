"""Turning a fee voucher into money in the school's account.

THE TWO HARD PARTS, and how each is handled:

1. **A replayed webhook must not credit twice.** Providers retry, sometimes
   for days. The guard is a unique constraint on (provider, event_id) in
   `PaymentWebhookEvent`, and the row is inserted in the SAME transaction that
   writes the receipt. A replay loses the insert race and the whole
   transaction -- event and ledger write together -- rolls back. This is a
   database guarantee, so it survives a cache eviction, a Redis outage, and
   two API workers handling the retry simultaneously.

2. **An abandoned checkout must leave nothing half-written.** An intent row is
   created BEFORE the payer is redirected, so an abandonment is a visible
   PENDING row that later resolves to ABANDONED, rather than silence. The
   voucher itself is untouched until a verified webhook says money arrived.

WHAT THIS DELIBERATELY DOES NOT DO: it never writes voucher balances itself.
Crediting goes through `process_fee_payment`, the same function the
back-office "record a payment" endpoint uses, so online and manual collection
cannot drift apart in their arithmetic. Two ledger writers is how a fee module
ends up with two different answers for what a family owes.
"""

import datetime
import logging
import uuid
from typing import List

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.keycloak_auth import SCHOOL_ADMIN, KeycloakUserPrincipal
from src.db.sms_fee_payments import (
    FeePaymentIntent,
    PaymentIntentStatus,
    PaymentWebhookEvent,
)
from src.db.sms_fees import StudentFeeVoucher, PaymentMethod, VoucherStatus
from src.schemas.sms_fees import RecordPaymentRequest
from src.security.school_ownership import get_own_children_ids
from src.services.payments import (
    CheckoutRequest,
    PaymentOutcome,
    PaymentProviderError,
    get_payment_provider,
)
from src.services.payments.money import Money, MoneyError, from_ledger_amount
from src.services.sms.fees import process_fee_payment
from src.services.sms.settings import get_fee_policy

logger = logging.getLogger(__name__)


async def assert_owns_student_or_privileged(
    principal: KeycloakUserPrincipal,
    student_id: int,
    db_session: AsyncSession,
) -> None:
    """Derived-value equivalent of `require_own_student_or_privileged`.

    That dependency reads `student_id` from path or query parameters. Checkout
    is addressed by VOUCHER id and the student is discovered from it, so the
    value to authorise against does not exist until after the lookup -- the
    same situation `assert_owns_section_or_privileged` exists for.

    Worth promoting into `security/school_ownership.py` alongside its
    siblings; kept local here only to avoid editing a shared security module
    while other lanes are in flight.
    """
    if principal.is_superadmin or principal.has_role(SCHOOL_ADMIN):
        return

    user_id = principal.raw_claims.get("lh_user_id")
    if user_id is not None:
        if student_id == user_id:
            return
        if student_id in await get_own_children_ids(user_id, db_session):
            return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You can only pay fees for your own record, or your own children's.",
    )


def _new_reference() -> str:
    return f"fee-{uuid.uuid4().hex}"


async def _load_voucher(session: AsyncSession, voucher_id: int) -> StudentFeeVoucher:
    voucher = (
        await session.execute(
            select(StudentFeeVoucher).where(StudentFeeVoucher.id == voucher_id)
        )
    ).scalar_one_or_none()
    if voucher is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Voucher ID {voucher_id} not found.",
        )
    return voucher


async def start_checkout(
    *,
    session: AsyncSession,
    voucher_id: int,
    principal: KeycloakUserPrincipal,
    success_url: str,
    cancel_url: str,
) -> FeePaymentIntent:
    """Open a payment session for one voucher and record the attempt."""
    if principal.org_id is None:
        # Never `principal.org_id or 1`. That pattern exists eighteen times in
        # this codebase and silently writes one school's data into another's;
        # with money involved it would take one family's payment and credit
        # another school's ledger.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is not attached to a school, so no payment can be taken.",
        )

    voucher = await _load_voucher(session, voucher_id)
    await assert_owns_student_or_privileged(principal, voucher.student_id, session)

    if voucher.status == VoucherStatus.CANCELLED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This voucher has been cancelled and cannot be paid.",
        )
    if voucher.status == VoucherStatus.PAID or voucher.balance_amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This voucher is already fully paid.",
        )

    policy = await get_fee_policy(session, principal.org_id)
    if not getattr(policy, "online_payments_enabled", False):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Online payment is not switched on for this school. A school "
                "administrator can enable it in fee settings."
            ),
        )

    currency = getattr(policy, "currency", None)
    if not currency:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No currency is configured for this school's fees.",
        )

    try:
        amount = from_ledger_amount(voucher.balance_amount, currency)
    except MoneyError as exc:
        # Refuse rather than round. Charging a payer a different figure from
        # the one printed on their invoice is not a rounding detail.
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    provider_name = getattr(policy, "payment_provider", None) or "stripe"
    try:
        provider = get_payment_provider(provider_name)
    except PaymentProviderError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    reference = _new_reference()
    intent = FeePaymentIntent(
        reference=reference,
        voucher_id=voucher.id,
        student_id=voucher.student_id,
        org_id=principal.org_id,
        provider=provider.name,
        amount_minor=amount.minor_units,
        currency=amount.currency,
        status=PaymentIntentStatus.CREATED,
        initiated_by_user_id=principal.raw_claims.get("lh_user_id"),
    )
    session.add(intent)
    # Persist the attempt BEFORE contacting the provider. If the provider call
    # then fails, the school still has a record that someone tried to pay --
    # which is exactly the evidence missing when a parent says they did.
    await session.commit()
    await session.refresh(intent)

    try:
        checkout = await provider.create_checkout(
            CheckoutRequest(
                reference=reference,
                amount=amount,
                description=f"School fees — voucher {voucher.voucher_no}",
                success_url=success_url,
                cancel_url=cancel_url,
                customer_email=None,
            )
        )
    except PaymentProviderError as exc:
        intent.status = PaymentIntentStatus.FAILED
        intent.failure_reason = str(exc)
        intent.updated_at = datetime.datetime.now(datetime.timezone.utc)
        session.add(intent)
        await session.commit()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    intent.provider_session_id = checkout.provider_session_id
    intent.status = PaymentIntentStatus.PENDING
    intent.updated_at = datetime.datetime.now(datetime.timezone.utc)
    session.add(intent)
    await session.commit()
    await session.refresh(intent)

    # Carried out-of-band to the router; not a column, because a redirect URL
    # is single-use and short-lived and has no business being stored.
    setattr(intent, "_redirect_url", checkout.redirect_url)
    return intent


async def handle_provider_webhook(
    *,
    session: AsyncSession,
    provider_name: str,
    payload: bytes,
    signature: str,
) -> str:
    """Verify, de-duplicate, and reconcile one provider notification.

    Returns a short status string for the response body. Raises only for
    conditions the provider should retry; anything terminal is recorded and
    acknowledged, because a provider that keeps retrying a permanently
    un-processable event is noise that hides real failures.
    """
    provider = get_payment_provider(provider_name)
    # WebhookVerificationError propagates to the router as a 400. An
    # unverified webhook is an unauthenticated instruction to move money and
    # is never logged-and-accepted.
    event = provider.verify_and_parse_webhook(payload, signature)

    # Insert-first idempotency, claimed with an explicit flush.
    #
    # The flush matters: without it the duplicate INSERT surfaces later, via
    # SQLAlchemy autoflush during the first SELECT below, as an IntegrityError
    # from a line that has nothing to do with idempotency. Flushing here
    # detects a replay at the exact point it happens. The row is written
    # inside the transaction but NOT committed, so if anything downstream
    # fails the event row rolls back with it -- and the eventual commit lands
    # event, intent and receipt together or not at all.
    session.add(
        PaymentWebhookEvent(
            provider=provider.name,
            event_id=event.event_id,
            event_type=event.event_type,
            intent_reference=event.reference,
        )
    )
    try:
        await session.flush()
    except IntegrityError:
        # Already handled -- a provider retry, or another worker holding the
        # same delivery. Nothing is written a second time.
        await session.rollback()
        return "duplicate"

    if event.outcome == PaymentOutcome.IGNORED or not event.reference:
        await session.commit()
        return "ignored"

    intent = (
        await session.execute(
            select(FeePaymentIntent).where(FeePaymentIntent.reference == event.reference)
        )
    ).scalar_one_or_none()

    if intent is None:
        # Verified, but about something we have no record of. Acknowledge so
        # the provider stops retrying, and leave the event row as evidence.
        await session.commit()
        logger.error(
            "Verified %s webhook %s referenced unknown intent %s.",
            provider.name, event.event_id, event.reference,
        )
        return "unknown-reference"

    if intent.status in (PaymentIntentStatus.SUCCEEDED, PaymentIntentStatus.FAILED):
        await session.commit()
        return "already-settled"

    now = datetime.datetime.now(datetime.timezone.utc)

    if event.outcome == PaymentOutcome.EXPIRED:
        intent.status = PaymentIntentStatus.ABANDONED
        intent.updated_at = now
        session.add(intent)
        await session.commit()
        return "abandoned"

    if event.outcome == PaymentOutcome.FAILED:
        intent.status = PaymentIntentStatus.FAILED
        intent.failure_reason = event.failure_reason or "The payment did not complete."
        intent.updated_at = now
        session.add(intent)
        await session.commit()
        return "failed"

    if event.outcome == PaymentOutcome.PENDING:
        await session.commit()
        return "pending"

    # -- SUCCEEDED --------------------------------------------------------
    paid = event.amount or Money(minor_units=intent.amount_minor, currency=intent.currency)
    if paid.minor_units != intent.amount_minor or paid.currency != intent.currency:
        # Verified as genuine, but not the figure we asked for. Crediting
        # either number would be a guess about real money, so it is recorded
        # for a human instead.
        intent.status = PaymentIntentStatus.SUCCEEDED
        intent.provider_payment_ref = event.provider_payment_ref
        intent.failure_reason = (
            f"Amount mismatch: expected {Money(intent.amount_minor, intent.currency)}, "
            f"provider reported {paid}. Not credited — needs manual reconciliation."
        )
        intent.updated_at = now
        session.add(intent)
        await session.commit()
        logger.error(
            "Payment amount mismatch on intent %s (event %s).", intent.reference, event.event_id
        )
        return "amount-mismatch"

    voucher = await _load_voucher(session, intent.voucher_id)
    if voucher.status == VoucherStatus.PAID or voucher.balance_amount <= 0:
        # Money arrived against a voucher settled some other way. Silently
        # dropping it would lose a real payment; crediting it would push the
        # voucher negative. Record it and surface it.
        intent.status = PaymentIntentStatus.SUCCEEDED
        intent.provider_payment_ref = event.provider_payment_ref
        intent.failure_reason = (
            "Payment received but the voucher was already settled. "
            "Not credited — needs manual reconciliation or refund."
        )
        intent.updated_at = now
        session.add(intent)
        await session.commit()
        logger.error("Payment for already-settled voucher %s.", voucher.id)
        return "already-paid"

    intent.status = PaymentIntentStatus.SUCCEEDED
    intent.provider_payment_ref = event.provider_payment_ref
    intent.updated_at = now
    session.add(intent)

    # `process_fee_payment` commits, which also commits the webhook-event row
    # and the intent update above -- receipt, voucher balance, intent and
    # replay guard all land together or not at all.
    receipt = await process_fee_payment(
        session=session,
        payload=RecordPaymentRequest(
            voucher_id=voucher.id,
            amount_paid=paid.as_ledger_amount,
            payment_method=PaymentMethod.ONLINE,
            payment_date=now.date(),
            transaction_ref=event.provider_payment_ref or event.provider_session_id,
            collected_by=None,
            remarks=f"Online payment via {provider.name} ({intent.reference}).",
        ),
    )

    intent.receipt_id = receipt.id
    session.add(intent)
    await session.commit()
    return "credited"


async def list_intents_for_voucher(
    session: AsyncSession, voucher_id: int
) -> List[FeePaymentIntent]:
    result = await session.execute(
        select(FeePaymentIntent)
        .where(FeePaymentIntent.voucher_id == voucher_id)
        .order_by(FeePaymentIntent.created_at.desc())
    )
    return list(result.scalars().all())


async def reconcile_stale_intent(
    session: AsyncSession, intent: FeePaymentIntent
) -> FeePaymentIntent:
    """Ask the provider what happened to an intent whose webhook never came.

    This is the ordinary case, not an edge case: a parent who closes the tab
    generates no webhook at all until the session expires, and some rails
    never send one.
    """
    if intent.status not in (PaymentIntentStatus.CREATED, PaymentIntentStatus.PENDING):
        return intent
    if not intent.provider_session_id:
        return intent

    provider = get_payment_provider(intent.provider)
    outcome = await provider.fetch_payment_status(intent.provider_session_id)

    if outcome == PaymentOutcome.EXPIRED:
        intent.status = PaymentIntentStatus.ABANDONED
    elif outcome == PaymentOutcome.FAILED:
        intent.status = PaymentIntentStatus.FAILED
    else:
        # SUCCEEDED is deliberately NOT credited here. Crediting belongs to
        # the signed webhook path, which has the replay guard; doing it from a
        # polled read would open a second, unguarded way to write the ledger.
        return intent

    intent.updated_at = datetime.datetime.now(datetime.timezone.utc)
    session.add(intent)
    await session.commit()
    await session.refresh(intent)
    return intent


async def refund_online_payment(
    *,
    session: AsyncSession,
    intent: FeePaymentIntent,
    amount: float,
    reason: str,
    principal: KeycloakUserPrincipal,
):
    """Return money that arrived online, through the rail it arrived on.

    ORDER IS DELIBERATE: the provider is called FIRST, and only then is the
    ledger written.

    Writing the ledger first and then failing at the provider would leave a
    voucher that says a family was refunded when no money moved -- the family
    chases a payment that was never sent, and the school's books say it was.
    The opposite failure (money returned, ledger write fails) is recoverable
    and, crucially, visible: `provider_refund_ref` is stamped on the intent
    before the ledger write is attempted, so the evidence survives.

    The ledger half goes through the existing `issue_refund`, which already
    recomputes the balance with the same expression `process_fee_payment`
    uses. A second refund path with its own arithmetic is how a voucher ends
    up with two different answers for what a family is owed.
    """
    from src.services.sms.fees_extended import issue_refund

    if intent.status != PaymentIntentStatus.SUCCEEDED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only a completed online payment can be refunded.",
        )
    if not intent.provider_payment_ref:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This payment has no provider reference, so it cannot be "
                "refunded automatically. Refund it manually instead."
            ),
        )
    if principal.org_id is not None and intent.org_id != principal.org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment attempt not found.",
        )

    try:
        money = from_ledger_amount(amount, intent.currency)
    except MoneyError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if money.minor_units > intent.amount_minor:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A refund cannot exceed the amount that was paid.",
        )

    provider = get_payment_provider(intent.provider)
    try:
        result = await provider.refund(intent.provider_payment_ref, money)
    except PaymentProviderError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    # Stamp the evidence before touching the ledger, so a failure in the next
    # step leaves a traceable record that money was actually returned.
    intent.failure_reason = None
    intent.provider_payment_ref = intent.provider_payment_ref
    intent.updated_at = datetime.datetime.now(datetime.timezone.utc)
    session.add(intent)
    await session.flush()

    refund = await issue_refund(
        session,
        voucher_id=intent.voucher_id,
        amount=money.as_ledger_amount,
        reason=reason,
        method="ONLINE",
        principal=principal,
    )
    return refund, result.provider_refund_ref
