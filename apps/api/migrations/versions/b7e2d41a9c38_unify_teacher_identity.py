"""unify teacher identity: add integer user-id columns beside the string ones

WHY THIS EXISTS
---------------
This system stored "which teacher" two incompatible ways and could not join
them:

  * `sms_lesson_plan.teacher_id`            VARCHAR(255)  -- user_uuid string
  * `sms_counseling_activity_log.psychologist_id` VARCHAR(255) -- user_uuid string
  * `sms_counseling_session.psychologist_id`  VARCHAR(255) -- user_uuid string

  * `sms_timetable_schedule.teacher_id`      INTEGER      -- user.id
  * `sms_timetable_substitution.original_teacher_id` / `.substitute_teacher_id`
  * `sms_live_class_session.teacher_id`      INTEGER      -- user.id
  * `class_section.class_teacher_id`         INTEGER      -- user.id (has FK)

So a teacher's lesson plans and their timetable were, at the database level,
about two different people. "What is this teacher doing today" -- the question a
head of department asks every morning, and the one a substitute needs answered --
had no answer in SQL. `sms_timetable.py`'s own docstring already recorded the
split as a known obstacle ("they cannot simply be merged").

The integer `user.id` wins as the canonical identity for three reasons: five of
the eight columns already use it; `security/school_principal.py` already carries
it on every request in `raw_claims["lh_user_id"]` beside the string `sub`; and
only an integer column can ever carry a real foreign key to `user`.

WHY BOTH COLUMNS SURVIVE THIS MIGRATION
---------------------------------------
The new column is added and backfilled; the old string column is left in place
and still written. Dropping it here would make the backfill irreversible before
anyone has confirmed it against real data -- and this migration was authored
without access to the production database (the container was unreachable from
the authoring shell), so the backfill's real-world hit rate is unknown until it
runs. A later migration drops the string columns, once someone has read the
counts this one reports.

WHY NO FOREIGN KEY
------------------
`user` is NOT created by Alembic -- it is built by `SQLModel.metadata.create_all`
at application boot, and Alembic runs BEFORE that. A migration declaring
`ForeignKey("user.id")` would therefore fail against a fresh database. This is
an established trap here: `5e3a9c7f1b2d_secure_media_storage_and_share_tokens`
declares `created_by_user_id` as a plain `sa.Integer()` for exactly this reason,
and `sms_timetable_schedule.teacher_id` / `sms_live_class_session.teacher_id`
are soft links for the same reason. This migration follows that convention.
(`class_section.class_teacher_id` does carry an FK, but it is created by
`create_all`, where `user` already exists -- not by a migration.)

WHY UNMAPPABLE ROWS STAY NULL, LOUDLY
-------------------------------------
A string that matches no `user.user_uuid` cannot be resolved to a person. It is
left NULL and COUNTED, and the count is logged. It is never coerced to user 1
or to "some teacher" -- attributing a counselling session to the wrong clinician
is worse than admitting the attribution is unknown.

Revision ID: b7e2d41a9c38
Revises: 2f4c13b60f5b
Create Date: 2026-09-14

"""
import logging
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa  # noqa: F401
import sqlmodel  # noqa: F401


# revision identifiers, used by Alembic.
revision: str = "b7e2d41a9c38"
down_revision: Union[str, None] = "2f4c13b60f5b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger("alembic.runtime.migration")

# (table, existing string column, new integer column, index name)
_TARGETS = [
    ("sms_lesson_plan", "teacher_id", "teacher_user_id", "ix_sms_lesson_plan_teacher_user_id"),
    (
        "sms_counseling_activity_log",
        "psychologist_id",
        "psychologist_user_id",
        "ix_counseling_activity_psych_user_id",
    ),
    (
        "sms_counseling_session",
        "psychologist_id",
        "psychologist_user_id",
        "ix_counseling_session_psych_user_id",
    ),
]


def upgrade() -> None:
    bind = op.get_bind()
    # `user` is a reserved word in PostgreSQL; quoting also works in SQLite.
    user_tbl = '"user"'
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    for table, old_col, new_col, index_name in _TARGETS:
        # The sms_* tables are built by `SQLModel.metadata.create_all` at
        # application boot, NOT by Alembic -- and Alembic runs first. So on a
        # FRESH database these tables do not exist yet, and an unguarded
        # add_column would abort the whole migration run. `create_all` will then
        # build the table with `<new_col>` already present from the model, and
        # there is nothing here to backfill. Guard pattern borrowed from
        # `a1b2c3d4e5f7_add_manually_graded_to_task_submission`.
        if table not in existing_tables:
            logger.info(
                "unify_teacher_identity: %s does not exist yet (fresh database); "
                "create_all will build it with %s already present. Skipping.",
                table,
                new_col,
            )
            continue

        if new_col in {c["name"] for c in inspector.get_columns(table)}:
            logger.info(
                "unify_teacher_identity: %s.%s already present; skipping.", table, new_col
            )
            continue

        op.add_column(table, sa.Column(new_col, sa.Integer(), nullable=True))
        op.create_index(index_name, table, [new_col])

        # A correlated subquery rather than UPDATE..FROM: the latter is not
        # portable to SQLite, which the test suite and local development use.
        op.execute(
            sa.text(
                f"UPDATE {table} SET {new_col} = ("
                f"  SELECT u.id FROM {user_tbl} u WHERE u.user_uuid = {table}.{old_col}"
                f") WHERE {old_col} IS NOT NULL"
            )
        )

        # Report, rather than assume, what the backfill achieved. An operator
        # reading the migration log needs to know whether any row failed to
        # resolve BEFORE a later migration drops the string column.
        total = bind.execute(
            sa.text(f"SELECT count(*) FROM {table} WHERE {old_col} IS NOT NULL")
        ).scalar()
        mapped = bind.execute(
            sa.text(f"SELECT count(*) FROM {table} WHERE {new_col} IS NOT NULL")
        ).scalar()
        unmapped = (total or 0) - (mapped or 0)

        logger.info(
            "unify_teacher_identity: %s.%s -> %s | rows_with_string=%s mapped=%s UNMAPPED=%s",
            table,
            old_col,
            new_col,
            total,
            mapped,
            unmapped,
        )
        if unmapped:
            # Deliberately a warning, not a failure. Refusing to migrate would
            # leave the schema split in two forever over rows that may be dev
            # residue; but this must never pass silently, because every such row
            # is a lesson plan or a counselling record whose author is now
            # unknown and which a later drop would orphan permanently.
            logger.warning(
                "unify_teacher_identity: %s has %s row(s) whose %s matches no "
                "user.user_uuid. They are left NULL, NOT guessed. Resolve or "
                "accept these before any migration drops %s.",
                table,
                unmapped,
                old_col,
                old_col,
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    for table, _old_col, new_col, index_name in reversed(_TARGETS):
        # Same reasoning as upgrade(): the table may legitimately not exist.
        if table not in existing_tables:
            continue
        if new_col not in {c["name"] for c in inspector.get_columns(table)}:
            continue
        op.drop_index(index_name, table_name=table)
        op.drop_column(table, new_col)
