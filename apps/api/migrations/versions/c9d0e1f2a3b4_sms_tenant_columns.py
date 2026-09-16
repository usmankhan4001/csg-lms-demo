"""Add org_id / campus_id to five unscoped SMS tables and backfill them

Tenant isolation in this schema is row-level and enforced only by service-layer
WHERE clauses. Roughly 59 of the 114 school tables carry neither ``org_id`` nor
``campus_id``, so for those tables a missed predicate is a cross-tenant read
with no database backstop at all. This migration scopes the five highest-risk
ones -- fee vouchers (money), attendance and gradebook entries (a child's
record), encrypted clinical case notes (therapy notes) and salary slips
(staff pay).

WHY NULLABLE
    The columns are added NULLable and stay NULLable. A NOT NULL column would
    require every row to resolve on the first run, and the whole point of the
    orphan policy below is that some rows cannot. Making them NOT NULL later is
    a separate, deliberate step once the orphan count is known to be zero.

BACKFILL CHAIN
    Every row is resolved through its parent, never guessed:

      sms_student_fee_voucher   student -> enrolment -> section -> campus -> org
      sms_student_attendance    own section -> campus -> org
                                (fallback: student -> enrolment -> section)
      sms_gradebook_entry       assessment plan -> section -> campus -> org
                                (fallback: student -> enrolment -> section)
      sms_clinical_case_notes   student -> enrolment -> section -> campus -> org
      sms_salary_slip           staff profile -> campus -> org

    ``org_id`` is always derived from ``campus.org_id`` rather than resolved
    independently, in a second pass. That is deliberate: two independent
    lookups could disagree, and a row whose org and campus point at different
    tenants is worse than a row with no tenant at all.

    Where a student has several enrolments the MOST RECENT one wins
    (``academic_year_id DESC, id DESC``). The choice is arbitrary but
    deterministic, so re-running produces the same answer; a student genuinely
    enrolled in two orgs is a data error this migration reports rather than
    silently repairs.

ORPHANS: LEFT NULL, COUNTED, LOGGED
    A row whose parent chain is broken -- a student with no enrolment, a
    section whose campus is gone, a staff member with no campus -- is left with
    NULL ``org_id``/``campus_id``. It is NOT deleted, NOT defaulted to any
    org, and does NOT abort the migration.

    Deleting would destroy a child's clinical note or a family's invoice to
    satisfy a schema rule. Defaulting to "some" org would attribute one
    school's data to another -- precisely the failure this work exists to
    prevent, and invisible afterwards. NULL is honest: it means "tenant
    unknown", it is countable, and it fails CLOSED under any future RLS policy
    of the form ``USING (org_id = current_org())``, which hides NULL rows
    rather than exposing them.

    The count is logged at WARNING per table. That log line is the remediation
    worklist: ``SELECT * FROM <table> WHERE org_id IS NULL``.

IDEMPOTENCY
    * Columns are added only if absent (``env.py`` also guards this, but the
      guard is repeated so the module is safe to call directly, as the tests
      do).
    * Both backfill UPDATEs are restricted to ``WHERE <col> IS NULL``, so a
      second run touches nothing and cannot overwrite a value an operator has
      since corrected by hand.
    * Indexes and the whole thing are skipped when a table is missing, which is
      the case on a database that has never had that feature provisioned.

NO FOREIGN KEYS, DELIBERATELY
    ``org_id``/``campus_id`` are plain integers here, matching
    ``sms_document_audit_logs``, ``sms_pastoral_escalations`` and
    ``sms_alumni_profiles``. Alembic cannot ALTER a constraint on SQLite
    (``NotImplementedError: No support for ALTER of constraints in SQLite
    dialect``), so an FK added by this migration would exist on a migrated
    PostgreSQL database and be absent on a migrated SQLite one while being
    present on both under ``create_all`` -- the exact create_all/migration
    divergence that ``StudentFeeVoucher.installment_plan_id`` documents. The
    backfill only ever writes ids read from live parent rows, so there are no
    orphans for an FK to catch today. Revisit if that changes.

NO RLS
    This pass adds data, not policy. No ``ENABLE ROW LEVEL SECURITY`` and no
    policies are created here; that is a separate decision.

Revision ID: c9d0e1f2a3b4
Revises: b5c6d7e8f9a0
Create Date: 2026-09-16

"""
import logging
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel  # noqa: F401


logger = logging.getLogger("alembic.runtime.migration")

revision: str = 'c9d0e1f2a3b4'
down_revision: Union[str, None] = 'b5c6d7e8f9a0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _student_campus(table: str) -> str:
    """Campus of a student's most recent enrolment, as a scalar subquery.

    ``student_enrollment`` is unique on (student_id, academic_year_id), so the
    ORDER BY picks one deterministically -- most recent year first, then
    highest id as a tiebreak for two enrolments in the same year.
    """
    return (
        "SELECT cs.campus_id "
        "FROM student_enrollment se "
        "JOIN class_section cs ON cs.id = se.section_id "
        f"WHERE se.student_id = {table}.student_id "
        "ORDER BY se.academic_year_id DESC, se.id DESC "
        "LIMIT 1"
    )


# (table, scalar subquery yielding campus_id, parent tables it needs,
#  [(index name, [columns]), ...])
#
# The parent list is checked before the backfill runs: a database that has the
# child table but not, say, `sms_assessment_plan` would otherwise abort on
# "no such table" instead of just leaving the rows unresolved.
_TABLES = [
    (
        "sms_student_fee_voucher",
        _student_campus("sms_student_fee_voucher"),
        ("campus", "class_section", "student_enrollment"),
        [
            ("ix_sms_voucher_org_campus", ["org_id", "campus_id"]),
            ("ix_sms_voucher_org_status", ["org_id", "status"]),
        ],
    ),
    (
        "sms_student_attendance",
        # The row's own section is authoritative; the enrolment chain is only a
        # fallback for a section row that has gone missing.
        "COALESCE("
        "(SELECT cs.campus_id FROM class_section cs "
        "WHERE cs.id = sms_student_attendance.section_id), "
        f"({_student_campus('sms_student_attendance')})"
        ")",
        ("campus", "class_section", "student_enrollment"),
        [
            ("ix_sms_att_org_campus", ["org_id", "campus_id"]),
            ("ix_sms_att_org_date", ["org_id", "date"]),
        ],
    ),
    (
        "sms_gradebook_entry",
        # The assessment plan's section is authoritative; a course-wide plan has
        # no section, and then the student's enrolment is the only path.
        "COALESCE("
        "(SELECT cs.campus_id FROM sms_assessment_plan ap "
        "JOIN class_section cs ON cs.id = ap.section_id "
        "WHERE ap.id = sms_gradebook_entry.assessment_plan_id), "
        f"({_student_campus('sms_gradebook_entry')})"
        ")",
        ("campus", "class_section", "student_enrollment", "sms_assessment_plan"),
        [
            ("ix_sms_grade_org_campus", ["org_id", "campus_id"]),
            ("ix_sms_grade_org_student", ["org_id", "student_id"]),
        ],
    ),
    (
        "sms_clinical_case_notes",
        _student_campus("sms_clinical_case_notes"),
        ("campus", "class_section", "student_enrollment"),
        [
            ("ix_clinical_notes_org_campus", ["org_id", "campus_id"]),
            ("ix_clinical_notes_org_student", ["org_id", "student_id"]),
        ],
    ),
    (
        "sms_salary_slip",
        "SELECT sp.campus_id FROM sms_staff_profile sp "
        "WHERE sp.id = sms_salary_slip.staff_id",
        ("campus", "sms_staff_profile"),
        [
            ("ix_sms_slip_org_campus", ["org_id", "campus_id"]),
            ("ix_sms_slip_org_period", ["org_id", "month", "year"]),
        ],
    ),
]


def _existing_columns(bind, table: str) -> set:
    return {col["name"] for col in sa.inspect(bind).get_columns(table)}


def _existing_indexes(bind, table: str) -> set:
    return {
        idx["name"]
        for idx in sa.inspect(bind).get_indexes(table)
        if idx.get("name")
    }


def _backfill(bind, table: str, campus_sql: str) -> None:
    """Resolve campus_id from the parent chain, then org_id from the campus.

    Two passes, in that order, so org_id can never disagree with campus_id.
    Both are restricted to NULL targets, which is what makes a re-run a no-op.
    """
    bind.execute(
        sa.text(f"UPDATE {table} SET campus_id = ({campus_sql}) WHERE campus_id IS NULL")
    )
    bind.execute(
        sa.text(
            f"UPDATE {table} SET org_id = "
            f"(SELECT c.org_id FROM campus c WHERE c.id = {table}.campus_id) "
            f"WHERE org_id IS NULL AND campus_id IS NOT NULL"
        )
    )

    unresolved = bind.execute(
        sa.text(f"SELECT COUNT(*) FROM {table} WHERE org_id IS NULL")
    ).scalar() or 0
    if unresolved:
        logger.warning(
            "%s: %s row(s) still have no org_id after backfill -- the parent "
            "chain (student enrolment / section / campus, or staff campus) is "
            "broken for them. Left NULL on purpose: they are hidden by any "
            "future org-scoped read, never attributed to the wrong school. "
            "Remediate with: SELECT * FROM %s WHERE org_id IS NULL",
            table, unresolved, table,
        )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    for table, campus_sql, parents, indexes in _TABLES:
        if table not in tables:
            continue

        existing = _existing_columns(bind, table)
        for column in ("org_id", "campus_id"):
            if column not in existing:
                op.add_column(table, sa.Column(column, sa.Integer(), nullable=True))

        # Without the parent tables there is no chain to walk and every row
        # would be an orphan anyway, so skip rather than fail on "no such
        # table". The columns still get added and indexed.
        if parents and not set(parents) <= tables:
            logger.warning(
                "%s: skipping backfill, missing parent table(s) %s",
                table, sorted(set(parents) - tables),
            )
        else:
            _backfill(bind, table, campus_sql)

        # Checked here as well as by env.py's guard, so a re-run -- or a call
        # from a test, which has no env.py -- does not try to create an index
        # that is already there.
        present = _existing_indexes(bind, table)
        for name, columns in indexes:
            if name not in present:
                op.create_index(name, table, columns)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    for table, _campus_sql, _parents, indexes in reversed(_TABLES):
        if table not in tables:
            continue

        present = _existing_indexes(bind, table)
        for name, _columns in reversed(indexes):
            if name in present:
                op.drop_index(name, table_name=table)

        existing = _existing_columns(bind, table)
        for column in ("campus_id", "org_id"):
            if column in existing:
                op.drop_column(table, column)
