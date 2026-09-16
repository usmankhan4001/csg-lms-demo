"""Enforce timetable slot uniqueness at the database level

``detect_timetable_clashes`` is a read-then-write check: two concurrent
``POST /sms/timetable/schedules`` requests both SELECT an empty slot and both
INSERT, so a teacher ends up timetabled for two sections in one period (or a
section for two lessons) with no error at all. ``scan_timetable_conflicts``
exists precisely to find the rows this leaves behind.

Adds four partial UNIQUE indexes on ``sms_timetable_schedule``:

* ``uq_sms_tt_teacher_slot_term``    -- (teacher_id, day_of_week, period_id,
  academic_term_id) WHERE academic_term_id IS NOT NULL
* ``uq_sms_tt_teacher_slot_no_term`` -- (teacher_id, day_of_week, period_id)
  WHERE academic_term_id IS NULL
* ``uq_sms_tt_section_slot_term``    -- (section_id, day_of_week, period_id,
  academic_term_id) WHERE academic_term_id IS NOT NULL
* ``uq_sms_tt_section_slot_no_term`` -- (section_id, day_of_week, period_id)
  WHERE academic_term_id IS NULL

Two per key, not one: ``academic_term_id`` is nullable and NULL != NULL in
SQL, so a single unique index over it would let unlimited duplicates through
wherever the term is unset -- which is every school that does not run terms.
The partial indexes split the rows into "has a term" and "has no term" and
make each group unique on its own.

Existing duplicates are deleted first (lowest id wins), because a UNIQUE index
cannot be built over rows that already violate it and the migration would
otherwise abort on any database that already has a clash -- which is the
common case, since nothing has been preventing them. A duplicate here is not
a judgement call: the same teacher cannot be in two places at once, so one of
the rows is definitionally wrong. The count removed is logged.

Revision ID: b5c6d7e8f9a0
Revises: c5d6e7f8a9b0
Create Date: 2026-09-16

"""
import logging
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel  # noqa: F401


logger = logging.getLogger("alembic.runtime.migration")

revision: str = 'b5c6d7e8f9a0'
down_revision: Union[str, None] = 'c5d6e7f8a9b0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_TABLE = 'sms_timetable_schedule'

# (index name, key columns, term predicate)
_INDEXES = [
    ('uq_sms_tt_teacher_slot_term',
     ['teacher_id', 'day_of_week', 'period_id', 'academic_term_id'],
     'academic_term_id IS NOT NULL'),
    ('uq_sms_tt_teacher_slot_no_term',
     ['teacher_id', 'day_of_week', 'period_id'],
     'academic_term_id IS NULL'),
    ('uq_sms_tt_section_slot_term',
     ['section_id', 'day_of_week', 'period_id', 'academic_term_id'],
     'academic_term_id IS NOT NULL'),
    ('uq_sms_tt_section_slot_no_term',
     ['section_id', 'day_of_week', 'period_id'],
     'academic_term_id IS NULL'),
]


def _dedupe(bind, cols: Sequence[str], predicate: str) -> int:
    """Delete rows that duplicate `cols`, keeping the lowest id.

    Correlated EXISTS rather than DELETE..USING so the statement is portable
    (the migration harness runs on SQLite too), and an explicit NULL-safe term
    comparison because `=` alone would never match a NULL term.
    """
    keys = " AND ".join(f"y.{c} = x.{c}" for c in cols if c != 'academic_term_id')
    if 'academic_term_id' in cols:
        term = "y.academic_term_id = x.academic_term_id"
    else:
        term = "y.academic_term_id IS NULL AND x.academic_term_id IS NULL"
    result = bind.execute(
        sa.text(
            f"""
            DELETE FROM {_TABLE} AS x
            WHERE {predicate.replace('academic_term_id', 'x.academic_term_id')}
              AND EXISTS (
                  SELECT 1 FROM {_TABLE} AS y
                  WHERE {keys}
                    AND {term}
                    AND y.id < x.id
              )
            """
        )
    )
    return result.rowcount or 0


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _TABLE not in inspector.get_table_names():
        return

    existing = {
        idx['name'] for idx in inspector.get_indexes(_TABLE) if idx.get('name')
    }

    for name, cols, predicate in _INDEXES:
        if name in existing:
            continue
        removed = _dedupe(bind, cols, predicate)
        if removed:
            logger.warning(
                "Removed %s duplicate %s row(s) that violated %s; kept the "
                "lowest id of each group.",
                removed, _TABLE, name,
            )
        op.create_index(
            name,
            _TABLE,
            cols,
            unique=True,
            postgresql_where=sa.text(predicate),
            sqlite_where=sa.text(predicate),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _TABLE not in inspector.get_table_names():
        return

    existing = {
        idx['name'] for idx in inspector.get_indexes(_TABLE) if idx.get('name')
    }

    for name, _cols, _predicate in _INDEXES:
        if name not in existing:
            continue
        op.drop_index(name, table_name=_TABLE)
