import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field
from src.db.sms_hr import ContractType, LeaveStatus, LeaveType


class StaffProfileBase(BaseModel):
    employee_code: str = Field(..., max_length=50)
    full_name: str = Field(..., max_length=150)
    designation: str = Field(..., max_length=100)
    department: str = Field(..., max_length=100)
    joining_date: datetime.date
    contract_type: ContractType = ContractType.PERMANENT
    basic_salary: float = Field(default=0.0, ge=0.0)
    user_id: Optional[int] = None
    campus_id: Optional[int] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    is_active: bool = True


class StaffProfileCreate(StaffProfileBase):
    pass


class StaffProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    designation: Optional[str] = None
    department: Optional[str] = None
    joining_date: Optional[datetime.date] = None
    contract_type: Optional[ContractType] = None
    basic_salary: Optional[float] = Field(None, ge=0.0)
    user_id: Optional[int] = None
    campus_id: Optional[int] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    is_active: Optional[bool] = None


class StaffProfileRead(StaffProfileBase):
    id: int
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class StaffLeaveCreate(BaseModel):
    staff_id: int
    leave_type: LeaveType
    start_date: datetime.date
    end_date: datetime.date
    reason: Optional[str] = None


class StaffLeaveActionRequest(BaseModel):
    status: LeaveStatus
    approved_by: Optional[int] = None


class StaffLeaveRead(BaseModel):
    id: int
    staff_id: int
    leave_type: LeaveType
    start_date: datetime.date
    end_date: datetime.date
    reason: Optional[str] = None
    status: LeaveStatus
    approved_by: Optional[int] = None
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)
