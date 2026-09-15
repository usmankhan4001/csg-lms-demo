"""
CSG-EMS Curricular Bridge & Gradebook Sync Service
==================================================
Provides business logic for section-subject course mappings and automated
synchronization between Learnhouse LMS course activities and the SMS Gradebook.
"""

import logging
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import HTTPException, status
from sqlalchemy import and_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.courses.courses import Course
from src.db.sms_campus import AcademicYear, ClassSection, StudentEnrollment, get_utc_now_iso
from src.db.sms_gradebook import (
    AssessmentPlan,
    GradeChangeAction,
    GradeChangeEvent,
    GradebookEntry,
)
from src.db.sms_section_subject import (
    SectionSubject,
    SectionSubjectCreate,
    SectionSubjectReadDetailed,
    SectionSubjectUpdate,
)
from src.db.users import User
from src.services.sms.gradebook import resolve_letter_and_gpa

logger = logging.getLogger("ems_section_subjects")


# ---------------------------------------------------------
# Section Subject CRUD Operations
# ---------------------------------------------------------

async def list_section_subjects(
    db_session: AsyncSession,
    section_id: int,
    academic_year_id: Optional[int] = None,
    is_elective: Optional[bool] = None,
) -> List[SectionSubjectReadDetailed]:
    """
    List all subjects mapped to a class section, enriched with course,
    section, and teacher metadata.
    """
    # Verify section exists
    section = (
        await db_session.execute(
            select(ClassSection).where(ClassSection.id == section_id)
        )
    ).scalar_one_or_none()
    if not section:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Class section {section_id} not found",
        )

    stmt = select(SectionSubject).where(SectionSubject.section_id == section_id)
    if academic_year_id is not None:
        stmt = stmt.where(
            (SectionSubject.academic_year_id == academic_year_id)
            | (SectionSubject.academic_year_id.is_(None))
        )
    if is_elective is not None:
        stmt = stmt.where(SectionSubject.is_elective == is_elective)

    records = (await db_session.execute(stmt)).scalars().all()
    detailed_list: List[SectionSubjectReadDetailed] = []

    for item in records:
        # Fetch related course details
        course = (
            await db_session.execute(
                select(Course).where(Course.id == item.course_id)
            )
        ).scalar_one_or_none()

        # Fetch teacher details if assigned
        teacher = None
        if item.teacher_id:
            teacher = (
                await db_session.execute(
                    select(User).where(User.id == item.teacher_id)
                )
            ).scalar_one_or_none()

        teacher_name = None
        teacher_email = None
        if teacher:
            teacher_name = f"{teacher.first_name} {teacher.last_name}".strip() or teacher.username
            teacher_email = teacher.email

        detailed_list.append(
            SectionSubjectReadDetailed(
                id=item.id,
                section_id=item.section_id,
                course_id=item.course_id,
                teacher_id=item.teacher_id,
                subject_name=item.subject_name,
                subject_code=item.subject_code,
                academic_year_id=item.academic_year_id,
                credit_hours=item.credit_hours,
                is_elective=item.is_elective,
                created_at=item.created_at,
                updated_at=item.updated_at,
                course_name=course.name if course else None,
                course_uuid=course.course_uuid if course else None,
                teacher_name=teacher_name,
                teacher_email=teacher_email,
                section_name=section.section_name,
                grade_level=section.grade_level,
            )
        )

    return detailed_list


async def get_section_subject(
    db_session: AsyncSession,
    section_id: int,
    subject_id: int,
) -> SectionSubjectReadDetailed:
    """Retrieve a single SectionSubject mapping with detailed metadata."""
    stmt = select(SectionSubject).where(
        SectionSubject.id == subject_id,
        SectionSubject.section_id == section_id,
    )
    item = (await db_session.execute(stmt)).scalar_one_or_none()
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Section subject {subject_id} not found in section {section_id}",
        )

    section = (
        await db_session.execute(
            select(ClassSection).where(ClassSection.id == item.section_id)
        )
    ).scalar_one_or_none()

    course = (
        await db_session.execute(
            select(Course).where(Course.id == item.course_id)
        )
    ).scalar_one_or_none()

    teacher = None
    if item.teacher_id:
        teacher = (
            await db_session.execute(
                select(User).where(User.id == item.teacher_id)
            )
        ).scalar_one_or_none()

    teacher_name = None
    teacher_email = None
    if teacher:
        teacher_name = f"{teacher.first_name} {teacher.last_name}".strip() or teacher.username
        teacher_email = teacher.email

    return SectionSubjectReadDetailed(
        id=item.id,
        section_id=item.section_id,
        course_id=item.course_id,
        teacher_id=item.teacher_id,
        subject_name=item.subject_name,
        subject_code=item.subject_code,
        academic_year_id=item.academic_year_id,
        credit_hours=item.credit_hours,
        is_elective=item.is_elective,
        created_at=item.created_at,
        updated_at=item.updated_at,
        course_name=course.name if course else None,
        course_uuid=course.course_uuid if course else None,
        teacher_name=teacher_name,
        teacher_email=teacher_email,
        section_name=section.section_name if section else None,
        grade_level=section.grade_level if section else None,
    )


async def create_section_subject(
    db_session: AsyncSession,
    section_id: int,
    payload: SectionSubjectCreate,
) -> SectionSubjectReadDetailed:
    """
    Create a new SectionSubject bridge mapping an LMS Course to an SMS Section.
    """
    # 1. Validate section
    section = (
        await db_session.execute(
            select(ClassSection).where(ClassSection.id == section_id)
        )
    ).scalar_one_or_none()
    if not section:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Class section {section_id} not found",
        )

    # 2. Validate course
    course = (
        await db_session.execute(
            select(Course).where(Course.id == payload.course_id)
        )
    ).scalar_one_or_none()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Course {payload.course_id} not found",
        )

    # 3. Validate teacher if supplied
    teacher = None
    if payload.teacher_id:
        teacher = (
            await db_session.execute(
                select(User).where(User.id == payload.teacher_id)
            )
        ).scalar_one_or_none()
        if not teacher:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Teacher user {payload.teacher_id} not found",
            )

    # 4. Validate academic year if supplied
    year_id = payload.academic_year_id or section.academic_year_id
    if year_id:
        year = (
            await db_session.execute(
                select(AcademicYear).where(AcademicYear.id == year_id)
            )
        ).scalar_one_or_none()
        if not year:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Academic year {year_id} not found",
            )

    # 5. Check if duplicate mapping exists
    existing = (
        await db_session.execute(
            select(SectionSubject).where(
                SectionSubject.section_id == section_id,
                SectionSubject.course_id == payload.course_id,
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Course {payload.course_id} is already mapped to section {section_id}",
        )

    now = get_utc_now_iso()
    new_bridge = SectionSubject(
        section_id=section_id,
        course_id=payload.course_id,
        teacher_id=payload.teacher_id,
        subject_name=payload.subject_name,
        subject_code=payload.subject_code,
        academic_year_id=year_id,
        credit_hours=payload.credit_hours,
        is_elective=payload.is_elective,
        created_at=now,
        updated_at=now,
    )
    db_session.add(new_bridge)
    await db_session.commit()
    await db_session.refresh(new_bridge)

    teacher_name = None
    teacher_email = None
    if teacher:
        teacher_name = f"{teacher.first_name} {teacher.last_name}".strip() or teacher.username
        teacher_email = teacher.email

    return SectionSubjectReadDetailed(
        id=new_bridge.id,
        section_id=new_bridge.section_id,
        course_id=new_bridge.course_id,
        teacher_id=new_bridge.teacher_id,
        subject_name=new_bridge.subject_name,
        subject_code=new_bridge.subject_code,
        academic_year_id=new_bridge.academic_year_id,
        credit_hours=new_bridge.credit_hours,
        is_elective=new_bridge.is_elective,
        created_at=new_bridge.created_at,
        updated_at=new_bridge.updated_at,
        course_name=course.name,
        course_uuid=course.course_uuid,
        teacher_name=teacher_name,
        teacher_email=teacher_email,
        section_name=section.section_name,
        grade_level=section.grade_level,
    )


async def update_section_subject(
    db_session: AsyncSession,
    section_id: int,
    subject_id: int,
    payload: SectionSubjectUpdate,
) -> SectionSubjectReadDetailed:
    """Update an existing SectionSubject mapping."""
    stmt = select(SectionSubject).where(
        SectionSubject.id == subject_id,
        SectionSubject.section_id == section_id,
    )
    item = (await db_session.execute(stmt)).scalar_one_or_none()
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Section subject {subject_id} not found in section {section_id}",
        )

    if payload.course_id is not None:
        course = (
            await db_session.execute(
                select(Course).where(Course.id == payload.course_id)
            )
        ).scalar_one_or_none()
        if not course:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Course {payload.course_id} not found",
            )
        item.course_id = payload.course_id

    if payload.teacher_id is not None:
        if payload.teacher_id > 0:
            teacher = (
                await db_session.execute(
                    select(User).where(User.id == payload.teacher_id)
                )
            ).scalar_one_or_none()
            if not teacher:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Teacher user {payload.teacher_id} not found",
                )
            item.teacher_id = payload.teacher_id
        else:
            item.teacher_id = None

    if payload.subject_name is not None:
        item.subject_name = payload.subject_name
    if payload.subject_code is not None:
        item.subject_code = payload.subject_code
    if payload.academic_year_id is not None:
        item.academic_year_id = payload.academic_year_id
    if payload.credit_hours is not None:
        item.credit_hours = payload.credit_hours
    if payload.is_elective is not None:
        item.is_elective = payload.is_elective

    item.updated_at = get_utc_now_iso()
    db_session.add(item)
    await db_session.commit()
    await db_session.refresh(item)

    return await get_section_subject(db_session, section_id, subject_id)


async def delete_section_subject(
    db_session: AsyncSession,
    section_id: int,
    subject_id: int,
) -> dict:
    """Remove a SectionSubject curricular bridge."""
    stmt = select(SectionSubject).where(
        SectionSubject.id == subject_id,
        SectionSubject.section_id == section_id,
    )
    item = (await db_session.execute(stmt)).scalar_one_or_none()
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Section subject {subject_id} not found in section {section_id}",
        )

    await db_session.delete(item)
    await db_session.commit()
    return {"message": f"Section subject {subject_id} removed successfully", "id": subject_id}


# ---------------------------------------------------------
# Automated LMS -> SMS Gradebook Synchronization Service
# ---------------------------------------------------------

async def sync_course_activity_grade_to_sms(
    db_session: AsyncSession,
    student_id: int,
    course_id: int,
    raw_score: float,
    max_score: float,
    activity_title: str,
    remarks: Optional[str] = None,
    graded_by: Optional[int] = None,
) -> List[GradebookEntry]:
    """
    Automated Bridge Sync:
    When a student completes/grades an activity in a Learnhouse Course, this
    service finds all SectionSubject mappings for that course, identifies
    the student's active section enrollment, and records a GradebookEntry in
    the SMS Gradebook under a corresponding AssessmentPlan.
    """
    # 1. Look up SectionSubjects attached to this Course
    stmt = select(SectionSubject).where(SectionSubject.course_id == course_id)
    section_subjects = (await db_session.execute(stmt)).scalars().all()

    if not section_subjects:
        logger.debug(
            "No SMS SectionSubject bridge found for course %s; skipping SMS grade sync.",
            course_id,
        )
        return []

    section_ids = [ss.section_id for ss in section_subjects]

    # 2. Check which of these sections the student is actively enrolled in
    enrollment_stmt = select(StudentEnrollment).where(
        StudentEnrollment.student_id == student_id,
        StudentEnrollment.section_id.in_(section_ids),
        StudentEnrollment.status == "active",
    )
    enrollments = (await db_session.execute(enrollment_stmt)).scalars().all()

    if not enrollments:
        logger.debug(
            "Student %s is not actively enrolled in any section bridged to course %s.",
            student_id,
            course_id,
        )
        return []

    synced_entries: List[GradebookEntry] = []
    now = datetime.now(timezone.utc)
    effective_max = float(max_score) if max_score > 0 else 100.0
    effective_raw = min(float(raw_score), effective_max)
    pct = (effective_raw / effective_max * 100.0) if effective_max > 0 else 0.0
    letter, gpa_pt = resolve_letter_and_gpa(pct)

    for enrollment in enrollments:
        section_id = enrollment.section_id

        # 3. Find or create an AssessmentPlan for this course and section
        plan_stmt = select(AssessmentPlan).where(
            AssessmentPlan.course_id == course_id,
            AssessmentPlan.section_id == section_id,
            AssessmentPlan.assessment_name == activity_title,
        )
        plan = (await db_session.execute(plan_stmt)).scalar_one_or_none()

        if not plan:
            # Create a dedicated assessment plan item for this course activity
            plan = AssessmentPlan(
                course_id=course_id,
                section_id=section_id,
                academic_term_id=None,
                assessment_name=activity_title,
                weight_percentage=100.0,
                max_score=effective_max,
            )
            db_session.add(plan)
            await db_session.flush()
            await db_session.refresh(plan)

        weighted_score = (pct * plan.weight_percentage) / 100.0

        # 4. Check existing GradebookEntry
        existing_stmt = select(GradebookEntry).where(
            and_(
                GradebookEntry.student_id == student_id,
                GradebookEntry.assessment_plan_id == plan.id,
            )
        )
        existing = (await db_session.execute(existing_stmt)).scalar_one_or_none()

        if existing:
            prev_raw = existing.raw_score
            prev_letter = existing.letter_grade
            existing.raw_score = effective_raw
            existing.max_score = plan.max_score
            existing.weighted_score = weighted_score
            existing.letter_grade = letter
            existing.gpa_point = gpa_pt
            existing.remarks = remarks or f"LMS Course Activity: {activity_title}"
            existing.graded_by = graded_by
            existing.graded_at = now
            db_session.add(existing)
            await db_session.flush()

            # Append to audit trail
            db_session.add(
                GradeChangeEvent(
                    gradebook_entry_id=existing.id,
                    student_id=student_id,
                    assessment_plan_id=plan.id,
                    section_id=section_id,
                    action=GradeChangeAction.CHANGED,
                    previous_raw_score=prev_raw,
                    new_raw_score=effective_raw,
                    previous_letter_grade=prev_letter,
                    new_letter_grade=letter,
                    max_score=plan.max_score,
                    changed_by_user_id=graded_by,
                    reason=f"LMS Course Grade Sync: {activity_title}",
                    created_at=now,
                )
            )
            synced_entries.append(existing)
        else:
            new_entry = GradebookEntry(
                student_id=student_id,
                assessment_plan_id=plan.id,
                raw_score=effective_raw,
                max_score=plan.max_score,
                weighted_score=weighted_score,
                letter_grade=letter,
                gpa_point=gpa_pt,
                remarks=remarks or f"LMS Course Activity: {activity_title}",
                graded_by=graded_by,
                graded_at=now,
            )
            db_session.add(new_entry)
            await db_session.flush()
            await db_session.refresh(new_entry)

            # Append to audit trail
            db_session.add(
                GradeChangeEvent(
                    gradebook_entry_id=new_entry.id,
                    student_id=student_id,
                    assessment_plan_id=plan.id,
                    section_id=section_id,
                    action=GradeChangeAction.CREATED,
                    previous_raw_score=None,
                    new_raw_score=effective_raw,
                    previous_letter_grade=None,
                    new_letter_grade=letter,
                    max_score=plan.max_score,
                    changed_by_user_id=graded_by,
                    reason=f"LMS Course Grade Sync: {activity_title}",
                    created_at=now,
                )
            )
            synced_entries.append(new_entry)

    await db_session.commit()
    logger.info(
        "Successfully synced LMS grade for student %s in course %s (%d gradebook entries updated)",
        student_id,
        course_id,
        len(synced_entries),
    )
    return synced_entries
