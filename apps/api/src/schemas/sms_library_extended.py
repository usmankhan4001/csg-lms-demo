"""Schemas for library reservations."""

import datetime
from typing import Optional

from pydantic import BaseModel, Field

from src.db.sms_library_extended import ReservationStatus


class ReserveBookRequest(BaseModel):
    book_id: int
    user_id: Optional[int] = Field(
        None,
        description=(
            "Only a librarian may reserve on another reader's behalf. A "
            "reader's own hold takes the caller's identity from the session, "
            "never from this field."
        ),
    )


class ReservationRead(BaseModel):
    id: int
    book_id: int
    user_id: int
    campus_id: Optional[int] = None
    status: ReservationStatus
    reserved_at: datetime.datetime
    ready_at: Optional[datetime.datetime] = None
    expires_at: Optional[datetime.datetime] = None
    closed_at: Optional[datetime.datetime] = None
    notes: Optional[str] = None

    class Config:
        from_attributes = True


class ReservationWithPosition(ReservationRead):
    queue_position: int = Field(
        ...,
        description=(
            "1-based place in the queue. 0 means a copy is held at the desk "
            "for this reader; -1 means the hold is closed."
        ),
    )


class MarkReadyRequest(BaseModel):
    hold_days: int = Field(
        3, ge=1, le=30, description="Days the copy is held before the hold lapses."
    )


class CloseReservationRequest(BaseModel):
    status: ReservationStatus = Field(
        ...,
        description="FULFILLED, CANCELLED or EXPIRED. Live statuses are refused.",
    )
