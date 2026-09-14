"""
Data-subject request log (access / erasure).
=============================================

Every subject-access export and every erasure is recorded here, because a
data-protection regime asks two questions this system previously could not
answer: *who looked at this child's record*, and *what did you delete and on
whose authority*.

Deliberately APPEND-ONLY. There is no update or delete path in the service or
the router. A log that can be rewritten is not a log -- if an erasure record
can itself be erased, the trail proves nothing.

Note this is a log of REQUESTS, not a copy of the data. It stores what was
covered (table names and row counts) and never the exported content, so the
log itself does not become a second, unguarded copy of a child's record.
"""

import datetime
from typing import Any, Dict, Optional

from sqlalchemy import Boolean, Column, DateTime, Index, Integer, JSON, String
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


class DataSubjectRequestLog(SQLModel, table=True):
    """One row per access or erasure request. Append-only."""

    # Custom index names only -- no `index=True` on any column. SQLAlchemy
    # auto-names a column index `ix_<table>_<column>`, and declaring both forms
    # made create_all emit CREATE INDEX twice elsewhere in this codebase, which
    # stopped the API booting.
    __tablename__ = "sms_data_subject_request"
    __table_args__ = (
        Index("ix_dsr_subject_time", "subject_user_id", "created_at"),
        Index("ix_dsr_org", "org_id"),
        {"extend_existing": True},
    )

    id: Optional[int] = Field(default=None, primary_key=True)

    # Who the request was ABOUT.
    subject_user_id: int = Field(sa_column=Column(Integer, nullable=False))

    # Who asked, and who actually executed it. Both come from the
    # authenticated principal, never from a payload.
    requested_by_user_id: Optional[int] = Field(
        default=None, sa_column=Column(Integer, nullable=True)
    )
    requested_by_role: Optional[str] = Field(
        default=None, sa_column=Column(String(64), nullable=True)
    )

    org_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))

    # "ACCESS" or "ERASURE".
    request_type: str = Field(sa_column=Column(String(32), nullable=False))

    # Itemised outcome: {"erased": {"table": n}, "retained": [{...}]} or
    # {"exported": {"table": n}}. Counts and table names only -- never content.
    outcome: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))

    # Whether the caller was entitled to see confidential (counselling /
    # safeguarding) records. Recorded so an auditor can tell a clinical
    # export from a routine one WITHOUT the row revealing that such records
    # exist for this child -- this is a property of the CALLER, not the child.
    included_confidential: bool = Field(
        default=False, sa_column=Column(Boolean, nullable=False, default=False)
    )

    created_at: datetime.datetime = Field(
        default_factory=_utcnow, sa_column=Column(DateTime(timezone=True), nullable=False)
    )
