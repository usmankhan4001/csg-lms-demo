import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlmodel import Field, SQLModel


class GradingScale(SQLModel, table=True):
    """
    Institutional grading scale defining grade bands and GPA point conversions.
    """
    __tablename__ = "sms_grading_scale"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(sa_column=Column(String(100), nullable=False, unique=True))
    description: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    intervals: List[Dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    is_default: bool = Field(default=False)


class AssessmentPlan(SQLModel, table=True):
    """
    Assessment weighting structure for a course/section (e.g. Midterm 30%, Final 50%, Quizzes 20%).
    """
    __tablename__ = "sms_assessment_plan"
    __table_args__ = (
        Index("ix_sms_assessment_course_term", "course_id", "academic_term_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    course_id: int = Field(sa_column=Column(Integer, nullable=False, index=True))
    section_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True, index=True))
    academic_term_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True, index=True))
    assessment_name: str = Field(sa_column=Column(String(150), nullable=False))
    weight_percentage: float = Field(sa_column=Column(Float, nullable=False))  # e.g., 30.0 for 30%
    max_score: float = Field(default=100.0, sa_column=Column(Float, nullable=False))


class GradebookEntry(SQLModel, table=True):
    """
    Individual student score entry for an assessment plan item.
    """
    __tablename__ = "sms_gradebook_entry"
    __table_args__ = (
        UniqueConstraint("student_id", "assessment_plan_id", name="uq_sms_student_assessment"),
        Index("ix_sms_grade_student", "student_id"),
        Index("ix_sms_grade_assessment", "assessment_plan_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    student_id: int = Field(sa_column=Column(Integer, nullable=False, index=True))
    assessment_plan_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("sms_assessment_plan.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    raw_score: float = Field(sa_column=Column(Float, nullable=False))
    max_score: float = Field(sa_column=Column(Float, nullable=False))
    weighted_score: Optional[float] = Field(default=None, sa_column=Column(Float, nullable=True))
    letter_grade: Optional[str] = Field(default=None, sa_column=Column(String(10), nullable=True))
    gpa_point: Optional[float] = Field(default=None, sa_column=Column(Float, nullable=True))
    remarks: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    graded_by: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))
    graded_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.datetime.now(datetime.timezone.utc),
        ),
    )


class ReportCardStatus:
    """Explicit draft->sent lifecycle for TermReportCard (plain string constants,
    not an Enum, so the JSON-facing status column stays a simple SQLModel str
    field -- matches the style of `letter_grade`/other free-text columns in
    this file rather than introducing a DB-level enum type).

    Product decision (Phase 4): the TEACHER approves and explicitly sends a
    report card -- it never auto-sends, and there is no separate
    SCHOOL_ADMIN approval gate. A report card is visible to the PARENT role
    only once it is SENT; while DRAFT it is teacher/admin-only.
    """
    DRAFT = "draft"
    SENT = "sent"


class TermReportCard(SQLModel, table=True):
    """
    Aggregated end-of-term student report card summary with GPA and credits.

    ``status``/``ai_narrative``/``sent_at``/``sent_by`` implement the explicit
    draft -> sent report-card distribution lifecycle (Phase 4, Part A.4): a
    TEACHER generates a DRAFT (GPA/grade data here plus an AI-assisted
    narrative), may edit it, then explicitly sends it -- which is the only
    thing that makes it visible to the PARENT role. See
    src/services/sms/gradebook.py for the lifecycle functions and
    src/routers/sms_gradebook.py for the endpoints.
    """
    __tablename__ = "sms_term_report_card"
    __table_args__ = (
        UniqueConstraint("student_id", "academic_term_id", name="uq_sms_student_term_report"),
        Index("ix_sms_report_student_term", "student_id", "academic_term_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    student_id: int = Field(sa_column=Column(Integer, nullable=False, index=True))
    section_id: int = Field(sa_column=Column(Integer, nullable=False, index=True))
    academic_term_id: int = Field(sa_column=Column(Integer, nullable=False, index=True))
    total_credits: float = Field(default=0.0, sa_column=Column(Float, nullable=False))
    gpa: float = Field(default=0.0, sa_column=Column(Float, nullable=False))
    letter_grade: Optional[str] = Field(default=None, sa_column=Column(String(10), nullable=True))
    remarks: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    course_summaries: List[Dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    calculated_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.datetime.now(datetime.timezone.utc),
        ),
    )
    # --- Draft -> Sent distribution lifecycle (Phase 4, Part A.4) ---
    status: str = Field(
        default=ReportCardStatus.DRAFT,
        sa_column=Column(String(20), nullable=False, index=True),
    )
    ai_narrative: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    sent_at: Optional[datetime.datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    # Keycloak `sub` of the TEACHER who sent it -- a string, not a Learnhouse
    # user.id FK, since the sender is identified from the Keycloak principal
    # (see get_current_user_principal), not a Learnhouse-native user row.
    sent_by: Optional[str] = Field(default=None, sa_column=Column(String(255), nullable=True))


class GradeChangeAction:
    """How a GradeChangeEvent row came about.

    ``CREATED`` is the first mark ever recorded for a student on an assessment;
    ``CHANGED`` is every subsequent overwrite. They must stay distinguishable:
    "first marked 41" and "was 72, now 41" are different facts in a dispute.
    """

    CREATED = "created"
    CHANGED = "changed"


class GradeChangeEvent(SQLModel, table=True):
    """Append-only audit trail for every gradebook mark written.

    Why this exists: ``GradebookEntry`` is uniquely constrained on
    (student_id, assessment_plan_id) and is UPDATED IN PLACE, so a corrected
    mark destroys the previous one. ``graded_by``/``graded_at`` record only the
    CURRENT grader. An auditor, or a parent disputing "this was 72 last week",
    had no answer available anywhere in the system.

    Why a new table rather than reusing an existing audit facility:

    * ``UserAuditEvent`` (db/user_audit_events.py) says in its own docstring
      that it is deliberately scoped to LEARNER actions, and its ``user_id`` FK
      means "the learner who acted". A grade change is a STAFF action ABOUT a
      learner -- two distinct user ids -- so it would have to overload
      ``user_id`` and bury the previous score in the ``audit_metadata`` JSON
      blob, turning "show me every change to this mark" into an unindexed JSON
      scan.
    * ``SMSImpersonationEvent`` (db/sms_identity.py) is itself a narrow,
      purpose-built audit table in this domain -- precedent for this shape.
    * ``create_all`` creates missing TABLES but never ALTERs an existing one,
      so a new table lands everywhere automatically while new columns on
      ``sms_gradebook_entry`` would not.

    APPEND-ONLY: nothing in this codebase updates or deletes these rows, and no
    endpoint exposes a way to. A trail that can be rewritten is not a trail.

    The identifying columns are deliberately plain integers rather than foreign
    keys, and student/assessment/section are SNAPSHOTTED here rather than
    joined. ``GradebookEntry.assessment_plan_id`` is ``ondelete="CASCADE"``, so
    an FK-linked trail would be destroyed by deleting the assessment plan --
    exactly when the record matters most. Snapshot, do not join, is the
    standard audit-log shape for this reason.
    """

    __tablename__ = "sms_grade_change_event"
    __table_args__ = (
        Index("ix_sms_grade_change_entry", "gradebook_entry_id", "created_at"),
        Index("ix_sms_grade_change_student", "student_id", "created_at"),
        Index("ix_sms_grade_change_section", "section_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)

    # The live row this describes. A plain Integer, not an FK: see class docstring.
    gradebook_entry_id: int = Field(sa_column=Column(Integer, nullable=False))

    # Snapshots, so the trail stays legible after the entry or plan is deleted.
    student_id: int = Field(sa_column=Column(Integer, nullable=False))
    assessment_plan_id: int = Field(sa_column=Column(Integer, nullable=False))
    # Nullable because a course-wide assessment plan has no section.
    section_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))

    action: str = Field(sa_column=Column(String(16), nullable=False))

    # None on CREATED -- there was no previous mark. Distinct from 0.0, which
    # is a real score a student can be given.
    previous_raw_score: Optional[float] = Field(default=None, sa_column=Column(Float, nullable=True))
    new_raw_score: float = Field(sa_column=Column(Float, nullable=False))
    previous_letter_grade: Optional[str] = Field(
        default=None, sa_column=Column(String(10), nullable=True)
    )
    new_letter_grade: Optional[str] = Field(default=None, sa_column=Column(String(10), nullable=True))
    max_score: float = Field(sa_column=Column(Float, nullable=False))

    # The AUTHENTICATED caller, resolved from the principal -- never a
    # client-supplied `graded_by`, which was found forgeable and fixed in
    # routers/sms_gradebook.py. Nullable only because a principal may carry no
    # resolvable Learnhouse user id; an unattributed row is still better than
    # no row, and reads as "unknown" rather than as somebody else.
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
