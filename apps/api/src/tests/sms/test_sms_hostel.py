import datetime
import pytest
from fastapi import HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_hostel import (
    AllocationStatusEnum,
    HostelGenderEnum,
    InspectionStatusEnum,
    RoomTypeEnum,
)
from src.schemas.sms.hostel import (
    BedAllocationCreate,
    BedTransferRequest,
    BedVacateRequest,
    CurfewLogCreate,
    DormRoomCreate,
    DormRoomUpdate,
    HostelBuildingCreate,
    HostelBuildingUpdate,
    RoomInspectionCreate,
)
from src.routers.sms_hostel import (
    allocate_bed_endpoint,
    create_building_endpoint,
    create_curfew_log_endpoint,
    create_inspection_endpoint,
    create_room_endpoint,
    delete_building_endpoint,
    delete_room_endpoint,
    get_building_endpoint,
    get_overview_endpoint,
    get_room_endpoint,
    list_allocations_endpoint,
    list_buildings_endpoint,
    list_curfew_logs_endpoint,
    list_inspections_endpoint,
    list_rooms_endpoint,
    transfer_bed_endpoint,
    update_building_endpoint,
    update_room_endpoint,
    vacate_bed_endpoint,
)
from src.tests.sms._principals import SUPERADMIN


@pytest.mark.asyncio
async def test_hostel_building_and_room_crud(db: AsyncSession):
    """Test creating, listing, updating, and deleting hostel buildings and dorm rooms."""
    # 1. Create Building
    building = await create_building_endpoint(
        payload=HostelBuildingCreate(
            campus_id=1,
            name="Cedar Hall (Boys Hostel)",
            building_code="BLD-CEDAR-01",
            gender=HostelGenderEnum.MALE,
            warden_name="Mr. Arthur Pendelton",
            warden_contact="+1555019283",
            warden_email="warden.cedar@csg.edu",
            total_floors=3,
        ),
        session=db,
        principal=SUPERADMIN,
    )
    assert building.id is not None
    assert building.building_code == "BLD-CEDAR-01"

    # 2. Duplicate building code rejected
    with pytest.raises(HTTPException) as exc_info:
        await create_building_endpoint(
            payload=HostelBuildingCreate(
                campus_id=1,
                name="Another Building",
                building_code="BLD-CEDAR-01",
            ),
            session=db,
            principal=SUPERADMIN,
        )
    assert exc_info.value.status_code == 400

    # 3. Create Dorm Rooms
    room1 = await create_room_endpoint(
        payload=DormRoomCreate(
            building_id=building.id,
            room_number="101",
            floor_number=1,
            room_type=RoomTypeEnum.DOUBLE,
            capacity=2,
            base_fee_per_term=500.0,
            is_ac=True,
            has_attached_bath=True,
        ),
        session=db,
        principal=SUPERADMIN,
    )
    assert room1.id is not None
    assert room1.capacity == 2
    assert room1.available_beds == 2

    room2 = await create_room_endpoint(
        payload=DormRoomCreate(
            building_id=building.id,
            room_number="102",
            floor_number=1,
            room_type=RoomTypeEnum.SINGLE,
            capacity=1,
            base_fee_per_term=800.0,
        ),
        session=db,
        principal=SUPERADMIN,
    )
    assert room2.id is not None

    # 4. List rooms
    rooms = await list_rooms_endpoint(building_id=building.id, session=db, principal=SUPERADMIN, limit=100, offset=0)
    assert len(rooms) == 2

    # 5. Update room
    updated_room = await update_room_endpoint(
        room_id=room1.id,
        payload=DormRoomUpdate(base_fee_per_term=550.0),
        session=db,
        principal=SUPERADMIN,
    )
    assert updated_room.base_fee_per_term == 550.0

    # 6. Delete empty room
    await delete_room_endpoint(room_id=room2.id, session=db, principal=SUPERADMIN)
    with pytest.raises(HTTPException) as exc_info:
        await get_room_endpoint(room_id=room2.id, session=db, principal=SUPERADMIN)
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_bed_allocation_engine_lifecycle(db: AsyncSession):
    """Test bed allocation, capacity enforcement, duplicate prevention, bed vacation, and room transfers."""
    # 1. Setup building and 2 rooms
    building = await create_building_endpoint(
        payload=HostelBuildingCreate(
            campus_id=1,
            name="Pine Hall",
            building_code="BLD-PINE",
            gender=HostelGenderEnum.FEMALE,
            total_floors=2,
        ),
        session=db,
        principal=SUPERADMIN,
    )
    roomA = await create_room_endpoint(
        payload=DormRoomCreate(
            building_id=building.id,
            room_number="201",
            floor_number=2,
            room_type=RoomTypeEnum.DOUBLE,
            capacity=2,
            base_fee_per_term=600.0,
        ),
        session=db,
        principal=SUPERADMIN,
    )
    roomB = await create_room_endpoint(
        payload=DormRoomCreate(
            building_id=building.id,
            room_number="202",
            floor_number=2,
            room_type=RoomTypeEnum.DOUBLE,
            capacity=2,
            base_fee_per_term=600.0,
        ),
        session=db,
        principal=SUPERADMIN,
    )

    # 2. Allocate Bed 1 to Student 101
    alloc1 = await allocate_bed_endpoint(
        payload=BedAllocationCreate(
            room_id=roomA.id,
            student_id=101,
            bed_number="Bed-A",
            start_date=datetime.date(2026, 9, 1),
        ),
        session=db,
        principal=SUPERADMIN,
    )
    assert alloc1.id is not None
    assert alloc1.status == AllocationStatusEnum.ACTIVE

    # Check room occupied beds incremented
    rA_check = await get_room_endpoint(room_id=roomA.id, session=db, principal=SUPERADMIN)
    assert rA_check.occupied_beds == 1
    assert rA_check.available_beds == 1

    # 3. Duplicate student allocation rejected
    with pytest.raises(HTTPException) as exc_info:
        await allocate_bed_endpoint(
            payload=BedAllocationCreate(
                room_id=roomB.id,
                student_id=101,
                bed_number="Bed-A",
            ),
            session=db,
            principal=SUPERADMIN,
        )
    assert exc_info.value.status_code == 400
    assert "already has an active bed allocation" in exc_info.value.detail

    # 4. Allocate Bed 2 to Student 102 in Room A (Room A is now full)
    alloc2 = await allocate_bed_endpoint(
        payload=BedAllocationCreate(
            room_id=roomA.id,
            student_id=102,
            bed_number="Bed-B",
        ),
        session=db,
        principal=SUPERADMIN,
    )
    assert alloc2.id is not None

    rA_check2 = await get_room_endpoint(room_id=roomA.id, session=db, principal=SUPERADMIN)
    assert rA_check2.occupied_beds == 2
    assert rA_check2.available_beds == 0

    # 5. Overbooking prevention: 3rd student into 2-bed room fails
    with pytest.raises(HTTPException) as exc_info:
        await allocate_bed_endpoint(
            payload=BedAllocationCreate(
                room_id=roomA.id,
                student_id=103,
                bed_number="Bed-C",
            ),
            session=db,
            principal=SUPERADMIN,
        )
    assert exc_info.value.status_code == 400
    assert "maximum capacity" in exc_info.value.detail

    # 6. Transfer Student 101 from Room A to Room B
    transferred = await transfer_bed_endpoint(
        allocation_id=alloc1.id,
        payload=BedTransferRequest(
            new_room_id=roomB.id,
            new_bed_number="Bed-1",
            effective_date=datetime.date(2026, 9, 15),
            notes="Transferred due to study group preference",
        ),
        session=db,
        principal=SUPERADMIN,
    )
    assert transferred.id is not None
    assert transferred.room_id == roomB.id
    assert transferred.status == AllocationStatusEnum.ACTIVE

    # Verify Room A now has 1 occupant, Room B has 1 occupant
    rA_post = await get_room_endpoint(room_id=roomA.id, session=db, principal=SUPERADMIN)
    rB_post = await get_room_endpoint(room_id=roomB.id, session=db, principal=SUPERADMIN)
    assert rA_post.occupied_beds == 1
    assert rB_post.occupied_beds == 1

    # 7. Vacate Student 102
    vacated = await vacate_bed_endpoint(
        allocation_id=alloc2.id,
        payload=BedVacateRequest(
            vacate_date=datetime.date(2026, 12, 15),
            notes="Term finished, graduated",
        ),
        session=db,
        principal=SUPERADMIN,
    )
    assert vacated.status == AllocationStatusEnum.VACATED

    rA_final = await get_room_endpoint(room_id=roomA.id, session=db, principal=SUPERADMIN)
    assert rA_final.occupied_beds == 0
    assert rA_final.available_beds == 2


@pytest.mark.asyncio
async def test_curfew_and_inspection_tracking(db: AsyncSession):
    """Test curfew check-ins, late violation calculations, and room inspections."""
    building = await create_building_endpoint(
        payload=HostelBuildingCreate(
            campus_id=1,
            name="Maple Dorm",
            building_code="BLD-MAPLE",
        ),
        session=db,
        principal=SUPERADMIN,
    )
    room = await create_room_endpoint(
        payload=DormRoomCreate(
            building_id=building.id,
            room_number="301",
            capacity=2,
        ),
        session=db,
        principal=SUPERADMIN,
    )

    # 1. On-time Curfew Log
    c1 = await create_curfew_log_endpoint(
        payload=CurfewLogCreate(
            student_id=201,
            building_id=building.id,
            log_date=datetime.date.today(),
            expected_entry_time="21:00",
            actual_entry_time="20:45",
        ),
        session=db,
        principal=SUPERADMIN,
    )
    assert c1.is_late is False
    assert c1.late_minutes == 0

    # 2. Late Curfew Log (Arrived 21:40 vs 21:00 curfew -> 40 minutes late)
    c2 = await create_curfew_log_endpoint(
        payload=CurfewLogCreate(
            student_id=202,
            building_id=building.id,
            log_date=datetime.date.today(),
            expected_entry_time="21:00",
            actual_entry_time="21:40",
            reason="Bus breakdown returning from debate tournament",
            action_taken="Warning note added to guardian digest",
        ),
        session=db,
        principal=SUPERADMIN,
    )
    assert c2.is_late is True
    assert c2.late_minutes == 40

    # 3. Query Violations only
    violations = await list_curfew_logs_endpoint(
        building_id=building.id,
        violations_only=True,
        session=db,
        principal=SUPERADMIN,
        limit=100,
offset=0,
    )
    assert len(violations) == 1
    assert violations[0].student_id == 202

    # 4. Room Inspection
    insp = await create_inspection_endpoint(
        payload=RoomInspectionCreate(
            room_id=room.id,
            inspection_date=datetime.date.today(),
            cleanliness_score=8,
            maintenance_status=InspectionStatusEnum.NEEDS_REPAIR,
            issues_found="Ceiling fan wobbling on high speed",
            action_required="Electrician dispatched",
        ),
        session=db,
        principal=SUPERADMIN,
    )
    assert insp.id is not None
    assert insp.maintenance_status == InspectionStatusEnum.NEEDS_REPAIR

    # 5. List inspections
    inspections = await list_inspections_endpoint(
        room_id=room.id,
        session=db,
        principal=SUPERADMIN,
        limit=100,
offset=0,
    )
    assert len(inspections) == 1
    assert inspections[0].cleanliness_score == 8

    # 6. Overview & Occupancy Stats
    overview = await get_overview_endpoint(campus_id=1, session=db, principal=SUPERADMIN)
    assert overview.total_buildings >= 1
    assert overview.total_rooms >= 1
    assert overview.pending_repairs_count >= 1
