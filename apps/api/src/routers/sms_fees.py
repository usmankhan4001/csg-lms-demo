from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.events.database import get_db_session
from src.core.keycloak_auth import (
    KeycloakUserPrincipal,
    get_current_user_principal,
    require_roles,
)
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
from src.db.sms_fees_extended import (
    BankTransferRecord,
    FeeChangeEvent,
    FeeConcession,
    FeeInstallmentPlan,
    FeeReminderLog,
)
from src.schemas.sms_fees_extended import (
    BankTransferRead,
    ConcessionRead,
    CreateConcessionRequest,
    CreateInstallmentPlanRequest,
    FeeChangeEventRead,
    FeeReminderLogRead,
    ImportBankTransfersRequest,
    InstallmentPlanSummary,
    IssueRefundRequest,
    MatchTransferRequest,
    RefundRead,
    TransferMatchSuggestion,
)
from src.security.features_utils.dependencies import require_sms_fees_feature
from src.security.school_ownership import (
    assert_campus_allowed,
    require_own_student_or_privileged,
    resolve_scoped_campus_id,
)
from src.services.sms.fees_extended import (
    create_concession,
    create_installment_plan,
    issue_refund,
    list_unmatched_transfers,
    match_transfer_to_voucher,
    record_bank_transfers,
    suggest_transfer_matches,
    summarise_installment_plan,
)
from src.services.sms.fees import (
    DEFAULT_LATE_FEE_GRACE_DAYS,
    DEFAULT_LATE_FEE_MAX_PERCENT,
    DEFAULT_LATE_FEE_PERCENT_PER_PERIOD,
    accrue_late_fees,
    fetch_student_fee_ledger,
    generate_vouchers_for_students,
    process_fee_payment,
)

# Recording money against a voucher is a back-office action. TEACHER is
# excluded alongside STUDENT/PARENT: a teacher has no business clearing a
# family's balance either.
_BURSAR = ["SUPER_ADMIN", "SCHOOL_ADMIN", "STAFF"]

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
    principal: KeycloakUserPrincipal = Depends(require_roles(_BURSAR)),
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
    principal: KeycloakUserPrincipal = Depends(require_roles(_BURSAR)),
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
    description=(
        "Record fee payment against a voucher and generate payment receipt. "
        "Restricted to back-office staff: this endpoint was previously open to "
        "ANY authenticated user and process_fee_payment looks a voucher up by "
        "id with no ownership filter, so a student or parent could mark any "
        "family's voucher paid."
    ),
    responses={403: {"description": "Only back-office staff may record payments"}},
)
async def record_payment(
    payload: RecordPaymentRequest,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_BURSAR)),
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
    principal: KeycloakUserPrincipal = Depends(require_own_student_or_privileged()),
) -> StudentFeeLedgerResponse:
    return await fetch_student_fee_ledger(session=session, student_id=student_id)


# ── Late Fee Accrual (M08) ──

@router.post(
    "/vouchers/accrue-late-fees",
    response_model=List[StudentFeeVoucherRead],
    summary="Accrue Late Fees On Overdue Vouchers",
    description=(
        "Charges late fees on every overdue UNPAID/PARTIAL voucher and persists "
        "the new balance. Safe to run repeatedly (idempotent: recomputes the "
        "target fee and charges only the difference), so it suits a nightly "
        "scheduled call as well as manual use. Late fees never compound and are "
        "capped as a percentage of the original principal. Returns only the "
        "vouchers that actually changed."
    ),
)
async def accrue_late_fees_endpoint(
    student_id: Optional[int] = Query(None, description="Limit accrual to one student"),
    voucher_id: Optional[int] = Query(None, description="Limit accrual to one voucher"),
    rate_percent: float = Query(
        DEFAULT_LATE_FEE_PERCENT_PER_PERIOD, ge=0, le=100,
        description="Late fee % of overdue principal, per 30-day period",
    ),
    grace_days: int = Query(
        DEFAULT_LATE_FEE_GRACE_DAYS, ge=0, le=365,
        description="Days after the due date before any late fee applies",
    ),
    max_percent: float = Query(
        DEFAULT_LATE_FEE_MAX_PERCENT, ge=0, le=100,
        description="Ceiling on total late fee, as % of overdue principal",
    ),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_BURSAR)),
) -> List[StudentFeeVoucherRead]:
    updated = await accrue_late_fees(
        session=session,
        rate_percent=rate_percent,
        grace_days=grace_days,
        max_percent=max_percent,
        student_id=student_id,
        voucher_id=voucher_id,
    )
    return [StudentFeeVoucherRead.model_validate(v) for v in updated]


# ===========================================================================
# M08 completion: instalments, concessions, refunds, reconciliation, audit.
#
# Gating note: every write below is _BURSAR (back-office). Reads that concern
# one family's money use `require_own_student_or_privileged` so a parent can
# see their own child's plan, matching the existing ledger endpoint.
# ===========================================================================

# Authorising a concession or a refund gives money away, so it sits above the
# ordinary bursar line: a clerk who can take a payment should not be able to
# waive one unilaterally. Segregation of duties -- the same reasoning that put
# journal-entry reversal above journal-entry creation.
_BURSAR_LEAD = ["SUPER_ADMIN", "SCHOOL_ADMIN"]


@router.post(
    "/installment-plans",
    response_model=InstallmentPlanSummary,
    status_code=status.HTTP_201_CREATED,
    summary="Create Fee Instalment Plan",
    description=(
        "Split a term or year fee into scheduled instalments. Each instalment "
        "is a real voucher, so payments, receipts, the ledger and late-fee "
        "accrual all work on it unchanged -- and a family that misses "
        "instalment 2 is charged a late fee on instalment 2 rather than on the "
        "whole year."
    ),
)
async def create_installment_plan_endpoint(
    payload: CreateInstallmentPlanRequest,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_BURSAR)),
) -> InstallmentPlanSummary:
    assert_campus_allowed(principal, payload.campus_id)
    plan, _ = await create_installment_plan(
        session,
        student_id=payload.student_id,
        fee_structure_id=payload.fee_structure_id,
        name=payload.name,
        due_dates=payload.due_dates,
        issue_date=payload.issue_date,
        campus_id=payload.campus_id,
        academic_term_id=payload.academic_term_id,
        apply_concessions=payload.apply_concessions,
        principal=principal,
    )
    summary = await summarise_installment_plan(session, plan)
    return InstallmentPlanSummary(
        **{k: v for k, v in summary.items() if k != "vouchers"},
        vouchers=[StudentFeeVoucherRead.model_validate(v) for v in summary["vouchers"]],
    )


@router.get(
    "/installment-plans/student/{student_id}",
    response_model=List[InstallmentPlanSummary],
    summary="List A Student Instalment Plans",
)
async def list_student_installment_plans(
    student_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_own_student_or_privileged()),
) -> List[InstallmentPlanSummary]:
    plans = (
        (
            await session.execute(
                select(FeeInstallmentPlan)
                .where(FeeInstallmentPlan.student_id == student_id)
                .order_by(FeeInstallmentPlan.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    out: List[InstallmentPlanSummary] = []
    for plan in plans:
        summary = await summarise_installment_plan(session, plan)
        out.append(
            InstallmentPlanSummary(
                **{k: v for k, v in summary.items() if k != "vouchers"},
                vouchers=[StudentFeeVoucherRead.model_validate(v) for v in summary["vouchers"]],
            )
        )
    return out


@router.post(
    "/concessions",
    response_model=ConcessionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Authorise A Fee Concession",
    description=(
        "Record a sibling discount, scholarship or hardship reduction for one "
        "named student, with the reason and the authorising officer. Attached "
        "to a named student rather than inferred: which child counts as the "
        "second child is a school policy question, and guessing it would "
        "quietly award or withhold money from a real family."
    ),
)
async def create_concession_endpoint(
    payload: CreateConcessionRequest,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_BURSAR_LEAD)),
) -> ConcessionRead:
    assert_campus_allowed(principal, payload.campus_id)
    concession = await create_concession(
        session,
        student_id=payload.student_id,
        kind=payload.kind,
        reason=payload.reason,
        percentage=payload.percentage,
        fixed_amount=payload.fixed_amount,
        campus_id=payload.campus_id,
        valid_from=payload.valid_from,
        valid_until=payload.valid_until,
        principal=principal,
    )
    return ConcessionRead.model_validate(concession)


@router.get(
    "/concessions/student/{student_id}",
    response_model=List[ConcessionRead],
    summary="List A Student Concessions",
)
async def list_student_concessions(
    student_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_own_student_or_privileged()),
) -> List[ConcessionRead]:
    rows = (
        (
            await session.execute(
                select(FeeConcession)
                .where(FeeConcession.student_id == student_id)
                .order_by(FeeConcession.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return [ConcessionRead.model_validate(c) for c in rows]


@router.post(
    "/refunds",
    response_model=RefundRead,
    status_code=status.HTTP_201_CREATED,
    summary="Issue A Fee Refund",
    description=(
        "Return money to a family. Can never exceed what was actually paid on "
        "the voucher, and recomputes the balance with the same expression the "
        "payment path uses, so a refunded voucher reads exactly like one that "
        "was never paid that much."
    ),
)
async def issue_refund_endpoint(
    payload: IssueRefundRequest,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_BURSAR_LEAD)),
) -> RefundRead:
    refund = await issue_refund(
        session,
        voucher_id=payload.voucher_id,
        amount=payload.amount,
        reason=payload.reason,
        method=payload.method,
        refund_date=payload.refund_date,
        principal=principal,
    )
    return RefundRead.model_validate(refund)


@router.post(
    "/bank-transfers/import",
    response_model=List[BankTransferRead],
    status_code=status.HTTP_201_CREATED,
    summary="Import Bank Statement Lines",
    description=(
        "Take already-parsed bank statement rows into the unmatched queue. "
        "Parsing a particular bank export format is deliberately not done "
        "here: formats are per-bank and per-country, and a parser guessing a "
        "column would silently attribute money to the wrong family."
    ),
)
async def import_bank_transfers(
    payload: ImportBankTransfersRequest,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_BURSAR)),
) -> List[BankTransferRead]:
    assert_campus_allowed(principal, payload.campus_id)
    created = await record_bank_transfers(
        session,
        rows=[r.model_dump() for r in payload.rows],
        campus_id=payload.campus_id,
    )
    return [BankTransferRead.model_validate(t) for t in created]


@router.get(
    "/bank-transfers/unmatched",
    response_model=List[BankTransferRead],
    summary="List Unmatched Bank Transfers",
    description="The reconciliation queue: money received that nobody has attributed to a family yet.",
)
async def list_unmatched_transfers_endpoint(
    campus_id: Optional[int] = Query(None, description="Filter by campus"),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_BURSAR)),
) -> List[BankTransferRead]:
    scoped = resolve_scoped_campus_id(principal, campus_id)
    rows = await list_unmatched_transfers(session, campus_id=scoped)
    return [BankTransferRead.model_validate(t) for t in rows]


@router.get(
    "/bank-transfers/{transfer_id}/suggestions",
    response_model=List[TransferMatchSuggestion],
    summary="Suggest Vouchers For An Unmatched Transfer",
    description=(
        "Candidates only -- nothing here marks anything paid. A wrong automatic "
        "match moves real money against the wrong family, so a human always "
        "confirms. Each suggestion states the evidence it was found on."
    ),
)
async def suggest_transfer_matches_endpoint(
    transfer_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_BURSAR)),
) -> List[TransferMatchSuggestion]:
    transfer = (
        await session.execute(
            select(BankTransferRecord).where(BankTransferRecord.id == transfer_id)
        )
    ).scalar_one_or_none()
    if not transfer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Bank transfer {transfer_id} not found."
        )
    assert_campus_allowed(principal, transfer.campus_id)

    candidates = await suggest_transfer_matches(session, transfer)
    haystack = " ".join(
        filter(
            None,
            [transfer.bank_reference or "", transfer.payer_note or "", transfer.payer_name or ""],
        )
    ).upper()

    out: List[TransferMatchSuggestion] = []
    for v in candidates:
        matched_on: List[str] = []
        if v.voucher_no and v.voucher_no.upper() in haystack:
            matched_on.append("voucher number in payer reference")
        if abs(round(v.balance_amount, 2) - round(transfer.amount, 2)) < 0.01:
            matched_on.append("amount equals outstanding balance")
        if str(v.student_id) in haystack:
            matched_on.append("student id in payer reference")
        out.append(
            TransferMatchSuggestion(
                voucher=StudentFeeVoucherRead.model_validate(v), matched_on=matched_on
            )
        )
    return out


@router.post(
    "/bank-transfers/match",
    response_model=BankTransferRead,
    summary="Match A Bank Transfer To A Voucher",
    description=(
        "Attribute a transfer by recording a real payment through the ordinary "
        "payment path, so a reconciled payment is indistinguishable from one "
        "taken at the counter and cannot drift from it."
    ),
)
async def match_transfer_endpoint(
    payload: MatchTransferRequest,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_BURSAR)),
) -> BankTransferRead:
    transfer, _ = await match_transfer_to_voucher(
        session,
        transfer_id=payload.transfer_id,
        voucher_id=payload.voucher_id,
        principal=principal,
    )
    return BankTransferRead.model_validate(transfer)


@router.get(
    "/vouchers/{voucher_id}/history",
    response_model=List[FeeChangeEventRead],
    summary="Read A Voucher Money Trail",
    description=(
        "Append-only record of every money mutation on this voucher. No "
        "endpoint updates or deletes a row here -- a trail that can be "
        "rewritten is not a trail."
    ),
)
async def get_voucher_history(
    voucher_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_BURSAR)),
) -> List[FeeChangeEventRead]:
    rows = (
        (
            await session.execute(
                select(FeeChangeEvent)
                .where(FeeChangeEvent.voucher_id == voucher_id)
                .order_by(FeeChangeEvent.created_at, FeeChangeEvent.id)
            )
        )
        .scalars()
        .all()
    )
    return [FeeChangeEventRead.model_validate(e) for e in rows]


@router.get(
    "/reminders",
    response_model=List[FeeReminderLogRead],
    summary="List Fee Reminders Sent",
    description=(
        "What the school actually told families, and what was actually "
        "delivered. `recipients` and `delivered` differ whenever mail is "
        "unconfigured -- which is exactly the gap a school needs to see rather "
        "than assume reminders went out."
    ),
)
async def list_fee_reminders(
    student_id: Optional[int] = Query(None, description="Filter by student"),
    voucher_id: Optional[int] = Query(None, description="Filter by voucher"),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_BURSAR)),
) -> List[FeeReminderLogRead]:
    conditions = []
    if isinstance(student_id, int):
        conditions.append(FeeReminderLog.student_id == student_id)
    if isinstance(voucher_id, int):
        conditions.append(FeeReminderLog.voucher_id == voucher_id)
    stmt = select(FeeReminderLog).order_by(FeeReminderLog.sent_on.desc())
    if conditions:
        stmt = stmt.where(and_(*conditions))
    rows = (await session.execute(stmt)).scalars().all()
    return [FeeReminderLogRead.model_validate(r) for r in rows]
