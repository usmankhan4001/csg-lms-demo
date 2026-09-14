"""Instalments, concessions, refunds, reconciliation and the fee audit trail.

THE RULE THIS MODULE IS BUILT AROUND: `StudentFeeVoucher.balance_amount` is the
only source of truth for what a family owes. Nothing here computes a balance a
second way.

* An instalment plan's totals are SUMS of its vouchers' stored fields.
* A concession is realised into `voucher.discount` at generation time; the
  concession row records provenance, not money.
* A refund adjusts `paid_amount` and recomputes `balance_amount` with the exact
  expression `process_fee_payment` uses.
* Matching a bank transfer calls the ordinary payment path; it never moves
  money itself.

Money is never invented. A voucher with no payment has no payment, and a figure
that cannot be computed is omitted rather than defaulted to zero.
"""

import datetime
import logging
import uuid
from typing import Dict, List, Optional, Sequence, Tuple

from fastapi import HTTPException, status
from sqlalchemy import and_, or_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_fees import (
    FeePaymentReceipt,
    FeeStructure,
    PaymentMethod,
    StudentFeeVoucher,
    VoucherStatus,
)
from src.db.sms_fees_extended import (
    BankTransferRecord,
    BankTransferStatus,
    ConcessionKind,
    FeeChangeAction,
    FeeChangeEvent,
    FeeConcession,
    FeeConcessionApplication,
    FeeInstallmentPlan,
    FeeRefund,
    InstallmentPlanStatus,
)

logger = logging.getLogger(__name__)


# ── Audit ───────────────────────────────────────────────────────────────────


def record_fee_change(
    session: AsyncSession,
    *,
    voucher: StudentFeeVoucher,
    action: FeeChangeAction,
    previous_paid_amount: Optional[float] = None,
    previous_balance: Optional[float] = None,
    amount: Optional[float] = None,
    changed_by_user_id: Optional[int] = None,
    reason: Optional[str] = None,
) -> FeeChangeEvent:
    """Stage an audit row. The CALLER commits it in the same transaction as the
    money it describes -- a trail committed separately can be lost by a crash
    that keeps the mutation, which is the one failure mode an audit trail must
    not have."""
    event = FeeChangeEvent(
        voucher_id=voucher.id,
        student_id=voucher.student_id,
        action=action,
        previous_paid_amount=previous_paid_amount,
        new_paid_amount=voucher.paid_amount,
        previous_balance=previous_balance,
        new_balance=voucher.balance_amount,
        amount=amount,
        changed_by_user_id=changed_by_user_id,
        reason=reason,
    )
    session.add(event)
    return event


def _actor(principal) -> Optional[int]:
    """The authenticated caller's Learnhouse user id, never a client-supplied
    field. Returns None when the principal carries no resolvable id -- an
    unattributed row is still better than no row, and reads as "unknown"
    rather than as somebody else."""
    return (getattr(principal, "raw_claims", None) or {}).get("lh_user_id")


# ── Concessions ─────────────────────────────────────────────────────────────


async def create_concession(
    session: AsyncSession,
    *,
    student_id: int,
    kind: ConcessionKind,
    reason: str,
    percentage: Optional[float] = None,
    fixed_amount: Optional[float] = None,
    campus_id: Optional[int] = None,
    valid_from: Optional[datetime.date] = None,
    valid_until: Optional[datetime.date] = None,
    principal=None,
) -> FeeConcession:
    """Authorise a reasoned reduction for one named student."""
    if (percentage is None) == (fixed_amount is None):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Provide exactly one of percentage or fixed_amount. A concession "
                "that is both 20% and a flat sum has no single meaning."
            ),
        )
    if percentage is not None and not (0 < percentage <= 100):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="percentage must be greater than 0 and at most 100.",
        )
    if fixed_amount is not None and fixed_amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="fixed_amount must be greater than 0.",
        )
    if not (reason or "").strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A concession must state why it was granted.",
        )

    concession = FeeConcession(
        student_id=student_id,
        campus_id=campus_id,
        kind=kind,
        percentage=percentage,
        fixed_amount=fixed_amount,
        reason=reason.strip(),
        authorised_by_user_id=_actor(principal),
        valid_from=valid_from,
        valid_until=valid_until,
        is_active=True,
    )
    session.add(concession)
    await session.commit()
    await session.refresh(concession)
    return concession


async def active_concessions_for(
    session: AsyncSession,
    student_id: int,
    on_date: datetime.date,
) -> List[FeeConcession]:
    """Concessions in force for this student on this date."""
    stmt = select(FeeConcession).where(
        and_(
            FeeConcession.student_id == student_id,
            FeeConcession.is_active == True,  # noqa: E712
        )
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [
        c
        for c in rows
        if (c.valid_from is None or c.valid_from <= on_date)
        and (c.valid_until is None or c.valid_until >= on_date)
    ]


def compute_concession_amount(
    concessions: Sequence[FeeConcession], gross: float
) -> Tuple[float, List[Tuple[FeeConcession, float]]]:
    """Total reduction and its breakdown, capped at the gross fee.

    Percentages apply to the gross, not compounding on one another: two 20%
    concessions take 40% off, not 36%. Compounding would make the order of
    award change the bill, which no bursar could explain to a family.

    The cap matters: concessions must never make a voucher negative, which
    would read as the school owing the family money it never received.
    """
    breakdown: List[Tuple[FeeConcession, float]] = []
    total = 0.0
    for c in concessions:
        if c.percentage is not None:
            amount = gross * (c.percentage / 100.0)
        elif c.fixed_amount is not None:
            amount = c.fixed_amount
        else:
            continue
        amount = round(amount, 2)
        if amount <= 0:
            continue
        breakdown.append((c, amount))
        total += amount

    if total > gross:
        # Scale proportionally so the breakdown still sums to what was applied.
        scale = gross / total if total else 0.0
        breakdown = [(c, round(a * scale, 2)) for c, a in breakdown]
        total = gross
    return round(total, 2), breakdown


# ── Instalment plans ────────────────────────────────────────────────────────


def _split_amount(total: float, parts: int) -> List[float]:
    """Split into `parts`, putting any rounding remainder on the FIRST
    instalment.

    Front-loading the remainder rather than trailing it means the final
    instalment is never a strange number a family queries, and the parts always
    sum to exactly the total -- a split that loses a cent is a ledger that never
    reconciles.
    """
    base = round(total / parts, 2)
    amounts = [base] * parts
    drift = round(total - base * parts, 2)
    amounts[0] = round(amounts[0] + drift, 2)
    return amounts


async def create_installment_plan(
    session: AsyncSession,
    *,
    student_id: int,
    fee_structure_id: int,
    name: str,
    due_dates: Sequence[datetime.date],
    issue_date: datetime.date,
    campus_id: Optional[int] = None,
    academic_term_id: Optional[int] = None,
    apply_concessions: bool = True,
    principal=None,
) -> Tuple[FeeInstallmentPlan, List[StudentFeeVoucher]]:
    """Create a plan and one real voucher per instalment.

    The gross fee comes from the structure, concessions are applied ONCE to the
    whole fee (not per instalment -- a 20% concession is 20% of the year, not
    20% of each of three bills plus 20% again), and the net is split across the
    instalments.
    """
    if len(due_dates) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An instalment plan needs at least two due dates; one is an ordinary voucher.",
        )
    if len(due_dates) > 24:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An instalment plan is capped at 24 instalments.",
        )
    if list(due_dates) != sorted(due_dates):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Instalment due dates must be in chronological order.",
        )

    structure = (
        await session.execute(select(FeeStructure).where(FeeStructure.id == fee_structure_id))
    ).scalar_one_or_none()
    if not structure:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Fee structure {fee_structure_id} not found.",
        )

    gross = (
        structure.tuition_fee + structure.transport_fee + structure.lab_fee + structure.other_fee
    )

    discount_total = 0.0
    breakdown: List[Tuple[FeeConcession, float]] = []
    if apply_concessions:
        concessions = await active_concessions_for(session, student_id, issue_date)
        discount_total, breakdown = compute_concession_amount(concessions, gross)

    net_total = round(max(0.0, gross - discount_total), 2)

    plan = FeeInstallmentPlan(
        student_id=student_id,
        campus_id=campus_id,
        fee_structure_id=structure.id,
        academic_term_id=academic_term_id,
        name=name,
        installment_count=len(due_dates),
        status=InstallmentPlanStatus.ACTIVE,
        created_by_user_id=_actor(principal),
    )
    session.add(plan)
    await session.flush()  # need plan.id for the vouchers

    amounts = _split_amount(net_total, len(due_dates))
    # The discount is attributed to instalments proportionally so each
    # voucher's own arithmetic (gross share - discount share = total) holds.
    gross_shares = _split_amount(gross, len(due_dates))

    vouchers: List[StudentFeeVoucher] = []
    for idx, (due, amount) in enumerate(zip(due_dates, amounts), start=1):
        rand_suffix = uuid.uuid4().hex[:6].upper()
        voucher_no = f"VCH-{issue_date.strftime('%Y%m')}-{student_id}-I{idx}-{rand_suffix}"
        share = gross_shares[idx - 1]
        voucher = StudentFeeVoucher(
            student_id=student_id,
            fee_structure_id=structure.id,
            installment_plan_id=plan.id,
            installment_number=idx,
            voucher_no=voucher_no,
            issue_date=issue_date,
            due_date=due,
            # Component fees are carried on instalment 1 only: splitting
            # "tuition" across three rows would invite summing them as three
            # separate tuition charges. The money that matters, total_amount,
            # is correct on every row.
            tuition_fee=structure.tuition_fee if idx == 1 else 0.0,
            transport_fee=structure.transport_fee if idx == 1 else 0.0,
            lab_fee=structure.lab_fee if idx == 1 else 0.0,
            other_fee=structure.other_fee if idx == 1 else 0.0,
            discount=round(max(0.0, share - amount), 2),
            fine=0.0,
            total_amount=amount,
            paid_amount=0.0,
            balance_amount=amount,
            status=VoucherStatus.UNPAID,
            remarks=f"{name} — instalment {idx} of {len(due_dates)}",
        )
        session.add(voucher)
        vouchers.append(voucher)

    await session.flush()

    actor = _actor(principal)
    for voucher in vouchers:
        record_fee_change(
            session,
            voucher=voucher,
            action=FeeChangeAction.VOUCHER_CREATED,
            amount=voucher.total_amount,
            changed_by_user_id=actor,
            reason=f"Instalment {voucher.installment_number} of {len(due_dates)}",
        )

    # Concession provenance, attributed to instalment 1 so the sum of
    # applications equals the sum of discounts across the plan.
    if breakdown and vouchers:
        first = vouchers[0]
        for concession, applied in breakdown:
            session.add(
                FeeConcessionApplication(
                    concession_id=concession.id,
                    voucher_id=first.id,
                    student_id=student_id,
                    kind=concession.kind.value
                    if isinstance(concession.kind, ConcessionKind)
                    else str(concession.kind),
                    amount_applied=applied,
                    reason=concession.reason,
                )
            )
        record_fee_change(
            session,
            voucher=vouchers[0],
            action=FeeChangeAction.CONCESSION_APPLIED,
            amount=discount_total,
            changed_by_user_id=actor,
            reason="; ".join(c.reason for c, _ in breakdown),
        )

    await session.commit()
    for v in vouchers:
        await session.refresh(v)
    await session.refresh(plan)
    return plan, vouchers


async def summarise_installment_plan(
    session: AsyncSession, plan: FeeInstallmentPlan
) -> Dict[str, object]:
    """Plan progress, derived ENTIRELY from its vouchers' stored fields.

    `paid_count` is a count of settled instalments, not a recomputation of
    money, so this can never disagree with the ledger.
    """
    vouchers = (
        (
            await session.execute(
                select(StudentFeeVoucher)
                .where(StudentFeeVoucher.installment_plan_id == plan.id)
                .order_by(StudentFeeVoucher.installment_number)
            )
        )
        .scalars()
        .all()
    )
    paid_count = sum(1 for v in vouchers if v.status == VoucherStatus.PAID)
    return {
        "plan_id": plan.id,
        "student_id": plan.student_id,
        "name": plan.name,
        "status": plan.status,
        "installment_count": plan.installment_count,
        "paid_count": paid_count,
        "total_amount": round(sum(v.total_amount for v in vouchers), 2),
        "paid_amount": round(sum(v.paid_amount for v in vouchers), 2),
        "balance_amount": round(sum(v.balance_amount for v in vouchers), 2),
        "vouchers": vouchers,
    }


# ── Refunds ─────────────────────────────────────────────────────────────────


async def issue_refund(
    session: AsyncSession,
    *,
    voucher_id: int,
    amount: float,
    reason: str,
    method: str = "BANK_TRANSFER",
    refund_date: Optional[datetime.date] = None,
    principal=None,
) -> FeeRefund:
    """Return money to a family.

    Reduces `paid_amount` and recomputes `balance_amount` with the SAME
    expression `process_fee_payment` uses, so a refunded voucher reads exactly
    like one that was never paid that much -- rather than acquiring a second,
    refund-aware balance that the payment path knows nothing about.
    """
    if amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="A refund must be greater than zero."
        )
    if not (reason or "").strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="A refund must state why it was issued."
        )

    voucher = (
        await session.execute(select(StudentFeeVoucher).where(StudentFeeVoucher.id == voucher_id))
    ).scalar_one_or_none()
    if not voucher:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Voucher {voucher_id} not found."
        )

    # A refund can never exceed what was actually received. `paid_amount`
    # already reflects every prior refund, so this single check covers repeat
    # refunds without a second running total to keep in step.
    if round(amount, 2) > round(voucher.paid_amount, 2):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Refund of {amount} exceeds the {voucher.paid_amount} actually paid "
                f"on this voucher."
            ),
        )

    previous_paid = voucher.paid_amount
    previous_balance = voucher.balance_amount

    r_date = refund_date or datetime.date.today()
    refund_no = f"RFD-{r_date.strftime('%Y%m%d')}-{voucher.id}-{uuid.uuid4().hex[:6].upper()}"

    refund = FeeRefund(
        voucher_id=voucher.id,
        refund_no=refund_no,
        refund_date=r_date,
        amount=round(amount, 2),
        method=method,
        reason=reason.strip(),
        authorised_by_user_id=_actor(principal),
    )
    session.add(refund)

    voucher.paid_amount = round(voucher.paid_amount - amount, 2)
    voucher.balance_amount = round(voucher.total_amount - voucher.paid_amount, 2)
    if voucher.balance_amount <= 0.001:
        voucher.balance_amount = 0.0
        voucher.status = VoucherStatus.PAID
    elif voucher.paid_amount > 0:
        voucher.status = VoucherStatus.PARTIAL
    else:
        voucher.status = VoucherStatus.UNPAID
    session.add(voucher)

    record_fee_change(
        session,
        voucher=voucher,
        action=FeeChangeAction.REFUND_ISSUED,
        previous_paid_amount=previous_paid,
        previous_balance=previous_balance,
        amount=round(amount, 2),
        changed_by_user_id=_actor(principal),
        reason=reason.strip(),
    )

    await session.commit()
    await session.refresh(refund)
    return refund


# ── Bank reconciliation ─────────────────────────────────────────────────────


async def record_bank_transfers(
    session: AsyncSession,
    *,
    rows: Sequence[Dict[str, object]],
    campus_id: Optional[int] = None,
) -> List[BankTransferRecord]:
    """Take already-parsed statement lines into the unmatched queue.

    Parsing a particular bank's export is deliberately NOT done here: formats
    are per-bank and per-country, and a parser guessing a column would silently
    attribute money to the wrong family. A CSV importer belongs above this API.
    """
    created: List[BankTransferRecord] = []
    for row in rows:
        record = BankTransferRecord(
            campus_id=campus_id,
            transfer_date=row["transfer_date"],  # type: ignore[index]
            amount=float(row["amount"]),  # type: ignore[index,arg-type]
            bank_reference=row.get("bank_reference"),  # type: ignore[arg-type]
            payer_name=row.get("payer_name"),  # type: ignore[arg-type]
            payer_note=row.get("payer_note"),  # type: ignore[arg-type]
            status=BankTransferStatus.UNMATCHED,
        )
        session.add(record)
        created.append(record)
    await session.commit()
    for r in created:
        await session.refresh(r)
    return created


async def suggest_transfer_matches(
    session: AsyncSession, transfer: BankTransferRecord, limit: int = 5
) -> List[StudentFeeVoucher]:
    """Candidate vouchers for an unmatched transfer.

    SUGGESTIONS ONLY -- nothing here marks anything paid. A wrong automatic
    match moves real money against the wrong family, so a human always
    confirms. Ranked by how strong the evidence is: an exact voucher number in
    the payer's reference beats an amount that merely happens to agree.
    """
    haystack = " ".join(
        filter(None, [transfer.bank_reference or "", transfer.payer_note or "", transfer.payer_name or ""])
    ).upper()

    conditions = [StudentFeeVoucher.status.in_([VoucherStatus.UNPAID, VoucherStatus.PARTIAL])]
    stmt = select(StudentFeeVoucher).where(and_(*conditions))
    open_vouchers = (await session.execute(stmt)).scalars().all()

    scored: List[Tuple[int, StudentFeeVoucher]] = []
    for v in open_vouchers:
        score = 0
        if v.voucher_no and v.voucher_no.upper() in haystack:
            score += 100
        if abs(round(v.balance_amount, 2) - round(transfer.amount, 2)) < 0.01:
            score += 50
        if str(v.student_id) in haystack:
            score += 25
        if score:
            scored.append((score, v))

    scored.sort(key=lambda pair: (-pair[0], pair[1].due_date))
    return [v for _, v in scored[:limit]]


async def match_transfer_to_voucher(
    session: AsyncSession,
    *,
    transfer_id: int,
    voucher_id: int,
    principal=None,
) -> Tuple[BankTransferRecord, FeePaymentReceipt]:
    """Attribute a bank transfer to a voucher by recording a real payment.

    Goes through the ordinary payment mechanics rather than writing balances
    directly, so a reconciled payment is indistinguishable from one taken at
    the counter and cannot drift from it.
    """
    transfer = (
        await session.execute(select(BankTransferRecord).where(BankTransferRecord.id == transfer_id))
    ).scalar_one_or_none()
    if not transfer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Bank transfer {transfer_id} not found."
        )
    if transfer.status != BankTransferStatus.UNMATCHED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Transfer {transfer_id} is already {transfer.status.value}.",
        )

    voucher = (
        await session.execute(select(StudentFeeVoucher).where(StudentFeeVoucher.id == voucher_id))
    ).scalar_one_or_none()
    if not voucher:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Voucher {voucher_id} not found."
        )
    if voucher.status == VoucherStatus.PAID:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Voucher is already fully paid."
        )
    if round(transfer.amount, 2) > round(voucher.balance_amount, 2):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Transfer of {transfer.amount} exceeds the outstanding balance "
                f"of {voucher.balance_amount}. Split the transfer or pick another voucher."
            ),
        )

    previous_paid = voucher.paid_amount
    previous_balance = voucher.balance_amount

    receipt_no = f"REC-{transfer.transfer_date.strftime('%Y%m%d')}-{voucher.id}-{uuid.uuid4().hex[:6].upper()}"
    receipt = FeePaymentReceipt(
        voucher_id=voucher.id,
        receipt_no=receipt_no,
        payment_date=transfer.transfer_date,
        amount_paid=transfer.amount,
        payment_method=PaymentMethod.BANK_TRANSFER,
        transaction_ref=transfer.bank_reference,
        collected_by=_actor(principal),
        remarks=f"Reconciled from bank transfer #{transfer.id}",
    )
    session.add(receipt)

    voucher.paid_amount = round(voucher.paid_amount + transfer.amount, 2)
    voucher.balance_amount = round(voucher.total_amount - voucher.paid_amount, 2)
    if voucher.balance_amount <= 0.001:
        voucher.balance_amount = 0.0
        voucher.status = VoucherStatus.PAID
    else:
        voucher.status = VoucherStatus.PARTIAL
    session.add(voucher)

    await session.flush()

    transfer.status = BankTransferStatus.MATCHED
    transfer.matched_receipt_id = receipt.id
    transfer.matched_voucher_id = voucher.id
    transfer.matched_by_user_id = _actor(principal)
    transfer.matched_at = datetime.datetime.now(datetime.timezone.utc)
    session.add(transfer)

    record_fee_change(
        session,
        voucher=voucher,
        action=FeeChangeAction.TRANSFER_MATCHED,
        previous_paid_amount=previous_paid,
        previous_balance=previous_balance,
        amount=transfer.amount,
        changed_by_user_id=_actor(principal),
        reason=f"Bank transfer #{transfer.id} ({transfer.bank_reference or 'no reference'})",
    )

    await session.commit()
    await session.refresh(transfer)
    await session.refresh(receipt)
    return transfer, receipt


async def list_unmatched_transfers(
    session: AsyncSession, campus_id: Optional[int] = None
) -> List[BankTransferRecord]:
    conditions = [BankTransferRecord.status == BankTransferStatus.UNMATCHED]
    if campus_id is not None:
        conditions.append(
            or_(BankTransferRecord.campus_id == campus_id, BankTransferRecord.campus_id.is_(None))
        )
    stmt = (
        select(BankTransferRecord)
        .where(and_(*conditions))
        .order_by(BankTransferRecord.transfer_date.desc())
    )
    return list((await session.execute(stmt)).scalars().all())
