"""
Unit Tests for SMS Campus Database Models & Hierarchy
======================================================
"""

import pytest
from src.db.sms_campus import (
    Campus,
    CampusCreate,
    AcademicYear,
    AcademicYearCreate,
    AcademicTerm,
    AcademicTermCreate,
    ClassSection,
    ClassSectionCreate,
    StudentEnrollment,
    StudentEnrollmentCreate,
)


def test_campus_model_instantiation():
    """Verify Campus model schema properties and defaults."""
    campus = Campus(
        org_id=1,
        name="Islamabad Campus",
        code="ISB-MAIN",
        address="Sector H-8/1, Islamabad",
        timezone="Asia/Karachi",
        is_active=True,
    )
    assert campus.org_id == 1
    assert campus.name == "Islamabad Campus"
    assert campus.code == "ISB-MAIN"
    assert campus.timezone == "Asia/Karachi"
    assert campus.is_active is True
    assert campus.created_at is not None
    assert campus.updated_at is not None


def test_academic_year_model_instantiation():
    """Verify AcademicYear model schema properties and defaults."""
    acad_year = AcademicYear(
        campus_id=10,
        name="2026-2027",
        start_date="2026-08-15",
        end_date="2027-06-15",
        is_active=True,
    )
    assert acad_year.campus_id == 10
    assert acad_year.name == "2026-2027"
    assert acad_year.start_date == "2026-08-15"
    assert acad_year.end_date == "2027-06-15"
    assert acad_year.is_active is True
    assert acad_year.created_at is not None


def test_academic_term_model_instantiation():
    """Verify AcademicTerm model properties and grade weighting."""
    term = AcademicTerm(
        academic_year_id=5,
        name="Fall Term",
        term_code="TERM-1",
        weight_percentage=50.0,
        start_date="2026-08-15",
        end_date="2026-12-20",
    )
    assert term.academic_year_id == 5
    assert term.name == "Fall Term"
    assert term.term_code == "TERM-1"
    assert term.weight_percentage == 50.0


def test_class_section_model_instantiation():
    """Verify ClassSection model capacity and teacher assignment."""
    section = ClassSection(
        campus_id=10,
        grade_level="Grade 10",
        section_name="Section Alpha",
        room_number="Room-204",
        class_teacher_id=42,
        max_capacity=35,
        is_active=True,
    )
    assert section.campus_id == 10
    assert section.grade_level == "Grade 10"
    assert section.section_name == "Section Alpha"
    assert section.room_number == "Room-204"
    assert section.class_teacher_id == 42
    assert section.max_capacity == 35


def test_student_enrollment_model_instantiation():
    """Verify StudentEnrollment model properties and status."""
    enrollment = StudentEnrollment(
        student_id=101,
        section_id=15,
        academic_year_id=5,
        roll_number="10-ALPHA-01",
        status="active",
    )
    assert enrollment.student_id == 101
    assert enrollment.section_id == 15
    assert enrollment.academic_year_id == 5
    assert enrollment.roll_number == "10-ALPHA-01"
    assert enrollment.status == "active"
    assert enrollment.enrolled_at is not None
