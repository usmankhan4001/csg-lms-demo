"""
CSG-EMS Dynamic Permission Evaluator & RBAC Engine
===================================================
Provides high-performance, dynamic permission evaluation, scope enforcement,
multi-tenant isolation, and clinical confidential data safeguards for CSG-EMS.

Compliant with FERPA/COPPA child safety, clinical psychological record isolation
(the 404-Never-403 rule for sealed therapeutic case notes), and multi-campus
hierarchical scoping (ALL, CAMPUS, DEPARTMENT, OWN_SECTION, OWN_ONLY).
"""

import logging
from typing import Any, Callable, Dict, List, Optional, Set, Union
from fastapi import Depends, HTTPException, Request, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.events.database import get_db_session
from src.core.keycloak_auth import (
    KeycloakUserPrincipal,
    PSYCHOLOGIST,
    SUPER_ADMIN,
    get_current_user_principal,
)
from src.db.ems_roles import (
    DEFAULT_EMS_ROLE_SPECS,
    CoreRoleSlug,
    EMSPermissionRule,
    EMSRole,
    EMSUserRoleAssignment,
    ResourceDomain,
    ScopeLevel,
)
from src.security.school_ownership import (
    get_own_children_ids,
    get_own_teacher_section_ids,
    get_user_id,
)

logger = logging.getLogger("ems_rbac")


async def is_clinical_specialist(
    user_principal: KeycloakUserPrincipal,
    db_session: Optional[AsyncSession] = None,
) -> bool:
    """
    Check if the user is an authorized clinical specialist (School Psychologist).
    Sealed clinical case notes and psychological records require this status.
    """
    if user_principal.has_role(PSYCHOLOGIST) or PSYCHOLOGIST in user_principal.roles:
        return True
    if "psychologist" in [str(r).lower() for r in user_principal.roles]:
        return True
    if user_principal.raw_claims.get("is_clinical_specialist") is True:
        return True

    user_id = get_user_id(user_principal)
    if db_session is not None and user_id is not None:
        query = select(EMSUserRoleAssignment).where(
            EMSUserRoleAssignment.user_id == user_id
        )
        if user_principal.org_id is not None:
            query = query.where(EMSUserRoleAssignment.org_id == user_principal.org_id)
        result = await db_session.execute(query)
        assignments = list(result.scalars().all())
        for assign in assignments:
            role = await db_session.get(EMSRole, assign.role_id)
            if role and (role.is_clinical_specialist or role.slug.lower() in ("psychologist", "clinical-specialist")):
                return True

    return False


RESOURCE_DOMAIN_MAP: Dict[str, str] = {
    "students": "academic",
    "students.records": "academic",
    "attendance": "academic",
    "attendance.records": "academic",
    "timetable": "academic",
    "timetable.schedules": "academic",
    "lesson.plans": "academic",
    "fees": "finance",
    "finance.fees": "finance",
    "finance.ledger": "finance",
    "admissions": "revops",
    "admissions.applications": "revops",
    "leads": "revops",
    "case_notes": "clinical",
    "clinical.case_notes": "clinical",
    "counseling.sessions": "clinical",
    "facilities": "operations",
    "campus.facilities": "operations",
    "inventory": "operations",
    "inventory.items": "operations",
    "library": "operations",
    "library.books": "operations",
    "transport": "operations",
    "transport.routes": "operations",
    "transport.vehicles": "operations",
    "payroll": "hr",
    "hr.payroll": "hr",
}


def _matches_resource(rule_key: str, requested_key: str) -> bool:
    """Check if the requested resource key matches the rule pattern (exact, prefix, or domain match)."""
    if rule_key == "*":
        return True
    r_key = rule_key.lower().strip()
    req_key = requested_key.lower().strip()
    if r_key == req_key:
        return True
    if req_key.startswith(r_key + "."):
        return True
    if r_key.startswith(req_key + "."):
        return True
    if r_key.endswith(".*"):
        prefix = r_key[:-2]
        return req_key == prefix or req_key.startswith(prefix + ".")
    if r_key.endswith("*"):
        prefix = r_key[:-1]
        return req_key.startswith(prefix)

    # Check mapped resource domains
    req_mapped = RESOURCE_DOMAIN_MAP.get(req_key)
    if req_mapped and req_mapped == r_key:
        return True
    r_mapped = RESOURCE_DOMAIN_MAP.get(r_key)
    if r_mapped and r_mapped == req_key:
        return True
    if req_mapped and r_mapped and req_mapped == r_mapped:
        return True

    return False


def _matches_action(rule: Union[EMSPermissionRule, Dict[str, Any]], requested_action: str) -> bool:
    """Check if the requested action is permitted by the rule definition."""
    req_act = requested_action.lower().strip()

    if isinstance(rule, dict):
        if req_act in ("read", "get", "view"):
            return rule.get("can_read", False)
        if req_act in ("create", "post", "add"):
            return rule.get("can_create", False)
        if req_act in ("update", "put", "patch", "edit"):
            return rule.get("can_update", False)
        if req_act in ("delete", "remove"):
            return rule.get("can_delete", False)
        if req_act in ("approve", "submit"):
            return rule.get("can_approve", False)
        if req_act in ("export", "download"):
            return rule.get("can_export", False)
        if req_act in ("manage", "*"):
            return (
                rule.get("can_read", False)
                or rule.get("can_create", False)
                or rule.get("can_update", False)
            )
        return False

    # EMSPermissionRule model
    if req_act in ("read", "get", "view"):
        return rule.can_read
    if req_act in ("create", "post", "add"):
        return rule.can_create
    if req_act in ("update", "put", "patch", "edit"):
        return rule.can_update
    if req_act in ("delete", "remove"):
        return rule.can_delete
    if req_act in ("approve", "submit"):
        return rule.can_approve
    if req_act in ("export", "download"):
        return rule.can_export
    if req_act in ("manage", "*"):
        return rule.can_read or rule.can_create or rule.can_update

    return False


async def _evaluate_scope(
    scope_level: Union[ScopeLevel, str],
    target_context: Dict[str, Any],
    user_id: Optional[int],
    principal: KeycloakUserPrincipal,
    assignment: Optional[EMSUserRoleAssignment],
    db_session: Optional[AsyncSession],
) -> bool:
    """
    Evaluates scope constraints:
      - ALL: Unrestricted tenant-wide access
      - CAMPUS: Matches assigned campus or unrestricted
      - DEPARTMENT: Matches assigned department
      - OWN_SECTION: Section teacher ownership check
      - OWN_ONLY: User's own record or parent-child link check
    """
    norm_scope = (scope_level.value if isinstance(scope_level, ScopeLevel) else str(scope_level)).upper().strip()

    if norm_scope == ScopeLevel.ALL.value:
        return True

    if norm_scope == ScopeLevel.CAMPUS.value:
        target_campus = target_context.get("campus_id")
        if target_campus is not None:
            assign_campus = assignment.campus_id if assignment else None
            user_campus = principal.campus_id
            if assign_campus is not None and assign_campus != target_campus:
                return False
            if assign_campus is None and user_campus is not None and user_campus != target_campus:
                return False
        return True

    if norm_scope == ScopeLevel.DEPARTMENT.value:
        target_dept = target_context.get("department_id")
        if target_dept is not None and assignment is not None:
            if assignment.department_id is not None and assignment.department_id != target_dept:
                return False
        return True

    if norm_scope == ScopeLevel.OWN_SECTION.value:
        target_section = target_context.get("section_id")
        if target_section is not None:
            if assignment is not None and assignment.section_id is not None:
                return assignment.section_id == target_section
            if db_session is not None and user_id is not None:
                own_sections = await get_own_teacher_section_ids(user_id, db_session)
                return target_section in own_sections
            return False
        return True

    if norm_scope == ScopeLevel.OWN_ONLY.value:
        target_person_id = target_context.get("student_id") or target_context.get("user_id")
        if target_person_id is not None and user_id is not None:
            if target_person_id == user_id:
                return True
            # Check parent-child relationship
            if db_session is not None:
                children_ids = await get_own_children_ids(user_id, db_session)
                if target_person_id in children_ids:
                    return True
            return False
        return True

    return True


async def has_permission(
    user_principal: KeycloakUserPrincipal,
    resource_key: str,
    action: str,
    target_context: Optional[Dict[str, Any]] = None,
    db_session: Optional[AsyncSession] = None,
) -> bool:
    """
    Evaluates dynamic permissions for a user principal against a resource and action.

    Special Guardrails:
      - Clinical Isolation: 'clinical.case_notes' requires `is_clinical_specialist`.
        Raises 404 HTTPException for non-specialists (the 404-Never-403 rule)
        to prevent probing the existence of sealed psychological records.
    """
    context = target_context or {}
    user_id = get_user_id(user_principal)

    # 1. Special Guardrail: Clinical Isolation
    is_clinical_resource = (
        resource_key == "clinical.case_notes"
        or resource_key.startswith("clinical.")
        or resource_key.lower() == "clinical"
        or "case_notes" in resource_key.lower()
    )
    if is_clinical_resource:
        is_spec = await is_clinical_specialist(user_principal, db_session)
        if not is_spec:
            # 404-Never-403 rule: raise 404 Not Found to obscure existence
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resource not found",
            )

    # 2. Superadmin global bypass for non-clinical resources
    if user_principal.is_superadmin:
        return True

    # 3. Dynamic database assignments
    if db_session is not None and user_id is not None:
        query = select(EMSUserRoleAssignment).where(
            EMSUserRoleAssignment.user_id == user_id
        )
        if user_principal.org_id is not None:
            query = query.where(EMSUserRoleAssignment.org_id == user_principal.org_id)

        result = await db_session.execute(query)
        assignments = list(result.scalars().all())

        for assignment in assignments:
            role = await db_session.get(EMSRole, assignment.role_id)
            if not role:
                continue

            rules_res = await db_session.execute(
                select(EMSPermissionRule).where(
                    EMSPermissionRule.role_id == role.id
                )
            )
            rules = list(rules_res.scalars().all())

            for rule in rules:
                if _matches_resource(rule.resource_key, resource_key) and _matches_action(rule, action):
                    scope_ok = await _evaluate_scope(
                        scope_level=rule.scope_level,
                        target_context=context,
                        user_id=user_id,
                        principal=user_principal,
                        assignment=assignment,
                        db_session=db_session,
                    )
                    if scope_ok:
                        return True

    # 4. Fallback / System Template Blueprints for assigned realm roles
    # Maps uppercase role names to template specs
    slug_map = {
        "SUPER_ADMIN": CoreRoleSlug.SUPER_ADMIN.value,
        "SCHOOL_ADMIN": CoreRoleSlug.SCHOOL_ADMIN.value,
        "TEACHER": CoreRoleSlug.TEACHER.value,
        "STUDENT": CoreRoleSlug.STUDENT.value,
        "PARENT": CoreRoleSlug.PARENT.value,
        "PSYCHOLOGIST": CoreRoleSlug.PSYCHOLOGIST.value,
        "STAFF": CoreRoleSlug.STAFF.value,
        "BURSAR": CoreRoleSlug.BURSAR.value,
        "LIBRARIAN": CoreRoleSlug.LIBRARIAN.value,
        "TRANSPORT_MANAGER": CoreRoleSlug.TRANSPORT_MANAGER.value,
    }

    templates_by_slug = {spec["slug"]: spec for spec in DEFAULT_EMS_ROLE_SPECS}

    for role_name in user_principal.roles:
        target_slug = slug_map.get(role_name.upper(), role_name.lower())
        template = templates_by_slug.get(target_slug)
        if not template:
            continue

        rules_dict = template.get("rules", {})
        for r_domain, r_rule in rules_dict.items():
            if _matches_resource(r_domain, resource_key) and _matches_action(r_rule, action):
                scope_ok = await _evaluate_scope(
                    scope_level=r_rule.get("scope_level", ScopeLevel.CAMPUS),
                    target_context=context,
                    user_id=user_id,
                    principal=user_principal,
                    assignment=None,
                    db_session=db_session,
                )
                if scope_ok:
                    return True

    return False


def require_permission(
    resource_key: str,
    action: str,
    required_scope: Optional[str] = None,
) -> Callable[..., Any]:
    """
    FastAPI dependency factory enforcing dynamic RBAC permissions and scope checks.

    Usage:
        @router.get("/courses/{course_id}")
        async def get_course(
            course_id: int,
            principal: KeycloakUserPrincipal = Depends(require_permission("academic.courses", "read")),
        ):
            ...
    """

    async def _permission_checker(
        request: Request,
        principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
        db_session: AsyncSession = Depends(get_db_session),
    ) -> KeycloakUserPrincipal:
        target_context: Dict[str, Any] = {}
        for param_name, param_val in {**request.query_params, **request.path_params}.items():
            if param_name in ("campus_id", "department_id", "section_id", "student_id", "user_id"):
                try:
                    target_context[param_name] = int(param_val)
                except (ValueError, TypeError):
                    target_context[param_name] = param_val

        if required_scope is not None:
            target_context["required_scope"] = required_scope

        allowed = await has_permission(
            user_principal=principal,
            resource_key=resource_key,
            action=action,
            target_context=target_context,
            db_session=db_session,
        )

        if not allowed:
            if resource_key == "clinical.case_notes" or resource_key.startswith("clinical."):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Resource not found",
                )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: Insufficient permissions for {resource_key}:{action}",
            )

        return principal

    return _permission_checker
