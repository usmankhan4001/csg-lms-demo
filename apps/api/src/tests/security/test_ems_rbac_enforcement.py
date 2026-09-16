"""
Enforcement tests for the wired-up dynamic RBAC engine.

src/security/ems_rbac.py has always had a full permission evaluator
(`has_permission`) and a dependency factory (`require_permission`); until now
neither was called from a router, and `resolve_school_principal()` never
surfaced EMS assignments, so the store was unpopulated for real users and the
engine could not have done anything.

This file proves the wiring:

  1. a caller holding the right EMS grant is allowed,
  2. a caller holding none is DENIED (fail closed -- no legacy-role fallback),
  3. an EXPIRED assignment is denied,
  4. a CROSS-ORG assignment grants nothing,
  5. the 262 legacy `require_roles([...])` call sites behave exactly as before
     -- EMS slugs are deliberately NOT merged into `principal.roles`,
  6. `resolve_school_principal()` carries the EMS assignments,
  7. the backfill gives every existing `SMSUserRole` holder an equivalent
     assignment, so fail-closed does not lock out a real deployment.

The subject under test is `sms_fees` (one of the five wired routers); the
gates are identical in shape across the other four.
"""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from sqlmodel import select

from src.core.events.database import get_db_session
from src.core.keycloak_auth import (
    KeycloakUserPrincipal,
    get_current_user_principal,
    require_roles,
)
from src.db.ems_roles import (
    EMSPermissionRule,
    EMSRole,
    EMSUserRoleAssignment,
    ScopeLevel,
    seed_default_ems_roles,
)
from src.db.organizations import Organization
from src.db.sms_identity import SMSUserRole, SchoolRole
from src.db.users import PublicUser
from src.routers import sms_fees
from src.security import ems_rbac
from src.security.ems_rbac import (
    backfill_ems_assignments_from_sms_roles,
    has_permission,
    principal_ems_role_slugs,
)
from src.security.features_utils.dependencies import require_sms_fees_feature
from src.security.school_principal import resolve_school_principal

FEES_READ = "/sms/fees/structures"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_app(db):
    app = FastAPI()
    app.include_router(sms_fees.router, prefix="/sms/fees")
    app.dependency_overrides[get_db_session] = lambda: db
    app.dependency_overrides[require_sms_fees_feature] = lambda: True
    return app


def _principal(user_id, roles, org_id=1, campus_id=1):
    return KeycloakUserPrincipal(
        sub=f"uuid-{user_id}",
        email=f"u{user_id}@school.test",
        org_id=org_id,
        campus_id=campus_id,
        realm_roles=list(roles),
        roles=set(roles),
        raw_claims={"lh_user_id": user_id},
    )


async def _role_id(db, slug):
    await seed_default_ems_roles(db, org_id=None)
    role = (await db.execute(select(EMSRole).where(EMSRole.slug == slug))).scalars().first()
    assert role is not None, f"EMS role {slug} was not seeded"
    return role.id


async def _assign(db, user_id, slug, *, org_id=1, campus_id=1, expires_at=None):
    db.add(
        EMSUserRoleAssignment(
            user_id=user_id,
            role_id=await _role_id(db, slug),
            org_id=org_id,
            campus_id=campus_id,
            expires_at=expires_at,
        )
    )
    await db.commit()


async def _get(client, principal, path=FEES_READ):
    return await client.get(path)


# ---------------------------------------------------------------------------
# 1. The right EMS grant is allowed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ems_grant_allows_the_request(db, org):
    """A caller holding a school-admin EMS grant (finance:read, scope ALL)
    passes BOTH the coarse require_roles gate and the granular one."""
    await _assign(db, 101, "school-admin", org_id=org.id)
    app = _make_app(db)
    app.dependency_overrides[get_current_user_principal] = lambda: _principal(
        101, {"SCHOOL_ADMIN"}, org_id=org.id
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get(FEES_READ)

    assert res.status_code == 200, res.text


@pytest.mark.asyncio
async def test_ems_grant_is_scoped_to_the_action_it_grants(db, org):
    """The grant is fine-grained: finance:read does not imply finance:approve
    (authorising a concession), even for the same user."""
    await _assign(db, 102, "school-admin", org_id=org.id)
    app = _make_app(db)
    app.dependency_overrides[get_current_user_principal] = lambda: _principal(
        102, {"SCHOOL_ADMIN"}, org_id=org.id
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # school-admin template: finance can_approve = True -> allowed
        assert (await client.post("/sms/fees/concessions", json={})).status_code != 403

    # A librarian grant has finance:read but NOT finance:approve.
    await _assign(db, 103, "librarian", org_id=org.id)
    app.dependency_overrides[get_current_user_principal] = lambda: _principal(
        103, {"SCHOOL_ADMIN"}, org_id=org.id
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.post("/sms/fees/concessions", json={})).status_code == 403


# ---------------------------------------------------------------------------
# 2. No EMS assignment -> DENIED (fail closed)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_caller_with_no_ems_assignment_is_denied(db, org):
    """FAIL CLOSED. A SCHOOL_ADMIN who passes the coarse `require_roles` gate
    but holds no EMS assignment is refused -- the engine does NOT fall back to
    their legacy role."""
    app = _make_app(db)
    app.dependency_overrides[get_current_user_principal] = lambda: _principal(
        104, {"SCHOOL_ADMIN"}, org_id=org.id
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get(FEES_READ)

    assert res.status_code == 403, res.text
    assert "finance.fees:read" in res.json()["detail"]


@pytest.mark.asyncio
async def test_legacy_fallback_switch_restores_the_old_behaviour(db, org, monkeypatch):
    """`EMS_RBAC_LEGACY_FALLBACK=1` is the documented migration escape hatch:
    it lets the legacy role answer when there is no EMS assignment. Off by
    default (see the assertion above)."""
    monkeypatch.setattr(ems_rbac, "EMS_RBAC_LEGACY_FALLBACK", True)
    app = _make_app(db)
    app.dependency_overrides[get_current_user_principal] = lambda: _principal(
        105, {"SCHOOL_ADMIN"}, org_id=org.id
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get(FEES_READ)

    assert res.status_code == 200, res.text


@pytest.mark.asyncio
async def test_has_permission_fails_closed_when_asked_to(db, org):
    """The same policy at the evaluator level: `allow_legacy_fallback=False`
    refuses a caller with no grant, where the default (True) would not."""
    principal = _principal(106, {"SCHOOL_ADMIN"}, org_id=org.id)

    assert await has_permission(principal, "finance.fees", "read", db_session=db) is True
    assert (
        await has_permission(
            principal, "finance.fees", "read", db_session=db, allow_legacy_fallback=False
        )
        is False
    )


# ---------------------------------------------------------------------------
# 3. An expired assignment is denied
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_expired_assignment_is_denied(db, org):
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    await _assign(db, 107, "school-admin", org_id=org.id, expires_at=yesterday)

    app = _make_app(db)
    app.dependency_overrides[get_current_user_principal] = lambda: _principal(
        107, {"SCHOOL_ADMIN"}, org_id=org.id
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get(FEES_READ)

    assert res.status_code == 403, res.text


@pytest.mark.asyncio
async def test_unexpired_assignment_is_allowed(db, org):
    """Control for the test above: the same grant one day in the future works,
    so the denial is about expiry and nothing else."""
    tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
    await _assign(db, 108, "school-admin", org_id=org.id, expires_at=tomorrow)

    app = _make_app(db)
    app.dependency_overrides[get_current_user_principal] = lambda: _principal(
        108, {"SCHOOL_ADMIN"}, org_id=org.id
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get(FEES_READ)

    assert res.status_code == 200, res.text


# ---------------------------------------------------------------------------
# 4. A cross-org assignment grants nothing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cross_org_assignment_grants_nothing(db, org, other_org):
    """Tenant isolation: an assignment in organisation 2 must not authorise a
    caller acting in organisation 1."""
    await _assign(db, 109, "school-admin", org_id=other_org.id)

    app = _make_app(db)
    app.dependency_overrides[get_current_user_principal] = lambda: _principal(
        109, {"SCHOOL_ADMIN"}, org_id=org.id
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get(FEES_READ)

    assert res.status_code == 403, res.text


@pytest.mark.asyncio
async def test_cross_campus_assignment_grants_nothing(db, org):
    """Same rule one level down: an assignment pinned to campus 2 does not
    authorise a caller whose principal is pinned to campus 1."""
    await _assign(db, 110, "school-admin", org_id=org.id, campus_id=2)

    app = _make_app(db)
    app.dependency_overrides[get_current_user_principal] = lambda: _principal(
        110, {"SCHOOL_ADMIN"}, org_id=org.id, campus_id=1
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get(FEES_READ)

    assert res.status_code == 403, res.text


# ---------------------------------------------------------------------------
# 5. The legacy require_roles gate is unchanged
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_require_roles_still_matches_only_the_legacy_enum(db, org):
    """The 262 `require_roles([...])` call sites must see exactly what they saw
    before: the 7-value legacy enum. An EMS grant does NOT satisfy them."""
    checker = require_roles(["SCHOOL_ADMIN"])

    # Legacy role present -> allowed (as before).
    assert await checker(principal=_principal(111, {"SCHOOL_ADMIN"}, org_id=org.id)) is not None

    # No legacy role, but an EMS 'school-admin' grant -> still REFUSED. Merging
    # EMS slugs into principal.roles would have silently opened every one of
    # the 262 gates to every custom role an operator creates.
    ems_only = _principal(112, set(), org_id=org.id)
    await _assign(db, 112, "school-admin", org_id=org.id)
    with pytest.raises(HTTPException) as exc:
        await checker(principal=ems_only)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_require_roles_superadmin_bypass_unchanged(db, org):
    checker = require_roles(["SCHOOL_ADMIN"])
    assert await checker(principal=_principal(113, {"SUPER_ADMIN"}, org_id=org.id)) is not None


@pytest.mark.asyncio
async def test_superadmin_still_bypasses_the_new_gate(db, org):
    """`has_permission`'s SUPER_ADMIN bypass is untouched, so the new gate adds
    no lockout risk for superadmins."""
    app = _make_app(db)
    app.dependency_overrides[get_current_user_principal] = lambda: _principal(
        114, {"SUPER_ADMIN"}, org_id=org.id
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get(FEES_READ)

    assert res.status_code == 200, res.text


# ---------------------------------------------------------------------------
# 6. resolve_school_principal carries the EMS assignments
# ---------------------------------------------------------------------------


def _public_user(id_, is_superadmin=False):
    return PublicUser(
        id=id_,
        username=f"user{id_}",
        first_name="Test",
        last_name=f"User{id_}",
        email=f"user{id_}@test.com",
        user_uuid=f"user_uuid_{id_}",
        is_superadmin=is_superadmin,
    )


@pytest.mark.asyncio
async def test_principal_carries_ems_assignments(db, org):
    """The critical catch: without this the engine reads a store nothing
    populates, and every check fails closed for real users."""
    db.add(SMSUserRole(user_id=201, org_id=org.id, role=SchoolRole.TEACHER, campus_id=1))
    await db.commit()
    await _assign(db, 201, "bursar", org_id=org.id, campus_id=1)

    principal = await resolve_school_principal(_public_user(201), db)

    # The legacy enum is UNCHANGED -- 'bursar' is not a legacy role.
    assert principal.roles == {"TEACHER"}
    assert principal.has_role("TEACHER")
    assert not principal.has_role("BURSAR")
    # ...but the EMS grant is exposed for the dynamic engine.
    assert principal_ems_role_slugs(principal) == {"bursar"}
    assignments = principal.raw_claims["ems_assignments"]
    assert len(assignments) == 1
    assert assignments[0]["role_slug"] == "bursar"
    assert assignments[0]["org_id"] == org.id
    assert assignments[0]["campus_id"] == 1


@pytest.mark.asyncio
async def test_principal_excludes_expired_and_cross_org_assignments(db, org, other_org):
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    db.add(SMSUserRole(user_id=202, org_id=org.id, role=SchoolRole.TEACHER))
    await db.commit()
    await _assign(db, 202, "bursar", org_id=org.id, expires_at=yesterday)
    await _assign(db, 202, "librarian", org_id=other_org.id)

    principal = await resolve_school_principal(_public_user(202), db)

    assert principal_ems_role_slugs(principal) == set()


@pytest.mark.asyncio
async def test_principal_with_no_ems_assignment_has_empty_claims(db, org):
    db.add(SMSUserRole(user_id=203, org_id=org.id, role=SchoolRole.TEACHER))
    await db.commit()

    principal = await resolve_school_principal(_public_user(203), db)

    assert principal.raw_claims["ems_assignments"] == []
    assert principal.raw_claims["ems_role_slugs"] == []


# ---------------------------------------------------------------------------
# 7. The backfill -- the path that makes fail-closed safe
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_backfill_gives_every_sms_role_holder_an_ems_assignment(db, org):
    db.add(SMSUserRole(user_id=301, org_id=org.id, role=SchoolRole.TEACHER, campus_id=1))
    db.add(SMSUserRole(user_id=302, org_id=org.id, role=SchoolRole.SCHOOL_ADMIN))
    db.add(SMSUserRole(user_id=303, org_id=org.id, role=SchoolRole.PSYCHOLOGIST, campus_id=2))
    db.add(SMSUserRole(user_id=304, org_id=org.id, role=SchoolRole.TEACHER, is_active=False))
    await db.commit()

    created = await backfill_ems_assignments_from_sms_roles(db)
    await db.commit()

    assert created == 3  # the inactive grant is skipped

    rows = list((await db.execute(select(EMSUserRoleAssignment))).scalars().all())
    by_user = {r.user_id: r for r in rows}
    assert set(by_user) == {301, 302, 303}

    slugs = {
        r.user_id: (await db.get(EMSRole, r.role_id)).slug for r in rows
    }
    assert slugs[301] == "teacher"
    assert slugs[302] == "school-admin"
    assert slugs[303] == "psychologist"
    # Campus scope is preserved, not flattened to org-wide.
    assert by_user[301].campus_id == 1
    assert by_user[303].campus_id == 2


@pytest.mark.asyncio
async def test_backfill_is_idempotent(db, org):
    db.add(SMSUserRole(user_id=305, org_id=org.id, role=SchoolRole.STAFF))
    await db.commit()

    assert await backfill_ems_assignments_from_sms_roles(db) == 1
    await db.commit()
    assert await backfill_ems_assignments_from_sms_roles(db) == 0
    await db.commit()

    rows = list((await db.execute(select(EMSUserRoleAssignment))).scalars().all())
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_backfilled_user_can_use_the_gated_endpoint(db, org):
    """End-to-end proof that the backfill unblocks a real deployment: a legacy
    SCHOOL_ADMIN, backfilled, passes the gate that refused them before."""
    db.add(SMSUserRole(user_id=306, org_id=org.id, role=SchoolRole.SCHOOL_ADMIN, campus_id=1))
    await db.commit()
    await backfill_ems_assignments_from_sms_roles(db)
    await db.commit()

    principal = await resolve_school_principal(_public_user(306), db)
    assert principal_ems_role_slugs(principal) == {"school-admin"}

    app = _make_app(db)
    app.dependency_overrides[get_current_user_principal] = lambda: principal
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get(FEES_READ)).status_code == 200


# ---------------------------------------------------------------------------
# Clinical guardrail still holds through the gate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_clinical_gate_answers_404_never_403(db, org):
    """The 404-Never-403 rule survives the wiring: a non-specialist probing a
    `clinical.*` resource gets 404, never 403."""
    from fastapi import HTTPException as _HTTPException
    from starlette.requests import Request

    from src.security.ems_rbac import require_permission

    checker = require_permission("clinical.case_notes", "read")
    teacher = _principal(401, {"TEACHER"}, org_id=org.id)
    request = Request({"type": "http", "method": "GET", "path": "/", "headers": [], "query_string": b""})

    with pytest.raises(_HTTPException) as exc:
        await checker(request=request, principal=teacher, db_session=db)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_custom_role_with_a_narrow_scope_is_refused_outside_it(db, org):
    """A hand-built role (the live CRUD surface in routers/ems_roles.py) is
    honoured, including its scope -- CAMPUS 2 does not read campus 1."""
    role = EMSRole(org_id=org.id, name="Campus Two Bursar", slug="campus-two-bursar")
    db.add(role)
    await db.flush()
    db.add(
        EMSPermissionRule(
            role_id=role.id,
            resource_key="finance",
            can_read=True,
            scope_level=ScopeLevel.CAMPUS,
        )
    )
    db.add(
        EMSUserRoleAssignment(
            user_id=501, role_id=role.id, org_id=org.id, campus_id=2
        )
    )
    await db.commit()

    app = _make_app(db)
    app.dependency_overrides[get_current_user_principal] = lambda: _principal(
        501, {"SCHOOL_ADMIN"}, org_id=org.id, campus_id=2
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # No campus in the request -> the caller's own campus (2) is in scope.
        assert (await client.get(FEES_READ)).status_code == 200
        # Naming campus 1 explicitly -> refused by the CAMPUS scope rule.
        assert (await client.get(FEES_READ, params={"campus_id": 1})).status_code == 403
