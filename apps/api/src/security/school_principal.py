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

from datetime import datetime, timedelta, timezone
from typing import Optional, Union

import jwt
from jwt.exceptions import PyJWTError
from fastapi import HTTPException, Request, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.keycloak_auth import SUPER_ADMIN, KeycloakUserPrincipal
from src.db.ems_roles import EMSRole
from src.db.organizations import Organization
from src.db.sms_identity import SMSUserRole
from src.db.users import APITokenUser, PublicUser, SuperadminAPITokenUser, User
from src.security.ems_rbac import (
    EMS_ASSIGNMENTS_CLAIM,
    EMS_ROLE_SLUGS_CLAIM,
    load_active_ems_assignments,
)
from src.security.security import ALGORITHM, SECRET_KEY

# ---------------------------------------------------------
# Superadmin impersonation (QA/demo tool)
# ---------------------------------------------------------
#
# Permanent, audited replacement for the old dev-only Keycloak-shaped-JWT
# minting mechanism (now fully removed -- see PROJECT_DOCS/ARCHITECTURE.md).
# A real superadmin, already authenticated via
# their own real Learnhouse session, can temporarily view the app AS a
# specific target user for QA/demo/support purposes -- NOT a new token type,
# and NOT a bypass of resolve_school_principal()'s normal resolution: the
# target's own SMSUserRole grants are what get resolved below, exactly as if
# the target had logged in themselves. See src/routers/sms_identity.py's
# POST /identity/impersonate and /identity/impersonate/stop.
#
# Signed with the exact same HS256 mechanism (SECRET_KEY/ALGORITHM from
# src.security.security) that src.security.auth already uses for the
# session/refresh/single-purpose JWTs (create_access_token, create_refresh_token)
# -- not a new signing scheme.
IMPERSONATION_COOKIE_NAME = "sms_impersonation"
IMPERSONATION_COOKIE_MAX_AGE_SECONDS = 2 * 60 * 60  # 2 hours
_IMPERSONATION_COOKIE_PURPOSE = "sms_impersonation"


def create_impersonation_cookie_value(*, actor_user_id: int, target_user_id: int) -> str:
    """Mint the signed, short-lived JWT stored in the `sms_impersonation` cookie."""
    now = datetime.now(timezone.utc)
    payload = {
        "purpose": _IMPERSONATION_COOKIE_PURPOSE,
        "actor_user_id": actor_user_id,
        "target_user_id": target_user_id,
        "iat": now,
        "exp": now + timedelta(seconds=IMPERSONATION_COOKIE_MAX_AGE_SECONDS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_impersonation_cookie(cookie_value: Optional[str]) -> Optional[dict]:
    """Verify and decode the `sms_impersonation` cookie value.

    Never raises: returns `None` for anything missing, malformed, expired, or
    signed with the wrong secret/purpose, so every caller fails SAFE (falls
    back to resolving the real, already-authenticated user) rather than
    erroring out.
    """
    if not cookie_value:
        return None
    try:
        payload = jwt.decode(
            cookie_value,
            SECRET_KEY,
            algorithms=[ALGORITHM],
            options={"require": ["exp", "iat", "target_user_id", "purpose"]},
        )
    except PyJWTError:
        return None
    if payload.get("purpose") != _IMPERSONATION_COOKIE_PURPOSE:
        return None
    return payload


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
    request: Optional[Request] = None,
) -> KeycloakUserPrincipal:
    """Builds the SMS auth principal for a real, already-authenticated Learnhouse user.

    Deliberately does NOT raise 403 for an authenticated user with zero
    `SMSUserRole` rows -- an empty role set is a valid, readable state (e.g.
    for GET /sms/me to report "you have no school role yet"). Route-level
    `require_roles()`/feature dependencies are still what enforce access.

    `request` is optional (and unused when omitted) so existing direct callers
    -- notably the unit tests in test_school_principal.py -- are unaffected.
    When provided, it is consulted ONLY for superadmin impersonation (see the
    module docstring above): if `current_user` (the REAL, already-authenticated
    caller) is a superadmin AND carries a valid `sms_impersonation` cookie, the
    principal is built from the target user's OWN grants instead. Any other
    combination (no cookie, invalid cookie, or a non-superadmin caller who
    somehow has the cookie) falls straight through to resolving `current_user`
    normally -- fail safe, never fail open.
    """
    effective_user: PublicUser
    impersonated_by_user_id: Optional[int] = None
    token_org_id: Optional[int] = None
    is_api_token = False
    api_token_scopes: list = []
    api_token_rights: Optional[dict] = None

    if isinstance(current_user, SuperadminAPITokenUser):
        is_api_token = True
        target = await db_session.get(User, current_user.created_by_user_id) if current_user.created_by_user_id else None
        if target is not None:
            effective_user = PublicUser(
                id=target.id,
                username=target.username,
                first_name=target.first_name,
                last_name=target.last_name,
                email=target.email,
                user_uuid=target.user_uuid,
                email_verified=target.email_verified,
                is_superadmin=True,
            )
        else:
            effective_user = PublicUser(
                id=1,
                username=current_user.username,
                first_name="Superadmin",
                last_name="API",
                user_uuid=current_user.user_uuid,
                is_superadmin=True,
            )
    elif isinstance(current_user, APITokenUser):
        is_api_token = True
        token_org_id = current_user.org_id
        api_token_scopes = current_user.scopes or []
        api_token_rights = current_user.rights
        target = await db_session.get(User, current_user.created_by_user_id) if current_user.created_by_user_id else None
        if target is not None:
            effective_user = PublicUser(
                id=target.id,
                username=target.username,
                first_name=target.first_name,
                last_name=target.last_name,
                email=target.email,
                user_uuid=target.user_uuid,
                email_verified=target.email_verified,
                is_superadmin=target.is_superadmin,
            )
        else:
            effective_user = PublicUser(
                id=0,
                username=current_user.username,
                first_name="API",
                last_name="Token",
                user_uuid=current_user.user_uuid,
                is_superadmin=False,
            )
    else:
        effective_user = current_user

    if request is not None and current_user.is_superadmin:
        payload = decode_impersonation_cookie(request.cookies.get(IMPERSONATION_COOKIE_NAME))
        if payload is not None:
            target_user_id = payload.get("target_user_id")
            target = await db_session.get(User, target_user_id) if target_user_id is not None else None
            if target is not None:
                effective_user = PublicUser(
                    id=target.id,
                    username=target.username,
                    first_name=target.first_name,
                    last_name=target.last_name,
                    email=target.email,
                    user_uuid=target.user_uuid,
                    email_verified=target.email_verified,
                    is_superadmin=target.is_superadmin,
                )
                impersonated_by_user_id = current_user.id

    result = await db_session.execute(
        select(SMSUserRole).where(SMSUserRole.user_id == effective_user.id, SMSUserRole.is_active == True)  # noqa: E712
    )
    grants = list(result.scalars().all())

    roles = {g.role.value if hasattr(g.role, "value") else str(g.role) for g in grants}
    if effective_user.is_superadmin:
        roles.add(SUPER_ADMIN)
    if is_api_token and not roles:
        roles.add(SCHOOL_ADMIN)

    org_id = next((g.org_id for g in grants if g.org_id), None)
    if token_org_id is not None:
        org_id = token_org_id
    campus_id = next((g.campus_id for g in grants if g.campus_id), None)
    if org_id is None and effective_user.is_superadmin:
        org_id = await _get_default_org_id(db_session)

    raw_claims: dict = {"lh_user_id": effective_user.id}
    if impersonated_by_user_id is not None:
        raw_claims["impersonated_by_user_id"] = impersonated_by_user_id
    if is_api_token:
        raw_claims["is_api_token"] = True
        raw_claims["token_scopes"] = api_token_scopes
        raw_claims["token_rights"] = api_token_rights

    # --- EMS (dynamic RBAC) assignments -----------------------------------
    #
    # `roles` above stays the LEGACY 7-value enum on purpose: it is what the
    # 262 `require_roles([...])` call sites match on, and widening it with EMS
    # slugs would silently open every one of those gates. EMS grants ride in
    # `raw_claims` instead, where `src/security/ems_rbac.py` reads them.
    #
    # The same loader the evaluator uses is called here so the principal and
    # `has_permission()` can never disagree about what a user holds: same org
    # and campus scoping, same expiry rule.
    ems_assignments = await load_active_ems_assignments(
        db_session,
        user_id=effective_user.id,
        org_id=org_id,
        campus_id=campus_id,
    )
    ems_descriptors: list = []
    ems_slugs: list = []
    for assignment in ems_assignments:
        role = await db_session.get(EMSRole, assignment.role_id)
        if role is None:
            continue
        ems_descriptors.append(
            {
                "assignment_id": assignment.id,
                "role_id": role.id,
                "role_slug": role.slug,
                "role_name": role.name,
                "is_clinical_specialist": bool(role.is_clinical_specialist),
                "org_id": assignment.org_id,
                "campus_id": assignment.campus_id,
                "department_id": assignment.department_id,
                "section_id": assignment.section_id,
                "expires_at": assignment.expires_at.isoformat() if assignment.expires_at else None,
            }
        )
        ems_slugs.append(role.slug)

    raw_claims[EMS_ASSIGNMENTS_CLAIM] = ems_descriptors
    raw_claims[EMS_ROLE_SLUGS_CLAIM] = ems_slugs

    return KeycloakUserPrincipal(
        sub=effective_user.user_uuid,
        email=getattr(effective_user, "email", None),
        preferred_username=getattr(effective_user, "username", None),
        given_name=getattr(effective_user, "first_name", None),
        family_name=getattr(effective_user, "last_name", None),
        name=" ".join(
            filter(None, [getattr(effective_user, "first_name", None), getattr(effective_user, "last_name", None)])
        )
        or None,
        org_id=org_id,
        campus_id=campus_id,
        realm_roles=sorted(roles),
        roles=roles,
        raw_claims=raw_claims,
    )
