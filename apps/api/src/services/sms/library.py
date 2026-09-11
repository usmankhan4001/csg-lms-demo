import datetime
from typing import List, Optional, Tuple
from sqlalchemy import and_, or_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_library import BookLoan, BookLoanStatus, LibraryBook


async def borrow_library_book(
    session: AsyncSession,
    book_id: int,
    user_id: int,
    borrowed_date: Optional[datetime.date] = None,
    due_date: Optional[datetime.date] = None,
) -> BookLoan:
    """
    Checks book availability, reserves a copy, and records the borrow loan.
    """
    stmt = select(LibraryBook).where(LibraryBook.id == book_id)
    book = (await session.execute(stmt)).scalars().first()
    if not book:
        raise ValueError(f"Book with ID {book_id} not found")

    if book.available_copies <= 0:
        raise ValueError(f"No copies of '{book.title}' are currently available for borrowing")

    b_date = borrowed_date or datetime.date.today()
    d_date = due_date or (b_date + datetime.timedelta(days=14))

    book.available_copies -= 1

    loan = BookLoan(
        book_id=book_id,
        user_id=user_id,
        borrowed_date=b_date,
        due_date=d_date,
        returned_date=None,
        fine_amount=0.0,
        status=BookLoanStatus.BORROWED,
    )
    session.add(loan)
    session.add(book)
    await session.commit()
    await session.refresh(loan)
    return loan


async def return_library_book(
    session: AsyncSession,
    loan_id: int,
    returned_date: Optional[datetime.date] = None,
    override_fine: Optional[float] = None,
    fine_rate_per_day: float = 1.0,
) -> BookLoan:
    """
    Processes book return, replenishes available inventory, and calculates overdue fines.
    """
    stmt = select(BookLoan).where(BookLoan.id == loan_id)
    loan = (await session.execute(stmt)).scalars().first()
    if not loan:
        raise ValueError(f"Loan with ID {loan_id} not found")

    if loan.status == BookLoanStatus.RETURNED:
        raise ValueError("Book has already been returned for this loan record")

    ret_date = returned_date or datetime.date.today()
    loan.returned_date = ret_date
    loan.status = BookLoanStatus.RETURNED

    if override_fine is not None:
        loan.fine_amount = round(override_fine, 2)
    elif ret_date > loan.due_date:
        overdue_days = (ret_date - loan.due_date).days
        loan.fine_amount = round(max(overdue_days * fine_rate_per_day, 0.0), 2)
    else:
        loan.fine_amount = 0.0

    # Replenish available copy count on book
    book_stmt = select(LibraryBook).where(LibraryBook.id == loan.book_id)
    book = (await session.execute(book_stmt)).scalars().first()
    if book:
        book.available_copies = min(book.available_copies + 1, book.total_copies)
        session.add(book)

    session.add(loan)
    await session.commit()
    await session.refresh(loan)
    return loan


async def batch_calculate_overdue_fines(
    session: AsyncSession,
    fine_per_day: float = 1.0,
    as_of_date: Optional[datetime.date] = None,
) -> Tuple[int, float]:
    """
    Evaluates all active loans against reference date, marks overdue items, and updates fines.
    """
    ref_date = as_of_date or datetime.date.today()

    stmt = select(BookLoan).where(
        and_(
            or_(
                BookLoan.status == BookLoanStatus.BORROWED,
                BookLoan.status == BookLoanStatus.OVERDUE,
            ),
            BookLoan.due_date < ref_date,
            BookLoan.returned_date.is_(None),
        )
    )
    overdue_loans = (await session.execute(stmt)).scalars().all()

    total_fines = 0.0
    for loan in overdue_loans:
        overdue_days = (ref_date - loan.due_date).days
        loan.status = BookLoanStatus.OVERDUE
        fine = round(max(overdue_days * fine_per_day, 0.0), 2)
        loan.fine_amount = fine
        total_fines += fine
        session.add(loan)

    await session.commit()
    return len(overdue_loans), round(total_fines, 2)
