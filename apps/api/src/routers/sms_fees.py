from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.events.database import get_db_session
from src.core.keycloak_auth import KeycloakUserPrincipal, get_current_user_principal
from src.db.sms_fees import (
    FeePaymentReceipt,
    FeeStructure,
    StudentFeeVoucher,
    VoucherStatus,
)
from src.schemas.sms_fees import (
    FeePaymentReceiptRead,
    FeeStructureCreate,
    FeeStructureRead,
    GenerateVouchersRequest,
    RecordPaymentRequest,
    StudentFeeLedgerResponse,
    StudentFeeVoucherRead,
)
from src.security.features_utils.dependencies import require_sms_fees_feature
from src.services.sms.fees import (
    fetch_student_fee_ledger,
    generate_vouchers_for_students,
    process_fee_payment,
)

router = APIRouter(dependencies=[Depends(require_sms_fees_feature)])


# ── Fee Structures ──

@router.post(
    "/structures",
    response_model=FeeStructureRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create Fee Structure",
)
async def create_fee_structure(
    payload: FeeStructureCreate,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> FeeStructureRead:
    total = payload.tuition_fee + payload.transport_fee + payload.lab_fee + payload.other_fee
    structure = FeeStructure(
        name=payload.name,
        campus_id=payload.campus_id,
        section_id=payload.section_id,
        academic_term_id=payload.academic_term_id,
        tuition_fee=payload.tuition_fee,
        transport_fee=payload.transport_fee,
        lab_fee=payload.lab_fee,
        other_fee=payload.other_fee,
        total_amount=round(total, 2),
    )
    session.add(structure)
    await session.commit()
    await session.refresh(structure)
    return FeeStructureRead.model_validate(structure)


@router.get(
    "/structures",
    response_model=List[FeeStructureRead],
    summary="List Fee Structures",
)
async def list_fee_structures(
    campus_id: Optional[int] = Query(None, description="Filter by Campus ID"),
    academic_term_id: Optional[int] = Query(None, description="Filter by Academic Term ID"),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> List[FeeStructureRead]:
    conditions = []
    if isinstance(campus_id, int):
        conditions.append(FeeStructure.campus_id == campus_id)
    if isinstance(academic_term_id, int):
        conditions.append(FeeStructure.academic_term_id == academic_term_id)

    stmt = select(FeeStructure)
    if conditions:
        stmt = stmt.where(and_(*conditions))
    structures = (await session.execute(stmt)).scalars().all()
    return [FeeStructureRead.model_validate(s) for s in structures]


# ── Voucher Generation & Listing ──

@router.post(
    "/vouchers/generate",
    response_model=List[StudentFeeVoucherRead],
    status_code=status.HTTP_201_CREATED,
    summary="Generate Student Fee Vouchers",
    description="Generate monthly/term fee invoice vouchers for a batch of students.",
)
async def generate_vouchers(
    payload: GenerateVouchersRequest,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> List[StudentFeeVoucherRead]:
    vouchers = await generate_vouchers_for_students(session=session, payload=payload)
    return [StudentFeeVoucherRead.model_validate(v) for v in vouchers]


@router.get(
    "/vouchers",
    response_model=List[StudentFeeVoucherRead],
    summary="List Fee Vouchers",
)
async def list_vouchers(
    student_id: Optional[int] = Query(None, description="Filter by Student ID"),
    status_filter: Optional[VoucherStatus] = Query(None, alias="status", description="Filter by voucher status"),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> List[StudentFeeVoucherRead]:
    conditions = []
    if isinstance(student_id, int):
        conditions.append(StudentFeeVoucher.student_id == student_id)
    if isinstance(status_filter, (VoucherStatus, str)):
        conditions.append(StudentFeeVoucher.status == status_filter)

    stmt = select(StudentFeeVoucher).order_by(StudentFeeVoucher.issue_date.desc())
    if conditions:
        stmt = stmt.where(and_(*conditions))
    vouchers = (await session.execute(stmt)).scalars().all()
    return [StudentFeeVoucherRead.model_validate(v) for v in vouchers]


# ── Fee Payments & Ledgers ──

@router.post(
    "/payments",
    response_model=FeePaymentReceiptRead,
    status_code=status.HTTP_201_CREATED,
    summary="Record Fee Payment",
    description="Record fee payment against a voucher and generate payment receipt.",
)
async def record_payment(
    payload: RecordPaymentRequest,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> FeePaymentReceiptRead:
    receipt = await process_fee_payment(session=session, payload=payload)
    return FeePaymentReceiptRead.model_validate(receipt)


@router.get(
    "/ledger/student/{student_id}",
    response_model=StudentFeeLedgerResponse,
    summary="Get Student Fee Ledger",
    description="Retrieve complete transaction history, vouchers, receipts, and balance for a student.",
)
async def get_student_fee_ledger_endpoint(
    student_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> StudentFeeLedgerResponse:
    return await fetch_student_fee_ledger(session=session, student_id=student_id)
