"""
CSG-EMS ERPNext-Style Dynamic RBAC Database Models
==================================================
This module defines the database models and seeding utilities for dynamic,
multi-tenant Role-Based Access Control (RBAC) with field/domain permission rules
and hierarchical scope levels (ALL, CAMPUS, DEPARTMENT, OWN_SECTION, OWN_ONLY).

Models:
- EMSRole: Role definition (system template or custom org role).
- EMSPermissionRule: Resource domain permission matrix and scope.
- EMSUserRoleAssignment: Scoped assignment of roles to users across org/campus/department/section.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlmodel import Field, SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.orm import Session


def get_utc_now() -> datetime:
    """Return current timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


# ---------------------------------------------------------
# Enums & Constants
# ---------------------------------------------------------

class ScopeLevel(str, Enum):
    """Hierarchical scope level defining the boundary of resource access."""
    ALL = "ALL"
    CAMPUS = "CAMPUS"
    DEPARTMENT = "DEPARTMENT"
    OWN_SECTION = "OWN_SECTION"
    OWN_ONLY = "OWN_ONLY"


class ResourceDomain(str, Enum):
    """Core resource domains governed by EMS permissions."""
    ACADEMIC = "academic"
    REVOPS = "revops"
    FINANCE = "finance"
    HR = "hr"
    PASTORAL = "pastoral"
    CLINICAL = "clinical"
    OPERATIONS = "operations"
    COMPLIANCE = "compliance"


class CoreRoleSlug(str, Enum):
    """Standard system role slugs."""
    SUPER_ADMIN = "super-admin"
    SCHOOL_ADMIN = "school-admin"
    TEACHER = "teacher"
    STUDENT = "student"
    PARENT = "parent"
    PSYCHOLOGIST = "psychologist"
    STAFF = "staff"
    BURSAR = "bursar"
    LIBRARIAN = "librarian"
    TRANSPORT_MANAGER = "transport-manager"


# ---------------------------------------------------------
# Database Models
# ---------------------------------------------------------

class EMSRoleBase(SQLModel):
    """Base schema for EMSRole."""
    name: str = Field(..., max_length=100, description="Role display name")
    slug: str = Field(..., max_length=100, description="Unique slug for the role (e.g. 'school-admin')")
    description: Optional[str] = Field(default=None, max_length=500, description="Role description and scope summary")
    is_system_template: bool = Field(default=False, description="Whether role is a built-in immutable system template")
    is_clinical_specialist: bool = Field(
        default=False,
        description="Clinical specialist marker for HIPAA/FERPA protected health & psychological records"
    )


class EMSRole(EMSRoleBase, table=True):
    """Database model for EMSRole (global template or organization-scoped custom role)."""
    __tablename__ = "ems_role"
    __table_args__ = (
        Index("ix_ems_role_org_slug", "org_id", "slug"),
        Index("ix_ems_role_org_template", "org_id", "is_system_template"),
        {"extend_existing": True},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    org_id: Optional[int] = Field(
        default=None,
        sa_column=Column(
            Integer,
            ForeignKey("organization.id", ondelete="CASCADE"),
            nullable=True,
            index=True
        ),
        description="Null for global system templates, or foreign key to organization for tenant-scoped roles"
    )
    created_at: datetime = Field(
        default_factory=get_utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    updated_at: datetime = Field(
        default_factory=get_utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )


class EMSPermissionRuleBase(SQLModel):
    """Base schema for EMSPermissionRule."""
    resource_key: str = Field(
        ...,
        max_length=64,
        description="Resource domain identifier (e.g. 'academic', 'finance', 'revops')"
    )
    can_read: bool = Field(default=False, description="Permission to view/query resource records")
    can_create: bool = Field(default=False, description="Permission to create new resource records")
    can_update: bool = Field(default=False, description="Permission to edit existing resource records")
    can_delete: bool = Field(default=False, description="Permission to delete resource records")
    can_approve: bool = Field(default=False, description="Permission to approve workflows / submit final grades")
    can_export: bool = Field(default=False, description="Permission to bulk export/download resource data")
    scope_level: ScopeLevel = Field(
        default=ScopeLevel.ALL,
        description="Access scope constraint: ALL, CAMPUS, DEPARTMENT, OWN_SECTION, OWN_ONLY"
    )


class EMSPermissionRule(EMSPermissionRuleBase, table=True):
    """Database model for granular permission rules attached to an EMSRole."""
    __tablename__ = "ems_permission_rule"
    __table_args__ = (
        UniqueConstraint("role_id", "resource_key", name="uq_ems_permission_rule_role_resource"),
        Index("ix_ems_permission_rule_role_resource", "role_id", "resource_key"),
        {"extend_existing": True},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    role_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("ems_role.id", ondelete="CASCADE"),
            nullable=False,
            index=True
        )
    )
    can_read: bool = Field(default=False, sa_column=Column(Boolean, nullable=False, server_default="false"))
    can_create: bool = Field(default=False, sa_column=Column(Boolean, nullable=False, server_default="false"))
    can_update: bool = Field(default=False, sa_column=Column(Boolean, nullable=False, server_default="false"))
    can_delete: bool = Field(default=False, sa_column=Column(Boolean, nullable=False, server_default="false"))
    can_approve: bool = Field(default=False, sa_column=Column(Boolean, nullable=False, server_default="false"))
    can_export: bool = Field(default=False, sa_column=Column(Boolean, nullable=False, server_default="false"))
    scope_level: ScopeLevel = Field(
        default=ScopeLevel.ALL,
        sa_column=Column(String(32), nullable=False, server_default="ALL")
    )
    created_at: datetime = Field(
        default_factory=get_utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    updated_at: datetime = Field(
        default_factory=get_utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )


class EMSUserRoleAssignmentBase(SQLModel):
    """Base schema for EMSUserRoleAssignment."""
    user_id: int = Field(..., description="Target user id")
    role_id: int = Field(..., description="Assigned EMSRole id")
    org_id: int = Field(..., description="Organization id scope")
    campus_id: Optional[int] = Field(default=None, description="Optional campus id scope")
    department_id: Optional[int] = Field(default=None, description="Optional department id scope")
    section_id: Optional[int] = Field(default=None, description="Optional class section id scope")
    expires_at: Optional[datetime] = Field(default=None, description="Optional assignment expiry timestamp")


class EMSUserRoleAssignment(EMSUserRoleAssignmentBase, table=True):
    """Database model for user role assignments scoped to org, campus, department, and/or section."""
    __tablename__ = "ems_user_role_assignment"
    __table_args__ = (
        Index("ix_ems_user_role_assignment_user_org", "user_id", "org_id"),
        Index("ix_ems_user_role_assignment_role", "role_id"),
        Index("ix_ems_user_role_assignment_scope", "org_id", "campus_id", "department_id", "section_id"),
        {"extend_existing": True},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("user.id", ondelete="CASCADE"),
            nullable=False,
            index=True
        )
    )
    role_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("ems_role.id", ondelete="CASCADE"),
            nullable=False,
            index=True
        )
    )
    org_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("organization.id", ondelete="CASCADE"),
            nullable=False,
            index=True
        )
    )
    campus_id: Optional[int] = Field(
        default=None,
        sa_column=Column(
            Integer,
            ForeignKey("campus.id", ondelete="SET NULL"),
            nullable=True,
            index=True
        )
    )
    department_id: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, nullable=True, index=True)
    )
    section_id: Optional[int] = Field(
        default=None,
        sa_column=Column(
            Integer,
            ForeignKey("class_section.id", ondelete="SET NULL"),
            nullable=True,
            index=True
        )
    )
    assigned_at: datetime = Field(
        default_factory=get_utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    expires_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True)
    )


# ---------------------------------------------------------
# Pydantic Schemas / DTOs
# ---------------------------------------------------------

class EMSRoleCreate(EMSRoleBase):
    org_id: Optional[int] = None


class EMSRoleUpdate(SQLModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_clinical_specialist: Optional[bool] = None


class EMSRoleRead(EMSRoleBase):
    id: int
    org_id: Optional[int]
    created_at: datetime
    updated_at: datetime


class EMSPermissionRuleCreate(EMSPermissionRuleBase):
    role_id: int


class EMSPermissionRuleUpdate(SQLModel):
    can_read: Optional[bool] = None
    can_create: Optional[bool] = None
    can_update: Optional[bool] = None
    can_delete: Optional[bool] = None
    can_approve: Optional[bool] = None
    can_export: Optional[bool] = None
    scope_level: Optional[ScopeLevel] = None


class EMSPermissionRuleRead(EMSPermissionRuleBase):
    id: int
    role_id: int
    created_at: datetime
    updated_at: datetime


class EMSUserRoleAssignmentCreate(EMSUserRoleAssignmentBase):
    pass


class EMSUserRoleAssignmentUpdate(SQLModel):
    campus_id: Optional[int] = None
    department_id: Optional[int] = None
    section_id: Optional[int] = None
    expires_at: Optional[datetime] = None


class EMSUserRoleAssignmentRead(EMSUserRoleAssignmentBase):
    id: int
    assigned_at: datetime


# ---------------------------------------------------------
# Default System Role Definitions
# ---------------------------------------------------------

DEFAULT_EMS_ROLE_SPECS: List[Dict[str, Any]] = [
    {
        "name": "Super Administrator",
        "slug": CoreRoleSlug.SUPER_ADMIN.value,
        "description": "Global system administrator with unrestricted access across all domains and organizations",
        "is_system_template": True,
        "is_clinical_specialist": True,
        "rules": {
            ResourceDomain.ACADEMIC.value: {"can_read": True, "can_create": True, "can_update": True, "can_delete": True, "can_approve": True, "can_export": True, "scope_level": ScopeLevel.ALL},
            ResourceDomain.REVOPS.value: {"can_read": True, "can_create": True, "can_update": True, "can_delete": True, "can_approve": True, "can_export": True, "scope_level": ScopeLevel.ALL},
            ResourceDomain.FINANCE.value: {"can_read": True, "can_create": True, "can_update": True, "can_delete": True, "can_approve": True, "can_export": True, "scope_level": ScopeLevel.ALL},
            ResourceDomain.HR.value: {"can_read": True, "can_create": True, "can_update": True, "can_delete": True, "can_approve": True, "can_export": True, "scope_level": ScopeLevel.ALL},
            ResourceDomain.PASTORAL.value: {"can_read": True, "can_create": True, "can_update": True, "can_delete": True, "can_approve": True, "can_export": True, "scope_level": ScopeLevel.ALL},
            ResourceDomain.CLINICAL.value: {"can_read": True, "can_create": True, "can_update": True, "can_delete": True, "can_approve": True, "can_export": True, "scope_level": ScopeLevel.ALL},
            ResourceDomain.OPERATIONS.value: {"can_read": True, "can_create": True, "can_update": True, "can_delete": True, "can_approve": True, "can_export": True, "scope_level": ScopeLevel.ALL},
            ResourceDomain.COMPLIANCE.value: {"can_read": True, "can_create": True, "can_update": True, "can_delete": True, "can_approve": True, "can_export": True, "scope_level": ScopeLevel.ALL},
        }
    },
    {
        "name": "School Administrator",
        "slug": CoreRoleSlug.SCHOOL_ADMIN.value,
        "description": "Campus/Institutional administrator managing academic, financial, HR, operational, and compliance workflows",
        "is_system_template": True,
        "is_clinical_specialist": False,
        "rules": {
            ResourceDomain.ACADEMIC.value: {"can_read": True, "can_create": True, "can_update": True, "can_delete": True, "can_approve": True, "can_export": True, "scope_level": ScopeLevel.ALL},
            ResourceDomain.REVOPS.value: {"can_read": True, "can_create": True, "can_update": True, "can_delete": True, "can_approve": True, "can_export": True, "scope_level": ScopeLevel.ALL},
            ResourceDomain.FINANCE.value: {"can_read": True, "can_create": True, "can_update": True, "can_delete": True, "can_approve": True, "can_export": True, "scope_level": ScopeLevel.ALL},
            ResourceDomain.HR.value: {"can_read": True, "can_create": True, "can_update": True, "can_delete": True, "can_approve": True, "can_export": True, "scope_level": ScopeLevel.ALL},
            ResourceDomain.PASTORAL.value: {"can_read": True, "can_create": True, "can_update": True, "can_delete": True, "can_approve": True, "can_export": True, "scope_level": ScopeLevel.ALL},
            ResourceDomain.CLINICAL.value: {"can_read": True, "can_create": False, "can_update": False, "can_delete": False, "can_approve": False, "can_export": False, "scope_level": ScopeLevel.ALL},
            ResourceDomain.OPERATIONS.value: {"can_read": True, "can_create": True, "can_update": True, "can_delete": True, "can_approve": True, "can_export": True, "scope_level": ScopeLevel.ALL},
            ResourceDomain.COMPLIANCE.value: {"can_read": True, "can_create": True, "can_update": True, "can_delete": True, "can_approve": True, "can_export": True, "scope_level": ScopeLevel.ALL},
        }
    },
    {
        "name": "Teacher",
        "slug": CoreRoleSlug.TEACHER.value,
        "description": "Instructional staff member managing assigned class sections, grading, curriculum, and pastoral notes",
        "is_system_template": True,
        "is_clinical_specialist": False,
        "rules": {
            ResourceDomain.ACADEMIC.value: {"can_read": True, "can_create": True, "can_update": True, "can_delete": False, "can_approve": True, "can_export": True, "scope_level": ScopeLevel.OWN_SECTION},
            ResourceDomain.REVOPS.value: {"can_read": False, "can_create": False, "can_update": False, "can_delete": False, "can_approve": False, "can_export": False, "scope_level": ScopeLevel.OWN_ONLY},
            ResourceDomain.FINANCE.value: {"can_read": False, "can_create": False, "can_update": False, "can_delete": False, "can_approve": False, "can_export": False, "scope_level": ScopeLevel.OWN_ONLY},
            ResourceDomain.HR.value: {"can_read": True, "can_create": False, "can_update": False, "can_delete": False, "can_approve": False, "can_export": False, "scope_level": ScopeLevel.OWN_ONLY},
            ResourceDomain.PASTORAL.value: {"can_read": True, "can_create": True, "can_update": True, "can_delete": False, "can_approve": False, "can_export": False, "scope_level": ScopeLevel.OWN_SECTION},
            ResourceDomain.CLINICAL.value: {"can_read": False, "can_create": False, "can_update": False, "can_delete": False, "can_approve": False, "can_export": False, "scope_level": ScopeLevel.OWN_ONLY},
            ResourceDomain.OPERATIONS.value: {"can_read": True, "can_create": True, "can_update": False, "can_delete": False, "can_approve": False, "can_export": False, "scope_level": ScopeLevel.OWN_SECTION},
            ResourceDomain.COMPLIANCE.value: {"can_read": True, "can_create": False, "can_update": False, "can_delete": False, "can_approve": False, "can_export": False, "scope_level": ScopeLevel.OWN_ONLY},
        }
    },
    {
        "name": "Student",
        "slug": CoreRoleSlug.STUDENT.value,
        "description": "Enrolled student accessing assigned courses, submissions, timetable, and learning resources",
        "is_system_template": True,
        "is_clinical_specialist": False,
        "rules": {
            ResourceDomain.ACADEMIC.value: {"can_read": True, "can_create": True, "can_update": False, "can_delete": False, "can_approve": False, "can_export": False, "scope_level": ScopeLevel.OWN_ONLY},
            ResourceDomain.REVOPS.value: {"can_read": False, "can_create": False, "can_update": False, "can_delete": False, "can_approve": False, "can_export": False, "scope_level": ScopeLevel.OWN_ONLY},
            ResourceDomain.FINANCE.value: {"can_read": True, "can_create": False, "can_update": False, "can_delete": False, "can_approve": False, "can_export": False, "scope_level": ScopeLevel.OWN_ONLY},
            ResourceDomain.HR.value: {"can_read": False, "can_create": False, "can_update": False, "can_delete": False, "can_approve": False, "can_export": False, "scope_level": ScopeLevel.OWN_ONLY},
            ResourceDomain.PASTORAL.value: {"can_read": True, "can_create": False, "can_update": False, "can_delete": False, "can_approve": False, "can_export": False, "scope_level": ScopeLevel.OWN_ONLY},
            ResourceDomain.CLINICAL.value: {"can_read": False, "can_create": False, "can_update": False, "can_delete": False, "can_approve": False, "can_export": False, "scope_level": ScopeLevel.OWN_ONLY},
            ResourceDomain.OPERATIONS.value: {"can_read": True, "can_create": False, "can_update": False, "can_delete": False, "can_approve": False, "can_export": False, "scope_level": ScopeLevel.OWN_ONLY},
            ResourceDomain.COMPLIANCE.value: {"can_read": False, "can_create": False, "can_update": False, "can_delete": False, "can_approve": False, "can_export": False, "scope_level": ScopeLevel.OWN_ONLY},
        }
    },
    {
        "name": "Parent",
        "slug": CoreRoleSlug.PARENT.value,
        "description": "Parent or legal guardian monitoring linked students' academic progress, attendance, and fee payments",
        "is_system_template": True,
        "is_clinical_specialist": False,
        "rules": {
            ResourceDomain.ACADEMIC.value: {"can_read": True, "can_create": False, "can_update": False, "can_delete": False, "can_approve": False, "can_export": False, "scope_level": ScopeLevel.OWN_ONLY},
            ResourceDomain.REVOPS.value: {"can_read": False, "can_create": False, "can_update": False, "can_delete": False, "can_approve": False, "can_export": False, "scope_level": ScopeLevel.OWN_ONLY},
            ResourceDomain.FINANCE.value: {"can_read": True, "can_create": True, "can_update": False, "can_delete": False, "can_approve": False, "can_export": True, "scope_level": ScopeLevel.OWN_ONLY},
            ResourceDomain.HR.value: {"can_read": False, "can_create": False, "can_update": False, "can_delete": False, "can_approve": False, "can_export": False, "scope_level": ScopeLevel.OWN_ONLY},
            ResourceDomain.PASTORAL.value: {"can_read": True, "can_create": False, "can_update": False, "can_delete": False, "can_approve": False, "can_export": False, "scope_level": ScopeLevel.OWN_ONLY},
            ResourceDomain.CLINICAL.value: {"can_read": False, "can_create": False, "can_update": False, "can_delete": False, "can_approve": False, "can_export": False, "scope_level": ScopeLevel.OWN_ONLY},
            ResourceDomain.OPERATIONS.value: {"can_read": True, "can_create": False, "can_update": False, "can_delete": False, "can_approve": False, "can_export": False, "scope_level": ScopeLevel.OWN_ONLY},
            ResourceDomain.COMPLIANCE.value: {"can_read": False, "can_create": False, "can_update": False, "can_delete": False, "can_approve": False, "can_export": False, "scope_level": ScopeLevel.OWN_ONLY},
        }
    },
    {
        "name": "Psychologist",
        "slug": CoreRoleSlug.PSYCHOLOGIST.value,
        "description": "Clinical mental health and counseling specialist with protected clinical records access",
        "is_system_template": True,
        "is_clinical_specialist": True,
        "rules": {
            ResourceDomain.ACADEMIC.value: {"can_read": True, "can_create": False, "can_update": False, "can_delete": False, "can_approve": False, "can_export": False, "scope_level": ScopeLevel.CAMPUS},
            ResourceDomain.REVOPS.value: {"can_read": False, "can_create": False, "can_update": False, "can_delete": False, "can_approve": False, "can_export": False, "scope_level": ScopeLevel.OWN_ONLY},
            ResourceDomain.FINANCE.value: {"can_read": False, "can_create": False, "can_update": False, "can_delete": False, "can_approve": False, "can_export": False, "scope_level": ScopeLevel.OWN_ONLY},
            ResourceDomain.HR.value: {"can_read": True, "can_create": False, "can_update": False, "can_delete": False, "can_approve": False, "can_export": False, "scope_level": ScopeLevel.OWN_ONLY},
            ResourceDomain.PASTORAL.value: {"can_read": True, "can_create": True, "can_update": True, "can_delete": False, "can_approve": False, "can_export": True, "scope_level": ScopeLevel.CAMPUS},
            ResourceDomain.CLINICAL.value: {"can_read": True, "can_create": True, "can_update": True, "can_delete": True, "can_approve": True, "can_export": True, "scope_level": ScopeLevel.CAMPUS},
            ResourceDomain.OPERATIONS.value: {"can_read": True, "can_create": False, "can_update": False, "can_delete": False, "can_approve": False, "can_export": False, "scope_level": ScopeLevel.CAMPUS},
            ResourceDomain.COMPLIANCE.value: {"can_read": True, "can_create": False, "can_update": False, "can_delete": False, "can_approve": False, "can_export": False, "scope_level": ScopeLevel.CAMPUS},
        }
    },
    {
        "name": "Staff",
        "slug": CoreRoleSlug.STAFF.value,
        "description": "General operational and support staff member supporting campus logistics and day-to-day administration",
        "is_system_template": True,
        "is_clinical_specialist": False,
        "rules": {
            ResourceDomain.ACADEMIC.value: {"can_read": True, "can_create": False, "can_update": False, "can_delete": False, "can_approve": False, "can_export": False, "scope_level": ScopeLevel.CAMPUS},
            ResourceDomain.REVOPS.value: {"can_read": False, "can_create": False, "can_update": False, "can_delete": False, "can_approve": False, "can_export": False, "scope_level": ScopeLevel.OWN_ONLY},
            ResourceDomain.FINANCE.value: {"can_read": False, "can_create": False, "can_update": False, "can_delete": False, "can_approve": False, "can_export": False, "scope_level": ScopeLevel.OWN_ONLY},
            ResourceDomain.HR.value: {"can_read": True, "can_create": False, "can_update": False, "can_delete": False, "can_approve": False, "can_export": False, "scope_level": ScopeLevel.OWN_ONLY},
            ResourceDomain.PASTORAL.value: {"can_read": False, "can_create": False, "can_update": False, "can_delete": False, "can_approve": False, "can_export": False, "scope_level": ScopeLevel.OWN_ONLY},
            ResourceDomain.CLINICAL.value: {"can_read": False, "can_create": False, "can_update": False, "can_delete": False, "can_approve": False, "can_export": False, "scope_level": ScopeLevel.OWN_ONLY},
            ResourceDomain.OPERATIONS.value: {"can_read": True, "can_create": True, "can_update": True, "can_delete": False, "can_approve": False, "can_export": False, "scope_level": ScopeLevel.CAMPUS},
            ResourceDomain.COMPLIANCE.value: {"can_read": False, "can_create": False, "can_update": False, "can_delete": False, "can_approve": False, "can_export": False, "scope_level": ScopeLevel.OWN_ONLY},
        }
    },
    {
        "name": "Bursar",
        "slug": CoreRoleSlug.BURSAR.value,
        "description": "Financial officer managing student billing, fee collection, accounts, refunds, and revenue operations",
        "is_system_template": True,
        "is_clinical_specialist": False,
        "rules": {
            ResourceDomain.ACADEMIC.value: {"can_read": True, "can_create": False, "can_update": False, "can_delete": False, "can_approve": False, "can_export": False, "scope_level": ScopeLevel.CAMPUS},
            ResourceDomain.REVOPS.value: {"can_read": True, "can_create": True, "can_update": True, "can_delete": False, "can_approve": False, "can_export": True, "scope_level": ScopeLevel.CAMPUS},
            ResourceDomain.FINANCE.value: {"can_read": True, "can_create": True, "can_update": True, "can_delete": False, "can_approve": True, "can_export": True, "scope_level": ScopeLevel.CAMPUS},
            ResourceDomain.HR.value: {"can_read": True, "can_create": False, "can_update": False, "can_delete": False, "can_approve": False, "can_export": False, "scope_level": ScopeLevel.CAMPUS},
            ResourceDomain.PASTORAL.value: {"can_read": False, "can_create": False, "can_update": False, "can_delete": False, "can_approve": False, "can_export": False, "scope_level": ScopeLevel.OWN_ONLY},
            ResourceDomain.CLINICAL.value: {"can_read": False, "can_create": False, "can_update": False, "can_delete": False, "can_approve": False, "can_export": False, "scope_level": ScopeLevel.OWN_ONLY},
            ResourceDomain.OPERATIONS.value: {"can_read": True, "can_create": False, "can_update": False, "can_delete": False, "can_approve": False, "can_export": False, "scope_level": ScopeLevel.CAMPUS},
            ResourceDomain.COMPLIANCE.value: {"can_read": True, "can_create": False, "can_update": False, "can_delete": False, "can_approve": False, "can_export": True, "scope_level": ScopeLevel.CAMPUS},
        }
    },
    {
        "name": "Librarian",
        "slug": CoreRoleSlug.LIBRARIAN.value,
        "description": "Resource manager handling library catalog, textbook distribution, and library fee/fine tracking",
        "is_system_template": True,
        "is_clinical_specialist": False,
        "rules": {
            ResourceDomain.ACADEMIC.value: {"can_read": True, "can_create": True, "can_update": True, "can_delete": False, "can_approve": True, "can_export": True, "scope_level": ScopeLevel.CAMPUS},
            ResourceDomain.REVOPS.value: {"can_read": False, "can_create": False, "can_update": False, "can_delete": False, "can_approve": False, "can_export": False, "scope_level": ScopeLevel.OWN_ONLY},
            ResourceDomain.FINANCE.value: {"can_read": True, "can_create": True, "can_update": True, "can_delete": False, "can_approve": False, "can_export": False, "scope_level": ScopeLevel.CAMPUS},
            ResourceDomain.HR.value: {"can_read": True, "can_create": False, "can_update": False, "can_delete": False, "can_approve": False, "can_export": False, "scope_level": ScopeLevel.OWN_ONLY},
            ResourceDomain.PASTORAL.value: {"can_read": False, "can_create": False, "can_update": False, "can_delete": False, "can_approve": False, "can_export": False, "scope_level": ScopeLevel.OWN_ONLY},
            ResourceDomain.CLINICAL.value: {"can_read": False, "can_create": False, "can_update": False, "can_delete": False, "can_approve": False, "can_export": False, "scope_level": ScopeLevel.OWN_ONLY},
            ResourceDomain.OPERATIONS.value: {"can_read": True, "can_create": True, "can_update": True, "can_delete": False, "can_approve": False, "can_export": False, "scope_level": ScopeLevel.CAMPUS},
            ResourceDomain.COMPLIANCE.value: {"can_read": True, "can_create": False, "can_update": False, "can_delete": False, "can_approve": False, "can_export": False, "scope_level": ScopeLevel.CAMPUS},
        }
    },
    {
        "name": "Transport Manager",
        "slug": CoreRoleSlug.TRANSPORT_MANAGER.value,
        "description": "Logistics coordinator managing buses, route assignments, drivers, and transit safety compliance",
        "is_system_template": True,
        "is_clinical_specialist": False,
        "rules": {
            ResourceDomain.ACADEMIC.value: {"can_read": True, "can_create": False, "can_update": False, "can_delete": False, "can_approve": False, "can_export": False, "scope_level": ScopeLevel.CAMPUS},
            ResourceDomain.REVOPS.value: {"can_read": False, "can_create": False, "can_update": False, "can_delete": False, "can_approve": False, "can_export": False, "scope_level": ScopeLevel.OWN_ONLY},
            ResourceDomain.FINANCE.value: {"can_read": True, "can_create": False, "can_update": False, "can_delete": False, "can_approve": False, "can_export": False, "scope_level": ScopeLevel.CAMPUS},
            ResourceDomain.HR.value: {"can_read": True, "can_create": False, "can_update": False, "can_delete": False, "can_approve": False, "can_export": False, "scope_level": ScopeLevel.CAMPUS},
            ResourceDomain.PASTORAL.value: {"can_read": False, "can_create": False, "can_update": False, "can_delete": False, "can_approve": False, "can_export": False, "scope_level": ScopeLevel.OWN_ONLY},
            ResourceDomain.CLINICAL.value: {"can_read": False, "can_create": False, "can_update": False, "can_delete": False, "can_approve": False, "can_export": False, "scope_level": ScopeLevel.OWN_ONLY},
            ResourceDomain.OPERATIONS.value: {"can_read": True, "can_create": True, "can_update": True, "can_delete": False, "can_approve": True, "can_export": True, "scope_level": ScopeLevel.CAMPUS},
            ResourceDomain.COMPLIANCE.value: {"can_read": True, "can_create": False, "can_update": False, "can_delete": False, "can_approve": False, "can_export": False, "scope_level": ScopeLevel.CAMPUS},
        }
    },
]


# ---------------------------------------------------------
# Seed Utility Functions
# ---------------------------------------------------------

async def seed_default_ems_roles(
    db_session: AsyncSession,
    org_id: Optional[int] = None
) -> List[EMSRole]:
    """
    Seed or reconcile the 10 core EMS system role templates and their standard
    permission rules across all 8 resource domains.

    Args:
        db_session: SQLModel AsyncSession
        org_id: Target organization ID, or None for global system templates.

    Returns:
        List of created or existing EMSRole instances.
    """
    seeded_roles: List[EMSRole] = []

    for spec in DEFAULT_EMS_ROLE_SPECS:
        slug = spec["slug"]
        stmt = select(EMSRole).where(
            EMSRole.slug == slug,
            EMSRole.org_id == org_id
        )
        result = await db_session.execute(stmt)
        role = result.scalars().first()

        if role is None:
            role = EMSRole(
                org_id=org_id,
                name=spec["name"],
                slug=slug,
                description=spec["description"],
                is_system_template=spec["is_system_template"],
                is_clinical_specialist=spec["is_clinical_specialist"],
                created_at=get_utc_now(),
                updated_at=get_utc_now(),
            )
            db_session.add(role)
            await db_session.flush()

        # Seed/reconcile permission rules
        rules_dict = spec.get("rules", {})
        for res_key, rule_data in rules_dict.items():
            rule_stmt = select(EMSPermissionRule).where(
                EMSPermissionRule.role_id == role.id,
                EMSPermissionRule.resource_key == res_key
            )
            rule_result = await db_session.execute(rule_stmt)
            perm_rule = rule_result.scalars().first()

            if perm_rule is None:
                perm_rule = EMSPermissionRule(
                    role_id=role.id,  # type: ignore
                    resource_key=res_key,
                    can_read=rule_data.get("can_read", False),
                    can_create=rule_data.get("can_create", False),
                    can_update=rule_data.get("can_update", False),
                    can_delete=rule_data.get("can_delete", False),
                    can_approve=rule_data.get("can_approve", False),
                    can_export=rule_data.get("can_export", False),
                    scope_level=rule_data.get("scope_level", ScopeLevel.ALL),
                    created_at=get_utc_now(),
                    updated_at=get_utc_now(),
                )
                db_session.add(perm_rule)
            else:
                # Update existing template rule properties
                perm_rule.can_read = rule_data.get("can_read", False)
                perm_rule.can_create = rule_data.get("can_create", False)
                perm_rule.can_update = rule_data.get("can_update", False)
                perm_rule.can_delete = rule_data.get("can_delete", False)
                perm_rule.can_approve = rule_data.get("can_approve", False)
                perm_rule.can_export = rule_data.get("can_export", False)
                perm_rule.scope_level = rule_data.get("scope_level", ScopeLevel.ALL)
                perm_rule.updated_at = get_utc_now()
                db_session.add(perm_rule)

        seeded_roles.append(role)

    await db_session.flush()
    return seeded_roles


def seed_default_ems_roles_sync(
    db_session: Session,
    org_id: Optional[int] = None
) -> List[EMSRole]:
    """Synchronous version of seed_default_ems_roles for migrations and CLI setup."""
    seeded_roles: List[EMSRole] = []

    for spec in DEFAULT_EMS_ROLE_SPECS:
        slug = spec["slug"]
        stmt = select(EMSRole).where(
            EMSRole.slug == slug,
            EMSRole.org_id == org_id
        )
        role = db_session.execute(stmt).scalars().first()

        if role is None:
            role = EMSRole(
                org_id=org_id,
                name=spec["name"],
                slug=slug,
                description=spec["description"],
                is_system_template=spec["is_system_template"],
                is_clinical_specialist=spec["is_clinical_specialist"],
                created_at=get_utc_now(),
                updated_at=get_utc_now(),
            )
            db_session.add(role)
            db_session.flush()

        rules_dict = spec.get("rules", {})
        for res_key, rule_data in rules_dict.items():
            rule_stmt = select(EMSPermissionRule).where(
                EMSPermissionRule.role_id == role.id,
                EMSPermissionRule.resource_key == res_key
            )
            perm_rule = db_session.execute(rule_stmt).scalars().first()

            if perm_rule is None:
                perm_rule = EMSPermissionRule(
                    role_id=role.id,  # type: ignore
                    resource_key=res_key,
                    can_read=rule_data.get("can_read", False),
                    can_create=rule_data.get("can_create", False),
                    can_update=rule_data.get("can_update", False),
                    can_delete=rule_data.get("can_delete", False),
                    can_approve=rule_data.get("can_approve", False),
                    can_export=rule_data.get("can_export", False),
                    scope_level=rule_data.get("scope_level", ScopeLevel.ALL),
                    created_at=get_utc_now(),
                    updated_at=get_utc_now(),
                )
                db_session.add(perm_rule)
            else:
                perm_rule.can_read = rule_data.get("can_read", False)
                perm_rule.can_create = rule_data.get("can_create", False)
                perm_rule.can_update = rule_data.get("can_update", False)
                perm_rule.can_delete = rule_data.get("can_delete", False)
                perm_rule.can_approve = rule_data.get("can_approve", False)
                perm_rule.can_export = rule_data.get("can_export", False)
                perm_rule.scope_level = rule_data.get("scope_level", ScopeLevel.ALL)
                perm_rule.updated_at = get_utc_now()
                db_session.add(perm_rule)

        seeded_roles.append(role)

    db_session.flush()
    return seeded_roles
