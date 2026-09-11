import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field
from src.db.sms_payroll import SalaryPaymentStatus


class SalaryStructureBase(BaseModel):
    staff_id: int
    basic: float = Field(default=0.0, ge=0.0)
    housing_allowance: float = Field(default=0.0, ge=0.0)
    medical_allowance: float = Field(default=0.0, ge=0.0)
    other_allowances: float = Field(default=0.0, ge=0.0)
    tax_deduction: float = Field(default=0.0, ge=0.0)
    provident_fund: float = Field(default=0.0, ge=0.0)
    other_deductions: float = Field(default=0.0, ge=0.0)


class SalaryStructureCreate(SalaryStructureBase):
    pass


class SalaryStructureRead(SalaryStructureBase):
    id: int
    gross_salary: float
    total_deductions: float
    net_salary: float
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class BatchSalarySlipGenerateRequest(BaseModel):
    month: int = Field(..., ge=1, le=12)
    year: int = Field(..., ge=2000, le=2100)
    campus_id: Optional[int] = None
    staff_ids: Optional[List[int]] = None
    remarks: Optional[str] = None


class SalarySlipRead(BaseModel):
    id: int
    slip_no: str
    staff_id: int
    month: int
    year: int
    basic: float
    housing_allowance: float
    medical_allowance: float
    other_allowances: float
    tax_deduction: float
    provident_fund: float
    other_deductions: float
    gross_salary: float
    total_deductions: float
    net_salary: float
    payment_status: SalaryPaymentStatus
    payment_date: Optional[datetime.date] = None
    payment_method: Optional[str] = None
    remarks: Optional[str] = None
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class ProcessSalaryPaymentRequest(BaseModel):
    payment_date: datetime.date
    payment_method: str = "BANK_TRANSFER"
    remarks: Optional[str] = None
