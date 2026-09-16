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
import os
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Set, Union
from fastapi import Depends, HTTPException, Request, status
from sqlmodel import or_, select
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
    seed_default_ems_roles,
)
from src.security.school_ownership import (
    get_own_children_ids,
    get_own_teacher_section_ids,
    get_user_id,
)

logger = logging.getLogger("ems_rbac")


# ---------------------------------------------------------
# Principal claims carrying the EMS role store
# ---------------------------------------------------------
#
# `KeycloakUserPrincipal.roles` is the LEGACY 7-value enum (SUPER_ADMIN,
# SCHOOL_ADMIN, TEACHER, STUDENT, PARENT, STAFF, PSYCHOLOGIST) and is what the
# 262 existing `require_roles([...])` call sites match on. EMS assignments are
# therefore NOT merged into `.roles` -- doing so would silently widen every one
# of those gates. They ride in `raw_claims` instead, which is built server-side
# by `resolve_school_principal()` and is never client-supplied.
EMS_ASSIGNMENTS_CLAIM = "ems_assignments"
EMS_ROLE_SLUGS_CLAIM = "ems_role_slugs"


# ---------------------------------------------------------
# Fallback policy: FAIL CLOSED
# ---------------------------------------------------------
#
# A caller with no (unexpired, in-scope) EMS assignment is DENIED.
#
# `has_permission()` keeps its historical legacy-role bridge for direct
# callers (it is a library function and existing callers/tests depend on that
# reading). The ENFORCEMENT path -- `require_permission()`, which is what the
# routers use -- does not: it reads this switch, which defaults to off.
#
# `EMS_RBAC_LEGACY_FALLBACK=1` is a migration escape hatch ONLY. It restores
# the pre-wiring behaviour (fall back to the built-in role template matching
# the caller's legacy role) so a deployment that has not yet run the backfill
# is not hard-locked out of fees/payroll/counseling/admissions/exports. Run
# the backfill (see `backfill_ems_assignments_from_sms_roles` at the bottom of
# this module) and leave it off.
EMS_RBAC_LEGACY_FALLBACK: bool = os.getenv("EMS_RBAC_LEGACY_FALLBACK", "").strip().lower() in (
    "1",
    "true",
    "yes",
)

_legacy_fallback_warned = False


# Scope breadth, narrowest first. Used only when a caller passes
# `required_scope` to demand that the GRANTING rule be at least this broad.
_SCOPE_BREADTH: Dict[str, int] = {
    ScopeLevel.OWN_ONLY.value: 0,
    ScopeLevel.OWN_SECTION.value: 1,
    ScopeLevel.DEPARTMENT.value: 2,
    ScopeLevel.CAMPUS.value: 3,
    ScopeLevel.ALL.value: 4,
}


def _normalise_scope(scope: Any) -> str:
    raw = scope.value if isinstance(scope, ScopeLevel) else str(scope)
    return raw.upper().strip()


def _is_expired(expires_at: Any, now: datetime) -> bool:
    """True when an assignment's `expires_at` is in the past.

    Tolerates a naive datetime (assumed UTC) and an ISO string (SQLite hands
    some drivers back the raw column text), so an unparseable value is treated
    as expired rather than as 'no expiry'.
    """
    if expires_at is None:
        return False
    if isinstance(expires_at, str):
        try:
            expires_at = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        except ValueError:
            return True
    if not isinstance(expires_at, datetime):
        return True
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at <= now


async def load_active_ems_assignments(
    db_session: Optional[AsyncSession],
    *,
    user_id: Optional[int],
    org_id: Optional[int],
    campus_id: Optional[int] = None,
    now: Optional[datetime] = None,
) -> List[EMSUserRoleAssignment]:
    """The single, canonical read of the EMS assignment store.

    Shared by `resolve_school_principal()` (to populate the principal),
    `has_permission()` and `is_clinical_specialist()`, so all three agree on
    what 'this user holds right now' means. An assignment counts only when it
    is:
      - for this user,
      - in the caller's organisation (a principal with no org is scoped to no
        school, so it gets nothing -- never 'every org'),
      - unscoped to a campus or scoped to the caller's own campus,
      - not expired.

    Expiry is filtered in Python rather than SQL: `expires_at` is a
    timezone-aware column and SQLite (the test dialect) compares it as text.
    """
    if db_session is None or user_id is None or org_id is None:
        return []

    query = select(EMSUserRoleAssignment).where(
        EMSUserRoleAssignment.user_id == user_id,
        EMSUserRoleAssignment.org_id == org_id,
    )
    if campus_id is not None:
        query = query.where(
            or_(
                EMSUserRoleAssignment.campus_id.is_(None),
                EMSUserRoleAssignment.campus_id == campus_id,
            )
        )

    result = await db_session.execute(query)
    now = now or datetime.now(timezone.utc)
    return [a for a in result.scalars().all() if not _is_expired(a.expires_at, now)]


def principal_ems_assignments(principal: KeycloakUserPrincipal) -> List[Dict[str, Any]]:
    """The EMS assignments `resolve_school_principal()` attached to this
    principal, or [] for a principal built by hand (tests, the dormant
    Keycloak-JWT path). Informational: `has_permission()` re-reads the store
    rather than trusting this."""
    raw = principal.raw_claims or {}
    value = raw.get(EMS_ASSIGNMENTS_CLAIM)
    return list(value) if isinstance(value, list) else []


def principal_ems_role_slugs(principal: KeycloakUserPrincipal) -> Set[str]:
    """The slugs of the EMS roles this principal carries."""
    raw = principal.raw_claims or {}
    value = raw.get(EMS_ROLE_SLUGS_CLAIM)
    return {str(s) for s in value} if isinstance(value, list) else set()


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
        assignments = await load_active_ems_assignments(
            db_session,
            user_id=user_id,
            org_id=user_principal.org_id,
            campus_id=user_principal.campus_id,
        )
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
    allow_legacy_fallback: bool = True,
) -> bool:
    """
    Evaluates dynamic permissions for a user principal against a resource and action.

    Special Guardrails:
      - Clinical Isolation: 'clinical.case_notes' requires `is_clinical_specialist`.
        Raises 404 HTTPException for non-specialists (the 404-Never-403 rule)
        to prevent probing the existence of sealed psychological records.

    `allow_legacy_fallback` (default True, the historical behaviour) permits
    the built-in role template matching the caller's LEGACY role to answer the
    question when the caller holds no EMS assignment. `require_permission()`
    passes False so the enforcement path FAILS CLOSED -- see
    `EMS_RBAC_LEGACY_FALLBACK` above.

    `target_context["required_scope"]`, when present, demands that the rule
    which grants the action be at least that broad (e.g. a CAMPUS floor
    refuses to honour an OWN_ONLY grant).
    """
    context = target_context or {}
    user_id = get_user_id(user_principal)
    required_scope = context.get("required_scope")
    required_breadth = (
        _SCOPE_BREADTH.get(_normalise_scope(required_scope), 0)
        if required_scope is not None
        else None
    )

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

    # 3. Dynamic database assignments -- the authoritative store.
    assignments = await load_active_ems_assignments(
        db_session,
        user_id=user_id,
        org_id=user_principal.org_id,
        campus_id=user_principal.campus_id,
    )

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
                if required_breadth is not None and _SCOPE_BREADTH.get(
                    _normalise_scope(rule.scope_level), 0
                ) < required_breadth:
                    continue  # granted, but too narrow for what was asked
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

    if not allow_legacy_fallback:
        # FAIL CLOSED: the caller holds no usable EMS grant for this
        # resource/action. Deliberately no fall-through to the legacy role.
        logger.info(
            "Denied %s:%s for user %s -- no EMS grant (fail closed)",
            resource_key,
            action,
            user_id,
        )
        return False

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
                if required_breadth is not None and _SCOPE_BREADTH.get(
                    _normalise_scope(r_rule.get("scope_level", ScopeLevel.CAMPUS)), 0
                ) < required_breadth:
                    continue
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

    This is the ENFORCEMENT entry point and it FAILS CLOSED: a caller with no
    unexpired, in-scope EMS assignment is refused, regardless of their legacy
    role. `EMS_RBAC_LEGACY_FALLBACK=1` restores the legacy-role bridge for a
    deployment that has not yet run the backfill.

    `required_scope` (a `ScopeLevel` name) additionally demands that the rule
    granting the action be at least that broad.

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
        # Identity/scope come from path and query params ONLY. The request body
        # is never consulted: it is attacker-controlled and is not yet parsed
        # at dependency time.
        target_context: Dict[str, Any] = {}
        for param_name, param_val in {**request.query_params, **request.path_params}.items():
            if param_name in ("campus_id", "department_id", "section_id", "student_id", "user_id"):
                try:
                    target_context[param_name] = int(param_val)
                except (ValueError, TypeError):
                    target_context[param_name] = param_val

        if required_scope is not None:
            target_context["required_scope"] = required_scope

        if EMS_RBAC_LEGACY_FALLBACK:
            global _legacy_fallback_warned
            if not _legacy_fallback_warned:
                _legacy_fallback_warned = True
                logger.warning(
                    "EMS_RBAC_LEGACY_FALLBACK is enabled -- require_permission "
                    "is falling back to legacy role templates instead of "
                    "failing closed. Run the EMS backfill and turn this off."
                )

        allowed = await has_permission(
            user_principal=principal,
            resource_key=resource_key,
            action=action,
            target_context=target_context,
            db_session=db_session,
            allow_legacy_fallback=EMS_RBAC_LEGACY_FALLBACK,
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


# ---------------------------------------------------------
# Backfill: the migration path that makes fail-closed safe
# ---------------------------------------------------------
#
# `require_permission()` refuses any caller with no EMS assignment. Before
# this engine was wired up, NOTHING populated `EMSUserRoleAssignment` for real
# users -- `resolve_school_principal()` built every principal from `SMSUserRole`
# alone -- so turning the gate on without this step would lock every existing
# deployment out of fees, payroll, counseling, admissions and exports.
#
# This gives every active `SMSUserRole` holder the equivalent EMS assignment,
# preserving their org and campus scope. It is idempotent: re-running it adds
# nothing and never removes an assignment an operator granted by hand.
#
# Run it once per deployment, before (or immediately after) enabling the gate:
#
#     cd apps/api
#     python -m src.security.ems_rbac --backfill
#     python -m src.security.ems_rbac --backfill --org-id 3   # one tenant only
#
# Wiring it into startup or an Alembic migration is deliberately NOT done here:
# that would put a write in the request path / schema history, and this change
# is scoped to the security layer.

LEGACY_ROLE_TO_CORE_SLUG: Dict[str, str] = {
    "SUPER_ADMIN": CoreRoleSlug.SUPER_ADMIN.value,
    "SCHOOL_ADMIN": CoreRoleSlug.SCHOOL_ADMIN.value,
    "TEACHER": CoreRoleSlug.TEACHER.value,
    "STUDENT": CoreRoleSlug.STUDENT.value,
    "PARENT": CoreRoleSlug.PARENT.value,
    "STAFF": CoreRoleSlug.STAFF.value,
    "PSYCHOLOGIST": CoreRoleSlug.PSYCHOLOGIST.value,
}


async def backfill_ems_assignments_from_sms_roles(
    db_session: AsyncSession,
    org_id: Optional[int] = None,
) -> int:
    """Give every active `SMSUserRole` holder an equivalent EMS assignment.

    Seeds the built-in role templates (globally, `org_id=None`) if they are
    missing, then creates one `EMSUserRoleAssignment` per active grant that
    does not already have one. Returns the number of assignments created.

    `org_id` restricts the pass to a single tenant; None backfills all.
    """
    from src.db.sms_identity import SMSUserRole  # local: keeps the security layer importable without the SMS identity tables

    await seed_default_ems_roles(db_session, org_id=None)

    roles_res = await db_session.execute(select(EMSRole))
    roles_by_slug: Dict[str, EMSRole] = {}
    for role in roles_res.scalars().all():
        # A tenant-scoped override of a built-in slug wins over the global
        # template, so a school that has customised 'teacher' keeps its version.
        if role.slug not in roles_by_slug or role.org_id is not None:
            roles_by_slug[role.slug] = role

    grants_query = select(SMSUserRole).where(SMSUserRole.is_active == True)  # noqa: E712
    if org_id is not None:
        grants_query = grants_query.where(SMSUserRole.org_id == org_id)
    grants = list((await db_session.execute(grants_query)).scalars().all())

    existing_res = await db_session.execute(select(EMSUserRoleAssignment))
    existing = {
        (a.user_id, a.role_id, a.org_id, a.campus_id)
        for a in existing_res.scalars().all()
    }

    created = 0
    for grant in grants:
        role_value = grant.role.value if hasattr(grant.role, "value") else str(grant.role)
        slug = LEGACY_ROLE_TO_CORE_SLUG.get(role_value.upper())
        if slug is None:
            logger.warning("No EMS core role maps to legacy role %s -- skipped", role_value)
            continue
        role = roles_by_slug.get(slug)
        if role is None or role.id is None:
            logger.warning("EMS role %s is not seeded -- skipped", slug)
            continue
        if grant.org_id is None:
            # An unscoped grant cannot be attributed to a school; refusing is
            # the safe direction (see school_ownership.require_org_id).
            continue
        key = (grant.user_id, role.id, grant.org_id, grant.campus_id)
        if key in existing:
            continue
        db_session.add(
            EMSUserRoleAssignment(
                user_id=grant.user_id,
                role_id=role.id,
                org_id=grant.org_id,
                campus_id=grant.campus_id,
            )
        )
        existing.add(key)
        created += 1

    await db_session.flush()
    logger.info("EMS backfill: created %s assignment(s) from %s SMS role grant(s)", created, len(grants))
    return created


async def _backfill_cli(org_id: Optional[int]) -> int:
    """Entry point for `python -m src.security.ems_rbac --backfill`."""
    from src.core.events.database import get_db_session

    created = 0
    async for session in get_db_session():  # type: ignore[attr-defined]
        created = await backfill_ems_assignments_from_sms_roles(session, org_id=org_id)
        await session.commit()
        break
    return created


if __name__ == "__main__":
    import argparse
    import asyncio

    parser = argparse.ArgumentParser(description="CSG-EMS dynamic RBAC maintenance")
    parser.add_argument(
        "--backfill",
        action="store_true",
        help="Create EMS role assignments for every active SMSUserRole holder.",
    )
    parser.add_argument("--org-id", type=int, default=None, help="Restrict the backfill to one organisation.")
    args = parser.parse_args()

    if not args.backfill:
        parser.error("nothing to do: pass --backfill")

    print(f"EMS backfill complete: {asyncio.run(_backfill_cli(args.org_id))} assignment(s) created")
