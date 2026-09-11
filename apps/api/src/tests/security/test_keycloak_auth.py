"""
Unit and Integration Tests for Keycloak 24 OIDC JWT Authentication & Multi-Campus RBAC
========================================================================================
"""

import jwt
import pytest
from unittest.mock import patch, MagicMock
from fastapi import HTTPException

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
    extract_principal_from_payload,
    decode_and_verify_token,
    require_roles,
    settings,
)


def test_realm_roles_defined():
    """Verify all required realm roles are properly defined in enum and sets."""
    assert KeycloakRole.SUPER_ADMIN.value == "SUPER_ADMIN"
    assert KeycloakRole.CAMPUS_PRINCIPAL.value == "CAMPUS_PRINCIPAL"
    assert KeycloakRole.TEACHER.value == "TEACHER"
    assert KeycloakRole.STUDENT.value == "STUDENT"
    assert KeycloakRole.PARENT.value == "PARENT"
    assert KeycloakRole.ACCOUNTANT.value == "ACCOUNTANT"

    assert {"SUPER_ADMIN", "CAMPUS_PRINCIPAL", "TEACHER", "STUDENT", "PARENT", "ACCOUNTANT"}.issubset(
        ALL_REALM_ROLES
    )


def test_extract_principal_from_payload_complete():
    """Verify extraction of standard OIDC claims, tenancy (org_id, campus_id), and realm roles."""
    payload = {
        "sub": "usr-uuid-12345",
        "email": "teacher.smith@campus.csg.edu",
        "preferred_username": "jsmith",
        "given_name": "John",
        "family_name": "Smith",
        "org_id": 42,
        "campus_id": 7,
        "realm_access": {
            "roles": ["TEACHER", "default-roles-csg"]
        },
        "resource_access": {
            "csg-lms-api": {
                "roles": ["GRADEBOOK_EDITOR"]
            }
        },
    }

    principal = extract_principal_from_payload(payload)
    assert principal.sub == "usr-uuid-12345"
    assert principal.email == "teacher.smith@campus.csg.edu"
    assert principal.preferred_username == "jsmith"
    assert principal.name == "John Smith"
    assert principal.org_id == 42
    assert principal.campus_id == 7
    assert "TEACHER" in principal.roles
    assert "GRADEBOOK_EDITOR" in principal.roles
    assert principal.has_role("TEACHER") is True
    assert principal.has_role("CAMPUS_PRINCIPAL") is False
    assert principal.is_superadmin is False


def test_extract_principal_from_nested_attributes():
    """Verify fallback extraction of org_id and campus_id from Keycloak user attributes."""
    payload = {
        "sub": "usr-uuid-principal-99",
        "email": "principal@islamabad.csg.edu",
        "attributes": {
            "org_id": ["10"],
            "campus_id": ["3"]
        },
        "realm_access": {
            "roles": ["CAMPUS_PRINCIPAL"]
        }
    }

    principal = extract_principal_from_payload(payload)
    assert principal.org_id == 10
    assert principal.campus_id == 3
    assert principal.has_role(CAMPUS_PRINCIPAL) is True
    assert principal.has_any_role([TEACHER, CAMPUS_PRINCIPAL]) is True


def test_superadmin_role_bypass():
    """Verify that SUPER_ADMIN role satisfies all role queries automatically."""
    payload = {
        "sub": "admin-super-01",
        "email": "superadmin@csginfotech.com",
        "realm_access": {
            "roles": ["SUPER_ADMIN"]
        }
    }

    principal = extract_principal_from_payload(payload)
    assert principal.is_superadmin is True
    assert principal.has_role(TEACHER) is True
    assert principal.has_role(CAMPUS_PRINCIPAL) is True
    assert principal.has_role(ACCOUNTANT) is True
    assert principal.has_any_role([STUDENT, PARENT]) is True
    assert principal.has_all_roles([TEACHER, ACCOUNTANT, CAMPUS_PRINCIPAL]) is True


def test_extract_principal_missing_sub_raises_401():
    """Verify that a token missing the sub claim raises HTTP 401."""
    with pytest.raises(HTTPException) as exc_info:
        extract_principal_from_payload({"email": "nosub@example.com"})
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_require_roles_dependency_success():
    """Verify require_roles dependency allows permitted roles."""
    principal = KeycloakUserPrincipal(
        sub="t-1",
        email="t@csg.edu",
        org_id=1,
        campus_id=2,
        roles={"TEACHER"},
    )
    checker = require_roles([TEACHER, CAMPUS_PRINCIPAL])
    result = await checker(principal=principal)
    assert result == principal


@pytest.mark.asyncio
async def test_require_roles_dependency_denied():
    """Verify require_roles dependency raises HTTP 403 when role is missing."""
    principal = KeycloakUserPrincipal(
        sub="s-1",
        email="s@csg.edu",
        org_id=1,
        campus_id=2,
        roles={"STUDENT"},
    )
    checker = require_roles([TEACHER, CAMPUS_PRINCIPAL])
    with pytest.raises(HTTPException) as exc_info:
        await checker(principal=principal)
    assert exc_info.value.status_code == 403
    assert "Insufficient privileges" in exc_info.value.detail


def test_decode_and_verify_token_hmac():
    """Verify JWT decoding using HMAC test key."""
    secret = "test-secret-key-12345678901234567890"
    token_payload = {
        "sub": "jwt-user-007",
        "email": "agent007@csg.edu",
        "org_id": 1,
        "campus_id": 5,
        "realm_access": {"roles": ["TEACHER"]},
    }
    token = jwt.encode(token_payload, secret, algorithm="HS256")

    with patch.object(settings, "shared_secret", secret):
        principal = decode_and_verify_token(token)
        assert principal.sub == "jwt-user-007"
        assert principal.email == "agent007@csg.edu"
        assert principal.campus_id == 5
        assert principal.has_role(TEACHER) is True
