"""
Builds a `KeycloakUserPrincipal` from a real, already-authenticated
Learnhouse user instead of decoding a separate Keycloak-shaped JWT.

Why this exists: no real Keycloak server has ever been deployed for this
project, but the 12 SMS/RevOps/Tutor routers were built against a
`KeycloakUserPrincipal` dependency. Rather than standing up a real Keycloak
server, this derives the same object from Learnhouse's own real session plus
`SMSUserRole` (src/db/sms_identity.py) -- the school-specific claims a real
Keycloak realm would have carried. See PROJECT_DOCS/ARCHITECTURE.md for the
full background.

`KeycloakUserPrincipal`'s shape/methods are preserved exactly (`sub`,
`org_id`, `campus_id`, `roles`, `has_role()`, `is_superadmin`, ...) so the
~90+ existing call sites across the SMS routers and services need zero
changes -- only how the principal gets CONSTRUCTED changes.
"""

from typing import Optional, Union

from fastapi import HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.keycloak_auth import SUPER_ADMIN, KeycloakUserPrincipal
from src.db.organizations import Organization
from src.db.sms_identity import SMSUserRole
from src.db.users import APITokenUser, PublicUser, SuperadminAPITokenUser


async def _get_default_org_id(db_session: AsyncSession) -> Optional[int]:
    """Mirrors src/routers/instance.py's default-org resolution (slug 'default',
    else the first org by id) -- duplicated rather than imported to keep this
    security module independent of a router file."""
    result = await db_session.execute(select(Organization).where(Organization.slug == "default"))
    org = result.scalar_one_or_none()
    if org is None:
        result = await db_session.execute(select(Organization).order_by(Organization.id).limit(1))
        org = result.scalar_one_or_none()
    return org.id if org else None


async def resolve_school_principal(
    current_user: Union[PublicUser, APITokenUser, SuperadminAPITokenUser],
    db_session: AsyncSession,
) -> KeycloakUserPrincipal:
    """Builds the SMS auth principal for a real, already-authenticated Learnhouse user.

    Deliberately does NOT raise 403 for an authenticated user with zero
    `SMSUserRole` rows -- an empty role set is a valid, readable state (e.g.
    for GET /sms/me to report "you have no school role yet"). Route-level
    `require_roles()`/feature dependencies are still what enforce access.
    """
    if isinstance(current_user, (APITokenUser, SuperadminAPITokenUser)):
        # API tokens have no school-role concept -- there was never a way to
        # mint a Keycloak-shaped token for one either, so this is not a
        # regression, just made explicit rather than silently mismatched.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API tokens are not supported for SMS endpoints",
        )

    result = await db_session.execute(
        select(SMSUserRole).where(SMSUserRole.user_id == current_user.id, SMSUserRole.is_active == True)  # noqa: E712
    )
    grants = list(result.scalars().all())

    roles = {g.role.value if hasattr(g.role, "value") else str(g.role) for g in grants}
    if current_user.is_superadmin:
        roles.add(SUPER_ADMIN)

    org_id = next((g.org_id for g in grants if g.org_id), None)
    campus_id = next((g.campus_id for g in grants if g.campus_id), None)
    if org_id is None and current_user.is_superadmin:
        org_id = await _get_default_org_id(db_session)

    return KeycloakUserPrincipal(
        sub=current_user.user_uuid,
        email=getattr(current_user, "email", None),
        preferred_username=getattr(current_user, "username", None),
        given_name=getattr(current_user, "first_name", None),
        family_name=getattr(current_user, "last_name", None),
        name=" ".join(
            filter(None, [getattr(current_user, "first_name", None), getattr(current_user, "last_name", None)])
        )
        or None,
        org_id=org_id,
        campus_id=campus_id,
        realm_roles=sorted(roles),
        roles=roles,
        raw_claims={"lh_user_id": current_user.id},
    )
