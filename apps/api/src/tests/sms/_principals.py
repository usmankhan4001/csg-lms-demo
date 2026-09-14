"""Real principals for tests that call route handlers directly.

These tests invoke handler functions as plain coroutines, so FastAPI's
dependency injection never runs and a `Depends(...)` default arrives as an
unresolved `Depends` object -- which is why adding `require_roles` to the
school routers surfaced as `AttributeError: 'Depends' object has no attribute
'is_superadmin'` rather than as an authorization failure.

Uses the real `KeycloakUserPrincipal` rather than a stand-in, so the role
predicates under test are the production ones.

These exist to let a test reach the code it is actually about. Tests that
assert authorization itself should build a principal with the specific roles
they mean -- see `test_sms_fees.py` and `test_live_class_token_privilege.py`.
"""

from src.core.keycloak_auth import KeycloakUserPrincipal


def principal(*roles: str, user_id: int = 1, org_id: int = 1, campus_id: int | None = 1):
    """A principal holding exactly `roles`."""
    return KeycloakUserPrincipal(
        sub=f"test-user-{user_id}",
        email=f"user{user_id}@test.local",
        org_id=org_id,
        campus_id=campus_id,
        realm_roles=list(roles),
        roles=set(roles),
        raw_claims={"lh_user_id": user_id},
    )


# A super admin: satisfies every `require_roles` gate. Use for tests whose
# subject is the module's behaviour, not who may call it.
SUPERADMIN = principal("SUPER_ADMIN")
SCHOOL_ADMIN = principal("SCHOOL_ADMIN")
STAFF = principal("STAFF")
TEACHER = principal("TEACHER")
