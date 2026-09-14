import logging
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
from src.services.notifications import resolve_guardians_of
from src.services.sms.discipline import DisciplineService
from src.services.sms.school_events import (
    DISCIPLINE_INCIDENT_RECORDED,
    DISCIPLINE_INCIDENT_SERIOUS,
    raise_school_event,
    student_display_name,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sms/discipline", tags=["sms-discipline"])

# Which incidents a family is told about without being able to switch it off.
# MAJOR and CRITICAL are the school's own severity words for "we need to talk
# to you", so they map to the unmutable safeguarding event; MINOR and MODERATE
# are a behaviour note and map to the routine one.
_SERIOUS_SEVERITIES = frozenset(
    {IncidentSeverityEnum.MAJOR, IncidentSeverityEnum.CRITICAL}
)


async def _announce_incident(
    session: AsyncSession,
    incident,
    principal: KeycloakUserPrincipal,
) -> None:
    """Tell a student's own guardians that an incident was recorded.

    CONFIDENTIALITY, and it is the whole reason this is a function rather than
    three lines at the call site:

      * Recipients come from THIS student's guardian links only. A school
        incident frequently involves several children; resolving recipients any
        other way (a section roster, everyone on the report) would tell one
        family about another's child.
      * `incident.description` and `incident.notes` are never sent. Those
        fields are written by staff for staff and routinely name other pupils
        ("pushed X in the corridor"). The message carries the title's subject
        matter only as far as date and severity, and the family signs in for
        the rest. The event's `required_context` deliberately omits them so
        this cannot be widened by editing a template.

    Never raises: the incident record is already committed and must stand.
    """
    student_id = getattr(incident, "student_id", None)
    if student_id is None:
        return

    try:
        guardians = await resolve_guardians_of(session, student_id)
    except Exception:
        logger.warning(
            "Could not resolve guardians for incident %s; it was recorded but "
            "the family was not told.",
            getattr(incident, "id", None),
            exc_info=True,
        )
        return

    if not guardians:
        logger.warning(
            "Incident %s recorded for student %s, who has no linked guardian, "
            "so nobody can be told.",
            getattr(incident, "id", None),
            student_id,
        )
        return

    severity = getattr(incident, "severity", None)
    is_serious = severity in _SERIOUS_SEVERITIES
    event = DISCIPLINE_INCIDENT_SERIOUS if is_serious else DISCIPLINE_INCIDENT_RECORDED

    context = {
        "student_name": await student_display_name(session, student_id),
        "incident_date": getattr(incident, "incident_date", None),
    }
    if is_serious:
        # Only the serious template names the severity; a parent reading
        # "minor" about a late mark learns nothing and it sounds dismissive.
        context["severity"] = (
            severity.value if hasattr(severity, "value") else str(severity)
        )

    await raise_school_event(
        session,
        event_key=event.key,
        org_id=principal.org_id,
        recipients=guardians,
        context=context,
        campus_id=principal.campus_id,
        related_kind="discipline_incident",
        related_id=getattr(incident, "id", None),
    )


@router.post("/incidents", response_model=IncidentRead, status_code=status.HTTP_201_CREATED)
async def create_incident(
    payload: IncidentCreate,
    db: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles([SUPER_ADMIN, SCHOOL_ADMIN, TEACHER, STAFF, PSYCHOLOGIST])),
):
    user_id = principal.raw_claims.get("lh_user_id", 0)
    incident = await DisciplineService.create_incident(
        db=db,
        payload=payload,
        reporter_id=user_id,
        org_id=principal.org_id,
        campus_id=principal.campus_id,
    )
    # The model has carried `parent_notified` / `parent_notified_at` columns
    # since it was written, and nothing has ever set them, because nothing ever
    # told a parent. This is the send that makes those fields meaningful.
    await _announce_incident(db, incident, principal)
    return incident


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
