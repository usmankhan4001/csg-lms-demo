"""
RevOps Admin Config (M30) and Knowledge Base (M34) storage.

M30 mirrors the shape of `db/sms_settings.py` deliberately: one row per
(org, campus, group) with the group's fields as a JSON payload, resolving
campus -> org -> code default. It is a SEPARATE table rather than new group
keys on `sms_school_settings` because the two are different administrative
domains -- academic policy is the registrar's, funnel behaviour is the
admissions officer's -- and separating them keeps their role gates and audit
independent. The cost is a small amount of duplicated resolution logic.

M34 is the managed knowledge base the RevOps agents draw on. Its point is
traceability: an answer given to a family should be traceable to something a
human approved, which is why `source_label` exists and is NULLABLE. An entry
with no source is stored as sourceless. A synthesised citation would be worse
than none -- this codebase has had fabricated content torn out three times,
including outbound copy naming a school that does not exist.

NOTE ON UNIQUENESS (M30), same reasoning as sms_settings: there is
deliberately NO UniqueConstraint spanning `campus_id`, because that column is
nullable and NULL != NULL in SQL. On Postgres such a constraint would silently
fail to prevent duplicate ORG-LEVEL rows -- exactly the case that matters
most. Uniqueness is enforced read-before-write in services/sms/revops_config.py.

NOTE ON INDEXES: every index below is declared ONLY in `__table_args__` with an
explicit name, and NO column carries `index=True`. SQLAlchemy auto-names a
column index `ix_<table>_<column>`, and a collision makes `create_all` emit
CREATE INDEX twice -- which has already taken this API down once.
"""

import datetime
from enum import Enum
from typing import Any, Dict, Optional

from sqlalchemy import JSON, Column, DateTime, Index, Integer, String, Text
from sqlmodel import Field, SQLModel


class RevOpsConfig(SQLModel, table=True):
    """One RevOps config group, for one org, optionally scoped to one campus."""

    __tablename__ = "sms_revops_config"
    __table_args__ = (
        Index("ix_sms_revops_config_scope", "org_id", "campus_id", "group_key"),
        {"extend_existing": True},
    )

    id: Optional[int] = Field(default=None, primary_key=True)

    org_id: int = Field(sa_column=Column(Integer, nullable=False))

    # NULL = the org-wide default row. A campus-scoped row overrides it.
    campus_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))

    # One of RevOpsConfigGroup (schemas/sms_revops_config.py).
    group_key: str = Field(sa_column=Column(String(64), nullable=False))

    # Validated against its Pydantic model on write, so never an arbitrary blob.
    payload: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))

    updated_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    # Who last changed it. Scoring weights decide which families get chased,
    # so an unattributed change is not good enough.
    updated_by_user_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))


class KnowledgeEntryStatus(str, Enum):
    """Publication state of a knowledge base entry.

    Only PUBLISHED entries are served to agents: a draft is a human's working
    note, not something to quote at a parent.
    """

    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"


class RevOpsKnowledgeEntry(SQLModel, table=True):
    """One piece of approved knowledge the admissions agents may draw on.

    `source_label` and `source_url` are both nullable and are never filled in
    automatically. An entry without a source is sourceless, and the read model
    reports that plainly so a reviewer can see which claims are unbacked.
    """

    __tablename__ = "sms_revops_knowledge_entry"
    __table_args__ = (
        Index("ix_sms_revops_kb_scope", "org_id", "campus_id", "status"),
        Index("ix_sms_revops_kb_category", "org_id", "category"),
        {"extend_existing": True},
    )

    id: Optional[int] = Field(default=None, primary_key=True)

    org_id: int = Field(sa_column=Column(Integer, nullable=False))
    # NULL = applies to the whole organisation, not one campus.
    campus_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))

    title: str = Field(sa_column=Column(String(300), nullable=False))
    body: str = Field(sa_column=Column(Text, nullable=False))

    # Free-text grouping ("fees", "curriculum", "admissions process"). A plain
    # string rather than an enum so a school can organise its own way.
    category: Optional[str] = Field(default=None, sa_column=Column(String(120), nullable=True))

    # Where this claim comes from. NULLABLE and never synthesised.
    source_label: Optional[str] = Field(default=None, sa_column=Column(String(300), nullable=True))
    source_url: Optional[str] = Field(default=None, sa_column=Column(String(600), nullable=True))

    status: str = Field(
        default=KnowledgeEntryStatus.DRAFT.value,
        sa_column=Column(String(20), nullable=False),
    )

    # The human accountable for this entry being correct.
    owner_user_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))

    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_by_user_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))
