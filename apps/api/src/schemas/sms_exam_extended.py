"""Schemas for exam seating and resits."""

import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from src.db.sms_exam_extended import ResitReason, ResitStatus


class SeatAllocationInput(BaseModel):
    student_id: int
    seat_label: str = Field(..., min_length=1, max_length=40)
    notes: Optional[str] = Field(
        None, description="Access arrangements, e.g. extra time or a separate room."
    )


class AllocateSeatsRequest(BaseModel):
    allocations: List[SeatAllocationInput]
    replace_existing: bool = Field(
        False,
        description=(
            "Overwrite an existing seat or reassign an occupied one. Off by "
            "default so a re-run cannot silently move candidates."
        ),
    )


class SeatAllocationRead(BaseModel):
    id: int
    schedule_id: int
    student_id: int
    seat_label: str
    notes: Optional[str] = None
    allocated_by_user_id: Optional[int] = None
    allocated_at: datetime.datetime

    class Config:
        from_attributes = True


class AllocateSeatsResponse(BaseModel):
    schedule_id: int
    allocated: List[SeatAllocationRead]
    skipped: List[str] = Field(
        default_factory=list,
        description=(
            "Rows that were NOT allocated, each with its reason. A clash is "
            "reported rather than resolved: an auto-reseated candidate finds "
            "someone in their chair on the day."
        ),
    )


class ApproveResitRequest(BaseModel):
    student_id: int
    reason: ResitReason
    reason_detail: Optional[str] = None


class ScheduleResitRequest(BaseModel):
    resit_exam_id: int


class ResitRead(BaseModel):
    id: int
    original_exam_id: int
    resit_exam_id: Optional[int] = None
    student_id: int
    reason: ResitReason
    reason_detail: Optional[str] = None
    status: ResitStatus
    approved_by_user_id: Optional[int] = None
    approved_at: datetime.datetime

    class Config:
        from_attributes = True


class ResitCandidate(BaseModel):
    student_id: int
    suggested_reason: Optional[ResitReason] = Field(
        None,
        description=(
            "None means the record shows a gap to chase rather than grounds "
            "for a resit -- e.g. sat the exam but has no mark yet."
        ),
    )
    evidence: str = Field(
        ...,
        description="What the record actually shows. Never an inference.",
    )
