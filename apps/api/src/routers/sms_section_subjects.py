"""
CSG-EMS Academic Curricular Bridge & Section-Subject Router
===========================================================
Provides RESTful endpoints for managing mappings between LMS Courses and
SMS Class Sections under `/api/v1/ems/academic/sections/{section_id}/subjects`.
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.events.database import get_db_session
from src.core.keycloak_auth import (
    KeycloakUserPrincipal,
    PARENT,
    SCHOOL_ADMIN,
    STAFF,
    STUDENT,
    SUPER_ADMIN,
    TEACHER,
    get_current_user_principal,
    require_roles,
)
from src.db.sms_section_subject import (
    SectionSubjectCreate,
    SectionSubjectReadDetailed,
    SectionSubjectUpdate,
)
from src.services.sms.section_subjects import (
    create_section_subject,
    delete_section_subject,
    get_section_subject,
    list_section_subjects,
    sync_course_activity_grade_to_sms,
    update_section_subject,
)

logger = logging.getLogger("ems_section_subjects")

router = APIRouter(prefix="/ems/academic", tags=["EMS Academic Curricular Bridge"])

# Staff roles allowed to create, update, or delete curricular mappings
STAFF_ROLES = [SUPER_ADMIN, SCHOOL_ADMIN, TEACHER]
# All roles allowed to view section subjects
READ_ROLES = [SUPER_ADMIN, SCHOOL_ADMIN, TEACHER, STUDENT, PARENT, STAFF]


class ManualGradeSyncRequest(BaseModel):
    """Payload for manually triggering a grade sync from an LMS course activity."""
    student_id: int = Field(..., description="Student User ID")
    course_id: int = Field(..., description="Learnhouse Course ID")
    raw_score: float = Field(..., description="Student's raw earned score")
    max_score: float = Field(default=100.0, description="Max possible score")
    activity_title: str = Field(..., description="Name of the activity/assignment")
    remarks: Optional[str] = Field(default=None, description="Optional grading remarks")


# ---------------------------------------------------------
# Section Subject Endpoints
# ---------------------------------------------------------

@router.get(
    "/sections/{section_id}/subjects",
    response_model=List[SectionSubjectReadDetailed],
    summary="List Section Subjects",
    description="Retrieve all mapped LMS courses/subjects for the specified class section.",
)
async def api_list_section_subjects(
    section_id: int,
    academic_year_id: Optional[int] = Query(None, description="Filter by Academic Year ID"),
    is_elective: Optional[bool] = Query(None, description="Filter elective subjects"),
    db_session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> List[SectionSubjectReadDetailed]:
    return await list_section_subjects(
        db_session=db_session,
        section_id=section_id,
        academic_year_id=academic_year_id,
        is_elective=is_elective,
    )


@router.post(
    "/sections/{section_id}/subjects",
    response_model=SectionSubjectReadDetailed,
    status_code=status.HTTP_201_CREATED,
    summary="Create Section Subject Mapping",
    description="Bridge a Learnhouse LMS Course to an SMS Class Section with subject details.",
)
async def api_create_section_subject(
    section_id: int,
    payload: SectionSubjectCreate = Body(...),
    db_session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(STAFF_ROLES)),
) -> SectionSubjectReadDetailed:
    return await create_section_subject(
        db_session=db_session,
        section_id=section_id,
        payload=payload,
    )


@router.get(
    "/sections/{section_id}/subjects/{subject_id}",
    response_model=SectionSubjectReadDetailed,
    summary="Get Section Subject",
    description="Retrieve detailed metadata for a specific section subject mapping.",
)
async def api_get_section_subject(
    section_id: int,
    subject_id: int,
    db_session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> SectionSubjectReadDetailed:
    return await get_section_subject(
        db_session=db_session,
        section_id=section_id,
        subject_id=subject_id,
    )


@router.put(
    "/sections/{section_id}/subjects/{subject_id}",
    response_model=SectionSubjectReadDetailed,
    summary="Update Section Subject",
    description="Update subject metadata, teacher assignment, or credit hours.",
)
async def api_update_section_subject(
    section_id: int,
    subject_id: int,
    payload: SectionSubjectUpdate = Body(...),
    db_session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(STAFF_ROLES)),
) -> SectionSubjectReadDetailed:
    return await update_section_subject(
        db_session=db_session,
        section_id=section_id,
        subject_id=subject_id,
        payload=payload,
    )


@router.delete(
    "/sections/{section_id}/subjects/{subject_id}",
    summary="Delete Section Subject",
    description="Remove the bridge between a Course and Class Section.",
)
async def api_delete_section_subject(
    section_id: int,
    subject_id: int,
    db_session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(STAFF_ROLES)),
) -> dict:
    return await delete_section_subject(
        db_session=db_session,
        section_id=section_id,
        subject_id=subject_id,
    )


@router.post(
    "/sections/{section_id}/sync-grades",
    summary="Manual Course Activity Grade Sync",
    description="Trigger manual sync of an LMS course activity score to the SMS Gradebook.",
)
async def api_manual_sync_course_grade(
    section_id: int,
    payload: ManualGradeSyncRequest = Body(...),
    db_session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(STAFF_ROLES)),
) -> dict:
    entries = await sync_course_activity_grade_to_sms(
        db_session=db_session,
        student_id=payload.student_id,
        course_id=payload.course_id,
        raw_score=payload.raw_score,
        max_score=payload.max_score,
        activity_title=payload.activity_title,
        remarks=payload.remarks,
        graded_by=principal.raw_claims.get("lh_user_id"),
    )
    return {
        "success": True,
        "synced_entries_count": len(entries),
        "section_id": section_id,
        "student_id": payload.student_id,
        "course_id": payload.course_id,
    }
