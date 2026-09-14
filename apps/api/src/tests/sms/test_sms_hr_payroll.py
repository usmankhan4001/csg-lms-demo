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
from src.schemas.sms_hr_extended import PayrollApprovalRequest
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
    approve_salary_slips,
    create_or_update_salary_structure,
    generate_salary_slips_batch,
    get_salary_slip,
    get_staff_salary_structure,
    list_salary_slips,
    record_salary_payment,
)

def _admin_principal(user_id: int = 1):
    """A resolved SCHOOL_ADMIN principal.

    These tests call the handlers directly, so FastAPI's DI never runs and the
    `principal` default would arrive as an unresolved `Depends`. HR writes are
    now role-gated (personnel files carry basic_salary) and leave requests are
    bound to the caller, so the caller has to be real here.
    """
    from types import SimpleNamespace

    return SimpleNamespace(
        is_superadmin=False,
        campus_id=None,
        has_any_role=lambda wanted: "SCHOOL_ADMIN" in wanted,
        has_role=lambda r: r == "SCHOOL_ADMIN",
        raw_claims={"lh_user_id": user_id},
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
    staff = await create_staff_profile(payload=staff_payload, session=db, principal=_admin_principal())
    assert staff.id is not None
    assert staff.employee_code == "EMP-2026-001"
    assert staff.full_name == "Dr. Alan Turing"
    assert staff.basic_salary == 75000.0

    # 2. Duplicate Employee Code check
    with pytest.raises(HTTPException) as exc_info:
        await create_staff_profile(payload=staff_payload, session=db, principal=_admin_principal())
    assert exc_info.value.status_code == 400

    # 3. Update Staff Profile
    updated = await update_staff_profile(
        staff_id=staff.id,
        payload=StaffProfileUpdate(designation="Head of Department"),
        session=db,
        principal=_admin_principal(),
    )
    assert updated.designation == "Head of Department"

    # 4. List Staff Directory
    staff_list = await list_staff_profiles(campus_id=1, department="Computer Science", session=db, principal=_admin_principal())
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
    leave = await apply_staff_leave(payload=leave_payload, session=db, principal=_admin_principal())
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
        principal=_admin_principal(),
    )
    assert approved_leave.status == LeaveStatus.APPROVED
    # The approver is the AUTHENTICATED caller, not whatever the payload said.
    # This test used to pass approved_by=10 and assert it came back; that was
    # the forgery -- a caller could attribute their own approval to someone
    # else, defeating the audit trail this column exists for. The principal
    # here is user 1, and the payload's 10 is correctly ignored.
    assert approved_leave.approved_by == 1

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
        principal=_admin_principal(),
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
        principal=_admin_principal(),
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
    struct1 = await create_or_update_salary_structure(payload=struct_payload, session=db, principal=_admin_principal())
    assert struct1.gross_salary == 80000.0
    assert struct1.total_deductions == 7000.0
    assert struct1.net_salary == 73000.0

    fetched_struct = await get_staff_salary_structure(staff_id=s1.id, session=db, principal=_admin_principal())
    assert fetched_struct.net_salary == 73000.0

    # 3. Batch Generate Monthly Salary Slips for September 2026 (Month 9, Year 2026)
    gen_payload = BatchSalarySlipGenerateRequest(
        month=9,
        year=2026,
        campus_id=1,
        staff_ids=[s1.id, s2.id],
        remarks="September 2026 Faculty Payroll Run",
    )
    slips = await generate_salary_slips_batch(payload=gen_payload, session=db, principal=_admin_principal())
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

    # 4. Approve, then disburse.
    #
    # This step is NEW. The test previously walked generate -> pay directly,
    # which was the self-dealing path: one person could set a salary structure,
    # generate the slip and mark it paid with no second party. Payment now
    # requires prior approval by someone OTHER than the preparer, so the test
    # has to model a real second reviewer. The default principal (user 1)
    # generated these slips, so user 2 approves them.
    approval = await approve_salary_slips(
        payload=PayrollApprovalRequest(slip_ids=[s1_slip.id]),
        session=db,
        principal=_admin_principal(user_id=2),
    )
    assert approval.results[0].outcome == "approved"

    paid_slip = await record_salary_payment(
        slip_id=s1_slip.id,
        payload=ProcessSalaryPaymentRequest(
            payment_date=datetime.date(2026, 9, 30),
            payment_method="DIRECT_DEPOSIT",
            remarks="Processed via Corporate Bank Batch #441",
        ),
        session=db,
        principal=_admin_principal(),
    )
    assert paid_slip.payment_status == SalaryPaymentStatus.PAID
    assert paid_slip.payment_date == datetime.date(2026, 9, 30)
    assert paid_slip.payment_method == "DIRECT_DEPOSIT"

    # 5. List slips filtered by payment status
    paid_slips = await list_salary_slips(month=9, year=2026, payment_status=SalaryPaymentStatus.PAID, session=db, principal=_admin_principal())
    assert len(paid_slips) == 1
    assert paid_slips[0].id == s1_slip.id

    pending_slips = await list_salary_slips(month=9, year=2026, payment_status=SalaryPaymentStatus.PENDING, session=db, principal=_admin_principal())
    assert len(pending_slips) == 1
    assert pending_slips[0].id == s2_slip.id


# ── Unpaid Leave Deduction & PII Masking (M11) ──

async def _staff_with_salary(db: AsyncSession, code: str, basic: float = 30000.0):
    """Staff member on a known basic salary, so the daily rate is exact:
    30000 / 30 days = 1000.00 per unpaid day."""
    staff = await create_staff_profile(
        payload=StaffProfileCreate(
            employee_code=code,
            full_name=f"Staff {code}",
            designation="Teacher",
            department="Science",
            joining_date=datetime.date(2026, 1, 1),
            contract_type=ContractType.PERMANENT,
            basic_salary=basic,
            campus_id=5,
        ),
        session=db,
        principal=_admin_principal(),
    )
    await create_or_update_salary_structure(
        payload=SalaryStructureCreate(
            staff_id=staff.id,
            basic=basic,
            housing_allowance=0.0,
            medical_allowance=0.0,
            other_allowances=0.0,
            tax_deduction=0.0,
            provident_fund=0.0,
            other_deductions=0.0,
        ),
        session=db,
        principal=_admin_principal(),
    )
    return staff


async def _approved_unpaid_leave(db: AsyncSession, staff_id: int, start: datetime.date, end: datetime.date):
    leave = await apply_staff_leave(
        payload=StaffLeaveCreate(
            staff_id=staff_id,
            leave_type=LeaveType.UNPAID,
            start_date=start,
            end_date=end,
            reason="Unpaid personal leave",
        ),
        session=db,
        principal=_admin_principal(),
    )
    await update_leave_status(
        leave_id=leave.id,
        payload=StaffLeaveActionRequest(status=LeaveStatus.APPROVED, approved_by=1),
        session=db,
        principal=_admin_principal(),
    )
    return leave


@pytest.mark.asyncio
async def test_approved_unpaid_leave_is_deducted_from_net_pay(db: AsyncSession):
    staff = await _staff_with_salary(db, "UL-001", basic=30000.0)
    # 3 unpaid days in June 2026.
    await _approved_unpaid_leave(db, staff.id, datetime.date(2026, 6, 10), datetime.date(2026, 6, 12))

    slips = await generate_salary_slips_batch(
        payload=BatchSalarySlipGenerateRequest(month=6, year=2026, staff_ids=[staff.id]),
        session=db,
        principal=_admin_principal(),
    )
    assert len(slips) == 1
    slip = slips[0]
    assert slip.unpaid_leave_days == 3
    # 30000/30 = 1000 per day x 3 days
    assert slip.unpaid_leave_deduction == 3000.0
    assert slip.total_deductions == 3000.0
    assert slip.gross_salary == 30000.0
    assert slip.net_salary == 27000.0


@pytest.mark.asyncio
async def test_paid_leave_types_are_not_deducted(db: AsyncSession):
    """Deducting for ANNUAL/SICK leave would silently turn paid leave unpaid."""
    staff = await _staff_with_salary(db, "UL-002", basic=30000.0)
    leave = await apply_staff_leave(
        payload=StaffLeaveCreate(
            staff_id=staff.id,
            leave_type=LeaveType.SICK,
            start_date=datetime.date(2026, 6, 1),
            end_date=datetime.date(2026, 6, 5),
        ),
        session=db,
        principal=_admin_principal(),
    )
    await update_leave_status(
        leave_id=leave.id,
        payload=StaffLeaveActionRequest(status=LeaveStatus.APPROVED, approved_by=1),
        session=db,
        principal=_admin_principal(),
    )

    slips = await generate_salary_slips_batch(
        payload=BatchSalarySlipGenerateRequest(month=6, year=2026, staff_ids=[staff.id]),
        session=db,
        principal=_admin_principal(),
    )
    assert slips[0].unpaid_leave_days == 0
    assert slips[0].net_salary == 30000.0


@pytest.mark.asyncio
async def test_pending_unpaid_leave_is_not_deducted(db: AsyncSession):
    """A request that may still be rejected must not dock pay."""
    staff = await _staff_with_salary(db, "UL-003", basic=30000.0)
    await apply_staff_leave(  # left PENDING, never approved
        payload=StaffLeaveCreate(
            staff_id=staff.id,
            leave_type=LeaveType.UNPAID,
            start_date=datetime.date(2026, 6, 10),
            end_date=datetime.date(2026, 6, 12),
        ),
        session=db,
        principal=_admin_principal(),
    )

    slips = await generate_salary_slips_batch(
        payload=BatchSalarySlipGenerateRequest(month=6, year=2026, staff_ids=[staff.id]),
        session=db,
        principal=_admin_principal(),
    )
    assert slips[0].unpaid_leave_days == 0
    assert slips[0].net_salary == 30000.0


@pytest.mark.asyncio
async def test_leave_spanning_month_boundary_is_clipped_to_the_pay_month(db: AsyncSession):
    """A leave straddling month-end must not be charged in full to both months."""
    staff = await _staff_with_salary(db, "UL-004", basic=30000.0)
    # 28 May - 3 June: 4 days in May (28,29,30,31), 3 days in June (1,2,3).
    await _approved_unpaid_leave(db, staff.id, datetime.date(2026, 5, 28), datetime.date(2026, 6, 3))

    may = await generate_salary_slips_batch(
        payload=BatchSalarySlipGenerateRequest(month=5, year=2026, staff_ids=[staff.id]),
        session=db,
        principal=_admin_principal(),
    )
    june = await generate_salary_slips_batch(
        payload=BatchSalarySlipGenerateRequest(month=6, year=2026, staff_ids=[staff.id]),
        session=db,
        principal=_admin_principal(),
    )
    assert may[0].unpaid_leave_days == 4
    assert june[0].unpaid_leave_days == 3


@pytest.mark.asyncio
async def test_salary_figures_are_masked_in_logs(db: AsyncSession):
    """An exact salary must never reach a log line."""
    from src.services.sms.payroll import _mask_amount

    masked = _mask_amount(27000.0)
    assert "27000" not in masked
    assert masked.startswith("***")
    assert _mask_amount(None) == "***"
