"""Offboarding, appraisals, and payroll separation of duties.

Three controls that did not exist before this module:

1. `StaffProfile.is_active = False` was the whole of "this person has left".
   It revoked nothing -- their role grants stayed active so they could still
   sign in, and they remained the named class teacher. It LOOKED like
   offboarding, which is the dangerous kind of missing feature.

2. The three payroll endpoints composed into a self-dealing path: one person
   could set a salary structure, generate the slip, and mark it paid with no
   second party. Narrowing the role was a stopgap; refusing self-approval is
   the actual control.

3. An appraisal whose author came from the payload would be worthless as
   evidence that a review happened.
"""

import datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_campus import ClassSection
from src.db.sms_hr import ContractType, StaffProfile
from src.db.sms_hr_extended import (
    AppraisalStatus,
    OffboardingReason,
    PayrollActionType,
)
from src.db.sms_identity import SchoolRole, SMSUserRole
from src.db.sms_payroll import SalaryPaymentStatus, SalarySlip
from src.routers.sms_hr import (
    create_appraisal,
    list_appraisals,
    offboard_staff,
    share_appraisal,
    update_appraisal,
)
from src.routers.sms_payroll import approve_salary_slips, record_salary_payment
from src.schemas.sms_hr_extended import (
    PayrollApprovalRequest,
    StaffAppraisalCreate,
    StaffAppraisalUpdate,
    StaffOffboardingRequest,
)
from src.schemas.sms_payroll import ProcessSalaryPaymentRequest
from src.services.sms.payroll_approval import record_payroll_action


def _admin(user_id: int = 1):
    """A resolved SCHOOL_ADMIN. These tests call handlers directly, so
    FastAPI's DI never runs and `principal` would arrive as an unresolved
    Depends."""
    return SimpleNamespace(
        is_superadmin=False,
        campus_id=None,
        has_any_role=lambda wanted: "SCHOOL_ADMIN" in wanted,
        has_role=lambda r: r == "SCHOOL_ADMIN",
        raw_claims={"lh_user_id": user_id},
    )


def _staff_caller(user_id: int):
    """A non-admin staff member -- a teacher reading their own records."""
    return SimpleNamespace(
        is_superadmin=False,
        campus_id=None,
        has_any_role=lambda wanted: "TEACHER" in wanted,
        has_role=lambda r: r == "TEACHER",
        raw_claims={"lh_user_id": user_id},
    )


async def _make_staff(db: AsyncSession, *, code: str, user_id: int) -> StaffProfile:
    profile = StaffProfile(
        employee_code=code,
        full_name=f"Staff {code}",
        designation="Teacher",
        department="Science",
        joining_date=datetime.date(2025, 1, 10),
        contract_type=ContractType.PERMANENT,
        basic_salary=50000.0,
        user_id=user_id,
        campus_id=None,
        is_active=True,
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return profile


# ── Offboarding ──


@pytest.mark.asyncio
async def test_offboarding_revokes_role_grants_and_releases_sections(db: AsyncSession):
    """The cascade must actually cascade.

    Before this existed, setting is_active=False left the person able to sign
    in and still named as the class teacher.
    """
    staff = await _make_staff(db, code="OFFB-1", user_id=9001)

    grant = SMSUserRole(user_id=9001, org_id=1, campus_id=None, role=SchoolRole.TEACHER)
    db.add(grant)
    section = ClassSection(
        campus_id=1,
        grade_level="Grade 9",
        section_name="A",
        max_capacity=30,
        class_teacher_id=9001,
        is_active=True,
    )
    db.add(section)
    await db.commit()
    await db.refresh(section)

    outcome = await offboard_staff(
        staff_id=staff.id,
        payload=StaffOffboardingRequest(
            effective_date=datetime.date(2026, 6, 30),
            reason=OffboardingReason.RESIGNATION,
        ),
        session=db,
        principal=_admin(),
    )

    assert outcome.offboarding.roles_revoked >= 1, "role grants must be revoked"

    await db.refresh(grant)
    assert grant.is_active is False, (
        "a departed employee retaining an active role grant can still sign in "
        "and act -- the entire point of offboarding"
    )

    await db.refresh(section)
    assert section.class_teacher_id is None, (
        "with no successor named, the section must be released to unassigned "
        "and reported, not left pointing at someone who has left"
    )

    await db.refresh(staff)
    assert staff.is_active is False


@pytest.mark.asyncio
async def test_offboarding_reassigns_sections_to_a_named_successor(db: AsyncSession):
    """A successor is used when supplied -- and never guessed when it is not."""
    staff = await _make_staff(db, code="OFFB-2", user_id=9002)
    section = ClassSection(
        campus_id=1,
        grade_level="Grade 10",
        section_name="B",
        max_capacity=30,
        class_teacher_id=9002,
        is_active=True,
    )
    db.add(section)
    await db.commit()
    await db.refresh(section)

    await offboard_staff(
        staff_id=staff.id,
        payload=StaffOffboardingRequest(
            effective_date=datetime.date(2026, 6, 30),
            reason=OffboardingReason.END_OF_CONTRACT,
            successor_user_id=9999,
        ),
        session=db,
        principal=_admin(),
    )

    await db.refresh(section)
    assert section.class_teacher_id == 9999


@pytest.mark.asyncio
async def test_offboarding_an_already_inactive_person_is_refused(db: AsyncSession):
    """Re-running would record a second departure for the same person."""
    staff = await _make_staff(db, code="OFFB-3", user_id=9003)
    staff.is_active = False
    db.add(staff)
    await db.commit()

    with pytest.raises(HTTPException) as exc:
        await offboard_staff(
            staff_id=staff.id,
            payload=StaffOffboardingRequest(
                effective_date=datetime.date(2026, 6, 30),
                reason=OffboardingReason.RESIGNATION,
            ),
            session=db,
            principal=_admin(),
        )
    assert exc.value.status_code == 409


# ── Payroll separation of duties ──


async def _slip(db: AsyncSession, staff: StaffProfile, *, preparer: int) -> SalarySlip:
    slip = SalarySlip(
        slip_no=f"SLIP-{staff.employee_code}-092026",
        staff_id=staff.id,
        month=9,
        year=2026,
        basic=50000.0,
        gross_salary=50000.0,
        total_deductions=0.0,
        net_salary=50000.0,
        payment_status=SalaryPaymentStatus.PENDING,
    )
    db.add(slip)
    await db.commit()
    await db.refresh(slip)

    await record_payroll_action(
        session=db,
        slip=slip,
        action=PayrollActionType.PREPARED,
        actor_user_id=preparer,
        campus_id=staff.campus_id,
        note=None,
    )
    await db.commit()
    return slip


@pytest.mark.asyncio
async def test_payroll_cannot_be_approved_by_whoever_prepared_it(db: AsyncSession):
    """THE control. Without it one person walks prepare -> approve -> pay."""
    staff = await _make_staff(db, code="PAY-1", user_id=9101)
    slip = await _slip(db, staff, preparer=555)

    response = await approve_salary_slips(
        payload=PayrollApprovalRequest(slip_ids=[slip.id]),
        session=db,
        principal=_admin(user_id=555),  # the same person who prepared it
    )

    outcomes = {r.slip_id: r.outcome for r in response.results}
    assert outcomes[slip.id] == "self_approval_refused"


@pytest.mark.asyncio
async def test_a_second_person_can_approve(db: AsyncSession):
    staff = await _make_staff(db, code="PAY-2", user_id=9102)
    slip = await _slip(db, staff, preparer=555)

    response = await approve_salary_slips(
        payload=PayrollApprovalRequest(slip_ids=[slip.id]),
        session=db,
        principal=_admin(user_id=777),
    )
    assert response.results[0].outcome == "approved"


@pytest.mark.asyncio
async def test_an_unapproved_slip_cannot_be_paid(db: AsyncSession):
    """A payment that goes out unapproved cannot be recalled, so refusing is
    the recoverable direction."""
    staff = await _make_staff(db, code="PAY-3", user_id=9103)
    slip = await _slip(db, staff, preparer=555)

    with pytest.raises(HTTPException) as exc:
        await record_salary_payment(
            slip_id=slip.id,
            payload=ProcessSalaryPaymentRequest(
                payment_date=datetime.date(2026, 9, 30),
                payment_reference="TRF-1",
            ),
            session=db,
            principal=_admin(user_id=777),
        )
    assert exc.value.status_code == 409
    assert "approv" in exc.value.detail.lower()


@pytest.mark.asyncio
async def test_one_bad_slip_does_not_abort_a_payroll_run(db: AsyncSession):
    """A reviewer must not be left unsure which of thirty slips were actioned."""
    staff = await _make_staff(db, code="PAY-4", user_id=9104)
    good = await _slip(db, staff, preparer=555)

    response = await approve_salary_slips(
        payload=PayrollApprovalRequest(slip_ids=[good.id, 999_999]),
        session=db,
        principal=_admin(user_id=777),
    )
    outcomes = {r.slip_id: r.outcome for r in response.results}
    assert outcomes[good.id] == "approved"
    assert outcomes[999_999] == "not_found"


# ── Appraisals ──


@pytest.mark.asyncio
async def test_an_appraisal_records_its_author_from_the_caller(db: AsyncSession):
    """Never from the payload -- the schema has no reviewer field precisely so
    an appraisal cannot name someone else as its author."""
    staff = await _make_staff(db, code="APP-1", user_id=9201)

    appraisal = await create_appraisal(
        payload=StaffAppraisalCreate(
            staff_id=staff.id,
            period_start=datetime.date(2026, 1, 1),
            period_end=datetime.date(2026, 6, 30),
            strengths="Strong classroom management.",
        ),
        session=db,
        principal=_admin(user_id=4242),
    )
    assert appraisal.reviewer_user_id == 4242
    assert appraisal.status == AppraisalStatus.DRAFT


@pytest.mark.asyncio
async def test_a_staff_member_sees_their_own_appraisal_only_once_shared(db: AsyncSession):
    """A draft is the reviewer's working document, not a disclosure."""
    staff = await _make_staff(db, code="APP-2", user_id=9202)

    created = await create_appraisal(
        payload=StaffAppraisalCreate(
            staff_id=staff.id,
            period_start=datetime.date(2026, 1, 1),
            period_end=datetime.date(2026, 6, 30),
        ),
        session=db,
        principal=_admin(user_id=4242),
    )

    as_draft = await list_appraisals(
        staff_id=None, campus_id=None, session=db, principal=_staff_caller(9202)
    )
    assert as_draft == [], "a DRAFT must not be visible to its subject"

    await share_appraisal(appraisal_id=created.id, session=db, principal=_admin())

    after_share = await list_appraisals(
        staff_id=None, campus_id=None, session=db, principal=_staff_caller(9202)
    )
    assert [a.id for a in after_share] == [created.id]


@pytest.mark.asyncio
async def test_a_staff_member_cannot_see_a_colleagues_appraisal(db: AsyncSession):
    subject = await _make_staff(db, code="APP-3", user_id=9203)
    created = await create_appraisal(
        payload=StaffAppraisalCreate(
            staff_id=subject.id,
            period_start=datetime.date(2026, 1, 1),
            period_end=datetime.date(2026, 6, 30),
        ),
        session=db,
        principal=_admin(user_id=4242),
    )
    await share_appraisal(appraisal_id=created.id, session=db, principal=_admin())

    # A different staff member with no profile of their own.
    rows = await list_appraisals(
        staff_id=None, campus_id=None, session=db, principal=_staff_caller(9999)
    )
    assert rows == [], "empty, not 403 -- existence is not confirmed either way"


@pytest.mark.asyncio
async def test_a_shared_appraisal_cannot_be_rewritten(db: AsyncSession):
    """Editing a document someone has already read rewrites what they were
    told."""
    staff = await _make_staff(db, code="APP-4", user_id=9204)
    created = await create_appraisal(
        payload=StaffAppraisalCreate(
            staff_id=staff.id,
            period_start=datetime.date(2026, 1, 1),
            period_end=datetime.date(2026, 6, 30),
        ),
        session=db,
        principal=_admin(user_id=4242),
    )
    await share_appraisal(appraisal_id=created.id, session=db, principal=_admin())

    with pytest.raises(HTTPException) as exc:
        await update_appraisal(
            appraisal_id=created.id,
            payload=StaffAppraisalUpdate(strengths="Rewritten after the fact."),
            session=db,
            principal=_admin(),
        )
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_sharing_twice_does_not_restamp_the_date(db: AsyncSession):
    """shared_at records when the person was actually told."""
    staff = await _make_staff(db, code="APP-5", user_id=9205)
    created = await create_appraisal(
        payload=StaffAppraisalCreate(
            staff_id=staff.id,
            period_start=datetime.date(2026, 1, 1),
            period_end=datetime.date(2026, 6, 30),
        ),
        session=db,
        principal=_admin(user_id=4242),
    )
    first = await share_appraisal(appraisal_id=created.id, session=db, principal=_admin())
    second = await share_appraisal(appraisal_id=created.id, session=db, principal=_admin())
    assert first.shared_at == second.shared_at
