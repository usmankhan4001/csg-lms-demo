"""
Keycloak 24 OIDC Authentication & JWT Token Verification
=========================================================
Provides robust OIDC Bearer token verification, claims extraction,
multi-campus tenancy parsing, and role-based access control (RBAC)
for CSG-LMS FastAPI services.

Compliant with ISO 27001 audit controls, FERPA/COPPA child data safety,
and multi-campus isolation requirements.
"""

import os
import logging
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Union
from datetime import datetime, timezone
from enum import Enum
import jwt
from jwt.exceptions import PyJWTError, ExpiredSignatureError, InvalidTokenError
from pydantic import BaseModel, ConfigDict, Field
from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, OAuth2PasswordBearer
from fastapi.security.utils import get_authorization_scheme_param

logger = logging.getLogger("keycloak_auth")


def get_utc_now_iso() -> str:
    """Returns the current UTC timestamp formatted in ISO-8601 format."""
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------
# CSG-LMS Standard Realm Roles
# ---------------------------------------------------------

class KeycloakRole(str, Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    SCHOOL_ADMIN = "SCHOOL_ADMIN"
    TEACHER = "TEACHER"
    STUDENT = "STUDENT"
    PARENT = "PARENT"
    STAFF = "STAFF"
    PSYCHOLOGIST = "PSYCHOLOGIST"


SUPER_ADMIN = KeycloakRole.SUPER_ADMIN.value
SCHOOL_ADMIN = KeycloakRole.SCHOOL_ADMIN.value
TEACHER = KeycloakRole.TEACHER.value
STUDENT = KeycloakRole.STUDENT.value
PARENT = KeycloakRole.PARENT.value
STAFF = KeycloakRole.STAFF.value
PSYCHOLOGIST = KeycloakRole.PSYCHOLOGIST.value

ALL_REALM_ROLES: Set[str] = {role.value for role in KeycloakRole}


# ---------------------------------------------------------
# Configuration Settings
# ---------------------------------------------------------

class KeycloakSettings:
    """Environment configuration for Keycloak OIDC integration."""

    @property
    def server_url(self) -> str:
        return os.getenv("KEYCLOAK_URL", os.getenv("KEYCLOAK_SERVER_URL", "http://localhost:8080")).rstrip("/")

    @property
    def realm(self) -> str:
        return os.getenv("KEYCLOAK_REALM", "csg-lms")

    @property
    def client_id(self) -> str:
        return os.getenv("KEYCLOAK_CLIENT_ID", "csg-lms-api")

    @property
    def audience(self) -> Optional[str]:
        return os.getenv("KEYCLOAK_AUDIENCE", None)

    @property
    def algorithms(self) -> List[str]:
        raw = os.getenv("KEYCLOAK_ALGORITHMS", "RS256,HS256")
        return [algo.strip() for algo in raw.split(",") if algo.strip()]

    @property
    def verify_signature(self) -> bool:
        return os.getenv("KEYCLOAK_VERIFY_SIGNATURE", "true").lower() in ("1", "true", "yes")

    @property
    def jwks_url(self) -> str:
        override = os.getenv("KEYCLOAK_JWKS_URL")
        if override:
            return override
        return f"{self.server_url}/realms/{self.realm}/protocol/openid-connect/certs"

    @property
    def issuer(self) -> Optional[str]:
        override = os.getenv("KEYCLOAK_ISSUER")
        if override:
            return override
        return f"{self.server_url}/realms/{self.realm}"

    @property
    def public_key_pem(self) -> Optional[str]:
        """Optional static RSA public key for verification without live JWKS calls."""
        key = os.getenv("KEYCLOAK_PUBLIC_KEY")
        if not key:
            return None
        cleaned = key.strip()
        if not cleaned.startswith("-----BEGIN"):
            return f"-----BEGIN PUBLIC KEY-----\n{cleaned}\n-----END PUBLIC KEY-----"
        return cleaned

    @property
    def shared_secret(self) -> Optional[str]:
        """Fallback symmetric secret for testing/development."""
        return os.getenv("KEYCLOAK_SECRET_KEY", os.getenv("AUTH_JWT_SECRET_KEY", "dev_jwt_secret_key_change_in_production"))


settings = KeycloakSettings()

# Lazy JWK Client cache
_jwks_client: Optional[jwt.PyJWKClient] = None


def get_jwks_client() -> jwt.PyJWKClient:
    """Return singleton PyJWKClient with caching."""
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = jwt.PyJWKClient(
            uri=settings.jwks_url,
            cache_keys=True,
            max_cached_keys=16,
            cache_jwk_set=True,
            lifespan=3600,  # Cache JWKS for 1 hour
        )
    return _jwks_client


# ---------------------------------------------------------
# Principal Model
# ---------------------------------------------------------

class KeycloakUserPrincipal(BaseModel):
    """
    Authenticated User Principal extracted from Keycloak JWT.
    Contains user identity, tenant isolation scopes (org_id, campus_id),
    and normalized role memberships.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    sub: str = Field(..., description="Keycloak Subject / User UUID")
    email: Optional[str] = Field(default=None, description="Verified user email")
    preferred_username: Optional[str] = Field(default=None, description="Username")
    given_name: Optional[str] = Field(default=None, description="First name")
    family_name: Optional[str] = Field(default=None, description="Last name")
    name: Optional[str] = Field(default=None, description="Full display name")
    org_id: Optional[int] = Field(default=None, description="Multi-tenant Organization ID")
    campus_id: Optional[int] = Field(default=None, description="Assigned Campus ID for campus isolation")
    realm_roles: List[str] = Field(default_factory=list, description="Keycloak Realm roles")
    client_roles: Dict[str, List[str]] = Field(default_factory=dict, description="Keycloak Client-level roles")
    roles: Set[str] = Field(default_factory=set, description="Consolidated normalized roles set")
    raw_claims: Dict[str, Any] = Field(default_factory=dict, description="Complete raw JWT payload")

    def has_role(self, role: str) -> bool:
        """Check if user has a specific role (SUPER_ADMIN always satisfies)."""
        target = role.upper()
        return SUPER_ADMIN in self.roles or target in self.roles

    def has_any_role(self, candidate_roles: Sequence[str]) -> bool:
        """Check if user possesses at least one of the requested roles."""
        if SUPER_ADMIN in self.roles:
            return True
        normalized = {r.upper() for r in candidate_roles}
        return bool(self.roles.intersection(normalized))

    def has_all_roles(self, candidate_roles: Sequence[str]) -> bool:
        """Check if user possesses all of the requested roles."""
        if SUPER_ADMIN in self.roles:
            return True
        normalized = {r.upper() for r in candidate_roles}
        return normalized.issubset(self.roles)

    @property
    def is_superadmin(self) -> bool:
        """Helper to test for global SUPER_ADMIN role."""
        return SUPER_ADMIN in self.roles

    @property
    def is_principal(self) -> bool:
        """Helper to test for SCHOOL_ADMIN role."""
        return self.has_role(SCHOOL_ADMIN)

    @property
    def is_teacher(self) -> bool:
        """Helper to test for TEACHER role."""
        return self.has_role(TEACHER)

    @property
    def is_student(self) -> bool:
        """Helper to test for STUDENT role."""
        return self.has_role(STUDENT)


# ---------------------------------------------------------
# Claim Extraction Helpers
# ---------------------------------------------------------

def _parse_int_claim(val: Any) -> Optional[int]:
    """Safely coerce scalar or single-element list to int."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return int(val)
    if isinstance(val, list) and len(val) > 0:
        return _parse_int_claim(val[0])
    try:
        return int(str(val).strip())
    except (ValueError, TypeError):
        return None


def extract_principal_from_payload(payload: Dict[str, Any]) -> KeycloakUserPrincipal:
    """
    Parse standard Keycloak claims and custom multi-campus attributes
    into a structured `KeycloakUserPrincipal`.
    """
    sub = str(payload.get("sub") or payload.get("user_id") or "")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="JWT token is missing 'sub' subject identifier",
            headers={"WWW-Authenticate": "Bearer"},
        )

    email = payload.get("email")
    preferred_username = payload.get("preferred_username") or payload.get("username")
    given_name = payload.get("given_name")
    family_name = payload.get("family_name")
    name = payload.get("name") or f"{given_name or ''} {family_name or ''}".strip() or None

    # Tenancy extraction: root claim -> user_metadata -> attributes
    attrs = payload.get("attributes") or {}
    metadata = payload.get("user_metadata") or {}

    raw_org_id = payload.get("org_id") or payload.get("organization_id") or attrs.get("org_id") or metadata.get("org_id")
    org_id = _parse_int_claim(raw_org_id)

    raw_campus_id = payload.get("campus_id") or payload.get("campus") or attrs.get("campus_id") or metadata.get("campus_id")
    campus_id = _parse_int_claim(raw_campus_id)

    # Realm & Client roles extraction
    realm_access = payload.get("realm_access") or {}
    raw_realm_roles = realm_access.get("roles") or []
    realm_roles = [str(r).upper() for r in raw_realm_roles if isinstance(r, (str, int))]

    resource_access = payload.get("resource_access") or {}
    client_roles: Dict[str, List[str]] = {}
    all_client_role_names: List[str] = []

    for client_key, access_data in resource_access.items():
        if isinstance(access_data, dict):
            c_roles = [str(r).upper() for r in access_data.get("roles", []) if isinstance(r, (str, int))]
            client_roles[client_key] = c_roles
            all_client_role_names.extend(c_roles)

    # Direct roles / groups claim support
    direct_roles = [str(r).upper() for r in payload.get("roles", []) if isinstance(r, (str, int))]
    groups = [str(g).lstrip("/").upper() for g in payload.get("groups", []) if isinstance(g, str)]

    # Consolidated role set
    consolidated_roles = set(realm_roles) | set(all_client_role_names) | set(direct_roles) | set(groups)

    return KeycloakUserPrincipal(
        sub=sub,
        email=email,
        preferred_username=preferred_username,
        given_name=given_name,
        family_name=family_name,
        name=name,
        org_id=org_id,
        campus_id=campus_id,
        realm_roles=realm_roles,
        client_roles=client_roles,
        roles=consolidated_roles,
        raw_claims=payload,
    )


# ---------------------------------------------------------
# JWT Verification & Decoding
# ---------------------------------------------------------

def decode_and_verify_token(token: str) -> KeycloakUserPrincipal:
    """
    Verify and decode a Keycloak OIDC JWT Bearer token.
    Supports JWKS remote keys, static PEM public key, and HMAC development keys.
    """
    try:
        # Check unverified headers to determine algorithm and key ID
        unverified_headers = jwt.get_unverified_header(token)
        alg = unverified_headers.get("alg", "RS256")
    except PyJWTError as e:
        logger.warning(f"Invalid JWT header: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed JWT token headers",
            headers={"WWW-Authenticate": "Bearer"},
        )

    decode_options = {
        "verify_signature": settings.verify_signature,
        "verify_exp": True,
        "verify_nbf": True,
        "verify_iat": True,
        "verify_aud": bool(settings.audience),
    }

    signing_key: Any = None

    if settings.verify_signature:
        if alg.startswith("RS") or alg.startswith("ES") or alg.startswith("PS"):
            # 1. Try static public key if configured
            if settings.public_key_pem:
                signing_key = settings.public_key_pem
            else:
                # 2. Try fetching public key from JWKS
                try:
                    jwks_client = get_jwks_client()
                    signing_key = jwks_client.get_signing_key_from_jwt(token).key
                except Exception as jwks_err:
                    logger.error(f"Failed to retrieve signing key from JWKS: {jwks_err}")
                    # In test/dev environment, fallback to PEM or Secret if present
                    if settings.shared_secret:
                        signing_key = settings.shared_secret
                    else:
                        raise HTTPException(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Unable to verify token signature: JWKS key retrieval failed",
                            headers={"WWW-Authenticate": "Bearer error=\"invalid_token\""},
                        )
        elif alg.startswith("HS"):
            # Symmetric secret fallback
            signing_key = settings.shared_secret
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Unsupported JWT algorithm: {alg}",
                headers={"WWW-Authenticate": "Bearer"},
            )
    else:
        # In test mode without signature verification
        signing_key = "dummy_key_for_unverified_test_mode"

    try:
        payload = jwt.decode(
            token,
            signing_key,
            algorithms=settings.algorithms,
            audience=settings.audience,
            issuer=settings.issuer if (settings.issuer and settings.verify_signature) else None,
            options=decode_options,
        )
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="JWT token has expired",
            headers={"WWW-Authenticate": "Bearer error=\"token_expired\""},
        )
    except InvalidTokenError as e:
        logger.warning(f"JWT verification failure: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer error=\"invalid_token\""},
        )

    return extract_principal_from_payload(payload)


# ---------------------------------------------------------
# FastAPI Security Schemes & Dependencies
# ---------------------------------------------------------

bearer_scheme = HTTPBearer(auto_error=False)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


async def get_bearer_token(
    request: Request,
    bearer_creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    oauth2_token: Optional[str] = Depends(oauth2_scheme),
) -> Optional[str]:
    """Extract raw bearer token from HTTP Bearer header, OAuth2, or Authorization header."""
    if bearer_creds and bearer_creds.credentials:
        return bearer_creds.credentials
    if oauth2_token:
        return oauth2_token
    auth_header = request.headers.get("Authorization")
    if auth_header:
        scheme, param = get_authorization_scheme_param(auth_header)
        if scheme.lower() == "bearer" and param:
            return param
    return None


async def get_current_user_principal(
    token: Optional[str] = Depends(get_bearer_token),
) -> KeycloakUserPrincipal:
    """
    FastAPI dependency: Requires a valid Keycloak JWT Bearer token and
    returns the decoded `KeycloakUserPrincipal`.
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization Bearer token header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return decode_and_verify_token(token)


async def get_optional_user_principal(
    token: Optional[str] = Depends(get_bearer_token),
) -> Optional[KeycloakUserPrincipal]:
    """
    FastAPI dependency: Returns `KeycloakUserPrincipal` if a valid Bearer token
    is provided, otherwise returns `None` without raising 401.
    """
    if not token:
        return None
    try:
        return decode_and_verify_token(token)
    except HTTPException:
        return None


def require_roles(
    required_roles: Union[Sequence[str], Set[str]],
    require_all: bool = False,
) -> Callable[..., Any]:
    """
    FastAPI dependency factory: Validates that the authenticated user possesses
    the required realm/client roles.

    :param required_roles: List or set of role names (e.g. ['TEACHER', 'SCHOOL_ADMIN'])
    :param require_all: If True, user must possess all listed roles. If False (default), any listed role satisfies.
    :returns: FastAPI Dependency callable returning `KeycloakUserPrincipal`.
    """
    role_list = [r.upper() for r in required_roles]

    async def _role_checker(
        principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
    ) -> KeycloakUserPrincipal:
        if principal.is_superadmin:
            return principal

        has_permission = (
            principal.has_all_roles(role_list)
            if require_all
            else principal.has_any_role(role_list)
        )

        if not has_permission:
            mode_desc = "all of" if require_all else "at least one of"
            logger.warning(
                f"User '{principal.sub}' ({principal.email}) denied access. Required {mode_desc} {role_list}, held {principal.roles}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: Insufficient privileges. Required {mode_desc} roles: {role_list}",
            )
        return principal

    return _role_checker


def require_campus_access(
    campus_id_param: str = "campus_id",
) -> Callable[..., Any]:
    """
    FastAPI dependency factory: Enforces campus tenancy isolation by ensuring
    the caller's `campus_id` matches the path/query parameter `campus_id`.
    Global SUPER_ADMIN bypasses this restriction.
    """
    async def _campus_checker(
        request: Request,
        principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
    ) -> KeycloakUserPrincipal:
        if principal.is_superadmin:
            return principal

        target_campus_raw = request.path_params.get(campus_id_param) or request.query_params.get(campus_id_param)
        if target_campus_raw is not None:
            try:
                target_campus_id = int(target_campus_raw)
                if principal.campus_id is not None and principal.campus_id != target_campus_id:
                    logger.warning(
                        f"Cross-campus isolation violation: User {principal.sub} (campus {principal.campus_id}) attempted to access campus {target_campus_id}"
                    )
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Forbidden: Multi-campus isolation policy prohibits cross-campus operations",
                    )
            except (ValueError, TypeError):
                pass

        return principal

    return _campus_checker
