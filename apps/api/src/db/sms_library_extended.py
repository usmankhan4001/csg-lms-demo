"""Library reservations.

A separate module so `sms_library.py`'s existing tables are untouched:
`create_all` creates missing TABLES but never ALTERs an existing one, so a new
table lands everywhere while a new column would silently fail to appear on any
database that already has the table. No Alembic migration is required.

A NOTE ON THE EXISTING MODEL, because it constrains what a reservation can
promise. `LibraryBook` tracks `total_copies` and `available_copies` as
COUNTERS -- there is no per-copy row, no accession number, no barcode. So the
library knows it holds three copies of a title and how many are out, but not
WHICH copy a given loan refers to. A reservation can therefore only ever hold a
place in a queue for the TITLE, never for a specific copy. That is honest for
most school libraries and worth knowing before anyone builds stock-taking,
per-copy condition, or "which copy did this child lose" on top of it.
"""

import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Index,
)
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


class ReservationStatus(str, Enum):
    """Where a hold is in its life.

    READY is distinct from FULFILLED: a copy has come back and is being held
    at the desk, but the borrower has not collected it yet. Without that
    distinction a library cannot tell "waiting for a copy" from "waiting for
    the reader to walk in", which are different problems with different
    remedies.
    """

    WAITING = "WAITING"
    READY = "READY"
    FULFILLED = "FULFILLED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class BookReservation(SQLModel, table=True):
    """A reader's place in the queue for a title.

    Queue order is derived from `reserved_at`, not stored as a position
    integer: a stored position has to be rewritten for everyone behind a
    cancellation, and any missed rewrite silently reorders a queue in a way
    nobody can see. A timestamp cannot drift out of order.
    """

    __tablename__ = "sms_book_reservation"
    __table_args__ = (
        Index("ix_sms_book_resv_book_status", "book_id", "status"),
        Index("ix_sms_book_resv_user", "user_id"),
        # Enforced in the service rather than here: a reader may hold the same
        # title again after a previous hold was fulfilled or cancelled, so
        # uniqueness applies only to LIVE holds, which a plain unique
        # constraint cannot express.
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    book_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("sms_library_book.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    # Plain integer: a reservation is a record of what a reader asked for and
    # should survive the user row being removed.
    user_id: int = Field(sa_column=Column(Integer, nullable=False))
    campus_id: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, nullable=True, index=True),
        description="Denormalised from the book so holds can be campus-scoped "
        "without a join on every read.",
    )
    status: ReservationStatus = Field(
        default=ReservationStatus.WAITING,
        sa_column=Column(String(20), nullable=False, default=ReservationStatus.WAITING.value),
    )
    reserved_at: datetime.datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    # Set when a copy is put aside. A library needs to release an uncollected
    # hold rather than let it block the queue forever.
    ready_at: Optional[datetime.datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    expires_at: Optional[datetime.datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    closed_at: Optional[datetime.datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    notes: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
