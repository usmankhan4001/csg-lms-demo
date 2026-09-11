import datetime
import pytest
from fastapi import HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_library import BookLoanStatus
from src.schemas.sms_library import (
    BorrowBookRequest,
    CalculateFinesRequest,
    LibraryBookCreate,
    LibraryBookUpdate,
    ReturnBookRequest,
)
from src.routers.sms_library import (
    borrow_book,
    calculate_overdue_fines_endpoint,
    create_book,
    delete_book,
    get_book,
    list_books,
    list_loans,
    return_book,
    update_book,
)


@pytest.mark.asyncio
async def test_library_catalog_crud_and_search(db: AsyncSession):
    """Test creating, reading, updating, searching, and deleting catalog books."""
    # 1. Create Books
    b1 = await create_book(
        payload=LibraryBookCreate(
            campus_id=1,
            isbn="978-0134685991",
            title="Effective Java",
            author="Joshua Bloch",
            category="Computer Science",
            total_copies=3,
        ),
        session=db,
    )
    assert b1.id is not None
    assert b1.available_copies == 3

    b2 = await create_book(
        payload=LibraryBookCreate(
            campus_id=1,
            isbn="978-0132350884",
            title="Clean Code",
            author="Robert C. Martin",
            category="Computer Science",
            total_copies=2,
            digital_file_url="https://library.csg.edu/books/clean-code.pdf",
        ),
        session=db,
    )
    assert b2.id is not None

    # 2. Get Book by ID
    fetched = await get_book(book_id=b1.id, session=db)
    assert fetched.title == "Effective Java"

    # 3. Search and filter
    cs_books = await list_books(category="Computer Science", session=db)
    assert len(cs_books) == 2

    searched = await list_books(search="Joshua", session=db)
    assert len(searched) == 1
    assert searched[0].id == b1.id

    # 4. Update Book
    updated = await update_book(
        book_id=b1.id,
        payload=LibraryBookUpdate(total_copies=5),
        session=db,
    )
    assert updated.total_copies == 5
    assert updated.available_copies == 5

    # 5. Delete Book
    await delete_book(book_id=b2.id, session=db)
    with pytest.raises(HTTPException) as exc_info:
        await get_book(book_id=b2.id, session=db)
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_library_borrow_return_and_fines(db: AsyncSession):
    """Test full book loan lifecycle: borrowing, returning, inventory tracking, and overdue fines."""
    # 1. Add book with 1 copy
    book = await create_book(
        payload=LibraryBookCreate(
            campus_id=1,
            isbn="978-0201616224",
            title="The Pragmatic Programmer",
            author="Andrew Hunt, David Thomas",
            category="Software Engineering",
            total_copies=1,
        ),
        session=db,
    )

    # 2. User 301 borrows the book
    borrow_date = datetime.date(2026, 8, 1)
    due_date = datetime.date(2026, 8, 15)
    loan = await borrow_book(
        payload=BorrowBookRequest(
            book_id=book.id,
            user_id=301,
            borrowed_date=borrow_date,
            due_date=due_date,
        ),
        session=db,
    )
    assert loan.id is not None
    assert loan.status == BookLoanStatus.BORROWED

    # Check available copies decremented to 0
    refreshed_book = await get_book(book_id=book.id, session=db)
    assert refreshed_book.available_copies == 0

    # 3. Another user tries to borrow the same unavailable book -> 400 error
    with pytest.raises(HTTPException) as exc:
        await borrow_book(
            payload=BorrowBookRequest(book_id=book.id, user_id=302),
            session=db,
        )
    assert exc.value.status_code == 400

    # 4. Calculate overdue fines as of 2026-08-20 (5 days overdue @ $2/day = $10)
    calc_res = await calculate_overdue_fines_endpoint(
        payload=CalculateFinesRequest(
            fine_per_day=2.0,
            as_of_date=datetime.date(2026, 8, 20),
        ),
        session=db,
    )
    assert calc_res.updated_loans_count == 1
    assert calc_res.total_fines_accumulated == 10.0

    # Verify loan status changed to OVERDUE
    loans = await list_loans(user_id=301, session=db)
    assert len(loans) == 1
    assert loans[0].status == BookLoanStatus.OVERDUE
    assert loans[0].fine_amount == 10.0

    # 5. User returns book on 2026-08-20
    returned_loan = await return_book(
        loan_id=loan.id,
        payload=ReturnBookRequest(
            returned_date=datetime.date(2026, 8, 20),
        ),
        session=db,
    )
    assert returned_loan.status == BookLoanStatus.RETURNED
    assert returned_loan.fine_amount == 5.0 * 1.0  # default return fine rate: 5 days * $1.0 = $5.0

    # Check available copies restored to 1
    restored_book = await get_book(book_id=book.id, session=db)
    assert restored_book.available_copies == 1
