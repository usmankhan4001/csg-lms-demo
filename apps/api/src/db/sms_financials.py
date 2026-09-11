import datetime
from enum import Enum
from typing import Optional
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlmodel import Field, SQLModel


class AccountType(str, Enum):
    """Core financial chart of accounts classification."""
    ASSET = "ASSET"
    LIABILITY = "LIABILITY"
    EQUITY = "EQUITY"
    REVENUE = "REVENUE"
    EXPENSE = "EXPENSE"


class ChartOfAccounts(SQLModel, table=True):
    """
    General Ledger Chart of Accounts ledger entity.
    """
    __tablename__ = "sms_chart_of_accounts"
    __table_args__ = (
        Index("ix_sms_coa_campus_code", "campus_id", "account_code"),
        Index("ix_sms_coa_type", "account_type"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    campus_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True, index=True))
    account_code: str = Field(sa_column=Column(String(50), nullable=False, index=True))
    account_name: str = Field(sa_column=Column(String(150), nullable=False))
    account_type: AccountType = Field(
        sa_column=Column(
            SAEnum(AccountType, name="sms_account_type", native_enum=False),
            nullable=False,
            index=True,
        )
    )
    balance: float = Field(default=0.0, sa_column=Column(Float, nullable=False, default=0.0))
    is_active: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, default=True))
    description: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.datetime.now(datetime.timezone.utc),
        ),
    )


class JournalEntry(SQLModel, table=True):
    """
    Financial General Ledger Journal Entry header.
    """
    __tablename__ = "sms_journal_entry"
    __table_args__ = (
        UniqueConstraint("reference_no", name="uq_sms_journal_reference_no"),
        Index("ix_sms_journal_date", "entry_date"),
        Index("ix_sms_journal_campus", "campus_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    campus_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True, index=True))
    entry_date: datetime.date = Field(sa_column=Column(Date, nullable=False, index=True))
    reference_no: str = Field(sa_column=Column(String(50), nullable=False, unique=True, index=True))
    description: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    total_debit: float = Field(default=0.0, sa_column=Column(Float, nullable=False, default=0.0))
    total_credit: float = Field(default=0.0, sa_column=Column(Float, nullable=False, default=0.0))
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.datetime.now(datetime.timezone.utc),
        ),
    )


class JournalEntryLine(SQLModel, table=True):
    """
    Individual debit/credit split line items for a journal entry.
    """
    __tablename__ = "sms_journal_entry_line"
    __table_args__ = (
        Index("ix_sms_jel_entry_id", "entry_id"),
        Index("ix_sms_jel_account_id", "account_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    entry_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("sms_journal_entry.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    account_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("sms_chart_of_accounts.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    debit_amount: float = Field(default=0.0, sa_column=Column(Float, nullable=False, default=0.0))
    credit_amount: float = Field(default=0.0, sa_column=Column(Float, nullable=False, default=0.0))
    description: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
