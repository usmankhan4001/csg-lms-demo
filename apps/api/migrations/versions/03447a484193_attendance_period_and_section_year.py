"""add attendance.period_id and class_section.academic_year_id

Two data-model corrections that `create_all` cannot deliver. It creates missing
TABLES but never ALTERs an existing one, so both columns would silently fail to
appear in every environment that already has these tables -- including the
running dev database, where the code and schema currently disagree.

WHY period_id (sms_student_attendance):
  The unique key was (student_id, section_id, date) and the roll-call handler
  upserts on it. In a school running 6-8 periods a day that means taking period
  5's register SILENTLY OVERWRITES period 1's -- a student absent first thing
  and present after lunch ends the day looking present. The system already
  modelled periods (ClassPeriod, TimetableSchedule); attendance was simply never
  wired to them.

  Nullable is deliberate: a primary school takes one register a day and has no
  periods, so `period_id IS NULL` remains a first-class whole-day register and
  every existing row keeps its meaning.

  RESTRICT rather than CASCADE, differing from TimetableSchedule.period_id: a
  timetable slot is a PLAN and may die with its period, but an attendance row is
  a RECORD OF WHAT HAPPENED and must outlive the bell schedule. CASCADE would
  destroy a legal record; SET NULL would be worse, silently reclassifying period
  rows as day rows and leaving several indistinguishable "day" rows for one date.

WHY academic_year_id (class_section):
  ClassSection had campus_id but no year, so "Grade 9 A" was the same row
  forever. That structurally blocked academic year rollover -- there was no way
  to promote a cohort, say who taught 9A last year, or archive a year. Every
  August a school would have hand-rebuilt every enrolment.

  Nullable because NULL means "not year-scoped yet", not "corrupt": section
  listing treats NULL as included, so upgrading does not make an existing
  school's sections vanish from its own screens. campus_id is deliberately
  retained even though AcademicYear carries one -- campus must stay resolvable
  for exactly those NULL rows.

Both tables were verified to hold ZERO attendance rows and a single section at
the time of writing, so this is additive and non-destructive.

Revision ID: 03447a484193
Revises: f0627c0d1171
Create Date: 2026-09-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa  # noqa: F401
import sqlmodel  # noqa: F401


# revision identifiers, used by Alembic.
revision: str = '03447a484193'
down_revision: Union[str, None] = 'f0627c0d1171'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---- attendance gains a period dimension -------------------------------
    op.add_column(
        "sms_student_attendance",
        sa.Column("period_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_sms_attendance_period",
        "sms_student_attendance",
        "sms_class_period",
        ["period_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_sms_student_attendance_period_id",
        "sms_student_attendance",
        ["period_id"],
    )
    # Widen the unique key so a period register no longer collides with the
    # day's other periods. NOTE: because period_id is nullable and NULL != NULL
    # in SQL, this constraint cannot prevent duplicate DAY-LEVEL rows -- that
    # case is enforced read-before-write in the roll-call handler, the same
    # approach sms_school_settings uses for its nullable campus_id.
    op.drop_constraint(
        "uq_sms_student_section_date",
        "sms_student_attendance",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_sms_student_section_date_period",
        "sms_student_attendance",
        ["student_id", "section_id", "date", "period_id"],
    )

    # ---- sections become year-scoped ---------------------------------------
    op.add_column(
        "class_section",
        sa.Column("academic_year_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_class_section_academic_year",
        "class_section",
        "academic_year",
        ["academic_year_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_class_section_academic_year_id",
        "class_section",
        ["academic_year_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_class_section_academic_year_id", table_name="class_section")
    op.drop_constraint("fk_class_section_academic_year", "class_section", type_="foreignkey")
    op.drop_column("class_section", "academic_year_id")

    op.drop_constraint(
        "uq_sms_student_section_date_period",
        "sms_student_attendance",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_sms_student_section_date",
        "sms_student_attendance",
        ["student_id", "section_id", "date"],
    )
    op.drop_index("ix_sms_student_attendance_period_id", table_name="sms_student_attendance")
    op.drop_constraint("fk_sms_attendance_period", "sms_student_attendance", type_="foreignkey")
    op.drop_column("sms_student_attendance", "period_id")
