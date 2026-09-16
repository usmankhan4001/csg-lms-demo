"""
Transport authorization, exercised over real HTTP.

The parent/student read path goes through the router's ownership dependency,
which reads the student id off the request -- so it can only be tested with a
real request, not by calling the handler directly.

It answers 404 rather than 403: a parent probing another family's child must not
be able to tell that the child has a transport record at all.
"""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.core.events.database import get_db_session
from src.db.sms_identity import SMSUserRole, SchoolRole, StudentGuardian
from src.db.users import PublicUser
from src.router import v1_router
from src.schemas.sms.transport import (
    StudentTransportAssignmentCreate,
    TransportRouteCreate,
    TransportRouteStopCreate,
)
from src.security.auth import get_authenticated_user
from src.services.sms import transport as transport_service


def _make_app(db):
    app = FastAPI()
    app.include_router(v1_router)
    app.dependency_overrides[get_db_session] = lambda: db
    return app


def _user(id_: int) -> PublicUser:
    return PublicUser(
        id=id_,
        username=f"user{id_}",
        first_name="Test",
        last_name=f"User{id_}",
        email=f"user{id_}@test.com",
        user_uuid=f"uuid-{id_}",
    )


async def _seed_assignment(db, org_id: int, student_id: int, route_code: str):
    route = await transport_service.create_route(
        session=db,
        payload=TransportRouteCreate(name=f"Route {route_code}", code=route_code),
        org_id=org_id,
    )
    stop = await transport_service.create_stop(
        session=db,
        payload=TransportRouteStopCreate(route_id=route.id, name=f"Stop {route_code}"),
        org_id=org_id,
    )
    return await transport_service.assign_student(
        session=db,
        payload=StudentTransportAssignmentCreate(route_id=route.id, student_id=student_id, stop_id=stop.id),
        org_id=org_id,
    )


@pytest.mark.asyncio
async def test_parent_can_read_their_own_childs_assignment(db, org):
    db.add(SMSUserRole(user_id=10, org_id=org.id, role=SchoolRole.PARENT))
    db.add(StudentGuardian(guardian_user_id=10, student_id=2))
    await db.commit()
    await _seed_assignment(db, org.id, student_id=2, route_code="R-PARENT")

    app = _make_app(db)
    app.dependency_overrides[get_authenticated_user] = lambda: _user(10)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/sms/transport/assignments/student/2")

    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body) == 1
    assert body[0]["student_id"] == 2
    assert body[0]["route_name"] == "Route R-PARENT"
    assert body[0]["stop_name"] == "Stop R-PARENT"


@pytest.mark.asyncio
async def test_parent_cannot_read_another_childs_assignment(db, org):
    db.add(SMSUserRole(user_id=10, org_id=org.id, role=SchoolRole.PARENT))
    db.add(StudentGuardian(guardian_user_id=10, student_id=2))  # their own child
    await db.commit()
    await _seed_assignment(db, org.id, student_id=77, route_code="R-OTHER")  # somebody else's

    app = _make_app(db)
    app.dependency_overrides[get_authenticated_user] = lambda: _user(10)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/sms/transport/assignments/student/77")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_student_can_read_their_own_assignment(db, org):
    db.add(SMSUserRole(user_id=5, org_id=org.id, role=SchoolRole.STUDENT))
    await db.commit()
    await _seed_assignment(db, org.id, student_id=5, route_code="R-SELF")

    app = _make_app(db)
    app.dependency_overrides[get_authenticated_user] = lambda: _user(5)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        own = await client.get("/api/v1/sms/transport/assignments/student/5")
        someone_else = await client.get("/api/v1/sms/transport/assignments/student/6")

    assert own.status_code == 200, own.text
    assert own.json()[0]["student_id"] == 5
    assert someone_else.status_code == 404


@pytest.mark.asyncio
async def test_parent_cannot_write_transport_records(db, org):
    """The own-record read path is read-only; fleet writes stay staff-only."""
    db.add(SMSUserRole(user_id=10, org_id=org.id, role=SchoolRole.PARENT))
    await db.commit()

    app = _make_app(db)
    app.dependency_overrides[get_authenticated_user] = lambda: _user(10)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_vehicle = await client.post(
            "/api/v1/sms/transport/vehicles", json={"registration_no": "XX-00-ZZ-0000"}
        )
        list_vehicles = await client.get("/api/v1/sms/transport/vehicles")

    assert create_vehicle.status_code == 403
    assert list_vehicles.status_code == 403


@pytest.mark.asyncio
async def test_staff_can_read_the_whole_fleet(db, org):
    db.add(SMSUserRole(user_id=20, org_id=org.id, role=SchoolRole.STAFF))
    await db.commit()
    await _seed_assignment(db, org.id, student_id=2, route_code="R-STAFF")

    app = _make_app(db)
    app.dependency_overrides[get_authenticated_user] = lambda: _user(20)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        vehicles = await client.get("/api/v1/sms/transport/vehicles")
        routes = await client.get("/api/v1/sms/transport/routes")
        assignments = await client.get("/api/v1/sms/transport/assignments")

    assert vehicles.status_code == 200, vehicles.text
    assert routes.status_code == 200, routes.text
    assert assignments.status_code == 200, assignments.text
    assert len(assignments.json()) == 1
