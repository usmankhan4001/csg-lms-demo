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
