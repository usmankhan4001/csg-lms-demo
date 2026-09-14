"""Academic year rollover: carry sections and students into the next year.

This is THE annual operation a school system must perform, and it did not
exist. `ClassSection` had no `academic_year_id`, so "Grade 9 A" was one
permanent row: you could not promote a cohort, could not say who taught 9A
last year, and could not archive a year. Every August a school would have had
to hand-rebuild every enrolment.

DESIGN RULES, and the reasoning matters more than the code:

1. **Rollover only ever CREATES.** It never updates or deletes a row belonging
   to the outgoing year. That makes "history stays readable" a structural
   property rather than a promise -- there is no code path here that can
   rewrite last year. It also means graduation is NOT handled by marking last
   year's enrolment `graduated`; see rule 4.

2. **Idempotent.** Re-running is safe and is expected: a school will run the
   dry run, run it for real, notice a missing section, and run it again.
   Sections are matched on (year, grade_level, section_name) and enrolments on
   the existing UNIQUE (student_id, academic_year_id) index, so a second run
   creates nothing and reports everything as already present.

3. **Dry run writes nothing.** A school will not press this button blind. The
   dry run returns the exact same plan object the real run acts on, so what is
   previewed is what happens.

4. **Grade progression is SUPPLIED, never inferred.** There is no grade
   ordering anywhere in this data model -- `grade_level` is a free string, and
   "KG-1", "Grade 1" and "Year 7" all appear in real schools. Guessing that
   "Grade 9" precedes "Grade 10" would work until it silently promoted a KG
   child into Year 1, or promoted a final-year cohort into a grade that does
   not exist. So the caller supplies an explicit map, and any grade NOT in the
   map is reported as unmapped and left alone. Mapping a grade to `None` is
   how a school says "this cohort is leaving" -- those students are reported
   as graduating and simply not promoted.

WHAT THIS DELIBERATELY DOES NOT DO:

- **Repeating students.** The data model has no "retained" or "promoted" flag,
  and nothing in an enrolment row says a child should repeat the year. Rather
  than infer it, the caller may pass `hold_back_student_ids`; those students
  are promoted into the SAME grade in the new year. Without that list, nobody
  is held back. A rollover that silently mis-promotes a child is worse than
  one that refuses.
- **Marking leavers graduated.** That is a mutation of the outgoing year (see
  rule 1) and is a separate, deliberate act by the office.
- **Teacher reassignment.** `class_teacher_id` is copied forward as-is; who
  teaches which class next year is a staffing decision, not a data migration.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from fastapi import HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_campus import (
    AcademicYear,
    ClassSection,
    StudentEnrollment,
    get_utc_now_iso,
)

# Only these enrolment statuses roll forward. A student who transferred out,
# graduated or withdrew is not a member of the school next year, and quietly
# re-enrolling them would recreate a record the office deliberately closed.
PROMOTABLE_STATUSES = ("active",)


@dataclass
class SectionPlan:
    """One section that will be, or already is, present in the target year."""
    source_section_id: int
    grade_level: str
    section_name: str
    target_grade_level: str
    already_exists: bool = False
    target_section_id: Optional[int] = None


@dataclass
class StudentPlan:
    """One student's outcome. `reason` is always populated for a non-promotion
    so the office can see WHY a child was left behind rather than guessing."""
    student_id: int
    source_section_id: int
    from_grade: str
    to_grade: Optional[str]
    action: str  # "promote" | "already_enrolled" | "graduating" | "unmapped" | "held_back"
    reason: Optional[str] = None


@dataclass
class RolloverPlan:
    source_year_id: int
    target_year_id: int
    campus_id: int
    dry_run: bool
    sections: List[SectionPlan] = field(default_factory=list)
    students: List[StudentPlan] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def summary(self) -> Dict[str, int]:
        return {
            "sections_to_create": sum(1 for s in self.sections if not s.already_exists),
            "sections_already_present": sum(1 for s in self.sections if s.already_exists),
            "students_to_promote": sum(1 for s in self.students if s.action == "promote"),
            "students_held_back": sum(1 for s in self.students if s.action == "held_back"),
            "students_already_enrolled": sum(1 for s in self.students if s.action == "already_enrolled"),
            "students_graduating": sum(1 for s in self.students if s.action == "graduating"),
            "students_unmapped": sum(1 for s in self.students if s.action == "unmapped"),
        }


async def _load_year(db_session: AsyncSession, year_id: int, label: str) -> AcademicYear:
    year = (
        await db_session.execute(select(AcademicYear).where(AcademicYear.id == year_id))
    ).scalar_one_or_none()
    if year is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{label} academic year {year_id} not found",
        )
    return year


async def plan_rollover(
    db_session: AsyncSession,
    *,
    source_year_id: int,
    target_year_id: int,
    grade_progression: Dict[str, Optional[str]],
    hold_back_student_ids: Optional[List[int]] = None,
    dry_run: bool = True,
) -> RolloverPlan:
    """Build (and optionally apply) the rollover plan.

    The dry run and the real run share this single code path, so the preview a
    school approves is literally the plan that executes -- they cannot drift.
    """
    held_back = set(hold_back_student_ids or [])

    source_year = await _load_year(db_session, source_year_id, "Source")
    target_year = await _load_year(db_session, target_year_id, "Target")

    if source_year.id == target_year.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source and target academic year must differ",
        )
    # Both years must belong to the same campus. Rolling a cohort across
    # campuses is a transfer, not a promotion, and must not happen by accident.
    if source_year.campus_id != target_year.campus_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Source and target academic years belong to different campuses. "
                "Moving students between campuses is a transfer, not a rollover."
            ),
        )

    plan = RolloverPlan(
        source_year_id=source_year_id,
        target_year_id=target_year_id,
        campus_id=source_year.campus_id,
        dry_run=dry_run,
    )

    # Sections in the outgoing year. Sections predating the academic_year_id
    # column (NULL) are matched by campus so a school mid-upgrade can still
    # roll forward -- they simply have no year of their own yet.
    source_sections = list(
        (
            await db_session.execute(
                select(ClassSection).where(
                    ClassSection.campus_id == source_year.campus_id,
                    ClassSection.academic_year_id == source_year_id,
                )
            )
        ).scalars().all()
    )
    if not source_sections:
        legacy = list(
            (
                await db_session.execute(
                    select(ClassSection).where(
                        ClassSection.campus_id == source_year.campus_id,
                        ClassSection.academic_year_id.is_(None),  # type: ignore[union-attr]
                    )
                )
            ).scalars().all()
        )
        if legacy:
            source_sections = legacy
            plan.warnings.append(
                f"{len(legacy)} section(s) have no academic year recorded and were "
                "treated as belonging to the source year. Set their academic year "
                "to remove this ambiguity."
            )

    existing_target = list(
        (
            await db_session.execute(
                select(ClassSection).where(
                    ClassSection.campus_id == target_year.campus_id,
                    ClassSection.academic_year_id == target_year_id,
                )
            )
        ).scalars().all()
    )
    # Idempotency key for sections.
    target_by_key = {(s.grade_level, s.section_name): s for s in existing_target}

    section_by_id = {s.id: s for s in source_sections}
    created_sections: Dict[int, ClassSection] = {}

    # Which source sections contain a student the school has told us to hold
    # back. Those students repeat their CURRENT grade, so that grade needs a
    # section in the target year too -- rollover otherwise only creates the
    # progressed grades and a retained child would have nowhere to go. This is
    # derived from the explicit hold_back list, not inferred.
    retained_source_section_ids = set()
    if held_back:
        for enr in (
            await db_session.execute(
                select(StudentEnrollment).where(
                    StudentEnrollment.academic_year_id == source_year_id,
                    StudentEnrollment.student_id.in_(held_back),  # type: ignore[union-attr]
                )
            )
        ).scalars().all():
            retained_source_section_ids.add(enr.section_id)

    # Sections the plan INTENDS to exist in the target year, whether they are
    # already there or would be created by this run. A dry run creates nothing,
    # so without this the preview would match no student to any section and
    # report "unmapped" for the entire school -- while the real run promoted
    # everybody. The preview a school approves has to be the plan that
    # executes, so both runs resolve students against this same set.
    planned_section_keys = set(target_by_key.keys())

    for section in source_sections:
        if section.grade_level not in grade_progression:
            plan.warnings.append(
                f"Grade '{section.grade_level}' is not in the progression map; "
                f"section '{section.section_name}' was not rolled forward."
            )
            continue
        target_grade = grade_progression[section.grade_level]
        if target_grade is None:
            # Leaving cohort: no section is created for them next year.
            continue

        key = (target_grade, section.section_name)
        existing = target_by_key.get(key)
        sp = SectionPlan(
            source_section_id=section.id,  # type: ignore[arg-type]
            grade_level=section.grade_level,
            section_name=section.section_name,
            target_grade_level=target_grade,
            already_exists=existing is not None,
            target_section_id=existing.id if existing else None,
        )
        if existing is None and not dry_run:
            new_section = ClassSection(
                campus_id=target_year.campus_id,
                academic_year_id=target_year_id,
                grade_level=target_grade,
                section_name=section.section_name,
                room_number=section.room_number,
                class_teacher_id=section.class_teacher_id,
                max_capacity=section.max_capacity,
                is_active=True,
            )
            db_session.add(new_section)
            await db_session.flush()
            sp.target_section_id = new_section.id
            created_sections[section.id] = new_section  # type: ignore[index]
            target_by_key[key] = new_section
        planned_section_keys.add(key)
        plan.sections.append(sp)

        # A retained child repeats this grade, so it must also exist next year.
        if section.id in retained_source_section_ids:
            retained_key = (section.grade_level, section.section_name)
            if retained_key not in planned_section_keys:
                retained_existing = target_by_key.get(retained_key)
                rsp = SectionPlan(
                    source_section_id=section.id,  # type: ignore[arg-type]
                    grade_level=section.grade_level,
                    section_name=section.section_name,
                    target_grade_level=section.grade_level,
                    already_exists=retained_existing is not None,
                    target_section_id=retained_existing.id if retained_existing else None,
                )
                if retained_existing is None and not dry_run:
                    retained_section = ClassSection(
                        campus_id=target_year.campus_id,
                        academic_year_id=target_year_id,
                        grade_level=section.grade_level,
                        section_name=section.section_name,
                        room_number=section.room_number,
                        class_teacher_id=section.class_teacher_id,
                        max_capacity=section.max_capacity,
                        is_active=True,
                    )
                    db_session.add(retained_section)
                    await db_session.flush()
                    rsp.target_section_id = retained_section.id
                    target_by_key[retained_key] = retained_section
                planned_section_keys.add(retained_key)
                plan.sections.append(rsp)

    # Enrolments in the outgoing year.
    source_enrollments = list(
        (
            await db_session.execute(
                select(StudentEnrollment).where(
                    StudentEnrollment.academic_year_id == source_year_id
                )
            )
        ).scalars().all()
    )

    already_in_target = {
        e.student_id
        for e in (
            await db_session.execute(
                select(StudentEnrollment).where(
                    StudentEnrollment.academic_year_id == target_year_id
                )
            )
        ).scalars().all()
    }

    for enr in source_enrollments:
        section = section_by_id.get(enr.section_id)
        if section is None:
            continue
        from_grade = section.grade_level

        if enr.status not in PROMOTABLE_STATUSES:
            plan.students.append(StudentPlan(
                student_id=enr.student_id,
                source_section_id=enr.section_id,
                from_grade=from_grade,
                to_grade=None,
                action="graduating" if enr.status == "graduated" else "unmapped",
                reason=f"Enrolment status is '{enr.status}', not active.",
            ))
            continue

        if from_grade not in grade_progression:
            plan.students.append(StudentPlan(
                student_id=enr.student_id,
                source_section_id=enr.section_id,
                from_grade=from_grade,
                to_grade=None,
                action="unmapped",
                reason=f"Grade '{from_grade}' is not in the progression map.",
            ))
            continue

        # A held-back student repeats the SAME grade rather than progressing.
        held = enr.student_id in held_back
        target_grade = from_grade if held else grade_progression[from_grade]

        if target_grade is None:
            plan.students.append(StudentPlan(
                student_id=enr.student_id,
                source_section_id=enr.section_id,
                from_grade=from_grade,
                to_grade=None,
                action="graduating",
                reason="Final year: this cohort leaves rather than progressing.",
            ))
            continue

        if enr.student_id in already_in_target:
            plan.students.append(StudentPlan(
                student_id=enr.student_id,
                source_section_id=enr.section_id,
                from_grade=from_grade,
                to_grade=target_grade,
                action="already_enrolled",
                reason="Student already has an enrolment in the target year.",
            ))
            continue

        target_key = (target_grade, section.section_name)
        if target_key not in planned_section_keys:
            plan.students.append(StudentPlan(
                student_id=enr.student_id,
                source_section_id=enr.section_id,
                from_grade=from_grade,
                to_grade=target_grade,
                action="unmapped",
                reason=(
                    f"No section '{section.section_name}' exists in grade "
                    f"'{target_grade}' for the target year."
                ),
            ))
            continue

        plan.students.append(StudentPlan(
            student_id=enr.student_id,
            source_section_id=enr.section_id,
            from_grade=from_grade,
            to_grade=target_grade,
            action="held_back" if held else "promote",
            reason="Repeating the year at the school's instruction." if held else None,
        ))

        if not dry_run:
            target_section = target_by_key[target_key]
            db_session.add(StudentEnrollment(
                student_id=enr.student_id,
                section_id=target_section.id,
                academic_year_id=target_year_id,
                roll_number=enr.roll_number,
                status="active",
                enrolled_at=get_utc_now_iso(),
            ))
            already_in_target.add(enr.student_id)

    if not dry_run:
        await db_session.commit()

    return plan
