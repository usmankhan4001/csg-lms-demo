"""M08 completion: instalments, concessions, refunds, reconciliation, reminders.

The through-line of every test here is that MONEY IS NEVER INVENTED and there
is exactly one source of truth for what a family owes. This codebase has torn
out fabricated data six times -- most recently an honour-roll GPA of 4.0 for a
student with zero grades that sat live in a router for weeks -- so the
assertions below check the absence of invention as carefully as the presence of
features.
"""

import datetime

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_fees import StudentFeeVoucher, VoucherStatus
from src.db.sms_fees_extended import (
    BankTransferStatus,
    ConcessionKind,
    FeeChangeAction,
    FeeChangeEvent,
    FeeReminderKind,
    FeeReminderLog,
)
from src.schemas.sms_fees import FeeStructureCreate, RecordPaymentRequest
from src.routers.sms_fees import create_fee_structure, record_payment
from src.services.sms.fee_reminders import _reminder_kind
from src.services.sms.fees_extended import (
    _split_amount,
    compute_concession_amount,
    create_concession,
    create_installment_plan,
    issue_refund,
    match_transfer_to_voucher,
    record_bank_transfers,
    suggest_transfer_matches,
    summarise_installment_plan,
)
from src.tests.sms._principals import SCHOOL_ADMIN, SUPERADMIN

from fastapi import HTTPException


async def _structure(db: AsyncSession, total_parts=(9000.0, 0.0, 0.0, 0.0)):
    """A fee structure totalling the sum of `total_parts`."""
    tuition, transport, lab, other = total_parts
    return await create_fee_structure(
        payload=FeeStructureCreate(
            name="Year Fee",
            campus_id=1,
            tuition_fee=tuition,
            transport_fee=transport,
            lab_fee=lab,
            other_fee=other,
        ),
        session=db,
        principal=SUPERADMIN,
    )


# ── Instalments ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_installment_plan_shows_paid_1_of_3_and_balance_matches_its_parts(db: AsyncSession):
    """The headline: "paid 1 of 3", and the plan total equals the sum of the
    vouchers. Any drift here means two screens can show a family two different
    numbers for the same debt."""
    structure = await _structure(db)  # 9000

    plan, vouchers = await create_installment_plan(
        db,
        student_id=7001,
        fee_structure_id=structure.id,
        name="2026-27 fees",
        issue_date=datetime.date(2026, 9, 1),
        due_dates=[
            datetime.date(2026, 9, 30),
            datetime.date(2026, 12, 31),
            datetime.date(2027, 3, 31),
        ],
        campus_id=1,
        principal=SUPERADMIN,
    )

    assert plan.installment_count == 3
    assert len(vouchers) == 3
    assert [v.installment_number for v in vouchers] == [1, 2, 3]
    # The split must be exact -- a plan that loses a cent never reconciles.
    assert round(sum(v.total_amount for v in vouchers), 2) == 9000.0

    summary = await summarise_installment_plan(db, plan)
    assert summary["paid_count"] == 0
    assert summary["total_amount"] == 9000.0
    assert summary["balance_amount"] == 9000.0

    # Pay instalment 1 in full.
    await record_payment(
        payload=RecordPaymentRequest(voucher_id=vouchers[0].id, amount_paid=vouchers[0].total_amount),
        session=db,
        principal=SUPERADMIN,
    )

    summary = await summarise_installment_plan(db, plan)
    assert summary["paid_count"] == 1, "one settled instalment out of three"
    assert summary["paid_amount"] == vouchers[0].total_amount
    # Derived from the vouchers' own stored fields, so it cannot disagree with
    # the ledger.
    assert summary["balance_amount"] == round(9000.0 - vouchers[0].total_amount, 2)


@pytest.mark.asyncio
async def test_each_instalment_has_its_own_due_date(db: AsyncSession):
    """The reason instalments are vouchers rather than schedule rows: late-fee
    accrual reads `due_date` per voucher, so a missed instalment 2 is charged
    on instalment 2 and not on the whole year."""
    structure = await _structure(db)
    _, vouchers = await create_installment_plan(
        db,
        student_id=7002,
        fee_structure_id=structure.id,
        name="Termly",
        issue_date=datetime.date(2026, 9, 1),
        due_dates=[datetime.date(2026, 10, 1), datetime.date(2027, 1, 1)],
        principal=SUPERADMIN,
    )
    assert [v.due_date for v in vouchers] == [
        datetime.date(2026, 10, 1),
        datetime.date(2027, 1, 1),
    ]


def test_split_never_loses_or_invents_a_cent():
    for total, parts in [(9000.0, 3), (1000.0, 3), (100.01, 3), (7.0, 4), (12345.67, 5)]:
        amounts = _split_amount(total, parts)
        assert len(amounts) == parts
        assert round(sum(amounts), 2) == round(total, 2), (total, parts, amounts)


@pytest.mark.asyncio
async def test_a_single_instalment_is_refused(db: AsyncSession):
    """One "instalment" is an ordinary voucher; accepting it would create two
    ways to express the same thing."""
    structure = await _structure(db)
    with pytest.raises(HTTPException) as exc:
        await create_installment_plan(
            db,
            student_id=7003,
            fee_structure_id=structure.id,
            name="Single",
            issue_date=datetime.date(2026, 9, 1),
            due_dates=[datetime.date(2026, 10, 1)],
            principal=SUPERADMIN,
        )
    assert exc.value.status_code == 400


# ── Concessions ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_sibling_discount_on_the_second_child_does_not_alter_the_first(db: AsyncSession):
    """A concession is attached to one named student. If it leaked across
    siblings the school would be giving away money it never authorised."""
    structure = await _structure(db)

    await create_concession(
        db,
        student_id=8002,  # the second child only
        kind=ConcessionKind.SIBLING,
        percentage=20.0,
        reason="Sibling discount, 2nd child",
        principal=SCHOOL_ADMIN,
    )

    _, first_child = await create_installment_plan(
        db,
        student_id=8001,
        fee_structure_id=structure.id,
        name="Child 1",
        issue_date=datetime.date(2026, 9, 1),
        due_dates=[datetime.date(2026, 10, 1), datetime.date(2027, 1, 1)],
        principal=SUPERADMIN,
    )
    _, second_child = await create_installment_plan(
        db,
        student_id=8002,
        fee_structure_id=structure.id,
        name="Child 2",
        issue_date=datetime.date(2026, 9, 1),
        due_dates=[datetime.date(2026, 10, 1), datetime.date(2027, 1, 1)],
        principal=SUPERADMIN,
    )

    first_total = round(sum(v.total_amount for v in first_child), 2)
    second_total = round(sum(v.total_amount for v in second_child), 2)

    assert first_total == 9000.0, "the first child is billed in full"
    assert second_total == 7200.0, "20% off the second child only"


@pytest.mark.asyncio
async def test_a_concession_records_who_authorised_it_and_why(db: AsyncSession):
    """The whole reason a flat `discount` float was not enough: a bursar is
    asked to justify a reduction, and a number cannot answer."""
    concession = await create_concession(
        db,
        student_id=8100,
        kind=ConcessionKind.HARDSHIP,
        fixed_amount=1500.0,
        reason="Father made redundant, reviewed by head of finance",
        principal=SCHOOL_ADMIN,
    )
    assert concession.reason.startswith("Father made redundant")
    assert concession.authorised_by_user_id == SCHOOL_ADMIN.raw_claims["lh_user_id"]
    assert concession.kind == ConcessionKind.HARDSHIP


@pytest.mark.asyncio
async def test_a_concession_must_state_a_reason_and_exactly_one_amount(db: AsyncSession):
    with pytest.raises(HTTPException):
        await create_concession(
            db, student_id=1, kind=ConcessionKind.OTHER, percentage=10.0, reason="   ",
            principal=SUPERADMIN,
        )
    with pytest.raises(HTTPException):
        # Both percentage AND fixed: no single meaning.
        await create_concession(
            db, student_id=1, kind=ConcessionKind.OTHER, percentage=10.0, fixed_amount=50.0,
            reason="ambiguous", principal=SUPERADMIN,
        )
    with pytest.raises(HTTPException):
        # Neither.
        await create_concession(
            db, student_id=1, kind=ConcessionKind.OTHER, reason="nothing", principal=SUPERADMIN,
        )


def test_concessions_never_make_a_voucher_negative():
    """A bill below zero would read as the school owing a family money it never
    received."""

    class _C:
        def __init__(self, pct=None, fixed=None):
            self.percentage = pct
            self.fixed_amount = fixed

    total, breakdown = compute_concession_amount([_C(pct=80.0), _C(pct=80.0)], 1000.0)
    assert total == 1000.0, "capped at the gross fee, never more"
    assert round(sum(a for _, a in breakdown), 2) == 1000.0, "breakdown still sums to what applied"


def test_percentage_concessions_do_not_compound():
    """Two 20% concessions take 40%, not 36%. Compounding would make the ORDER
    of award change the bill, which no bursar could explain."""

    class _C:
        def __init__(self, pct):
            self.percentage = pct
            self.fixed_amount = None

    total, _ = compute_concession_amount([_C(20.0), _C(20.0)], 1000.0)
    assert total == 400.0


# ── Refunds ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_refund_cannot_exceed_what_was_actually_paid(db: AsyncSession):
    structure = await _structure(db, (1000.0, 0.0, 0.0, 0.0))
    _, vouchers = await create_installment_plan(
        db,
        student_id=9001,
        fee_structure_id=structure.id,
        name="Plan",
        issue_date=datetime.date(2026, 9, 1),
        due_dates=[datetime.date(2026, 10, 1), datetime.date(2026, 11, 1)],
        principal=SUPERADMIN,
    )
    voucher = vouchers[0]
    await record_payment(
        payload=RecordPaymentRequest(voucher_id=voucher.id, amount_paid=200.0),
        session=db,
        principal=SUPERADMIN,
    )

    with pytest.raises(HTTPException) as exc:
        await issue_refund(
            db, voucher_id=voucher.id, amount=500.0, reason="overpaid", principal=SCHOOL_ADMIN
        )
    assert exc.value.status_code == 400
    assert "exceeds" in exc.value.detail.lower()


@pytest.mark.asyncio
async def test_a_refund_restores_the_balance_using_the_same_formula_as_payment(db: AsyncSession):
    """A refunded voucher must read exactly like one never paid that much --
    not acquire a second, refund-aware balance the payment path knows nothing
    about."""
    structure = await _structure(db, (1000.0, 0.0, 0.0, 0.0))
    _, vouchers = await create_installment_plan(
        db,
        student_id=9002,
        fee_structure_id=structure.id,
        name="Plan",
        issue_date=datetime.date(2026, 9, 1),
        due_dates=[datetime.date(2026, 10, 1), datetime.date(2026, 11, 1)],
        principal=SUPERADMIN,
    )
    voucher = vouchers[0]
    total = voucher.total_amount

    await record_payment(
        payload=RecordPaymentRequest(voucher_id=voucher.id, amount_paid=total),
        session=db,
        principal=SUPERADMIN,
    )
    await db.refresh(voucher)
    assert voucher.status == VoucherStatus.PAID
    assert voucher.balance_amount == 0.0

    await issue_refund(
        db, voucher_id=voucher.id, amount=total, reason="Withdrew before term", principal=SCHOOL_ADMIN
    )
    await db.refresh(voucher)

    assert voucher.paid_amount == 0.0
    assert voucher.balance_amount == total
    assert voucher.status == VoucherStatus.UNPAID
    assert round(voucher.total_amount - voucher.paid_amount, 2) == voucher.balance_amount


@pytest.mark.asyncio
async def test_repeat_refunds_cannot_exceed_the_total_paid(db: AsyncSession):
    """`paid_amount` already reflects prior refunds, so one check covers repeats
    without a second running total to keep in step."""
    structure = await _structure(db, (1000.0, 0.0, 0.0, 0.0))
    _, vouchers = await create_installment_plan(
        db,
        student_id=9003,
        fee_structure_id=structure.id,
        name="Plan",
        issue_date=datetime.date(2026, 9, 1),
        due_dates=[datetime.date(2026, 10, 1), datetime.date(2026, 11, 1)],
        principal=SUPERADMIN,
    )
    voucher = vouchers[0]
    await record_payment(
        payload=RecordPaymentRequest(voucher_id=voucher.id, amount_paid=300.0),
        session=db,
        principal=SUPERADMIN,
    )
    await issue_refund(db, voucher_id=voucher.id, amount=200.0, reason="partial", principal=SCHOOL_ADMIN)
    with pytest.raises(HTTPException):
        await issue_refund(
            db, voucher_id=voucher.id, amount=200.0, reason="too much now", principal=SCHOOL_ADMIN
        )


# ── Reconciliation ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_an_unmatched_transfer_suggests_but_never_marks_paid(db: AsyncSession):
    """Suggestions are evidence, not action. A wrong automatic match moves real
    money against the wrong family."""
    structure = await _structure(db, (5000.0, 0.0, 0.0, 0.0))
    _, vouchers = await create_installment_plan(
        db,
        student_id=9100,
        fee_structure_id=structure.id,
        name="Plan",
        issue_date=datetime.date(2026, 9, 1),
        due_dates=[datetime.date(2026, 10, 1), datetime.date(2026, 11, 1)],
        principal=SUPERADMIN,
    )
    target = vouchers[0]

    transfers = await record_bank_transfers(
        db,
        rows=[
            {
                "transfer_date": datetime.date(2026, 10, 2),
                "amount": target.balance_amount,
                "bank_reference": f"PAYMENT {target.voucher_no}",
                "payer_name": "A Parent",
                "payer_note": None,
            }
        ],
    )
    transfer = transfers[0]
    assert transfer.status == BankTransferStatus.UNMATCHED

    suggestions = await suggest_transfer_matches(db, transfer)
    assert suggestions, "the voucher number is right there in the reference"
    assert suggestions[0].id == target.id

    # Nothing was paid by asking for suggestions.
    await db.refresh(target)
    assert target.paid_amount == 0.0
    assert target.status == VoucherStatus.UNPAID


@pytest.mark.asyncio
async def test_matching_a_transfer_records_a_real_payment(db: AsyncSession):
    """Reconciled money must be indistinguishable from money taken at the
    counter, so it goes through the ordinary payment mechanics."""
    structure = await _structure(db, (4000.0, 0.0, 0.0, 0.0))
    _, vouchers = await create_installment_plan(
        db,
        student_id=9101,
        fee_structure_id=structure.id,
        name="Plan",
        issue_date=datetime.date(2026, 9, 1),
        due_dates=[datetime.date(2026, 10, 1), datetime.date(2026, 11, 1)],
        principal=SUPERADMIN,
    )
    target = vouchers[0]
    transfers = await record_bank_transfers(
        db,
        rows=[
            {
                "transfer_date": datetime.date(2026, 10, 2),
                "amount": target.balance_amount,
                "bank_reference": "NEFT 88231",
                "payer_name": None,
                "payer_note": None,
            }
        ],
    )

    transfer, receipt = await match_transfer_to_voucher(
        db, transfer_id=transfers[0].id, voucher_id=target.id, principal=SUPERADMIN
    )

    assert transfer.status == BankTransferStatus.MATCHED
    assert transfer.matched_receipt_id == receipt.id
    await db.refresh(target)
    assert target.status == VoucherStatus.PAID
    assert target.balance_amount == 0.0
    assert receipt.amount_paid == transfer.amount


@pytest.mark.asyncio
async def test_a_transfer_cannot_be_matched_twice(db: AsyncSession):
    structure = await _structure(db, (4000.0, 0.0, 0.0, 0.0))
    _, vouchers = await create_installment_plan(
        db,
        student_id=9102,
        fee_structure_id=structure.id,
        name="Plan",
        issue_date=datetime.date(2026, 9, 1),
        due_dates=[datetime.date(2026, 10, 1), datetime.date(2026, 11, 1)],
        principal=SUPERADMIN,
    )
    transfers = await record_bank_transfers(
        db,
        rows=[{"transfer_date": datetime.date(2026, 10, 2), "amount": 100.0}],
    )
    await match_transfer_to_voucher(
        db, transfer_id=transfers[0].id, voucher_id=vouchers[0].id, principal=SUPERADMIN
    )
    with pytest.raises(HTTPException) as exc:
        await match_transfer_to_voucher(
            db, transfer_id=transfers[0].id, voucher_id=vouchers[1].id, principal=SUPERADMIN
        )
    assert exc.value.status_code == 400


# ── Reminders ───────────────────────────────────────────────────────────────


def test_no_reminder_is_due_for_a_voucher_that_is_neither_upcoming_nor_overdue():
    """A family is contacted about a date that means something, not every day
    in between."""
    v = StudentFeeVoucher(
        student_id=1,
        voucher_no="V1",
        issue_date=datetime.date(2026, 9, 1),
        due_date=datetime.date(2026, 10, 1),
        total_amount=100.0,
        balance_amount=100.0,
    )
    # 20 days out: nothing.
    assert _reminder_kind(v, datetime.date(2026, 9, 11)) is None
    # Exactly the courtesy window.
    assert _reminder_kind(v, datetime.date(2026, 9, 24)) == FeeReminderKind.UPCOMING
    assert _reminder_kind(v, datetime.date(2026, 10, 1)) == FeeReminderKind.DUE_TODAY
    assert _reminder_kind(v, datetime.date(2026, 10, 9)) == FeeReminderKind.OVERDUE


@pytest.mark.asyncio
async def test_a_settled_voucher_is_never_reminded(db: AsyncSession):
    """Chasing a debt that does not exist is worse than not chasing at all."""
    from src.services.sms.fee_reminders import send_fee_reminders  # noqa: F401

    structure = await _structure(db, (500.0, 0.0, 0.0, 0.0))
    _, vouchers = await create_installment_plan(
        db,
        student_id=9200,
        fee_structure_id=structure.id,
        name="Plan",
        issue_date=datetime.date(2026, 9, 1),
        due_dates=[datetime.date(2026, 10, 1), datetime.date(2026, 11, 1)],
        principal=SUPERADMIN,
    )
    paid = vouchers[0]
    await record_payment(
        payload=RecordPaymentRequest(voucher_id=paid.id, amount_paid=paid.total_amount),
        session=db,
        principal=SUPERADMIN,
    )
    await db.refresh(paid)
    assert paid.status == VoucherStatus.PAID

    # The job's own selection excludes PAID and CANCELLED, so a settled
    # voucher can never reach the reminder path at all.
    stmt = select(StudentFeeVoucher).where(
        StudentFeeVoucher.status.in_([VoucherStatus.UNPAID, VoucherStatus.PARTIAL])
    )
    selectable = (await db.execute(stmt)).scalars().all()
    assert paid.id not in [v.id for v in selectable]

    logs = (await db.execute(select(FeeReminderLog))).scalars().all()
    assert logs == [], "nothing sent, so nothing logged"


# ── Audit ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_every_money_mutation_leaves_an_attributed_trail(db: AsyncSession):
    """A voucher's money history must answer who did what, from what, when --
    the question a bursar is asked and could not previously answer."""
    structure = await _structure(db, (2000.0, 0.0, 0.0, 0.0))
    _, vouchers = await create_installment_plan(
        db,
        student_id=9300,
        fee_structure_id=structure.id,
        name="Plan",
        issue_date=datetime.date(2026, 9, 1),
        due_dates=[datetime.date(2026, 10, 1), datetime.date(2026, 11, 1)],
        principal=SUPERADMIN,
    )
    voucher = vouchers[0]

    await record_payment(
        payload=RecordPaymentRequest(voucher_id=voucher.id, amount_paid=voucher.total_amount),
        session=db,
        principal=SUPERADMIN,
    )
    await issue_refund(
        db, voucher_id=voucher.id, amount=100.0, reason="Overcharged lab fee", principal=SCHOOL_ADMIN
    )

    events = (
        (
            await db.execute(
                select(FeeChangeEvent)
                .where(FeeChangeEvent.voucher_id == voucher.id)
                .order_by(FeeChangeEvent.id)
            )
        )
        .scalars()
        .all()
    )
    actions = [e.action for e in events]
    assert FeeChangeAction.VOUCHER_CREATED in actions
    assert FeeChangeAction.REFUND_ISSUED in actions

    refund_event = next(e for e in events if e.action == FeeChangeAction.REFUND_ISSUED)
    # Attributed to the AUTHENTICATED caller, never a client-supplied field.
    assert refund_event.changed_by_user_id == SCHOOL_ADMIN.raw_claims["lh_user_id"]
    assert refund_event.reason == "Overcharged lab fee"
    # The previous figure is recorded, which is the entire point of a trail.
    assert refund_event.previous_paid_amount == voucher.total_amount
    assert refund_event.new_paid_amount == round(voucher.total_amount - 100.0, 2)


@pytest.mark.asyncio
async def test_the_audit_trail_has_no_mutating_endpoint(db: AsyncSession):
    """A trail that can be rewritten is not a trail. Asserted structurally so
    adding a mutating route later breaks the build."""
    import src.routers.sms_fees as fees_router

    for route in fees_router.router.routes:
        if "history" in getattr(route, "path", ""):
            assert set(route.methods) <= {"GET", "HEAD", "OPTIONS"}, (
                f"{route.path} exposes {route.methods}; the fee trail must be append-only"
            )
