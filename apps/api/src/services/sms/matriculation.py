"""
Automated Matriculation Handshake Service (Contract 1)
======================================================
Phase 3 RevOps / Admissions Handshake:
Executes the unified, atomic matriculation workflow when a prospective lead converts:
1. Creates/activates permanent User accounts for both Student and Parent/Guardian.
2. Assigns SMSUserRole (STUDENT, PARENT) and binds the StudentGuardian relationship link.
3. Enrolls student into designated ClassSection and AcademicYear.
4. Generates structured quarterly StudentFeeVoucher records backed by a FeeInstallmentPlan.
5. Emits non-repudiable audit trail events across identity, academic, and financial modules.
6. Updates AdmissionsLead to ENROLLED stage with complete handshake timeline logging.

Idempotent: Re-executing against an enrolled lead converges cleanly without duplicating accounts or vouchers.
Atomic: All operations execute within a single transaction session.
"""

import datetime
import logging
import secrets
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_campus import (
    AcademicYear,
    Campus,
    ClassSection,
    StudentEnrollment,
    get_utc_now_iso,
)
from src.db.sms_fees import (
    FeeStructure,
    StudentFeeVoucher,
    VoucherStatus,
)
from src.db.sms_fees_extended import (
    FeeChangeEvent,
    FeeChangeAction,
    FeeInstallmentPlan,
    InstallmentPlanStatus,
)
from src.db.sms_identity import (
    PersonProvisioningAction,
    SchoolRole,
    SMSPersonProvisioningEvent,
    SMSUserRole,
    StudentGuardian,
)
from src.db.sms_revops import (
    ActivityType,
    AdmissionsLead,
    LeadActivityLog,
    LeadStage,
    OfferStatus,
    ScholarshipOffer,
)
from src.db.user_organizations import UserOrganization
from src.db.users import User
from src.security.security import security_hash_password

logger = logging.getLogger(__name__)

LEARNER_ROLE_ID = 4


def _unusable_password_hash() -> str:
    """Generate secure Argon2 hash of ephemeral secret for newly provisioned accounts."""
    return security_hash_password(secrets.token_urlsafe(64))


async def _unique_username(session: AsyncSession, email: str, default_prefix: str = "member") -> str:
    """Derive unique username from email address local part."""
    base = (email.split("@")[0] if "@" in email else default_prefix)[:35].lower()
    base = "".join(c for c in base if c.isalnum() or c in ("-", "_")) or default_prefix
    clash = (await session.execute(select(User).where(User.username == base))).scalars().first()
    if clash is None:
        return base
    return f"{base}-{uuid4().hex[:6]}"


def _split_name(full_name: Optional[str], default_first: str = "User") -> Tuple[str, str]:
    """Splits full name string into (first_name, last_name)."""
    parts = (full_name or "").strip().split(" ", 1)
    first_name = parts[0] if parts and parts[0] else default_first
    last_name = parts[1] if len(parts) > 1 else ""
    return first_name, last_name


class MatriculationHandshakeResult:
    """Comprehensive result summary of the automated matriculation handshake."""

    def __init__(
        self,
        lead: AdmissionsLead,
        student_user: User,
        parent_user: User,
        enrollment: StudentEnrollment,
        installment_plan: FeeInstallmentPlan,
        vouchers: List[StudentFeeVoucher],
        created_student: bool,
        created_parent: bool,
        created_enrollment: bool,
        already_matriculated: bool = False,
    ) -> None:
        self.lead = lead
        self.student_user = student_user
        self.parent_user = parent_user
        self.enrollment = enrollment
        self.installment_plan = installment_plan
        self.vouchers = vouchers
        self.created_student = created_student
        self.created_parent = created_parent
        self.created_enrollment = created_enrollment
        self.already_matriculated = already_matriculated

    def as_dict(self) -> Dict[str, Any]:
        return {
            "lead_id": self.lead.id,
            "status": "matriculated",
            "student": {
                "id": self.student_user.id,
                "name": f"{self.student_user.first_name} {self.student_user.last_name}".strip(),
                "email": self.student_user.email,
                "created": self.created_student,
            },
            "parent": {
                "id": self.parent_user.id,
                "name": f"{self.parent_user.first_name} {self.parent_user.last_name}".strip(),
                "email": self.parent_user.email,
                "created": self.created_parent,
            },
            "enrollment": {
                "id": self.enrollment.id,
                "section_id": self.enrollment.section_id,
                "academic_year_id": self.enrollment.academic_year_id,
                "status": self.enrollment.status,
                "created": self.created_enrollment,
            },
            "fee_schedule": {
                "installment_plan_id": self.installment_plan.id,
                "installment_count": self.installment_plan.installment_count,
                "vouchers_count": len(self.vouchers),
                "total_invoiced": sum(v.total_amount for v in self.vouchers),
                "voucher_numbers": [v.voucher_no for v in self.vouchers],
            },
            "already_matriculated": self.already_matriculated,
        }


async def execute_matriculation_handshake(
    db_session: AsyncSession,
    lead_id: int,
    section_id: int,
    tuition_plan_id: Optional[int] = None,
    payment_terms: Optional[Dict[str, Any]] = None,
    actor_user_id: Optional[int] = None,
) -> MatriculationHandshakeResult:
    """
    Executes Contract 1: The Automated Matriculation Handshake.

    Steps:
    1. Validates lead, campus, academic year, and section integrity.
    2. Creates/reuses Learnhouse permanent User accounts for Student and Parent.
    3. Assigns SMSUserRole (STUDENT, PARENT) and creates StudentGuardian link.
    4. Enrolls student into ClassSection and AcademicYear.
    5. Generates structured quarterly StudentFeeVoucher records with FeeInstallmentPlan.
    6. Emits non-repudiable audit records across identity and fee modules.
    7. Advances lead stage to ENROLLED with full timeline logging.
    """
    payment_terms = payment_terms or {}

    # -------------------------------------------------------------------------
    # 1. Lead & Campus Structure Validation
    # -------------------------------------------------------------------------
    stmt = select(AdmissionsLead).where(AdmissionsLead.id == lead_id)
    lead = (await db_session.execute(stmt)).scalar_one_or_none()
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Admissions lead {lead_id} not found.",
        )

    if lead.stage == LeadStage.LOST:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot matriculate a lead marked LOST. Re-activate lead into admissions pipeline first.",
        )

    section = await db_session.get(ClassSection, section_id)
    if not section:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Class section {section_id} does not exist.",
        )

    campus = await db_session.get(Campus, section.campus_id)
    if not campus:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Campus {section.campus_id} associated with class section {section_id} not found.",
        )

    academic_year_id = payment_terms.get("academic_year_id") or section.academic_year_id or lead.academic_year_id
    if not academic_year_id:
        # Fetch active academic year for this campus
        ay_stmt = (
            select(AcademicYear)
            .where(AcademicYear.campus_id == campus.id, AcademicYear.is_active == True)  # noqa: E712
            .order_by(AcademicYear.id.desc())
        )
        active_ay = (await db_session.execute(ay_stmt)).scalars().first()
        if active_ay:
            academic_year_id = active_ay.id
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No active academic year found for campus {campus.id}. Please configure academic year.",
            )

    year = await db_session.get(AcademicYear, academic_year_id)
    if not year:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Academic year {academic_year_id} does not exist.",
        )

    org_id = campus.org_id
    now = datetime.datetime.now(datetime.timezone.utc)
    now_iso = get_utc_now_iso()

    # -------------------------------------------------------------------------
    # 2. Provision Student & Parent Permanent Accounts
    # -------------------------------------------------------------------------
    student_first, student_last = _split_name(lead.student_name, default_first="Student")
    parent_first, parent_last = _split_name(lead.parent_name, default_first="Parent")

    # Determine Student Email
    raw_student_email = payment_terms.get("student_email")
    if raw_student_email and str(raw_student_email).strip():
        student_email = str(raw_student_email).strip().lower()
    else:
        # Derive standard institutional email if not explicitly provided
        base_clean = "".join(c for c in f"{student_first}.{student_last}".lower() if c.isalnum() or c == ".")
        student_email = f"{base_clean or 'student'}.{lead.id}@school.edu"

    parent_email = (payment_terms.get("parent_email") or lead.email or f"parent.{lead.id}@guardian.edu").strip().lower()

    # Provision Student User
    student_user = (
        await db_session.execute(select(User).where(User.email == student_email))
    ).scalars().first()
    created_student = False

    if student_user is None:
        student_user = User(
            username=await _unique_username(db_session, student_email, default_prefix="student"),
            first_name=student_first,
            last_name=student_last,
            email=student_email,
            password=_unusable_password_hash(),
            user_uuid=f"user_{uuid4()}",
            email_verified=False,
            signup_method="admissions_matriculation",
            creation_date=now_iso,
            update_date=now_iso,
        )
        db_session.add(student_user)
        await db_session.flush()
        created_student = True

    # Student Organization Membership
    student_org_mem = (
        await db_session.execute(
            select(UserOrganization).where(
                UserOrganization.user_id == student_user.id,
                UserOrganization.org_id == org_id,
            )
        )
    ).scalars().first()
    if student_org_mem is None:
        db_session.add(
            UserOrganization(
                user_id=student_user.id,
                org_id=org_id,
                role_id=LEARNER_ROLE_ID,
                creation_date=now_iso,
                update_date=now_iso,
            )
        )

    # Provision Parent User
    parent_user = (
        await db_session.execute(select(User).where(User.email == parent_email))
    ).scalars().first()
    created_parent = False

    if parent_user is None:
        parent_user = User(
            username=await _unique_username(db_session, parent_email, default_prefix="parent"),
            first_name=parent_first,
            last_name=parent_last,
            email=parent_email,
            password=_unusable_password_hash(),
            user_uuid=f"user_{uuid4()}",
            email_verified=False,
            signup_method="admissions_matriculation_guardian",
            creation_date=now_iso,
            update_date=now_iso,
        )
        db_session.add(parent_user)
        await db_session.flush()
        created_parent = True

    # Parent Organization Membership
    parent_org_mem = (
        await db_session.execute(
            select(UserOrganization).where(
                UserOrganization.user_id == parent_user.id,
                UserOrganization.org_id == org_id,
            )
        )
    ).scalars().first()
    if parent_org_mem is None:
        db_session.add(
            UserOrganization(
                user_id=parent_user.id,
                org_id=org_id,
                role_id=LEARNER_ROLE_ID,
                creation_date=now_iso,
                update_date=now_iso,
            )
        )

    # -------------------------------------------------------------------------
    # 3. Assign Roles & Guardian Link
    # -------------------------------------------------------------------------
    # Assign Student Role
    student_role = (
        await db_session.execute(
            select(SMSUserRole).where(
                SMSUserRole.user_id == student_user.id,
                SMSUserRole.org_id == org_id,
                SMSUserRole.role == SchoolRole.STUDENT,
            )
        )
    ).scalars().first()
    if student_role is None:
        db_session.add(
            SMSUserRole(
                user_id=student_user.id,
                org_id=org_id,
                campus_id=campus.id,
                role=SchoolRole.STUDENT,
                is_active=True,
            )
        )
    elif not student_role.is_active:
        student_role.is_active = True
        student_role.campus_id = campus.id
        db_session.add(student_role)

    # Assign Parent Role
    parent_role = (
        await db_session.execute(
            select(SMSUserRole).where(
                SMSUserRole.user_id == parent_user.id,
                SMSUserRole.org_id == org_id,
                SMSUserRole.role == SchoolRole.PARENT,
            )
        )
    ).scalars().first()
    if parent_role is None:
        db_session.add(
            SMSUserRole(
                user_id=parent_user.id,
                org_id=org_id,
                campus_id=campus.id,
                role=SchoolRole.PARENT,
                is_active=True,
            )
        )
    elif not parent_role.is_active:
        parent_role.is_active = True
        parent_role.campus_id = campus.id
        db_session.add(parent_role)

    # Bind StudentGuardian Relationship
    guardian_link = (
        await db_session.execute(
            select(StudentGuardian).where(
                StudentGuardian.guardian_user_id == parent_user.id,
                StudentGuardian.student_id == student_user.id,
            )
        )
    ).scalars().first()
    if guardian_link is None:
        db_session.add(
            StudentGuardian(
                guardian_user_id=parent_user.id,
                student_id=student_user.id,
                relationship=payment_terms.get("relationship", "parent"),
                is_primary_contact=True,
            )
        )

    # -------------------------------------------------------------------------
    # 4. Enroll Student in Section & Year
    # -------------------------------------------------------------------------
    enrollment = (
        await db_session.execute(
            select(StudentEnrollment).where(
                StudentEnrollment.student_id == student_user.id,
                StudentEnrollment.academic_year_id == year.id,
            )
        )
    ).scalars().first()
    created_enrollment = False

    if enrollment is None:
        enrollment = StudentEnrollment(
            student_id=student_user.id,
            section_id=section.id,
            academic_year_id=year.id,
            roll_number=payment_terms.get("roll_number") or f"RN-{student_user.id:04d}",
            status="active",
            enrolled_at=now_iso,
        )
        db_session.add(enrollment)
        await db_session.flush()
        created_enrollment = True

    # -------------------------------------------------------------------------
    # 5. Generate Quarterly Fee Vouchers & FeeInstallmentPlan
    # -------------------------------------------------------------------------
    # Check if student already has active installment plan
    existing_plan = (
        await db_session.execute(
            select(FeeInstallmentPlan).where(
                FeeInstallmentPlan.student_id == student_user.id,
                FeeInstallmentPlan.status == InstallmentPlanStatus.ACTIVE,
            )
        )
    ).scalars().first()

    vouchers: List[StudentFeeVoucher] = []

    if existing_plan:
        installment_plan = existing_plan
        # Fetch existing vouchers for this plan
        v_stmt = select(StudentFeeVoucher).where(StudentFeeVoucher.installment_plan_id == installment_plan.id)
        vouchers = list((await db_session.execute(v_stmt)).scalars().all())
    else:
        # Resolve FeeStructure
        fee_structure: Optional[FeeStructure] = None
        if tuition_plan_id:
            fee_structure = await db_session.get(FeeStructure, tuition_plan_id)

        if not fee_structure:
            # Look up campus/section structure or create standard default
            fs_stmt = (
                select(FeeStructure)
                .where(FeeStructure.campus_id == campus.id)
                .order_by(FeeStructure.id.desc())
            )
            fee_structure = (await db_session.execute(fs_stmt)).scalars().first()

        if not fee_structure:
            # Create standard default fee structure for campus
            fee_structure = FeeStructure(
                name=f"Standard Tuition Plan - {campus.name}",
                campus_id=campus.id,
                section_id=section.id,
                tuition_fee=12000.0,
                transport_fee=1200.0,
                lab_fee=800.0,
                other_fee=500.0,
                total_amount=14500.0,
            )
            db_session.add(fee_structure)
            await db_session.flush()

        # Check for accepted ScholarshipOffer to apply discount
        off_stmt = (
            select(ScholarshipOffer)
            .where(
                ScholarshipOffer.lead_id == lead.id,
                ScholarshipOffer.status == OfferStatus.ACCEPTED,
            )
            .order_by(ScholarshipOffer.id.desc())
        )
        accepted_offer = (await db_session.execute(off_stmt)).scalars().first()

        discount_pct = 0.0
        if accepted_offer:
            discount_pct = accepted_offer.tuition_discount_percentage
        elif "discount_percentage" in payment_terms:
            discount_pct = float(payment_terms["discount_percentage"])

        # Create FeeInstallmentPlan (Quarterly = 4 installments)
        installment_count = int(payment_terms.get("installment_count", 4))
        installment_plan = FeeInstallmentPlan(
            student_id=student_user.id,
            campus_id=campus.id,
            fee_structure_id=fee_structure.id,
            name=f"Quarterly Tuition Plan - {student_first} {student_last}",
            installment_count=installment_count,
            status=InstallmentPlanStatus.ACTIVE,
            created_by_user_id=actor_user_id,
            created_at=now,
        )
        db_session.add(installment_plan)
        await db_session.flush()

        # Generate Quarterly Vouchers
        gross_tuition = fee_structure.tuition_fee / installment_count
        gross_transport = fee_structure.transport_fee / installment_count
        gross_lab = fee_structure.lab_fee / installment_count
        gross_other = fee_structure.other_fee / installment_count
        quarterly_discount = round((gross_tuition * (discount_pct / 100.0)), 2)

        base_issue_date = datetime.date.today()

        for q in range(1, installment_count + 1):
            # Stagger quarterly due dates (+90 days each quarter)
            q_days_offset = (q - 1) * 90
            q_issue_date = base_issue_date + datetime.timedelta(days=q_days_offset)
            q_due_date = q_issue_date + datetime.timedelta(days=15)

            quarterly_gross = gross_tuition + gross_transport + gross_lab + gross_other
            quarterly_net = round(max(0.0, quarterly_gross - quarterly_discount), 2)

            rand_suffix = uuid4().hex[:4].upper()
            voucher_no = f"VCH-{q_due_date.strftime('%Y%m')}-{student_user.id}-Q{q}-{rand_suffix}"

            voucher = StudentFeeVoucher(
                student_id=student_user.id,
                fee_structure_id=fee_structure.id,
                installment_plan_id=installment_plan.id,
                installment_number=q,
                voucher_no=voucher_no,
                issue_date=q_issue_date,
                due_date=q_due_date,
                tuition_fee=round(gross_tuition, 2),
                transport_fee=round(gross_transport, 2),
                lab_fee=round(gross_lab, 2),
                other_fee=round(gross_other, 2),
                discount=quarterly_discount,
                fine=0.0,
                late_fee_applied=0.0,
                total_amount=quarterly_net,
                paid_amount=0.0,
                balance_amount=quarterly_net,
                status=VoucherStatus.UNPAID,
                remarks=f"Quarter {q} of {installment_count} ({discount_pct:.0f}% scholarship applied)" if discount_pct > 0 else f"Quarter {q} of {installment_count}",
                created_at=now,
            )
            db_session.add(voucher)
            await db_session.flush()
            vouchers.append(voucher)

            # Emit Fee Change Audit Event
            db_session.add(
                FeeChangeEvent(
                    voucher_id=voucher.id,
                    student_id=student_user.id,
                    action=FeeChangeAction.VOUCHER_CREATED,
                    amount=quarterly_net,
                    new_balance=quarterly_net,
                    changed_by_user_id=actor_user_id,
                    reason=f"Automated Matriculation Handshake - Q{q} Voucher Created",
                    created_at=now,
                )
            )

    # -------------------------------------------------------------------------
    # 6. Emit Non-Repudiable Person Provisioning Audit Events
    # -------------------------------------------------------------------------
    db_session.add(
        SMSPersonProvisioningEvent(
            subject_user_id=student_user.id,
            subject_email=student_email,
            org_id=org_id,
            campus_id=campus.id,
            role=SchoolRole.STUDENT.value,
            action=PersonProvisioningAction.CREATED if created_student else PersonProvisioningAction.REUSED,
            enrolled_section_id=section.id,
            actor_user_id=actor_user_id,
            created_at=now,
        )
    )

    db_session.add(
        SMSPersonProvisioningEvent(
            subject_user_id=parent_user.id,
            subject_email=parent_email,
            org_id=org_id,
            campus_id=campus.id,
            role=SchoolRole.PARENT.value,
            action=PersonProvisioningAction.CREATED if created_parent else PersonProvisioningAction.REUSED,
            linked_student_id=student_user.id,
            actor_user_id=actor_user_id,
            created_at=now,
        )
    )

    # -------------------------------------------------------------------------
    # 7. Update Lead Pipeline Stage & Timeline Log
    # -------------------------------------------------------------------------
    already_enrolled = (lead.stage == LeadStage.ENROLLED)
    if not already_enrolled:
        lead.stage = LeadStage.ENROLLED
        lead.updated_at = now
        db_session.add(lead)

        db_session.add(
            LeadActivityLog(
                lead_id=lead.id,
                activity_type=ActivityType.STAGE_CHANGE,
                summary=(
                    f"Matriculation Handshake Completed: Student provisioned as user #{student_user.id} "
                    f"and enrolled into {section.grade_level} {section.section_name}. "
                    f"Parent account #{parent_user.id} linked. {len(vouchers)} fee vouchers generated."
                ),
                metadata_json={
                    "student_user_id": student_user.id,
                    "parent_user_id": parent_user.id,
                    "section_id": section.id,
                    "academic_year_id": year.id,
                    "installment_plan_id": installment_plan.id,
                    "vouchers_generated": len(vouchers),
                    "total_fee": sum(v.total_amount for v in vouchers),
                },
                created_at=now,
            )
        )

    await db_session.commit()
    await db_session.refresh(lead)
    await db_session.refresh(student_user)
    await db_session.refresh(parent_user)
    await db_session.refresh(enrollment)
    await db_session.refresh(installment_plan)
    for v in vouchers:
        await db_session.refresh(v)

    logger.info(
        "Matriculation Handshake executed for lead_id=%s: student_id=%s parent_id=%s vouchers=%d",
        lead.id,
        student_user.id,
        parent_user.id,
        len(vouchers),
    )

    return MatriculationHandshakeResult(
        lead=lead,
        student_user=student_user,
        parent_user=parent_user,
        enrollment=enrollment,
        installment_plan=installment_plan,
        vouchers=vouchers,
        created_student=created_student,
        created_parent=created_parent,
        created_enrollment=created_enrollment,
        already_matriculated=already_enrolled,
    )
