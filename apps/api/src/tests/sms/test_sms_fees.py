import datetime
import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_fees import PaymentMethod, VoucherStatus
from src.schemas.sms_fees import (
    FeeStructureCreate,
    GenerateVouchersRequest,
    RecordPaymentRequest,
)
from src.routers.sms_fees import (
    create_fee_structure,
    generate_vouchers,
    get_student_fee_ledger_endpoint,
    list_fee_structures,
    list_vouchers,
    record_payment,
)
from src.services.sms.fees import accrue_late_fees


@pytest.mark.asyncio
async def test_fee_management_and_voucher_lifecycle(db: AsyncSession):
    """Test full fee structure, batch voucher generation, payment processing, and ledger."""
    # 1. Create Fee Structure: Tuition 5000, Transport 1500, Lab 500, Other 200 = Total 7200
    struct_payload = FeeStructureCreate(
        name="Grade 10 Term Fee Structure",
        campus_id=1,
        section_id=1,
        academic_term_id=1,
        tuition_fee=5000.0,
        transport_fee=1500.0,
        lab_fee=500.0,
        other_fee=200.0,
    )
    structure = await create_fee_structure(payload=struct_payload, session=db)
    assert structure.id is not None
    assert structure.total_amount == 7200.0

    structures = await list_fee_structures(campus_id=1, session=db)
    assert len(structures) == 1

    # 2. Generate Vouchers for Students [601, 602] with 200 discount
    # Net Total = 7200 - 200 = 7000
    gen_payload = GenerateVouchersRequest(
        fee_structure_id=structure.id,
        student_ids=[601, 602],
        issue_date=datetime.date(2026, 9, 1),
        due_date=datetime.date(2026, 9, 20),
        discount_per_student=200.0,
        fine_per_student=0.0,
        remarks="Monthly invoice September 2026",
    )
    vouchers = await generate_vouchers(payload=gen_payload, session=db)
    assert len(vouchers) == 2
    v1 = vouchers[0]
    assert v1.total_amount == 7000.0
    assert v1.balance_amount == 7000.0
    assert v1.status == VoucherStatus.UNPAID
    assert v1.voucher_no.startswith("VCH-202609-")

    # 3. Partial Payment of 3000 for student 601
    pay1 = await record_payment(
        payload=RecordPaymentRequest(
            voucher_id=v1.id,
            amount_paid=3000.0,
            payment_method=PaymentMethod.BANK_TRANSFER,
            payment_date=datetime.date(2026, 9, 5),
            transaction_ref="TXN-987654",
            collected_by=99,
            remarks="Online bank transfer",
        ),
        session=db,
    )
    assert pay1.amount_paid == 3000.0
    assert pay1.receipt_no.startswith("REC-20260905-")

    # Check voucher state
    v_list = await list_vouchers(student_id=601, session=db)
    assert len(v_list) == 1
    assert v_list[0].paid_amount == 3000.0
    assert v_list[0].balance_amount == 4000.0
    assert v_list[0].status == VoucherStatus.PARTIAL

    # 4. Settle remaining 4000 for student 601
    await record_payment(
        payload=RecordPaymentRequest(
            voucher_id=v1.id,
            amount_paid=4000.0,
            payment_method=PaymentMethod.CASH,
            payment_date=datetime.date(2026, 9, 10),
        ),
        session=db,
    )

    # 5. Fetch Student Fee Ledger
    ledger = await get_student_fee_ledger_endpoint(student_id=601, session=db)
    assert ledger.student_id == 601
    assert ledger.total_invoiced == 7000.0
    assert ledger.total_paid == 7000.0
    assert ledger.total_outstanding == 0.0
    assert len(ledger.vouchers) == 1
    assert ledger.vouchers[0].status == VoucherStatus.PAID
    assert len(ledger.receipts) == 2


# ── Late Fee Accrual (M08) ──

async def _make_overdue_voucher(
    db: AsyncSession,
    student_id: int,
    due_date: datetime.date,
    total: float = 1000.0,
) -> int:
    """Create a single UNPAID voucher with a known principal and due date."""
    struct = await create_fee_structure(
        payload=FeeStructureCreate(
            name=f"LateFee Struct {student_id}",
            campus_id=9,
            section_id=9,
            academic_term_id=9,
            tuition_fee=total,
            transport_fee=0.0,
            lab_fee=0.0,
            other_fee=0.0,
        ),
        session=db,
    )
    vouchers = await generate_vouchers(
        payload=GenerateVouchersRequest(
            fee_structure_id=struct.id,
            student_ids=[student_id],
            issue_date=due_date - datetime.timedelta(days=30),
            due_date=due_date,
        ),
        session=db,
    )
    return vouchers[0].id


@pytest.mark.asyncio
async def test_late_fee_not_charged_before_due_date_or_within_grace(db: AsyncSession):
    """A voucher that is not yet overdue, or still inside the grace window,
    must accrue nothing."""
    due = datetime.date(2026, 6, 10)
    vid = await _make_overdue_voucher(db, 7001, due, total=1000.0)

    # Before the due date entirely.
    updated = await accrue_late_fees(session=db, as_of=due - datetime.timedelta(days=1), voucher_id=vid)
    assert updated == []

    # Past due but inside the 7-day grace window.
    updated = await accrue_late_fees(session=db, as_of=due + datetime.timedelta(days=5), voucher_id=vid)
    assert updated == []

    vouchers = await list_vouchers(student_id=7001, session=db)
    assert vouchers[0].late_fee_applied == 0.0
    assert vouchers[0].total_amount == 1000.0


@pytest.mark.asyncio
async def test_late_fee_charged_once_past_grace_and_is_idempotent(db: AsyncSession):
    """The core guarantee: re-running accrual must not double-charge."""
    due = datetime.date(2026, 6, 10)
    vid = await _make_overdue_voucher(db, 7002, due, total=1000.0)

    # 10 days past due = 3 days past the 7-day grace -> 1 period at 2% = 20.00
    as_of = due + datetime.timedelta(days=10)
    updated = await accrue_late_fees(session=db, as_of=as_of, voucher_id=vid)
    assert len(updated) == 1
    assert updated[0].late_fee_applied == 20.0
    assert updated[0].fine == 20.0
    assert updated[0].total_amount == 1020.0
    assert updated[0].balance_amount == 1020.0
    assert updated[0].late_fee_last_accrued_on == as_of

    # Running again on the SAME day must charge nothing further.
    again = await accrue_late_fees(session=db, as_of=as_of, voucher_id=vid)
    assert again == []

    vouchers = await list_vouchers(student_id=7002, session=db)
    assert vouchers[0].total_amount == 1020.0
    assert vouchers[0].late_fee_applied == 20.0


@pytest.mark.asyncio
async def test_late_fee_does_not_compound_and_respects_cap(db: AsyncSession):
    """Fees accrue on the ORIGINAL principal (never on prior late fees), and
    stop at the configured ceiling."""
    due = datetime.date(2026, 1, 10)
    vid = await _make_overdue_voucher(db, 7003, due, total=1000.0)

    # One period.
    await accrue_late_fees(session=db, as_of=due + datetime.timedelta(days=10), voucher_id=vid)
    # Three periods total (~70 days past grace).
    updated = await accrue_late_fees(session=db, as_of=due + datetime.timedelta(days=77), voucher_id=vid)
    assert len(updated) == 1
    # 3 periods x 2% of the 1000 principal = 60, NOT 2% of a growing balance.
    assert updated[0].late_fee_applied == 60.0
    assert updated[0].total_amount == 1060.0

    # Far future: cap at 20% of principal = 200, not 2% x many periods.
    capped = await accrue_late_fees(session=db, as_of=due + datetime.timedelta(days=3650), voucher_id=vid)
    assert len(capped) == 1
    assert capped[0].late_fee_applied == 200.0
    assert capped[0].total_amount == 1200.0

    # And once capped, further runs add nothing.
    assert await accrue_late_fees(session=db, as_of=due + datetime.timedelta(days=4000), voucher_id=vid) == []


@pytest.mark.asyncio
async def test_late_fee_skips_paid_and_cancelled_vouchers(db: AsyncSession):
    """A settled or void voucher must never have a debt resurrected on it."""
    due = datetime.date(2026, 6, 10)
    vid = await _make_overdue_voucher(db, 7004, due, total=1000.0)

    # Settle it in full.
    await record_payment(
        payload=RecordPaymentRequest(
            voucher_id=vid,
            amount_paid=1000.0,
            payment_method=PaymentMethod.CASH,
            payment_date=due,
        ),
        session=db,
    )

    updated = await accrue_late_fees(session=db, as_of=due + datetime.timedelta(days=90), voucher_id=vid)
    assert updated == []

    vouchers = await list_vouchers(student_id=7004, session=db)
    assert vouchers[0].status == VoucherStatus.PAID
    assert vouchers[0].total_amount == 1000.0
    assert vouchers[0].late_fee_applied == 0.0


@pytest.mark.asyncio
async def test_late_fee_on_partial_voucher_increases_outstanding_balance(db: AsyncSession):
    """A part-paid overdue voucher still accrues, and the extra shows up as
    outstanding balance the payment path will enforce."""
    due = datetime.date(2026, 6, 10)
    vid = await _make_overdue_voucher(db, 7005, due, total=1000.0)

    await record_payment(
        payload=RecordPaymentRequest(
            voucher_id=vid,
            amount_paid=400.0,
            payment_method=PaymentMethod.CASH,
            payment_date=due,
        ),
        session=db,
    )

    updated = await accrue_late_fees(session=db, as_of=due + datetime.timedelta(days=10), voucher_id=vid)
    assert len(updated) == 1
    assert updated[0].status == VoucherStatus.PARTIAL
    assert updated[0].total_amount == 1020.0
    # 1020 owed - 400 paid = 620 still outstanding.
    assert updated[0].balance_amount == 620.0

    ledger = await get_student_fee_ledger_endpoint(student_id=7005, session=db)
    assert ledger.total_outstanding == 620.0


# ---------------------------------------------------------------------------
# Authorization on the money-moving endpoints.
#
# Every write in this router was previously gated only by
# `get_current_user_principal` -- i.e. ANY authenticated user -- while
# `process_fee_payment` looks a voucher up by id with no ownership filter. A
# student or parent could therefore mark any family's voucher paid, create fee
# structures, bill the whole school, or charge everyone late fees.
#
# These assert the dependency wiring rather than going over HTTP, because the
# bug was in the dependency, not in the handler body: a handler can be
# perfectly correct and still be reachable by the wrong person.
# ---------------------------------------------------------------------------

def _dependency_source(func) -> str:
    """Flatten a route handler's dependency defaults into inspectable text."""
    import inspect

    sig = inspect.signature(func)
    return " ".join(repr(p.default) for p in sig.parameters.values())


@pytest.mark.parametrize(
    "handler_name",
    ["create_fee_structure", "generate_vouchers", "record_payment", "accrue_late_fees_endpoint"],
)
def test_fee_writes_are_restricted_to_back_office(handler_name):
    import src.routers.sms_fees as fees_router

    handler = getattr(fees_router, handler_name)
    source = _dependency_source(handler)

    # The open dependency must not be what guards a write.
    assert "get_current_user_principal" not in source, (
        f"{handler_name} is gated by get_current_user_principal, which admits ANY "
        "authenticated user -- including the student being billed."
    )
    assert "require_roles" in source or "RoleChecker" in source or "_BURSAR" in source, (
        f"{handler_name} must be role-gated."
    )


def test_bursar_roles_exclude_families_and_teachers():
    """A teacher has no business clearing a family's balance either."""
    from src.routers.sms_fees import _BURSAR

    assert "STUDENT" not in _BURSAR
    assert "PARENT" not in _BURSAR
    assert "TEACHER" not in _BURSAR
    assert "SCHOOL_ADMIN" in _BURSAR
