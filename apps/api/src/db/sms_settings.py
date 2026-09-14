"""
CSG School Settings -- the store that lets a school configure itself.

Why this exists: grading scales, fee policy and attendance rules were
hardcoded Python constants (services/sms/fees.py:150-153,
services/sms/gradebook.py:33). A school on a different grading scale, or with
a different late-fee policy, could not use those modules correctly without a
code change. This is the operator layer those modules were missing.

Shape: one row per (org, campus, settings group), with the group's fields as
a JSON payload rather than a column each. The groups will grow -- that is the
whole point of a settings surface -- and a column-per-field table would need a
schema change every time. `OrganizationConfig` already uses this pattern in
this codebase for the same reason.

Resolution is campus -> org -> code default:

    campus_id = 5    a row specific to campus 5, wins for that campus
    campus_id = NULL the org-wide default, used by any campus without its own
    (no row)         the hardcoded constant in schemas/sms_settings.py

Per-campus matters because a multi-campus school may genuinely run different
fee policies per campus, and `campus_id` is already the tenancy root every
other SMS module scopes against.

NOTE ON UNIQUENESS. There is deliberately NO UniqueConstraint spanning
`campus_id`, because that column is nullable and NULL != NULL in SQL: on
Postgres such a constraint would silently fail to prevent duplicate ORG-LEVEL
rows, which is exactly the case that matters most. (Partial unique indexes
would work but differ between Postgres and the SQLite used by the test suite.)
Uniqueness is enforced in services/sms/settings.py by reading before writing,
and `resolve_settings_group` orders deterministically so even a duplicate row
could never produce an inconsistent read.
"""

import datetime
from typing import Any, Dict, Optional

from sqlalchemy import JSON, Column, DateTime, Index, Integer, String
from sqlmodel import Field, SQLModel


class SchoolSettings(SQLModel, table=True):
    """One settings group, for one org, optionally scoped to one campus."""

    __tablename__ = "sms_school_settings"
    __table_args__ = (
        # Lookup index only -- see the module docstring on why this is not a
        # UniqueConstraint. Named explicitly, and NO `index=True` on any of
        # these columns: SQLAlchemy auto-names a column index identically and
        # `create_all` would then emit CREATE INDEX twice, which has already
        # taken this API down once.
        Index("ix_sms_school_settings_scope", "org_id", "campus_id", "group_key"),
        {"extend_existing": True},
    )

    id: Optional[int] = Field(default=None, primary_key=True)

    org_id: int = Field(sa_column=Column(Integer, nullable=False))

    # NULL = the org-wide default row. A campus-scoped row overrides it.
    campus_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))

    # One of SettingsGroup (schemas/sms_settings.py). Stored as a plain string
    # rather than a native enum so adding a group needs no ALTER TYPE -- the
    # activity-type enum in this project required exactly that migration.
    group_key: str = Field(sa_column=Column(String(64), nullable=False))

    # The group's fields. Validated against its Pydantic model on write, so
    # this is never an arbitrary blob.
    payload: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))

    updated_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    # Who last changed it. Settings drive money and grades, so an unattributed
    # change is not good enough.
    updated_by_user_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))
