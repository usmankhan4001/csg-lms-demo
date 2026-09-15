"""
Unit & Integration Tests for CSG-EMS Academic Curricular Bridge
===============================================================
Validates:
1. SectionSubject model & registration in db package
2. SectionSubject CRUD endpoints under `/api/v1/ems/academic/sections/{section_id}/subjects`
3. Manual and automated synchronization of LMS course activity grades to SMS Gradebook.
"""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app import app
from src.core.events.database import get_db_session
from src.core.keycloak_auth import get_current_user_principal
from src.db import SectionSubject, SectionSubjectCreate, SectionSubjectRead
from src.db.courses.courses import Course
from src.db.sms_campus import AcademicYear, Campus, ClassSection, StudentEnrollment
from src.db.sms_gradebook import AssessmentPlan, GradeChangeEvent, GradebookEntry
from src.db.users import User
from src.services.sms.section_subjects import sync_course_activity_grade_to_sms
from src.tests.security.test_ems_rbac import _make_principal


@pytest.fixture
def admin_principal(org):
    return _make_principal(1, {"SCHOOL_ADMIN"}, org_id=org.id, campus_id=1)


@pytest.fixture
def teacher_principal(org):
    return _make_principal(2, {"TEACHER"}, org_id=org.id, campus_id=1)


@pytest.fixture
def student_principal(org):
    return _make_principal(3, {"STUDENT"}, org_id=org.id, campus_id=1)


@pytest.fixture
async def academic_setup(db, org, regular_user):
    """Setup campus, academic year, class section, course, and enrolled student."""
    # Campus
    campus = Campus(name="Main Campus", code="MAIN-01", org_id=org.id)
    db.add(campus)
    await db.commit()
    await db.refresh(campus)

    # Academic Year
    year = AcademicYear(name="2026-2027", campus_id=campus.id, is_active=True)
    db.add(year)
    await db.commit()
    await db.refresh(year)

    # Class Section
    section = ClassSection(
        grade_level="Grade 10",
        section_name="Section A",
        campus_id=campus.id,
        academic_year_id=year.id,
    )
    db.add(section)
    await db.commit()
    await db.refresh(section)

    # LMS Course
    course = Course(
        name="AP Physics C: Mechanics",
        org_id=org.id,
        course_uuid="crs-physics-101",
        public=True,
        published=True,
        open_to_contributors=False,
    )
    db.add(course)
    await db.commit()
    await db.refresh(course)

    # Student User & Enrollment
    student = User(
        username="einstein_student",
        first_name="Albert",
        last_name="Einstein",
        email="einstein@school.edu",
    )
    db.add(student)
    await db.commit()
    await db.refresh(student)

    enrollment = StudentEnrollment(
        student_id=student.id,
        section_id=section.id,
        academic_year_id=year.id,
        status="active",
    )
    db.add(enrollment)
    await db.commit()
    await db.refresh(enrollment)

    return {
        "campus": campus,
        "academic_year": year,
        "section": section,
        "course": course,
        "student": student,
        "teacher": regular_user,
    }


# ---------------------------------------------------------
# Test Cases
# ---------------------------------------------------------

@pytest.mark.asyncio
async def test_section_subject_crud_endpoints(db, academic_setup, admin_principal):
    """Verify POST, GET, PUT, DELETE endpoints for Section-Subject mappings."""
    app.dependency_overrides[get_current_user_principal] = lambda: admin_principal
    app.dependency_overrides[get_db_session] = lambda: db

    section = academic_setup["section"]
    course = academic_setup["course"]
    teacher = academic_setup["teacher"]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create Section Subject
        create_payload = {
            "course_id": course.id,
            "teacher_id": teacher.id,
            "subject_name": "Physics",
            "subject_code": "PHY-101",
            "credit_hours": 3.0,
            "is_elective": False,
        }
        res = await client.post(
            f"/api/v1/ems/academic/sections/{section.id}/subjects",
            json=create_payload,
        )
        assert res.status_code == 201, res.text
        data = res.json()
        assert data["subject_name"] == "Physics"
        assert data["subject_code"] == "PHY-101"
        assert data["course_id"] == course.id
        assert data["section_id"] == section.id
        assert data["credit_hours"] == 3.0
        assert data["course_name"] == course.name
        subject_id = data["id"]

        # 2. List Section Subjects
        list_res = await client.get(
            f"/api/v1/ems/academic/sections/{section.id}/subjects"
        )
        assert list_res.status_code == 200
        subjects = list_res.json()
        assert len(subjects) == 1
        assert subjects[0]["id"] == subject_id

        # 3. Get Single Section Subject
        get_res = await client.get(
            f"/api/v1/ems/academic/sections/{section.id}/subjects/{subject_id}"
        )
        assert get_res.status_code == 200
        assert get_res.json()["subject_name"] == "Physics"

        # 4. Update Section Subject
        update_payload = {
            "subject_name": "Advanced Physics",
            "credit_hours": 4.0,
            "is_elective": True,
        }
        put_res = await client.put(
            f"/api/v1/ems/academic/sections/{section.id}/subjects/{subject_id}",
            json=update_payload,
        )
        assert put_res.status_code == 200
        updated = put_res.json()
        assert updated["subject_name"] == "Advanced Physics"
        assert updated["credit_hours"] == 4.0
        assert updated["is_elective"] is True

        # 5. Delete Section Subject
        del_res = await client.delete(
            f"/api/v1/ems/academic/sections/{section.id}/subjects/{subject_id}"
        )
        assert del_res.status_code == 200

        # Verify Deleted
        get_deleted = await client.get(
            f"/api/v1/ems/academic/sections/{section.id}/subjects/{subject_id}"
        )
        assert get_deleted.status_code == 404

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_automatic_gradebook_synchronization(db, academic_setup):
    """
    Verify that when a course activity is completed/graded,
    sync_course_activity_grade_to_sms automatically creates an AssessmentPlan
    and GradebookEntry in the SMS gradebook with audit history.
    """
    section = academic_setup["section"]
    course = academic_setup["course"]
    student = academic_setup["student"]
    teacher = academic_setup["teacher"]

    # 1. Create the SectionSubject bridge
    bridge = SectionSubject(
        section_id=section.id,
        course_id=course.id,
        teacher_id=teacher.id,
        subject_name="Physics",
        subject_code="PHY-101",
        credit_hours=3.0,
    )
    db.add(bridge)
    await db.commit()

    # 2. Trigger automated grade sync
    entries = await sync_course_activity_grade_to_sms(
        db_session=db,
        student_id=student.id,
        course_id=course.id,
        raw_score=92.0,
        max_score=100.0,
        activity_title="Midterm Mechanics Exam",
        remarks="Excellent performance on rotational dynamics",
        graded_by=teacher.id,
    )

    assert len(entries) == 1
    entry = entries[0]
    assert entry.student_id == student.id
    assert entry.raw_score == 92.0
    assert entry.max_score == 100.0
    assert entry.letter_grade == "A+"
    assert entry.gpa_point == 4.0

    # Verify AssessmentPlan was created
    plan_stmt = select(AssessmentPlan).where(
        AssessmentPlan.course_id == course.id,
        AssessmentPlan.section_id == section.id,
    )
    plan = (await db.execute(plan_stmt)).scalar_one_or_none()
    assert plan is not None
    assert plan.assessment_name == "Midterm Mechanics Exam"
    assert plan.max_score == 100.0

    # Verify GradeChangeEvent audit row was created
    audit_stmt = select(GradeChangeEvent).where(
        GradeChangeEvent.gradebook_entry_id == entry.id
    )
    audit = (await db.execute(audit_stmt)).scalar_one_or_none()
    assert audit is not None
    assert audit.action == "created"
    assert audit.new_raw_score == 92.0
    assert audit.new_letter_grade == "A+"

    # 3. Update the grade (e.g. regrading)
    entries_updated = await sync_course_activity_grade_to_sms(
        db_session=db,
        student_id=student.id,
        course_id=course.id,
        raw_score=78.0,
        max_score=100.0,
        activity_title="Midterm Mechanics Exam",
        remarks="Regraded after correction",
        graded_by=teacher.id,
    )
    assert len(entries_updated) == 1
    updated_entry = entries_updated[0]
    assert updated_entry.raw_score == 78.0
    assert updated_entry.letter_grade == "B+"
    assert updated_entry.gpa_point == 3.3

    # Verify second audit row for CHANGED action
    audit_changes = (
        await db.execute(
            select(GradeChangeEvent).where(
                GradeChangeEvent.gradebook_entry_id == entry.id
            )
        )
    ).scalars().all()
    assert len(audit_changes) == 2
    assert audit_changes[1].action == "changed"
    assert audit_changes[1].previous_raw_score == 92.0
    assert audit_changes[1].new_raw_score == 78.0


@pytest.mark.asyncio
async def test_manual_sync_endpoint(db, academic_setup, admin_principal):
    """Test POST /api/v1/ems/academic/sections/{section_id}/sync-grades endpoint."""
    app.dependency_overrides[get_current_user_principal] = lambda: admin_principal
    app.dependency_overrides[get_db_session] = lambda: db

    section = academic_setup["section"]
    course = academic_setup["course"]
    student = academic_setup["student"]

    # Create Bridge
    bridge = SectionSubject(
        section_id=section.id,
        course_id=course.id,
        subject_name="Physics",
        subject_code="PHY-101",
    )
    db.add(bridge)
    await db.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        sync_payload = {
            "student_id": student.id,
            "course_id": course.id,
            "raw_score": 85.0,
            "max_score": 100.0,
            "activity_title": "Quiz 1: Kinematics",
            "remarks": "Great work",
        }
        res = await client.post(
            f"/api/v1/ems/academic/sections/{section.id}/sync-grades",
            json=sync_payload,
        )
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["synced_entries_count"] == 1

    app.dependency_overrides.clear()
