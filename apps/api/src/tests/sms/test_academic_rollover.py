"""Academic year rollover, and the campus holes in the tenancy root.

Rollover is THE annual operation a school must perform and it did not exist:
`ClassSection` had no `academic_year_id`, so "Grade 9 A" was one permanent row
and every August a school would have hand-rebuilt every enrolment.

The rules these pin, in order of how much damage getting them wrong would do:
  - last year is never mutated (rollover only ever INSERTs)
  - a dry run writes nothing
  - re-running promotes nobody twice
  - a grade the school did not map is left alone, never guessed
"""

import pytest
from fastapi import HTTPException
from sqlmodel import select

from src.db.sms_campus import AcademicYear, Campus, ClassSection, StudentEnrollment
from src.routers.sms_campus import create_class_section, enroll_student
from src.db.sms_campus import ClassSectionBase, StudentEnrollmentCreate
from src.services.sms.academic_rollover import plan_rollover
from src.tests.sms._principals import principal


async def _campus(db, org_id=1, name="Main", code="MAIN"):
    c = Campus(org_id=org_id, name=name, code=code, timezone="Asia/Karachi")
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return c


async def _year(db, campus_id, name, is_active=True):
    y = AcademicYear(campus_id=campus_id, name=name, is_active=is_active)
    db.add(y)
    await db.commit()
    await db.refresh(y)
    return y


async def _section(db, campus_id, year_id, grade, name="A"):
    s = ClassSection(
        campus_id=campus_id,
        academic_year_id=year_id,
        grade_level=grade,
        section_name=name,
    )
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return s


async def _enrol(db, student_id, section_id, year_id, status="active"):
    e = StudentEnrollment(
        student_id=student_id,
        section_id=section_id,
        academic_year_id=year_id,
        status=status,
    )
    db.add(e)
    await db.commit()
    await db.refresh(e)
    return e


# ---------------------------------------------------------------------------
# Rollover
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dry_run_writes_nothing(db):
    campus = await _campus(db)
    y1 = await _year(db, campus.id, "2025-2026")
    y2 = await _year(db, campus.id, "2026-2027", is_active=False)
    s1 = await _section(db, campus.id, y1.id, "Grade 9")
    await _enrol(db, 501, s1.id, y1.id)

    plan = await plan_rollover(
        db,
        source_year_id=y1.id,
        target_year_id=y2.id,
        grade_progression={"Grade 9": "Grade 10"},
        dry_run=True,
    )

    assert plan.summary()["sections_to_create"] == 1
    assert plan.summary()["students_to_promote"] == 1

    # Nothing was actually written.
    sections = (await db.execute(
        select(ClassSection).where(ClassSection.academic_year_id == y2.id)
    )).scalars().all()
    enrols = (await db.execute(
        select(StudentEnrollment).where(StudentEnrollment.academic_year_id == y2.id)
    )).scalars().all()
    assert len(sections) == 0, "dry run created a section"
    assert len(enrols) == 0, "dry run created an enrolment"


@pytest.mark.asyncio
async def test_rollover_promotes_and_is_idempotent(db):
    campus = await _campus(db)
    y1 = await _year(db, campus.id, "2025-2026")
    y2 = await _year(db, campus.id, "2026-2027", is_active=False)
    s1 = await _section(db, campus.id, y1.id, "Grade 9")
    await _enrol(db, 601, s1.id, y1.id)

    progression = {"Grade 9": "Grade 10"}
    await plan_rollover(
        db, source_year_id=y1.id, target_year_id=y2.id,
        grade_progression=progression, dry_run=False,
    )

    enrols = (await db.execute(
        select(StudentEnrollment).where(StudentEnrollment.academic_year_id == y2.id)
    )).scalars().all()
    assert len(enrols) == 1

    # Run it AGAIN -- a school will, after fixing something.
    second = await plan_rollover(
        db, source_year_id=y1.id, target_year_id=y2.id,
        grade_progression=progression, dry_run=False,
    )
    enrols_after = (await db.execute(
        select(StudentEnrollment).where(StudentEnrollment.academic_year_id == y2.id)
    )).scalars().all()
    assert len(enrols_after) == 1, "second run double-enrolled the student"
    assert second.summary()["students_already_enrolled"] == 1
    assert second.summary()["sections_already_present"] == 1


@pytest.mark.asyncio
async def test_last_year_is_never_mutated(db):
    """The entire point of rollover is that history stays readable."""
    campus = await _campus(db)
    y1 = await _year(db, campus.id, "2025-2026")
    y2 = await _year(db, campus.id, "2026-2027", is_active=False)
    s1 = await _section(db, campus.id, y1.id, "Grade 9")
    original = await _enrol(db, 701, s1.id, y1.id)
    original_section_id = original.section_id
    original_status = original.status

    await plan_rollover(
        db, source_year_id=y1.id, target_year_id=y2.id,
        grade_progression={"Grade 9": "Grade 10"}, dry_run=False,
    )

    await db.refresh(original)
    assert original.section_id == original_section_id
    assert original.status == original_status
    assert original.academic_year_id == y1.id


@pytest.mark.asyncio
async def test_an_unmapped_grade_is_refused_not_guessed(db):
    """Guessing that one grade follows another would eventually mis-promote a
    child. An unmapped grade must be reported, never inferred."""
    campus = await _campus(db)
    y1 = await _year(db, campus.id, "2025-2026")
    y2 = await _year(db, campus.id, "2026-2027", is_active=False)
    s1 = await _section(db, campus.id, y1.id, "KG-1")
    await _enrol(db, 801, s1.id, y1.id)

    plan = await plan_rollover(
        db, source_year_id=y1.id, target_year_id=y2.id,
        grade_progression={"Grade 9": "Grade 10"},  # KG-1 absent
        dry_run=False,
    )

    assert plan.summary()["students_unmapped"] == 1
    assert plan.summary()["students_to_promote"] == 0
    enrols = (await db.execute(
        select(StudentEnrollment).where(StudentEnrollment.academic_year_id == y2.id)
    )).scalars().all()
    assert len(enrols) == 0


@pytest.mark.asyncio
async def test_final_year_cohort_graduates_rather_than_promoting(db):
    campus = await _campus(db)
    y1 = await _year(db, campus.id, "2025-2026")
    y2 = await _year(db, campus.id, "2026-2027", is_active=False)
    s1 = await _section(db, campus.id, y1.id, "Grade 12")
    await _enrol(db, 901, s1.id, y1.id)

    plan = await plan_rollover(
        db, source_year_id=y1.id, target_year_id=y2.id,
        grade_progression={"Grade 12": None},  # explicit: this cohort leaves
        dry_run=False,
    )

    assert plan.summary()["students_graduating"] == 1
    enrols = (await db.execute(
        select(StudentEnrollment).where(StudentEnrollment.academic_year_id == y2.id)
    )).scalars().all()
    assert len(enrols) == 0


@pytest.mark.asyncio
async def test_a_held_back_student_repeats_the_same_grade(db):
    campus = await _campus(db)
    y1 = await _year(db, campus.id, "2025-2026")
    y2 = await _year(db, campus.id, "2026-2027", is_active=False)
    s9 = await _section(db, campus.id, y1.id, "Grade 9")
    await _enrol(db, 1001, s9.id, y1.id)
    await _enrol(db, 1002, s9.id, y1.id)

    plan = await plan_rollover(
        db, source_year_id=y1.id, target_year_id=y2.id,
        grade_progression={"Grade 9": "Grade 10"},
        hold_back_student_ids=[1002],
        dry_run=True,
    )
    outcomes = {s.student_id: s for s in plan.students}
    assert outcomes[1001].action == "promote"
    assert outcomes[1001].to_grade == "Grade 10"
    assert outcomes[1002].action == "held_back"
    assert outcomes[1002].to_grade == "Grade 9"


@pytest.mark.asyncio
async def test_non_active_enrolments_do_not_roll_forward(db):
    """A student who withdrew is not quietly re-enrolled next year."""
    campus = await _campus(db)
    y1 = await _year(db, campus.id, "2025-2026")
    y2 = await _year(db, campus.id, "2026-2027", is_active=False)
    s1 = await _section(db, campus.id, y1.id, "Grade 9")
    await _enrol(db, 1101, s1.id, y1.id, status="withdrawn")

    plan = await plan_rollover(
        db, source_year_id=y1.id, target_year_id=y2.id,
        grade_progression={"Grade 9": "Grade 10"}, dry_run=False,
    )
    assert plan.summary()["students_to_promote"] == 0


@pytest.mark.asyncio
async def test_rollover_across_campuses_is_refused(db):
    """Moving a cohort between campuses is a transfer, not a promotion."""
    a = await _campus(db, name="Campus A", code="A")
    b = await _campus(db, name="Campus B", code="B")
    y1 = await _year(db, a.id, "2025-2026")
    y2 = await _year(db, b.id, "2026-2027", is_active=False)

    with pytest.raises(HTTPException) as exc:
        await plan_rollover(
            db, source_year_id=y1.id, target_year_id=y2.id,
            grade_progression={"Grade 9": "Grade 10"}, dry_run=True,
        )
    assert exc.value.status_code == 400


# ---------------------------------------------------------------------------
# The two campus holes in the tenancy root
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_campus_bound_admin_cannot_create_a_section_elsewhere(db):
    a = await _campus(db, name="Campus A", code="A")
    b = await _campus(db, name="Campus B", code="B")
    admin_at_a = principal("SCHOOL_ADMIN", campus_id=a.id)

    with pytest.raises(HTTPException) as exc:
        await create_class_section(
            campus_id=b.id,
            payload=ClassSectionBase(grade_level="Grade 9", section_name="A"),
            class_teacher_id=None,
            academic_year_id=None,
            db_session=db,
            principal=admin_at_a,
        )
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_a_student_cannot_be_enrolled_into_another_campuss_section(db):
    a = await _campus(db, name="Campus A", code="A")
    b = await _campus(db, name="Campus B", code="B")
    year_b = await _year(db, b.id, "2026-2027")
    section_b = await _section(db, b.id, year_b.id, "Grade 9")
    staff_at_a = principal("STAFF", campus_id=a.id)

    with pytest.raises(HTTPException) as exc:
        await enroll_student(
            payload=StudentEnrollmentCreate(
                student_id=1201, section_id=section_b.id, academic_year_id=year_b.id
            ),
            db_session=db,
            principal=staff_at_a,
        )
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_section_and_year_from_different_campuses_is_refused(db):
    """The two could be mismatched, giving an enrolment that spans campuses."""
    a = await _campus(db, name="Campus A", code="A")
    b = await _campus(db, name="Campus B", code="B")
    year_a = await _year(db, a.id, "2026-2027")
    section_b = await _section(db, b.id, (await _year(db, b.id, "2026-2027")).id, "Grade 9")
    admin = principal("SUPER_ADMIN", campus_id=None)

    with pytest.raises(HTTPException) as exc:
        await enroll_student(
            payload=StudentEnrollmentCreate(
                student_id=1301, section_id=section_b.id, academic_year_id=year_a.id
            ),
            db_session=db,
            principal=admin,
        )
    assert exc.value.status_code == 400
