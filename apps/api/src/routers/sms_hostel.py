import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.events.database import get_db_session
from src.core.keycloak_auth import (
    KeycloakUserPrincipal,
    get_current_user_principal,
    require_roles,
)
from src.db.sms_hostel import (
    AllocationStatusEnum,
    DormRoom,
    HostelBuilding,
    HostelGenderEnum,
    InspectionStatusEnum,
    RoomTypeEnum,
)
from src.schemas.sms.hostel import (
    BedAllocationCreate,
    BedAllocationRead,
    BedTransferRequest,
    BedVacateRequest,
    CurfewLogCreate,
    CurfewLogRead,
    DormRoomCreate,
    DormRoomRead,
    DormRoomUpdate,
    HostelBuildingCreate,
    HostelBuildingRead,
    HostelBuildingUpdate,
    HostelOverviewRead,
    RoomInspectionCreate,
    RoomInspectionRead,
)
from src.security.features_utils.dependencies import require_sms_hostel_feature
from src.security.school_ownership import (
    assert_campus_allowed,
    resolve_scoped_campus_id,
)
from src.services.sms import hostel as hostel_service

_HOSTEL_STAFF = ["SUPER_ADMIN", "SCHOOL_ADMIN", "STAFF", "PRINCIPAL"]

router = APIRouter(dependencies=[Depends(require_sms_hostel_feature)])


# ── Hostel Buildings ──

@router.post(
    "/buildings",
    response_model=HostelBuildingRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create Hostel Building",
)
async def create_building_endpoint(
    payload: HostelBuildingCreate,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_HOSTEL_STAFF)),
) -> HostelBuildingRead:
    assert_campus_allowed(principal, payload.campus_id)
    building = await hostel_service.create_hostel_building(
        session=session,
        payload=payload,
        campus_id=resolve_scoped_campus_id(principal, payload.campus_id),
        org_id=principal.org_id,
    )
    return HostelBuildingRead.model_validate(building)


@router.get(
    "/buildings",
    response_model=List[HostelBuildingRead],
    summary="List Hostel Buildings",
)
async def list_buildings_endpoint(
    campus_id: Optional[int] = None,
    gender: Optional[HostelGenderEnum] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_HOSTEL_STAFF)),
) -> List[HostelBuildingRead]:
    scoped_campus = resolve_scoped_campus_id(principal, campus_id)
    buildings = await hostel_service.list_hostel_buildings(
        session=session,
        campus_id=scoped_campus,
        gender=gender,
        is_active=is_active,
        search=search,
        limit=limit,
        offset=offset,
    )
    out = []
    for b in buildings:
        rooms = await hostel_service.list_dorm_rooms(session, building_id=b.id)
        total_rooms = len(rooms)
        cap = sum(r.capacity for r in rooms)
        occ = sum(r.occupied_beds for r in rooms)
        avail = max(0, cap - occ)
        rate = round((occ / cap * 100.0), 1) if cap > 0 else 0.0

        br = HostelBuildingRead.model_validate(b)
        br.total_rooms = total_rooms
        br.total_capacity = cap
        br.occupied_beds = occ
        br.available_beds = avail
        br.occupancy_rate = rate
        out.append(br)
    return out


@router.get(
    "/buildings/{building_id}",
    response_model=HostelBuildingRead,
    summary="Get Hostel Building Details",
)
async def get_building_endpoint(
    building_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_HOSTEL_STAFF)),
) -> HostelBuildingRead:
    b = await hostel_service.get_hostel_building(session, building_id)
    assert_campus_allowed(principal, b.campus_id)
    rooms = await hostel_service.list_dorm_rooms(session, building_id=b.id)
    cap = sum(r.capacity for r in rooms)
    occ = sum(r.occupied_beds for r in rooms)
    
    br = HostelBuildingRead.model_validate(b)
    br.total_rooms = len(rooms)
    br.total_capacity = cap
    br.occupied_beds = occ
    br.available_beds = max(0, cap - occ)
    br.occupancy_rate = round((occ / cap * 100.0), 1) if cap > 0 else 0.0
    return br


@router.patch(
    "/buildings/{building_id}",
    response_model=HostelBuildingRead,
    summary="Update Hostel Building",
)
async def update_building_endpoint(
    building_id: int,
    payload: HostelBuildingUpdate,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_HOSTEL_STAFF)),
) -> HostelBuildingRead:
    existing = await hostel_service.get_hostel_building(session, building_id)
    assert_campus_allowed(principal, existing.campus_id)
    building = await hostel_service.update_hostel_building(session, building_id, payload)
    return HostelBuildingRead.model_validate(building)


@router.delete(
    "/buildings/{building_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Hostel Building",
)
async def delete_building_endpoint(
    building_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_HOSTEL_STAFF)),
) -> None:
    existing = await hostel_service.get_hostel_building(session, building_id)
    assert_campus_allowed(principal, existing.campus_id)
    await hostel_service.delete_hostel_building(session, building_id)


# ── Dorm Rooms ──

@router.post(
    "/rooms",
    response_model=DormRoomRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create Dorm Room",
)
async def create_room_endpoint(
    payload: DormRoomCreate,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_HOSTEL_STAFF)),
) -> DormRoomRead:
    building = await hostel_service.get_hostel_building(session, payload.building_id)
    assert_campus_allowed(principal, building.campus_id)
    room = await hostel_service.create_dorm_room(session, payload)
    
    rr = DormRoomRead.model_validate(room)
    rr.building_name = building.name
    rr.available_beds = max(0, room.capacity - room.occupied_beds)
    return rr


@router.get(
    "/rooms",
    response_model=List[DormRoomRead],
    summary="List Dorm Rooms",
)
async def list_rooms_endpoint(
    building_id: Optional[int] = None,
    room_type: Optional[RoomTypeEnum] = None,
    available_only: bool = False,
    is_active: Optional[bool] = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_HOSTEL_STAFF)),
) -> List[DormRoomRead]:
    rooms = await hostel_service.list_dorm_rooms(
        session=session,
        building_id=building_id,
        room_type=room_type,
        available_only=available_only,
        is_active=is_active,
        limit=limit,
        offset=offset,
    )
    out = []
    for r in rooms:
        building = await session.get(HostelBuilding, r.building_id)
        if building and principal.campus_id and building.campus_id != principal.campus_id and not principal.is_superadmin:
            continue
        rr = DormRoomRead.model_validate(r)
        rr.building_name = building.name if building else None
        rr.available_beds = max(0, r.capacity - r.occupied_beds)
        out.append(rr)
    return out


@router.get(
    "/rooms/{room_id}",
    response_model=DormRoomRead,
    summary="Get Dorm Room Details",
)
async def get_room_endpoint(
    room_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_HOSTEL_STAFF)),
) -> DormRoomRead:
    room = await hostel_service.get_dorm_room(session, room_id)
    building = await hostel_service.get_hostel_building(session, room.building_id)
    assert_campus_allowed(principal, building.campus_id)
    
    rr = DormRoomRead.model_validate(room)
    rr.building_name = building.name
    rr.available_beds = max(0, room.capacity - room.occupied_beds)
    return rr


@router.patch(
    "/rooms/{room_id}",
    response_model=DormRoomRead,
    summary="Update Dorm Room",
)
async def update_room_endpoint(
    room_id: int,
    payload: DormRoomUpdate,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_HOSTEL_STAFF)),
) -> DormRoomRead:
    room = await hostel_service.get_dorm_room(session, room_id)
    building = await hostel_service.get_hostel_building(session, room.building_id)
    assert_campus_allowed(principal, building.campus_id)
    updated = await hostel_service.update_dorm_room(session, room_id, payload)
    
    rr = DormRoomRead.model_validate(updated)
    rr.building_name = building.name
    rr.available_beds = max(0, updated.capacity - updated.occupied_beds)
    return rr


@router.delete(
    "/rooms/{room_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Dorm Room",
)
async def delete_room_endpoint(
    room_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_HOSTEL_STAFF)),
) -> None:
    room = await hostel_service.get_dorm_room(session, room_id)
    building = await hostel_service.get_hostel_building(session, room.building_id)
    assert_campus_allowed(principal, building.campus_id)
    await hostel_service.delete_dorm_room(session, room_id)


# ── Bed Allocations ──

@router.post(
    "/allocations",
    response_model=BedAllocationRead,
    status_code=status.HTTP_201_CREATED,
    summary="Allocate Bed to Student",
)
async def allocate_bed_endpoint(
    payload: BedAllocationCreate,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_HOSTEL_STAFF)),
) -> BedAllocationRead:
    room = await hostel_service.get_dorm_room(session, payload.room_id)
    building = await hostel_service.get_hostel_building(session, room.building_id)
    assert_campus_allowed(principal, building.campus_id)
    
    user_id = principal.raw_claims.get("lh_user_id")
    alloc = await hostel_service.allocate_bed(session, payload, allocated_by_user_id=user_id)
    
    ar = BedAllocationRead.model_validate(alloc)
    ar.room_number = room.room_number
    ar.building_id = building.id
    ar.building_name = building.name
    return ar


@router.get(
    "/allocations",
    response_model=List[BedAllocationRead],
    summary="List Bed Allocations",
)
async def list_allocations_endpoint(
    building_id: Optional[int] = None,
    room_id: Optional[int] = None,
    student_id: Optional[int] = None,
    status_filter: Optional[AllocationStatusEnum] = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_HOSTEL_STAFF)),
) -> List[BedAllocationRead]:
    allocs = await hostel_service.list_bed_allocations(
        session=session,
        building_id=building_id,
        room_id=room_id,
        student_id=student_id,
        status_filter=status_filter,
        limit=limit,
        offset=offset,
    )
    out = []
    for a in allocs:
        room = await session.get(DormRoom, a.room_id)
        building = await session.get(HostelBuilding, room.building_id) if room else None
        if building and principal.campus_id and building.campus_id != principal.campus_id and not principal.is_superadmin:
            continue
        ar = BedAllocationRead.model_validate(a)
        ar.room_number = room.room_number if room else None
        ar.building_id = building.id if building else None
        ar.building_name = building.name if building else None
        out.append(ar)
    return out


@router.post(
    "/allocations/{allocation_id}/vacate",
    response_model=BedAllocationRead,
    summary="Vacate Bed Allocation",
)
async def vacate_bed_endpoint(
    allocation_id: int,
    payload: BedVacateRequest,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_HOSTEL_STAFF)),
) -> BedAllocationRead:
    alloc = await session.get(hostel_service.BedAllocation, allocation_id)
    if not alloc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Allocation not found.")
    room = await hostel_service.get_dorm_room(session, alloc.room_id)
    building = await hostel_service.get_hostel_building(session, room.building_id)
    assert_campus_allowed(principal, building.campus_id)
    
    vacated = await hostel_service.vacate_bed(session, allocation_id, payload)
    ar = BedAllocationRead.model_validate(vacated)
    ar.room_number = room.room_number
    ar.building_id = building.id
    ar.building_name = building.name
    return ar


@router.post(
    "/allocations/{allocation_id}/transfer",
    response_model=BedAllocationRead,
    summary="Transfer Student to Another Room/Bed",
)
async def transfer_bed_endpoint(
    allocation_id: int,
    payload: BedTransferRequest,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_HOSTEL_STAFF)),
) -> BedAllocationRead:
    alloc = await session.get(hostel_service.BedAllocation, allocation_id)
    if not alloc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Allocation not found.")
    old_room = await hostel_service.get_dorm_room(session, alloc.room_id)
    old_building = await hostel_service.get_hostel_building(session, old_room.building_id)
    assert_campus_allowed(principal, old_building.campus_id)
    
    user_id = principal.raw_claims.get("lh_user_id")
    new_alloc = await hostel_service.transfer_bed(session, allocation_id, payload, performed_by_user_id=user_id)
    new_room = await hostel_service.get_dorm_room(session, new_alloc.room_id)
    new_b = await hostel_service.get_hostel_building(session, new_room.building_id)
    
    ar = BedAllocationRead.model_validate(new_alloc)
    ar.room_number = new_room.room_number
    ar.building_id = new_b.id
    ar.building_name = new_b.name
    return ar


# ── Curfew Logs ──

@router.post(
    "/curfew-logs",
    response_model=CurfewLogRead,
    status_code=status.HTTP_201_CREATED,
    summary="Record Hostel Curfew Log",
)
async def create_curfew_log_endpoint(
    payload: CurfewLogCreate,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_HOSTEL_STAFF)),
) -> CurfewLogRead:
    if payload.building_id:
        b = await hostel_service.get_hostel_building(session, payload.building_id)
        assert_campus_allowed(principal, b.campus_id)
    user_id = principal.raw_claims.get("lh_user_id")
    curfew = await hostel_service.create_curfew_log(session, payload, reported_by_user_id=user_id)
    building = await session.get(HostelBuilding, curfew.building_id) if curfew.building_id else None
    
    cr = CurfewLogRead.model_validate(curfew)
    cr.building_name = building.name if building else None
    return cr


@router.get(
    "/curfew-logs",
    response_model=List[CurfewLogRead],
    summary="List Curfew Logs",
)
async def list_curfew_logs_endpoint(
    student_id: Optional[int] = None,
    building_id: Optional[int] = None,
    date_from: Optional[datetime.date] = None,
    date_to: Optional[datetime.date] = None,
    violations_only: bool = False,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_HOSTEL_STAFF)),
) -> List[CurfewLogRead]:
    logs = await hostel_service.list_curfew_logs(
        session=session,
        student_id=student_id,
        building_id=building_id,
        date_from=date_from,
        date_to=date_to,
        violations_only=violations_only,
        limit=limit,
        offset=offset,
    )
    out = []
    for log in logs:
        building = await session.get(HostelBuilding, log.building_id) if log.building_id else None
        if building and principal.campus_id and building.campus_id != principal.campus_id and not principal.is_superadmin:
            continue
        cr = CurfewLogRead.model_validate(log)
        cr.building_name = building.name if building else None
        out.append(cr)
    return out


# ── Room Inspections ──

@router.post(
    "/inspections",
    response_model=RoomInspectionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Record Room Inspection",
)
async def create_inspection_endpoint(
    payload: RoomInspectionCreate,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_HOSTEL_STAFF)),
) -> RoomInspectionRead:
    room = await hostel_service.get_dorm_room(session, payload.room_id)
    building = await hostel_service.get_hostel_building(session, room.building_id)
    assert_campus_allowed(principal, building.campus_id)
    
    user_id = principal.raw_claims.get("lh_user_id")
    inspection = await hostel_service.create_room_inspection(session, payload, inspected_by_user_id=user_id)
    
    ir = RoomInspectionRead.model_validate(inspection)
    ir.room_number = room.room_number
    ir.building_id = building.id
    ir.building_name = building.name
    return ir


@router.get(
    "/inspections",
    response_model=List[RoomInspectionRead],
    summary="List Room Inspections",
)
async def list_inspections_endpoint(
    room_id: Optional[int] = None,
    building_id: Optional[int] = None,
    maintenance_status: Optional[InspectionStatusEnum] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_HOSTEL_STAFF)),
) -> List[RoomInspectionRead]:
    inspections = await hostel_service.list_room_inspections(
        session=session,
        room_id=room_id,
        building_id=building_id,
        maintenance_status=maintenance_status,
        limit=limit,
        offset=offset,
    )
    out = []
    for insp in inspections:
        room = await session.get(DormRoom, insp.room_id)
        building = await session.get(HostelBuilding, room.building_id) if room else None
        if building and principal.campus_id and building.campus_id != principal.campus_id and not principal.is_superadmin:
            continue
        ir = RoomInspectionRead.model_validate(insp)
        ir.room_number = room.room_number if room else None
        ir.building_id = building.id if building else None
        ir.building_name = building.name if building else None
        out.append(ir)
    return out


# ── Overview & Occupancy Stats ──

@router.get(
    "/overview",
    response_model=HostelOverviewRead,
    summary="Get Hostel Overview and Occupancy Metrics",
)
async def get_overview_endpoint(
    campus_id: Optional[int] = None,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_HOSTEL_STAFF)),
) -> HostelOverviewRead:
    scoped_campus = resolve_scoped_campus_id(principal, campus_id)
    return await hostel_service.get_hostel_overview(session, campus_id=scoped_campus)
