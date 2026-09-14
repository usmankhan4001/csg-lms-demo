import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field
from src.db.sms_financials import AccountType


class ChartOfAccountsBase(BaseModel):
    account_code: str = Field(..., max_length=50)
    account_name: str = Field(..., max_length=150)
    account_type: AccountType
    campus_id: Optional[int] = None
    is_active: bool = True
    description: Optional[str] = None


class ChartOfAccountsCreate(ChartOfAccountsBase):
    initial_balance: Optional[float] = Field(default=0.0)


class ChartOfAccountsRead(ChartOfAccountsBase):
    id: int
    balance: float
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class JournalEntryLineCreate(BaseModel):
    account_id: int
    debit_amount: float = Field(default=0.0, ge=0.0)
    credit_amount: float = Field(default=0.0, ge=0.0)
    description: Optional[str] = None


class JournalEntryLineRead(BaseModel):
    id: int
    entry_id: int
    account_id: int
    debit_amount: float
    credit_amount: float
    description: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class JournalEntryCreate(BaseModel):
    campus_id: Optional[int] = None
    entry_date: datetime.date
    reference_no: Optional[str] = None
    description: Optional[str] = None
    lines: List[JournalEntryLineCreate] = Field(..., min_length=2)


class JournalEntryRead(BaseModel):
    id: int
    campus_id: Optional[int] = None
    entry_date: datetime.date
    reference_no: str
    description: Optional[str] = None
    # Non-null on a reversal entry, naming the entry it negates. Exposed so a
    # ledger reader can tell a correction apart from a genuine transaction.
    reverses_entry_id: Optional[int] = None
    total_debit: float
    total_credit: float
    created_at: datetime.datetime
    lines: List[JournalEntryLineRead] = []

    model_config = ConfigDict(from_attributes=True)


class TrialBalanceItemRead(BaseModel):
    account_id: int
    account_code: str
    account_name: str
    account_type: AccountType
    debit_balance: float
    credit_balance: float


class TrialBalanceResponse(BaseModel):
    campus_id: Optional[int] = None
    items: List[TrialBalanceItemRead]
    total_debit: float
    total_credit: float
    is_balanced: bool
