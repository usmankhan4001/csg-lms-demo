import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, desc, or_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.events.database import get_db_session
from src.db.sms_library import BookLoan, BookLoanStatus, LibraryBook
from src.schemas.sms_library import (
    BookLoanRead,
    BorrowBookRequest,
    CalculateFinesRequest,
    CalculateFinesResponse,
    LibraryBookCreate,
    LibraryBookRead,
    LibraryBookUpdate,
    ReturnBookRequest,
)
from src.services.sms.library import (
    batch_calculate_overdue_fines,
    borrow_library_book,
    return_library_book,
)

router = APIRouter()


# ── Books Catalog Endpoints ──

@router.post(
    "/books",
    response_model=LibraryBookRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add Book to Library Catalog",
)
async def create_book(
    payload: LibraryBookCreate,
    session: AsyncSession = Depends(get_db_session),
) -> LibraryBookRead:
    book = LibraryBook(
        campus_id=payload.campus_id,
        isbn=payload.isbn,
        title=payload.title,
        author=payload.author,
        category=payload.category,
        total_copies=payload.total_copies,
        available_copies=payload.total_copies,
        digital_file_url=payload.digital_file_url,
    )
    session.add(book)
    await session.commit()
    await session.refresh(book)
    return LibraryBookRead.model_validate(book)


@router.get(
    "/books",
    response_model=List[LibraryBookRead],
    summary="Search and List Library Books",
)
async def list_books(
    campus_id: Optional[int] = Query(None, description="Filter by Campus ID"),
    category: Optional[str] = Query(None, description="Filter by category"),
    search: Optional[str] = Query(None, description="Search by title, author, or ISBN"),
    available_only: bool = Query(False, description="Filter only books with available copies"),
    session: AsyncSession = Depends(get_db_session),
) -> List[LibraryBookRead]:
    conditions = []
    if isinstance(campus_id, int):
        conditions.append(LibraryBook.campus_id == campus_id)
    if isinstance(category, str) and category:
        conditions.append(LibraryBook.category == category)
    if isinstance(available_only, bool) and available_only:
        conditions.append(LibraryBook.available_copies > 0)
    if isinstance(search, str) and search:
        search_pattern = f"%{search.strip()}%"
        conditions.append(
            or_(
                LibraryBook.title.ilike(search_pattern),
                LibraryBook.author.ilike(search_pattern),
                LibraryBook.isbn.ilike(search_pattern),
            )
        )

    stmt = select(LibraryBook)
    if conditions:
        stmt = stmt.where(and_(*conditions))
    stmt = stmt.order_by(LibraryBook.title)

    books = (await session.execute(stmt)).scalars().all()
    return [LibraryBookRead.model_validate(b) for b in books]


@router.get(
    "/books/{book_id}",
    response_model=LibraryBookRead,
    summary="Get Book by ID",
)
async def get_book(
    book_id: int,
    session: AsyncSession = Depends(get_db_session),
) -> LibraryBookRead:
    stmt = select(LibraryBook).where(LibraryBook.id == book_id)
    book = (await session.execute(stmt)).scalars().first()
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Book with ID {book_id} not found",
        )
    return LibraryBookRead.model_validate(book)


@router.put(
    "/books/{book_id}",
    response_model=LibraryBookRead,
    summary="Update Book in Catalog",
)
async def update_book(
    book_id: int,
    payload: LibraryBookUpdate,
    session: AsyncSession = Depends(get_db_session),
) -> LibraryBookRead:
    stmt = select(LibraryBook).where(LibraryBook.id == book_id)
    book = (await session.execute(stmt)).scalars().first()
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Book with ID {book_id} not found",
        )

    if payload.campus_id is not None:
        book.campus_id = payload.campus_id
    if payload.isbn is not None:
        book.isbn = payload.isbn
    if payload.title is not None:
        book.title = payload.title
    if payload.author is not None:
        book.author = payload.author
    if payload.category is not None:
        book.category = payload.category
    if payload.total_copies is not None:
        diff = payload.total_copies - book.total_copies
        book.total_copies = payload.total_copies
        book.available_copies = max(book.available_copies + diff, 0)
    if payload.available_copies is not None:
        book.available_copies = payload.available_copies
    if payload.digital_file_url is not None:
        book.digital_file_url = payload.digital_file_url

    session.add(book)
    await session.commit()
    await session.refresh(book)
    return LibraryBookRead.model_validate(book)


@router.delete(
    "/books/{book_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Book from Catalog",
)
async def delete_book(
    book_id: int,
    session: AsyncSession = Depends(get_db_session),
):
    stmt = select(LibraryBook).where(LibraryBook.id == book_id)
    book = (await session.execute(stmt)).scalars().first()
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Book with ID {book_id} not found",
        )
    await session.delete(book)
    await session.commit()
    return None


# ── Book Loans & Circulation Endpoints ──

@router.post(
    "/loans/borrow",
    response_model=BookLoanRead,
    status_code=status.HTTP_201_CREATED,
    summary="Borrow a Library Book",
)
async def borrow_book(
    payload: BorrowBookRequest,
    session: AsyncSession = Depends(get_db_session),
) -> BookLoanRead:
    try:
        loan = await borrow_library_book(
            session=session,
            book_id=payload.book_id,
            user_id=payload.user_id,
            borrowed_date=payload.borrowed_date,
            due_date=payload.due_date,
        )
        return BookLoanRead.model_validate(loan)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/loans/{loan_id}/return",
    response_model=BookLoanRead,
    summary="Return a Borrowed Library Book",
)
async def return_book(
    loan_id: int,
    payload: Optional[ReturnBookRequest] = None,
    session: AsyncSession = Depends(get_db_session),
) -> BookLoanRead:
    ret_date = payload.returned_date if payload else None
    override_fine = payload.fine_amount if payload else None

    try:
        loan = await return_library_book(
            session=session,
            loan_id=loan_id,
            returned_date=ret_date,
            override_fine=override_fine,
        )
        return BookLoanRead.model_validate(loan)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/loans",
    response_model=List[BookLoanRead],
    summary="List Book Loans",
)
async def list_loans(
    user_id: Optional[int] = Query(None, description="Filter by borrower user ID"),
    book_id: Optional[int] = Query(None, description="Filter by book ID"),
    loan_status: Optional[BookLoanStatus] = Query(None, alias="status", description="Filter by status"),
    session: AsyncSession = Depends(get_db_session),
) -> List[BookLoanRead]:
    conditions = []
    if isinstance(user_id, int):
        conditions.append(BookLoan.user_id == user_id)
    if isinstance(book_id, int):
        conditions.append(BookLoan.book_id == book_id)
    if isinstance(loan_status, (BookLoanStatus, str)):
        conditions.append(BookLoan.status == loan_status)

    stmt = select(BookLoan)
    if conditions:
        stmt = stmt.where(and_(*conditions))
    stmt = stmt.order_by(desc(BookLoan.borrowed_date))

    loans = (await session.execute(stmt)).scalars().all()
    return [BookLoanRead.model_validate(l) for l in loans]


@router.post(
    "/loans/calculate-fines",
    response_model=CalculateFinesResponse,
    summary="Calculate Overdue Fines",
    description="Evaluates all active loans against due dates, marks overdue items, and updates fine amounts.",
)
async def calculate_overdue_fines_endpoint(
    payload: Optional[CalculateFinesRequest] = None,
    session: AsyncSession = Depends(get_db_session),
) -> CalculateFinesResponse:
    fine_rate = payload.fine_per_day if payload else 1.0
    ref_date = payload.as_of_date if payload else datetime.date.today()

    count, total = await batch_calculate_overdue_fines(
        session=session,
        fine_per_day=fine_rate,
        as_of_date=ref_date,
    )
    return CalculateFinesResponse(
        updated_loans_count=count,
        total_fines_accumulated=total,
    )
