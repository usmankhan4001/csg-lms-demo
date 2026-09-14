import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from src.db.sms_fees_extended import (
    BankTransferStatus,
    ConcessionKind,
    FeeChangeAction,
    FeeReminderKind,
    InstallmentPlanStatus,
)
from src.schemas.sms_fees import StudentFeeVoucherRead


# ── Instalments ─────────────────────────────────────────────────────────────


class CreateInstallmentPlanRequest(BaseModel):
    student_id: int
    fee_structure_id: int
    name: str
    issue_date: datetime.date
    # One due date per instalment. At least two, because a single "instalment"
    # is just an ordinary voucher.
    due_dates: List[datetime.date] = Field(..., min_length=2, max_length=24)
    campus_id: Optional[int] = None
    academic_term_id: Optional[int] = None
    apply_concessions: bool = True


class InstallmentPlanSummary(BaseModel):
    """Progress on a plan.

    Every figure here is a SUM or COUNT over the plan's vouchers' stored
    fields, never a recomputation -- so this can never disagree with the
    ledger.
    """

    plan_id: int
    student_id: int
    name: str
    status: InstallmentPlanStatus
    installment_count: int
    paid_count: int
    total_amount: float
    paid_amount: float
    balance_amount: float
    vouchers: List[StudentFeeVoucherRead]


# ── Concessions ─────────────────────────────────────────────────────────────


class CreateConcessionRequest(BaseModel):
    student_id: int
    kind: ConcessionKind
    # Exactly one of these. Enforced in the service, which returns a 400
    # explaining why rather than silently preferring one.
    percentage: Optional[float] = Field(default=None, gt=0, le=100)
    fixed_amount: Optional[float] = Field(default=None, gt=0)
    # Required: a concession with no stated reason is what this model exists to
    # prevent.
    reason: str = Field(..., min_length=1)
    campus_id: Optional[int] = None
    valid_from: Optional[datetime.date] = None
    valid_until: Optional[datetime.date] = None


class ConcessionRead(BaseModel):
    id: int
    student_id: int
    campus_id: Optional[int] = None
    kind: ConcessionKind
    percentage: Optional[float] = None
    fixed_amount: Optional[float] = None
    reason: str
    authorised_by_user_id: Optional[int] = None
    valid_from: Optional[datetime.date] = None
    valid_until: Optional[datetime.date] = None
    is_active: bool
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


# ── Refunds ─────────────────────────────────────────────────────────────────


class IssueRefundRequest(BaseModel):
    voucher_id: int
    amount: float = Field(..., gt=0)
    reason: str = Field(..., min_length=1)
    method: str = "BANK_TRANSFER"
    refund_date: Optional[datetime.date] = None


class RefundRead(BaseModel):
    id: int
    voucher_id: int
    refund_no: str
    refund_date: datetime.date
    amount: float
    method: str
    reason: str
    authorised_by_user_id: Optional[int] = None
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


# ── Bank reconciliation ─────────────────────────────────────────────────────


class BankTransferLine(BaseModel):
    transfer_date: datetime.date
    amount: float = Field(..., gt=0)
    bank_reference: Optional[str] = None
    payer_name: Optional[str] = None
    payer_note: Optional[str] = None


class ImportBankTransfersRequest(BaseModel):
    rows: List[BankTransferLine] = Field(..., min_length=1, max_length=500)
    campus_id: Optional[int] = None


class BankTransferRead(BaseModel):
    id: int
    campus_id: Optional[int] = None
    transfer_date: datetime.date
    amount: float
    bank_reference: Optional[str] = None
    payer_name: Optional[str] = None
    payer_note: Optional[str] = None
    status: BankTransferStatus
    matched_receipt_id: Optional[int] = None
    matched_voucher_id: Optional[int] = None
    matched_by_user_id: Optional[int] = None
    matched_at: Optional[datetime.datetime] = None
    ignored_reason: Optional[str] = None
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class TransferMatchSuggestion(BaseModel):
    """A candidate, with the evidence spelled out.

    `confidence` is deliberately a label rather than a percentage: a fabricated
    "87% match" on somebody's fee payment would invite a clerk to trust a
    number the system cannot actually justify.
    """

    voucher: StudentFeeVoucherRead
    matched_on: List[str]


class MatchTransferRequest(BaseModel):
    transfer_id: int
    voucher_id: int


# ── Audit ───────────────────────────────────────────────────────────────────


class FeeChangeEventRead(BaseModel):
    id: int
    voucher_id: int
    student_id: int
    action: FeeChangeAction
    previous_paid_amount: Optional[float] = None
    new_paid_amount: Optional[float] = None
    previous_balance: Optional[float] = None
    new_balance: Optional[float] = None
    amount: Optional[float] = None
    changed_by_user_id: Optional[int] = None
    reason: Optional[str] = None
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class FeeReminderLogRead(BaseModel):
    id: int
    voucher_id: int
    student_id: int
    kind: FeeReminderKind
    sent_on: datetime.date
    recipients: int
    # What the provider actually accepted. Differs from `recipients` whenever
    # mail is unconfigured, and that difference is the point.
    delivered: int
    balance_at_send: float
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)
