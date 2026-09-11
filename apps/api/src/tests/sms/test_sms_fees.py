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
