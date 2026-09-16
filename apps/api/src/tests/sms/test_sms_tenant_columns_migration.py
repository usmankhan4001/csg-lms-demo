"""Tenant columns on the five highest-risk unscoped SMS tables.

Covers migration ``c9d0e1f2a3b4`` (adds ``org_id``/``campus_id`` to
``sms_student_fee_voucher``, ``sms_student_attendance``,
``sms_gradebook_entry``, ``sms_clinical_case_notes`` and ``sms_salary_slip``,
then backfills them from the parent chain).

Two databases are exercised because the two deployment paths differ:

``legacy_db``
    The child tables are created by hand WITHOUT the new columns -- the state
    of every database that predates this migration. Proves ``add_column`` plus
    backfill, and that a broken parent chain leaves NULL rather than raising.

``fresh_db``
    The child tables come from ``SQLModel.metadata.create_all``, so the columns
    already exist -- the state of a brand-new database, since ``env.py`` runs
    ``create_all`` before migrations. Proves the backfill still runs on that
    path and that the columns are queryable through the ORM.

Both run on SQLite, which is what the suite uses. The backfill SQL is written
to be portable (correlated scalar subqueries, no ``UPDATE ... FROM``) for that
reason.
"""

import datetime
import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import JSON, create_engine, inspect, select, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel

from src.db.sms_attendance import StudentAttendance  # noqa: F401  (registers the table)
from src.db.sms_campus import (
    AcademicYear,
    Campus,
    ClassSection,
    StudentEnrollment,
)
from src.db.sms_counseling import EncryptedClinicalCaseNote
from src.db.sms_fees import StudentFeeVoucher
from src.db.sms_gradebook import AssessmentPlan, GradebookEntry
from src.db.sms_hr import StaffProfile
from src.db.sms_payroll import SalarySlip
# Registers sms_class_period, which sms_student_attendance.period_id points at.
# Without it create_all cannot sort the table subset by FK dependency.
from src.db.sms_timetable import ClassPeriod  # noqa: F401

_MIGRATION_PATH = (
    Path(__file__).resolve().parents[3]
    / "migrations"
    / "versions"
    / "c9d0e1f2a3b4_sms_tenant_columns.py"
)

# (table, [(index name, [columns]), ...]) -- mirrors the migration's _TABLES.
EXPECTED_INDEXES = {
    "sms_student_fee_voucher": [
        ("ix_sms_voucher_org_campus", ["org_id", "campus_id"]),
        ("ix_sms_voucher_org_status", ["org_id", "status"]),
    ],
    "sms_student_attendance": [
        ("ix_sms_att_org_campus", ["org_id", "campus_id"]),
        ("ix_sms_att_org_date", ["org_id", "date"]),
    ],
    "sms_gradebook_entry": [
        ("ix_sms_grade_org_campus", ["org_id", "campus_id"]),
        ("ix_sms_grade_org_student", ["org_id", "student_id"]),
    ],
    "sms_clinical_case_notes": [
        ("ix_clinical_notes_org_campus", ["org_id", "campus_id"]),
        ("ix_clinical_notes_org_student", ["org_id", "student_id"]),
    ],
    "sms_salary_slip": [
        ("ix_sms_slip_org_campus", ["org_id", "campus_id"]),
        ("ix_sms_slip_org_period", ["org_id", "month", "year"]),
    ],
}

# The five tables as they exist BEFORE the migration: no org_id, no campus_id.
# Only the columns the backfill and the assertions touch.
LEGACY_DDL = [
    """CREATE TABLE sms_student_fee_voucher (
        id INTEGER PRIMARY KEY, student_id INTEGER NOT NULL,
        voucher_no VARCHAR(50) NOT NULL, status VARCHAR(20) NOT NULL)""",
    """CREATE TABLE sms_student_attendance (
        id INTEGER PRIMARY KEY, student_id INTEGER NOT NULL,
        section_id INTEGER NOT NULL, date DATE NOT NULL)""",
    """CREATE TABLE sms_gradebook_entry (
        id INTEGER PRIMARY KEY, student_id INTEGER NOT NULL,
        assessment_plan_id INTEGER NOT NULL)""",
    """CREATE TABLE sms_clinical_case_notes (
        id INTEGER PRIMARY KEY, student_id INTEGER NOT NULL)""",
    """CREATE TABLE sms_salary_slip (
        id INTEGER PRIMARY KEY, staff_id INTEGER NOT NULL,
        month INTEGER NOT NULL, year INTEGER NOT NULL)""",
]

# Fixture ids. Two orgs, two campuses, so a wrong-tenant backfill is visible.
ORG_A, ORG_B = 1, 2
CAMPUS_A, CAMPUS_B = 10, 20
YEAR_A, YEAR_B = 100, 200
SECTION_A, SECTION_B = 1000, 2000
STUDENT_A, STUDENT_B = 500, 501
STUDENT_NO_ENROLMENT = 502
STUDENT_TWO_ORGS = 503
STAFF_A, STAFF_B = 700, 701
STAFF_NO_CAMPUS = 702
PLAN_WITH_SECTION, PLAN_COURSE_WIDE = 3000, 3001
MISSING_SECTION = 9999  # a section row that does not exist


def _load_migration():
    spec = importlib.util.spec_from_file_location(
        "mig_c9d0e1f2a3b4", _MIGRATION_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(migration, conn, direction="upgrade"):
    """Run the migration against `conn` with a real Alembic Operations proxy."""
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    ctx = MigrationContext.configure(conn)
    with Operations.context(ctx):
        getattr(migration, direction)()


def _remap_jsonb():
    """SQLite has no JSONB; the suite remaps it globally (see tests/conftest.py)."""
    for table in SQLModel.metadata.tables.values():
        for col in table.columns:
            if isinstance(col.type, JSONB):
                col.type = JSON()


def _new_engine():
    return create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


def _seed_parents(session: Session) -> None:
    """org 1 / campus 10 / section 1000 and org 2 / campus 20 / section 2000."""
    session.add_all(
        [
            Campus(id=CAMPUS_A, org_id=ORG_A, name="Main", code="MAIN"),
            Campus(id=CAMPUS_B, org_id=ORG_B, name="North", code="NORTH"),
            AcademicYear(id=YEAR_A, campus_id=CAMPUS_A, name="2025-2026"),
            AcademicYear(id=YEAR_B, campus_id=CAMPUS_B, name="2026-2027"),
            ClassSection(
                id=SECTION_A,
                campus_id=CAMPUS_A,
                academic_year_id=YEAR_A,
                grade_level="9",
                section_name="A",
            ),
            ClassSection(
                id=SECTION_B,
                campus_id=CAMPUS_B,
                academic_year_id=YEAR_B,
                grade_level="9",
                section_name="B",
            ),
            # 500 -> org 1, 501 -> org 2, 502 -> nowhere, 503 -> both.
            StudentEnrollment(
                id=1, student_id=STUDENT_A, section_id=SECTION_A, academic_year_id=YEAR_A
            ),
            StudentEnrollment(
                id=2, student_id=STUDENT_B, section_id=SECTION_B, academic_year_id=YEAR_B
            ),
            StudentEnrollment(
                id=3, student_id=STUDENT_TWO_ORGS, section_id=SECTION_A, academic_year_id=YEAR_A
            ),
            StudentEnrollment(
                id=4, student_id=STUDENT_TWO_ORGS, section_id=SECTION_B, academic_year_id=YEAR_B
            ),
            StaffProfile(
                id=STAFF_A, campus_id=CAMPUS_A, employee_code="E-A",
                full_name="A", designation="T", department="Math",
                joining_date=datetime.date(2020, 1, 1),
            ),
            StaffProfile(
                id=STAFF_B, campus_id=CAMPUS_B, employee_code="E-B",
                full_name="B", designation="T", department="Math",
                joining_date=datetime.date(2020, 1, 1),
            ),
            StaffProfile(
                id=STAFF_NO_CAMPUS, campus_id=None, employee_code="E-C",
                full_name="C", designation="T", department="Math",
                joining_date=datetime.date(2020, 1, 1),
            ),
            AssessmentPlan(
                id=PLAN_WITH_SECTION, course_id=1, section_id=SECTION_A,
                assessment_name="Mid", weight_percentage=30.0,
            ),
            AssessmentPlan(
                id=PLAN_COURSE_WIDE, course_id=1, section_id=None,
                assessment_name="Final", weight_percentage=70.0,
            ),
        ]
    )
    session.commit()


def _seed_children_raw(conn) -> None:
    """Insert pre-migration rows, including one deliberately orphaned each."""
    conn.execute(
        text(
            "INSERT INTO sms_student_fee_voucher (id, student_id, voucher_no, status) "
            "VALUES (1, :a, 'V-A', 'UNPAID'), (2, :b, 'V-B', 'UNPAID'), "
            "(3, :none, 'V-ORPHAN', 'UNPAID'), (4, :two, 'V-TWO', 'UNPAID')"
        ),
        {"a": STUDENT_A, "b": STUDENT_B, "none": STUDENT_NO_ENROLMENT, "two": STUDENT_TWO_ORGS},
    )
    conn.execute(
        text(
            "INSERT INTO sms_student_attendance (id, student_id, section_id, date) "
            "VALUES (1, :a, :sa, '2026-01-05'), (2, :b, :sb, '2026-01-05'), "
            "(3, :none, :missing, '2026-01-05')"
        ),
        {
            "a": STUDENT_A, "b": STUDENT_B, "none": STUDENT_NO_ENROLMENT,
            "sa": SECTION_A, "sb": SECTION_B, "missing": MISSING_SECTION,
        },
    )
    conn.execute(
        text(
            "INSERT INTO sms_gradebook_entry (id, student_id, assessment_plan_id) "
            "VALUES (1, :a, :with_sec), (2, :b, :course_wide), (3, :none, :course_wide)"
        ),
        {
            "a": STUDENT_A, "b": STUDENT_B, "none": STUDENT_NO_ENROLMENT,
            "with_sec": PLAN_WITH_SECTION, "course_wide": PLAN_COURSE_WIDE,
        },
    )
    conn.execute(
        text(
            "INSERT INTO sms_clinical_case_notes (id, student_id) "
            "VALUES (1, :a), (2, :b), (3, :none)"
        ),
        {"a": STUDENT_A, "b": STUDENT_B, "none": STUDENT_NO_ENROLMENT},
    )
    conn.execute(
        text(
            "INSERT INTO sms_salary_slip (id, staff_id, month, year) "
            "VALUES (1, :a, 1, 2026), (2, :b, 1, 2026), (3, :no_campus, 1, 2026)"
        ),
        {"a": STAFF_A, "b": STAFF_B, "no_campus": STAFF_NO_CAMPUS},
    )
    conn.commit()


@pytest.fixture()
def legacy_db():
    """A pre-migration database: child tables exist without the tenant columns."""
    _remap_jsonb()
    engine = _new_engine()
    parents = [
        SQLModel.metadata.tables[name]
        for name in (
            "campus", "academic_year", "class_section", "student_enrollment",
            "sms_staff_profile", "sms_assessment_plan",
        )
    ]
    SQLModel.metadata.create_all(engine, tables=parents)
    with engine.connect() as conn:
        _seed_parents(Session(conn))
        for ddl in LEGACY_DDL:
            conn.execute(text(ddl))
        _seed_children_raw(conn)
    yield engine
    engine.dispose()


@pytest.fixture()
def fresh_db():
    """A brand-new database: create_all has already delivered the columns."""
    _remap_jsonb()
    engine = _new_engine()
    tables = [
        SQLModel.metadata.tables[name]
        for name in (
            "campus", "academic_year", "class_section", "student_enrollment",
            "sms_staff_profile", "sms_assessment_plan",
            "sms_student_fee_voucher", "sms_student_attendance",
            "sms_gradebook_entry", "sms_clinical_case_notes", "sms_salary_slip",
        )
    ]
    SQLModel.metadata.create_all(engine, tables=tables)
    with engine.connect() as conn:
        _seed_parents(Session(conn))
    yield engine
    engine.dispose()


def _rows(engine, table, columns="id, org_id, campus_id"):
    with engine.connect() as conn:
        return {
            row[0]: (row[1], row[2])
            for row in conn.execute(text(f"SELECT {columns} FROM {table} ORDER BY id"))
        }


# --------------------------------------------------------------------------
# legacy database: columns added, then backfilled
# --------------------------------------------------------------------------

def test_migration_adds_columns_to_legacy_tables(legacy_db):
    migration = _load_migration()
    with legacy_db.connect() as conn:
        _run(migration, conn)
        conn.commit()

    for table in EXPECTED_INDEXES:
        cols = {c["name"] for c in inspect(legacy_db).get_columns(table)}
        assert {"org_id", "campus_id"} <= cols, table


def test_backfill_resolves_org_and_campus_from_parent_chain(legacy_db):
    migration = _load_migration()
    with legacy_db.connect() as conn:
        _run(migration, conn)
        conn.commit()

    # voucher -> student -> enrolment -> section -> campus -> org
    assert _rows(legacy_db, "sms_student_fee_voucher") == {
        1: (ORG_A, CAMPUS_A),
        2: (ORG_B, CAMPUS_B),
        3: (None, None),  # student never enrolled
        4: (ORG_B, CAMPUS_B),  # two enrolments: most recent year wins
    }

    # attendance -> its own section -> campus -> org
    assert _rows(legacy_db, "sms_student_attendance") == {
        1: (ORG_A, CAMPUS_A),
        2: (ORG_B, CAMPUS_B),
        3: (None, None),  # section row missing and student never enrolled
    }

    # gradebook -> assessment plan's section, else the student's enrolment
    assert _rows(legacy_db, "sms_gradebook_entry") == {
        1: (ORG_A, CAMPUS_A),  # plan has a section
        2: (ORG_B, CAMPUS_B),  # course-wide plan: falls back to the student
        3: (None, None),  # course-wide plan and no enrolment
    }

    # clinical notes -> student -> enrolment -> section -> campus -> org
    assert _rows(legacy_db, "sms_clinical_case_notes") == {
        1: (ORG_A, CAMPUS_A),
        2: (ORG_B, CAMPUS_B),
        3: (None, None),
    }

    # salary slip -> staff profile -> campus -> org
    assert _rows(legacy_db, "sms_salary_slip") == {
        1: (ORG_A, CAMPUS_A),
        2: (ORG_B, CAMPUS_B),
        3: (None, None),  # staff member has no campus
    }


def test_orphans_are_left_null_not_guessed(legacy_db):
    """A broken parent chain must never attribute a row to the wrong tenant."""
    migration = _load_migration()
    with legacy_db.connect() as conn:
        _run(migration, conn)
        conn.commit()

        for table in EXPECTED_INDEXES:
            unscoped = conn.execute(
                text(f"SELECT COUNT(*) FROM {table} WHERE org_id IS NULL")
            ).scalar()
            assert unscoped == 1, f"{table} should have exactly one orphan"

            # org_id is only ever derived from campus_id, so the two agree.
            mismatched = conn.execute(
                text(
                    f"SELECT COUNT(*) FROM {table} "
                    f"WHERE (org_id IS NULL) <> (campus_id IS NULL)"
                )
            ).scalar()
            assert mismatched == 0, table

            # No row may be attributed to an org it does not belong to.
            wrong = conn.execute(
                text(
                    f"SELECT COUNT(*) FROM {table} t "
                    f"JOIN campus c ON c.id = t.campus_id "
                    f"WHERE c.org_id <> t.org_id"
                )
            ).scalar()
            assert wrong == 0, table


def test_backfill_is_idempotent(legacy_db):
    migration = _load_migration()
    with legacy_db.connect() as conn:
        _run(migration, conn)
        conn.commit()
        first = {t: _rows(legacy_db, t) for t in EXPECTED_INDEXES}

        _run(migration, conn)
        conn.commit()

    for table, before in first.items():
        assert _rows(legacy_db, table) == before, table


def test_backfill_does_not_overwrite_a_corrected_value(legacy_db):
    """The WHERE ... IS NULL guard means a hand-corrected row survives a re-run."""
    migration = _load_migration()
    with legacy_db.connect() as conn:
        _run(migration, conn)
        conn.commit()

        conn.execute(
            text(
                "UPDATE sms_student_fee_voucher SET org_id = 99, campus_id = 98 "
                "WHERE id = 3"
            )
        )
        conn.commit()

        _run(migration, conn)
        conn.commit()

        assert _rows(legacy_db, "sms_student_fee_voucher")[3] == (99, 98)


def test_indexes_are_created(legacy_db):
    migration = _load_migration()
    with legacy_db.connect() as conn:
        _run(migration, conn)
        conn.commit()

    for table, expected in EXPECTED_INDEXES.items():
        found = {idx["name"]: idx["column_names"] for idx in inspect(legacy_db).get_indexes(table)}
        for name, columns in expected:
            assert name in found, f"{table}.{name} missing"
            assert found[name] == columns, f"{table}.{name} on {found[name]}"


def test_missing_parent_tables_skip_backfill_instead_of_failing():
    """A database with the child table but no parents must not abort."""
    _remap_jsonb()
    engine = _new_engine()
    with engine.connect() as conn:
        for ddl in LEGACY_DDL:
            conn.execute(text(ddl))
        conn.execute(
            text("INSERT INTO sms_salary_slip (id, staff_id, month, year) VALUES (1, 1, 1, 2026)")
        )
        conn.commit()

        _run(_load_migration(), conn)
        conn.commit()

    cols = {c["name"] for c in inspect(engine).get_columns("sms_salary_slip")}
    assert {"org_id", "campus_id"} <= cols
    assert _rows(engine, "sms_salary_slip") == {1: (None, None)}
    engine.dispose()


def test_downgrade_removes_columns_and_indexes(legacy_db):
    migration = _load_migration()
    with legacy_db.connect() as conn:
        _run(migration, conn)
        conn.commit()
        _run(migration, conn, direction="downgrade")
        conn.commit()

    for table in EXPECTED_INDEXES:
        cols = {c["name"] for c in inspect(legacy_db).get_columns(table)}
        assert "org_id" not in cols and "campus_id" not in cols, table
        names = {idx["name"] for idx in inspect(legacy_db).get_indexes(table)}
        for name, _ in EXPECTED_INDEXES[table]:
            assert name not in names


# --------------------------------------------------------------------------
# fresh database: create_all path, and ORM queryability
# --------------------------------------------------------------------------

def test_fresh_database_is_backfilled_and_queryable(fresh_db):
    """The create_all path (env.py runs it first) still gets real values."""
    migration = _load_migration()
    with fresh_db.connect() as conn:
        session = Session(conn)
        session.add_all(
            [
                # `sa_column=` suppresses the SQLModel field default, so the
                # NOT NULL numeric columns are passed explicitly.
                StudentFeeVoucher(
                    id=1, student_id=STUDENT_A, voucher_no="V-A",
                    issue_date=datetime.date(2026, 1, 1),
                    due_date=datetime.date(2026, 2, 1),
                    tuition_fee=0.0, transport_fee=0.0, lab_fee=0.0,
                    other_fee=0.0, discount=0.0, fine=0.0,
                    total_amount=0.0, paid_amount=0.0, balance_amount=0.0,
                ),
                StudentFeeVoucher(
                    id=2, student_id=STUDENT_B, voucher_no="V-B",
                    issue_date=datetime.date(2026, 1, 1),
                    due_date=datetime.date(2026, 2, 1),
                    tuition_fee=0.0, transport_fee=0.0, lab_fee=0.0,
                    other_fee=0.0, discount=0.0, fine=0.0,
                    total_amount=0.0, paid_amount=0.0, balance_amount=0.0,
                ),
                GradebookEntry(
                    id=1, student_id=STUDENT_A, assessment_plan_id=PLAN_WITH_SECTION,
                    raw_score=10.0, max_score=100.0,
                ),
                GradebookEntry(
                    id=2, student_id=STUDENT_B, assessment_plan_id=PLAN_COURSE_WIDE,
                    raw_score=20.0, max_score=100.0,
                ),
                EncryptedClinicalCaseNote(
                    id=1, student_id=STUDENT_A, psychologist_id="psy-1",
                    envelope_ciphertext="c", envelope_iv="i", envelope_tag="t",
                ),
                EncryptedClinicalCaseNote(
                    id=2, student_id=STUDENT_B, psychologist_id="psy-2",
                    envelope_ciphertext="c", envelope_iv="i", envelope_tag="t",
                ),
                SalarySlip(id=1, staff_id=STAFF_A, slip_no="S-A", month=1, year=2026),
                SalarySlip(id=2, staff_id=STAFF_B, slip_no="S-B", month=1, year=2026),
            ]
        )
        session.commit()

        _run(migration, conn)
        conn.commit()

        # The columns are queryable through the ORM, which is the point of
        # putting them on the model at all.
        org_a_vouchers = session.execute(
            select(StudentFeeVoucher.id).where(StudentFeeVoucher.org_id == ORG_A)
        ).scalars().all()
        assert org_a_vouchers == [1]

        org_b_grades = session.execute(
            select(GradebookEntry.id).where(GradebookEntry.org_id == ORG_B)
        ).scalars().all()
        assert org_b_grades == [2]  # course-wide plan, resolved via enrolment

        org_a_notes = session.execute(
            select(EncryptedClinicalCaseNote.id).where(
                EncryptedClinicalCaseNote.org_id == ORG_A
            )
        ).scalars().all()
        assert org_a_notes == [1]

        org_b_slips = session.execute(
            select(SalarySlip.id).where(SalarySlip.org_id == ORG_B)
        ).scalars().all()
        assert org_b_slips == [2]

        # And the composite index serves a tenant + campus lookup.
        both = session.execute(
            select(StudentFeeVoucher.id).where(
                StudentFeeVoucher.org_id == ORG_A,
                StudentFeeVoucher.campus_id == CAMPUS_A,
            )
        ).scalars().all()
        assert both == [1]


# --------------------------------------------------------------------------
# model / migration agreement
# --------------------------------------------------------------------------

def test_models_declare_the_columns_and_indexes():
    """The model must match the migration, or create_all and Alembic diverge."""
    for table, expected in EXPECTED_INDEXES.items():
        model_table = SQLModel.metadata.tables[table]
        assert "org_id" in model_table.c and "campus_id" in model_table.c, table
        assert model_table.c["org_id"].nullable, f"{table}.org_id must stay nullable"
        assert model_table.c["campus_id"].nullable, f"{table}.campus_id must stay nullable"

        names = {idx.name for idx in model_table.indexes}
        for name, _columns in expected:
            assert name in names, f"{table}.{name} missing from the model"


def test_create_all_does_not_emit_duplicate_indexes():
    """The known trap: Index(...) in __table_args__ plus index=True on the same
    column makes create_all emit CREATE INDEX twice and the API fails to boot.
    """
    _remap_jsonb()
    engine = _new_engine()
    tables = [SQLModel.metadata.tables[name] for name in EXPECTED_INDEXES]
    SQLModel.metadata.create_all(engine, tables=tables)  # must not raise
    for table in EXPECTED_INDEXES:
        names = [idx["name"] for idx in inspect(engine).get_indexes(table)]
        assert len(names) == len(set(names)), f"{table}: {names}"
    engine.dispose()
