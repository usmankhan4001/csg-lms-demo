"""
Auth Wiring Tests for the CSG-LMS SMS / RevOps Routers
=======================================================

Before this change, sms_attendance, sms_timetable, sms_gradebook, sms_fees,
sms_financials, sms_hr, sms_payroll, sms_library, and sms_revops had ZERO
authentication dependency -- any caller, logged in or not, could hit them.
sms_campus.py, ai_tutor.py, and ai_student_profile.py already required a
valid Keycloak OIDC Bearer token via `get_current_user_principal`.

These tests confirm each of the 9 routers now rejects an unauthenticated
request with 401, and that a caller presenting a valid Keycloak principal is
not blocked by the new dependency. Feature-toggle gating (require_<module>_feature)
is exercised separately in src/tests/security/test_feature_resolve.py, so it is
stubbed out here to isolate the auth check.
"""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.core.events.database import get_db_session
from src.core.keycloak_auth import KeycloakUserPrincipal, get_current_user_principal
from src.routers import (
    sms_attendance,
    sms_fees,
    sms_financials,
    sms_gradebook,
    sms_hr,
    sms_library,
    sms_payroll,
    sms_revops,
    sms_timetable,
)
from src.security.features_utils.dependencies import (
    require_revops_feature,
    require_sms_attendance_feature,
    require_sms_fees_feature,
    require_sms_financials_feature,
    require_sms_gradebook_feature,
    require_sms_hr_payroll_feature,
    require_sms_library_feature,
    require_sms_timetable_feature,
)

# (router module, mount prefix matching src/router.py, its feature-toggle
#  dependency, a GET path on it with no required params/body)
ROUTER_CASES = [
    pytest.param(
        sms_attendance.router, "/sms/attendance", require_sms_attendance_feature,
        "/sms/attendance/leave-requests", id="sms_attendance",
    ),
    pytest.param(
        sms_timetable.router, "/sms/timetable", require_sms_timetable_feature,
        "/sms/timetable/periods", id="sms_timetable",
    ),
    pytest.param(
        sms_gradebook.router, "/sms/gradebook", require_sms_gradebook_feature,
        "/sms/gradebook/scales", id="sms_gradebook",
    ),
    pytest.param(
        sms_fees.router, "/sms/fees", require_sms_fees_feature,
        "/sms/fees/structures", id="sms_fees",
    ),
    pytest.param(
        sms_financials.router, "/sms/financials", require_sms_financials_feature,
        "/sms/financials/accounts", id="sms_financials",
    ),
    pytest.param(
        sms_hr.router, "/sms/hr", require_sms_hr_payroll_feature,
        "/sms/hr/staff", id="sms_hr",
    ),
    pytest.param(
        sms_payroll.router, "/sms/payroll", require_sms_hr_payroll_feature,
        "/sms/payroll/slips", id="sms_payroll",
    ),
    pytest.param(
        sms_library.router, "/sms/library", require_sms_library_feature,
        "/sms/library/books", id="sms_library",
    ),
    pytest.param(
        sms_revops.router, "/revops", require_revops_feature,
        "/revops/leads", id="sms_revops",
    ),
]


def _make_app(db, router, prefix, feature_dependency):
    app = FastAPI()
    app.include_router(router, prefix=prefix)
    app.dependency_overrides[get_db_session] = lambda: db
    # Stub the feature-toggle dependency so this suite only exercises auth.
    app.dependency_overrides[feature_dependency] = lambda: True
    return app


@pytest.mark.asyncio
@pytest.mark.parametrize("router,prefix,feature_dependency,path", ROUTER_CASES)
async def test_router_rejects_unauthenticated_request(db, router, prefix, feature_dependency, path):
    """Every previously-open SMS/RevOps router must 401 a request with no Bearer token."""
    app = _make_app(db, router, prefix, feature_dependency)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(path)

    assert response.status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize("router,prefix,feature_dependency,path", ROUTER_CASES)
async def test_router_allows_authenticated_request(db, router, prefix, feature_dependency, path):
    """A caller with a valid Keycloak principal is not blocked by the new auth dependency."""
    principal = KeycloakUserPrincipal(
        sub="tester-1",
        email="tester@csg.edu",
        org_id=1,
        campus_id=1,
        roles={"SUPER_ADMIN"},
    )
    app = _make_app(db, router, prefix, feature_dependency)
    app.dependency_overrides[get_current_user_principal] = lambda: principal

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(path)

    assert response.status_code == 200
