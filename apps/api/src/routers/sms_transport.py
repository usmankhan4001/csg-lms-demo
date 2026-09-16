"""
Transport Fleet & Routes (Domain 4) HTTP layer.

Gating:
  * writes  -- SUPER_ADMIN / SCHOOL_ADMIN / STAFF
  * reads   -- SUPER_ADMIN / SCHOOL_ADMIN / STAFF
  * one's own assignment -- `_require_own_student_or_privileged` below, so a
    parent or a student reaches only their own record and staff still reach
    everything. It answers 404, not 403: this is the endpoint a parent opens
    for their own child, so the only reason to call it with somebody else's id
    is probing, and a 403 would confirm that child has a transport record.

Tenancy: `require_org_id` refuses a principal with no organisation rather than
falling back to org 1, and `resolve_scoped_campus_id` pins a campus-bound
caller to their own campus. Writes additionally call `assert_campus_allowed`
so naming another campus fails loudly instead of silently landing elsewhere.

No feature-flag dependency is mounted here: unlike sms_hostel/sms_inventory
there is no `sms_transport` entry on AdminToggles, and adding one would mean
editing src/db/organization_config.py.
"""

from typing import Callable, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.events.database import get_db_session
from src.core.keycloak_auth import (
    SCHOOL_ADMIN,
    KeycloakUserPrincipal,
    get_current_user_principal,
    require_roles,
)
from src.db.sms_transport import VehicleTypeEnum
from src.schemas.sms.transport import (
    StudentTransportAssignmentCreate,
    StudentTransportAssignmentEnd,
    StudentTransportAssignmentRead,
    TransportRouteCreate,
    TransportRouteRead,
    TransportRouteStopCreate,
    TransportRouteStopRead,
    TransportRouteStopUpdate,
    TransportRouteUpdate,
    TransportVehicleCreate,
    TransportVehicleRead,
    TransportVehicleUpdate,
)
from src.security.school_ownership import (
    assert_campus_allowed,
    get_own_children_ids,
    get_user_id,
    require_org_id,
    resolve_scoped_campus_id,
)
from src.services.sms import transport as transport_service

_TRANSPORT_STAFF = ["SUPER_ADMIN", "SCHOOL_ADMIN", "STAFF"]

router = APIRouter()


def _require_own_student_or_privileged(
    student_id_param: str = "student_id",
) -> Callable[..., "KeycloakUserPrincipal"]:
    """Ownership gate for the parent/student read path, answering 404.

    Same test as `security.school_ownership.require_own_student_or_privileged`
    -- the student themselves, a guardian on StudentGuardian, SCHOOL_ADMIN, or
    SUPER_ADMIN -- but it refuses with 404 instead of 403.

    The distinction matters here specifically: this is the endpoint a parent
    opens for their own child, so the only people who should ever be calling it
    with somebody else's id are probing. A 403 confirms that student 77 exists
    and has a transport record; a 404 does not. School staff who legitimately
    need any student's bus use `GET /assignments?student_id=`, which is
    role-gated and campus-scoped instead.
    """

    async def _checker(
        request: Request,
        principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
        session: AsyncSession = Depends(get_db_session),
    ) -> KeycloakUserPrincipal:
        if principal.is_superadmin or principal.has_role(SCHOOL_ADMIN):
            return principal

        raw = request.path_params.get(student_id_param) or request.query_params.get(student_id_param)
        if raw is None:
            return principal
        try:
            target_student_id = int(raw)
        except (ValueError, TypeError):
            return principal

        user_id = get_user_id(principal)
        if user_id is not None:
            if target_student_id == user_id:  # the student reading their own record
                return principal
            if target_student_id in await get_own_children_ids(user_id, session):
                return principal

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transport assignment not found.",
        )

    return _checker


# ── Vehicles ──

@router.post(
    "/vehicles",
    response_model=TransportVehicleRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create Transport Vehicle",
)
async def create_vehicle_endpoint(
    payload: TransportVehicleCreate,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_TRANSPORT_STAFF)),
) -> TransportVehicleRead:
    assert_campus_allowed(principal, payload.campus_id)
    vehicle = await transport_service.create_vehicle(
        session=session,
        payload=payload,
        org_id=require_org_id(principal),
        campus_id=resolve_scoped_campus_id(principal, payload.campus_id),
    )
    return TransportVehicleRead.model_validate(vehicle)


@router.get(
    "/vehicles",
    response_model=List[TransportVehicleRead],
    summary="List Transport Vehicles",
)
async def list_vehicles_endpoint(
    campus_id: Optional[int] = None,
    vehicle_type: Optional[VehicleTypeEnum] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_TRANSPORT_STAFF)),
) -> List[TransportVehicleRead]:
    vehicles = await transport_service.list_vehicles(
        session=session,
        org_id=require_org_id(principal),
        campus_id=resolve_scoped_campus_id(principal, campus_id),
        vehicle_type=vehicle_type,
        is_active=is_active,
        search=search,
        limit=limit,
        offset=offset,
    )
    return [TransportVehicleRead.model_validate(v) for v in vehicles]


@router.get(
    "/vehicles/{vehicle_id}",
    response_model=TransportVehicleRead,
    summary="Get Transport Vehicle",
)
async def get_vehicle_endpoint(
    vehicle_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_TRANSPORT_STAFF)),
) -> TransportVehicleRead:
    vehicle = await transport_service.get_vehicle(session, vehicle_id, org_id=require_org_id(principal))
    assert_campus_allowed(principal, vehicle.campus_id)
    return TransportVehicleRead.model_validate(vehicle)


@router.patch(
    "/vehicles/{vehicle_id}",
    response_model=TransportVehicleRead,
    summary="Update Transport Vehicle",
)
async def update_vehicle_endpoint(
    vehicle_id: int,
    payload: TransportVehicleUpdate,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_TRANSPORT_STAFF)),
) -> TransportVehicleRead:
    org_id = require_org_id(principal)
    existing = await transport_service.get_vehicle(session, vehicle_id, org_id=org_id)
    assert_campus_allowed(principal, existing.campus_id)
    if payload.campus_id is not None:
        assert_campus_allowed(principal, payload.campus_id)
    vehicle = await transport_service.update_vehicle(session, vehicle_id, payload, org_id=org_id)
    return TransportVehicleRead.model_validate(vehicle)


@router.delete(
    "/vehicles/{vehicle_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Transport Vehicle",
)
async def delete_vehicle_endpoint(
    vehicle_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_TRANSPORT_STAFF)),
) -> None:
    org_id = require_org_id(principal)
    existing = await transport_service.get_vehicle(session, vehicle_id, org_id=org_id)
    assert_campus_allowed(principal, existing.campus_id)
    await transport_service.delete_vehicle(session, vehicle_id, org_id=org_id)


# ── Routes ──

@router.post(
    "/routes",
    response_model=TransportRouteRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create Transport Route",
)
async def create_route_endpoint(
    payload: TransportRouteCreate,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_TRANSPORT_STAFF)),
) -> TransportRouteRead:
    assert_campus_allowed(principal, payload.campus_id)
    route = await transport_service.create_route(
        session=session,
        payload=payload,
        org_id=require_org_id(principal),
        campus_id=resolve_scoped_campus_id(principal, payload.campus_id),
    )
    return await _route_read(session, route)


@router.get(
    "/routes",
    response_model=List[TransportRouteRead],
    summary="List Transport Routes",
)
async def list_routes_endpoint(
    campus_id: Optional[int] = None,
    vehicle_id: Optional[int] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_TRANSPORT_STAFF)),
) -> List[TransportRouteRead]:
    routes = await transport_service.list_routes(
        session=session,
        org_id=require_org_id(principal),
        campus_id=resolve_scoped_campus_id(principal, campus_id),
        vehicle_id=vehicle_id,
        is_active=is_active,
        search=search,
        limit=limit,
        offset=offset,
    )
    return [await _route_read(session, r) for r in routes]


@router.get(
    "/routes/{route_id}",
    response_model=TransportRouteRead,
    summary="Get Transport Route",
)
async def get_route_endpoint(
    route_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_TRANSPORT_STAFF)),
) -> TransportRouteRead:
    route = await transport_service.get_route(session, route_id, org_id=require_org_id(principal))
    assert_campus_allowed(principal, route.campus_id)
    return await _route_read(session, route)


@router.patch(
    "/routes/{route_id}",
    response_model=TransportRouteRead,
    summary="Update Transport Route",
)
async def update_route_endpoint(
    route_id: int,
    payload: TransportRouteUpdate,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_TRANSPORT_STAFF)),
) -> TransportRouteRead:
    org_id = require_org_id(principal)
    existing = await transport_service.get_route(session, route_id, org_id=org_id)
    assert_campus_allowed(principal, existing.campus_id)
    if payload.campus_id is not None:
        assert_campus_allowed(principal, payload.campus_id)
    route = await transport_service.update_route(session, route_id, payload, org_id=org_id)
    return await _route_read(session, route)


@router.delete(
    "/routes/{route_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Transport Route",
)
async def delete_route_endpoint(
    route_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_TRANSPORT_STAFF)),
) -> None:
    org_id = require_org_id(principal)
    existing = await transport_service.get_route(session, route_id, org_id=org_id)
    assert_campus_allowed(principal, existing.campus_id)
    await transport_service.delete_route(session, route_id, org_id=org_id)


async def _route_read(session: AsyncSession, route) -> TransportRouteRead:
    """Route plus its vehicle's plate.

    `vehicle_registration_no` stays None when the route has no vehicle, rather
    than being filled with a placeholder: no vehicle is not the same as a
    vehicle with no plate.
    """
    read = TransportRouteRead.model_validate(route)
    if route.vehicle_id is not None:
        vehicle = await session.get(transport_service.TransportVehicle, route.vehicle_id)
        read.vehicle_registration_no = vehicle.registration_no if vehicle else None
    return read


# ── Route Stops ──

@router.post(
    "/stops",
    response_model=TransportRouteStopRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create Route Stop",
)
async def create_stop_endpoint(
    payload: TransportRouteStopCreate,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_TRANSPORT_STAFF)),
) -> TransportRouteStopRead:
    org_id = require_org_id(principal)
    route = await transport_service.get_route(session, payload.route_id, org_id=org_id)
    assert_campus_allowed(principal, route.campus_id)
    stop = await transport_service.create_stop(
        session=session,
        payload=payload,
        org_id=org_id,
        campus_id=resolve_scoped_campus_id(principal, route.campus_id),
    )
    return await _stop_read(session, stop)


@router.get(
    "/stops",
    response_model=List[TransportRouteStopRead],
    summary="List Route Stops",
)
async def list_stops_endpoint(
    campus_id: Optional[int] = None,
    route_id: Optional[int] = None,
    is_active: Optional[bool] = None,
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_TRANSPORT_STAFF)),
) -> List[TransportRouteStopRead]:
    stops = await transport_service.list_stops(
        session=session,
        org_id=require_org_id(principal),
        campus_id=resolve_scoped_campus_id(principal, campus_id),
        route_id=route_id,
        is_active=is_active,
        limit=limit,
        offset=offset,
    )
    return [await _stop_read(session, s) for s in stops]


@router.get(
    "/stops/{stop_id}",
    response_model=TransportRouteStopRead,
    summary="Get Route Stop",
)
async def get_stop_endpoint(
    stop_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_TRANSPORT_STAFF)),
) -> TransportRouteStopRead:
    stop = await transport_service.get_stop(session, stop_id, org_id=require_org_id(principal))
    assert_campus_allowed(principal, stop.campus_id)
    return await _stop_read(session, stop)


@router.patch(
    "/stops/{stop_id}",
    response_model=TransportRouteStopRead,
    summary="Update Route Stop",
)
async def update_stop_endpoint(
    stop_id: int,
    payload: TransportRouteStopUpdate,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_TRANSPORT_STAFF)),
) -> TransportRouteStopRead:
    org_id = require_org_id(principal)
    existing = await transport_service.get_stop(session, stop_id, org_id=org_id)
    assert_campus_allowed(principal, existing.campus_id)
    stop = await transport_service.update_stop(session, stop_id, payload, org_id=org_id)
    return await _stop_read(session, stop)


@router.delete(
    "/stops/{stop_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Route Stop",
)
async def delete_stop_endpoint(
    stop_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_TRANSPORT_STAFF)),
) -> None:
    org_id = require_org_id(principal)
    existing = await transport_service.get_stop(session, stop_id, org_id=org_id)
    assert_campus_allowed(principal, existing.campus_id)
    await transport_service.delete_stop(session, stop_id, org_id=org_id)


async def _stop_read(session: AsyncSession, stop) -> TransportRouteStopRead:
    read = TransportRouteStopRead.model_validate(stop)
    route = await session.get(transport_service.TransportRoute, stop.route_id)
    read.route_name = route.name if route else None
    return read


# ── Student Assignments ──

@router.post(
    "/assignments",
    response_model=StudentTransportAssignmentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Assign Student to a Route",
)
async def assign_student_endpoint(
    payload: StudentTransportAssignmentCreate,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_TRANSPORT_STAFF)),
) -> StudentTransportAssignmentRead:
    org_id = require_org_id(principal)
    route = await transport_service.get_route(session, payload.route_id, org_id=org_id)
    assert_campus_allowed(principal, route.campus_id)
    assignment = await transport_service.assign_student(
        session=session,
        payload=payload,
        org_id=org_id,
        campus_id=resolve_scoped_campus_id(principal, route.campus_id),
        # Who recorded it comes from the authenticated principal, never the body.
        assigned_by_user_id=get_user_id(principal),
    )
    return await _assignment_read(session, assignment)


@router.get(
    "/assignments/student/{student_id}",
    response_model=List[StudentTransportAssignmentRead],
    summary="List One Student's Transport Assignments",
    description=(
        "Reachable by the student themselves, by their guardian via "
        "StudentGuardian, and by SCHOOL_ADMIN/SUPER_ADMIN. Anyone else gets "
        "404, so that probing ids reveals nothing about other families' children."
    ),
)
async def list_student_assignments_endpoint(
    student_id: int,
    is_active: Optional[bool] = None,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(_require_own_student_or_privileged()),
) -> List[StudentTransportAssignmentRead]:
    assignments = await transport_service.list_assignments(
        session=session,
        org_id=require_org_id(principal),
        student_id=student_id,
        is_active=is_active,
    )
    return [await _assignment_read(session, a) for a in assignments]


@router.get(
    "/assignments",
    response_model=List[StudentTransportAssignmentRead],
    summary="List Transport Assignments",
)
async def list_assignments_endpoint(
    campus_id: Optional[int] = None,
    route_id: Optional[int] = None,
    student_id: Optional[int] = None,
    is_active: Optional[bool] = None,
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_TRANSPORT_STAFF)),
) -> List[StudentTransportAssignmentRead]:
    assignments = await transport_service.list_assignments(
        session=session,
        org_id=require_org_id(principal),
        campus_id=resolve_scoped_campus_id(principal, campus_id),
        route_id=route_id,
        student_id=student_id,
        is_active=is_active,
        limit=limit,
        offset=offset,
    )
    return [await _assignment_read(session, a) for a in assignments]


@router.get(
    "/assignments/{assignment_id}",
    response_model=StudentTransportAssignmentRead,
    summary="Get Transport Assignment",
)
async def get_assignment_endpoint(
    assignment_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_TRANSPORT_STAFF)),
) -> StudentTransportAssignmentRead:
    assignment = await transport_service.get_assignment(
        session, assignment_id, org_id=require_org_id(principal)
    )
    assert_campus_allowed(principal, assignment.campus_id)
    return await _assignment_read(session, assignment)


@router.post(
    "/assignments/{assignment_id}/end",
    response_model=StudentTransportAssignmentRead,
    summary="End a Transport Assignment",
)
async def end_assignment_endpoint(
    assignment_id: int,
    payload: StudentTransportAssignmentEnd,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_TRANSPORT_STAFF)),
) -> StudentTransportAssignmentRead:
    org_id = require_org_id(principal)
    existing = await transport_service.get_assignment(session, assignment_id, org_id=org_id)
    assert_campus_allowed(principal, existing.campus_id)
    assignment = await transport_service.end_assignment(session, assignment_id, payload, org_id=org_id)
    return await _assignment_read(session, assignment)


async def _assignment_read(session: AsyncSession, assignment) -> StudentTransportAssignmentRead:
    read = StudentTransportAssignmentRead.model_validate(assignment)
    route = await session.get(transport_service.TransportRoute, assignment.route_id)
    read.route_name = route.name if route else None
    if assignment.stop_id is not None:
        stop = await session.get(transport_service.TransportRouteStop, assignment.stop_id)
        read.stop_name = stop.name if stop else None
    return read
