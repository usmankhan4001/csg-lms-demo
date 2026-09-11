import datetime
import pytest
from fastapi import HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_hr import ContractType, LeaveStatus, LeaveType
from src.db.sms_payroll import SalaryPaymentStatus
from src.schemas.sms_hr import (
    StaffLeaveActionRequest,
    StaffLeaveCreate,
    StaffProfileCreate,
    StaffProfileUpdate,
)
from src.schemas.sms_payroll import (
    BatchSalarySlipGenerateRequest,
    ProcessSalaryPaymentRequest,
    SalaryStructureCreate,
)
from src.routers.sms_hr import (
    apply_staff_leave,
    create_staff_profile,
    get_staff_profile,
    list_staff_leaves,
    list_staff_profiles,
    update_leave_status,
    update_staff_profile,
)
from src.routers.sms_payroll import (
    create_or_update_salary_structure,
    generate_salary_slips_batch,
    get_salary_slip,
    get_staff_salary_structure,
    list_salary_slips,
    record_salary_payment,
)


@pytest.mark.asyncio
async def test_hr_faculty_management_lifecycle(db: AsyncSession):
    """Test Staff registration, profile management, and leave workflow."""
    # 1. Register Staff Profile
    staff_payload = StaffProfileCreate(
        employee_code="EMP-2026-001",
        full_name="Dr. Alan Turing",
        designation="Professor of Computer Science",
        department="Computer Science",
        joining_date=datetime.date(2025, 8, 1),
        contract_type=ContractType.PERMANENT,
        basic_salary=75000.0,
        campus_id=1,
        email="alan.turing@csg-lms.edu",
        phone="+1-555-0199",
    )
    staff = await create_staff_profile(payload=staff_payload, session=db)
    assert staff.id is not None
    assert staff.employee_code == "EMP-2026-001"
    assert staff.full_name == "Dr. Alan Turing"
    assert staff.basic_salary == 75000.0

    # 2. Duplicate Employee Code check
    with pytest.raises(HTTPException) as exc_info:
        await create_staff_profile(payload=staff_payload, session=db)
    assert exc_info.value.status_code == 400

    # 3. Update Staff Profile
    updated = await update_staff_profile(
        staff_id=staff.id,
        payload=StaffProfileUpdate(designation="Head of Department"),
        session=db,
    )
    assert updated.designation == "Head of Department"

    # 4. List Staff Directory
    staff_list = await list_staff_profiles(campus_id=1, department="Computer Science", session=db)
    assert len(staff_list) == 1
    assert staff_list[0].id == staff.id

    # 5. Apply for Staff Leave (Annual Leave: 5 days)
    leave_payload = StaffLeaveCreate(
        staff_id=staff.id,
        leave_type=LeaveType.ANNUAL,
        start_date=datetime.date(2026, 10, 1),
        end_date=datetime.date(2026, 10, 5),
        reason="Attending international computing conference",
    )
    leave = await apply_staff_leave(payload=leave_payload, session=db)
    assert leave.id is not None
    assert leave.status == LeaveStatus.PENDING

    # 6. Approve Staff Leave
    approved_leave = await update_leave_status(
        leave_id=leave.id,
        payload=StaffLeaveActionRequest(
            status=LeaveStatus.APPROVED,
            approved_by=10,
        ),
        session=db,
    )
    assert approved_leave.status == LeaveStatus.APPROVED
    assert approved_leave.approved_by == 10

    # 7. List leaves by status
    leaves = await list_staff_leaves(staff_id=staff.id, status_filter=LeaveStatus.APPROVED, session=db)
    assert len(leaves) == 1


@pytest.mark.asyncio
async def test_payroll_salary_structure_and_batch_slips(db: AsyncSession):
    """Test salary structure configuration, batch monthly slip generation, and disbursement."""
    # 1. Create two staff members
    s1 = await create_staff_profile(
        payload=StaffProfileCreate(
            employee_code="FAC-010",
            full_name="Grace Hopper",
            designation="Senior Lecturer",
            department="Mathematics",
            joining_date=datetime.date(2024, 1, 15),
            contract_type=ContractType.PERMANENT,
            basic_salary=60000.0,
            campus_id=1,
        ),
        session=db,
    )
    s2 = await create_staff_profile(
        payload=StaffProfileCreate(
            employee_code="FAC-020",
            full_name="Ada Lovelace",
            designation="Lecturer",
            department="Mathematics",
            joining_date=datetime.date(2024, 6, 1),
            contract_type=ContractType.PERMANENT,
            basic_salary=50000.0,
            campus_id=1,
        ),
        session=db,
    )

    # 2. Configure Salary Structure for Grace Hopper
    # Basic: 60000, Housing: 15000, Medical: 5000 -> Gross = 80000
    # Tax: 4000, Provident Fund: 3000 -> Deductions = 7000 -> Net = 73000
    struct_payload = SalaryStructureCreate(
        staff_id=s1.id,
        basic=60000.0,
        housing_allowance=15000.0,
        medical_allowance=5000.0,
        other_allowances=0.0,
        tax_deduction=4000.0,
        provident_fund=3000.0,
        other_deductions=0.0,
    )
    struct1 = await create_or_update_salary_structure(payload=struct_payload, session=db)
    assert struct1.gross_salary == 80000.0
    assert struct1.total_deductions == 7000.0
    assert struct1.net_salary == 73000.0

    fetched_struct = await get_staff_salary_structure(staff_id=s1.id, session=db)
    assert fetched_struct.net_salary == 73000.0

    # 3. Batch Generate Monthly Salary Slips for September 2026 (Month 9, Year 2026)
    gen_payload = BatchSalarySlipGenerateRequest(
        month=9,
        year=2026,
        campus_id=1,
        staff_ids=[s1.id, s2.id],
        remarks="September 2026 Faculty Payroll Run",
    )
    slips = await generate_salary_slips_batch(payload=gen_payload, session=db)
    assert len(slips) == 2

    slip_map = {s.staff_id: s for s in slips}

    # Verify Grace's slip uses configured structure
    s1_slip = slip_map[s1.id]
    assert s1_slip.gross_salary == 80000.0
    assert s1_slip.total_deductions == 7000.0
    assert s1_slip.net_salary == 73000.0
    assert s1_slip.payment_status == SalaryPaymentStatus.PENDING
    assert s1_slip.slip_no.startswith("SLIP-202609-")

    # Verify Ada's slip uses fallback basic_salary
    s2_slip = slip_map[s2.id]
    assert s2_slip.basic == 50000.0
    assert s2_slip.gross_salary == 50000.0
    assert s2_slip.total_deductions == 0.0
    assert s2_slip.net_salary == 50000.0

    # 4. Disburse / Pay Salary Slip for Grace Hopper
    paid_slip = await record_salary_payment(
        slip_id=s1_slip.id,
        payload=ProcessSalaryPaymentRequest(
            payment_date=datetime.date(2026, 9, 30),
            payment_method="DIRECT_DEPOSIT",
            remarks="Processed via Corporate Bank Batch #441",
        ),
        session=db,
    )
    assert paid_slip.payment_status == SalaryPaymentStatus.PAID
    assert paid_slip.payment_date == datetime.date(2026, 9, 30)
    assert paid_slip.payment_method == "DIRECT_DEPOSIT"

    # 5. List slips filtered by payment status
    paid_slips = await list_salary_slips(month=9, year=2026, payment_status=SalaryPaymentStatus.PAID, session=db)
    assert len(paid_slips) == 1
    assert paid_slips[0].id == s1_slip.id

    pending_slips = await list_salary_slips(month=9, year=2026, payment_status=SalaryPaymentStatus.PENDING, session=db)
    assert len(pending_slips) == 1
    assert pending_slips[0].id == s2_slip.id
