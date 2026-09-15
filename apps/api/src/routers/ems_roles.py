"""
CSG-EMS Role & Permission Management Router
============================================
Provides administrative endpoints for custom roles, granular permission rules,
multi-tenant role assignments, and system template blueprints.
"""

import logging
import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.events.database import get_db_session
from src.core.keycloak_auth import (
    KeycloakUserPrincipal,
    SCHOOL_ADMIN,
    SUPER_ADMIN,
    get_current_user_principal,
)
from src.db.ems_roles import (
    DEFAULT_EMS_ROLE_SPECS,
    EMSPermissionRule,
    EMSRole,
    EMSUserRoleAssignment,
    ScopeLevel,
    get_utc_now,
    seed_default_ems_roles,
)
from src.security.school_ownership import require_org_id, require_user_id

logger = logging.getLogger("ems_roles")

router = APIRouter(prefix="/ems/roles", tags=["EMS Roles & Permissions"])


# ---------------------------------------------------------
# Request & Response Schemas
# ---------------------------------------------------------

class PermissionRulePayload(BaseModel):
    resource_key: str
    can_read: bool = True
    can_create: bool = False
    can_update: bool = False
    can_delete: bool = False
    can_approve: bool = False
    can_export: bool = False
    scope_level: ScopeLevel = ScopeLevel.CAMPUS


class CustomRoleCreatePayload(BaseModel):
    name: str
    slug: Optional[str] = None
    description: Optional[str] = None
    is_clinical_specialist: bool = False
    rules: Optional[List[PermissionRulePayload]] = []


class CustomRoleUpdatePayload(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_clinical_specialist: Optional[bool] = None
    rules: Optional[List[PermissionRulePayload]] = None


class UserRoleAssignmentPayload(BaseModel):
    user_id: int
    role_id: int
    campus_id: Optional[int] = None
    department_id: Optional[int] = None
    section_id: Optional[int] = None


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return slug or "custom-role"


def _assert_admin_or_manage_roles(principal: KeycloakUserPrincipal) -> None:
    """Ensures caller has administrative authority to manage EMS roles."""
    if principal.is_superadmin or principal.has_role(SCHOOL_ADMIN):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Forbidden: Administrative privileges required to manage roles",
    )


@router.get(
    "/templates",
    response_model=List[Dict[str, Any]],
    summary="Get System Role Template Blueprints",
)
async def get_system_role_templates(
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> List[Dict[str, Any]]:
    """Returns the core system role template blueprints with standard permission rules."""
    return DEFAULT_EMS_ROLE_SPECS


@router.get(
    "",
    summary="List Roles for Current Organization",
)
async def list_roles(
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
    db_session: AsyncSession = Depends(get_db_session),
) -> List[Dict[str, Any]]:
    """Lists all active roles for the caller's organization, including system templates."""
    org_id = require_org_id(principal) if not principal.is_superadmin else principal.org_id

    # Check if system roles have been seeded
    roles_res = await db_session.execute(select(EMSRole))
    roles = list(roles_res.scalars().all())

    if not roles:
        await seed_default_ems_roles(db_session, org_id=None)
        await db_session.commit()
        roles_res = await db_session.execute(select(EMSRole))
        roles = list(roles_res.scalars().all())

    if org_id is not None:
        query = select(EMSRole).where(
            (EMSRole.org_id == org_id) | (EMSRole.is_system_template == True)  # noqa: E712
        ).order_by(EMSRole.is_system_template.desc(), EMSRole.name.asc())
        roles = list((await db_session.execute(query)).scalars().all())

    output = []
    for r in roles:
        output.append({
            "id": r.id,
            "org_id": r.org_id,
            "name": r.name,
            "slug": r.slug,
            "description": r.description,
            "is_system_template": r.is_system_template,
            "is_clinical_specialist": r.is_clinical_specialist,
            "created_at": r.created_at,
            "updated_at": r.updated_at,
        })
    return output


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Create Custom Role",
)
async def create_role(
    payload: CustomRoleCreatePayload,
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
    db_session: AsyncSession = Depends(get_db_session),
) -> Dict[str, Any]:
    """Creates a tenant-isolated custom role with granular permission rules."""
    _assert_admin_or_manage_roles(principal)
    org_id = require_org_id(principal)

    slug = payload.slug or _slugify(payload.name)

    existing = (
        await db_session.execute(
            select(EMSRole).where(EMSRole.org_id == org_id, EMSRole.slug == slug)
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A role with slug '{slug}' already exists in this organization",
        )

    role = EMSRole(
        org_id=org_id,
        name=payload.name,
        slug=slug,
        description=payload.description,
        is_system_template=False,
        is_clinical_specialist=payload.is_clinical_specialist,
        created_at=get_utc_now(),
        updated_at=get_utc_now(),
    )
    db_session.add(role)
    await db_session.flush()
    await db_session.refresh(role)

    rules_out = []
    if payload.rules:
        for r_in in payload.rules:
            rule = EMSPermissionRule(
                role_id=role.id,  # type: ignore
                resource_key=r_in.resource_key,
                can_read=r_in.can_read,
                can_create=r_in.can_create,
                can_update=r_in.can_update,
                can_delete=r_in.can_delete,
                can_approve=r_in.can_approve,
                can_export=r_in.can_export,
                scope_level=r_in.scope_level,
                created_at=get_utc_now(),
                updated_at=get_utc_now(),
            )
            db_session.add(rule)
            await db_session.flush()
            await db_session.refresh(rule)
            rules_out.append({
                "id": rule.id,
                "resource_key": rule.resource_key,
                "can_read": rule.can_read,
                "can_create": rule.can_create,
                "can_update": rule.can_update,
                "can_delete": rule.can_delete,
                "can_approve": rule.can_approve,
                "can_export": rule.can_export,
                "scope_level": rule.scope_level.value if hasattr(rule.scope_level, "value") else str(rule.scope_level),
            })

    await db_session.commit()
    await db_session.refresh(role)

    return {
        "id": role.id,
        "org_id": role.org_id,
        "name": role.name,
        "slug": role.slug,
        "description": role.description,
        "is_system_template": role.is_system_template,
        "is_clinical_specialist": role.is_clinical_specialist,
        "created_at": role.created_at,
        "updated_at": role.updated_at,
        "rules": rules_out,
    }


@router.post(
    "/assign",
    status_code=status.HTTP_201_CREATED,
    summary="Assign Role to User",
)
async def assign_role(
    payload: UserRoleAssignmentPayload,
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
    db_session: AsyncSession = Depends(get_db_session),
) -> Dict[str, Any]:
    """Assigns an EMS role to a user with multi-tier scope constraints."""
    _assert_admin_or_manage_roles(principal)
    org_id = require_org_id(principal)

    role = await db_session.get(EMSRole, payload.role_id)
    if not role or (role.org_id is not None and role.org_id != org_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found in this organization",
        )

    assignment = EMSUserRoleAssignment(
        user_id=payload.user_id,
        role_id=payload.role_id,
        org_id=org_id,
        campus_id=payload.campus_id,
        department_id=payload.department_id,
        section_id=payload.section_id,
        assigned_at=get_utc_now(),
    )
    db_session.add(assignment)
    await db_session.commit()
    await db_session.refresh(assignment)

    return {
        "id": assignment.id,
        "user_id": assignment.user_id,
        "role_id": assignment.role_id,
        "role_name": role.name,
        "role_slug": role.slug,
        "org_id": assignment.org_id,
        "campus_id": assignment.campus_id,
        "department_id": assignment.department_id,
        "section_id": assignment.section_id,
        "assigned_at": assignment.assigned_at,
    }


@router.delete(
    "/assign/{assignment_id}",
    summary="Revoke Role Assignment",
)
async def revoke_role_assignment(
    assignment_id: int,
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
    db_session: AsyncSession = Depends(get_db_session),
) -> Dict[str, str]:
    """Revokes an existing EMS role assignment."""
    _assert_admin_or_manage_roles(principal)
    org_id = require_org_id(principal)

    assignment = await db_session.get(EMSUserRoleAssignment, assignment_id)
    if not assignment or assignment.org_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role assignment not found",
        )

    await db_session.delete(assignment)
    await db_session.commit()

    return {"status": "success", "message": "Role assignment revoked successfully"}


@router.get(
    "/{role_id}",
    summary="Get Role Details",
)
async def get_role(
    role_id: int,
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
    db_session: AsyncSession = Depends(get_db_session),
) -> Dict[str, Any]:
    """Gets details and permission rules for a specific role."""
    org_id = principal.org_id

    role = await db_session.get(EMSRole, role_id)
    if not role or (not role.is_system_template and role.org_id != org_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found",
        )

    rules_res = await db_session.execute(
        select(EMSPermissionRule).where(EMSPermissionRule.role_id == role.id)
    )
    rules = list(rules_res.scalars().all())

    return {
        "id": role.id,
        "org_id": role.org_id,
        "name": role.name,
        "slug": role.slug,
        "description": role.description,
        "is_system_template": role.is_system_template,
        "is_clinical_specialist": role.is_clinical_specialist,
        "created_at": role.created_at,
        "updated_at": role.updated_at,
        "rules": [
            {
                "id": r.id,
                "resource_key": r.resource_key,
                "can_read": r.can_read,
                "can_create": r.can_create,
                "can_update": r.can_update,
                "can_delete": r.can_delete,
                "can_approve": r.can_approve,
                "can_export": r.can_export,
                "scope_level": r.scope_level.value if hasattr(r.scope_level, "value") else str(r.scope_level),
            }
            for r in rules
        ],
    }


@router.put(
    "/{role_id}",
    summary="Update Custom Role",
)
async def update_role(
    role_id: int,
    payload: CustomRoleUpdatePayload,
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
    db_session: AsyncSession = Depends(get_db_session),
) -> Dict[str, Any]:
    """Updates role metadata and permission rules."""
    _assert_admin_or_manage_roles(principal)
    org_id = require_org_id(principal)

    role = await db_session.get(EMSRole, role_id)
    if not role or (role.org_id is not None and role.org_id != org_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found",
        )

    if role.is_system_template:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot mutate system role templates directly; create a custom role instead",
        )

    if payload.name is not None:
        role.name = payload.name
    if payload.description is not None:
        role.description = payload.description
    if payload.is_clinical_specialist is not None:
        role.is_clinical_specialist = payload.is_clinical_specialist
    role.updated_at = get_utc_now()

    db_session.add(role)

    # If rules are provided, replace existing rules
    if payload.rules is not None:
        existing_rules = (
            await db_session.execute(
                select(EMSPermissionRule).where(EMSPermissionRule.role_id == role.id)
            )
        ).scalars().all()
        for r in existing_rules:
            await db_session.delete(r)

        for r_in in payload.rules:
            new_rule = EMSPermissionRule(
                role_id=role.id,  # type: ignore
                resource_key=r_in.resource_key,
                can_read=r_in.can_read,
                can_create=r_in.can_create,
                can_update=r_in.can_update,
                can_delete=r_in.can_delete,
                can_approve=r_in.can_approve,
                can_export=r_in.can_export,
                scope_level=r_in.scope_level,
                created_at=get_utc_now(),
                updated_at=get_utc_now(),
            )
            db_session.add(new_rule)

    await db_session.commit()
    await db_session.refresh(role)

    rules_res = await db_session.execute(
        select(EMSPermissionRule).where(EMSPermissionRule.role_id == role.id)
    )
    rules = list(rules_res.scalars().all())

    return {
        "id": role.id,
        "org_id": role.org_id,
        "name": role.name,
        "slug": role.slug,
        "description": role.description,
        "is_system_template": role.is_system_template,
        "is_clinical_specialist": role.is_clinical_specialist,
        "created_at": role.created_at,
        "updated_at": role.updated_at,
        "rules": [
            {
                "id": r.id,
                "resource_key": r.resource_key,
                "can_read": r.can_read,
                "can_create": r.can_create,
                "can_update": r.can_update,
                "can_delete": r.can_delete,
                "can_approve": r.can_approve,
                "can_export": r.can_export,
                "scope_level": r.scope_level.value if hasattr(r.scope_level, "value") else str(r.scope_level),
            }
            for r in rules
        ],
    }


@router.delete(
    "/{role_id}",
    summary="Delete Custom Role",
)
async def delete_role(
    role_id: int,
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
    db_session: AsyncSession = Depends(get_db_session),
) -> Dict[str, str]:
    """Deletes a custom role. Refuses deletion if system role template."""
    _assert_admin_or_manage_roles(principal)
    org_id = require_org_id(principal)

    role = await db_session.get(EMSRole, role_id)
    if not role or (role.org_id is not None and role.org_id != org_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found",
        )

    if role.is_system_template:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="System role templates cannot be deleted",
        )

    await db_session.delete(role)
    await db_session.commit()

    return {"status": "success", "message": f"Role '{role.name}' deleted successfully"}
