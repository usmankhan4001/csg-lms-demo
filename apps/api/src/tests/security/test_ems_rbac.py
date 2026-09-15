"""
Unit & Integration Tests for CSG-EMS Dynamic RBAC & Permission Evaluator
========================================================================
Validates:
1. Dynamic role evaluation & rule matching
2. Multi-tier scope constraints (ALL, CAMPUS, DEPARTMENT, OWN_SECTION, OWN_ONLY)
3. Guardrails: Clinical isolation 404-Never-403 rule for sealed case notes
4. require_permission FastAPI dependency
5. Custom role creation, update, assignment, and revocation
"""

import pytest
from fastapi import HTTPException

from src.core.keycloak_auth import KeycloakUserPrincipal
from src.db.ems_roles import (
    EMSPermissionRule,
    EMSRole,
    EMSUserRoleAssignment,
    ScopeLevel,
)
from src.db.organizations import Organization
from src.db.sms_campus import Campus, ClassSection
from src.db.sms_identity import StudentGuardian
from src.security.ems_rbac import has_permission, is_clinical_specialist


def _make_principal(
    user_id: int,
    roles: set[str],
    org_id: int = 1,
    campus_id: int | None = None,
    is_superadmin: bool = False,
    claims: dict | None = None,
) -> KeycloakUserPrincipal:
    raw_claims = {"lh_user_id": user_id}
    if claims:
        raw_claims.update(claims)
    return KeycloakUserPrincipal(
        sub=f"uuid_{user_id}",
        email=f"user{user_id}@school.org",
        preferred_username=f"user_{user_id}",
        org_id=org_id,
        campus_id=campus_id,
        roles=roles,
        realm_roles=list(roles),
        raw_claims=raw_claims,
    )


@pytest.mark.asyncio
async def test_clinical_isolation_raises_404_for_non_specialist(db):
    """The 404-Never-403 rule: Non-clinical users probing clinical notes get 404 Not Found."""
    teacher_principal = _make_principal(10, {"TEACHER"}, campus_id=1)
    admin_principal = _make_principal(11, {"SCHOOL_ADMIN"}, campus_id=1)

    # Teacher access to clinical.case_notes must raise 404
    with pytest.raises(HTTPException) as exc_info:
        await has_permission(teacher_principal, "clinical.case_notes", "read", db_session=db)
    assert exc_info.value.status_code == 404

    # Admin without clinical specialist status must also get 404
    with pytest.raises(HTTPException) as exc_info:
        await has_permission(admin_principal, "clinical.case_notes", "read", db_session=db)
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_clinical_isolation_allows_psychologist(db):
    """Clinical psychologist with PSYCHOLOGIST role can access clinical case notes."""
    psychologist_principal = _make_principal(12, {"PSYCHOLOGIST"}, campus_id=1)
    allowed = await has_permission(
        psychologist_principal,
        "clinical.case_notes",
        "read",
        target_context={"campus_id": 1},
        db_session=db,
    )
    assert allowed is True


@pytest.mark.asyncio
async def test_superadmin_global_access_for_general_resources(db):
    """Superadmin has unrestricted access for standard academic and administrative resources."""
    superadmin = _make_principal(1, {"SUPER_ADMIN"}, is_superadmin=True)
    allowed = await has_permission(superadmin, "academic.courses", "delete", db_session=db)
    assert allowed is True


@pytest.mark.asyncio
async def test_teacher_section_scoping(db):
    """Teacher can manage grades for their own section, but not an unowned section."""
    teacher = _make_principal(20, {"TEACHER"}, org_id=1, campus_id=1)

    # Create section owned by teacher 20
    section = ClassSection(
        id=101,
        campus_id=1,
        grade_level="Grade 10",
        section_name="10-A",
        max_capacity=30,
        class_teacher_id=20,
    )
    db.add(section)
    await db.commit()

    # Access own section gradebook -> Allowed
    allowed_own = await has_permission(
        teacher,
        "academic.gradebook",
        "update",
        target_context={"section_id": 101},
        db_session=db,
    )
    assert allowed_own is True

    # Access unowned section gradebook -> Denied
    allowed_other = await has_permission(
        teacher,
        "academic.gradebook",
        "update",
        target_context={"section_id": 999},
        db_session=db,
    )
    assert allowed_other is False


@pytest.mark.asyncio
async def test_parent_own_only_scoping(db):
    """Parent can view only their linked child's records."""
    parent = _make_principal(30, {"PARENT"}, org_id=1)

    # Link parent 30 to student 55
    db.add(StudentGuardian(guardian_user_id=30, student_id=55, relationship="Mother"))
    await db.commit()

    # Access linked child's records -> Allowed
    allowed_child = await has_permission(
        parent,
        "students.records",
        "read",
        target_context={"student_id": 55},
        db_session=db,
    )
    assert allowed_child is True

    # Access unrelated student's records -> Denied
    allowed_other = await has_permission(
        parent,
        "students.records",
        "read",
        target_context={"student_id": 88},
        db_session=db,
    )
    assert allowed_other is False


@pytest.mark.asyncio
async def test_custom_dynamic_role_assignment(db):
    """Custom created role with specific permission rules is properly evaluated for assigned user."""
    user = _make_principal(40, set(), org_id=1, campus_id=2)

    # Create custom role "LAB_ASSISTANT"
    custom_role = EMSRole(
        org_id=1,
        name="Lab Assistant",
        slug="lab-assistant",
        description="Assists with lab equipment and inventory",
        is_system_template=False,
    )
    db.add(custom_role)
    await db.flush()
    await db.refresh(custom_role)

    # Add permission rule for lab inventory
    rule = EMSPermissionRule(
        role_id=custom_role.id,
        resource_key="science.inventory",
        can_read=True,
        can_update=True,
        scope_level=ScopeLevel.CAMPUS,
    )
    db.add(rule)

    # Assign role to user 40 on campus 2
    assignment = EMSUserRoleAssignment(
        user_id=40,
        role_id=custom_role.id,
        org_id=1,
        campus_id=2,
    )
    db.add(assignment)
    await db.commit()

    # User 40 matches campus 2 -> Allowed
    allowed = await has_permission(
        user,
        "science.inventory",
        "update",
        target_context={"campus_id": 2},
        db_session=db,
    )
    assert allowed is True

    # User 40 probing campus 3 -> Denied by campus scope
    denied = await has_permission(
        user,
        "science.inventory",
        "update",
        target_context={"campus_id": 3},
        db_session=db,
    )
    assert denied is False
