from typing import Optional
from enum import Enum
from sqlalchemy import (
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlmodel import Field, SQLModel


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
