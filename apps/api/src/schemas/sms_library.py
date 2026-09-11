import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field
from src.db.sms_library import BookLoanStatus


class LibraryBookCreate(BaseModel):
    campus_id: Optional[int] = Field(None, description="Campus ID where book is located")
    isbn: Optional[str] = Field(None, description="ISBN / Barcode number")
    title: str = Field(..., description="Title of the book")
    author: str = Field(..., description="Author name")
    category: Optional[str] = Field(None, description="Genre or category")
    total_copies: int = Field(1, ge=1, description="Total number of physical copies")
    digital_file_url: Optional[str] = Field(None, description="PDF / ePub media link for e-library")


class LibraryBookUpdate(BaseModel):
    campus_id: Optional[int] = None
    isbn: Optional[str] = None
    title: Optional[str] = None
    author: Optional[str] = None
    category: Optional[str] = None
    total_copies: Optional[int] = Field(None, ge=0)
    available_copies: Optional[int] = Field(None, ge=0)
    digital_file_url: Optional[str] = None


class LibraryBookRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campus_id: Optional[int] = None
    isbn: Optional[str] = None
    title: str
    author: str
    category: Optional[str] = None
    total_copies: int
    available_copies: int
    digital_file_url: Optional[str] = None
    created_at: datetime.datetime


class BorrowBookRequest(BaseModel):
    book_id: int = Field(..., description="ID of the book to borrow")
    user_id: int = Field(..., description="User ID borrowing the book")
    borrowed_date: Optional[datetime.date] = Field(None, description="Date borrowed (default today)")
    due_date: Optional[datetime.date] = Field(None, description="Due date for return (default borrowed_date + 14 days)")


class ReturnBookRequest(BaseModel):
    returned_date: Optional[datetime.date] = Field(None, description="Actual return date (default today)")
    fine_amount: Optional[float] = Field(None, ge=0.0, description="Override fine amount")


class CalculateFinesRequest(BaseModel):
    fine_per_day: float = Field(1.0, ge=0.0, description="Fine amount per overdue day")
    as_of_date: Optional[datetime.date] = Field(None, description="Reference date for calculating overdue days")


class BookLoanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    book_id: int
    user_id: int
    borrowed_date: datetime.date
    due_date: datetime.date
    returned_date: Optional[datetime.date] = None
    fine_amount: float
    status: BookLoanStatus
    created_at: datetime.datetime
    book_title: Optional[str] = None


class CalculateFinesResponse(BaseModel):
    updated_loans_count: int
    total_fines_accumulated: float
