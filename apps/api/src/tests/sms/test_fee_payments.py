"""Online fee payment: the ledger is credited exactly once, or not at all.

The assertions here are weighted toward the ways money goes wrong quietly:

* A provider replays a webhook and a family is charged twice.
* A parent abandons a checkout and the voucher is left looking paid.
* One family can open a checkout against another family's invoice.
* A signature is not checked and an unauthenticated caller credits a voucher.

Every one of those is silent in production until somebody complains, so each
gets a test that fails loudly here instead.
"""

import datetime

import pytest
from fastapi import HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_fee_payments import (
    FeePaymentIntent,
    PaymentIntentStatus,
    PaymentWebhookEvent,
)
from src.db.sms_fees import FeePaymentReceipt, StudentFeeVoucher, VoucherStatus
from src.db.sms_identity import StudentGuardian
from src.services.payments.base import (
    CheckoutSession,
    PaymentOutcome,
    PaymentProvider,
    WebhookEvent,
    WebhookVerificationError,
)
from src.services.payments.money import Money, MoneyError, from_ledger_amount
from src.services.sms import fee_checkout
from src.services.sms.fee_checkout import handle_provider_webhook, start_checkout
from src.tests.sms._principals import SUPERADMIN, principal


# --------------------------------------------------------------------------
# A fake rail. Never touches the network; exists so the reconciliation logic
# is what is under test rather than Stripe's SDK.
# --------------------------------------------------------------------------
class FakeProvider(PaymentProvider):
    name = "fake"

    def __init__(self):
        self.created = []
        self.refunds = []
        self.next_status = PaymentOutcome.PENDING
        self.pending_event: WebhookEvent | None = None
        self.reject_signature = False

    async def create_checkout(self, request):
        self.created.append(request)
        return CheckoutSession(
            provider_session_id=f"sess_{request.reference}",
            redirect_url=f"https://pay.test/{request.reference}",
        )

    def verify_and_parse_webhook(self, payload: bytes, signature: str) -> WebhookEvent:
        if self.reject_signature or not signature:
            raise WebhookVerificationError("Webhook rejected.")
        assert self.pending_event is not None
        return self.pending_event

    async def fetch_payment_status(self, provider_session_id):
        return self.next_status

    async def refund(self, provider_payment_ref, amount):
        self.refunds.append((provider_payment_ref, amount))
        from src.services.payments.base import RefundResult

        return RefundResult(provider_refund_ref="re_1", amount=amount)


@pytest.fixture
def fake_provider(monkeypatch):
    provider = FakeProvider()
    monkeypatch.setattr(fee_checkout, "get_payment_provider", lambda name="fake": provider)
    return provider


@pytest.fixture
def payments_on(monkeypatch):
    """Fee policy with online payment enabled, without touching settings rows."""

    class _Policy:
        online_payments_enabled = True
        payment_provider = "fake"
        currency = "PKR"

    async def _get(session, org_id, campus_id=None):
        return _Policy()

    monkeypatch.setattr(fee_checkout, "get_fee_policy", _get)
    return _Policy


PARENT = principal("PARENT", user_id=5001, org_id=1)
OTHER_PARENT = principal("PARENT", user_id=5002, org_id=1)


_voucher_seq = 0


async def _voucher(db: AsyncSession, student_id: int = 7100, amount: float = 9000.0):
    """One ordinary unpaid voucher.

    Built directly rather than through `create_installment_plan`, which
    requires at least two due dates -- a single-instalment "plan" is just a
    voucher, and the service says so.
    """
    global _voucher_seq
    _voucher_seq += 1
    voucher = StudentFeeVoucher(
        student_id=student_id,
        voucher_no=f"V-TEST-{_voucher_seq:05d}",
        issue_date=datetime.date(2026, 9, 1),
        due_date=datetime.date(2026, 9, 30),
        tuition_fee=amount,
        total_amount=amount,
        paid_amount=0.0,
        balance_amount=amount,
        status=VoucherStatus.UNPAID,
    )
    db.add(voucher)
    await db.commit()
    await db.refresh(voucher)
    return voucher


async def _link_guardian(db: AsyncSession, guardian_user_id: int, student_id: int):
    db.add(StudentGuardian(guardian_user_id=guardian_user_id, student_id=student_id))
    await db.commit()


def _success_event(intent: FeePaymentIntent, event_id="evt_1") -> WebhookEvent:
    return WebhookEvent(
        event_id=event_id,
        event_type="checkout.session.completed",
        outcome=PaymentOutcome.SUCCEEDED,
        reference=intent.reference,
        provider_session_id=intent.provider_session_id,
        provider_payment_ref="pi_1",
        amount=Money(intent.amount_minor, intent.currency),
    )


# --------------------------------------------------------------------------
# Money
# --------------------------------------------------------------------------
class TestMoney:
    def test_two_decimal_currency_converts_exactly(self):
        assert from_ledger_amount(9000.0, "PKR").minor_units == 900000
        assert from_ledger_amount(1500.10, "PKR").minor_units == 150010

    def test_zero_decimal_currency_is_not_multiplied(self):
        """JPY 1000 is 1000, not 100000. Getting this wrong overcharges the
        payer by a hundred times."""
        assert from_ledger_amount(1000.0, "JPY").minor_units == 1000

    def test_sub_unit_amount_is_refused_not_rounded(self):
        with pytest.raises(MoneyError):
            from_ledger_amount(1500.005, "PKR")

    def test_float_minor_units_rejected(self):
        with pytest.raises(MoneyError):
            Money(minor_units=100.5, currency="PKR")  # type: ignore[arg-type]

    def test_round_trips_back_to_the_ledger_figure(self):
        assert from_ledger_amount(1500.10, "PKR").as_ledger_amount == 1500.10


# --------------------------------------------------------------------------
# Authorisation
# --------------------------------------------------------------------------
class TestCheckoutAuthorisation:
    @pytest.mark.asyncio
    async def test_parent_cannot_check_out_another_familys_invoice(
        self, db: AsyncSession, fake_provider, payments_on
    ):
        voucher = await _voucher(db, student_id=7200)
        await _link_guardian(db, guardian_user_id=PARENT.raw_claims["lh_user_id"], student_id=7200)

        with pytest.raises(HTTPException) as exc:
            await start_checkout(
                session=db, voucher_id=voucher.id, principal=OTHER_PARENT,
                success_url="https://s", cancel_url="https://c",
            )
        assert exc.value.status_code == 403
        # And nothing was written.
        intents = (await db.execute(select(FeePaymentIntent))).scalars().all()
        assert intents == []

    @pytest.mark.asyncio
    async def test_parent_can_check_out_their_own_childs_invoice(
        self, db: AsyncSession, fake_provider, payments_on
    ):
        voucher = await _voucher(db, student_id=7201)
        await _link_guardian(db, guardian_user_id=PARENT.raw_claims["lh_user_id"], student_id=7201)

        intent = await start_checkout(
            session=db, voucher_id=voucher.id, principal=PARENT,
            success_url="https://s", cancel_url="https://c",
        )
        assert intent.status == PaymentIntentStatus.PENDING
        assert intent.amount_minor == 900000
        assert getattr(intent, "_redirect_url", "").startswith("https://pay.test/")

    @pytest.mark.asyncio
    async def test_principal_without_an_org_is_refused(
        self, db: AsyncSession, fake_provider, payments_on
    ):
        """Never `principal.org_id or 1`. A principal with no school must not
        have its payment credited to whichever school happens to be first."""
        voucher = await _voucher(db, student_id=7202)
        orphan = principal("PARENT", user_id=5003, org_id=None)
        orphan.org_id = None

        with pytest.raises(HTTPException) as exc:
            await start_checkout(
                session=db, voucher_id=voucher.id, principal=orphan,
                success_url="https://s", cancel_url="https://c",
            )
        assert exc.value.status_code == 403


# --------------------------------------------------------------------------
# Checkout preconditions
# --------------------------------------------------------------------------
class TestCheckoutPreconditions:
    @pytest.mark.asyncio
    async def test_online_payment_off_by_default_refuses(
        self, db: AsyncSession, fake_provider, monkeypatch
    ):
        """A rail must not switch itself on because a key is in the
        environment. A test deployment would take real money."""
        class _Off:
            online_payments_enabled = False
            payment_provider = "fake"
            currency = "PKR"

        async def _get(session, org_id, campus_id=None):
            return _Off()

        monkeypatch.setattr(fee_checkout, "get_fee_policy", _get)
        voucher = await _voucher(db, student_id=7203)

        with pytest.raises(HTTPException) as exc:
            await start_checkout(
                session=db, voucher_id=voucher.id, principal=SUPERADMIN,
                success_url="https://s", cancel_url="https://c",
            )
        assert exc.value.status_code == 409

    @pytest.mark.asyncio
    async def test_already_paid_voucher_cannot_be_checked_out(
        self, db: AsyncSession, fake_provider, payments_on
    ):
        voucher = await _voucher(db, student_id=7204)
        voucher.status = VoucherStatus.PAID
        voucher.balance_amount = 0.0
        db.add(voucher)
        await db.commit()

        with pytest.raises(HTTPException) as exc:
            await start_checkout(
                session=db, voucher_id=voucher.id, principal=SUPERADMIN,
                success_url="https://s", cancel_url="https://c",
            )
        assert exc.value.status_code == 400


# --------------------------------------------------------------------------
# Webhook: the part that moves money
# --------------------------------------------------------------------------
class TestWebhookCrediting:
    @pytest.mark.asyncio
    async def test_successful_payment_credits_the_ledger_once(
        self, db: AsyncSession, fake_provider, payments_on
    ):
        voucher = await _voucher(db, student_id=7300)
        intent = await start_checkout(
            session=db, voucher_id=voucher.id, principal=SUPERADMIN,
            success_url="https://s", cancel_url="https://c",
        )
        fake_provider.pending_event = _success_event(intent)

        result = await handle_provider_webhook(
            session=db, provider_name="fake", payload=b"{}", signature="sig"
        )
        assert result == "credited"

        await db.refresh(voucher)
        assert voucher.status == VoucherStatus.PAID
        assert voucher.paid_amount == 9000.0
        assert voucher.balance_amount == 0.0

        receipts = (await db.execute(select(FeePaymentReceipt))).scalars().all()
        assert len(receipts) == 1
        assert receipts[0].amount_paid == 9000.0

    @pytest.mark.asyncio
    async def test_replayed_webhook_does_not_credit_twice(
        self, db: AsyncSession, fake_provider, payments_on
    ):
        """The one that costs a refund and an apology if it regresses."""
        voucher = await _voucher(db, student_id=7301)
        intent = await start_checkout(
            session=db, voucher_id=voucher.id, principal=SUPERADMIN,
            success_url="https://s", cancel_url="https://c",
        )
        event = _success_event(intent, event_id="evt_replay")
        fake_provider.pending_event = event

        first = await handle_provider_webhook(
            session=db, provider_name="fake", payload=b"{}", signature="sig"
        )
        second = await handle_provider_webhook(
            session=db, provider_name="fake", payload=b"{}", signature="sig"
        )

        assert first == "credited"
        assert second != "credited"

        await db.refresh(voucher)
        assert voucher.paid_amount == 9000.0, "voucher was credited twice"
        receipts = (await db.execute(select(FeePaymentReceipt))).scalars().all()
        assert len(receipts) == 1, "a second receipt was written for one payment"

    @pytest.mark.asyncio
    async def test_unsigned_webhook_is_rejected_and_writes_nothing(
        self, db: AsyncSession, fake_provider, payments_on
    ):
        voucher = await _voucher(db, student_id=7302)
        intent = await start_checkout(
            session=db, voucher_id=voucher.id, principal=SUPERADMIN,
            success_url="https://s", cancel_url="https://c",
        )
        fake_provider.pending_event = _success_event(intent, event_id="evt_unsigned")

        with pytest.raises(WebhookVerificationError):
            await handle_provider_webhook(
                session=db, provider_name="fake", payload=b"{}", signature=""
            )

        await db.refresh(voucher)
        assert voucher.paid_amount == 0.0
        assert (await db.execute(select(PaymentWebhookEvent))).scalars().all() == []

    @pytest.mark.asyncio
    async def test_abandoned_checkout_leaves_the_voucher_unpaid(
        self, db: AsyncSession, fake_provider, payments_on
    ):
        voucher = await _voucher(db, student_id=7303)
        intent = await start_checkout(
            session=db, voucher_id=voucher.id, principal=SUPERADMIN,
            success_url="https://s", cancel_url="https://c",
        )
        fake_provider.pending_event = WebhookEvent(
            event_id="evt_expired",
            event_type="checkout.session.expired",
            outcome=PaymentOutcome.EXPIRED,
            reference=intent.reference,
        )

        result = await handle_provider_webhook(
            session=db, provider_name="fake", payload=b"{}", signature="sig"
        )
        assert result == "abandoned"

        await db.refresh(voucher)
        assert voucher.status != VoucherStatus.PAID
        assert voucher.paid_amount == 0.0
        assert voucher.balance_amount == 9000.0

        await db.refresh(intent)
        assert intent.status == PaymentIntentStatus.ABANDONED
        # No receipt, and no half-written ledger row.
        assert (await db.execute(select(FeePaymentReceipt))).scalars().all() == []

    @pytest.mark.asyncio
    async def test_pending_payment_is_not_credited_yet(
        self, db: AsyncSession, fake_provider, payments_on
    ):
        """A bank rail can accept a payment that settles later. Crediting on
        acceptance credits money that has not arrived."""
        voucher = await _voucher(db, student_id=7304)
        intent = await start_checkout(
            session=db, voucher_id=voucher.id, principal=SUPERADMIN,
            success_url="https://s", cancel_url="https://c",
        )
        fake_provider.pending_event = WebhookEvent(
            event_id="evt_pending",
            event_type="checkout.session.completed",
            outcome=PaymentOutcome.PENDING,
            reference=intent.reference,
        )

        assert await handle_provider_webhook(
            session=db, provider_name="fake", payload=b"{}", signature="sig"
        ) == "pending"
        await db.refresh(voucher)
        assert voucher.paid_amount == 0.0

    @pytest.mark.asyncio
    async def test_amount_mismatch_is_flagged_not_credited(
        self, db: AsyncSession, fake_provider, payments_on
    ):
        voucher = await _voucher(db, student_id=7305)
        intent = await start_checkout(
            session=db, voucher_id=voucher.id, principal=SUPERADMIN,
            success_url="https://s", cancel_url="https://c",
        )
        fake_provider.pending_event = WebhookEvent(
            event_id="evt_mismatch",
            event_type="checkout.session.completed",
            outcome=PaymentOutcome.SUCCEEDED,
            reference=intent.reference,
            provider_payment_ref="pi_x",
            amount=Money(minor_units=100, currency="PKR"),
        )

        result = await handle_provider_webhook(
            session=db, provider_name="fake", payload=b"{}", signature="sig"
        )
        assert result == "amount-mismatch"

        await db.refresh(voucher)
        assert voucher.paid_amount == 0.0
        await db.refresh(intent)
        assert intent.failure_reason and "reconciliation" in intent.failure_reason

    @pytest.mark.asyncio
    async def test_unknown_reference_is_acknowledged_but_credits_nothing(
        self, db: AsyncSession, fake_provider, payments_on
    ):
        fake_provider.pending_event = WebhookEvent(
            event_id="evt_ghost",
            event_type="checkout.session.completed",
            outcome=PaymentOutcome.SUCCEEDED,
            reference="fee-does-not-exist",
            amount=Money(100, "PKR"),
        )
        result = await handle_provider_webhook(
            session=db, provider_name="fake", payload=b"{}", signature="sig"
        )
        assert result == "unknown-reference"
        assert (await db.execute(select(FeePaymentReceipt))).scalars().all() == []


# --------------------------------------------------------------------------
# Resolving attempts whose callback never arrived
# --------------------------------------------------------------------------
class TestReconcileStaleIntent:
    @pytest.mark.asyncio
    async def test_expired_session_marks_the_attempt_abandoned(
        self, db: AsyncSession, fake_provider, payments_on
    ):
        voucher = await _voucher(db, student_id=7400)
        intent = await start_checkout(
            session=db, voucher_id=voucher.id, principal=SUPERADMIN,
            success_url="https://s", cancel_url="https://c",
        )
        fake_provider.next_status = PaymentOutcome.EXPIRED

        resolved = await fee_checkout.reconcile_stale_intent(db, intent)
        assert resolved.status == PaymentIntentStatus.ABANDONED

        await db.refresh(voucher)
        assert voucher.paid_amount == 0.0

    @pytest.mark.asyncio
    async def test_polling_never_credits_even_when_the_provider_says_paid(
        self, db: AsyncSession, fake_provider, payments_on
    ):
        """Crediting belongs to the signed webhook path, which carries the
        replay guard. A polled read that also credited would be a second,
        unguarded way to write the ledger -- and the two could race."""
        voucher = await _voucher(db, student_id=7401)
        intent = await start_checkout(
            session=db, voucher_id=voucher.id, principal=SUPERADMIN,
            success_url="https://s", cancel_url="https://c",
        )
        fake_provider.next_status = PaymentOutcome.SUCCEEDED

        resolved = await fee_checkout.reconcile_stale_intent(db, intent)

        assert resolved.status == PaymentIntentStatus.PENDING
        await db.refresh(voucher)
        assert voucher.paid_amount == 0.0
        assert (await db.execute(select(FeePaymentReceipt))).scalars().all() == []


# --------------------------------------------------------------------------
# CSRF: the webhook must reach its handler, and nothing else may ride along
# --------------------------------------------------------------------------
class TestWebhookCsrfExemption:
    """A payment callback is server-to-server with no browser and no cookies,
    so CSRF's threat model does not apply -- but the exemption must be narrow.

    Stripe is already exempt via its signature header. This path rule exists
    so a second rail (JazzCash, Easypaisa) is not silently blocked the day it
    is added, which would make the provider seam a fiction.
    """

    @staticmethod
    def _middleware():
        from unittest.mock import MagicMock, patch

        from src.tests.security.test_csrf import _make_mock_config

        with patch(
            "src.security.csrf.get_learnhouse_config",
            return_value=_make_mock_config(allowed_origins=["https://example.com"]),
        ):
            from src.security.csrf import CSRFProtectionMiddleware

            return CSRFProtectionMiddleware(MagicMock())

    @staticmethod
    def _request(path: str, headers: dict | None = None):
        """Mirrors the helper in test_csrf.py: `url.path` must be a real
        string, because `_is_csrf_exempt` calls `.endswith` on it and an
        unconfigured MagicMock would return a truthy mock -- making every
        request look exempt and the test vacuous."""
        from unittest.mock import MagicMock

        req = MagicMock()
        req.method = "POST"
        req.headers = headers or {}
        req.url.path = path
        return req

    def test_fee_payment_webhook_path_is_exempt(self):
        mw = self._middleware()
        req = self._request(
            "/api/v1/sms/fee-payments/jazzcash/webhook",
            {"x-payment-signature": "abc"},
        )
        assert mw._is_csrf_exempt(req) is True

    def test_other_fee_endpoints_are_not_exempt(self):
        """The rule must not widen to the rest of the fee module, which is
        cookie-authenticated and genuinely needs CSRF protection."""
        mw = self._middleware()
        assert mw._is_csrf_exempt(
            self._request("/api/v1/sms/fees/vouchers/1/checkout")
        ) is False
        assert mw._is_csrf_exempt(
            self._request("/api/v1/sms/fee-payments/stripe/refund")
        ) is False


# --------------------------------------------------------------------------
# The Stripe adapter's parsing, with the SDK stubbed
# --------------------------------------------------------------------------
class TestStripeAdapterParsing:
    """Only the normalisation is under test here -- never the network.

    The case that matters most is a completed session whose payment is still
    processing: some bank-backed methods settle hours later, and treating that
    as SUCCEEDED credits a ledger against money that has not arrived.
    """

    @staticmethod
    def _provider():
        from src.services.payments.stripe_provider import StripePaymentProvider

        return StripePaymentProvider(secret_key="sk_test", webhook_secret="whsec_test")

    @staticmethod
    def _event(event_type, payment_status=None, amount=900000, reference="fee-abc"):
        return {
            "id": "evt_stripe_1",
            "type": event_type,
            "data": {
                "object": {
                    "id": "cs_test_1",
                    "metadata": {"csg_fee_intent_reference": reference},
                    "amount_total": amount,
                    "currency": "pkr",
                    "payment_status": payment_status,
                    "payment_intent": "pi_test_1",
                }
            },
        }

    def test_paid_session_is_succeeded(self, monkeypatch):
        import stripe

        monkeypatch.setattr(
            stripe.Webhook, "construct_event",
            lambda **kw: self._event("checkout.session.completed", payment_status="paid"),
        )
        event = self._provider().verify_and_parse_webhook(b"{}", "sig")
        assert event.outcome == PaymentOutcome.SUCCEEDED
        assert event.reference == "fee-abc"
        assert event.amount == Money(900000, "PKR")
        assert event.provider_payment_ref == "pi_test_1"

    def test_completed_but_unpaid_session_is_pending_not_succeeded(self, monkeypatch):
        import stripe

        monkeypatch.setattr(
            stripe.Webhook, "construct_event",
            lambda **kw: self._event("checkout.session.completed", payment_status="unpaid"),
        )
        event = self._provider().verify_and_parse_webhook(b"{}", "sig")
        assert event.outcome == PaymentOutcome.PENDING

    def test_expired_session_is_expired(self, monkeypatch):
        import stripe

        monkeypatch.setattr(
            stripe.Webhook, "construct_event",
            lambda **kw: self._event("checkout.session.expired"),
        )
        assert self._provider().verify_and_parse_webhook(b"{}", "sig").outcome == PaymentOutcome.EXPIRED

    def test_missing_signature_is_rejected_before_parsing(self):
        with pytest.raises(WebhookVerificationError):
            self._provider().verify_and_parse_webhook(b"{}", "")

    def test_bad_signature_is_rejected(self, monkeypatch):
        import stripe

        def _boom(**kw):
            raise ValueError("bad signature")

        monkeypatch.setattr(stripe.Webhook, "construct_event", _boom)
        with pytest.raises(WebhookVerificationError):
            self._provider().verify_and_parse_webhook(b"{}", "sig")

    def test_unconfigured_provider_refuses_to_construct(self):
        """Fail when payments are switched on, not when a parent is midway
        through paying."""
        from src.services.payments.base import PaymentProviderError
        from src.services.payments.stripe_provider import StripePaymentProvider

        with pytest.raises(PaymentProviderError):
            StripePaymentProvider(secret_key="", webhook_secret="whsec")


# --------------------------------------------------------------------------
# Refunds
# --------------------------------------------------------------------------
class TestOnlineRefund:
    async def _paid_intent(self, db: AsyncSession, fake_provider, student_id: int):
        voucher = await _voucher(db, student_id=student_id)
        intent = await start_checkout(
            session=db, voucher_id=voucher.id, principal=SUPERADMIN,
            success_url="https://s", cancel_url="https://c",
        )
        fake_provider.pending_event = _success_event(intent, event_id=f"evt_{student_id}")
        await handle_provider_webhook(
            session=db, provider_name="fake", payload=b"{}", signature="sig"
        )
        await db.refresh(voucher)
        await db.refresh(intent)
        return voucher, intent

    @pytest.mark.asyncio
    async def test_refund_reverses_the_ledger_exactly(
        self, db: AsyncSession, fake_provider, payments_on
    ):
        voucher, intent = await self._paid_intent(db, fake_provider, 7500)
        assert voucher.paid_amount == 9000.0

        await fee_checkout.refund_online_payment(
            session=db, intent=intent, amount=9000.0,
            reason="Withdrew before term start", principal=SUPERADMIN,
        )

        await db.refresh(voucher)
        # Reads exactly like a voucher that was never paid -- not a voucher
        # carrying a second, refund-aware balance.
        assert voucher.paid_amount == 0.0
        assert voucher.balance_amount == 9000.0
        # And the money actually went back through the rail it came in on.
        assert fake_provider.refunds == [("pi_1", Money(900000, "PKR"))]

    @pytest.mark.asyncio
    async def test_partial_refund_leaves_the_remainder_owing(
        self, db: AsyncSession, fake_provider, payments_on
    ):
        voucher, intent = await self._paid_intent(db, fake_provider, 7501)

        await fee_checkout.refund_online_payment(
            session=db, intent=intent, amount=2000.0,
            reason="Transport component waived", principal=SUPERADMIN,
        )

        await db.refresh(voucher)
        assert voucher.paid_amount == 7000.0
        assert voucher.balance_amount == 2000.0

    @pytest.mark.asyncio
    async def test_cannot_refund_more_than_was_paid(
        self, db: AsyncSession, fake_provider, payments_on
    ):
        _voucher_row, intent = await self._paid_intent(db, fake_provider, 7502)

        with pytest.raises(HTTPException) as exc:
            await fee_checkout.refund_online_payment(
                session=db, intent=intent, amount=9000.01,
                reason="Typo", principal=SUPERADMIN,
            )
        assert exc.value.status_code == 400
        assert fake_provider.refunds == [], "money was returned before validation"

    @pytest.mark.asyncio
    async def test_cannot_refund_an_attempt_that_never_succeeded(
        self, db: AsyncSession, fake_provider, payments_on
    ):
        voucher = await _voucher(db, student_id=7503)
        intent = await start_checkout(
            session=db, voucher_id=voucher.id, principal=SUPERADMIN,
            success_url="https://s", cancel_url="https://c",
        )
        with pytest.raises(HTTPException) as exc:
            await fee_checkout.refund_online_payment(
                session=db, intent=intent, amount=100.0,
                reason="Nope", principal=SUPERADMIN,
            )
        assert exc.value.status_code == 400
        assert fake_provider.refunds == []


class TestReceiptLinkSurvivesACrashBetweenCommits:
    """`handle_provider_webhook` credits money and writes the receipt in one
    transaction, then links `intent.receipt_id` in a SECOND one -- it has to,
    because the receipt id does not exist until the first commit returns.

    A crash in that window leaves a correctly-credited payment whose intent
    points at no receipt. The money is right; the audit link is missing, and
    the parent's payment-history screen reads exactly that column
    (`routers/sms_fees.py`). Nothing repaired it: `reconcile_stale_intent`
    returns early for anything already SUCCEEDED, so the state was terminal.
    """

    @pytest.mark.asyncio
    async def test_a_dangling_receipt_link_is_repaired(
        self, db: AsyncSession, fake_provider, payments_on
    ):
        from src.services.sms.fee_checkout import reconcile_stale_intent

        voucher = await _voucher(db, student_id=7801)
        intent = await start_checkout(
            session=db, voucher_id=voucher.id, principal=SUPERADMIN,
            success_url="https://s", cancel_url="https://c",
        )
        fake_provider.pending_event = _success_event(intent, event_id="evt_dangle")
        assert await handle_provider_webhook(
            session=db, provider_name="fake", payload=b"{}", signature="sig"
        ) == "credited"

        await db.refresh(intent)
        credited_receipt_id = intent.receipt_id
        assert credited_receipt_id is not None

        # Simulate the crash: the money landed, the link did not.
        intent.receipt_id = None
        db.add(intent)
        await db.commit()
        await db.refresh(intent)
        assert intent.receipt_id is None

        repaired = await reconcile_stale_intent(db, intent)

        assert repaired.receipt_id == credited_receipt_id, (
            "A credited payment was left with no receipt link and nothing "
            "could repair it."
        )

    @pytest.mark.asyncio
    async def test_no_receipt_means_no_invented_link(
        self, db: AsyncSession, fake_provider, payments_on
    ):
        """A missing receipt means the payment genuinely was not processed.

        Inventing a link there would assert money arrived when it did not --
        far worse than leaving the gap visible.
        """
        from src.services.sms.fee_checkout import backfill_missing_receipt_link

        voucher = await _voucher(db, student_id=7802)
        intent = await start_checkout(
            session=db, voucher_id=voucher.id, principal=SUPERADMIN,
            success_url="https://s", cancel_url="https://c",
        )
        intent.status = PaymentIntentStatus.SUCCEEDED
        intent.provider_payment_ref = "ref-that-has-no-receipt"
        intent.receipt_id = None
        db.add(intent)
        await db.commit()

        result = await backfill_missing_receipt_link(db, intent)
        assert result.receipt_id is None
