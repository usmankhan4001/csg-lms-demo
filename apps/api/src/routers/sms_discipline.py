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
    PSYCHOLOGIST,
    get_current_user_principal,
    require_roles,
)
from src.db.sms_discipline import IncidentSeverityEnum, IncidentStatusEnum
from src.schemas.sms_discipline import (
    IncidentCreate,
    IncidentRead,
    IncidentUpdate,
    SuspensionCreate,
    SuspensionRead,
)
from src.services.sms.discipline import DisciplineService

router = APIRouter(prefix="/sms/discipline", tags=["sms-discipline"])


@router.post("/incidents", response_model=IncidentRead, status_code=status.HTTP_201_CREATED)
async def create_incident(
    payload: IncidentCreate,
    db: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles([SUPER_ADMIN, SCHOOL_ADMIN, TEACHER, STAFF, PSYCHOLOGIST])),
):
    user_id = principal.raw_claims.get("lh_user_id", 0)
    return await DisciplineService.create_incident(
        db=db,
        payload=payload,
        reporter_id=user_id,
        org_id=principal.org_id,
        campus_id=principal.campus_id,
    )


@router.get("/incidents", response_model=List[IncidentRead])
async def list_incidents(
    student_id: Optional[int] = Query(None),
    severity: Optional[IncidentSeverityEnum] = Query(None),
    status_filter: Optional[IncidentStatusEnum] = Query(None),
    db: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles([SUPER_ADMIN, SCHOOL_ADMIN, TEACHER, STAFF, PSYCHOLOGIST])),
):
    return await DisciplineService.list_incidents(
        db=db,
        org_id=principal.org_id,
        student_id=student_id,
        severity=severity,
        status_filter=status_filter,
    )


@router.get("/incidents/{incident_id}", response_model=IncidentRead)
async def get_incident(
    incident_id: int,
    db: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles([SUPER_ADMIN, SCHOOL_ADMIN, TEACHER, STAFF, PSYCHOLOGIST])),
):
    return await DisciplineService.get_incident(db=db, incident_id=incident_id, org_id=principal.org_id)


@router.patch("/incidents/{incident_id}", response_model=IncidentRead)
async def update_incident(
    incident_id: int,
    payload: IncidentUpdate,
    db: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles([SUPER_ADMIN, SCHOOL_ADMIN, TEACHER, STAFF, PSYCHOLOGIST])),
):
    return await DisciplineService.update_incident(
        db=db, incident_id=incident_id, payload=payload, org_id=principal.org_id
    )


@router.post("/suspensions", response_model=SuspensionRead, status_code=status.HTTP_201_CREATED)
async def create_suspension(
    payload: SuspensionCreate,
    db: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles([SUPER_ADMIN, SCHOOL_ADMIN])),
):
    user_id = principal.raw_claims.get("lh_user_id", 0)
    return await DisciplineService.create_suspension(
        db=db,
        payload=payload,
        authorized_by_id=user_id,
        org_id=principal.org_id,
    )
