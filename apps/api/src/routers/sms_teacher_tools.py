"""
CSG-LMS Teacher Module router — Lesson Planning & Coursework-Hour Allocation
(Phase 4, Part A.1/A.2).

Gated by the existing `sms_gradebook` feature toggle (not a new toggle key):
this is additive teacher tooling layered on the gradebook/teacher module,
not a standalone new module -- see
src/security/features_utils/dependencies.py:require_sms_gradebook_feature.

Mount pattern matches the other SMS routers exactly (see
src/routers/sms_attendance.py): router-level `dependencies=[Depends(require_x_feature)]`
plus a per-handler `Depends(get_current_user_principal)`. Mounted in
src/router.py WITHOUT any router-mount-level Learnhouse-native auth
dependency, to avoid reintroducing the double-auth-gate bug fixed for the
other 8 SMS routers (see src/tests/routers/test_sms_router_mount_auth.py).
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.events.database import get_db_session
from src.security.school_ownership import get_user_id
from src.core.keycloak_auth import (
    KeycloakUserPrincipal,
    SCHOOL_ADMIN,
    SUPER_ADMIN,
    TEACHER,
    get_current_user_principal,
)
from src.schemas.sms_teacher_tools import (
    CourseworkHourAllocationCreate,
    CourseworkHourAllocationRead,
    CourseworkHourAllocationUpdate,
    LessonPlanGenerateRequest,
    LessonPlanRead,
)
from src.security.features_utils.dependencies import require_sms_gradebook_feature
from src.services.ai.llm import AINotConfiguredError
from src.services.sms.teacher_tools import (
    create_hour_allocation,
    delete_hour_allocation,
    generate_lesson_plan,
    get_lesson_plan,
    list_hour_allocations,
    list_lesson_plans,
    update_hour_allocation,
)

router = APIRouter(dependencies=[Depends(require_sms_gradebook_feature)])

TEACHER_STAFF_ROLES = [TEACHER, SCHOOL_ADMIN, SUPER_ADMIN]


def _require_staff(principal: KeycloakUserPrincipal) -> None:
    if not principal.has_any_role(TEACHER_STAFF_ROLES):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only teachers or school admins can manage teacher tools.",
        )


# ── Lesson Plans ──

@router.post(
    "/lesson-plans/generate",
    response_model=LessonPlanRead,
    status_code=status.HTTP_201_CREATED,
    summary="AI-Generate a Structured Lesson Plan",
    description=(
        "Generates a structured lesson plan (objectives, activities, timing "
        "breakdown) from a teacher's prompt (subject/topic/grade/duration)."
    ),
)
async def generate_lesson_plan_endpoint(
    payload: LessonPlanGenerateRequest,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> LessonPlanRead:
    _require_staff(principal)
    # Resolved before the try: this is identity, not generation. Raising inside
    # would be swallowed by the broad `except Exception` below and reported to
    # the teacher as "lesson plan generation failed", which is untrue.
    author_user_id = get_user_id(principal)
    try:
        record = await generate_lesson_plan(
            session=session,
            request=payload,
            teacher_id=principal.sub,
            teacher_user_id=author_user_id,
        )
    except AINotConfiguredError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Lesson plan generation failed. Please try again.",
        )
    return LessonPlanRead.model_validate(record)


@router.get(
    "/lesson-plans",
    response_model=List[LessonPlanRead],
    summary="List Lesson Plans",
)
async def list_lesson_plans_endpoint(
    course_id: Optional[int] = Query(None, description="Filter by Course ID"),
    mine_only: bool = Query(False, description="Only the caller's own generated plans"),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> List[LessonPlanRead]:
    # Both identities, because a teacher's own plans may predate migration
    # b7e2d41a9c38 (string only) or postdate it (both). Passing one alone would
    # silently drop half of their own list.
    teacher_id = principal.sub if mine_only else None
    teacher_user_id = get_user_id(principal) if mine_only else None
    records = await list_lesson_plans(
        session,
        teacher_id=teacher_id,
        course_id=course_id,
        teacher_user_id=teacher_user_id,
    )
    return [LessonPlanRead.model_validate(r) for r in records]


@router.get(
    "/lesson-plans/{lesson_plan_id}",
    response_model=LessonPlanRead,
    summary="Get a Lesson Plan by ID",
)
async def get_lesson_plan_endpoint(
    lesson_plan_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> LessonPlanRead:
    record = await get_lesson_plan(session, lesson_plan_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson plan not found.")
    return LessonPlanRead.model_validate(record)


# ── Coursework-Hour Allocation ──

@router.post(
    "/coursework-hours",
    response_model=CourseworkHourAllocationRead,
    status_code=status.HTTP_201_CREATED,
    summary="Allocate Planned Hours to a Coursework Unit",
)
async def create_hour_allocation_endpoint(
    payload: CourseworkHourAllocationCreate,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> CourseworkHourAllocationRead:
    _require_staff(principal)
    record = await create_hour_allocation(session, payload)
    return CourseworkHourAllocationRead.model_validate(record)


@router.get(
    "/coursework-hours",
    response_model=List[CourseworkHourAllocationRead],
    summary="List Coursework-Hour Allocations",
)
async def list_hour_allocations_endpoint(
    course_id: Optional[int] = Query(None, description="Filter by Course ID"),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> List[CourseworkHourAllocationRead]:
    records = await list_hour_allocations(session, course_id=course_id)
    return [CourseworkHourAllocationRead.model_validate(r) for r in records]


@router.patch(
    "/coursework-hours/{allocation_id}",
    response_model=CourseworkHourAllocationRead,
    summary="Update a Coursework-Hour Allocation",
)
async def update_hour_allocation_endpoint(
    allocation_id: int,
    payload: CourseworkHourAllocationUpdate,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> CourseworkHourAllocationRead:
    _require_staff(principal)
    record = await update_hour_allocation(session, allocation_id, payload)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Allocation not found.")
    return CourseworkHourAllocationRead.model_validate(record)


@router.delete(
    "/coursework-hours/{allocation_id}",
    summary="Delete a Coursework-Hour Allocation",
)
async def delete_hour_allocation_endpoint(
    allocation_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> dict:
    _require_staff(principal)
    deleted = await delete_hour_allocation(session, allocation_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Allocation not found.")
    return {"detail": "deleted"}
