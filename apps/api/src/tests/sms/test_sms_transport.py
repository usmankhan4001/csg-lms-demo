import datetime

import pytest
from fastapi import HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_transport import RouteDirectionEnum, VehicleTypeEnum
from src.routers.sms_transport import (
    assign_student_endpoint,
    create_route_endpoint,
    create_stop_endpoint,
    create_vehicle_endpoint,
    delete_route_endpoint,
    delete_stop_endpoint,
    delete_vehicle_endpoint,
    end_assignment_endpoint,
    get_route_endpoint,
    get_stop_endpoint,
    get_vehicle_endpoint,
    list_assignments_endpoint,
    list_routes_endpoint,
    list_stops_endpoint,
    list_vehicles_endpoint,
    update_route_endpoint,
    update_stop_endpoint,
    update_vehicle_endpoint,
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
from src.tests.sms._principals import SUPERADMIN, principal

# A staff member of a DIFFERENT organisation (org 2), used for tenant isolation.
OTHER_ORG_STAFF = principal("STAFF", user_id=2, org_id=2, campus_id=2)

# A staff member pinned to campus 2 of the SAME org, used for campus isolation.
CAMPUS_TWO_STAFF = principal("STAFF", user_id=3, org_id=1, campus_id=2)


@pytest.mark.asyncio
async def test_vehicle_route_and_stop_crud(db: AsyncSession):
    """Create, read, update and delete the fleet/route/stop hierarchy."""
    # 1. Create a vehicle
    vehicle = await create_vehicle_endpoint(
        payload=TransportVehicleCreate(
            campus_id=1,
            registration_no="KA-01-AB-1234",
            vehicle_type=VehicleTypeEnum.BUS,
            capacity=40,
            make="Tata",
            model="Starbus",
            manufacture_year=2021,
            driver_name="Mr. Ramesh Kumar",
            driver_contact="+919900000001",
        ),
        session=db,
        principal=SUPERADMIN,
    )
    assert vehicle.id is not None
    assert vehicle.registration_no == "KA-01-AB-1234"
    assert vehicle.is_active is True

    # 2. Duplicate registration within the org is rejected
    with pytest.raises(HTTPException) as exc_info:
        await create_vehicle_endpoint(
            payload=TransportVehicleCreate(campus_id=1, registration_no="ka-01-ab-1234"),
            session=db,
            principal=SUPERADMIN,
        )
    assert exc_info.value.status_code == 400

    # 3. Read back / list
    fetched = await get_vehicle_endpoint(vehicle_id=vehicle.id, session=db, principal=SUPERADMIN)
    assert fetched.capacity == 40
    assert len(await list_vehicles_endpoint(session=db, principal=SUPERADMIN, limit=100, offset=0)) == 1

    # 4. Update
    updated = await update_vehicle_endpoint(
        vehicle_id=vehicle.id,
        payload=TransportVehicleUpdate(capacity=45, is_active=False),
        session=db,
        principal=SUPERADMIN,
    )
    assert updated.capacity == 45
    assert updated.is_active is False
    await update_vehicle_endpoint(
        vehicle_id=vehicle.id,
        payload=TransportVehicleUpdate(is_active=True),
        session=db,
        principal=SUPERADMIN,
    )

    # 5. Create a route on that vehicle
    route = await create_route_endpoint(
        payload=TransportRouteCreate(
            campus_id=1,
            name="North Loop",
            code="R-NORTH",
            vehicle_id=vehicle.id,
            description="Via Market Square and the bypass",
        ),
        session=db,
        principal=SUPERADMIN,
    )
    assert route.id is not None
    # The plate is joined on, not left blank.
    assert route.vehicle_registration_no == "KA-01-AB-1234"

    with pytest.raises(HTTPException) as exc_info:
        await create_route_endpoint(
            payload=TransportRouteCreate(campus_id=1, name="North Loop Duplicate", code="r-north"),
            session=db,
            principal=SUPERADMIN,
        )
    assert exc_info.value.status_code == 400

    # 6. Stops: sequence is assigned when omitted, in creation order
    stop1 = await create_stop_endpoint(
        payload=TransportRouteStopCreate(route_id=route.id, name="Market Square", pickup_time="07:15"),
        session=db,
        principal=SUPERADMIN,
    )
    stop2 = await create_stop_endpoint(
        payload=TransportRouteStopCreate(route_id=route.id, name="Railway Crossing", pickup_time="07:35"),
        session=db,
        principal=SUPERADMIN,
    )
    assert (stop1.sequence_no, stop2.sequence_no) == (1, 2)
    assert stop1.route_name == "North Loop"

    stops = await list_stops_endpoint(route_id=route.id, session=db, principal=SUPERADMIN, limit=100, offset=0)
    assert [s.name for s in stops] == ["Market Square", "Railway Crossing"]

    moved = await update_stop_endpoint(
        stop_id=stop2.id,
        payload=TransportRouteStopUpdate(sequence_no=1, drop_time="15:30"),
        session=db,
        principal=SUPERADMIN,
    )
    assert moved.sequence_no == 1
    assert moved.drop_time == "15:30"

    # 7. A vehicle still on an active route cannot be deleted
    with pytest.raises(HTTPException) as exc_info:
        await delete_vehicle_endpoint(vehicle_id=vehicle.id, session=db, principal=SUPERADMIN)
    assert exc_info.value.status_code == 400

    # 8. Detach, then both delete cleanly
    await update_route_endpoint(
        route_id=route.id,
        payload=TransportRouteUpdate(vehicle_id=None),
        session=db,
        principal=SUPERADMIN,
    )
    await delete_stop_endpoint(stop_id=stop1.id, session=db, principal=SUPERADMIN)
    await delete_stop_endpoint(stop_id=stop2.id, session=db, principal=SUPERADMIN)
    await delete_route_endpoint(route_id=route.id, session=db, principal=SUPERADMIN)
    await delete_vehicle_endpoint(vehicle_id=vehicle.id, session=db, principal=SUPERADMIN)

    with pytest.raises(HTTPException) as exc_info:
        await get_vehicle_endpoint(vehicle_id=vehicle.id, session=db, principal=SUPERADMIN)
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_student_assignment_lifecycle(db: AsyncSession):
    """Assign students to a route/stop, enforce capacity, then end the assignment."""
    vehicle = await create_vehicle_endpoint(
        payload=TransportVehicleCreate(campus_id=1, registration_no="MH-12-CD-9999", capacity=2),
        session=db,
        principal=SUPERADMIN,
    )
    route = await create_route_endpoint(
        payload=TransportRouteCreate(campus_id=1, name="East Loop", code="R-EAST", vehicle_id=vehicle.id),
        session=db,
        principal=SUPERADMIN,
    )
    stop = await create_stop_endpoint(
        payload=TransportRouteStopCreate(route_id=route.id, name="Hill Top"),
        session=db,
        principal=SUPERADMIN,
    )

    # 1. Assign two students (vehicle seats exactly 2)
    first = await assign_student_endpoint(
        payload=StudentTransportAssignmentCreate(
            route_id=route.id, student_id=101, stop_id=stop.id, effective_from=datetime.date(2026, 9, 1)
        ),
        session=db,
        principal=SUPERADMIN,
    )
    assert first.is_active is True
    assert first.route_name == "East Loop"
    assert first.stop_name == "Hill Top"
    # Who recorded it comes from the principal, not the body.
    assert first.assigned_by_user_id == 1

    await assign_student_endpoint(
        payload=StudentTransportAssignmentCreate(route_id=route.id, student_id=102),
        session=db,
        principal=SUPERADMIN,
    )

    # 2. A third student would overload the vehicle
    with pytest.raises(HTTPException) as exc_info:
        await assign_student_endpoint(
            payload=StudentTransportAssignmentCreate(route_id=route.id, student_id=103),
            session=db,
            principal=SUPERADMIN,
        )
    assert exc_info.value.status_code == 400
    assert "full" in exc_info.value.detail

    # 3. A student already on a route cannot be double-assigned
    with pytest.raises(HTTPException) as exc_info:
        await assign_student_endpoint(
            payload=StudentTransportAssignmentCreate(route_id=route.id, student_id=101),
            session=db,
            principal=SUPERADMIN,
        )
    assert exc_info.value.status_code == 400
    assert "already has an active transport assignment" in exc_info.value.detail

    # 4. A stop from another route is rejected
    other_route = await create_route_endpoint(
        payload=TransportRouteCreate(campus_id=1, name="West Loop", code="R-WEST"),
        session=db,
        principal=SUPERADMIN,
    )
    other_stop = await create_stop_endpoint(
        payload=TransportRouteStopCreate(route_id=other_route.id, name="Lake Side"),
        session=db,
        principal=SUPERADMIN,
    )
    with pytest.raises(HTTPException) as exc_info:
        await assign_student_endpoint(
            payload=StudentTransportAssignmentCreate(route_id=route.id, student_id=104, stop_id=other_stop.id),
            session=db,
            principal=SUPERADMIN,
        )
    assert exc_info.value.status_code == 400
    assert "does not belong to route" in exc_info.value.detail

    # 5. Listing
    assert len(await list_assignments_endpoint(route_id=route.id, session=db, principal=SUPERADMIN, limit=100, offset=0)) == 2
    assert len(await list_assignments_endpoint(route_id=route.id, is_active=True, session=db, principal=SUPERADMIN, limit=100, offset=0)) == 2

    # 6. Ending an assignment frees the seat
    ended = await end_assignment_endpoint(
        assignment_id=first.id,
        payload=StudentTransportAssignmentEnd(end_date=datetime.date(2026, 12, 15), notes="Family relocated"),
        session=db,
        principal=SUPERADMIN,
    )
    assert ended.is_active is False
    assert ended.effective_to == datetime.date(2026, 12, 15)

    with pytest.raises(HTTPException) as exc_info:
        await end_assignment_endpoint(
            assignment_id=first.id,
            payload=StudentTransportAssignmentEnd(end_date=datetime.date(2026, 12, 15)),
            session=db,
            principal=SUPERADMIN,
        )
    assert exc_info.value.status_code == 400

    # The freed seat is reusable
    reused = await assign_student_endpoint(
        payload=StudentTransportAssignmentCreate(route_id=route.id, student_id=103),
        session=db,
        principal=SUPERADMIN,
    )
    assert reused.student_id == 103

    # 7. A route with active students cannot be deleted
    with pytest.raises(HTTPException) as exc_info:
        await delete_route_endpoint(route_id=route.id, session=db, principal=SUPERADMIN)
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_stop_listing_is_campus_scoped(db: AsyncSession):
    """A caller pinned to one campus cannot read or write another campus's stops."""
    route_one = await create_route_endpoint(
        payload=TransportRouteCreate(campus_id=1, name="Campus One Loop", code="R-C1"),
        session=db,
        principal=SUPERADMIN,
    )
    route_two = await create_route_endpoint(
        payload=TransportRouteCreate(campus_id=2, name="Campus Two Loop", code="R-C2"),
        session=db,
        principal=SUPERADMIN,
    )
    await create_stop_endpoint(
        payload=TransportRouteStopCreate(route_id=route_one.id, name="Campus One Gate"),
        session=db,
        principal=SUPERADMIN,
    )
    await create_stop_endpoint(
        payload=TransportRouteStopCreate(route_id=route_two.id, name="Campus Two Gate"),
        session=db,
        principal=SUPERADMIN,
    )

    # Naming campus 1 does not widen a campus-2 caller's view; they are pinned.
    visible = await list_stops_endpoint(session=db, principal=CAMPUS_TWO_STAFF, limit=100, offset=0)
    assert [s.name for s in visible] == ["Campus Two Gate"]

    asked_for_one = await list_stops_endpoint(
        campus_id=1, session=db, principal=CAMPUS_TWO_STAFF, limit=100, offset=0
    )
    assert [s.name for s in asked_for_one] == ["Campus Two Gate"]

    # And they cannot hang a stop off the other campus's route.
    with pytest.raises(HTTPException) as exc_info:
        await create_stop_endpoint(
            payload=TransportRouteStopCreate(route_id=route_one.id, name="Sneaky Stop"),
            session=db,
            principal=CAMPUS_TWO_STAFF,
        )
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_compliance_dates_direction_and_coordinates_round_trip(db: AsyncSession):
    """Insurance/road-tax dates, route direction and stop coordinates persist."""
    vehicle = await create_vehicle_endpoint(
        payload=TransportVehicleCreate(
            campus_id=1,
            registration_no="TN-09-GH-4321",
            capacity=30,
            insurance_expiry=datetime.date(2027, 3, 31),
            road_tax_expiry=datetime.date(2026, 11, 30),
        ),
        session=db,
        principal=SUPERADMIN,
    )
    assert vehicle.insurance_expiry == datetime.date(2027, 3, 31)
    assert vehicle.road_tax_expiry == datetime.date(2026, 11, 30)

    route = await create_route_endpoint(
        payload=TransportRouteCreate(
            campus_id=1, name="South Loop", code="R-SOUTH", direction=RouteDirectionEnum.DROP
        ),
        session=db,
        principal=SUPERADMIN,
    )
    assert route.direction == RouteDirectionEnum.DROP

    stop = await create_stop_endpoint(
        payload=TransportRouteStopCreate(
            route_id=route.id, name="Temple Road", latitude=12.9716, longitude=77.5946
        ),
        session=db,
        principal=SUPERADMIN,
    )
    assert (stop.latitude, stop.longitude) == (12.9716, 77.5946)

    # An unsurveyed stop stays NULL. 0.0 is a real place (the Gulf of Guinea),
    # so "no coordinates" must never be rendered as a coordinate.
    unsurveyed = await create_stop_endpoint(
        payload=TransportRouteStopCreate(route_id=route.id, name="Unsurveyed Corner"),
        session=db,
        principal=SUPERADMIN,
    )
    assert unsurveyed.latitude is None
    assert unsurveyed.longitude is None


@pytest.mark.asyncio
async def test_another_organisations_fleet_is_invisible(db: AsyncSession):
    """A caller from org 2 cannot list, read or attach org 1's transport data."""
    vehicle = await create_vehicle_endpoint(
        payload=TransportVehicleCreate(campus_id=1, registration_no="DL-03-EF-1111", capacity=30),
        session=db,
        principal=SUPERADMIN,
    )
    route = await create_route_endpoint(
        payload=TransportRouteCreate(campus_id=1, name="Org One Route", code="R-ORG1", vehicle_id=vehicle.id),
        session=db,
        principal=SUPERADMIN,
    )
    await create_stop_endpoint(
        payload=TransportRouteStopCreate(route_id=route.id, name="Org One Stop"),
        session=db,
        principal=SUPERADMIN,
    )

    # Lists come back empty rather than leaking the other tenant's rows.
    assert await list_vehicles_endpoint(session=db, principal=OTHER_ORG_STAFF, limit=100, offset=0) == []
    assert await list_routes_endpoint(session=db, principal=OTHER_ORG_STAFF, limit=100, offset=0) == []
    assert await list_stops_endpoint(session=db, principal=OTHER_ORG_STAFF, limit=100, offset=0) == []

    # Direct reads 404 -- the row's existence is not confirmed.
    with pytest.raises(HTTPException) as exc_info:
        await get_vehicle_endpoint(vehicle_id=vehicle.id, session=db, principal=OTHER_ORG_STAFF)
    assert exc_info.value.status_code == 404

    with pytest.raises(HTTPException) as exc_info:
        await get_route_endpoint(route_id=route.id, session=db, principal=OTHER_ORG_STAFF)
    assert exc_info.value.status_code == 404

    # And org 1's vehicle cannot be attached to an org 2 route by id alone.
    with pytest.raises(HTTPException) as exc_info:
        await create_route_endpoint(
            payload=TransportRouteCreate(campus_id=2, name="Org Two Route", code="R-ORG2", vehicle_id=vehicle.id),
            session=db,
            principal=OTHER_ORG_STAFF,
        )
    assert exc_info.value.status_code == 404

    # Org 2's own data is visible to org 2 and invisible to org 1.
    own = await create_route_endpoint(
        payload=TransportRouteCreate(campus_id=2, name="Org Two Route", code="R-ORG2"),
        session=db,
        principal=OTHER_ORG_STAFF,
    )
    assert own.org_id == 2
    listed = await list_routes_endpoint(session=db, principal=OTHER_ORG_STAFF, limit=100, offset=0)
    assert [r.id for r in listed] == [own.id]
