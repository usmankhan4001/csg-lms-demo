import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, desc, or_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.events.database import get_db_session
from src.core.keycloak_auth import (
    KeycloakUserPrincipal,
    get_current_user_principal,
    require_roles,
)
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
from src.db.sms_library_extended import ReservationStatus
from src.schemas.sms_library_extended import (
    CloseReservationRequest,
    MarkReadyRequest,
    ReservationRead,
    ReservationWithPosition,
    ReserveBookRequest,
)
from src.services.sms.library_extended import (
    ReservationError,
    close_reservation,
    expire_stale_holds,
    list_reservations,
    mark_ready,
    queue_position,
    reserve_book,
)
from src.security.features_utils.dependencies import require_sms_library_feature
from src.security.school_ownership import (
    assert_campus_allowed,
    resolve_scoped_campus_id,
)
from src.services.sms.library import (
    batch_calculate_overdue_fines,
    borrow_library_book,
    return_library_book,
)

# The catalogue and the loan desk are librarian/back-office work. TEACHER is
# excluded: a teacher borrowing books is a patron, not a librarian.
#
# `return_book` is gated here too, which is deliberate and worth stating: it
# accepts a `fine_amount` override and an arbitrary `loan_id`, so leaving it
# open let any signed-in user close someone else's loan and zero their own
# fine. A genuine self-service return flow would need the override removed and
# the loan bound to the caller first; until then this stays a desk action.
_LIBRARIAN = ["SUPER_ADMIN", "SCHOOL_ADMIN", "STAFF"]

router = APIRouter(dependencies=[Depends(require_sms_library_feature)])


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
    principal: KeycloakUserPrincipal = Depends(require_roles(_LIBRARIAN)),
) -> LibraryBookRead:
    # Fail loudly rather than quietly shelving the book at a different campus.
    assert_campus_allowed(principal, payload.campus_id)
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
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> List[LibraryBookRead]:
    conditions = []
    # Narrow: an omitted filter previously listed every campus's catalogue.
    campus_id = resolve_scoped_campus_id(principal, campus_id if isinstance(campus_id, int) else None)
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
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
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
    principal: KeycloakUserPrincipal = Depends(require_roles(_LIBRARIAN)),
) -> LibraryBookRead:
    stmt = select(LibraryBook).where(LibraryBook.id == book_id)
    book = (await session.execute(stmt)).scalars().first()
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Book with ID {book_id} not found",
        )

    # Both directions: the book you are editing, and where you move it to.
    assert_campus_allowed(principal, book.campus_id)
    assert_campus_allowed(principal, payload.campus_id)

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
    principal: KeycloakUserPrincipal = Depends(require_roles(_LIBRARIAN)),
):
    stmt = select(LibraryBook).where(LibraryBook.id == book_id)
    book = (await session.execute(stmt)).scalars().first()
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Book with ID {book_id} not found",
        )
    # Deleting another campus's catalogue entry is a cross-campus write.
    assert_campus_allowed(principal, book.campus_id)
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
    principal: KeycloakUserPrincipal = Depends(require_roles(_LIBRARIAN)),
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
    principal: KeycloakUserPrincipal = Depends(require_roles(_LIBRARIAN)),
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
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
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
    principal: KeycloakUserPrincipal = Depends(require_roles(_LIBRARIAN)),
) -> CalculateFinesResponse:
    fine_rate = payload.fine_per_day if payload else 1.0
    ref_date = payload.as_of_date if payload else datetime.date.today()

    count, total = await batch_calculate_overdue_fines(
        session=session,
        fine_per_day=fine_rate,
        as_of_date=ref_date,
        # Scope the run to the caller's campus: unscoped, this levied fines on
        # overdue families at every campus in the org.
        campus_id=resolve_scoped_campus_id(principal, None),
    )
    return CalculateFinesResponse(
        updated_loans_count=count,
        total_fines_accumulated=total,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Reservations / holds (M12)
#
# Queue position is DERIVED from reserved_at on every read, never stored. A
# stored position must be rewritten for everyone behind a cancellation, and one
# missed rewrite silently reorders the queue -- which in a school means telling
# a child they are next when they are not.
#
# NOTE ON THE MODEL: LibraryBook counts total_copies/available_copies and has
# no per-copy row, so a hold reserves a place in the queue for the TITLE, never
# a specific copy. Honest for a school library, but it means per-copy condition
# or "which copy was lost" cannot be built on this without a copies table.
# ─────────────────────────────────────────────────────────────────────────────


@router.post(
    "/reservations",
    response_model=ReservationWithPosition,
    status_code=status.HTTP_201_CREATED,
    summary="Reserve a Book",
    description=(
        "Places a hold and returns the reader's position in the queue. A "
        "second live hold on the same title is refused: it would jump the "
        "reader ahead of others genuinely waiting."
    ),
)
async def reserve_book_endpoint(
    payload: ReserveBookRequest,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> ReservationWithPosition:
    caller_id = (principal.raw_claims or {}).get("lh_user_id")
    target_user_id = payload.user_id

    # Reserving for someone else is a desk action. Without this a reader could
    # place holds in another person's name and consume their queue slots.
    if target_user_id is not None and target_user_id != caller_id:
        if not (
            principal.is_superadmin
            or principal.has_any_role(_LIBRARIAN)
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only library staff may reserve on another reader's behalf.",
            )
    if target_user_id is None:
        target_user_id = caller_id
    if target_user_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not resolve the reader for this reservation.",
        )

    try:
        row, position = await reserve_book(
            session=session, book_id=payload.book_id, user_id=target_user_id
        )
    except ReservationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    data = ReservationRead.model_validate(row).model_dump()
    return ReservationWithPosition(**data, queue_position=position)


@router.get(
    "/reservations",
    response_model=List[ReservationWithPosition],
    summary="List Reservations",
)
async def list_reservations_endpoint(
    book_id: Optional[int] = Query(None),
    user_id: Optional[int] = Query(None),
    reservation_status: Optional[ReservationStatus] = Query(None),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> List[ReservationWithPosition]:
    caller_id = (principal.raw_claims or {}).get("lh_user_id")
    is_staff = principal.is_superadmin or principal.has_any_role(_LIBRARIAN)

    # A reader sees only their own holds. Otherwise the queue for a title
    # discloses who in the school is reading what.
    effective_user = user_id if is_staff else caller_id

    rows = await list_reservations(
        session=session,
        book_id=book_id,
        user_id=effective_user,
        campus_id=resolve_scoped_campus_id(principal, None) if is_staff else None,
        status=reservation_status,
    )
    out: List[ReservationWithPosition] = []
    for r in rows:
        pos = await queue_position(session=session, reservation=r)
        out.append(
            ReservationWithPosition(
                **ReservationRead.model_validate(r).model_dump(), queue_position=pos
            )
        )
    return out


@router.patch(
    "/reservations/{reservation_id}/ready",
    response_model=ReservationRead,
    summary="Hold a Returned Copy for the Next Reader",
    description=(
        "Refuses when no copy is actually available -- otherwise the desk "
        "tells a child their book is waiting when it is not."
    ),
)
async def mark_reservation_ready(
    reservation_id: int,
    payload: MarkReadyRequest,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_LIBRARIAN)),
) -> ReservationRead:
    try:
        row = await mark_ready(
            session=session,
            reservation_id=reservation_id,
            hold_days=payload.hold_days,
        )
    except ReservationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return ReservationRead.model_validate(row)


@router.patch(
    "/reservations/{reservation_id}/close",
    response_model=ReservationRead,
    summary="Close a Reservation",
    description=(
        "Closes a hold as FULFILLED, CANCELLED or EXPIRED. Closing is explicit "
        "and never inferred from a loan appearing, because a copy may be "
        "borrowed by someone else entirely."
    ),
)
async def close_reservation_endpoint(
    reservation_id: int,
    payload: CloseReservationRequest,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_LIBRARIAN)),
) -> ReservationRead:
    try:
        row = await close_reservation(
            session=session, reservation_id=reservation_id, status=payload.status
        )
    except ReservationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return ReservationRead.model_validate(row)


@router.post(
    "/reservations/expire-stale",
    response_model=List[ReservationRead],
    summary="Release Uncollected Holds",
    description=(
        "Expires READY holds nobody collected so the queue moves on. Returns "
        "what it expired, so a librarian sees it happened rather than finding "
        "holds silently gone."
    ),
)
async def expire_stale_holds_endpoint(
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_LIBRARIAN)),
) -> List[ReservationRead]:
    rows = await expire_stale_holds(
        session=session, campus_id=resolve_scoped_campus_id(principal, None)
    )
    return [ReservationRead.model_validate(r) for r in rows]
