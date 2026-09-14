"""
Integration test for GET /api/v1/sms/me -- the endpoint that replaces the
dev Keycloak JWT's client-side-decoded claims with a real, server-side
identity resolution. See src/routers/sms_identity.py.
"""

from datetime import date, datetime, timedelta

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.core.events.database import get_db_session
from src.db.sms_campus import AcademicTerm, AcademicYear, Campus, ClassSection, StudentEnrollment
from src.db.sms_hr import StaffProfile
from src.db.sms_identity import SMSUserRole, SchoolRole, StudentGuardian
from src.db.users import PublicUser, User
from src.router import v1_router
from src.security.auth import get_authenticated_user


async def _add_db_user(db, id_: int) -> User:
    """Insert a real `User` row -- GET /identity/children/{id}/context looks
    the target student up in the database (src.db.users.User), not from the
    caller-supplied PublicUser stub."""
    u = User(
        id=id_,
        username=f"dbuser{id_}",
        first_name="Child",
        last_name=f"User{id_}",
        email=f"dbuser{id_}@test.com",
        password="hashed_password",
        user_uuid=f"db-uuid-{id_}",
        creation_date=str(datetime.now()),
        update_date=str(datetime.now()),
    )
    db.add(u)
    await db.commit()
    return u


def _make_app(db):
    app = FastAPI()
    app.include_router(v1_router)
    app.dependency_overrides[get_db_session] = lambda: db
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


async def _get_me(db, current_user: PublicUser) -> dict:
    app = _make_app(db)
    app.dependency_overrides[get_authenticated_user] = lambda: current_user
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/sms/me")
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.asyncio
async def test_me_resolves_student_enrollment_and_current_term(db, org):
    campus = Campus(name="Main", code="MAIN-01", org_id=org.id)
    db.add(campus)
    await db.commit()
    await db.refresh(campus)

    year = AcademicYear(name="2026-2027", campus_id=campus.id)
    db.add(year)
    await db.commit()
    await db.refresh(year)

    today = date.today()
    term = AcademicTerm(
        name="Term 1",
        academic_year_id=year.id,
        start_date=(today - timedelta(days=10)).isoformat(),
        end_date=(today + timedelta(days=10)).isoformat(),
    )
    section = ClassSection(grade_level="Grade 9", section_name="A", campus_id=campus.id)
    db.add(term)
    db.add(section)
    await db.commit()
    await db.refresh(section)

    db.add(SMSUserRole(user_id=10, org_id=org.id, campus_id=campus.id, role=SchoolRole.STUDENT))
    db.add(StudentEnrollment(student_id=10, section_id=section.id, academic_year_id=year.id))
    await db.commit()
    await db.refresh(term)

    data = await _get_me(db, _user(10))

    assert data["roles"] == ["STUDENT"]
    assert data["student_id"] == 10
    assert data["section_id"] == section.id
    assert data["academic_term_id"] == term.id


@pytest.mark.asyncio
async def test_me_resolves_parents_children(db, org):
    db.add(SMSUserRole(user_id=20, org_id=org.id, role=SchoolRole.PARENT))
    db.add(StudentGuardian(guardian_user_id=20, student_id=101))
    db.add(StudentGuardian(guardian_user_id=20, student_id=102))
    await db.commit()

    data = await _get_me(db, _user(20))

    assert data["roles"] == ["PARENT"]
    assert sorted(data["children_ids"]) == [101, 102]


@pytest.mark.asyncio
async def test_me_resolves_teacher_own_section(db, org):
    campus = Campus(name="Main", code="MAIN-02", org_id=org.id)
    db.add(campus)
    await db.commit()
    await db.refresh(campus)

    section = ClassSection(grade_level="Grade 10", section_name="B", campus_id=campus.id, class_teacher_id=30)
    db.add(section)
    db.add(SMSUserRole(user_id=30, org_id=org.id, campus_id=campus.id, role=SchoolRole.TEACHER))
    db.add(StaffProfile(
        user_id=30,
        campus_id=campus.id,
        employee_code="EMP-30",
        full_name="Teacher Thirty",
        designation="Teacher",
        department="Science",
        joining_date=date.today(),
    ))
    await db.commit()
    await db.refresh(section)

    data = await _get_me(db, _user(30))

    assert data["roles"] == ["TEACHER"]
    assert data["section_id"] == section.id
    # Must be the Learnhouse user_id (30), NOT StaffProfile.id -- every SMS
    # table that references "the teacher" is an FK matching user.id, so the
    # frontend's `teacherId` (compared against those columns) would silently
    # get empty results for every "my timetable"/"my section" query if this
    # returned the StaffProfile surrogate key instead.
    assert data["staff_id"] == 30


@pytest.mark.asyncio
async def test_me_for_unprovisioned_authenticated_user_returns_empty_identity(db):
    """No SMSUserRole grants at all -- must 200 with empty identity, not error."""
    data = await _get_me(db, _user(999))

    assert data["roles"] == []
    assert data["student_id"] is None
    assert data["children_ids"] == []


async def _get(db, current_user, path):
    app = _make_app(db)
    app.dependency_overrides[get_authenticated_user] = lambda: current_user
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(path)
    return response


@pytest.mark.asyncio
async def test_get_child_context_for_guardian(db, org):
    campus = Campus(name="Main", code="CTX-01", org_id=org.id)
    db.add(campus)
    await db.commit()
    await db.refresh(campus)

    year = AcademicYear(name="2026-2027", campus_id=campus.id)
    db.add(year)
    await db.commit()
    await db.refresh(year)

    today = date.today()
    term = AcademicTerm(
        name="Term 1",
        academic_year_id=year.id,
        start_date=(today - timedelta(days=10)).isoformat(),
        end_date=(today + timedelta(days=10)).isoformat(),
    )
    section = ClassSection(grade_level="Grade 6", section_name="A", campus_id=campus.id)
    db.add(term)
    db.add(section)
    await db.commit()
    await db.refresh(section)
    await db.refresh(term)

    await _add_db_user(db, 201)
    db.add(SMSUserRole(user_id=40, org_id=org.id, role=SchoolRole.PARENT))
    db.add(StudentGuardian(guardian_user_id=40, student_id=201))
    db.add(StudentEnrollment(student_id=201, section_id=section.id, academic_year_id=year.id))
    await db.commit()

    response = await _get(db, _user(40), "/api/v1/sms/identity/children/201/context")

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["student_id"] == 201
    assert data["section_id"] == section.id
    assert data["academic_term_id"] == term.id


@pytest.mark.asyncio
async def test_get_child_context_denies_non_guardian(db, org):
    db.add(SMSUserRole(user_id=41, org_id=org.id, role=SchoolRole.PARENT))
    await db.commit()

    response = await _get(db, _user(41), "/api/v1/sms/identity/children/999/context")

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_child_context_for_self(db, org):
    await _add_db_user(db, 42)
    db.add(SMSUserRole(user_id=42, org_id=org.id, role=SchoolRole.STUDENT))
    await db.commit()

    response = await _get(db, _user(42), "/api/v1/sms/identity/children/42/context")

    assert response.status_code == 200, response.text
    assert response.json()["student_id"] == 42


@pytest.mark.asyncio
async def test_get_child_context_404_for_unknown_student(db, org):
    db.add(SMSUserRole(user_id=43, org_id=org.id, role=SchoolRole.SCHOOL_ADMIN))
    await db.commit()

    response = await _get(db, _user(43), "/api/v1/sms/identity/children/999999/context")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_academic_terms_for_own_org(db, org):
    campus = Campus(name="Main", code="AT-01", org_id=org.id)
    db.add(campus)
    await db.commit()
    await db.refresh(campus)

    year = AcademicYear(name="2026-2027", campus_id=campus.id)
    db.add(year)
    await db.commit()
    await db.refresh(year)

    db.add(AcademicTerm(name="Term 1", academic_year_id=year.id, start_date="2026-08-01", end_date="2026-12-20"))
    db.add(SMSUserRole(user_id=50, org_id=org.id, role=SchoolRole.SCHOOL_ADMIN))
    await db.commit()

    response = await _get(db, _user(50), "/api/v1/sms/academic-terms")

    assert response.status_code == 200, response.text
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Term 1"


@pytest.mark.asyncio
async def test_list_academic_terms_excludes_other_orgs(db, org, other_org):
    campus = Campus(name="Main", code="AT-02", org_id=other_org.id)
    db.add(campus)
    await db.commit()
    await db.refresh(campus)

    year = AcademicYear(name="2026-2027", campus_id=campus.id)
    db.add(year)
    await db.commit()
    await db.refresh(year)

    db.add(AcademicTerm(name="Other Org Term", academic_year_id=year.id))
    db.add(SMSUserRole(user_id=51, org_id=org.id, role=SchoolRole.SCHOOL_ADMIN))
    await db.commit()

    response = await _get(db, _user(51), "/api/v1/sms/academic-terms")

    assert response.status_code == 200, response.text
    assert response.json() == []
