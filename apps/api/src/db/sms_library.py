import datetime
from enum import Enum
from typing import Optional
from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlmodel import Field, SQLModel


class BookLoanStatus(str, Enum):
    """Status enumeration for library book loans."""
    BORROWED = "BORROWED"
    RETURNED = "RETURNED"
    OVERDUE = "OVERDUE"


class LibraryBook(SQLModel, table=True):
    """
    Catalog record of physical or digital library books.
    """
    __tablename__ = "sms_library_book"
    __table_args__ = (
        Index("ix_sms_lib_campus", "campus_id"),
        Index("ix_sms_lib_category", "category"),
        Index("ix_sms_lib_isbn", "isbn"),
        Index("ix_sms_lib_title", "title"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    campus_id: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, nullable=True, index=True)
    )
    isbn: Optional[str] = Field(
        default=None,
        sa_column=Column(String(50), nullable=True, index=True)
    )
    title: str = Field(
        sa_column=Column(String(255), nullable=False, index=True)
    )
    author: str = Field(
        sa_column=Column(String(255), nullable=False, index=True)
    )
    category: Optional[str] = Field(
        default=None,
        sa_column=Column(String(100), nullable=True, index=True)
    )
    total_copies: int = Field(
        default=1,
        sa_column=Column(Integer, nullable=False, default=1)
    )
    available_copies: int = Field(
        default=1,
        sa_column=Column(Integer, nullable=False, default=1)
    )
    digital_file_url: Optional[str] = Field(
        default=None,
        sa_column=Column(String(500), nullable=True)
    )
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.datetime.now(datetime.timezone.utc),
        ),
    )


class BookLoan(SQLModel, table=True):
    """
    Circulation tracking record for borrowed books and overdue fines.
    """
    __tablename__ = "sms_library_book_loan"
    __table_args__ = (
        Index("ix_sms_loan_book", "book_id"),
        Index("ix_sms_loan_user", "user_id"),
        Index("ix_sms_loan_status", "status"),
        Index("ix_sms_loan_due_date", "due_date"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    book_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("sms_library_book.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    user_id: int = Field(
        sa_column=Column(Integer, nullable=False, index=True)
    )
    borrowed_date: datetime.date = Field(
        sa_column=Column(Date, nullable=False)
    )
    due_date: datetime.date = Field(
        sa_column=Column(Date, nullable=False, index=True)
    )
    returned_date: Optional[datetime.date] = Field(
        default=None,
        sa_column=Column(Date, nullable=True)
    )
    fine_amount: float = Field(
        default=0.0,
        sa_column=Column(Float, nullable=False, default=0.0)
    )
    status: BookLoanStatus = Field(
        default=BookLoanStatus.BORROWED,
        sa_column=Column(
            SAEnum(BookLoanStatus, name="sms_book_loan_status", native_enum=False),
            nullable=False,
            default=BookLoanStatus.BORROWED,
        ),
    )
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.datetime.now(datetime.timezone.utc),
        ),
    )
