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
mounts it) to prove each of the 8 affected routers is reachable given only a
real, authenticated Learnhouse session -- matching every one of their
handlers' own `get_current_user_principal` dependency.

`sms_revops.py` had the identical double-gate bug (confirmed: every one of
its handlers already has its own `get_current_user_principal` dependency,
same as the 8 routers above) and is now covered by the same fix + test below.

`live_classes.py` is deliberately NOT covered here and must not be "fixed"
the same way: unlike every other router in this list, none of its handlers
have a per-handler Keycloak dependency at all -- the router-mount-level
`require_authenticated_user_or_api_token` wrapper is its ONLY auth gate, not
a redundant second one. Removing it would leave the router unauthenticated.

NOTE on the auth mechanism itself: `get_current_user_principal` no longer
decodes a Keycloak-shaped JWT at all -- it derives a `KeycloakUserPrincipal`
from a real, already-authenticated Learnhouse user via
`src/security/school_principal.py` (see that module and
`src/tests/security/test_school_principal.py` for the principal-construction
tests). This file only proves ROUTER REACHABILITY given a real session; it
overrides `get_authenticated_user` directly rather than performing a real
login, since a real login is out of scope for a router-mount regression test.
"""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.core.events.database import get_db_session
from src.db.users import PublicUser
from src.router import v1_router
from src.security.auth import get_authenticated_user
from src.security.features_utils.dependencies import (
    require_revops_feature,
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
    pytest.param(
        "/api/v1/revops/leads/pipeline", require_revops_feature,
        id="sms_revops",
    ),
]


def _make_app(db):
    app = FastAPI()
    app.include_router(v1_router)
    app.dependency_overrides[get_db_session] = lambda: db
    return app


def _stub_superadmin() -> PublicUser:
    """A real Learnhouse user (superadmin, so no SMSUserRole row is needed to
    satisfy any of these routers' RBAC/feature checks) -- overridden in place
    of a real login, since this test proves router reachability, not login."""
    return PublicUser(
        id=1,
        user_uuid="test-superadmin-uuid",
        username="test-superadmin",
        first_name="Test",
        last_name="Superadmin",
        email="test-superadmin@example.com",
        is_superadmin=True,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("path,feature_dependency", ROUTER_CASES)
async def test_authenticated_learnhouse_session_reaches_the_really_mounted_router(db, path, feature_dependency):
    """A real, authenticated Learnhouse session -- no Keycloak JWT involved at all -- must be sufficient."""
    app = _make_app(db)
    app.dependency_overrides[feature_dependency] = lambda: True
    app.dependency_overrides[get_authenticated_user] = _stub_superadmin

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(path)

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
