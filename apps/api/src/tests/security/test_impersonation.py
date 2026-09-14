"""
Tests for the permanent, audited superadmin impersonation feature that
replaces the now fully-removed dev-only Keycloak-shaped-JWT minting mechanism
(the module and endpoint it lived in have been deleted entirely).

Covers:
  - `resolve_school_principal()`'s cookie handling (src/security/school_principal.py):
    a superadmin with a valid `sms_impersonation` cookie resolves the TARGET
    user's own principal (their own SMSUserRole grants), a non-superadmin's
    cookie is ignored (fail safe), and omitting `request` entirely stays
    backward compatible with existing call sites.
  - `POST /sms/identity/impersonate` and `POST /sms/identity/impersonate/stop`
    (src/routers/sms_identity.py): superadmin-only gating, 404 on an unknown
    target, the cookie round-tripping through a real HTTP client so a
    *subsequent* request resolves as the target, `stop` reverting to the real
    user, and both actions writing an audited `SMSImpersonationEvent` row with
    the correct actor/target/action.
"""

from datetime import datetime

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlmodel import select

from src.core.events.database import get_db_session
from src.db.sms_identity import SMSImpersonationEvent, SMSUserRole, SchoolRole
from src.db.users import PublicUser, User
from src.router import v1_router
from src.security.auth import get_authenticated_user
from src.security.school_principal import (
    IMPERSONATION_COOKIE_NAME,
    create_impersonation_cookie_value,
    resolve_school_principal,
)


def _public_user(id_: int, *, is_superadmin: bool = False) -> PublicUser:
    return PublicUser(
        id=id_,
        username=f"user{id_}",
        first_name="Test",
        last_name=f"User{id_}",
        email=f"user{id_}@test.com",
        user_uuid=f"uuid-{id_}",
        is_superadmin=is_superadmin,
    )


async def _add_db_user(db, id_: int, *, is_superadmin: bool = False) -> User:
    """Insert a real `User` row -- impersonation resolves the TARGET from the
    database (src.db.users.User), not from a caller-supplied PublicUser."""
    u = User(
        id=id_,
        username=f"dbuser{id_}",
        first_name="Target",
        last_name=f"User{id_}",
        email=f"dbuser{id_}@test.com",
        password="hashed_password",
        user_uuid=f"db-uuid-{id_}",
        is_superadmin=is_superadmin,
        creation_date=str(datetime.now()),
        update_date=str(datetime.now()),
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


def _make_app(db, current_user) -> FastAPI:
    app = FastAPI()
    app.include_router(v1_router)
    app.dependency_overrides[get_db_session] = lambda: db
    app.dependency_overrides[get_authenticated_user] = lambda: current_user
    return app


class _FakeRequest:
    """Minimal stand-in for `fastapi.Request` -- `resolve_school_principal`
    only ever reads `.cookies.get(...)` off it."""

    def __init__(self, cookies: dict | None = None):
        self.cookies = cookies or {}


# ---------------------------------------------------------
# Unit-level: resolve_school_principal's cookie handling
# ---------------------------------------------------------


@pytest.mark.asyncio
async def test_superadmin_with_valid_cookie_resolves_as_target(db, org):
    target = await _add_db_user(db, 50)
    db.add(SMSUserRole(user_id=target.id, org_id=org.id, role=SchoolRole.TEACHER, campus_id=7))
    await db.commit()

    superadmin = _public_user(1, is_superadmin=True)
    cookie_value = create_impersonation_cookie_value(actor_user_id=superadmin.id, target_user_id=target.id)
    request = _FakeRequest({IMPERSONATION_COOKIE_NAME: cookie_value})

    principal = await resolve_school_principal(superadmin, db, request)

    assert principal.sub == target.user_uuid
    assert principal.email == target.email
    assert "TEACHER" in principal.roles
    assert principal.campus_id == 7
    assert principal.raw_claims["lh_user_id"] == target.id
    assert principal.raw_claims["impersonated_by_user_id"] == superadmin.id


@pytest.mark.asyncio
async def test_non_superadmin_cookie_is_ignored(db, org):
    """Even if a non-superadmin somehow carries the cookie, it must be
    ignored -- fail safe, not fail open."""
    target = await _add_db_user(db, 51)
    db.add(SMSUserRole(user_id=target.id, org_id=org.id, role=SchoolRole.TEACHER))
    await db.commit()

    non_admin = _public_user(2, is_superadmin=False)
    cookie_value = create_impersonation_cookie_value(actor_user_id=999, target_user_id=target.id)
    request = _FakeRequest({IMPERSONATION_COOKIE_NAME: cookie_value})

    principal = await resolve_school_principal(non_admin, db, request)

    assert principal.sub == non_admin.user_uuid
    assert principal.email == non_admin.email
    assert "impersonated_by_user_id" not in principal.raw_claims


@pytest.mark.asyncio
async def test_no_cookie_resolves_real_user_normally(db):
    superadmin = _public_user(3, is_superadmin=True)
    principal = await resolve_school_principal(superadmin, db, _FakeRequest({}))
    assert principal.sub == superadmin.user_uuid
    assert principal.is_superadmin


@pytest.mark.asyncio
async def test_invalid_cookie_signature_is_ignored(db, org):
    target = await _add_db_user(db, 52)
    superadmin = _public_user(4, is_superadmin=True)
    request = _FakeRequest({IMPERSONATION_COOKIE_NAME: "not-a-real-jwt"})

    principal = await resolve_school_principal(superadmin, db, request)

    assert principal.sub == superadmin.user_uuid


@pytest.mark.asyncio
async def test_request_omitted_is_backward_compatible(db):
    """Existing call sites (and the pre-existing test_school_principal.py
    suite) that don't pass `request` at all must keep working unchanged."""
    superadmin = _public_user(5, is_superadmin=True)
    principal = await resolve_school_principal(superadmin, db)
    assert principal.sub == superadmin.user_uuid


# ---------------------------------------------------------
# Router-level: POST /identity/impersonate and /identity/impersonate/stop
# ---------------------------------------------------------


@pytest.mark.asyncio
async def test_start_impersonation_sets_cookie_and_writes_audit_event(db, org):
    target = await _add_db_user(db, 60)
    superadmin = _public_user(10, is_superadmin=True)
    app = _make_app(db, superadmin)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/sms/identity/impersonate", json={"target_user_id": target.id})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == target.id
    assert body["email"] == target.email
    assert IMPERSONATION_COOKIE_NAME in response.cookies

    events = (
        (await db.execute(select(SMSImpersonationEvent).where(SMSImpersonationEvent.target_user_id == target.id)))
        .scalars()
        .all()
    )
    assert len(events) == 1
    assert events[0].actor_user_id == superadmin.id
    assert events[0].target_user_id == target.id
    assert events[0].action == "start"


@pytest.mark.asyncio
async def test_non_superadmin_cannot_start_impersonation(db):
    non_admin = _public_user(11, is_superadmin=False)
    app = _make_app(db, non_admin)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/sms/identity/impersonate", json={"target_user_id": 999})

    assert response.status_code == 403

    events = (await db.execute(select(SMSImpersonationEvent))).scalars().all()
    assert events == []


@pytest.mark.asyncio
async def test_start_impersonation_404_for_unknown_target(db):
    superadmin = _public_user(12, is_superadmin=True)
    app = _make_app(db, superadmin)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/sms/identity/impersonate", json={"target_user_id": 999999})

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_subsequent_request_resolves_as_target_then_stop_reverts(db, org):
    target = await _add_db_user(db, 61)
    db.add(SMSUserRole(user_id=target.id, org_id=org.id, role=SchoolRole.TEACHER, campus_id=3))
    await db.commit()

    superadmin = _public_user(13, is_superadmin=True)
    app = _make_app(db, superadmin)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        start_resp = await client.post("/api/v1/sms/identity/impersonate", json={"target_user_id": target.id})
        assert start_resp.status_code == 200

        # httpx's client-side cookie jar carries the Set-Cookie from the start
        # response onto this NEXT request automatically, exactly like a browser.
        me_resp = await client.get("/api/v1/sms/me")
        assert me_resp.status_code == 200
        me_body = me_resp.json()
        assert me_body["email"] == target.email
        assert "TEACHER" in me_body["roles"]
        assert me_body["campus_id"] == 3

        stop_resp = await client.post("/api/v1/sms/identity/impersonate/stop")
        assert stop_resp.status_code == 204

        me_after_stop = await client.get("/api/v1/sms/me")
        assert me_after_stop.status_code == 200
        assert me_after_stop.json()["email"] == superadmin.email

    stop_events = (
        (
            await db.execute(
                select(SMSImpersonationEvent).where(
                    SMSImpersonationEvent.target_user_id == target.id,
                    SMSImpersonationEvent.action == "stop",
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(stop_events) == 1
    assert stop_events[0].actor_user_id == superadmin.id

    all_events = (
        (await db.execute(select(SMSImpersonationEvent).where(SMSImpersonationEvent.target_user_id == target.id)))
        .scalars()
        .all()
    )
    assert sorted(e.action for e in all_events) == ["start", "stop"]


@pytest.mark.asyncio
async def test_stop_without_cookie_is_a_noop_not_an_error(db):
    non_admin = _public_user(14, is_superadmin=False)
    app = _make_app(db, non_admin)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/sms/identity/impersonate/stop")

    assert response.status_code == 204

    events = (await db.execute(select(SMSImpersonationEvent))).scalars().all()
    assert events == []


@pytest.mark.asyncio
async def test_stop_with_garbage_cookie_is_a_noop_not_an_error(db):
    non_admin = _public_user(15, is_superadmin=False)
    app = _make_app(db, non_admin)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.cookies.set(IMPERSONATION_COOKIE_NAME, "garbage-not-a-jwt")
        response = await client.post("/api/v1/sms/identity/impersonate/stop")

    assert response.status_code == 204

    events = (await db.execute(select(SMSImpersonationEvent))).scalars().all()
    assert events == []
