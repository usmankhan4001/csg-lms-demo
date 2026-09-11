"""
Tests for the CSG-LMS Teacher Module additions (Phase 4, Part A.1/A.2):
AI-assisted lesson-plan authoring and coursework-hour allocation CRUD.

This module reuses the existing `sms_gradebook` feature toggle rather than
introducing a new one (see src/routers/sms_teacher_tools.py), so it is
exercised here as a standalone router the same way test_sms_gradebook.py
exercises the gradebook router's functions directly.
"""

import pytest
from fastapi import HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.keycloak_auth import KeycloakUserPrincipal
from src.schemas.sms_teacher_tools import (
    CourseworkHourAllocationCreate,
    CourseworkHourAllocationUpdate,
    LessonPlanGenerateRequest,
)
from src.routers.sms_teacher_tools import (
    create_hour_allocation_endpoint,
    delete_hour_allocation_endpoint,
    generate_lesson_plan_endpoint,
    get_lesson_plan_endpoint,
    list_hour_allocations_endpoint,
    list_lesson_plans_endpoint,
    update_hour_allocation_endpoint,
)
from src.services.sms import teacher_tools as teacher_tools_service


TEACHER = KeycloakUserPrincipal(sub="teacher-9", org_id=1, campus_id=1, roles={"TEACHER"})
STUDENT = KeycloakUserPrincipal(sub="student-9", org_id=1, campus_id=1, roles={"STUDENT"})


@pytest.mark.asyncio
async def test_generate_lesson_plan_produces_structured_output(db: AsyncSession, monkeypatch):
    from src.schemas.sms_teacher_tools import (
        GeneratedLessonPlan,
        LessonPlanActivity,
        LessonPlanTimingBlock,
    )

    async def _fake_generate(**kwargs):
        return GeneratedLessonPlan(
            subject="Biology",
            topic="Photosynthesis",
            grade_level="Grade 8",
            duration_minutes=45,
            objectives=["Explain the inputs and outputs of photosynthesis"],
            activities=[
                LessonPlanActivity(name="Warm-up discussion", duration_minutes=10, description="Recall plant cell parts."),
                LessonPlanActivity(name="Guided diagram activity", duration_minutes=25, description="Label the photosynthesis diagram."),
                LessonPlanActivity(name="Exit ticket", duration_minutes=10, description="Answer one recall question."),
            ],
            timing_breakdown=[
                LessonPlanTimingBlock(label="Warm-up", minutes=10),
                LessonPlanTimingBlock(label="Activity", minutes=25),
                LessonPlanTimingBlock(label="Closure", minutes=10),
            ],
            materials=["Diagram handout", "Colored pencils"],
            assessment_ideas=["Exit ticket recall question"],
        )

    monkeypatch.setattr(teacher_tools_service, "generate", _fake_generate)

    request = LessonPlanGenerateRequest(
        subject="Biology", topic="Photosynthesis", grade_level="Grade 8", duration_minutes=45,
    )
    plan = await generate_lesson_plan_endpoint(payload=request, session=db, principal=TEACHER)

    assert plan.subject == "Biology"
    assert plan.teacher_id == "teacher-9"
    assert len(plan.objectives) == 1
    assert len(plan.activities) == 3
    assert sum(a.duration_minutes for a in plan.activities) == 45
    assert len(plan.timing_breakdown) == 3

    # Non-staff caller cannot generate a lesson plan.
    with pytest.raises(HTTPException) as excinfo:
        await generate_lesson_plan_endpoint(payload=request, session=db, principal=STUDENT)
    assert excinfo.value.status_code == 403

    listed = await list_lesson_plans_endpoint(course_id=None, mine_only=False, session=db, principal=TEACHER)
    assert len(listed) == 1

    fetched = await get_lesson_plan_endpoint(lesson_plan_id=listed[0].id, session=db, principal=TEACHER)
    assert fetched.topic == "Photosynthesis"


@pytest.mark.asyncio
async def test_coursework_hour_allocation_crud(db: AsyncSession):
    created = await create_hour_allocation_endpoint(
        payload=CourseworkHourAllocationCreate(
            course_id=301, unit_name="Unit 1: Cell Biology", planned_hours=6.0, order_index=1,
        ),
        session=db,
        principal=TEACHER,
    )
    assert created.id is not None
    assert created.planned_hours == 6.0

    await create_hour_allocation_endpoint(
        payload=CourseworkHourAllocationCreate(
            course_id=301, unit_name="Unit 2: Genetics", planned_hours=8.0, order_index=2,
        ),
        session=db,
        principal=TEACHER,
    )

    listed = await list_hour_allocations_endpoint(course_id=301, session=db, principal=TEACHER)
    assert len(listed) == 2
    assert listed[0].unit_name == "Unit 1: Cell Biology"

    updated = await update_hour_allocation_endpoint(
        allocation_id=created.id,
        payload=CourseworkHourAllocationUpdate(planned_hours=7.5),
        session=db,
        principal=TEACHER,
    )
    assert updated.planned_hours == 7.5

    # Non-staff caller cannot create/update allocations.
    with pytest.raises(HTTPException) as excinfo:
        await create_hour_allocation_endpoint(
            payload=CourseworkHourAllocationCreate(course_id=301, unit_name="x", planned_hours=1.0),
            session=db,
            principal=STUDENT,
        )
    assert excinfo.value.status_code == 403

    deleted = await delete_hour_allocation_endpoint(
        allocation_id=created.id, session=db, principal=TEACHER
    )
    assert deleted == {"detail": "deleted"}

    remaining = await list_hour_allocations_endpoint(course_id=301, session=db, principal=TEACHER)
    assert len(remaining) == 1

    with pytest.raises(HTTPException) as excinfo_404:
        await update_hour_allocation_endpoint(
            allocation_id=99999,
            payload=CourseworkHourAllocationUpdate(planned_hours=1.0),
            session=db,
            principal=TEACHER,
        )
    assert excinfo_404.value.status_code == 404
