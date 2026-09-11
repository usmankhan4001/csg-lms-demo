"""
Middleware and re-exports for Keycloak Authentication & Tenant Context.
"""

from src.core.keycloak_auth import (
    KeycloakRole,
    KeycloakUserPrincipal,
    SUPER_ADMIN,
    CAMPUS_PRINCIPAL,
    TEACHER,
    STUDENT,
    PARENT,
    ACCOUNTANT,
    ALL_REALM_ROLES,
    get_current_user_principal,
    get_optional_user_principal,
    require_roles,
    require_campus_access,
    decode_and_verify_token,
    extract_principal_from_payload,
)

__all__ = [
    "KeycloakRole",
    "KeycloakUserPrincipal",
    "SUPER_ADMIN",
    "CAMPUS_PRINCIPAL",
    "TEACHER",
    "STUDENT",
    "PARENT",
    "ACCOUNTANT",
    "ALL_REALM_ROLES",
    "get_current_user_principal",
    "get_optional_user_principal",
    "require_roles",
    "require_campus_access",
    "decode_and_verify_token",
    "extract_principal_from_payload",
]
