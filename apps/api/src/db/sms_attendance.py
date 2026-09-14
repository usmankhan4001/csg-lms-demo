import datetime
from typing import Optional
from enum import Enum
from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlmodel import Field, SQLModel


class AttendanceStatus(str, Enum):
    """Status enumeration for student attendance records."""
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"
    LATE = "LATE"
    EXCUSED = "EXCUSED"


class LeaveRequestStatus(str, Enum):
    """Status enumeration for student leave requests."""
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class StudentAttendance(SQLModel, table=True):
    """
    Records roll-call attendance per student, for a section, on a date, and
    -- optionally -- for one class period within that date.

    Ported from Frappe Education & RosarioSIS student attendance ledger.

    TWO REGISTER MODELS, BOTH FIRST-CLASS
    -------------------------------------
    `period_id IS NULL` is a DAY-level register: one row per student per day,
    which is how a primary school (and this table, historically) works.

    `period_id` set is a PERIOD-level register: one row per student per
    period, which is what a secondary school running 6-8 periods needs.
    Before this column existed the unique key was
    (student_id, section_id, date), so taking period 5's register silently
    OVERWROTE period 1's -- a student absent first thing and present after
    lunch ended the day looking present, with no warning and no history.
    `ClassPeriod`/`TimetableSchedule` were already period-aware; attendance
    simply had never been wired to them.

    A school picks one model and stays with it. Nothing here forbids mixing
    them, but a section with both a day row and period rows for the same date
    will double-count in any naive record count, so the readers in
    services/sms/attendance.py collapse per DATE rather than per row.

    NOTE ON UNIQUENESS. The constraint below genuinely protects the
    period-level case. It does NOT protect the day-level case, because
    `period_id` is nullable and NULL != NULL in SQL -- on PostgreSQL two rows
    with the same (student, section, date) and a NULL period both satisfy it.
    Partial unique indexes would fix that but differ between PostgreSQL (prod)
    and the SQLite used in tests, so day-level uniqueness is enforced by
    reading before writing in routers/sms_attendance.py, the same approach
    db/sms_settings.py takes for its nullable campus_id.
    """
    __tablename__ = "sms_student_attendance"
    __table_args__ = (
        UniqueConstraint(
            "student_id", "section_id", "date", "period_id",
            name="uq_sms_student_section_date_period"
        ),
        Index("ix_sms_att_section_date", "section_id", "date"),
        Index("ix_sms_att_student_date", "student_id", "date"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    student_id: int = Field(
        sa_column=Column(Integer, nullable=False, index=True)
    )
    section_id: int = Field(
        sa_column=Column(Integer, nullable=False, index=True)
    )
    date: datetime.date = Field(
        sa_column=Column(Date, nullable=False, index=True)
    )
    # NULL = a whole-day register (see the class docstring).
    #
    # RESTRICT, deliberately, where TimetableSchedule.period_id uses CASCADE.
    # A timetable slot is a PLAN and may be deleted with its period; an
    # attendance row is a RECORD OF WHAT HAPPENED and must outlive the bell
    # schedule. CASCADE would destroy a legal record, and SET NULL would be
    # worse than either: it would silently reclassify period rows as day rows
    # and could leave several indistinguishable "day" rows for one date.
    period_id: Optional[int] = Field(
        default=None,
        sa_column=Column(
            Integer,
            ForeignKey("sms_class_period.id", ondelete="RESTRICT"),
            nullable=True,
            index=True,
        ),
    )
    status: AttendanceStatus = Field(
        default=AttendanceStatus.PRESENT,
        sa_column=Column(
            SAEnum(AttendanceStatus, name="sms_attendance_status", native_enum=False),
            nullable=False,
            default=AttendanceStatus.PRESENT,
        ),
    )
    marked_by: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, nullable=True, index=True)
    )
    remarks: Optional[str] = Field(
        default=None,
        sa_column=Column(Text, nullable=True)
    )
    timestamp: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.datetime.now(datetime.timezone.utc),
        ),
    )


class AttendanceLeaveRequest(SQLModel, table=True):
    """
    Leave requests submitted by or on behalf of students.
    """
    __tablename__ = "sms_attendance_leave_request"
    __table_args__ = (
        Index("ix_sms_leave_student_dates", "student_id", "start_date", "end_date"),
        Index("ix_sms_leave_status", "status"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    student_id: int = Field(
        sa_column=Column(Integer, nullable=False, index=True)
    )
    start_date: datetime.date = Field(
        sa_column=Column(Date, nullable=False, index=True)
    )
    end_date: datetime.date = Field(
        sa_column=Column(Date, nullable=False, index=True)
    )
    reason: Optional[str] = Field(
        default=None,
        sa_column=Column(Text, nullable=True)
    )
    status: LeaveRequestStatus = Field(
        default=LeaveRequestStatus.PENDING,
        sa_column=Column(
            SAEnum(LeaveRequestStatus, name="sms_leave_request_status", native_enum=False),
            nullable=False,
            default=LeaveRequestStatus.PENDING,
        ),
    )
    approved_by: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, nullable=True, index=True)
    )
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.datetime.now(datetime.timezone.utc),
        ),
    )


class AttendanceChangeAction(str, Enum):
    """Distinguishes the first marking from every later correction.

    ``MARKED`` is the first record ever written for a student on a date (and
    period); ``CORRECTED`` is every subsequent overwrite. They must stay
    distinguishable: "first marked absent" and "was present, now absent" are
    different facts when a family disputes a register.
    """

    MARKED = "marked"
    CORRECTED = "corrected"


class AttendanceChangeEvent(SQLModel, table=True):
    """Append-only audit trail for every attendance record written.

    WHY THIS EXISTS, stated precisely because the original brief overstated it:
    ``StudentAttendance.timestamp`` is NOT overwritten on update -- there is no
    ``onupdate`` on the column and the roll-call handler never assigns it -- so
    the original marking time survives a correction. Verified directly rather
    than assumed.

    The real gap is narrower and still serious: nothing recorded WHAT changed,
    WHO changed it, or WHEN the correction happened. A register could be
    silently rewritten weeks later and the only trace was a status field that
    had quietly become something else. For a record a school may have to
    defend to an inspector or a court, that is the wrong trade.

    EDITABLE-WITH-HISTORY, NOT LOCKED-SHUT. Teachers genuinely misclick and
    late corrections are legitimate (a note arrives, a child was in the nurse's
    office). Freezing the register would push those corrections into paper and
    email, where they are invisible. Instead every write is recorded, so a
    correction is cheap, honest and attributable.

    Mirrors ``GradeChangeEvent`` (db/sms_gradebook.py) deliberately -- same
    shape, same reasoning -- rather than inventing a second audit idiom for the
    same problem. In particular the identifying columns are plain integers and
    student/section/date are SNAPSHOTTED rather than joined, so the trail stays
    legible after the attendance row, section or period is deleted.

    APPEND-ONLY: nothing updates or deletes these rows and no endpoint exposes
    a way to. A trail that can be rewritten is not a trail.
    """

    __tablename__ = "sms_attendance_change_event"
    __table_args__ = (
        Index("ix_sms_att_change_record", "attendance_id", "created_at"),
        Index("ix_sms_att_change_student", "student_id", "created_at"),
        Index("ix_sms_att_change_section_date", "section_id", "date"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)

    # The live row this describes. A plain Integer, not an FK: see docstring.
    attendance_id: int = Field(sa_column=Column(Integer, nullable=False))

    # Snapshots, so the trail survives deletion of what it points at.
    student_id: int = Field(sa_column=Column(Integer, nullable=False))
    section_id: int = Field(sa_column=Column(Integer, nullable=False))
    date: datetime.date = Field(sa_column=Column(Date, nullable=False))
    period_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))

    action: AttendanceChangeAction = Field(
        sa_column=Column(
            SAEnum(
                AttendanceChangeAction,
                name="sms_attendance_change_action",
                native_enum=False,
            ),
            nullable=False,
        )
    )

    # None on MARKED -- there was no previous status. Distinct from PRESENT,
    # which is a real status a student can be given.
    previous_status: Optional[AttendanceStatus] = Field(
        default=None,
        sa_column=Column(
            SAEnum(AttendanceStatus, name="sms_attendance_status", native_enum=False),
            nullable=True,
        ),
    )
    new_status: AttendanceStatus = Field(
        sa_column=Column(
            SAEnum(AttendanceStatus, name="sms_attendance_status", native_enum=False),
            nullable=False,
        )
    )

    # The AUTHENTICATED caller, never a client-supplied `marked_by` -- that
    # field is forgeable and is recorded separately on the live row. Nullable
    # only because a principal may carry no resolvable Learnhouse user id; an
    # unattributed row still beats no row, and reads as "unknown" rather than
    # as somebody else.
    changed_by_user_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))
    reason: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))

    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.datetime.now(datetime.timezone.utc),
        ),
    )


class ExcuseStatus(str, Enum):
    """Lifecycle of a parent's absence note."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class AbsenceExcuse(SQLModel, table=True):
    """A note explaining an absence that has ALREADY happened.

    Distinct from ``AttendanceLeaveRequest``, which is planned leave requested
    in advance ("we are travelling next week"). This is the far more common
    case a school handles every morning: "my child was ill on Tuesday", sent
    after the register was already marked ABSENT.

    Before this, those notes had nowhere to go. A parent wrote one, a teacher
    read it, and the child's attendance percentage still said absent.

    Scoped to ONE date rather than a range, deliberately. A range invites a
    single note to silently rewrite a fortnight of registers; one note per day
    keeps each conversion individually visible and individually approvable.
    """

    __tablename__ = "sms_absence_excuse"
    __table_args__ = (
        Index("ix_sms_excuse_student_date", "student_id", "date"),
        Index("ix_sms_excuse_status", "status"),
        Index("ix_sms_excuse_section_date", "section_id", "date"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    student_id: int = Field(sa_column=Column(Integer, nullable=False, index=True))
    section_id: int = Field(sa_column=Column(Integer, nullable=False, index=True))
    date: datetime.date = Field(sa_column=Column(Date, nullable=False, index=True))

    reason: str = Field(sa_column=Column(Text, nullable=False))
    # Who filed it -- a parent, or staff entering a paper note on their behalf.
    submitted_by_user_id: Optional[int] = Field(
        default=None, sa_column=Column(Integer, nullable=True)
    )

    status: ExcuseStatus = Field(
        default=ExcuseStatus.PENDING,
        sa_column=Column(
            SAEnum(ExcuseStatus, name="sms_excuse_status", native_enum=False),
            nullable=False,
            default=ExcuseStatus.PENDING,
        ),
    )
    # The AUTHENTICATED reviewer, never client-supplied.
    reviewed_by_user_id: Optional[int] = Field(
        default=None, sa_column=Column(Integer, nullable=True)
    )
    review_note: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    reviewed_at: Optional[datetime.datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )

    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.datetime.now(datetime.timezone.utc),
        ),
    )


class PastoralConcernStatus(str, Enum):
    """Where a pastoral concern has got to."""

    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"


class PastoralConcern(SQLModel, table=True):
    """A student flagged as at risk, and what the school did about it.

    THE GAP THIS FILLS. ``check_and_emit_absence_streak`` already works: it
    detects a run of absences and emits an event whose only subscriber emails
    the guardians. With mail unconfigured -- the default -- that detection
    fires into a void. Nobody is told, nothing is recorded, and no screen
    anywhere shows which children are currently at risk.

    So the hard part was already built and had no destination. This is the
    destination: a durable row per concern, with interventions recorded
    against it, so "who is at risk right now, why, and what has been done" is
    answerable.

    Deliberately NOT auto-resolved by a student returning to school. A child
    who missed four days and came back still warrants a conversation; closing
    the concern silently would erase the only prompt for it. A human resolves
    it, and says what happened.
    """

    __tablename__ = "sms_pastoral_concern"
    __table_args__ = (
        Index("ix_sms_pastoral_student", "student_id", "created_at"),
        Index("ix_sms_pastoral_section_status", "section_id", "status"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    student_id: int = Field(sa_column=Column(Integer, nullable=False, index=True))
    section_id: int = Field(sa_column=Column(Integer, nullable=False, index=True))

    # What triggered it, e.g. "absence_streak". A plain string rather than an
    # enum so a future detector (falling grades, a safeguarding referral) can
    # raise a concern without a schema change.
    trigger: str = Field(sa_column=Column(String(64), nullable=False))
    # Human-readable specifics, e.g. "Absent 4 consecutive days". Never a
    # fabricated figure: written from a real computed streak.
    detail: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    # The streak length (or other magnitude) when raised. None where the
    # trigger has no natural magnitude -- not 0, which reads as "a streak of
    # zero".
    magnitude: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))

    status: PastoralConcernStatus = Field(
        default=PastoralConcernStatus.OPEN,
        sa_column=Column(
            SAEnum(
                PastoralConcernStatus,
                name="sms_pastoral_concern_status",
                native_enum=False,
            ),
            nullable=False,
            default=PastoralConcernStatus.OPEN,
        ),
    )
    resolved_by_user_id: Optional[int] = Field(
        default=None, sa_column=Column(Integer, nullable=True)
    )
    resolution_note: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    resolved_at: Optional[datetime.datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )

    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.datetime.now(datetime.timezone.utc),
        ),
    )


class PastoralIntervention(SQLModel, table=True):
    """Something a member of staff actually did about a concern.

    Append-only by construction: an intervention records an action that
    happened at a point in time, so editing one would be rewriting history. To
    correct a mistake, add another.
    """

    __tablename__ = "sms_pastoral_intervention"
    __table_args__ = (
        Index("ix_sms_pastoral_int_concern", "concern_id", "created_at"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    concern_id: int = Field(sa_column=Column(Integer, nullable=False, index=True))

    # e.g. "called_guardian", "meeting", "referred_to_counsellor".
    action: str = Field(sa_column=Column(String(64), nullable=False))
    note: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    outcome: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))

    # The AUTHENTICATED actor.
    acted_by_user_id: Optional[int] = Field(
        default=None, sa_column=Column(Integer, nullable=True)
    )
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.datetime.now(datetime.timezone.utc),
        ),
    )
