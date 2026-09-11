import datetime
from typing import Optional
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlmodel import Field, SQLModel


class LiveClassSession(SQLModel, table=True):
    """
    Virtual live classroom session linked to a section, course, or teacher.
    """
    __tablename__ = "sms_live_class_session"
    __table_args__ = (
        UniqueConstraint("room_name", name="uq_sms_live_room_name"),
        Index("ix_sms_live_session_section", "section_id"),
        Index("ix_sms_live_session_course", "course_id"),
        Index("ix_sms_live_session_teacher", "teacher_id"),
        Index("ix_sms_live_session_active", "is_active"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    section_id: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, nullable=True, index=True)
    )
    course_id: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, nullable=True, index=True)
    )
    teacher_id: int = Field(
        sa_column=Column(Integer, nullable=False, index=True)
    )
    title: str = Field(
        sa_column=Column(String(200), nullable=False)
    )
    room_name: str = Field(
        sa_column=Column(String(100), nullable=False, unique=True, index=True)
    )
    start_time: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.datetime.now(datetime.timezone.utc),
        ),
    )
    end_time: Optional[datetime.datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    is_active: bool = Field(
        default=True,
        sa_column=Column(Boolean, nullable=False, default=True)
    )
    recording_url: Optional[str] = Field(
        default=None,
        sa_column=Column(String(500), nullable=True)
    )
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.datetime.now(datetime.timezone.utc),
        ),
    )


class LiveClassAttendanceLog(SQLModel, table=True):
    """
    Detailed log of student entry and exit for attendance reporting in live virtual classes.
    """
    __tablename__ = "sms_live_class_attendance"
    __table_args__ = (
        Index("ix_sms_live_att_session", "session_id"),
        Index("ix_sms_live_att_student", "student_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("sms_live_class_session.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    student_id: int = Field(
        sa_column=Column(Integer, nullable=False, index=True)
    )
    joined_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.datetime.now(datetime.timezone.utc),
        ),
    )
    left_at: Optional[datetime.datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    duration_minutes: Optional[float] = Field(
        default=0.0,
        sa_column=Column(Float, nullable=True, default=0.0)
    )
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.datetime.now(datetime.timezone.utc),
        ),
    )
