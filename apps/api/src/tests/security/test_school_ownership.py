"""
Tests for src/security/school_ownership.py -- the server-side "is this
actually your data" checks that close a real, pre-existing gap (student_id/
section_id were previously trusted, unverified client-supplied params).
Exercised through the real HTTP endpoints they're wired into, not just the
dependency function in isolation, so a regression in the wiring itself
(wrong param name, wrong endpoint) is caught too.
"""

from datetime import date

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.core.events.database import get_db_session
from src.db.sms_attendance import StudentAttendance
from src.db.sms_campus import ClassSection
from src.db.sms_identity import SMSUserRole, SchoolRole, StudentGuardian
from src.db.users import PublicUser
from src.router import v1_router
from src.security.auth import get_authenticated_user
from src.security.features_utils.dependencies import require_sms_attendance_feature


def _make_app(db):
    app = FastAPI()
    app.include_router(v1_router)
    app.dependency_overrides[get_db_session] = lambda: db
    app.dependency_overrides[require_sms_attendance_feature] = lambda: True
    return app


def _user(id_: int) -> PublicUser:
    return PublicUser(
        id=id_,
        username=f"user{id_}",
        first_name="Test",
        last_name=f"User{id_}",
        email=f"user{id_}@test.com",
        user_uuid=f"uuid-{id_}",
    )


async def _seed_attendance(db, student_id: int, section_id: int = 1):
    db.add(StudentAttendance(student_id=student_id, section_id=section_id, date=date.today(), status="PRESENT"))
    await db.commit()


@pytest.mark.asyncio
async def test_student_can_read_own_attendance(db, org):
    db.add(SMSUserRole(user_id=1, org_id=org.id, role=SchoolRole.STUDENT))
    await _seed_attendance(db, student_id=1)

    app = _make_app(db)
    app.dependency_overrides[get_authenticated_user] = lambda: _user(1)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/sms/attendance/student/1/monthly", params={"year": date.today().year, "month": date.today().month})

    assert response.status_code == 200, response.text


@pytest.mark.asyncio
async def test_student_cannot_read_someone_elses_attendance(db, org):
    db.add(SMSUserRole(user_id=1, org_id=org.id, role=SchoolRole.STUDENT))
    await _seed_attendance(db, student_id=2)

    app = _make_app(db)
    app.dependency_overrides[get_authenticated_user] = lambda: _user(1)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/sms/attendance/student/2/monthly", params={"year": date.today().year, "month": date.today().month})

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_parent_can_read_their_childs_attendance(db, org):
    db.add(SMSUserRole(user_id=10, org_id=org.id, role=SchoolRole.PARENT))
    db.add(StudentGuardian(guardian_user_id=10, student_id=2))
    await _seed_attendance(db, student_id=2)

    app = _make_app(db)
    app.dependency_overrides[get_authenticated_user] = lambda: _user(10)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/sms/attendance/student/2/monthly", params={"year": date.today().year, "month": date.today().month})

    assert response.status_code == 200, response.text


@pytest.mark.asyncio
async def test_parent_cannot_read_a_non_childs_attendance(db, org):
    db.add(SMSUserRole(user_id=10, org_id=org.id, role=SchoolRole.PARENT))
    db.add(StudentGuardian(guardian_user_id=10, student_id=999))  # unrelated child
    await _seed_attendance(db, student_id=2)

    app = _make_app(db)
    app.dependency_overrides[get_authenticated_user] = lambda: _user(10)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/sms/attendance/student/2/monthly", params={"year": date.today().year, "month": date.today().month})

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_school_admin_bypasses_ownership_check(db, org):
    db.add(SMSUserRole(user_id=20, org_id=org.id, role=SchoolRole.SCHOOL_ADMIN))
    await _seed_attendance(db, student_id=2)

    app = _make_app(db)
    app.dependency_overrides[get_authenticated_user] = lambda: _user(20)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/sms/attendance/student/2/monthly", params={"year": date.today().year, "month": date.today().month})

    assert response.status_code == 200, response.text


@pytest.mark.asyncio
async def test_superadmin_bypasses_ownership_check(db):
    await _seed_attendance(db, student_id=2)

    app = _make_app(db)
    app.dependency_overrides[get_authenticated_user] = lambda: PublicUser(
        id=99, username="sa", first_name="Super", last_name="Admin",
        email="sa@test.com", user_uuid="uuid-99", is_superadmin=True,
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/sms/attendance/student/2/monthly", params={"year": date.today().year, "month": date.today().month})

    assert response.status_code == 200, response.text


@pytest.mark.asyncio
async def test_teacher_can_submit_roll_call_for_own_section(db, org):
    from src.db.sms_campus import Campus
    campus = Campus(name="Main", code="RC-01", org_id=org.id)
    db.add(campus)
    await db.commit()
    await db.refresh(campus)

    section = ClassSection(grade_level="Grade 9", section_name="A", campus_id=campus.id, class_teacher_id=30)
    db.add(section)
    db.add(SMSUserRole(user_id=30, org_id=org.id, role=SchoolRole.TEACHER))
    await db.commit()
    await db.refresh(section)

    app = _make_app(db)
    app.dependency_overrides[get_authenticated_user] = lambda: _user(30)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/sms/attendance/roll-call",
            json={
                "section_id": section.id,
                "date": date.today().isoformat(),
                "marked_by": 30,
                "entries": [{"student_id": 1, "status": "PRESENT"}],
            },
        )

    assert response.status_code == 200, response.text


@pytest.mark.asyncio
async def test_teacher_cannot_submit_roll_call_for_someone_elses_section(db, org):
    from src.db.sms_campus import Campus
    campus = Campus(name="Main", code="RC-02", org_id=org.id)
    db.add(campus)
    await db.commit()
    await db.refresh(campus)

    section = ClassSection(grade_level="Grade 9", section_name="B", campus_id=campus.id, class_teacher_id=999)
    db.add(section)
    db.add(SMSUserRole(user_id=30, org_id=org.id, role=SchoolRole.TEACHER))
    await db.commit()
    await db.refresh(section)

    app = _make_app(db)
    app.dependency_overrides[get_authenticated_user] = lambda: _user(30)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/sms/attendance/roll-call",
            json={
                "section_id": section.id,
                "date": date.today().isoformat(),
                "marked_by": 30,
                "entries": [{"student_id": 1, "status": "PRESENT"}],
            },
        )

    assert response.status_code == 403
