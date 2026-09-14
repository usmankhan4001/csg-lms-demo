"""Exam seating and resits.

Two gaps a real school hits on its first exam week, kept in a separate module
so `sms_exam.py`'s existing tables are untouched: `create_all` creates missing
TABLES but never ALTERs an existing one, so new tables land everywhere while a
new column would silently fail to appear on any database that already has the
table. No Alembic migration is required for anything here.

SEATING is per (exam section schedule, student) rather than per (exam,
student): an exam is sat by several sections at once, each in its own room
under its own invigilator, and `ExamSectionSchedule` already carries that
split. Hanging seats off the schedule row means a seat inherits the room and
invigilator it was allocated under, instead of duplicating them.

RESITS are a link between the original exam and a second exam, never an edit
of the first result. A resit that overwrote the original mark would destroy the
record that the first sitting happened -- which is exactly what a school needs
when a parent or an inspector asks why a grade changed. Both sittings stay
readable, and the school decides which counts.
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


class ResitReason(str, Enum):
    """Why a candidate is sitting again.

    Recorded rather than inferred: a school is regularly asked to justify a
    resit, and "the system decided" is not an answer. MALPRACTICE is kept
    distinct from FAILED because the two carry entirely different
    consequences for a child.
    """

    ABSENT = "ABSENT"
    ILLNESS = "ILLNESS"
    TIMETABLE_CLASH = "TIMETABLE_CLASH"
    FAILED = "FAILED"
    MALPRACTICE = "MALPRACTICE"
    OTHER = "OTHER"


class ResitStatus(str, Enum):
    APPROVED = "APPROVED"
    SCHEDULED = "SCHEDULED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class ExamSeatAllocation(SQLModel, table=True):
    """One candidate's seat for one section's sitting of one exam.

    `seat_label` is free text ("A12", "Row 3 Seat 4") because seating
    conventions are a school's own and a rigid row/column model would fit
    some halls and not others.
    """

    __tablename__ = "sms_exam_seat_allocation"
    __table_args__ = (
        # One seat per candidate per sitting, and one candidate per seat.
        UniqueConstraint(
            "schedule_id", "student_id", name="uq_sms_exam_seat_student"
        ),
        UniqueConstraint(
            "schedule_id", "seat_label", name="uq_sms_exam_seat_label"
        ),
        Index("ix_sms_exam_seat_schedule", "schedule_id"),
        Index("ix_sms_exam_seat_student", "student_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    schedule_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("sms_exam_section_schedule.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    # Plain integer, not an FK: the seating record is a record of where a
    # candidate actually sat, and must survive the student row being removed.
    student_id: int = Field(sa_column=Column(Integer, nullable=False))
    seat_label: str = Field(sa_column=Column(String(40), nullable=False))
    notes: Optional[str] = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
        description="Access arrangements, e.g. extra time or a separate room.",
    )
    allocated_by_user_id: Optional[int] = Field(
        default=None, sa_column=Column(Integer, nullable=True)
    )
    allocated_at: datetime.datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class ExamResit(SQLModel, table=True):
    """A candidate's approved second sitting of an exam.

    `resit_exam_id` is nullable on purpose: a resit is approved before it is
    scheduled, and forcing a school to invent a date at approval time would
    put a fictional exam in the calendar.
    """

    __tablename__ = "sms_exam_resit"
    __table_args__ = (
        # A candidate has at most one live resit per original exam. A second
        # is a data-entry mistake far more often than a genuine third sitting.
        UniqueConstraint(
            "original_exam_id", "student_id", name="uq_sms_exam_resit_student"
        ),
        Index("ix_sms_exam_resit_student", "student_id"),
        Index("ix_sms_exam_resit_original", "original_exam_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    original_exam_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("sms_exam.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    # Nullable, and deliberately NOT a foreign key with CASCADE: deleting a
    # resit exam must not silently erase the record that a resit was approved.
    resit_exam_id: Optional[int] = Field(
        default=None, sa_column=Column(Integer, nullable=True)
    )
    student_id: int = Field(sa_column=Column(Integer, nullable=False))
    reason: ResitReason = Field(
        sa_column=Column(String(20), nullable=False),
    )
    reason_detail: Optional[str] = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    status: ResitStatus = Field(
        default=ResitStatus.APPROVED,
        sa_column=Column(String(20), nullable=False, default=ResitStatus.APPROVED.value),
    )
    approved_by_user_id: Optional[int] = Field(
        default=None, sa_column=Column(Integer, nullable=True)
    )
    approved_at: datetime.datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
