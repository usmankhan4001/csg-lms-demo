"""
CSG-LMS Counseling / Wellbeing / Career Guidance Module (Phase 4, Part B)
==========================================================================
A genuinely new, separate, restricted dataset — deliberately NOT folded into
the existing M45 Student 360 Profile (src/routers/ai_student_profile.py /
src/services/ai/knowledge_graph.py). Per product decision: teachers/admins
viewing a student's general profile must see zero trace that counseling
records exist for that student.

Confidentiality is enforced in the service/router layers (see
src/services/sms/counseling.py and src/routers/sms_counseling.py), not here —
this module only defines the schema. See those files for the uniform
empty-result-not-403 rule mandated by DESIGN-SYSTEM.md §4/§10.

Three record types:
  1. CounselingActivityLog — psychologist-only engagement-signal log
     (attendance patterns, behavioral flags, ...).
  2. CounselingSession — structured 1:1 session record (date, duration,
     notes, follow-up plan), PSYCHOLOGIST-only except for the narrow
     `parent_visible_summary` slice (see class docstring).
  3. CareerGuidancePlan — an AI-generated structured career-guidance plan.
     Academic/advisory in nature, not a clinical record, so it is NOT
     subject to the same existence-masking rule as 1/2 (see the router).
"""

import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy import Boolean, Column, DateTime, Index, Integer, JSON, String, Text
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


class CounselingActivityLog(SQLModel, table=True):
    """Psychologist-only record of a student engagement signal relevant to
    counseling (an attendance pattern, a behavioral flag, ...). A simple
    activity-log table, not a diagnosis or treatment record."""
    __tablename__ = "sms_counseling_activity_log"
    __table_args__ = (
        Index("ix_counseling_activity_student", "student_id"),
        Index("ix_counseling_activity_psychologist", "psychologist_id"),
        # Same NAME the migration uses. On an existing database migration
        # b7e2d41a9c38 creates it and `create_all` skips the whole table; on a
        # FRESH database the migration skips (the table does not exist yet) and
        # `create_all` builds the table from here -- without this line the new
        # column would be unindexed on every new deployment.
        Index("ix_counseling_activity_psych_user_id", "psychologist_user_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    student_id: int = Field(sa_column=Column(Integer, nullable=False, index=True))
    # Bound to the authenticated PSYCHOLOGIST's Keycloak `sub` at creation
    # time (see services/sms/counseling.py) — never trusted from the request
    # body, so read-scoping by this column is a real authorization boundary,
    # not a client-declared identity.
    psychologist_id: str = Field(sa_column=Column(String(255), nullable=False, index=True))

    # Canonical clinician identity: integer `user.id`, matching timetable,
    # live classes and section ownership. `psychologist_id` above is the legacy
    # user_uuid STRING -- see migration b7e2d41a9c38. Both are written during
    # the transition; the string is dropped by a later migration once its
    # backfill is confirmed.
    #
    # Nullable even though `psychologist_id` is NOT NULL: a row written before
    # this column existed, or whose string matched no user, has no integer to
    # carry. NULL here means "not yet resolved", never "no clinician".
    #
    # No `index=True`: migration b7e2d41a9c38 creates the index. Declaring both
    # an explicit Index and index=True on one column makes `create_all` emit
    # CREATE INDEX twice, which stops the API booting.
    psychologist_user_id: Optional[int] = Field(
        default=None, sa_column=Column(Integer, nullable=True)
    )
    signal_type: str = Field(sa_column=Column(String(50), nullable=False))
    description: str = Field(sa_column=Column(Text, nullable=False))
    severity: str = Field(default="low", sa_column=Column(String(20), nullable=False))
    recorded_at: datetime.datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False, default=_utcnow),
    )


class CounselingSession(SQLModel, table=True):
    """Structured 1:1 counseling session record. Confidential
    (PSYCHOLOGIST-only) in full, except for the narrow parent-involvement
    slice: when `share_summary_with_parent` is True, `parent_visible_summary`
    (a separate, deliberately non-clinical field) is surfaced to the
    student's PARENT — see list_parent_visible_sessions in
    services/sms/counseling.py. This is the "loop a parent in" mechanism:
    a boolean flag plus a parent-safe summary field, not a messaging system."""
    __tablename__ = "sms_counseling_session"
    __table_args__ = (
        Index("ix_counseling_session_student", "student_id"),
        Index("ix_counseling_session_psychologist", "psychologist_id"),
        # Same NAME the migration uses. On an existing database migration
        # b7e2d41a9c38 creates it and `create_all` skips the whole table; on a
        # FRESH database the migration skips (the table does not exist yet) and
        # `create_all` builds the table from here -- without this line the new
        # column would be unindexed on every new deployment.
        Index("ix_counseling_session_psych_user_id", "psychologist_user_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    student_id: int = Field(sa_column=Column(Integer, nullable=False, index=True))
    psychologist_id: str = Field(sa_column=Column(String(255), nullable=False, index=True))

    # Canonical clinician identity: integer `user.id`, matching timetable,
    # live classes and section ownership. `psychologist_id` above is the legacy
    # user_uuid STRING -- see migration b7e2d41a9c38. Both are written during
    # the transition; the string is dropped by a later migration once its
    # backfill is confirmed.
    #
    # Nullable even though `psychologist_id` is NOT NULL: a row written before
    # this column existed, or whose string matched no user, has no integer to
    # carry. NULL here means "not yet resolved", never "no clinician".
    #
    # No `index=True`: migration b7e2d41a9c38 creates the index. Declaring both
    # an explicit Index and index=True on one column makes `create_all` emit
    # CREATE INDEX twice, which stops the API booting.
    psychologist_user_id: Optional[int] = Field(
        default=None, sa_column=Column(Integer, nullable=True)
    )
    session_date: datetime.datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    duration_minutes: int = Field(sa_column=Column(Integer, nullable=False))
    notes: str = Field(sa_column=Column(Text, nullable=False))
    follow_up_plan: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    share_summary_with_parent: bool = Field(default=False, sa_column=Column(Boolean, nullable=False))
    parent_visible_summary: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    created_at: datetime.datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False, default=_utcnow),
    )
    updated_at: datetime.datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False, default=_utcnow),
    )


class CareerGuidancePlan(SQLModel, table=True):
    """An AI-generated structured career-guidance plan for a student: a
    single generate-and-store operation, not a conversational agent. Not a
    clinical/confidential record (see module docstring) — visible to the
    student, their parent, and school staff, unlike CounselingActivityLog /
    CounselingSession."""
    __tablename__ = "sms_career_guidance_plan"
    __table_args__ = (
        Index("ix_career_plan_student", "student_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    student_id: int = Field(sa_column=Column(Integer, nullable=False, index=True))
    # Keycloak `sub` of whoever triggered generation (counselor/teacher/admin).
    generated_by: Optional[str] = Field(default=None, sa_column=Column(String(255), nullable=True))
    suggested_pathways: List[Dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    reasoning: str = Field(sa_column=Column(Text, nullable=False))
    next_steps: List[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    generated_at: datetime.datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False, default=_utcnow),
    )
