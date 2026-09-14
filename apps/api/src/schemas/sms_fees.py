import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field
from src.db.sms_fees import PaymentMethod, VoucherStatus


class FeeStructureBase(BaseModel):
    name: str
    campus_id: Optional[int] = None
    section_id: Optional[int] = None
    academic_term_id: Optional[int] = None
    tuition_fee: float = Field(default=0.0, ge=0.0)
    transport_fee: float = Field(default=0.0, ge=0.0)
    lab_fee: float = Field(default=0.0, ge=0.0)
    other_fee: float = Field(default=0.0, ge=0.0)


class FeeStructureCreate(FeeStructureBase):
    pass


class FeeStructureRead(FeeStructureBase):
    id: int
    total_amount: float

    model_config = ConfigDict(from_attributes=True)


class GenerateVouchersRequest(BaseModel):
    fee_structure_id: int
    student_ids: List[int]
    issue_date: datetime.date
    due_date: datetime.date
    discount_per_student: Optional[float] = 0.0
    fine_per_student: Optional[float] = 0.0
    remarks: Optional[str] = None


class StudentFeeVoucherRead(BaseModel):
    id: int
    student_id: int
    fee_structure_id: Optional[int] = None
    voucher_no: str
    issue_date: datetime.date
    due_date: datetime.date
    tuition_fee: float
    transport_fee: float
    lab_fee: float
    other_fee: float
    discount: float
    fine: float
    # Surfaced so a parent can see how much of `fine` is an automatic late
    # charge versus a fine the school set by hand — an unexplained increase in
    # what is owed is exactly the kind of thing that generates a support call.
    late_fee_applied: float = 0.0
    late_fee_last_accrued_on: Optional[datetime.date] = None
    total_amount: float
    paid_amount: float
    balance_amount: float
    status: VoucherStatus
    remarks: Optional[str] = None
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class RecordPaymentRequest(BaseModel):
    voucher_id: int
    amount_paid: float = Field(..., gt=0.0)
    payment_method: PaymentMethod = PaymentMethod.CASH
    payment_date: Optional[datetime.date] = None
    transaction_ref: Optional[str] = None
    collected_by: Optional[int] = None
    remarks: Optional[str] = None


class FeePaymentReceiptRead(BaseModel):
    id: int
    voucher_id: int
    receipt_no: str
    payment_date: datetime.date
    amount_paid: float
    payment_method: PaymentMethod
    transaction_ref: Optional[str] = None
    collected_by: Optional[int] = None
    remarks: Optional[str] = None
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class StudentFeeLedgerResponse(BaseModel):
    student_id: int
    total_invoiced: float
    total_paid: float
    total_outstanding: float
    vouchers: List[StudentFeeVoucherRead]
    receipts: List[FeePaymentReceiptRead]
