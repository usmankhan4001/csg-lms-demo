"""
Tests for the CSG-LMS Counseling / Wellbeing / Career Guidance module
(Phase 4, Part B).

Covers:
  - Session-logging CRUD by a PSYCHOLOGIST.
  - The confidentiality mandate (DESIGN-SYSTEM.md §4/§10): a TEACHER or
    SCHOOL_ADMIN request for a student's counseling record gets an EMPTY
    result (200 empty list / 404), NEVER a 403 -- because a 403 would itself
    confirm a record exists.
  - Per-psychologist scoping: a different PSYCHOLOGIST also gets the empty
    result for a colleague's record.
  - Parent involvement: a session flagged share_summary_with_parent appears
    to that student's PARENT via the narrow parent-summary endpoint, and
    only that endpoint.
  - Career guidance plan generation (structured, AI-generated, and stored).
"""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlmodel import select

from src.core.events.database import get_db_session
from src.core.keycloak_auth import KeycloakUserPrincipal, get_current_user_principal
from src.db.ems_roles import EMSRole, EMSUserRoleAssignment, seed_default_ems_roles
from src.routers import sms_counseling
from src.security.features_utils.dependencies import require_tutor_counseling_feature
from src.services.sms import counseling as counseling_service


def _make_app(db):
    app = FastAPI()
    app.include_router(sms_counseling.router, prefix="/sms/counseling")
    app.dependency_overrides[get_db_session] = lambda: db
    app.dependency_overrides[require_tutor_counseling_feature] = lambda: True
    return app


async def _grant_ems_role(db, user_id, slug, org_id=1, campus_id=1):
    """Give `user_id` the built-in EMS role `slug`.

    These principals are constructed by hand rather than resolved from a real
    session, so nothing has populated `EMSUserRoleAssignment` for them. The
    dynamic gate (src/security/ems_rbac.require_permission) FAILS CLOSED, so a
    principal with no assignment is refused -- which is exactly what
    `backfill_ems_assignments_from_sms_roles()` exists to prevent for real
    users. Seeding the grant here models a backfilled deployment.
    """
    await seed_default_ems_roles(db, org_id=None)
    role = (await db.execute(select(EMSRole).where(EMSRole.slug == slug))).scalars().first()
    assert role is not None, f"EMS role {slug} was not seeded"
    db.add(
        EMSUserRoleAssignment(
            user_id=user_id, role_id=role.id, org_id=org_id, campus_id=campus_id
        )
    )
    await db.commit()


def _principal(roles, sub, user_id):
    """`lh_user_id` is required: it is how the EMS store is keyed."""
    return KeycloakUserPrincipal(
        sub=sub,
        org_id=1,
        campus_id=1,
        roles=set(roles),
        raw_claims={"lh_user_id": user_id},
    )


SESSION_PAYLOAD = {
    "student_id": 501,
    "session_date": "2026-09-01T10:00:00Z",
    "duration_minutes": 45,
    "notes": "Discussed exam stress coping strategies.",
    "follow_up_plan": "Check in again next week.",
    "share_summary_with_parent": False,
}


@pytest.mark.asyncio
async def test_psychologist_can_log_and_read_activity_and_session(db):
    app = _make_app(db)
    psych = _principal({"PSYCHOLOGIST"}, "psych-1", user_id=11)
    await _grant_ems_role(db, 11, "psychologist")
    app.dependency_overrides[get_current_user_principal] = lambda: psych

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Activity log
        resp = await client.post(
            "/sms/counseling/activity-logs",
            json={
                "student_id": 501,
                "signal_type": "behavioral_flag",
                "description": "Withdrawn during group activities this week.",
                "severity": "medium",
            },
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["psychologist_id"] == "psych-1"
        assert resp.json()["student_id"] == 501

        logs = await client.get("/sms/counseling/activity-logs/student/501")
        assert logs.status_code == 200
        assert len(logs.json()) == 1

        # Session logging
        resp2 = await client.post("/sms/counseling/sessions", json=SESSION_PAYLOAD)
        assert resp2.status_code == 201, resp2.text
        session_body = resp2.json()
        session_id = session_body["id"]
        assert session_body["psychologist_id"] == "psych-1"
        assert session_body["notes"] == SESSION_PAYLOAD["notes"]

        # Full-record reads, psychologist-only
        full_list = await client.get("/sms/counseling/sessions/student/501")
        assert full_list.status_code == 200
        assert len(full_list.json()) == 1
        assert full_list.json()[0]["notes"] == SESSION_PAYLOAD["notes"]

        single = await client.get(f"/sms/counseling/sessions/{session_id}")
        assert single.status_code == 200
        assert single.json()["id"] == session_id

        # Edit while still the author
        patched = await client.patch(
            f"/sms/counseling/sessions/{session_id}",
            json={"follow_up_plan": "Escalate to weekly check-ins."},
        )
        assert patched.status_code == 200
        assert patched.json()["follow_up_plan"] == "Escalate to weekly check-ins."


@pytest.mark.asyncio
async def test_teacher_and_school_admin_get_empty_result_never_403(db):
    """The confidentiality mandate: unauthorized roles get an empty list or a
    generic 404, never a 403 -- a 403 itself would confirm the record exists."""
    app = _make_app(db)

    psych = _principal({"PSYCHOLOGIST"}, "psych-2", user_id=12)
    await _grant_ems_role(db, 12, "psychologist")
    app.dependency_overrides[get_current_user_principal] = lambda: psych
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/sms/counseling/sessions",
            json={**SESSION_PAYLOAD, "student_id": 777},
        )
        assert resp.status_code == 201
        session_id = resp.json()["id"]

        await client.post(
            "/sms/counseling/activity-logs",
            json={
                "student_id": 777,
                "signal_type": "attendance_pattern",
                "description": "Three unexplained absences this month.",
            },
        )

    for role, uid in (("TEACHER", 20), ("SCHOOL_ADMIN", 21)):
        staff = _principal({role}, f"staff-{role}", user_id=uid)
        app.dependency_overrides[get_current_user_principal] = lambda staff=staff: staff
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # List endpoints: empty list, status 200 -- not 403.
            sessions_resp = await client.get("/sms/counseling/sessions/student/777")
            assert sessions_resp.status_code == 200, sessions_resp.text
            assert sessions_resp.json() == []

            logs_resp = await client.get("/sms/counseling/activity-logs/student/777")
            assert logs_resp.status_code == 200
            assert logs_resp.json() == []

            # Single-record fetch: generic 404 -- not 403.
            single_resp = await client.get(f"/sms/counseling/sessions/{session_id}")
            assert single_resp.status_code == 404
            assert single_resp.status_code != 403

            # Write attempts are also masked as 404, never 403.
            create_resp = await client.post(
                "/sms/counseling/sessions",
                json={**SESSION_PAYLOAD, "student_id": 777},
            )
            assert create_resp.status_code == 404
            assert create_resp.status_code != 403

            create_log_resp = await client.post(
                "/sms/counseling/activity-logs",
                json={"student_id": 777, "signal_type": "behavioral_flag", "description": "x"},
            )
            assert create_log_resp.status_code == 404
            assert create_log_resp.status_code != 403


@pytest.mark.asyncio
async def test_a_different_psychologist_cannot_see_a_colleagues_record(db):
    """Scoping is per-psychologist-author (mirrors zapier's per-token scoping,
    adapted here) -- a PSYCHOLOGIST who didn't author the record also gets
    the empty result, not the confidential data."""
    app = _make_app(db)

    psych_a = _principal({"PSYCHOLOGIST"}, "psych-a", user_id=13)
    await _grant_ems_role(db, 13, "psychologist")
    app.dependency_overrides[get_current_user_principal] = lambda: psych_a
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/sms/counseling/sessions",
            json={**SESSION_PAYLOAD, "student_id": 888},
        )
        session_id = resp.json()["id"]

    psych_b = _principal({"PSYCHOLOGIST"}, "psych-b", user_id=14)
    await _grant_ems_role(db, 14, "psychologist")
    app.dependency_overrides[get_current_user_principal] = lambda: psych_b
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        list_resp = await client.get("/sms/counseling/sessions/student/888")
        assert list_resp.status_code == 200
        assert list_resp.json() == []

        single_resp = await client.get(f"/sms/counseling/sessions/{session_id}")
        assert single_resp.status_code == 404


@pytest.mark.asyncio
async def test_parent_sees_only_the_parent_visible_flagged_session(db):
    app = _make_app(db)

    psych = _principal({"PSYCHOLOGIST"}, "psych-3", user_id=15)
    await _grant_ems_role(db, 15, "psychologist")
    app.dependency_overrides[get_current_user_principal] = lambda: psych
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # One flagged for the parent, one not.
        flagged = await client.post(
            "/sms/counseling/sessions",
            json={
                **SESSION_PAYLOAD,
                "student_id": 999,
                "share_summary_with_parent": True,
                "parent_visible_summary": "We had a supportive check-in about exam stress.",
            },
        )
        assert flagged.status_code == 201
        unflagged = await client.post(
            "/sms/counseling/sessions",
            json={**SESSION_PAYLOAD, "student_id": 999, "share_summary_with_parent": False},
        )
        assert unflagged.status_code == 201

    parent = _principal({"PARENT"}, "parent-1", user_id=30)
    app.dependency_overrides[get_current_user_principal] = lambda: parent
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        summary_resp = await client.get("/sms/counseling/sessions/student/999/parent-summary")
        assert summary_resp.status_code == 200
        data = summary_resp.json()
        assert len(data) == 1
        assert data[0]["parent_visible_summary"] == "We had a supportive check-in about exam stress."
        # No clinical notes field leaks into the parent-visible schema.
        assert "notes" not in data[0]
        assert "follow_up_plan" not in data[0]

        # The full-record endpoint stays empty for the parent -- confidentiality
        # extends to PARENT/STUDENT too, not just staff roles.
        full_resp = await client.get("/sms/counseling/sessions/student/999")
        assert full_resp.status_code == 200
        assert full_resp.json() == []


@pytest.mark.asyncio
async def test_career_guidance_plan_generation_and_listing(db, monkeypatch):
    from src.schemas.sms_counseling import CareerGuidancePathway, CareerGuidancePlanGenerated

    async def _fake_generate(**kwargs):
        return CareerGuidancePlanGenerated(
            suggested_pathways=[
                CareerGuidancePathway(
                    pathway="Software Engineering",
                    reasoning="Strong performance in math and logic-heavy coursework.",
                )
            ],
            reasoning="Based on consistently strong STEM performance.",
            next_steps=["Join the robotics club", "Take an introductory programming elective"],
        )

    monkeypatch.setattr(counseling_service, "generate", _fake_generate)

    app = _make_app(db)
    teacher = _principal({"TEACHER"}, "teacher-2", user_id=22)
    await _grant_ems_role(db, 22, "teacher")
    app.dependency_overrides[get_current_user_principal] = lambda: teacher

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/sms/counseling/career-guidance/generate",
            json={"student_id": 501, "interests": ["robotics", "math"]},
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["reasoning"] == "Based on consistently strong STEM performance."
        assert len(body["suggested_pathways"]) == 1
        assert body["suggested_pathways"][0]["pathway"] == "Software Engineering"
        assert body["generated_by"] == "teacher-2"
        assert len(body["next_steps"]) == 2

        listed = await client.get("/sms/counseling/career-guidance/student/501")
        assert listed.status_code == 200
        assert len(listed.json()) == 1


@pytest.mark.asyncio
async def test_career_guidance_generation_requires_staff_role(db):
    app = _make_app(db)
    student = _principal({"STUDENT"}, "student-1", user_id=40)
    app.dependency_overrides[get_current_user_principal] = lambda: student

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/sms/counseling/career-guidance/generate",
            json={"student_id": 501},
        )
        # Career guidance is not confidential clinical data -- a plain 403 is
        # correct here (unlike the activity-log/session endpoints above).
        assert resp.status_code == 403
