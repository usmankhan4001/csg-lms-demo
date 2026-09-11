"""
CSG-LMS Multi-Campus & Academic Hierarchy Models
=================================================
This module defines database schemas for multi-campus isolation, academic calendars,
grade levels, class sections, and student enrollment tracking with PostgreSQL Row-Level Security
(RLS) compatibility and ISO 27001 audit compliance.
"""

from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import Column, ForeignKey, Index, Integer, String, Float, Boolean
from sqlmodel import Field, SQLModel


def get_utc_now_iso() -> str:
    """Return current UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------
# Campus Models
# ---------------------------------------------------------

class CampusBase(SQLModel):
    """Base schema for Campus entity."""
    name: str = Field(..., max_length=255, description="Official campus name")
    code: str = Field(..., max_length=50, description="Unique human-readable campus code (e.g. 'MAIN-01', 'ISB-NORTH')")
    address: Optional[str] = Field(default=None, description="Physical street address")
    timezone: str = Field(default="UTC", max_length=100, description="IANA timezone name (e.g. 'Asia/Karachi', 'America/New_York')")
    is_active: bool = Field(default=True, description="Whether this campus is currently operational")


class Campus(CampusBase, table=True):
    """Database model for Campus with multi-tenant org isolation."""
    __tablename__ = "campus"
    __table_args__ = (
        Index("ix_campus_org_code", "org_id", "code", unique=True),
        Index("ix_campus_org_active", "org_id", "is_active"),
        {"extend_existing": True},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    org_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("organization.id", ondelete="CASCADE"),
            index=True,
            nullable=False
        )
    )
    created_at: str = Field(default_factory=get_utc_now_iso)
    updated_at: str = Field(default_factory=get_utc_now_iso)


class CampusCreate(CampusBase):
    """Schema for creating a new Campus."""
    org_id: int


class CampusUpdate(SQLModel):
    """Schema for updating an existing Campus."""
    name: Optional[str] = None
    code: Optional[str] = None
    address: Optional[str] = None
    timezone: Optional[str] = None
    is_active: Optional[bool] = None


class CampusRead(CampusBase):
    """Schema for reading Campus entity."""
    id: int
    org_id: int
    created_at: str
    updated_at: str


# ---------------------------------------------------------
# Academic Year Models
# ---------------------------------------------------------

class AcademicYearBase(SQLModel):
    """Base schema for Academic Year entity."""
    name: str = Field(..., max_length=100, description="Academic year title (e.g. '2026-2027')")
    start_date: Optional[str] = Field(default=None, max_length=50, description="Session start date (YYYY-MM-DD)")
    end_date: Optional[str] = Field(default=None, max_length=50, description="Session end date (YYYY-MM-DD)")
    is_active: bool = Field(default=True, description="Whether this academic year is current/active")


class AcademicYear(AcademicYearBase, table=True):
    """Database model for Academic Year per campus."""
    __tablename__ = "academic_year"
    __table_args__ = (
        Index("ix_academic_year_campus_active", "campus_id", "is_active"),
        Index("ix_academic_year_campus_name", "campus_id", "name"),
        {"extend_existing": True},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    campus_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("campus.id", ondelete="CASCADE"),
            index=True,
            nullable=False
        )
    )
    created_at: str = Field(default_factory=get_utc_now_iso)


class AcademicYearCreate(AcademicYearBase):
    """Schema for creating an Academic Year."""
    campus_id: int


class AcademicYearUpdate(SQLModel):
    """Schema for updating an Academic Year."""
    name: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    is_active: Optional[bool] = None


class AcademicYearRead(AcademicYearBase):
    """Schema for reading Academic Year."""
    id: int
    campus_id: int
    created_at: str


# ---------------------------------------------------------
# Academic Term Models
# ---------------------------------------------------------

class AcademicTermBase(SQLModel):
    """Base schema for Academic Term (Semester / Trimester / Quarter)."""
    name: str = Field(..., max_length=100, description="Term title (e.g. 'Fall Semester', 'Term 1')")
    term_code: Optional[str] = Field(default=None, max_length=50, description="Term code (e.g. 'T1', 'SEM-1')")
    weight_percentage: float = Field(default=100.0, description="Grade weighting contribution percentage (0.0 to 100.0)")
    start_date: Optional[str] = Field(default=None, max_length=50, description="Term start date (YYYY-MM-DD)")
    end_date: Optional[str] = Field(default=None, max_length=50, description="Term end date (YYYY-MM-DD)")


class AcademicTerm(AcademicTermBase, table=True):
    """Database model for Academic Term within an Academic Year."""
    __tablename__ = "academic_term"
    __table_args__ = (
        Index("ix_academic_term_year", "academic_year_id"),
        {"extend_existing": True},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    academic_year_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("academic_year.id", ondelete="CASCADE"),
            index=True,
            nullable=False
        )
    )


class AcademicTermCreate(AcademicTermBase):
    """Schema for creating an Academic Term."""
    academic_year_id: int


class AcademicTermUpdate(SQLModel):
    """Schema for updating an Academic Term."""
    name: Optional[str] = None
    term_code: Optional[str] = None
    weight_percentage: Optional[float] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class AcademicTermRead(AcademicTermBase):
    """Schema for reading Academic Term."""
    id: int
    academic_year_id: int


# ---------------------------------------------------------
# Class Section Models
# ---------------------------------------------------------

class ClassSectionBase(SQLModel):
    """Base schema for Class Section."""
    grade_level: str = Field(..., max_length=50, description="Grade level / Year (e.g. 'Grade 9', 'Grade 10', 'KG-1')")
    section_name: str = Field(..., max_length=100, description="Section moniker (e.g. 'Section A', 'Rose', 'Alpha')")
    room_number: Optional[str] = Field(default=None, max_length=50, description="Physical homeroom / classroom number")
    max_capacity: int = Field(default=30, ge=1, le=500, description="Maximum student seating capacity")
    is_active: bool = Field(default=True, description="Whether section is active for enrollments")


class ClassSection(ClassSectionBase, table=True):
    """Database model for Class Section in a Campus."""
    __tablename__ = "class_section"
    __table_args__ = (
        Index("ix_class_section_campus_grade", "campus_id", "grade_level", "section_name"),
        Index("ix_class_section_teacher", "class_teacher_id"),
        {"extend_existing": True},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    campus_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("campus.id", ondelete="CASCADE"),
            index=True,
            nullable=False
        )
    )
    class_teacher_id: Optional[int] = Field(
        default=None,
        sa_column=Column(
            Integer,
            ForeignKey("user.id", ondelete="SET NULL"),
            nullable=True,
            index=True
        )
    )


class ClassSectionCreate(ClassSectionBase):
    """Schema for creating a Class Section."""
    campus_id: int
    class_teacher_id: Optional[int] = None


class ClassSectionUpdate(SQLModel):
    """Schema for updating a Class Section."""
    grade_level: Optional[str] = None
    section_name: Optional[str] = None
    room_number: Optional[str] = None
    class_teacher_id: Optional[int] = None
    max_capacity: Optional[int] = None
    is_active: Optional[bool] = None


class ClassSectionRead(ClassSectionBase):
    """Schema for reading Class Section."""
    id: int
    campus_id: int
    class_teacher_id: Optional[int] = None


# ---------------------------------------------------------
# Student Enrollment Models
# ---------------------------------------------------------

class StudentEnrollmentBase(SQLModel):
    """Base schema for Student Enrollment."""
    roll_number: Optional[str] = Field(default=None, max_length=50, description="Student roll / identity number in section")
    status: str = Field(default="active", max_length=50, description="Enrollment status: 'active', 'transferred', 'graduated', 'withdrawn'")


class StudentEnrollment(StudentEnrollmentBase, table=True):
    """Database model for Student Enrollment in a Class Section for an Academic Year."""
    __tablename__ = "student_enrollment"
    __table_args__ = (
        Index("ix_student_enrollment_unique_year", "student_id", "academic_year_id", unique=True),
        Index("ix_enrollment_section_status", "section_id", "status"),
        Index("ix_enrollment_academic_year", "academic_year_id"),
        {"extend_existing": True},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    student_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("user.id", ondelete="CASCADE"),
            index=True,
            nullable=False
        )
    )
    section_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("class_section.id", ondelete="CASCADE"),
            index=True,
            nullable=False
        )
    )
    academic_year_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("academic_year.id", ondelete="CASCADE"),
            index=True,
            nullable=False
        )
    )
    enrolled_at: str = Field(default_factory=get_utc_now_iso)


class StudentEnrollmentCreate(StudentEnrollmentBase):
    """Schema for enrolling a student."""
    student_id: int
    section_id: int
    academic_year_id: int


class StudentEnrollmentUpdate(SQLModel):
    """Schema for updating student enrollment."""
    roll_number: Optional[str] = None
    section_id: Optional[int] = None
    status: Optional[str] = None


class StudentEnrollmentRead(StudentEnrollmentBase):
    """Schema for reading Student Enrollment."""
    id: int
    student_id: int
    section_id: int
    academic_year_id: int
    enrolled_at: str
