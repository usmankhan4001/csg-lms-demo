"""Classrooms & Rooms CRUD (Domain 1: Campuses & Classrooms).

The first entity in the system that can answer "how many children fit in this
room", which is what the timetable constraint solver needs and what the
free-text `room_number` columns on `ClassSection` / `sms_exam` /
`sms_timetable` could never answer.

Wiring `room_id` into the timetable is a separate change; nothing here is
called by it yet.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.events.database import get_db_session
from src.core.keycloak_auth import (
    SCHOOL_ADMIN,
    STAFF,
    SUPER_ADMIN,
    KeycloakUserPrincipal,
    require_roles,
)
from src.db.sms_facilities import (
    Classroom,
    ClassroomCreate,
    ClassroomRead,
    ClassroomType,
    ClassroomUpdate,
    get_utc_now_iso,
)
from src.security.school_ownership import (
    assert_campus_allowed,
    require_org_id,
    resolve_scoped_campus_id,
)

_CLASSROOM_STAFF = [SUPER_ADMIN, SCHOOL_ADMIN, STAFF]

router = APIRouter(prefix="/sms/facilities", tags=["sms-facilities"])


async def _get_scoped_classroom(
    session: AsyncSession,
    classroom_id: int,
    org_id: int,
) -> Classroom:
    """Fetch a classroom by id, pinned to the caller's organisation.

    The org filter sits in the WHERE clause rather than being checked after
    the fetch: a room belonging to another school must be indistinguishable
    from one that does not exist, so both raise 404. A 403 here would confirm
    to the caller that the id is real.
    """
    result = await session.exec(
        select(Classroom).where(
            Classroom.id == classroom_id,
            Classroom.org_id == org_id,
        )
    )
    classroom = result.first()
    if classroom is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Classroom not found",
        )
    return classroom


@router.post(
    "/classrooms",
    response_model=ClassroomRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create Classroom",
)
async def create_classroom(
    payload: ClassroomCreate,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_CLASSROOM_STAFF)),
) -> ClassroomRead:
    org_id = require_org_id(principal)
    assert_campus_allowed(principal, payload.campus_id)
    fields = payload.model_dump()
    requested_campus_id = fields.pop("campus_id")
    classroom = Classroom(
        **fields,
        org_id=org_id,
        campus_id=resolve_scoped_campus_id(principal, requested_campus_id),
    )
    session.add(classroom)
    await session.commit()
    await session.refresh(classroom)
    return ClassroomRead.model_validate(classroom)


@router.get(
    "/classrooms",
    response_model=List[ClassroomRead],
    summary="List Classrooms",
)
async def list_classrooms(
    campus_id: Optional[int] = None,
    room_type: Optional[ClassroomType] = None,
    is_active: Optional[bool] = None,
    min_capacity: Optional[int] = None,  # only rooms seating at least this many
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_CLASSROOM_STAFF)),
) -> List[ClassroomRead]:
    # campus_id arrives from the CLIENT. Filtering on org_id alone is not
    # enough tenancy: without this, a campus-bound admin at campus A could
    # list campus B's rooms simply by passing campus_id=B.
    # resolve_scoped_campus_id pins a campus-bound caller to their own campus
    # whether they ask for another or ask for none; only a caller with no
    # campus of their own sees org-wide.
    scoped_campus = resolve_scoped_campus_id(principal, campus_id)
    statement = select(Classroom).where(Classroom.org_id == require_org_id(principal))
    if scoped_campus is not None:
        statement = statement.where(Classroom.campus_id == scoped_campus)
    if room_type is not None:
        statement = statement.where(Classroom.room_type == room_type)
    if is_active is not None:
        statement = statement.where(Classroom.is_active == is_active)
    if min_capacity is not None:
        statement = statement.where(Classroom.capacity >= min_capacity)
    statement = statement.order_by(Classroom.code).offset(offset).limit(limit)
    result = await session.exec(statement)
    return [ClassroomRead.model_validate(row) for row in result.all()]


@router.get(
    "/classrooms/{classroom_id}",
    response_model=ClassroomRead,
    summary="Get Classroom",
)
async def get_classroom(
    classroom_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_CLASSROOM_STAFF)),
) -> ClassroomRead:
    classroom = await _get_scoped_classroom(
        session, classroom_id, require_org_id(principal)
    )
    assert_campus_allowed(principal, classroom.campus_id)
    return ClassroomRead.model_validate(classroom)


@router.patch(
    "/classrooms/{classroom_id}",
    response_model=ClassroomRead,
    summary="Update Classroom",
)
async def update_classroom(
    classroom_id: int,
    payload: ClassroomUpdate,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_CLASSROOM_STAFF)),
) -> ClassroomRead:
    classroom = await _get_scoped_classroom(
        session, classroom_id, require_org_id(principal)
    )
    assert_campus_allowed(principal, classroom.campus_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(classroom, field, value)
    classroom.updated_at = get_utc_now_iso()
    session.add(classroom)
    await session.commit()
    await session.refresh(classroom)
    return ClassroomRead.model_validate(classroom)


@router.delete(
    "/classrooms/{classroom_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate Classroom",
)
async def delete_classroom(
    classroom_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_CLASSROOM_STAFF)),
) -> None:
    """Deactivate the room rather than dropping the row.

    A room is referenced by timetable slots and exam seating (the `room_id`
    wiring is a separate change), so a hard delete would either orphan those
    rows or fail on the foreign key. `is_active=False` removes the room from
    every picker and from the solver's candidate set -- which is what
    "delete a room" means to a school -- while leaving the historical record
    readable.
    """
    classroom = await _get_scoped_classroom(
        session, classroom_id, require_org_id(principal)
    )
    assert_campus_allowed(principal, classroom.campus_id)
    classroom.is_active = False
    classroom.updated_at = get_utc_now_iso()
    session.add(classroom)
    await session.commit()
