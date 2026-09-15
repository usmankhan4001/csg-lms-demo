"""
Cognia Accreditation Evidence storage (M16).

WHY THIS FILE EXISTS
--------------------
Accreditation evidence was held in a module-level Python list:

    _EVIDENCE_STORE: List[Dict[str, Any]] = []

That is not storage. It died on every container restart, and production runs
`WORKERS=4`, so four worker processes each held a different list -- a school
submitted an artifact to one worker and the other three had never heard of it.
The evidence a school spends a year assembling for an external review panel was
being kept in a variable.

This module replaces it with a real table.

IDENTITY
--------
`submitted_by_user_id` is the integer Learnhouse `user.id`, not the `user_uuid`
string that `principal.sub` carries. The string form is what produced the
two-incompatible-teacher-identities problem that migration `b7e2d41a9c38` had to
unpick, so a new table starts on the integer. The presented `sub` is retained
alongside it for the audit trail -- it records what the request actually
asserted, which is not always recoverable from the id later.

No foreign key is declared to `user`. `user` is built by
`SQLModel.metadata.create_all` at application boot and Alembic runs BEFORE that,
so a migration declaring `ForeignKey("user.id")` fails against a fresh database.
This matches `sms_timetable_schedule.teacher_id` and the columns added by
`b7e2d41a9c38`, which are soft links for the same reason.

INDEXES
-------
Declared with `index=True` on the fields only, never also as an explicit
`Index()` in `__table_args__`. Declaring both makes `create_all` emit CREATE
INDEX twice for one column and the API fails to boot. The accompanying
migration creates the same indexes using SQLAlchemy's own generated names
(`ix_<table>_<column>`), so whichever of the two builds this table first, the
names agree.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel


class CogniaEvidenceStatus(str, Enum):
    """Where an artifact sits in the school's own review workflow.

    SUBMITTED is the default and means a person has offered the artifact.
    VERIFIED means someone entitled to do so has accepted it. Nothing here
    implies Cognia has seen it -- the binder export says so explicitly.
    """

    SUBMITTED = "submitted"
    VERIFIED = "verified"


class CogniaEvidenceItem(SQLModel, table=True):
    """One evidence artifact mapped to one Cognia performance standard."""

    __tablename__ = "sms_cognia_evidence"

    id: Optional[int] = Field(default=None, primary_key=True)

    # Tenancy. org_id is NOT nullable: an accreditation record that belongs to
    # no school is meaningless, and the routers establish it with
    # `require_org_id`, which refuses rather than falling back to org 1.
    org_id: int = Field(index=True)
    campus_id: Optional[int] = Field(
        default=None,
        index=True,
        description="Null means the artifact is institution-wide rather than campus-specific.",
    )

    standard_code: str = Field(max_length=20, index=True, description="Cognia code, e.g. 1.1, 2.3")
    domain: str = Field(max_length=100, description="Resolved from standard_code at write time")
    title: str = Field(max_length=255)
    description: str
    evidence_type: str = Field(
        default="policy",
        max_length=50,
        description="policy | rubric | student_work | survey | assessment",
    )
    artifact_url: Optional[str] = Field(default=None, max_length=1000)
    academic_year: str = Field(max_length=20, index=True)

    # 1.0 Ineffective / 2.0 Developing / 3.0 Effective / 4.0 Exemplary.
    # Stored as given; the summary never invents one for a standard with no
    # artifact, which is the defect this table was built to end.
    performance_score: float

    status: CogniaEvidenceStatus = Field(default=CogniaEvidenceStatus.SUBMITTED)

    submitted_by_user_id: int = Field(index=True)
    submitted_by_sub: str = Field(
        max_length=255,
        description="The user_uuid the request presented, kept for the audit trail.",
    )
    verified_by_user_id: Optional[int] = Field(default=None)
    verified_at: Optional[datetime] = Field(default=None)

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
