"""
Tests for the dev-only Keycloak token-minting utility (Step 0 of the CSG-LMS
frontend dashboard rewrite).

Covers:
  - `is_hmac_dev_verification_active()` (src/core/keycloak_auth.py): must be
    True for a local/dev-shaped config and False the instant anything looks
    like a real Keycloak deployment.
  - `mint_dev_keycloak_token()` (src/core/dev_tokens.py): must refuse to run
    outside HMAC/dev mode, reject unknown roles, and otherwise produce a
    token that `decode_and_verify_token` (the exact function every sms_*
    router authenticates through) accepts and resolves to the expected
    principal.
  - `POST /api/v1/dev/mint_keycloak_token` (src/routers/dev.py): superadmin
    gating and the same "inert outside dev mode" guarantee at the HTTP layer.

We deliberately use `monkeypatch.setenv`/`delenv` rather than patching
`settings.<property>` directly, since `KeycloakSettings`'s attributes are
read-only `@property` descriptors computed from `os.environ` -- patching env
vars exercises the real code path.
"""

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.core.dev_tokens import mint_dev_keycloak_token
from src.core.keycloak_auth import decode_and_verify_token, is_hmac_dev_verification_active
from src.db.users import PublicUser
from src.routers.dev import router as dev_router
from src.security.auth import get_authenticated_user


def _clear_keycloak_env(monkeypatch):
    for var in ("KEYCLOAK_JWKS_URL", "KEYCLOAK_PUBLIC_KEY", "KEYCLOAK_URL", "KEYCLOAK_SERVER_URL", "KEYCLOAK_SECRET_KEY", "AUTH_JWT_SECRET_KEY"):
        monkeypatch.delenv(var, raising=False)


class TestIsHmacDevVerificationActive:
    def test_true_for_default_localhost_config(self, monkeypatch):
        """No overrides at all -> server_url defaults to localhost:8080 -> dev mode active."""
        _clear_keycloak_env(monkeypatch)
        assert is_hmac_dev_verification_active() is True

    def test_true_for_explicit_localhost_server_url(self, monkeypatch):
        _clear_keycloak_env(monkeypatch)
        monkeypatch.setenv("KEYCLOAK_SERVER_URL", "http://localhost:8080")
        assert is_hmac_dev_verification_active() is True

    def test_false_when_jwks_url_explicitly_set(self, monkeypatch):
        """This is exactly what docker-compose.prod.yml / dokploy-compose.yml set for the real service."""
        _clear_keycloak_env(monkeypatch)
        monkeypatch.setenv("KEYCLOAK_JWKS_URL", "http://keycloak:8080/realms/csg-lms/protocol/openid-connect/certs")
        assert is_hmac_dev_verification_active() is False

    def test_false_when_public_key_pinned(self, monkeypatch):
        _clear_keycloak_env(monkeypatch)
        monkeypatch.setenv("KEYCLOAK_PUBLIC_KEY", "some-rsa-public-key-material")
        assert is_hmac_dev_verification_active() is False

    def test_false_when_server_url_is_docker_internal_hostname(self, monkeypatch):
        _clear_keycloak_env(monkeypatch)
        monkeypatch.setenv("KEYCLOAK_SERVER_URL", "http://keycloak:8080")
        assert is_hmac_dev_verification_active() is False

    def test_false_when_server_url_is_real_public_host(self, monkeypatch):
        _clear_keycloak_env(monkeypatch)
        monkeypatch.setenv("KEYCLOAK_URL", "https://auth.csginfotech.com")
        monkeypatch.setenv("KEYCLOAK_SERVER_URL", "https://auth.csginfotech.com")
        assert is_hmac_dev_verification_active() is False


class TestMintDevKeycloakToken:
    def test_raises_runtime_error_outside_dev_mode(self, monkeypatch):
        _clear_keycloak_env(monkeypatch)
        monkeypatch.setenv("KEYCLOAK_JWKS_URL", "http://keycloak:8080/realms/csg-lms/protocol/openid-connect/certs")

        with pytest.raises(RuntimeError):
            mint_dev_keycloak_token(role="TEACHER")

    def test_raises_value_error_on_unknown_role(self, monkeypatch):
        _clear_keycloak_env(monkeypatch)

        with pytest.raises(ValueError):
            mint_dev_keycloak_token(role="NOT_A_REAL_ROLE")

    def test_minted_token_is_well_formed(self, monkeypatch):
        _clear_keycloak_env(monkeypatch)
        result = mint_dev_keycloak_token(role="TEACHER", sub="teacher-42", org_id=3, campus_id=2)

        assert result["token_type"] == "Bearer"
        assert isinstance(result["access_token"], str) and result["access_token"].count(".") == 2
        assert result["claims"]["sub"] == "teacher-42"
        assert result["claims"]["realm_access"]["roles"] == ["TEACHER"]

    def test_minted_token_round_trips_through_real_decode_and_verify(self, monkeypatch):
        """
        The exact function every sms_* router authenticates through
        (get_current_user_principal -> decode_and_verify_token) must accept
        this token and resolve the expected principal -- this is the proof
        that the utility genuinely unblocks the authenticated SMS endpoints.
        """
        _clear_keycloak_env(monkeypatch)

        result = mint_dev_keycloak_token(
            role="TEACHER",
            sub="teacher-42",
            org_id=3,
            campus_id=2,
            subject_id=99,
        )

        principal = decode_and_verify_token(result["access_token"])

        assert principal.sub == "teacher-42"
        assert principal.org_id == 3
        assert principal.campus_id == 2
        assert principal.has_role("TEACHER") is True
        assert principal.is_superadmin is False
        # Dev convenience claim survives into raw_claims even though it's not
        # a typed KeycloakUserPrincipal field.
        assert principal.raw_claims["subject_id"] == 99

    def test_minted_token_rejected_once_pointed_at_real_keycloak(self, monkeypatch):
        """
        Defense in depth: even if somehow minted (e.g. a stale token from a
        previous dev session), decode_and_verify_token still requires the
        HS256 shared secret to match. Rotating KEYCLOAK_SECRET_KEY when going
        to a real deployment invalidates old dev tokens automatically.
        """
        _clear_keycloak_env(monkeypatch)
        result = mint_dev_keycloak_token(role="TEACHER")

        monkeypatch.setenv("KEYCLOAK_SECRET_KEY", "a-completely-different-production-secret")
        with pytest.raises(Exception):
            decode_and_verify_token(result["access_token"])

    def test_superadmin_role_mint_grants_superadmin_bypass(self, monkeypatch):
        _clear_keycloak_env(monkeypatch)
        result = mint_dev_keycloak_token(role="SUPER_ADMIN", sub="root-1")
        principal = decode_and_verify_token(result["access_token"])
        assert principal.is_superadmin is True


class TestMintKeycloakTokenEndpoint:
    @pytest.fixture
    def superadmin_user(self):
        return PublicUser(
            id=99,
            username="superadmin",
            first_name="Super",
            last_name="Admin",
            email="superadmin@test.com",
            user_uuid="user_superadmin",
            is_superadmin=True,
        )

    @pytest.fixture
    def non_admin_user(self):
        return PublicUser(
            id=5,
            username="regular",
            first_name="Regular",
            last_name="User",
            email="regular@test.com",
            user_uuid="user_regular",
            is_superadmin=False,
        )

    @pytest.fixture
    def app(self, superadmin_user):
        app = FastAPI()
        app.include_router(dev_router, prefix="/api/v1/dev")
        app.dependency_overrides[get_authenticated_user] = lambda: superadmin_user
        yield app
        app.dependency_overrides.clear()

    @pytest.fixture
    async def client(self, app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            yield c

    async def test_mints_token_for_superadmin_in_dev_mode(self, client, monkeypatch):
        _clear_keycloak_env(monkeypatch)
        response = await client.post(
            "/api/v1/dev/mint_keycloak_token",
            json={"role": "STUDENT", "sub": "student-1", "subject_id": 7},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["token_type"] == "Bearer"
        assert body["claims"]["subject_id"] == 7

        # Confirm it's actually usable against the real verifier.
        principal = decode_and_verify_token(body["access_token"])
        assert principal.has_role("STUDENT")

    async def test_rejects_non_superadmin(self, client, app, non_admin_user, monkeypatch):
        _clear_keycloak_env(monkeypatch)
        app.dependency_overrides[get_authenticated_user] = lambda: non_admin_user
        response = await client.post("/api/v1/dev/mint_keycloak_token", json={"role": "TEACHER"})
        assert response.status_code == 403

    async def test_returns_404_when_not_hmac_dev_mode(self, client, monkeypatch):
        _clear_keycloak_env(monkeypatch)
        monkeypatch.setenv("KEYCLOAK_JWKS_URL", "http://keycloak:8080/realms/csg-lms/protocol/openid-connect/certs")
        response = await client.post("/api/v1/dev/mint_keycloak_token", json={"role": "TEACHER"})
        assert response.status_code == 404

    async def test_rejects_unknown_role(self, client, monkeypatch):
        _clear_keycloak_env(monkeypatch)
        response = await client.post("/api/v1/dev/mint_keycloak_token", json={"role": "NOT_A_ROLE"})
        assert response.status_code == 422
