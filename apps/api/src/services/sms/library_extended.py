"""Library reservations.

Queue position is DERIVED from `reserved_at` on every read rather than stored.
A stored position has to be rewritten for everyone behind a cancellation, and
a single missed rewrite silently reorders a queue in a way nobody can see --
which in a school means a child being told they are next when they are not.
"""

import datetime
from typing import List, Optional, Tuple

from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_library import LibraryBook
from src.db.sms_library_extended import BookReservation, ReservationStatus

# How long a copy is held at the desk before the hold lapses and the next
# reader is offered it. A school's own policy, so it is a default rather than
# a constant baked into the logic.
DEFAULT_HOLD_DAYS = 3

LIVE_STATUSES = (ReservationStatus.WAITING, ReservationStatus.READY)


class ReservationError(ValueError):
    """A hold could not be placed or changed, with a reason a human can act on."""


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


async def reserve_book(
    *,
    session: AsyncSession,
    book_id: int,
    user_id: int,
) -> Tuple[BookReservation, int]:
    """Place a hold. Returns (reservation, queue_position).

    Refuses if the reader already holds a live reservation for this title --
    a second hold would jump them ahead of readers who are genuinely waiting.
    """
    book = (
        await session.execute(select(LibraryBook).where(LibraryBook.id == book_id))
    ).scalar_one_or_none()
    if book is None:
        raise ReservationError(f"Book {book_id} not found.")

    existing = (
        await session.execute(
            select(BookReservation).where(
                BookReservation.book_id == book_id,
                BookReservation.user_id == user_id,
                BookReservation.status.in_([s.value for s in LIVE_STATUSES]),
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise ReservationError(
            "You already have a live reservation for this title."
        )

    row = BookReservation(
        book_id=book_id,
        user_id=user_id,
        campus_id=getattr(book, "campus_id", None),
        status=ReservationStatus.WAITING,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)

    position = await queue_position(session=session, reservation=row)
    return row, position


async def queue_position(
    *, session: AsyncSession, reservation: BookReservation
) -> int:
    """1-based place in the queue, derived from reserved_at.

    A READY hold is position 0: the copy is already on the desk, so the
    reader is not waiting for anyone.
    """
    if reservation.status == ReservationStatus.READY:
        return 0
    if reservation.status not in LIVE_STATUSES:
        return -1

    ahead = (
        (
            await session.execute(
                select(BookReservation).where(
                    BookReservation.book_id == reservation.book_id,
                    BookReservation.status.in_([s.value for s in LIVE_STATUSES]),
                    BookReservation.reserved_at < reservation.reserved_at,
                )
            )
        )
        .scalars()
        .all()
    )
    return len(ahead) + 1


async def list_reservations(
    *,
    session: AsyncSession,
    book_id: Optional[int] = None,
    user_id: Optional[int] = None,
    campus_id: Optional[int] = None,
    status: Optional[ReservationStatus] = None,
) -> List[BookReservation]:
    stmt = select(BookReservation)
    if book_id is not None:
        stmt = stmt.where(BookReservation.book_id == book_id)
    if user_id is not None:
        stmt = stmt.where(BookReservation.user_id == user_id)
    if campus_id is not None:
        stmt = stmt.where(BookReservation.campus_id == campus_id)
    if status is not None:
        stmt = stmt.where(BookReservation.status == status)
    result = await session.execute(stmt.order_by(BookReservation.reserved_at))
    return list(result.scalars().all())


async def next_in_queue(
    *, session: AsyncSession, book_id: int
) -> Optional[BookReservation]:
    """The reader who has been waiting longest, or None."""
    result = await session.execute(
        select(BookReservation)
        .where(
            BookReservation.book_id == book_id,
            BookReservation.status == ReservationStatus.WAITING,
        )
        .order_by(BookReservation.reserved_at)
        .limit(1)
    )
    return result.scalar_one_or_none()


async def mark_ready(
    *,
    session: AsyncSession,
    reservation_id: int,
    hold_days: int = DEFAULT_HOLD_DAYS,
) -> BookReservation:
    """Put a returned copy aside for the next reader.

    Refuses to hold a copy that is not actually available -- otherwise the
    desk tells a child their book is waiting and it is not.
    """
    row = (
        await session.execute(
            select(BookReservation).where(BookReservation.id == reservation_id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise ReservationError(f"Reservation {reservation_id} not found.")
    if row.status != ReservationStatus.WAITING:
        raise ReservationError(
            f"Reservation is {row.status}, so it cannot be made ready."
        )

    book = (
        await session.execute(
            select(LibraryBook).where(LibraryBook.id == row.book_id)
        )
    ).scalar_one_or_none()
    if book is None:
        raise ReservationError("The title no longer exists.")
    if (book.available_copies or 0) <= 0:
        raise ReservationError(
            "No copy is available to hold. The title is still fully on loan."
        )

    now = _utcnow()
    row.status = ReservationStatus.READY
    row.ready_at = now
    row.expires_at = now + datetime.timedelta(days=hold_days)
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def close_reservation(
    *,
    session: AsyncSession,
    reservation_id: int,
    status: ReservationStatus,
) -> BookReservation:
    """Close a hold as FULFILLED, CANCELLED or EXPIRED.

    Closing is explicit and never inferred from a loan appearing: a copy can
    be borrowed by someone else entirely, and guessing would silently consume
    a reader's place in the queue.
    """
    if status in LIVE_STATUSES:
        raise ReservationError(f"{status} is not a closing status.")

    row = (
        await session.execute(
            select(BookReservation).where(BookReservation.id == reservation_id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise ReservationError(f"Reservation {reservation_id} not found.")
    if row.status not in LIVE_STATUSES:
        raise ReservationError(f"Reservation is already {row.status}.")

    row.status = status
    row.closed_at = _utcnow()
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def expire_stale_holds(
    *, session: AsyncSession, campus_id: Optional[int] = None
) -> List[BookReservation]:
    """Release READY holds nobody collected, so the queue moves on.

    Returns what it expired, so a librarian can see it happened rather than
    finding holds silently vanished.
    """
    now = _utcnow()
    stmt = select(BookReservation).where(
        BookReservation.status == ReservationStatus.READY,
        BookReservation.expires_at.is_not(None),
        BookReservation.expires_at < now,
    )
    if campus_id is not None:
        stmt = stmt.where(BookReservation.campus_id == campus_id)

    stale = (await session.execute(stmt)).scalars().all()
    for row in stale:
        row.status = ReservationStatus.EXPIRED
        row.closed_at = now
        session.add(row)
    if stale:
        await session.commit()
    return list(stale)
