"""Classrooms & Rooms: CRUD and tenant isolation.

Handlers are invoked directly, so FastAPI never runs `Depends(...)` and the
`require_roles` gate is not exercised here -- see src/tests/sms/_principals.py.
What these tests do cover is the scoping that happens inside the handler:
org isolation and campus isolation.

`limit`/`offset` are passed explicitly for the same reason: their `Query(...)`
defaults are unresolved `Query` objects until FastAPI processes them.
"""

import pytest
from fastapi import HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_facilities import ClassroomCreate, ClassroomType, ClassroomUpdate
from src.routers.sms_facilities import (
    create_classroom,
    delete_classroom,
    get_classroom,
    list_classrooms,
    update_classroom,
)
from src.tests.sms._principals import SUPERADMIN, principal


def _payload(**overrides) -> ClassroomCreate:
    fields = {
        "campus_id": 1,
        "name": "Room 204",
        "code": "A-204",
        "room_type": ClassroomType.CLASSROOM,
        "capacity": 32,
    }
    fields.update(overrides)
    return ClassroomCreate(**fields)


@pytest.mark.asyncio
async def test_classroom_can_be_created_and_read(db: AsyncSession):
    created = await create_classroom(
        payload=_payload(), session=db, principal=SUPERADMIN
    )

    assert created.id is not None
    assert created.name == "Room 204"
    assert created.code == "A-204"
    assert created.room_type == ClassroomType.CLASSROOM
    assert created.capacity == 32
    assert created.is_active is True
    # Tenant columns come from the principal, not from the request body.
    assert created.org_id == 1
    assert created.campus_id == 1

    fetched = await get_classroom(
        classroom_id=created.id, session=db, principal=SUPERADMIN
    )
    assert fetched.id == created.id
    assert fetched.capacity == 32

    listed = await list_classrooms(
        session=db, principal=SUPERADMIN, limit=100, offset=0
    )
    assert created.id in [row.id for row in listed]


@pytest.mark.asyncio
async def test_classroom_from_another_org_is_invisible(db: AsyncSession):
    """The tenant boundary: org 2 must not see, read or count org 1's room."""
    created = await create_classroom(
        payload=_payload(), session=db, principal=SUPERADMIN
    )

    other_org_admin = principal("SCHOOL_ADMIN", org_id=2, campus_id=1)

    # 404, not 403: a 403 would confirm the id exists in another school.
    with pytest.raises(HTTPException) as exc_info:
        await get_classroom(
            classroom_id=created.id, session=db, principal=other_org_admin
        )
    assert exc_info.value.status_code == 404

    assert (
        await list_classrooms(
            session=db, principal=other_org_admin, limit=100, offset=0
        )
        == []
    )

    # And the owner still sees it -- the filter is the org, not a blanket deny.
    assert (
        await list_classrooms(session=db, principal=SUPERADMIN, limit=100, offset=0)
        != []
    )


@pytest.mark.asyncio
async def test_classroom_is_scoped_to_the_callers_campus(db: AsyncSession):
    """A campus-bound admin cannot reach another campus's room."""
    created = await create_classroom(
        payload=_payload(campus_id=1), session=db, principal=SUPERADMIN
    )

    other_campus_admin = principal("SCHOOL_ADMIN", org_id=1, campus_id=2)

    with pytest.raises(HTTPException) as exc_info:
        await get_classroom(
            classroom_id=created.id, session=db, principal=other_campus_admin
        )
    assert exc_info.value.status_code == 403

    # Asking for another campus does not widen the list either.
    assert (
        await list_classrooms(
            campus_id=1,
            session=db,
            principal=other_campus_admin,
            limit=100,
            offset=0,
        )
        == []
    )


@pytest.mark.asyncio
async def test_classroom_update_and_deactivate(db: AsyncSession):
    created = await create_classroom(
        payload=_payload(), session=db, principal=SUPERADMIN
    )

    updated = await update_classroom(
        classroom_id=created.id,
        payload=ClassroomUpdate(capacity=24, room_type=ClassroomType.LAB),
        session=db,
        principal=SUPERADMIN,
    )
    assert updated.capacity == 24
    assert updated.room_type == ClassroomType.LAB
    assert updated.name == "Room 204"  # untouched fields survive a PATCH

    await delete_classroom(
        classroom_id=created.id, session=db, principal=SUPERADMIN
    )

    # Deactivation is a soft delete: the row stays readable...
    assert (
        await get_classroom(
            classroom_id=created.id, session=db, principal=SUPERADMIN
        )
    ).is_active is False
    # ...but drops out of the default picker.
    assert (
        await list_classrooms(
            is_active=True, session=db, principal=SUPERADMIN, limit=100, offset=0
        )
        == []
    )


@pytest.mark.asyncio
async def test_classroom_list_filters_by_type_and_capacity(db: AsyncSession):
    await create_classroom(
        payload=_payload(code="A-204", capacity=32), session=db, principal=SUPERADMIN
    )
    await create_classroom(
        payload=_payload(
            code="CHEM-1",
            name="Chemistry Lab 1",
            room_type=ClassroomType.LAB,
            capacity=20,
        ),
        session=db,
        principal=SUPERADMIN,
    )

    labs = await list_classrooms(
        room_type=ClassroomType.LAB,
        session=db,
        principal=SUPERADMIN,
        limit=100,
        offset=0,
    )
    assert [row.code for row in labs] == ["CHEM-1"]

    big_enough = await list_classrooms(
        min_capacity=30, session=db, principal=SUPERADMIN, limit=100, offset=0
    )
    assert [row.code for row in big_enough] == ["A-204"]
