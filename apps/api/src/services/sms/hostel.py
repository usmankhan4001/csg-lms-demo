import datetime
from typing import List, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy import func, or_
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_hostel import (
    AllocationStatusEnum,
    BedAllocation,
    CurfewLog,
    DormRoom,
    HostelBuilding,
    HostelGenderEnum,
    InspectionStatusEnum,
    RoomInspection,
    RoomTypeEnum,
)
from src.schemas.sms.hostel import (
    BedAllocationCreate,
    BedAllocationRead,
    BedTransferRequest,
    BedVacateRequest,
    BuildingOccupancyRead,
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


# ── Hostel Buildings ──

async def create_hostel_building(
    session: AsyncSession,
    payload: HostelBuildingCreate,
    campus_id: Optional[int] = None,
    org_id: Optional[int] = None,
) -> HostelBuilding:
    query = select(HostelBuilding).where(HostelBuilding.building_code == payload.building_code)
    if campus_id is not None:
        query = query.where(HostelBuilding.campus_id == campus_id)
    existing = (await session.exec(query)).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A hostel building with code '{payload.building_code}' already exists.",
        )

    resolved_campus_id = payload.campus_id if payload.campus_id is not None else campus_id
    resolved_org_id = payload.org_id if payload.org_id is not None else org_id

    building = HostelBuilding(
        campus_id=resolved_campus_id,
        org_id=resolved_org_id,
        name=payload.name.strip(),
        building_code=payload.building_code.strip(),
        gender=payload.gender,
        warden_name=payload.warden_name,
        warden_contact=payload.warden_contact,
        warden_email=payload.warden_email,
        address=payload.address,
        total_floors=payload.total_floors,
        total_capacity=payload.total_capacity,
        is_active=True,
    )
    session.add(building)
    await session.commit()
    await session.refresh(building)
    return building


async def update_hostel_building(
    session: AsyncSession,
    building_id: int,
    payload: HostelBuildingUpdate,
) -> HostelBuilding:
    building = await session.get(HostelBuilding, building_id)
    if not building:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hostel building not found.")

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(building, key, value)

    building.updated_at = datetime.datetime.now(datetime.timezone.utc)
    session.add(building)
    await session.commit()
    await session.refresh(building)
    return building


async def delete_hostel_building(session: AsyncSession, building_id: int) -> None:
    building = await session.get(HostelBuilding, building_id)
    if not building:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hostel building not found.")
    await session.delete(building)
    await session.commit()


async def get_hostel_building(session: AsyncSession, building_id: int) -> HostelBuilding:
    building = await session.get(HostelBuilding, building_id)
    if not building:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hostel building not found.")
    return building


async def list_hostel_buildings(
    session: AsyncSession,
    campus_id: Optional[int] = None,
    gender: Optional[HostelGenderEnum] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[HostelBuilding]:
    query = select(HostelBuilding)
    if campus_id is not None:
        query = query.where(HostelBuilding.campus_id == campus_id)
    if gender is not None:
        query = query.where(HostelBuilding.gender == gender)
    if is_active is not None:
        query = query.where(HostelBuilding.is_active == is_active)
    if search:
        search_pattern = f"%{search}%"
        query = query.where(
            or_(
                HostelBuilding.name.ilike(search_pattern),
                HostelBuilding.building_code.ilike(search_pattern),
                HostelBuilding.warden_name.ilike(search_pattern),
            )
        )
    query = query.order_by(HostelBuilding.name).offset(offset).limit(limit)
    result = await session.exec(query)
    return result.all()


# ── Dorm Rooms ──

async def create_dorm_room(
    session: AsyncSession,
    payload: DormRoomCreate,
) -> DormRoom:
    building = await session.get(HostelBuilding, payload.building_id)
    if not building:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hostel building not found.")

    # Check room number uniqueness within the building
    existing = (
        await session.exec(
            select(DormRoom).where(
                DormRoom.building_id == payload.building_id,
                DormRoom.room_number == payload.room_number.strip(),
            )
        )
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Room '{payload.room_number}' already exists in {building.name}.",
        )

    room = DormRoom(
        building_id=payload.building_id,
        room_number=payload.room_number.strip(),
        floor_number=payload.floor_number,
        room_type=payload.room_type,
        capacity=payload.capacity,
        occupied_beds=0,
        base_fee_per_term=payload.base_fee_per_term,
        is_ac=payload.is_ac,
        has_attached_bath=payload.has_attached_bath,
        notes=payload.notes,
        is_active=True,
    )
    session.add(room)
    # Update building capacity sum
    building.total_capacity += payload.capacity
    session.add(building)

    await session.commit()
    await session.refresh(room)
    return room


async def update_dorm_room(
    session: AsyncSession,
    room_id: int,
    payload: DormRoomUpdate,
) -> DormRoom:
    room = await session.get(DormRoom, room_id)
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dorm room not found.")

    if payload.capacity is not None and payload.capacity < room.occupied_beds:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot reduce capacity to {payload.capacity} below currently occupied beds ({room.occupied_beds}).",
        )

    old_capacity = room.capacity
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(room, key, value)

    room.updated_at = datetime.datetime.now(datetime.timezone.utc)
    session.add(room)

    if payload.capacity is not None and payload.capacity != old_capacity:
        building = await session.get(HostelBuilding, room.building_id)
        if building:
            building.total_capacity += (payload.capacity - old_capacity)
            session.add(building)

    await session.commit()
    await session.refresh(room)
    return room


async def delete_dorm_room(session: AsyncSession, room_id: int) -> None:
    room = await session.get(DormRoom, room_id)
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dorm room not found.")

    if room.occupied_beds > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete room with active bed allocations. Vacate all occupants first.",
        )

    building = await session.get(HostelBuilding, room.building_id)
    if building:
        building.total_capacity = max(0, building.total_capacity - room.capacity)
        session.add(building)

    await session.delete(room)
    await session.commit()


async def get_dorm_room(session: AsyncSession, room_id: int) -> DormRoom:
    room = await session.get(DormRoom, room_id)
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dorm room not found.")
    return room


async def list_dorm_rooms(
    session: AsyncSession,
    building_id: Optional[int] = None,
    room_type: Optional[RoomTypeEnum] = None,
    available_only: bool = False,
    is_active: Optional[bool] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[DormRoom]:
    query = select(DormRoom)
    if building_id is not None:
        query = query.where(DormRoom.building_id == building_id)
    if room_type is not None:
        query = query.where(DormRoom.room_type == room_type)
    if is_active is not None:
        query = query.where(DormRoom.is_active == is_active)
    if available_only:
        query = query.where(DormRoom.occupied_beds < DormRoom.capacity)

    query = query.order_by(DormRoom.floor_number, DormRoom.room_number).offset(offset).limit(limit)
    result = await session.exec(query)
    return result.all()


# ── Bed Allocation Engine ──

async def allocate_bed(
    session: AsyncSession,
    payload: BedAllocationCreate,
    allocated_by_user_id: Optional[int] = None,
) -> BedAllocation:
    room = await session.get(DormRoom, payload.room_id)
    if not room or not room.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dorm room not found or inactive.")

    # 1. Capacity check
    if room.occupied_beds >= room.capacity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Room {room.room_number} is at maximum capacity ({room.capacity}/{room.capacity} beds occupied).",
        )

    # 2. Check if student already has an active allocation
    active_student_alloc = (
        await session.exec(
            select(BedAllocation).where(
                BedAllocation.student_id == payload.student_id,
                BedAllocation.status == AllocationStatusEnum.ACTIVE,
            )
        )
    ).first()
    if active_student_alloc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Student ID {payload.student_id} already has an active bed allocation (ID {active_student_alloc.id}).",
        )

    # 3. Check if specific bed number in room is already occupied
    bed_conflict = (
        await session.exec(
            select(BedAllocation).where(
                BedAllocation.room_id == payload.room_id,
                BedAllocation.bed_number == payload.bed_number.strip(),
                BedAllocation.status == AllocationStatusEnum.ACTIVE,
            )
        )
    ).first()
    if bed_conflict:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Bed '{payload.bed_number}' in room {room.room_number} is already occupied.",
        )

    fee_charged = payload.fee_charged if payload.fee_charged > 0 else room.base_fee_per_term

    allocation = BedAllocation(
        room_id=payload.room_id,
        student_id=payload.student_id,
        bed_number=payload.bed_number.strip(),
        start_date=payload.start_date,
        end_date=payload.end_date,
        status=AllocationStatusEnum.ACTIVE,
        fee_charged=fee_charged,
        allocated_by_user_id=allocated_by_user_id,
        notes=payload.notes,
    )
    session.add(allocation)

    # Increment room occupied beds
    room.occupied_beds += 1
    room.updated_at = datetime.datetime.now(datetime.timezone.utc)
    session.add(room)

    await session.commit()
    await session.refresh(allocation)
    return allocation


async def vacate_bed(
    session: AsyncSession,
    allocation_id: int,
    payload: BedVacateRequest,
) -> BedAllocation:
    allocation = await session.get(BedAllocation, allocation_id)
    if not allocation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bed allocation not found.")

    if allocation.status != AllocationStatusEnum.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot vacate allocation in status '{allocation.status.value}'. Only ACTIVE allocations can be vacated.",
        )

    allocation.status = AllocationStatusEnum.VACATED
    allocation.end_date = payload.vacate_date
    if payload.notes:
        allocation.notes = (allocation.notes or "") + f" | Vacated: {payload.notes}"
    allocation.updated_at = datetime.datetime.now(datetime.timezone.utc)
    session.add(allocation)

    # Decrement room occupied beds
    room = await session.get(DormRoom, allocation.room_id)
    if room:
        room.occupied_beds = max(0, room.occupied_beds - 1)
        room.updated_at = datetime.datetime.now(datetime.timezone.utc)
        session.add(room)

    await session.commit()
    await session.refresh(allocation)
    return allocation


async def transfer_bed(
    session: AsyncSession,
    allocation_id: int,
    payload: BedTransferRequest,
    performed_by_user_id: Optional[int] = None,
) -> BedAllocation:
    old_alloc = await session.get(BedAllocation, allocation_id)
    if not old_alloc or old_alloc.status != AllocationStatusEnum.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Allocation not found or is not currently ACTIVE.",
        )

    new_room = await session.get(DormRoom, payload.new_room_id)
    if not new_room or not new_room.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Destination dorm room not found or inactive.")

    if new_room.occupied_beds >= new_room.capacity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Destination room {new_room.room_number} is full ({new_room.occupied_beds}/{new_room.capacity}).",
        )

    # Check if bed in new room is taken
    bed_conflict = (
        await session.exec(
            select(BedAllocation).where(
                BedAllocation.room_id == payload.new_room_id,
                BedAllocation.bed_number == payload.new_bed_number.strip(),
                BedAllocation.status == AllocationStatusEnum.ACTIVE,
            )
        )
    ).first()
    if bed_conflict:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Bed '{payload.new_bed_number}' in destination room is already occupied.",
        )

    # 1. Close old allocation
    old_alloc.status = AllocationStatusEnum.TRANSFERRED
    old_alloc.end_date = payload.effective_date
    old_alloc.notes = (old_alloc.notes or "") + f" | Transferred to Room {new_room.room_number} Bed {payload.new_bed_number}"
    old_alloc.updated_at = datetime.datetime.now(datetime.timezone.utc)
    session.add(old_alloc)

    old_room = await session.get(DormRoom, old_alloc.room_id)
    if old_room:
        old_room.occupied_beds = max(0, old_room.occupied_beds - 1)
        session.add(old_room)

    # 2. Create new allocation
    new_alloc = BedAllocation(
        room_id=new_room.id,
        student_id=old_alloc.student_id,
        bed_number=payload.new_bed_number.strip(),
        start_date=payload.effective_date,
        status=AllocationStatusEnum.ACTIVE,
        fee_charged=new_room.base_fee_per_term,
        allocated_by_user_id=performed_by_user_id,
        notes=payload.notes or f"Transferred from Room {old_room.room_number if old_room else 'unknown'}",
    )
    session.add(new_alloc)

    new_room.occupied_beds += 1
    session.add(new_room)

    await session.commit()
    await session.refresh(new_alloc)
    return new_alloc


async def list_bed_allocations(
    session: AsyncSession,
    building_id: Optional[int] = None,
    room_id: Optional[int] = None,
    student_id: Optional[int] = None,
    status_filter: Optional[AllocationStatusEnum] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[BedAllocation]:
    query = select(BedAllocation)
    if room_id is not None:
        query = query.where(BedAllocation.room_id == room_id)
    if student_id is not None:
        query = query.where(BedAllocation.student_id == student_id)
    if status_filter is not None:
        query = query.where(BedAllocation.status == status_filter)
    if building_id is not None:
        # Join with DormRoom to filter by building
        query = query.join(DormRoom, BedAllocation.room_id == DormRoom.id).where(DormRoom.building_id == building_id)

    query = query.order_by(BedAllocation.created_at.desc()).offset(offset).limit(limit)
    result = await session.exec(query)
    return result.all()


# ── Curfew Logs & Violation Tracking ──

async def create_curfew_log(
    session: AsyncSession,
    payload: CurfewLogCreate,
    reported_by_user_id: Optional[int] = None,
) -> CurfewLog:
    # Check if late
    is_late = payload.is_late
    late_min = payload.late_minutes

    if payload.actual_entry_time and payload.expected_entry_time and not payload.is_absent:
        try:
            exp_h, exp_m = map(int, payload.expected_entry_time.split(":")[:2])
            act_h, act_m = map(int, payload.actual_entry_time.split(":")[:2])
            exp_total = exp_h * 60 + exp_m
            act_total = act_h * 60 + act_m
            if act_total > exp_total:
                is_late = True
                late_min = act_total - exp_total
        except Exception:
            pass

    curfew = CurfewLog(
        student_id=payload.student_id,
        building_id=payload.building_id,
        log_date=payload.log_date,
        expected_entry_time=payload.expected_entry_time,
        actual_entry_time=payload.actual_entry_time,
        is_late=is_late,
        is_absent=payload.is_absent,
        late_minutes=late_min,
        reason=payload.reason,
        action_taken=payload.action_taken,
        reported_by_user_id=reported_by_user_id,
    )
    session.add(curfew)
    await session.commit()
    await session.refresh(curfew)
    return curfew


async def list_curfew_logs(
    session: AsyncSession,
    student_id: Optional[int] = None,
    building_id: Optional[int] = None,
    date_from: Optional[datetime.date] = None,
    date_to: Optional[datetime.date] = None,
    violations_only: bool = False,
    limit: int = 100,
    offset: int = 0,
) -> List[CurfewLog]:
    query = select(CurfewLog)
    if student_id is not None:
        query = query.where(CurfewLog.student_id == student_id)
    if building_id is not None:
        query = query.where(CurfewLog.building_id == building_id)
    if date_from is not None:
        query = query.where(CurfewLog.log_date >= date_from)
    if date_to is not None:
        query = query.where(CurfewLog.log_date <= date_to)
    if violations_only:
        query = query.where(or_(CurfewLog.is_late == True, CurfewLog.is_absent == True))

    query = query.order_by(CurfewLog.log_date.desc(), CurfewLog.created_at.desc()).offset(offset).limit(limit)
    result = await session.exec(query)
    return result.all()


# ── Room Inspections ──

async def create_room_inspection(
    session: AsyncSession,
    payload: RoomInspectionCreate,
    inspected_by_user_id: Optional[int] = None,
) -> RoomInspection:
    room = await session.get(DormRoom, payload.room_id)
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dorm room not found.")

    inspection = RoomInspection(
        room_id=payload.room_id,
        inspection_date=payload.inspection_date,
        cleanliness_score=payload.cleanliness_score,
        maintenance_status=payload.maintenance_status,
        issues_found=payload.issues_found,
        action_required=payload.action_required,
        inspected_by_user_id=inspected_by_user_id,
    )
    session.add(inspection)
    await session.commit()
    await session.refresh(inspection)
    return inspection


async def list_room_inspections(
    session: AsyncSession,
    room_id: Optional[int] = None,
    building_id: Optional[int] = None,
    maintenance_status: Optional[InspectionStatusEnum] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[RoomInspection]:
    query = select(RoomInspection)
    if room_id is not None:
        query = query.where(RoomInspection.room_id == room_id)
    if maintenance_status is not None:
        query = query.where(RoomInspection.maintenance_status == maintenance_status)
    if building_id is not None:
        query = query.join(DormRoom, RoomInspection.room_id == DormRoom.id).where(DormRoom.building_id == building_id)

    query = query.order_by(RoomInspection.inspection_date.desc()).offset(offset).limit(limit)
    result = await session.exec(query)
    return result.all()


# ── Hostel Overview & Occupancy Stats ──

async def get_hostel_overview(
    session: AsyncSession,
    campus_id: Optional[int] = None,
) -> HostelOverviewRead:
    b_query = select(HostelBuilding).where(HostelBuilding.is_active == True)
    if campus_id is not None:
        b_query = b_query.where(HostelBuilding.campus_id == campus_id)
    buildings = (await session.exec(b_query)).all()

    building_stats: List[BuildingOccupancyRead] = []
    total_rooms_all = 0
    total_capacity_all = 0
    total_occupied_all = 0

    for b in buildings:
        rooms = (await session.exec(select(DormRoom).where(DormRoom.building_id == b.id, DormRoom.is_active == True))).all()
        b_rooms = len(rooms)
        b_capacity = sum(r.capacity for r in rooms)
        b_occupied = sum(r.occupied_beds for r in rooms)
        b_avail = max(0, b_capacity - b_occupied)
        b_rate = round((b_occupied / b_capacity * 100.0), 1) if b_capacity > 0 else 0.0

        total_rooms_all += b_rooms
        total_capacity_all += b_capacity
        total_occupied_all += b_occupied

        building_stats.append(
            BuildingOccupancyRead(
                building_id=b.id,
                building_name=b.name,
                building_code=b.building_code,
                gender=b.gender,
                total_rooms=b_rooms,
                total_capacity=b_capacity,
                occupied_beds=b_occupied,
                available_beds=b_avail,
                occupancy_rate=b_rate,
            )
        )

    overall_rate = round((total_occupied_all / total_capacity_all * 100.0), 1) if total_capacity_all > 0 else 0.0
    total_avail_all = max(0, total_capacity_all - total_occupied_all)

    # 30-day late curfew incidents
    cutoff = datetime.date.today() - datetime.timedelta(days=30)
    curfew_query = select(CurfewLog).where(
        CurfewLog.log_date >= cutoff,
        or_(CurfewLog.is_late == True, CurfewLog.is_absent == True),
    )
    late_incidents = len((await session.exec(curfew_query)).all())

    # Pending maintenance repairs
    repair_query = select(RoomInspection).where(
        RoomInspection.maintenance_status.in_([InspectionStatusEnum.FAILED, InspectionStatusEnum.NEEDS_REPAIR])
    )
    pending_repairs = len((await session.exec(repair_query)).all())

    return HostelOverviewRead(
        total_buildings=len(buildings),
        total_rooms=total_rooms_all,
        total_capacity=total_capacity_all,
        total_occupied_beds=total_occupied_all,
        total_available_beds=total_avail_all,
        overall_occupancy_rate=overall_rate,
        late_curfew_incidents_30d=late_incidents,
        pending_repairs_count=pending_repairs,
        buildings=building_stats,
    )
