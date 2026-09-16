import datetime
from typing import Optional
from enum import Enum
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


class DayOfWeek(str, Enum):
    """Day of week enumeration for timetable scheduling."""
    MONDAY = "MONDAY"
    TUESDAY = "TUESDAY"
    WEDNESDAY = "WEDNESDAY"
    THURSDAY = "THURSDAY"
    FRIDAY = "FRIDAY"
    SATURDAY = "SATURDAY"
    SUNDAY = "SUNDAY"


class ClassPeriod(SQLModel, table=True):
    """
    Represents bell schedule / class periods for a school/campus.
    """
    __tablename__ = "sms_class_period"
    __table_args__ = (
        Index("ix_sms_period_campus_number", "campus_id", "period_number"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    campus_id: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, nullable=True, index=True)
    )
    period_number: int = Field(
        sa_column=Column(Integer, nullable=False, index=True)
    )
    start_time: str = Field(
        sa_column=Column(String(20), nullable=False)
    )  # e.g., "08:30:00" or "08:30"
    end_time: str = Field(
        sa_column=Column(String(20), nullable=False)
    )  # e.g., "09:15:00" or "09:15"
    name: Optional[str] = Field(
        default=None,
        sa_column=Column(String(100), nullable=True)
    )


class TimetableSchedule(SQLModel, table=True):
    """
    Represents a single slot in the institutional timetable.
    
    Contains relational linkages to section, course, teacher, day of week,
    period, room, and academic term.
    """
    __tablename__ = "sms_timetable_schedule"
    __table_args__ = (
        # Teacher clash index
        Index(
            "ix_sms_tt_teacher_slot",
            "teacher_id",
            "day_of_week",
            "period_id",
            "academic_term_id",
        ),
        # Room clash index
        Index(
            "ix_sms_tt_room_slot",
            "room_number",
            "day_of_week",
            "period_id",
            "academic_term_id",
        ),
        # Section clash index
        Index(
            "ix_sms_tt_section_slot",
            "section_id",
            "day_of_week",
            "period_id",
            "academic_term_id",
        ),
        # ── Uniqueness, not just lookup ──
        # A teacher cannot stand in front of two sections in one period, and a
        # section cannot attend two lessons at once. Enforced here rather than
        # only in the service because the service check is a read-then-write:
        # two concurrent creates both see an empty slot and both insert.
        #
        # `academic_term_id` is nullable and NULL != NULL in SQL, so a single
        # unique index would let unlimited duplicates through wherever the term
        # is unset -- which is every school that does not run terms. Two
        # partial indexes per key cover it: one for term-scoped rows, one for
        # the term-less ones.
        Index(
            "uq_sms_tt_teacher_slot_term",
            "teacher_id",
            "day_of_week",
            "period_id",
            "academic_term_id",
            unique=True,
            postgresql_where=text("academic_term_id IS NOT NULL"),
            sqlite_where=text("academic_term_id IS NOT NULL"),
        ),
        Index(
            "uq_sms_tt_teacher_slot_no_term",
            "teacher_id",
            "day_of_week",
            "period_id",
            unique=True,
            postgresql_where=text("academic_term_id IS NULL"),
            sqlite_where=text("academic_term_id IS NULL"),
        ),
        Index(
            "uq_sms_tt_section_slot_term",
            "section_id",
            "day_of_week",
            "period_id",
            "academic_term_id",
            unique=True,
            postgresql_where=text("academic_term_id IS NOT NULL"),
            sqlite_where=text("academic_term_id IS NOT NULL"),
        ),
        Index(
            "uq_sms_tt_section_slot_no_term",
            "section_id",
            "day_of_week",
            "period_id",
            unique=True,
            postgresql_where=text("academic_term_id IS NULL"),
            sqlite_where=text("academic_term_id IS NULL"),
        ),
        # Room is deliberately NOT constrained here. `room_number` is free
        # text, and a slot carries no campus of its own (it reaches one only
        # through period_id), so a unique index over it would reject "Room 1"
        # at two different campuses in the same period -- a false clash -- while
        # still missing "Room 1" against "room 1" at the same one, because the
        # service compares case- and whitespace-insensitively and an index
        # cannot. Room double-booking stays a service-level check.
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    section_id: int = Field(
        sa_column=Column(Integer, nullable=False, index=True)
    )
    course_id: int = Field(
        sa_column=Column(Integer, nullable=False, index=True)
    )
    teacher_id: int = Field(
        sa_column=Column(Integer, nullable=False, index=True)
    )
    day_of_week: str = Field(
        sa_column=Column(String(20), nullable=False, index=True)
    )  # e.g. "MONDAY"
    period_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("sms_class_period.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    room_number: Optional[str] = Field(
        default=None,
        sa_column=Column(String(50), nullable=True, index=True)
    )
    academic_term_id: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, nullable=True, index=True)
    )


class TimetableSubstitution(SQLModel, table=True):
    """
    A substitute teacher covering one recurring timetable slot on ONE
    specific calendar date (a sick day, training, leave).

    Deliberately a separate row rather than mutating
    `TimetableSchedule.teacher_id`: schedules here are RECURRING (day_of_week
    + period), so overwriting the teacher would silently reassign the slot
    for every future week, and the original teacher could not be restored.
    Keeping the override date-scoped and additive means the permanent
    timetable stays the source of truth and a substitution can simply be
    cancelled.

    `is_active` rather than row deletion, so a cancelled substitution stays
    auditable (who was asked to cover, and that it was called off).
    """
    __tablename__ = "sms_timetable_substitution"
    __table_args__ = (
        # One active substitution per slot per date is enforced in the
        # service layer (it must ignore cancelled rows, which a DB unique
        # constraint spanning is_active cannot express cleanly).
        Index("ix_sms_tt_sub_schedule_date", "schedule_id", "substitution_date"),
        Index("ix_sms_tt_sub_substitute_date", "substitute_teacher_id", "substitution_date"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    schedule_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("sms_timetable_schedule.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    substitution_date: str = Field(
        sa_column=Column(String(10), nullable=False, index=True)
    )  # ISO 'YYYY-MM-DD'; string-dated to match AcademicTerm's existing convention
    original_teacher_id: int = Field(
        sa_column=Column(Integer, nullable=False, index=True)
    )
    substitute_teacher_id: int = Field(
        sa_column=Column(Integer, nullable=False, index=True)
    )
    reason: Optional[str] = Field(
        default=None,
        sa_column=Column(String(255), nullable=True)
    )
    created_by: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, nullable=True)
    )
    is_active: bool = Field(
        default=True,
        sa_column=Column(Boolean, nullable=False, default=True, index=True)
    )


class TimetableLessonLog(SQLModel, table=True):
    """A record of what was ACTUALLY taught in one timetable slot on one date.

    Deliberately distinct from `LessonPlan` (src/db/sms_teacher_tools.py),
    which is an AI-authored plan of what a teacher INTENDS to cover and is not
    attached to any slot or date. A plan is written before the lesson and may
    never be followed; a log is written after it and is what the next person
    standing in front of that class needs. They are also keyed differently --
    `LessonPlan.teacher_id` is a Keycloak `sub` string, while every timetable
    table keys the teacher on the integer Learnhouse user id -- so they cannot
    simply be merged. `lesson_plan_id` links the two when a plan was used.

    This is THE answer to "what was taught last lesson", which a substitute
    teacher covering an unfamiliar class has no other way to find out.

    Date-scoped against a RECURRING slot, for the same reason
    `TimetableSubstitution` is: a timetable row describes every Tuesday, so a
    log written onto the slot itself would claim to be true of all of them.
    """
    __tablename__ = "sms_timetable_lesson_log"
    __table_args__ = (
        # One log per slot per date is enforced read-before-write in the
        # service, which also lets a teacher correct a log they already wrote.
        Index("ix_sms_tt_lesson_schedule_date", "schedule_id", "lesson_date"),
        # "What did this section do recently?" -- the substitute's question.
        Index("ix_sms_tt_lesson_section_date", "section_id", "lesson_date"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    schedule_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("sms_timetable_schedule.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    # Denormalised from the slot so a substitute can ask "what has 9A been
    # doing?" without first knowing which slot ids belong to that section, and
    # so the log survives a timetable being rebuilt around it.
    section_id: int = Field(
        sa_column=Column(Integer, nullable=False, index=True)
    )
    lesson_date: str = Field(
        sa_column=Column(String(10), nullable=False, index=True)
    )  # ISO 'YYYY-MM-DD', matching TimetableSubstitution's convention
    # The teacher who actually took the lesson -- which on a covered day is the
    # SUBSTITUTE, not the slot's permanent teacher.
    taught_by_user_id: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, nullable=True, index=True)
    )
    topic_covered: str = Field(
        sa_column=Column(Text, nullable=False)
    )
    homework_set: Optional[str] = Field(
        default=None,
        sa_column=Column(Text, nullable=True)
    )
    # The handover note. Named for its purpose so it is not quietly reused as
    # a private teacher scratchpad: whoever covers this class next reads it.
    notes_for_next_teacher: Optional[str] = Field(
        default=None,
        sa_column=Column(Text, nullable=True)
    )
    lesson_plan_id: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, nullable=True, index=True)
    )
    recorded_by_user_id: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, nullable=True)
    )
    created_at: datetime.datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False, default=_utcnow),
    )
    updated_at: Optional[datetime.datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
