import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_discipline import IncidentSeverityEnum, IncidentStatusEnum
from src.schemas.sms_discipline import IncidentCreate, IncidentUpdate, SuspensionCreate
from src.services.sms.discipline import DisciplineService


@pytest.mark.asyncio
async def test_discipline_incident_lifecycle(db: AsyncSession):
    # 1. Create incident
    payload = IncidentCreate(
        student_id=101,
        incident_date="2026-09-14",
        title="Classroom Disturbance",
        description="Repeated disruptive talking during physics lab.",
        location="Physics Lab 1",
        severity=IncidentSeverityEnum.MINOR,
        notes="First verbal warning given",
    )
    incident = await DisciplineService.create_incident(
        db=db,
        payload=payload,
        reporter_id=10,
        org_id=1,
        campus_id=1,
    )
    assert incident.id is not None
    assert incident.student_id == 101
    assert incident.severity == IncidentSeverityEnum.MINOR
    assert incident.status == IncidentStatusEnum.OPEN

    # 2. List incidents
    incidents = await DisciplineService.list_incidents(
        db=db,
        org_id=1,
        student_id=101,
    )
    assert len(incidents) >= 1
    assert incidents[0].title == "Classroom Disturbance"

    # 3. Update incident (Notify parent)
    updated = await DisciplineService.update_incident(
        db=db,
        incident_id=incident.id,
        payload=IncidentUpdate(
            severity=IncidentSeverityEnum.MODERATE,
            parent_notified=True,
            action_taken="1-Hour Detention",
        ),
        org_id=1,
    )
    assert updated.severity == IncidentSeverityEnum.MODERATE
    assert updated.parent_notified is True
    assert updated.parent_notified_at is not None

    # 4. Suspension authorization
    suspension = await DisciplineService.create_suspension(
        db=db,
        payload=SuspensionCreate(
            incident_id=incident.id,
            student_id=101,
            start_date="2026-09-15",
            end_date="2026-09-17",
            is_in_school=True,
            reinstatement_conditions="Parent meeting required",
        ),
        authorized_by_id=1,
        org_id=1,
    )
    assert suspension.id is not None
    assert suspension.is_in_school is True
    assert suspension.student_id == 101


@pytest.mark.asyncio
async def test_another_schools_incident_is_not_found_never_forbidden(db: AsyncSession):
    """A cross-tenant read must be indistinguishable from a missing record.

    This previously answered 404 for "no such incident" and 403 "Access denied"
    for "belongs to another school". That difference is an existence oracle:
    an authenticated user at school A could walk incident ids and learn which
    ones exist at school B -- and therefore roughly how many behaviour
    incidents another school has recorded -- without ever reading one.

    The body was never disclosed. The EXISTENCE was, and for a child's
    discipline record that is the disclosure that matters.
    """
    from fastapi import HTTPException

    owned = await DisciplineService.create_incident(
        db=db,
        payload=IncidentCreate(
            student_id=777,
            incident_date="2026-09-15",
            title="Corridor incident",
            description="Running in the corridor.",
            severity=IncidentSeverityEnum.MINOR,
        ),
        reporter_id=1,
        org_id=1,
        campus_id=None,
    )

    # Same id, different tenant.
    with pytest.raises(HTTPException) as cross_tenant:
        await DisciplineService.get_incident(db=db, incident_id=owned.id, org_id=2)

    # An id that exists nowhere.
    with pytest.raises(HTTPException) as absent:
        await DisciplineService.get_incident(db=db, incident_id=999_999, org_id=2)

    assert cross_tenant.value.status_code == 404
    assert absent.value.status_code == 404
    # Identical detail too: a differing message leaks what the status hides.
    assert cross_tenant.value.detail == absent.value.detail

    # And the owning school still reads it normally.
    mine = await DisciplineService.get_incident(db=db, incident_id=owned.id, org_id=1)
    assert mine.id == owned.id
