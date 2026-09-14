from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.events.database import get_db_session
from src.core.keycloak_auth import (
    KeycloakUserPrincipal,
    SUPER_ADMIN,
    SCHOOL_ADMIN,
    TEACHER,
    STAFF,
    STUDENT,
    get_current_user_principal,
    require_roles,
)
from src.schemas.sms_pathways import (
    CurricularPathwayCreate,
    CurricularPathwayRead,
    EnrollPathwayPayload,
    StudentPathwayProgressRead,
)
from src.services.sms.pathways import CurricularPathwayService

router = APIRouter(prefix="/sms/pathways", tags=["sms-pathways"])


@router.post("", response_model=CurricularPathwayRead, status_code=status.HTTP_201_CREATED)
async def create_pathway(
    payload: CurricularPathwayCreate,
    db: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles([SUPER_ADMIN, SCHOOL_ADMIN])),
):
    pathway = await CurricularPathwayService.create_pathway(db=db, payload=payload, org_id=principal.org_id)
    return (await CurricularPathwayService.list_pathways(db=db, org_id=principal.org_id))[0]


@router.get("", response_model=List[CurricularPathwayRead])
async def list_pathways(
    db: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
):
    return await CurricularPathwayService.list_pathways(db=db, org_id=principal.org_id)


@router.post("/enroll", status_code=status.HTTP_201_CREATED)
async def enroll_student(
    payload: EnrollPathwayPayload,
    db: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles([SUPER_ADMIN, SCHOOL_ADMIN, TEACHER, STAFF])),
):
    return await CurricularPathwayService.enroll_student(
        db=db, student_id=payload.student_id, pathway_id=payload.pathway_id, org_id=principal.org_id
    )


@router.get("/progress/{student_id}", response_model=List[StudentPathwayProgressRead])
async def get_student_progress(
    student_id: int,
    db: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
):
    return await CurricularPathwayService.get_student_progress(db=db, student_id=student_id)
