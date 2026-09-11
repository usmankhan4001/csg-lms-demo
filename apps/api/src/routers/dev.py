import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from config.config import get_learnhouse_config
from migrations.orgconfigs.orgconfigs_migrations import migrate_to_v1_1, migrate_to_v1_2, migrate_v0_to_v1
from src.core.dev_tokens import mint_dev_keycloak_token
from src.core.events.database import get_db_session
from src.db.organization_config import OrganizationConfig
from src.db.users import PublicUser
from src.security.auth import get_authenticated_user

logger = logging.getLogger(__name__)


router = APIRouter()


def _require_superadmin(current_user: PublicUser):
    """Require superadmin access for dev endpoints."""
    if not hasattr(current_user, 'is_superadmin') or not current_user.is_superadmin:
        raise HTTPException(status_code=403, detail="Superadmin access required")


@router.get(
    "/config",
    summary="Get LearnHouse runtime config",
    description="Returns the current LearnHouse configuration with sensitive values redacted. Restricted to superadmin users.",
    responses={
        200: {"description": "Configuration dictionary with secrets redacted"},
        401: {"description": "Authentication required"},
        403: {"description": "Superadmin access required"},
    },
)
async def config(
    current_user: PublicUser = Depends(get_authenticated_user),
):
    _require_superadmin(current_user)
    config = get_learnhouse_config()
    config_dict = config.model_dump()

    # Redact sensitive values
    _redact_secrets(config_dict)
    return config_dict


def _redact_secrets(d: dict, _sensitive_keys=None):
    """Recursively redact values for keys that look like secrets."""
    if _sensitive_keys is None:
        _sensitive_keys = {
            "password", "secret", "token", "key", "api_key", "api_secret",
            "connection_string", "redis_connection_string", "database_url",
            "ingest_token", "read_token", "write_token", "webhook_secret",
            "client_secret", "private_key",
        }
    for k, v in d.items():
        if isinstance(v, dict):
            _redact_secrets(v, _sensitive_keys)
        elif isinstance(v, str) and any(s in k.lower() for s in _sensitive_keys):
            if v:
                d[k] = v[:4] + "***REDACTED***"


@router.post(
    "/migrate_orgconfig_v0_to_v1",
    summary="Migrate organization config v0 to v1",
    description="Runs the v0 to v1 schema migration across every organization's configuration. Restricted to superadmin users.",
    responses={
        200: {"description": "Migration completed successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Superadmin access required"},
    },
)
async def migrate(
    db_session: AsyncSession = Depends(get_db_session),
    current_user: PublicUser = Depends(get_authenticated_user),
):
    """
    Migrate organization config from v0 to v1
    """
    _require_superadmin(current_user)
    statement = select(OrganizationConfig)
    result = (await db_session.execute(statement)).scalars().all()

    for orgConfig in result:
        orgConfig.config = migrate_v0_to_v1(orgConfig.config)

        db_session.add(orgConfig)
        await db_session.commit()

    return {"message": "Migration successful"}


@router.post(
    "/migrate_orgconfig_v1_to_v1.1",
    summary="Migrate organization config v1 to v1.1",
    description="Runs the v1 to v1.1 schema migration across every organization's configuration. Restricted to superadmin users.",
    responses={
        200: {"description": "Migration completed successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Superadmin access required"},
    },
)
async def migratev1_1(
    db_session: AsyncSession = Depends(get_db_session),
    current_user: PublicUser = Depends(get_authenticated_user),
):
    """
    Migrate organization config from v1 to v1.1
    """
    _require_superadmin(current_user)
    statement = select(OrganizationConfig)
    result = (await db_session.execute(statement)).scalars().all()

    for orgConfig in result:
        orgConfig.config = migrate_to_v1_1(orgConfig.config)

        db_session.add(orgConfig)
        await db_session.commit()

    return {"message": "Migration successful"}

@router.post(
    "/migrate_orgconfig_v1_to_v1.2",
    summary="Migrate organization config v1 to v1.2",
    description="Runs the v1 to v1.2 schema migration across every organization's configuration. Restricted to superadmin users.",
    responses={
        200: {"description": "Migration completed successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Superadmin access required"},
    },
)
async def migratev1_2(
    db_session: AsyncSession = Depends(get_db_session),
    current_user: PublicUser = Depends(get_authenticated_user),
):
    """
    Migrate organization config from v1 to v1.2
    """
    _require_superadmin(current_user)
    statement = select(OrganizationConfig)
    result = (await db_session.execute(statement)).scalars().all()

    for orgConfig in result:
        orgConfig.config = migrate_to_v1_2(orgConfig.config)

        db_session.add(orgConfig)
        await db_session.commit()

    return {"message": "Migration successful"}


# ---------------------------------------------------------
# Dev-only Keycloak token minting
# ---------------------------------------------------------
# See src/core/dev_tokens.py for the full rationale: no real Keycloak server
# has ever been deployed for this project, and the SMS/RevOps routers require
# a Keycloak-shaped Bearer JWT. This mints one locally using the same HS256
# shared secret `keycloak_auth.decode_and_verify_token` already falls back to.


class MintKeycloakTokenRequest(BaseModel):
    role: str = Field(
        default="SCHOOL_ADMIN",
        description="Primary realm role: SUPER_ADMIN, SCHOOL_ADMIN, TEACHER, STUDENT, PARENT, STAFF, or PSYCHOLOGIST.",
    )
    sub: str = Field(default="dev-user-1", description="Keycloak subject / user UUID to embed")
    email: Optional[str] = Field(default="dev@csg.edu.pk")
    name: Optional[str] = Field(default="Dev Tester")
    org_id: Optional[int] = Field(default=1)
    campus_id: Optional[int] = Field(default=1)
    subject_id: Optional[int] = Field(
        default=1,
        description="Dev convenience claim used by the frontend as 'my' student_id/staff_id/teacher_id (see mint_dev_keycloak_token docstring).",
    )
    section_id: Optional[int] = Field(default=1)
    academic_term_id: Optional[int] = Field(default=1)
    children_ids: Optional[List[int]] = Field(default=None, description="For PARENT tokens: the student_ids of this parent's children.")
    expires_in_minutes: int = Field(default=480, ge=1, le=1440)


class MintKeycloakTokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    claims: Dict[str, Any]


@router.post(
    "/mint_keycloak_token",
    response_model=MintKeycloakTokenResponse,
    summary="[DEV ONLY] Mint an HMAC-signed Keycloak-shaped JWT for local testing",
    description="""
    Mints a locally-valid, Keycloak-shaped Bearer JWT so the SMS/RevOps
    routers (which require `get_current_user_principal`) can be exercised
    end-to-end without a real Keycloak deployment.

    Layered safety (all four must pass):
      1. This whole router is only mounted when `LEARNHOUSE_DEVELOPMENT_MODE`
         is true (`isDevModeEnabledOrRaise`, see src/router.py).
      2. The caller must have a real, non-API-token Learnhouse session
         (`get_non_api_token_user`, also at the router mount).
      3. `_require_superadmin` below requires that session to be a superadmin.
      4. `mint_dev_keycloak_token` independently refuses (404 here) the
         instant this deployment looks like it is pointed at a real Keycloak
         server -- see `is_hmac_dev_verification_active` in
         src/core/keycloak_auth.py. This makes the endpoint inert in any real
         deployment even if step 1 were mistakenly left on.

    Usage: log in to the Learnhouse app as a superadmin, then:
      curl -X POST http://localhost:1338/api/v1/dev/mint_keycloak_token \\
        -H "Authorization: Bearer <learnhouse_session_token>" \\
        -H "Content-Type: application/json" \\
        -d '{"role": "TEACHER", "org_id": 1, "campus_id": 1, "subject_id": 1}'

    Take the returned `access_token` and send it as
    `Authorization: Bearer <access_token>` to any `/api/v1/sms/*` or
    `/api/v1/revops/*` endpoint. See apps/web/lib/api/dev-token.ts and
    apps/web/lib/api/api-client.ts for how the frontend stores/attaches it.
    """,
    responses={
        200: {"description": "Minted Keycloak-shaped JWT"},
        401: {"description": "Authentication required"},
        403: {"description": "Superadmin access required"},
        404: {"description": "Not found (this deployment is not configured for HMAC/dev Keycloak verification)"},
        422: {"description": "Unknown role"},
    },
)
async def mint_keycloak_token(
    payload: MintKeycloakTokenRequest,
    current_user: PublicUser = Depends(get_authenticated_user),
):
    _require_superadmin(current_user)

    try:
        minted = mint_dev_keycloak_token(
            role=payload.role,
            sub=payload.sub,
            email=payload.email,
            name=payload.name,
            org_id=payload.org_id,
            campus_id=payload.campus_id,
            subject_id=payload.subject_id,
            section_id=payload.section_id,
            academic_term_id=payload.academic_term_id,
            children_ids=payload.children_ids,
            expires_in_minutes=payload.expires_in_minutes,
        )
    except RuntimeError:
        # Deliberately 404, not 403: a real deployment should not even reveal
        # that this capability exists.
        raise HTTPException(status_code=404, detail="Not found")
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return MintKeycloakTokenResponse(**minted)
