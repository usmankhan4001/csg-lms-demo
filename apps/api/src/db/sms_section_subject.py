"""
CSG-EMS Curricular Bridge: Section-Subject Database Model
=========================================================
Links Learnhouse LMS Courses with SMS Class Sections, assigning subject teachers,
credit hours, and academic year scopes for unified curricular progression and
automated gradebook synchronization.
"""

from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import Boolean, Column, Float, ForeignKey, Index, Integer, String
from sqlmodel import Field, SQLModel


def get_utc_now_iso() -> str:
    """Return current UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------
# Section Subject Models
# ---------------------------------------------------------

class SectionSubjectBase(SQLModel):
    """Base schema for Section-Subject curricular mapping."""
    section_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("class_section.id", ondelete="CASCADE"),
            index=True,
            nullable=False,
        ),
        description="Target SMS Class Section ID",
    )
    course_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("course.id", ondelete="CASCADE"),
            index=True,
            nullable=False,
        ),
        description="Linked Learnhouse Course ID",
    )
    teacher_id: Optional[int] = Field(
        default=None,
        sa_column=Column(
            Integer,
            ForeignKey("user.id", ondelete="SET NULL"),
            index=True,
            nullable=True,
        ),
        description="Assigned Subject Teacher (User ID)",
    )
    subject_name: str = Field(
        ...,
        sa_column=Column(String(150), nullable=False),
        description="Subject title (e.g., 'Physics', 'Advanced Mathematics')",
    )
    subject_code: Optional[str] = Field(
        default=None,
        sa_column=Column(String(50), nullable=True, index=True),
        description="Standardized Subject Code (e.g., 'PHY-101', 'MATH-202')",
    )
    academic_year_id: Optional[int] = Field(
        default=None,
        sa_column=Column(
            Integer,
            ForeignKey("academic_year.id", ondelete="CASCADE"),
            index=True,
            nullable=True,
        ),
        description="Associated Academic Year ID",
    )
    credit_hours: float = Field(
        default=1.0,
        sa_column=Column(Float, nullable=False, default=1.0),
        description="Academic credit hours value (default: 1.0)",
    )
    is_elective: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, default=False),
        description="Whether this subject is an elective course",
    )


class SectionSubject(SectionSubjectBase, table=True):
    """
    Database model representing the Curricular Bridge between
    SMS Class Sections and LMS Courses.
    """
    __tablename__ = "sms_section_subject"
    __table_args__ = (
        Index("ix_sms_sec_subj_sec_course", "section_id", "course_id"),
        Index("ix_sms_sec_subj_teacher", "teacher_id"),
        Index("ix_sms_sec_subj_year", "academic_year_id"),
        {"extend_existing": True},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: str = Field(default_factory=get_utc_now_iso)
    updated_at: str = Field(default_factory=get_utc_now_iso)


class SectionSubjectCreate(SQLModel):
    """Payload schema for creating a Section-Subject curricular bridge."""
    course_id: int
    subject_name: str
    section_id: Optional[int] = None
    teacher_id: Optional[int] = None
    subject_code: Optional[str] = None
    academic_year_id: Optional[int] = None
    credit_hours: float = 1.0
    is_elective: bool = False


class SectionSubjectUpdate(SQLModel):
    """Payload schema for updating a Section-Subject bridge."""
    course_id: Optional[int] = None
    teacher_id: Optional[int] = None
    subject_name: Optional[str] = None
    subject_code: Optional[str] = None
    academic_year_id: Optional[int] = None
    credit_hours: Optional[float] = None
    is_elective: Optional[bool] = None


class SectionSubjectRead(SectionSubjectBase):
    """Response schema for reading Section-Subject entities."""
    id: int
    created_at: str
    updated_at: str


class SectionSubjectReadDetailed(SectionSubjectRead):
    """Detailed response schema including course, section, and teacher metadata."""
    course_name: Optional[str] = None
    course_uuid: Optional[str] = None
    teacher_name: Optional[str] = None
    teacher_email: Optional[str] = None
    section_name: Optional[str] = None
    grade_level: Optional[str] = None
