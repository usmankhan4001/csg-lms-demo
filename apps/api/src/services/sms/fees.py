import datetime
import logging
import uuid
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy import and_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_fees import (
    FeePaymentReceipt,
    FeeStructure,
    PaymentMethod,
    StudentFeeVoucher,
    VoucherStatus,
)
from src.schemas.sms_fees import (
    FeePaymentReceiptRead,
    GenerateVouchersRequest,
    RecordPaymentRequest,
    StudentFeeLedgerResponse,
    StudentFeeVoucherRead,
)

logger = logging.getLogger(__name__)


async def generate_vouchers_for_students(
    session: AsyncSession,
    payload: GenerateVouchersRequest,
) -> List[StudentFeeVoucher]:
    """
    Monthly & term fee voucher generation engine.
    """
    # Fetch structure
    struct_stmt = select(FeeStructure).where(FeeStructure.id == payload.fee_structure_id)
    structure = (await session.execute(struct_stmt)).scalar_one_or_none()
    if not structure:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Fee structure {payload.fee_structure_id} not found.",
        )

    discount = payload.discount_per_student or 0.0
    fine = payload.fine_per_student or 0.0
    gross = structure.tuition_fee + structure.transport_fee + structure.lab_fee + structure.other_fee
    net_total = max(0.0, gross + fine - discount)

    created_vouchers: List[StudentFeeVoucher] = []

    for s_id in payload.student_ids:
        # Generate unique voucher no
        rand_suffix = uuid.uuid4().hex[:6].upper()
        date_str = payload.issue_date.strftime("%Y%m")
        voucher_no = f"VCH-{date_str}-{s_id}-{rand_suffix}"

        voucher = StudentFeeVoucher(
            student_id=s_id,
            fee_structure_id=structure.id,
            voucher_no=voucher_no,
            issue_date=payload.issue_date,
            due_date=payload.due_date,
            tuition_fee=structure.tuition_fee,
            transport_fee=structure.transport_fee,
            lab_fee=structure.lab_fee,
            other_fee=structure.other_fee,
            discount=discount,
            fine=fine,
            total_amount=net_total,
            paid_amount=0.0,
            balance_amount=net_total,
            status=VoucherStatus.UNPAID,
            remarks=payload.remarks,
        )
        session.add(voucher)
        created_vouchers.append(voucher)

    await session.commit()
    for v in created_vouchers:
        await session.refresh(v)

    return created_vouchers


async def process_fee_payment(
    session: AsyncSession,
    payload: RecordPaymentRequest,
) -> FeePaymentReceipt:
    """
    Records fee collection against an invoice voucher and updates voucher state.
    """
    stmt = select(StudentFeeVoucher).where(StudentFeeVoucher.id == payload.voucher_id)
    voucher = (await session.execute(stmt)).scalar_one_or_none()
    if not voucher:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Voucher ID {payload.voucher_id} not found.",
        )

    if voucher.status == VoucherStatus.PAID:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Voucher is already fully paid.",
        )

    if payload.amount_paid > voucher.balance_amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Payment amount ({payload.amount_paid}) exceeds outstanding balance ({voucher.balance_amount}).",
        )

    # Generate receipt no
    rand_id = uuid.uuid4().hex[:6].upper()
    pay_date = payload.payment_date or datetime.date.today()
    receipt_no = f"REC-{pay_date.strftime('%Y%m%d')}-{voucher.id}-{rand_id}"

    receipt = FeePaymentReceipt(
        voucher_id=voucher.id,
        receipt_no=receipt_no,
        payment_date=pay_date,
        amount_paid=payload.amount_paid,
        payment_method=payload.payment_method,
        transaction_ref=payload.transaction_ref,
        collected_by=payload.collected_by,
        remarks=payload.remarks,
    )
    session.add(receipt)

    # Update voucher balances
    voucher.paid_amount += payload.amount_paid
    voucher.balance_amount = round(voucher.total_amount - voucher.paid_amount, 2)
    if voucher.balance_amount <= 0.001:
        voucher.balance_amount = 0.0
        voucher.status = VoucherStatus.PAID
    else:
        voucher.status = VoucherStatus.PARTIAL

    session.add(voucher)
    await session.commit()
    await session.refresh(receipt)
    return receipt


async def fetch_student_fee_ledger(
    session: AsyncSession,
    student_id: int,
) -> StudentFeeLedgerResponse:
    """
    Retrieves complete fee transaction history and outstanding balance for a student.
    """
    # Fetch all vouchers for student
    v_stmt = (
        select(StudentFeeVoucher)
        .where(StudentFeeVoucher.student_id == student_id)
        .order_by(StudentFeeVoucher.issue_date.desc())
    )
    vouchers = (await session.execute(v_stmt)).scalars().all()
    v_ids = [v.id for v in vouchers if v.id is not None]

    # Fetch all receipts
    receipts: List[FeePaymentReceipt] = []
    if v_ids:
        r_stmt = (
            select(FeePaymentReceipt)
            .where(FeePaymentReceipt.voucher_id.in_(v_ids))
            .order_by(FeePaymentReceipt.payment_date.desc())
        )
        receipts = (await session.execute(r_stmt)).scalars().all()

    total_invoiced = sum(v.total_amount for v in vouchers)
    total_paid = sum(v.paid_amount for v in vouchers)
    total_outstanding = sum(v.balance_amount for v in vouchers)

    return StudentFeeLedgerResponse(
        student_id=student_id,
        total_invoiced=round(total_invoiced, 2),
        total_paid=round(total_paid, 2),
        total_outstanding=round(total_outstanding, 2),
        vouchers=[StudentFeeVoucherRead.model_validate(v) for v in vouchers],
        receipts=[FeePaymentReceiptRead.model_validate(r) for r in receipts],
    )
