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
