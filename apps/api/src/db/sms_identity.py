"""
CSG-LMS School Identity Models
===============================
Carries the school-specific claims (role, campus assignment, parent-child
linkage) that a real Keycloak server would have carried, now that
`src/security/school_principal.py` derives the SMS auth principal from
Learnhouse's own real, already-authenticated session instead of a separate
dev-only Keycloak-shaped JWT. See PROJECT_DOCS/ARCHITECTURE.md for the full
two-auth-systems background this replaces.

Both tables are purely additive (no ALTER on any existing table), matching
every other `sms_*` model in this codebase: picked up by
`SQLModel.metadata.create_all` at app startup (`src/core/events/database.py`),
never through Alembic (confirmed: none of the 13 sms_* modules ever have been).
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlmodel import Field, SQLModel


def get_utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SchoolRole(str, Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    SCHOOL_ADMIN = "SCHOOL_ADMIN"
    TEACHER = "TEACHER"
    STUDENT = "STUDENT"
    PARENT = "PARENT"
    STAFF = "STAFF"
    PSYCHOLOGIST = "PSYCHOLOGIST"


class SMSUserRole(SQLModel, table=True):
    """
    A grant of one school role to a real Learnhouse user, scoped to an org
    and (optionally) a campus. This is the single source of truth for
    `KeycloakUserPrincipal.org_id` / `.campus_id` / `.roles` once
    `resolve_school_principal()` builds the principal from a real session
    instead of decoding a JWT -- an admin-managed grant, not something
    derived by joining other tables.

    A user may hold more than one row (e.g. a teacher who is also a parent),
    so this is NOT unique on `user_id` alone.
    """

    __tablename__ = "sms_user_role"
    __table_args__ = (
        UniqueConstraint("user_id", "org_id", "role", name="uq_sms_user_role_user_org_role"),
        Index("ix_sms_user_role_org_campus", "org_id", "campus_id"),
        {"extend_existing": True},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(sa_column=Column(Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True))
    org_id: int = Field(sa_column=Column(Integer, ForeignKey("organization.id", ondelete="CASCADE"), nullable=False))
    campus_id: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("campus.id", ondelete="SET NULL"), nullable=True),
        description="Null for org-level roles (e.g. an org-wide SCHOOL_ADMIN not scoped to one campus).",
    )
    role: SchoolRole = Field(sa_column=Column(String(32), nullable=False))
    is_active: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, server_default="true"))
    created_at: datetime = Field(default_factory=get_utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=get_utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class StudentGuardian(SQLModel, table=True):
    """
    Parent/guardian <-> student linkage. This has never existed anywhere in
    this codebase before -- `children_ids` was previously a pure dev-token
    JWT convenience claim with zero database backing (confirmed via
    repo-wide search: no parent/guardian table existed prior to this file).
    """

    __tablename__ = "sms_student_guardian"
    __table_args__ = (
        UniqueConstraint("guardian_user_id", "student_id", name="uq_sms_student_guardian_pair"),
        Index("ix_sms_student_guardian_student", "student_id"),
        Index("ix_sms_student_guardian_guardian", "guardian_user_id"),
        {"extend_existing": True},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    guardian_user_id: int = Field(sa_column=Column(Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False))
    student_id: int = Field(sa_column=Column(Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False))
    relationship: Optional[str] = Field(default=None, max_length=50, description="e.g. 'mother', 'father', 'guardian'")
    is_primary_contact: bool = Field(default=False, sa_column=Column(Boolean, nullable=False, server_default="false"))
    created_at: datetime = Field(default_factory=get_utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


# ---------------------------------------------------------
# API schemas
# ---------------------------------------------------------

class SMSUserRoleCreate(SQLModel):
    user_id: int
    org_id: int
    role: SchoolRole
    campus_id: Optional[int] = None


class SMSUserRoleRead(SQLModel):
    id: int
    user_id: int
    org_id: int
    campus_id: Optional[int]
    role: SchoolRole
    is_active: bool


class StudentGuardianCreate(SQLModel):
    guardian_user_id: int
    student_id: int
    relationship: Optional[str] = None
    is_primary_contact: bool = False


class StudentGuardianRead(SQLModel):
    id: int
    guardian_user_id: int
    student_id: int
    relationship: Optional[str]
    is_primary_contact: bool
