"""cognia accreditation evidence: a real table, replacing a Python list

WHY THIS EXISTS
---------------
`routers/sms_cognia.py` kept accreditation evidence in a module-level global:

    _EVIDENCE_STORE: List[Dict[str, Any]] = []

Every artifact a school submitted was lost on container restart, and production
runs `WORKERS=4` -- four processes, four independent lists, so an artifact
written by one worker was invisible to the other three. A school assembling a
year of evidence for an external review panel was keeping it in a variable.

WHY NO FOREIGN KEY TO `user`
----------------------------
`user` is not created by Alembic. It is built by `SQLModel.metadata.create_all`
at application boot, and Alembic runs BEFORE that, so a migration declaring
`ForeignKey("user.id")` fails against a fresh database. `submitted_by_user_id`
and `verified_by_user_id` are therefore plain integers -- the same soft-link
convention as `sms_timetable_schedule.teacher_id` and the columns added by
`b7e2d41a9c38`.

WHY THE INDEX NAMES LOOK AUTO-GENERATED
---------------------------------------
They are: `ix_<table>_<column>` is exactly what SQLAlchemy emits for a field
declared `index=True`, which is how `db/sms_cognia.py` declares them. Either
this migration builds the table or `create_all` does, depending on which runs
against a given database first, and the names have to agree in both cases.

The model deliberately does NOT also declare these in `__table_args__`:
declaring an explicit `Index()` and `index=True` on one column makes
`create_all` emit CREATE INDEX twice and the API fails to boot.

WHY THE WHOLE THING IS GUARDED
------------------------------
`create_all` may already have built this table on an environment that booted
before this migration was applied -- which is the normal case here, since this
project's schema was built by `create_all` for months and migrations were never
run. Creating it unconditionally would abort the migration run with
"relation already exists" and, with the hardened entrypoint, stop the API.

Revision ID: c4f81a7d2e93
Revises: b7e2d41a9c38
Create Date: 2026-09-15

"""
import logging
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa  # noqa: F401
import sqlmodel  # noqa: F401


# revision identifiers, used by Alembic.
revision: str = "c4f81a7d2e93"
down_revision: Union[str, None] = "b7e2d41a9c38"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger("alembic.runtime.migration")

_TABLE = "sms_cognia_evidence"

# (column, index name) -- names match SQLAlchemy's own `index=True` convention.
_INDEXES = [
    ("org_id", "ix_sms_cognia_evidence_org_id"),
    ("campus_id", "ix_sms_cognia_evidence_campus_id"),
    ("standard_code", "ix_sms_cognia_evidence_standard_code"),
    ("academic_year", "ix_sms_cognia_evidence_academic_year"),
    ("submitted_by_user_id", "ix_sms_cognia_evidence_submitted_by_user_id"),
]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _TABLE in set(inspector.get_table_names()):
        logger.info(
            "cognia_evidence: %s already exists (create_all built it); skipping.", _TABLE
        )
        return

    op.create_table(
        _TABLE,
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("org_id", sa.Integer(), nullable=False),
        sa.Column("campus_id", sa.Integer(), nullable=True),
        sa.Column("standard_code", sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False),
        sa.Column("domain", sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False),
        sa.Column("title", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column("description", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("evidence_type", sqlmodel.sql.sqltypes.AutoString(length=50), nullable=False),
        sa.Column("artifact_url", sqlmodel.sql.sqltypes.AutoString(length=1000), nullable=True),
        sa.Column("academic_year", sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False),
        sa.Column("performance_score", sa.Float(), nullable=False),
        # The status enum is stored as its string value rather than a native
        # Postgres ENUM type: adding a member to a native enum needs its own
        # migration and a lock, and this workflow is likely to grow one.
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False),
        sa.Column("submitted_by_user_id", sa.Integer(), nullable=False),
        sa.Column("submitted_by_sub", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column("verified_by_user_id", sa.Integer(), nullable=True),
        sa.Column("verified_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    for column, index_name in _INDEXES:
        op.create_index(index_name, _TABLE, [column])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if _TABLE not in set(inspector.get_table_names()):
        return
    for _column, index_name in _INDEXES:
        op.drop_index(index_name, table_name=_TABLE)
    op.drop_table(_TABLE)
