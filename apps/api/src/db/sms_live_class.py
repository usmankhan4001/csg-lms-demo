import datetime
import enum
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
    Text,
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


class LiveClassStatus(str, enum.Enum):
    """Lifecycle of a scheduled class.

    `LiveClassSession.is_active` alone conflates "scheduled but not started"
    with "running right now", and cannot express a cancellation at all -- a
    cancelled class and a class that ran and ended both end up is_active=False,
    which a school genuinely needs to tell apart.
    """

    SCHEDULED = "SCHEDULED"
    LIVE = "LIVE"
    ENDED = "ENDED"
    CANCELLED = "CANCELLED"


class RecordingStatus(str, enum.Enum):
    """State of a class recording.

    UNAVAILABLE is distinct from FAILED on purpose: UNAVAILABLE means the
    deployment has no object storage configured, so recording was never
    possible; FAILED means it was attempted and did not work. Collapsing them
    would tell a teacher their recording broke when in fact nobody ever set up
    storage.
    """

    NOT_REQUESTED = "NOT_REQUESTED"
    UNAVAILABLE = "UNAVAILABLE"
    PENDING = "PENDING"
    RECORDING = "RECORDING"
    PROCESSING = "PROCESSING"
    READY = "READY"
    FAILED = "FAILED"


class LiveClassSessionDetail(SQLModel, table=True):
    """Scheduling and recording state for a live class.

    WHY A COMPANION TABLE RATHER THAN COLUMNS ON `LiveClassSession`:
    this project creates schema with `SQLModel.metadata.create_all`, which
    creates missing TABLES but never ALTERs an existing one to add a column.
    Agents have added columns to existing tables here before and the modules
    500'd in every environment that already had the table. A new additive
    table is the only change that actually lands.

    A session with no detail row is a legacy/ad-hoc room: it reads as not
    recording and not cancelled, which is the correct, safe interpretation.
    """

    __tablename__ = "sms_live_class_detail"
    __table_args__ = (
        UniqueConstraint("session_id", name="uq_lc_detail_session"),
        # Custom names deliberately unlike SQLAlchemy's auto-generated
        # `ix_<table>_<column>`: declaring an Index() here AND index=True on
        # the same column makes create_all emit CREATE INDEX twice, and the
        # API fails to boot. No column below uses index=True.
        Index("ix_lc_detail_status", "status"),
        Index("ix_lc_detail_recording_status", "recording_status"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("sms_live_class_session.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    description: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    status: str = Field(
        default=LiveClassStatus.SCHEDULED.value,
        sa_column=Column(String(20), nullable=False, default=LiveClassStatus.SCHEDULED.value),
    )
    cancelled_reason: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    cancelled_by_user_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))
    cancelled_at: Optional[datetime.datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )

    # Recording is OPT-IN. These are classes full of children; an opt-out
    # default would mean a teacher who never thought about it records them.
    recording_enabled: bool = Field(
        default=False, sa_column=Column(Boolean, nullable=False, default=False)
    )
    # And a finished recording is NOT visible to students until the teacher
    # deliberately shares it.
    recording_shared_with_students: bool = Field(
        default=False, sa_column=Column(Boolean, nullable=False, default=False)
    )
    recording_status: str = Field(
        default=RecordingStatus.NOT_REQUESTED.value,
        sa_column=Column(String(20), nullable=False, default=RecordingStatus.NOT_REQUESTED.value),
    )
    # Why a recording is unavailable or failed, shown to the teacher verbatim.
    # Never a fabricated success.
    recording_note: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    egress_id: Optional[str] = Field(default=None, sa_column=Column(String(120), nullable=True))
    # Where the file was written in object storage. Kept separate from
    # `recording_note` (which is prose shown to a teacher) so neither has to
    # double as the other.
    recording_object_key: Optional[str] = Field(
        default=None, sa_column=Column(String(500), nullable=True)
    )
    recording_started_at: Optional[datetime.datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    recording_completed_at: Optional[datetime.datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    recording_duration_seconds: Optional[float] = Field(
        default=None, sa_column=Column(Float, nullable=True)
    )

    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.datetime.now(datetime.timezone.utc),
        ),
    )


class LiveClassCoursework(SQLModel, table=True):
    """An existing course activity attached to a live class.

    Stores only a reference to Learnhouse's own `activity` row -- no parallel
    content type. The class is a place where existing coursework is used, not
    a second place where coursework is authored.
    """

    __tablename__ = "sms_live_class_coursework"
    __table_args__ = (
        UniqueConstraint("session_id", "activity_id", name="uq_lc_coursework_once"),
        Index("ix_lc_coursework_session", "session_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("sms_live_class_session.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    activity_id: int = Field(sa_column=Column(Integer, nullable=False))
    attached_by_user_id: int = Field(sa_column=Column(Integer, nullable=False))
    note: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.datetime.now(datetime.timezone.utc),
        ),
    )
