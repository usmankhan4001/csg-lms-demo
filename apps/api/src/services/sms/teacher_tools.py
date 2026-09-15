"""
CSG-LMS Teacher Module service layer — Lesson Planning & Coursework-Hour
Allocation (Phase 4, Part A.1/A.2).

Lesson-plan generation reuses the existing provider-agnostic LLM layer
(src.services.ai.llm.generate) -- the same abstraction the Socratic Tutor
(src/services/ai/socratic_tutor.py) and the AI assignment generator
(src/services/ai/assignment_gen.py) already use -- with a strict Pydantic
output type (GeneratedLessonPlan), not freeform chat.
"""

import logging
from typing import List, Optional

from sqlalchemy import and_, or_
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_teacher_tools import CourseworkHourAllocation, LessonPlan
from src.schemas.sms_teacher_tools import (
    CourseworkHourAllocationCreate,
    CourseworkHourAllocationUpdate,
    GeneratedLessonPlan,
    LessonPlanGenerateRequest,
)
from src.services.ai.llm import generate, model_for_tier

logger = logging.getLogger(__name__)

LESSON_PLAN_SYSTEM_PROMPT = """You are an expert instructional designer helping a teacher plan a single lesson.

Produce a structured, grade-appropriate lesson plan:
- Clear, measurable learning objectives (2-5).
- A sequence of activities (warm-up, direct instruction, guided/independent practice,
  closure as appropriate) whose durations sum to approximately the requested total
  lesson duration.
- A timing breakdown mirroring the activities.
- A short materials list and one or two formative assessment ideas.

Base everything strictly on the requested subject, topic, and grade level. Return ONLY
the structured plan."""


async def generate_lesson_plan(
    *,
    session: AsyncSession,
    request: LessonPlanGenerateRequest,
    teacher_id: Optional[str] = None,
    teacher_user_id: Optional[int] = None,
    model_name: Optional[str] = None,
) -> LessonPlan:
    """Generate a structured lesson plan from a teacher's prompt and persist it."""
    user_prompt = (
        f"Subject: {request.subject}\n"
        f"Topic: {request.topic}\n"
        f"Grade level: {request.grade_level}\n"
        f"Total lesson duration: {request.duration_minutes} minutes.\n"
    )
    if request.extra_instructions:
        user_prompt += f"Additional instructions: {request.extra_instructions}\n"

    plan: GeneratedLessonPlan = await generate(
        model_name=model_name or model_for_tier("standard"),
        user_prompt=user_prompt,
        system_prompt=LESSON_PLAN_SYSTEM_PROMPT,
        output_type=GeneratedLessonPlan,
    )

    record = LessonPlan(
        teacher_id=teacher_id,
        # Canonical identity (migration b7e2d41a9c38). Written alongside the
        # legacy user_uuid string so a plan authored now can be joined to its
        # author's timetable -- which the string alone never could.
        teacher_user_id=teacher_user_id,
        course_id=request.course_id,
        subject=plan.subject or request.subject,
        topic=plan.topic or request.topic,
        grade_level=plan.grade_level or request.grade_level,
        duration_minutes=plan.duration_minutes or request.duration_minutes,
        objectives=list(plan.objectives),
        activities=[a.model_dump() for a in plan.activities],
        timing_breakdown=[t.model_dump() for t in plan.timing_breakdown],
        materials=list(plan.materials),
        assessment_ideas=list(plan.assessment_ideas),
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record


async def get_lesson_plan(session: AsyncSession, lesson_plan_id: int) -> Optional[LessonPlan]:
    return await session.get(LessonPlan, lesson_plan_id)


async def list_lesson_plans(
    session: AsyncSession,
    teacher_id: Optional[str] = None,
    course_id: Optional[int] = None,
    teacher_user_id: Optional[int] = None,
) -> List[LessonPlan]:
    stmt = select(LessonPlan)
    if teacher_id is not None or teacher_user_id is not None:
        # Either identity names the same teacher. Plans written before
        # migration b7e2d41a9c38 carry only the user_uuid string; plans written
        # since carry both. Matching one alone would hide a teacher's own older
        # plans from their "my plans" list.
        arms = []
        if teacher_id is not None:
            arms.append(LessonPlan.teacher_id == teacher_id)
        if teacher_user_id is not None:
            arms.append(
                and_(
                    LessonPlan.teacher_user_id.is_not(None),
                    LessonPlan.teacher_user_id == teacher_user_id,
                )
            )
        stmt = stmt.where(or_(*arms) if len(arms) > 1 else arms[0])
    if course_id is not None:
        stmt = stmt.where(LessonPlan.course_id == course_id)
    stmt = stmt.order_by(LessonPlan.created_at.desc())
    return (await session.execute(stmt)).scalars().all()


# ---------------------------------------------------------------------------
# Coursework-hour allocation (plain CRUD, no AI)
# ---------------------------------------------------------------------------

async def create_hour_allocation(
    session: AsyncSession, payload: CourseworkHourAllocationCreate
) -> CourseworkHourAllocation:
    record = CourseworkHourAllocation(
        course_id=payload.course_id,
        unit_name=payload.unit_name,
        planned_hours=payload.planned_hours,
        order_index=payload.order_index,
        notes=payload.notes,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record


async def list_hour_allocations(
    session: AsyncSession, course_id: Optional[int] = None
) -> List[CourseworkHourAllocation]:
    stmt = select(CourseworkHourAllocation)
    if course_id is not None:
        stmt = stmt.where(CourseworkHourAllocation.course_id == course_id)
    stmt = stmt.order_by(CourseworkHourAllocation.order_index.asc())
    return (await session.execute(stmt)).scalars().all()


async def update_hour_allocation(
    session: AsyncSession,
    allocation_id: int,
    payload: CourseworkHourAllocationUpdate,
) -> Optional[CourseworkHourAllocation]:
    record = await session.get(CourseworkHourAllocation, allocation_id)
    if record is None:
        return None
    if payload.unit_name is not None:
        record.unit_name = payload.unit_name
    if payload.planned_hours is not None:
        record.planned_hours = payload.planned_hours
    if payload.order_index is not None:
        record.order_index = payload.order_index
    if payload.notes is not None:
        record.notes = payload.notes
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record


async def delete_hour_allocation(session: AsyncSession, allocation_id: int) -> bool:
    record = await session.get(CourseworkHourAllocation, allocation_id)
    if record is None:
        return False
    await session.delete(record)
    await session.commit()
    return True
