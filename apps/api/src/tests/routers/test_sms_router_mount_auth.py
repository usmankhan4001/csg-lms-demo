"""
Regression test for a router-mount double-auth-gate bug found while wiring
the CSG-LMS frontend dashboards to real data (Step 0 of that task).

Before this fix, `src/router.py` mounted 8 of the 9 SMS/RevOps routers
(everything except `sms_campus.py`) with BOTH:
  - a router-mount-level `dependencies=[Depends(require_authenticated_user_or_api_token)]`
    (Learnhouse's own native session/API-token auth, `src/security/auth.py`), AND
  - a per-handler `Depends(get_current_user_principal)` (Keycloak OIDC,
    `src/core/keycloak_auth.py`) inside every single endpoint of those files.

Both dependencies read the *same* `Authorization: Bearer <token>` header but
expect mutually incompatible token shapes/secrets, so a request could never
satisfy both -- these routers were unreachable over HTTP by any caller.
`src/tests/sms/test_sms_auth.py` didn't catch this because it mounts each
router standalone (bypassing this file's router-level wrapper entirely), so
it only ever exercised the per-handler Keycloak gate in isolation.

This test mounts the REAL `v1_router` from `src.router` (exactly how `app.py`
mounts it) and sends a request carrying ONLY a Keycloak-shaped Bearer token
-- no Learnhouse session, cookie, or API token -- to prove each of the 8
affected routers is now reachable that way, matching every one of their
handlers' own `get_current_user_principal` dependency. `sms_revops.py` and
`live_classes.py` are deliberately NOT covered here: they still carry the
Learnhouse-native wrapper unchanged (left alone -- see the AGENT scope
boundary on not touching AI RevOps/Tutor-adjacent code), so are out of scope
for this particular regression.
"""

import jwt
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.core.events.database import get_db_session
from src.core.keycloak_auth import settings as keycloak_settings
from src.router import v1_router
from src.security.features_utils.dependencies import (
    require_sms_attendance_feature,
    require_sms_fees_feature,
    require_sms_financials_feature,
    require_sms_gradebook_feature,
    require_sms_hr_payroll_feature,
    require_sms_library_feature,
    require_sms_timetable_feature,
    require_tutor_counseling_feature,
)

ROUTER_CASES = [
    pytest.param("/api/v1/sms/attendance/leave-requests", require_sms_attendance_feature, id="sms_attendance"),
    pytest.param("/api/v1/sms/timetable/periods", require_sms_timetable_feature, id="sms_timetable"),
    pytest.param("/api/v1/sms/gradebook/scales", require_sms_gradebook_feature, id="sms_gradebook"),
    pytest.param("/api/v1/sms/fees/structures", require_sms_fees_feature, id="sms_fees"),
    pytest.param("/api/v1/sms/financials/accounts", require_sms_financials_feature, id="sms_financials"),
    pytest.param("/api/v1/sms/hr/staff", require_sms_hr_payroll_feature, id="sms_hr"),
    pytest.param("/api/v1/sms/payroll/slips", require_sms_hr_payroll_feature, id="sms_payroll"),
    pytest.param("/api/v1/sms/library/books", require_sms_library_feature, id="sms_library"),
    # Phase 4: new sms_counseling module + sms_teacher_tools (which reuses
    # the sms_gradebook toggle -- see src/routers/sms_teacher_tools.py).
    pytest.param(
        "/api/v1/sms/counseling/activity-logs/student/1", require_tutor_counseling_feature,
        id="sms_counseling",
    ),
    pytest.param(
        "/api/v1/sms/teacher-tools/lesson-plans", require_sms_gradebook_feature,
        id="sms_teacher_tools",
    ),
]


def _make_app(db):
    app = FastAPI()
    app.include_router(v1_router)
    app.dependency_overrides[get_db_session] = lambda: db
    return app


def _keycloak_only_token() -> str:
    """A minimal, realistically-shaped Keycloak HS256 token -- no Learnhouse claims at all."""
    claims = {"sub": "integration-test-user", "realm_access": {"roles": ["SUPER_ADMIN"]}}
    if keycloak_settings.issuer:
        claims["iss"] = keycloak_settings.issuer
    return jwt.encode(claims, keycloak_settings.shared_secret, algorithm="HS256")


@pytest.mark.asyncio
@pytest.mark.parametrize("path,feature_dependency", ROUTER_CASES)
async def test_keycloak_only_bearer_reaches_the_really_mounted_router(db, path, feature_dependency, monkeypatch):
    """A Keycloak-only Bearer token -- no Learnhouse session/cookie/API token -- must be sufficient."""
    monkeypatch.delenv("KEYCLOAK_JWKS_URL", raising=False)
    monkeypatch.delenv("KEYCLOAK_PUBLIC_KEY", raising=False)

    app = _make_app(db)
    app.dependency_overrides[feature_dependency] = lambda: True
    token = _keycloak_only_token()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(path, headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200, response.text


@pytest.mark.asyncio
@pytest.mark.parametrize("path,feature_dependency", ROUTER_CASES)
async def test_still_rejects_a_request_with_no_token_at_all(db, path, feature_dependency):
    """The fix removes the redundant Learnhouse-native gate -- it must not remove auth entirely."""
    app = _make_app(db)
    app.dependency_overrides[feature_dependency] = lambda: True

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(path)

    assert response.status_code == 401
