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


class SMSImpersonationEvent(SQLModel, table=True):
    """Durable audit trail for superadmin impersonation (start/stop). Separate
    from UserAuditEvent (apps/api/src/db/user_audit_events.py), which is
    deliberately scoped to learner activity only, not admin actions."""

    __tablename__ = "sms_impersonation_event"
    __table_args__ = ({"extend_existing": True},)

    id: Optional[int] = Field(default=None, primary_key=True)
    actor_user_id: int = Field(sa_column=Column(Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True))
    target_user_id: int = Field(sa_column=Column(Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True))
    action: str = Field(sa_column=Column(String(16), nullable=False))  # "start" | "stop"
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


class PersonProvisioningAction:
    """How a `SMSPersonProvisioningEvent` row came about.

    ``CREATED`` is a brand-new account minted by an administrator.
    ``REUSED`` is a provisioning request that matched an existing account by
    email and granted it a role instead of creating a second one. They must
    stay distinguishable: "we created this account" and "we attached a role to
    an account that already existed" are different facts if the person later
    disputes who has access to what.
    """

    CREATED = "created"
    REUSED = "reused"


class SMSPersonProvisioningEvent(SQLModel, table=True):
    """Append-only audit trail for every account an administrator provisions.

    Creating an account and granting it a school role are security events. Two
    of them, in fact, and neither was recorded anywhere before this: a role
    granted through ``POST /sms/identity/roles`` overwrites its own row in
    place (see `assign_role`), so "who gave this person TEACHER, and when"
    had no answer available in the system at all.

    Shape deliberately copied from ``sms_grade_change_event``
    (db/sms_gradebook.py), which ``sms_attendance_change_event``,
    ``sms_fee_change_event`` and the HR trail already copy -- a fifth audit
    idiom would mean five places to look during an investigation.

    Identifying columns are plain integers, not foreign keys, and the email and
    role are SNAPSHOTTED rather than joined. ``SMSUserRole.user_id`` is
    ``ondelete="CASCADE"``, so an FK-linked trail would be destroyed by
    deleting the user -- exactly when the record matters most.

    APPEND-ONLY: nothing writes to these rows after insert and no endpoint
    exposes a way to.
    """

    __tablename__ = "sms_person_provisioning_event"
    __table_args__ = (
        Index("ix_sms_provisioning_org", "org_id", "created_at"),
        Index("ix_sms_provisioning_subject", "subject_user_id", "created_at"),
        {"extend_existing": True},
    )

    id: Optional[int] = Field(default=None, primary_key=True)

    # The account this describes. A plain Integer, not an FK: see docstring.
    subject_user_id: int = Field(sa_column=Column(Integer, nullable=False))
    # Snapshot, so the trail stays legible after the user row is deleted.
    subject_email: str = Field(sa_column=Column(String(255), nullable=False))

    org_id: int = Field(sa_column=Column(Integer, nullable=False))
    campus_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))
    role: str = Field(sa_column=Column(String(32), nullable=False))

    action: str = Field(sa_column=Column(String(16), nullable=False))

    # What else the same request did, so a half-provisioned person is visible
    # in the trail rather than inferred from three other tables.
    enrolled_section_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))
    linked_student_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))

    # The AUTHENTICATED caller, resolved from the principal -- never a
    # client-supplied field. Nullable only because a principal may carry no
    # resolvable Learnhouse user id; an unattributed row still beats no row.
    actor_user_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))

    # True when the account was created as part of a bulk import, so a school
    # can tell a cohort upload from a one-off admission.
    via_bulk_import: bool = Field(default=False, sa_column=Column(Boolean, nullable=False, server_default="false"))

    created_at: datetime = Field(
        default_factory=get_utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
