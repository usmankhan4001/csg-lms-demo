"""
Tests for `resolve_school_principal()` -- the function that replaced
Keycloak JWT decoding as the source of `KeycloakUserPrincipal`. See
src/security/school_principal.py and PROJECT_DOCS/ARCHITECTURE.md.
"""

import pytest
from datetime import datetime, timezone

from fastapi import HTTPException

from src.db.organizations import Organization
from src.db.sms_identity import SMSUserRole, SchoolRole
from src.db.users import APITokenUser, PublicUser, SuperadminAPITokenUser
from src.security.school_principal import resolve_school_principal


def _user(id_: int, *, is_superadmin: bool = False, uuid: str | None = None) -> PublicUser:
    return PublicUser(
        id=id_,
        username=f"user{id_}",
        first_name="Test",
        last_name=f"User{id_}",
        email=f"user{id_}@test.com",
        user_uuid=uuid or f"user_uuid_{id_}",
        is_superadmin=is_superadmin,
    )


@pytest.mark.asyncio
async def test_superadmin_gets_super_admin_role_with_no_grants(db):
    principal = await resolve_school_principal(_user(1, is_superadmin=True), db)
    assert principal.is_superadmin
    assert "SUPER_ADMIN" in principal.roles


@pytest.mark.asyncio
async def test_authenticated_user_with_zero_roles_is_not_rejected(db):
    """An authenticated-but-unprovisioned user must be readable (e.g. for
    GET /sms/me to report 'no school role yet'), not 403/401 -- that's
    require_roles()'s job at the route level, not this resolver's."""
    principal = await resolve_school_principal(_user(2), db)
    assert principal.roles == set()
    assert not principal.is_superadmin


@pytest.mark.asyncio
async def test_multi_role_user(db, org):
    user = _user(3)
    db.add(SMSUserRole(user_id=3, org_id=org.id, role=SchoolRole.TEACHER))
    db.add(SMSUserRole(user_id=3, org_id=org.id, role=SchoolRole.PARENT))
    await db.commit()

    principal = await resolve_school_principal(user, db)

    assert principal.roles == {"TEACHER", "PARENT"}
    assert principal.has_role("TEACHER")
    assert principal.has_role("PARENT")
    assert principal.org_id == org.id


@pytest.mark.asyncio
async def test_campus_id_comes_from_the_role_grant(db, org):
    user = _user(4)
    db.add(SMSUserRole(user_id=4, org_id=org.id, role=SchoolRole.TEACHER, campus_id=42))
    await db.commit()

    principal = await resolve_school_principal(user, db)

    assert principal.campus_id == 42


@pytest.mark.asyncio
async def test_inactive_grant_is_not_counted(db, org):
    user = _user(5)
    db.add(SMSUserRole(user_id=5, org_id=org.id, role=SchoolRole.TEACHER, is_active=False))
    await db.commit()

    principal = await resolve_school_principal(user, db)

    assert "TEACHER" not in principal.roles


@pytest.mark.asyncio
async def test_api_token_user_is_rejected(db):
    token_user = APITokenUser(org_id=1, created_by_user_id=1)
    with pytest.raises(HTTPException) as exc_info:
        await resolve_school_principal(token_user, db)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_superadmin_api_token_user_is_rejected(db):
    with pytest.raises(HTTPException) as exc_info:
        await resolve_school_principal(SuperadminAPITokenUser(), db)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_sub_is_stable_across_calls_for_the_same_user(db, org):
    """`principal.sub` is written into ownership-filter DB columns
    (psychologist_id, teacher_id, sent_by, ...) -- it must be the same
    string every time the same person authenticates, not a random per-call
    value."""
    user = _user(6, uuid="stable-uuid-6")
    db.add(SMSUserRole(user_id=6, org_id=org.id, role=SchoolRole.TEACHER))
    await db.commit()

    first = await resolve_school_principal(user, db)
    second = await resolve_school_principal(user, db)

    assert first.sub == second.sub == "stable-uuid-6"


@pytest.mark.asyncio
async def test_superadmin_falls_back_to_default_org_when_no_grants(db):
    default_org = Organization(
        id=100,
        name="Default Org",
        slug="default",
        email="default@test.com",
        org_uuid="org_default",
        creation_date=str(datetime.now(timezone.utc)),
        update_date=str(datetime.now(timezone.utc)),
    )
    db.add(default_org)
    await db.commit()

    principal = await resolve_school_principal(_user(7, is_superadmin=True), db)

    assert principal.org_id == 100


@pytest.mark.asyncio
async def test_non_superadmin_with_no_grants_has_no_org(db):
    principal = await resolve_school_principal(_user(8), db)
    assert principal.org_id is None
