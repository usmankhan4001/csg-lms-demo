"""
CSG-LMS School Examination Models (M04)
=======================================
School examinations -- scheduled, sat by a class section, invigilated, marked,
and fed into the existing gradebook.

Deliberately SEPARATE from Learnhouse's own LMS quiz feature
(`src/services/ai/quiz.py`): that is course content a learner takes inline at
their own pace. A school exam is an administrative event -- it has a date, a
room, an invigilator, a duration, and a result that lands on a report card.

Grading is NOT re-implemented here. `ExamResult.assessment_plan_id` links an
exam to an existing `AssessmentPlan`, and posting results writes ordinary
`GradebookEntry` rows, so the weighted-GPA engine in
`src/services/sms/gradebook.py` stays the single source of truth for what a
student scored. Two grading engines that could disagree would be far worse
than none.

PROCTORING SCOPE -- read this before assuming coverage:
Automated/remote proctoring (webcam monitoring, browser lockdown, screen
recording, identity verification, AI cheating detection) is **NOT
implemented** and nothing here should be read as providing it. What exists is
the administrative record a physical invigilated exam produces: who
invigilated, which room, actual start/end times, and a log of incidents the
invigilator writes down. That is a paper trail, not surveillance.

All tables are purely additive (no ALTER on any existing table), matching
every other `sms_*` model here: picked up by `SQLModel.metadata.create_all` at
app startup via `import_all_models()`, never through Alembic.
"""

import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlmodel import Field, SQLModel


def get_utc_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


class ExamStatus(str, Enum):
    """Lifecycle of an exam.

    RESULTS_POSTED is terminal and deliberately distinct from COMPLETED: it
    records that marks have reached the gradebook, which is the point after
    which re-posting must not silently double-write.
    """
    SCHEDULED = "SCHEDULED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    RESULTS_POSTED = "RESULTS_POSTED"
    CANCELLED = "CANCELLED"


class ExamAttendanceStatus(str, Enum):
    """Whether a student actually sat the exam.

    ABSENT and EXEMPT are NOT the same as scoring zero, and are stored
    separately from `marks_obtained` precisely so nothing downstream can
    mistake "did not sit" for "sat and failed".
    """
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"
    EXEMPT = "EXEMPT"
    MALPRACTICE = "MALPRACTICE"


class Exam(SQLModel, table=True):
    """A scheduled school examination for one course within a term."""
    __tablename__ = "sms_exam"
    __table_args__ = (
        Index("ix_sms_exam_campus_term", "campus_id", "academic_term_id"),
        Index("ix_sms_exam_date", "exam_date"),
        Index("ix_sms_exam_status", "status"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    campus_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("campus.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    academic_term_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("academic_term.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    course_id: int = Field(sa_column=Column(Integer, nullable=False, index=True))
    title: str = Field(sa_column=Column(String(200), nullable=False))
    exam_type: Optional[str] = Field(
        default=None,
        sa_column=Column(String(50), nullable=True),
        description="Free text, e.g. 'Midterm', 'Final', 'Unit Test'",
    )
    exam_date: datetime.date = Field(sa_column=Column(Date, nullable=False))
    start_time: Optional[str] = Field(
        default=None, sa_column=Column(String(5), nullable=True), description="HH:MM"
    )
    duration_minutes: int = Field(default=60, sa_column=Column(Integer, nullable=False))
    total_marks: float = Field(default=100.0, sa_column=Column(Float, nullable=False))
    pass_marks: float = Field(default=40.0, sa_column=Column(Float, nullable=False))
    # Links this exam to the gradebook's weighting structure. Nullable because
    # an exam may be scheduled before anyone has decided how it is weighted --
    # but results cannot be posted to the gradebook until it is set, and the
    # service raises rather than inventing a plan.
    assessment_plan_id: Optional[int] = Field(
        default=None,
        sa_column=Column(
            Integer,
            ForeignKey("sms_assessment_plan.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
    )
    status: ExamStatus = Field(
        default=ExamStatus.SCHEDULED,
        # No index=True here: __table_args__ already declares
        # Index("ix_sms_exam_status", "status"), and SQLAlchemy auto-names a
        # column index identically (ix_<table>_<column>) -- declaring both
        # makes create_all emit CREATE INDEX twice and fail on startup.
        sa_column=Column(String(20), nullable=False, default=ExamStatus.SCHEDULED.value),
    )
    instructions: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    created_by: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))
    created_at: datetime.datetime = Field(
        default_factory=get_utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False, default=get_utc_now),
    )


class ExamSectionSchedule(SQLModel, table=True):
    """Which class sections sit a given exam, in which room, under whom.

    An exam is typically sat by several sections at once, each in its own room
    with its own invigilator -- hence a separate row per section rather than
    room/invigilator columns on Exam itself.

    `actual_start_at`/`actual_end_at` are what the invigilator observed, which
    is frequently not the scheduled time. Keeping both matters for any later
    dispute about time allowed.
    """
    __tablename__ = "sms_exam_section_schedule"
    __table_args__ = (
        UniqueConstraint("exam_id", "section_id", name="uq_sms_exam_section"),
        Index("ix_sms_exam_sched_section", "section_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    exam_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("sms_exam.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    section_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("class_section.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    room_number: Optional[str] = Field(default=None, sa_column=Column(String(50), nullable=True))
    # Learnhouse user.id, matching ClassSection.class_teacher_id /
    # TimetableSchedule.teacher_id -- NOT StaffProfile.id. Every SMS table
    # that means "a member of staff" uses user.id directly.
    invigilator_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True, index=True))
    actual_start_at: Optional[datetime.datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    actual_end_at: Optional[datetime.datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    created_at: datetime.datetime = Field(
        default_factory=get_utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False, default=get_utc_now),
    )


class ExamResult(SQLModel, table=True):
    """One student's result for one exam.

    `marks_obtained` is deliberately NULLABLE. A student who has not been
    marked yet, or who was absent, has NO mark -- not a zero. This codebase
    has twice had to tear out endpoints that defaulted missing academic data
    to a plausible-looking number, so absence is represented as absence and
    every reader must handle None.

    `posted_to_gradebook_at` is the idempotency guard: posting results writes
    GradebookEntry rows, and this timestamp is what stops a second post from
    double-writing.
    """
    __tablename__ = "sms_exam_result"
    __table_args__ = (
        UniqueConstraint("exam_id", "student_id", name="uq_sms_exam_student_result"),
        Index("ix_sms_exam_result_student", "student_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    exam_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("sms_exam.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    student_id: int = Field(sa_column=Column(Integer, nullable=False, index=True))
    marks_obtained: Optional[float] = Field(default=None, sa_column=Column(Float, nullable=True))
    attendance_status: ExamAttendanceStatus = Field(
        default=ExamAttendanceStatus.PRESENT,
        sa_column=Column(
            String(20), nullable=False, default=ExamAttendanceStatus.PRESENT.value
        ),
    )
    remarks: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    marked_by: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))
    marked_at: Optional[datetime.datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    posted_to_gradebook_at: Optional[datetime.datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )


class ExamIncident(SQLModel, table=True):
    """An invigilator's written record of something that happened in the room.

    This is the honest extent of "proctoring" here: a human writes down what
    they saw. There is no automated detection of anything. Rows are additive
    and never edited away -- an incident log that can be quietly rewritten is
    not a record.
    """
    __tablename__ = "sms_exam_incident"
    __table_args__ = (
        Index("ix_sms_exam_incident_exam", "exam_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    exam_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("sms_exam.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    section_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True, index=True))
    student_id: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, nullable=True, index=True),
        description="Null when the incident concerns the room rather than one student",
    )
    severity: str = Field(default="INFO", sa_column=Column(String(20), nullable=False))
    description: str = Field(sa_column=Column(Text, nullable=False))
    reported_by: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))
    reported_at: datetime.datetime = Field(
        default_factory=get_utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False, default=get_utc_now),
    )


class AssignmentHintUsage(SQLModel, table=True):
    """Socratic-tutor hints a student consumed on one assignment (M40).

    WHY THIS TABLE IS THE SOURCE OF TRUTH FOR THE DEDUCTION, NOT THE GRADE:
    the tutor issues hints continuously while a student works, long before
    anyone grades anything. Writing a running deduction into the gradebook as
    hints accrue would mean mutating a score that does not exist yet, and
    would make the gradebook disagree with itself between hint and grading.

    So hint COUNT accrues here, and the deduction is computed and applied once
    at grading time. `deduction_applied_at` plus `applied_to_gradebook_entry_id`
    make that application idempotent: re-grading recomputes from the raw score
    rather than deducting a second time from an already-reduced one.
    """
    __tablename__ = "sms_assignment_hint_usage"
    __table_args__ = (
        UniqueConstraint("student_id", "assignment_ref", name="uq_sms_hint_student_assignment"),
        Index("ix_sms_hint_student", "student_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    student_id: int = Field(sa_column=Column(Integer, nullable=False, index=True))
    # Free-form reference to whatever the hint was about (an assignment uuid,
    # an assessment plan id as a string, a course activity uuid). Kept as a
    # string because the tutor is asked for help on things from more than one
    # subsystem, and a hard FK to any single one would be wrong for the others.
    assignment_ref: str = Field(sa_column=Column(String(255), nullable=False, index=True))
    assessment_plan_id: Optional[int] = Field(
        default=None,
        sa_column=Column(
            Integer,
            ForeignKey("sms_assessment_plan.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
    )
    hints_used: int = Field(default=0, sa_column=Column(Integer, nullable=False, default=0))
    # Highest hint_level reached, for reporting -- a level-3 "almost the
    # answer" hint is not equivalent to three level-1 nudges.
    max_hint_level: int = Field(default=0, sa_column=Column(Integer, nullable=False, default=0))
    deduction_applied_at: Optional[datetime.datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    applied_to_gradebook_entry_id: Optional[int] = Field(
        default=None, sa_column=Column(Integer, nullable=True)
    )
    applied_deduction_percentage: Optional[float] = Field(
        default=None, sa_column=Column(Float, nullable=True)
    )
    first_hint_at: datetime.datetime = Field(
        default_factory=get_utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False, default=get_utc_now),
    )
    last_hint_at: datetime.datetime = Field(
        default_factory=get_utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False, default=get_utc_now),
    )
