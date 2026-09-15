"""
Unit & Integration Tests for CSG-EMS Role & Permission Management Router
========================================================================
Validates all endpoints under `/api/v1/ems/roles`:
- GET /templates (system template blueprints)
- GET / (list org roles)
- POST / (create custom role)
- GET /{role_id} (get role details & rules)
- PUT /{role_id} (update custom role & rules)
- DELETE /{role_id} (delete custom role / refuse system template)
- POST /assign (assign role with multi-tier scope)
- DELETE /assign/{assignment_id} (revoke assignment)
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app import app
from src.core.events.database import get_db_session
from src.core.keycloak_auth import get_current_user_principal
from src.db.ems_roles import EMSRole, ScopeLevel
from src.tests.security.test_ems_rbac import _make_principal


@pytest.fixture
def admin_principal(org):
    return _make_principal(1, {"SCHOOL_ADMIN"}, org_id=org.id, campus_id=1)


@pytest.fixture
def non_admin_principal(org):
    return _make_principal(2, {"TEACHER"}, org_id=org.id, campus_id=1)


@pytest.mark.asyncio
async def test_get_templates(db, admin_principal):
    """GET /api/v1/ems/roles/templates returns system template blueprints."""
    app.dependency_overrides[get_current_user_principal] = lambda: admin_principal
    app.dependency_overrides[get_db_session] = lambda: db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/ems/roles/templates")
        assert res.status_code == 200
        data = res.json()
        assert len(data) >= 7
        slugs = [t["slug"] for t in data]
        assert "super-admin" in slugs or "super_admin" in slugs or "teacher" in slugs
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_and_create_custom_role(db, org, admin_principal):
    """POST /api/v1/ems/roles creates custom role, then GET lists it."""
    app.dependency_overrides[get_current_user_principal] = lambda: admin_principal
    app.dependency_overrides[get_db_session] = lambda: db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create
        create_payload = {
            "name": "Math Department Head",
            "slug": "math-dept-head",
            "description": "Oversees mathematics faculty and curriculum",
            "is_clinical_specialist": False,
            "rules": [
                {
                    "resource_key": "academic",
                    "can_read": True,
                    "can_create": True,
                    "can_update": True,
                    "can_delete": False,
                    "can_approve": True,
                    "can_export": True,
                    "scope_level": "DEPARTMENT",
                }
            ],
        }
        res = await client.post("/api/v1/ems/roles", json=create_payload)
        assert res.status_code == 201
        role_data = res.json()
        assert role_data["name"] == "Math Department Head"
        assert role_data["slug"] == "math-dept-head"
        assert len(role_data["rules"]) == 1
        role_id = role_data["id"]

        # List
        list_res = await client.get("/api/v1/ems/roles")
        assert list_res.status_code == 200
        roles = list_res.json()
        assert any(r["id"] == role_id for r in roles)

        # Get details
        get_res = await client.get(f"/api/v1/ems/roles/{role_id}")
        assert get_res.status_code == 200
        assert get_res.json()["slug"] == "math-dept-head"

        # Update
        update_payload = {
            "name": "Mathematics & STEM Department Head",
            "description": "Updated STEM head description",
        }
        put_res = await client.put(f"/api/v1/ems/roles/{role_id}", json=update_payload)
        assert put_res.status_code == 200
        assert put_res.json()["name"] == "Mathematics & STEM Department Head"

        # Delete
        del_res = await client.delete(f"/api/v1/ems/roles/{role_id}")
        assert del_res.status_code == 200

        # Verify deleted
        get_deleted = await client.get(f"/api/v1/ems/roles/{role_id}")
        assert get_deleted.status_code == 404

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_assign_and_revoke_role(db, org, admin_principal):
    """POST /api/v1/ems/roles/assign assigns a role and DELETE revokes it."""
    # Seed a role in db
    custom_role = EMSRole(
        org_id=org.id,
        name="Campus Registrar",
        slug="campus-registrar",
        is_system_template=False,
    )
    db.add(custom_role)
    await db.commit()
    await db.refresh(custom_role)

    app.dependency_overrides[get_current_user_principal] = lambda: admin_principal
    app.dependency_overrides[get_db_session] = lambda: db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        assign_payload = {
            "user_id": 45,
            "role_id": custom_role.id,
            "campus_id": 1,
            "department_id": None,
            "section_id": None,
        }
        res = await client.post("/api/v1/ems/roles/assign", json=assign_payload)
        assert res.status_code == 201
        assignment_data = res.json()
        assert assignment_data["user_id"] == 45
        assert assignment_data["role_id"] == custom_role.id
        assignment_id = assignment_data["id"]

        # Revoke assignment
        del_res = await client.delete(f"/api/v1/ems/roles/assign/{assignment_id}")
        assert del_res.status_code == 200
        assert del_res.json()["status"] == "success"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_non_admin_forbidden_from_managing_roles(db, non_admin_principal):
    """Non-admin caller cannot create or mutate roles."""
    app.dependency_overrides[get_current_user_principal] = lambda: non_admin_principal
    app.dependency_overrides[get_db_session] = lambda: db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/api/v1/ems/roles",
            json={"name": "Hacker Role", "slug": "hacker-role"},
        )
        assert res.status_code == 403
    app.dependency_overrides.clear()
