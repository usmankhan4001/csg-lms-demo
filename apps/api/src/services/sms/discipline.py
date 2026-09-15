from datetime import datetime
from typing import List, Optional
from fastapi import HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_discipline import (
    DisciplinaryIncident,
    IncidentSeverityEnum,
    IncidentStatusEnum,
    SuspensionRecord,
)
from src.schemas.sms_discipline import (
    IncidentCreate,
    IncidentUpdate,
    SuspensionCreate,
)


class DisciplineService:
    @staticmethod
    async def create_incident(
        db: AsyncSession,
        payload: IncidentCreate,
        reporter_id: int,
        org_id: Optional[int],
        campus_id: Optional[int],
    ) -> DisciplinaryIncident:
        incident = DisciplinaryIncident(
            org_id=org_id,
            campus_id=campus_id,
            student_id=payload.student_id,
            reporter_id=reporter_id,
            incident_date=payload.incident_date,
            title=payload.title,
            description=payload.description,
            location=payload.location,
            severity=payload.severity,
            action_taken=payload.action_taken,
            notes=payload.notes,
            status=IncidentStatusEnum.OPEN,
        )
        db.add(incident)
        await db.commit()
        await db.refresh(incident)
        return incident

    @staticmethod
    async def list_incidents(
        db: AsyncSession,
        org_id: Optional[int],
        student_id: Optional[int] = None,
        severity: Optional[IncidentSeverityEnum] = None,
        status_filter: Optional[IncidentStatusEnum] = None,
    ) -> List[DisciplinaryIncident]:
        query = select(DisciplinaryIncident)
        if org_id is not None:
            query = query.where(DisciplinaryIncident.org_id == org_id)
        if student_id is not None:
            query = query.where(DisciplinaryIncident.student_id == student_id)
        if severity is not None:
            query = query.where(DisciplinaryIncident.severity == severity)
        if status_filter is not None:
            query = query.where(DisciplinaryIncident.status == status_filter)

        query = query.order_by(DisciplinaryIncident.incident_date.desc())
        result = await db.exec(query)
        return list(result.all())

    @staticmethod
    async def get_incident(
        db: AsyncSession,
        incident_id: int,
        org_id: Optional[int],
    ) -> DisciplinaryIncident:
        incident = await db.get(DisciplinaryIncident, incident_id)
        # ONE answer for "no such incident" and "not this school's incident".
        #
        # This previously returned 404 for the first and 403 "Access denied"
        # for the second, which is a cross-tenant existence oracle: walking ids
        # and reading the status code tells an authenticated user of school A
        # exactly which incident ids exist at school B, and by counting them,
        # roughly how many behaviour incidents another school has recorded.
        # The incident body was never disclosed, but its existence was, and
        # that is the disclosure that matters for a child's discipline record.
        #
        # Not a hypothetical shape here: 18 silent `org_id or 1` tenant
        # defaults were removed from this codebase in the same phase.
        if not incident or (org_id and incident.org_id != org_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Disciplinary incident not found",
            )
        return incident

    @staticmethod
    async def update_incident(
        db: AsyncSession,
        incident_id: int,
        payload: IncidentUpdate,
        org_id: Optional[int],
    ) -> DisciplinaryIncident:
        incident = await DisciplineService.get_incident(db, incident_id, org_id)
        update_data = payload.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(incident, key, value)
        if payload.parent_notified and not incident.parent_notified_at:
            incident.parent_notified_at = datetime.utcnow()
        incident.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(incident)
        return incident

    @staticmethod
    async def create_suspension(
        db: AsyncSession,
        payload: SuspensionCreate,
        authorized_by_id: int,
        org_id: Optional[int],
    ) -> SuspensionRecord:
        incident = await DisciplineService.get_incident(db, payload.incident_id, org_id)
        suspension = SuspensionRecord(
            org_id=org_id,
            incident_id=incident.id,
            student_id=payload.student_id,
            authorized_by_id=authorized_by_id,
            start_date=payload.start_date,
            end_date=payload.end_date,
            is_in_school=payload.is_in_school,
            academic_work_provided=payload.academic_work_provided,
            reinstatement_conditions=payload.reinstatement_conditions,
        )
        db.add(suspension)
        incident.action_taken = f"Suspension ({payload.start_date} to {payload.end_date})"
        incident.status = IncidentStatusEnum.RESOLVED
        await db.commit()
        await db.refresh(suspension)
        return suspension
