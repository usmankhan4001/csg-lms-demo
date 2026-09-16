"""
Transport Fleet & Routes (Domain 4) service layer.

Every read and write is scoped by `org_id` (the tenant boundary) and, where
the caller is campus-bound, by `campus_id`. There is no Postgres RLS here, so
the scoping has to be in the query -- a row belonging to another organisation
is reported as 404 rather than 403, so its existence is not confirmed to a
caller who has no business knowing it is there.

No money is handled: transport is billed as a fee category by the fees module.
"""

import datetime
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy import func, or_
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_transport import (
    StudentTransportAssignment,
    TransportRoute,
    TransportRouteStop,
    TransportVehicle,
    VehicleTypeEnum,
)
from src.schemas.sms.transport import (
    StudentTransportAssignmentCreate,
    StudentTransportAssignmentEnd,
    TransportRouteCreate,
    TransportRouteStopCreate,
    TransportRouteStopUpdate,
    TransportRouteUpdate,
    TransportVehicleCreate,
    TransportVehicleUpdate,
)


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _assert_org(row: object, org_id: int, what: str) -> None:
    """Refuse a row belonging to another organisation.

    404, not 403: telling a caller the row exists but is not theirs leaks the
    other tenant's data.
    """
    if getattr(row, "org_id", None) != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{what} not found.")


# ── Vehicles ──

async def create_vehicle(
    session: AsyncSession,
    payload: TransportVehicleCreate,
    org_id: int,
    campus_id: Optional[int] = None,
) -> TransportVehicle:
    registration = payload.registration_no.strip().upper()
    existing = (
        await session.exec(
            select(TransportVehicle).where(
                TransportVehicle.org_id == org_id,
                TransportVehicle.registration_no == registration,
            )
        )
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A vehicle with registration '{registration}' already exists.",
        )

    vehicle = TransportVehicle(
        org_id=org_id,
        campus_id=campus_id,
        registration_no=registration,
        vehicle_type=payload.vehicle_type,
        capacity=payload.capacity,
        make=payload.make,
        model=payload.model,
        manufacture_year=payload.manufacture_year,
        insurance_expiry=payload.insurance_expiry,
        road_tax_expiry=payload.road_tax_expiry,
        driver_user_id=payload.driver_user_id,
        driver_name=payload.driver_name,
        driver_contact=payload.driver_contact,
        notes=payload.notes,
        is_active=True,
    )
    session.add(vehicle)
    await session.commit()
    await session.refresh(vehicle)
    return vehicle


async def get_vehicle(session: AsyncSession, vehicle_id: int, org_id: int) -> TransportVehicle:
    vehicle = await session.get(TransportVehicle, vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found.")
    _assert_org(vehicle, org_id, "Vehicle")
    return vehicle


async def list_vehicles(
    session: AsyncSession,
    org_id: int,
    campus_id: Optional[int] = None,
    vehicle_type: Optional[VehicleTypeEnum] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[TransportVehicle]:
    query = select(TransportVehicle).where(TransportVehicle.org_id == org_id)
    if campus_id is not None:
        query = query.where(TransportVehicle.campus_id == campus_id)
    if vehicle_type is not None:
        query = query.where(TransportVehicle.vehicle_type == vehicle_type)
    if is_active is not None:
        query = query.where(TransportVehicle.is_active == is_active)
    if search:
        pattern = f"%{search}%"
        query = query.where(
            or_(
                TransportVehicle.registration_no.ilike(pattern),
                TransportVehicle.make.ilike(pattern),
                TransportVehicle.model.ilike(pattern),
                TransportVehicle.driver_name.ilike(pattern),
            )
        )
    query = query.order_by(TransportVehicle.registration_no).offset(offset).limit(limit)
    return (await session.exec(query)).all()


async def update_vehicle(
    session: AsyncSession,
    vehicle_id: int,
    payload: TransportVehicleUpdate,
    org_id: int,
) -> TransportVehicle:
    vehicle = await get_vehicle(session, vehicle_id, org_id)

    update_data = payload.model_dump(exclude_unset=True)
    if "registration_no" in update_data and update_data["registration_no"] is not None:
        update_data["registration_no"] = update_data["registration_no"].strip().upper()

    for key, value in update_data.items():
        setattr(vehicle, key, value)

    vehicle.updated_at = _utcnow()
    session.add(vehicle)
    await session.commit()
    await session.refresh(vehicle)
    return vehicle


async def delete_vehicle(session: AsyncSession, vehicle_id: int, org_id: int) -> None:
    vehicle = await get_vehicle(session, vehicle_id, org_id)

    assigned_route = (
        await session.exec(
            select(TransportRoute).where(
                TransportRoute.vehicle_id == vehicle_id,
                TransportRoute.is_active == True,  # noqa: E712
            )
        )
    ).first()
    if assigned_route:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Vehicle is still assigned to active route '{assigned_route.name}'. Reassign the route first.",
        )

    await session.delete(vehicle)
    await session.commit()


# ── Routes ──

async def create_route(
    session: AsyncSession,
    payload: TransportRouteCreate,
    org_id: int,
    campus_id: Optional[int] = None,
) -> TransportRoute:
    code = payload.code.strip().upper()
    existing = (
        await session.exec(
            select(TransportRoute).where(TransportRoute.org_id == org_id, TransportRoute.code == code)
        )
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A route with code '{code}' already exists.",
        )

    if payload.vehicle_id is not None:
        # A vehicle from another org must not be attachable by id alone.
        await get_vehicle(session, payload.vehicle_id, org_id)

    route = TransportRoute(
        org_id=org_id,
        campus_id=campus_id,
        name=payload.name.strip(),
        code=code,
        direction=payload.direction,
        vehicle_id=payload.vehicle_id,
        description=payload.description,
        is_active=True,
    )
    session.add(route)
    await session.commit()
    await session.refresh(route)
    return route


async def get_route(session: AsyncSession, route_id: int, org_id: int) -> TransportRoute:
    route = await session.get(TransportRoute, route_id)
    if not route:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Route not found.")
    _assert_org(route, org_id, "Route")
    return route


async def list_routes(
    session: AsyncSession,
    org_id: int,
    campus_id: Optional[int] = None,
    vehicle_id: Optional[int] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[TransportRoute]:
    query = select(TransportRoute).where(TransportRoute.org_id == org_id)
    if campus_id is not None:
        query = query.where(TransportRoute.campus_id == campus_id)
    if vehicle_id is not None:
        query = query.where(TransportRoute.vehicle_id == vehicle_id)
    if is_active is not None:
        query = query.where(TransportRoute.is_active == is_active)
    if search:
        pattern = f"%{search}%"
        query = query.where(or_(TransportRoute.name.ilike(pattern), TransportRoute.code.ilike(pattern)))
    query = query.order_by(TransportRoute.name).offset(offset).limit(limit)
    return (await session.exec(query)).all()


async def update_route(
    session: AsyncSession,
    route_id: int,
    payload: TransportRouteUpdate,
    org_id: int,
) -> TransportRoute:
    route = await get_route(session, route_id, org_id)

    update_data = payload.model_dump(exclude_unset=True)
    if update_data.get("code") is not None:
        update_data["code"] = update_data["code"].strip().upper()
    if update_data.get("vehicle_id") is not None:
        await get_vehicle(session, update_data["vehicle_id"], org_id)

    for key, value in update_data.items():
        setattr(route, key, value)

    route.updated_at = _utcnow()
    session.add(route)
    await session.commit()
    await session.refresh(route)
    return route


async def delete_route(session: AsyncSession, route_id: int, org_id: int) -> None:
    route = await get_route(session, route_id, org_id)

    active_assignment = (
        await session.exec(
            select(StudentTransportAssignment).where(
                StudentTransportAssignment.route_id == route_id,
                StudentTransportAssignment.is_active == True,  # noqa: E712
            )
        )
    ).first()
    if active_assignment:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Route still has students assigned. End every assignment before deleting it.",
        )

    await session.delete(route)
    await session.commit()


# ── Route Stops ──

async def create_stop(
    session: AsyncSession,
    payload: TransportRouteStopCreate,
    org_id: int,
    campus_id: Optional[int] = None,
) -> TransportRouteStop:
    route = await get_route(session, payload.route_id, org_id)

    if payload.sequence_no is not None:
        sequence_no = payload.sequence_no
    else:
        last = (
            await session.execute(
                select(func.max(TransportRouteStop.sequence_no)).where(
                    TransportRouteStop.route_id == route.id
                )
            )
        ).scalars().first()
        sequence_no = (last or 0) + 1

    stop = TransportRouteStop(
        org_id=org_id,
        campus_id=campus_id if campus_id is not None else route.campus_id,
        route_id=route.id,
        name=payload.name.strip(),
        sequence_no=sequence_no,
        pickup_time=payload.pickup_time,
        drop_time=payload.drop_time,
        address=payload.address,
        latitude=payload.latitude,
        longitude=payload.longitude,
        notes=payload.notes,
        is_active=True,
    )
    session.add(stop)
    await session.commit()
    await session.refresh(stop)
    return stop


async def get_stop(session: AsyncSession, stop_id: int, org_id: int) -> TransportRouteStop:
    stop = await session.get(TransportRouteStop, stop_id)
    if not stop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Route stop not found.")
    _assert_org(stop, org_id, "Route stop")
    return stop


async def list_stops(
    session: AsyncSession,
    org_id: int,
    campus_id: Optional[int] = None,
    route_id: Optional[int] = None,
    is_active: Optional[bool] = None,
    limit: int = 200,
    offset: int = 0,
) -> List[TransportRouteStop]:
    query = select(TransportRouteStop).where(TransportRouteStop.org_id == org_id)
    if campus_id is not None:
        query = query.where(TransportRouteStop.campus_id == campus_id)
    if route_id is not None:
        query = query.where(TransportRouteStop.route_id == route_id)
    if is_active is not None:
        query = query.where(TransportRouteStop.is_active == is_active)
    query = query.order_by(TransportRouteStop.route_id, TransportRouteStop.sequence_no).offset(offset).limit(limit)
    return (await session.exec(query)).all()


async def update_stop(
    session: AsyncSession,
    stop_id: int,
    payload: TransportRouteStopUpdate,
    org_id: int,
) -> TransportRouteStop:
    stop = await get_stop(session, stop_id, org_id)

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(stop, key, value)

    stop.updated_at = _utcnow()
    session.add(stop)
    await session.commit()
    await session.refresh(stop)
    return stop


async def delete_stop(session: AsyncSession, stop_id: int, org_id: int) -> None:
    stop = await get_stop(session, stop_id, org_id)

    using_it = (
        await session.exec(
            select(StudentTransportAssignment).where(
                StudentTransportAssignment.stop_id == stop_id,
                StudentTransportAssignment.is_active == True,  # noqa: E712
            )
        )
    ).first()
    if using_it:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Students are still assigned to this stop. Reassign them before deleting it.",
        )

    await session.delete(stop)
    await session.commit()


# ── Student Assignments ──

async def assign_student(
    session: AsyncSession,
    payload: StudentTransportAssignmentCreate,
    org_id: int,
    campus_id: Optional[int] = None,
    assigned_by_user_id: Optional[int] = None,
) -> StudentTransportAssignment:
    route = await get_route(session, payload.route_id, org_id)
    if not route.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Route is not active.")

    if payload.stop_id is not None:
        stop = await get_stop(session, payload.stop_id, org_id)
        if stop.route_id != route.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Stop '{stop.name}' does not belong to route '{route.name}'.",
            )

    duplicate = (
        await session.exec(
            select(StudentTransportAssignment).where(
                StudentTransportAssignment.student_id == payload.student_id,
                StudentTransportAssignment.is_active == True,  # noqa: E712
            )
        )
    ).first()
    if duplicate:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Student ID {payload.student_id} already has an active transport assignment (ID {duplicate.id}).",
        )

    # Capacity guard. This is a READ-THEN-WRITE check: the count below and the
    # insert at the end of this function are two statements on one session, not
    # one atomic statement, so two concurrent assignments can both read the same
    # seat count and both succeed -- overfilling the bus by one. Closing that
    # properly needs either SELECT ... FOR UPDATE on the route row or a
    # serializable transaction; neither is in place, and a real overfill is
    # caught by the driver's headcount, not by this check. It is a guard against
    # the ordinary mistake (assigning past capacity in the office), not a
    # concurrency guarantee.
    if route.vehicle_id is not None:
        vehicle = await get_vehicle(session, route.vehicle_id, org_id)
        if vehicle.capacity > 0:
            seated = (
                await session.execute(
                    select(func.count(StudentTransportAssignment.id)).where(
                        StudentTransportAssignment.route_id == route.id,
                        StudentTransportAssignment.is_active == True,  # noqa: E712
                    )
                )
            ).scalar_one()
            if seated >= vehicle.capacity:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Route '{route.name}' is full: {seated}/{vehicle.capacity} seats taken "
                        f"on vehicle {vehicle.registration_no}."
                    ),
                )

    assignment = StudentTransportAssignment(
        org_id=org_id,
        campus_id=campus_id if campus_id is not None else route.campus_id,
        student_id=payload.student_id,
        route_id=route.id,
        stop_id=payload.stop_id,
        is_active=True,
        effective_from=payload.effective_from,
        effective_to=payload.effective_to,
        assigned_by_user_id=assigned_by_user_id,
        notes=payload.notes,
    )
    session.add(assignment)
    await session.commit()
    await session.refresh(assignment)
    return assignment


async def get_assignment(
    session: AsyncSession, assignment_id: int, org_id: int
) -> StudentTransportAssignment:
    assignment = await session.get(StudentTransportAssignment, assignment_id)
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transport assignment not found.")
    _assert_org(assignment, org_id, "Transport assignment")
    return assignment


async def list_assignments(
    session: AsyncSession,
    org_id: int,
    campus_id: Optional[int] = None,
    route_id: Optional[int] = None,
    student_id: Optional[int] = None,
    is_active: Optional[bool] = None,
    limit: int = 200,
    offset: int = 0,
) -> List[StudentTransportAssignment]:
    query = select(StudentTransportAssignment).where(StudentTransportAssignment.org_id == org_id)
    if campus_id is not None:
        query = query.where(StudentTransportAssignment.campus_id == campus_id)
    if route_id is not None:
        query = query.where(StudentTransportAssignment.route_id == route_id)
    if student_id is not None:
        query = query.where(StudentTransportAssignment.student_id == student_id)
    if is_active is not None:
        query = query.where(StudentTransportAssignment.is_active == is_active)
    query = query.order_by(StudentTransportAssignment.id.desc()).offset(offset).limit(limit)
    return (await session.exec(query)).all()


async def end_assignment(
    session: AsyncSession,
    assignment_id: int,
    payload: StudentTransportAssignmentEnd,
    org_id: int,
) -> StudentTransportAssignment:
    assignment = await get_assignment(session, assignment_id, org_id)
    if not assignment.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Transport assignment is already ended.",
        )

    assignment.is_active = False
    assignment.effective_to = payload.end_date
    if payload.notes:
        assignment.notes = payload.notes
    assignment.updated_at = _utcnow()

    session.add(assignment)
    await session.commit()
    await session.refresh(assignment)
    return assignment
