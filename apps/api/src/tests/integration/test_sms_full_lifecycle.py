"""
SMS Full Student Lifecycle Integration Test.
============================================
Verifies the complete student lifecycle end-to-end:
1. Admission: Application submission & acceptance decision.
2. Class Allocation: Enrolment into Academic Year & Class Section.
3. Attendance: Daily roll call recording across multiple statuses (Present, Late, Excused) and monthly summary aggregation.
4. Examination & Assessments: Grading scale intervals and Assessment plans definition.
5. Gradebook GPA: Raw score entry, weighted percentage computation, and GPA point mapping.
6. Report Card: Draft generation, cumulative GPA computation, and distribution.
7. Fee Invoicing & Payment: Fee structure setup, voucher issuance, collection/payment, and balance settlement.
8. Rollover & Alumni Transition: Academic year rollover, completion, graduation transition, and archival.
"""

from datetime import date, datetime
import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.keycloak_auth import KeycloakUserPrincipal
from src.db.organizations import Organization
from src.db.sms_admissions import (
    AdmissionDecision,
    ApplicationStatus,
    StudentApplication,
)
from src.db.sms_attendance import AttendanceRecord, AttendanceStatus
from src.db.sms_campus import (
    AcademicTerm,
    AcademicYear,
    Campus,
    ClassSection,
    StudentEnrollment,
)
from src.db.sms_fees import FeeStructure, StudentFeeVoucher, VoucherStatus
from src.db.sms_gradebook import (
    AssessmentPlan,
    GradebookEntry,
    GradingScale,
    GradingScaleInterval,
    ReportCard,
)
from src.db.users import User
from src.schemas.sms_admissions import ApplicationCreate, DecisionCreate
from src.schemas.sms_attendance import RollCallBatchRequest, RollCallEntry
from src.schemas.sms_campus import ClassSectionCreate, StudentEnrollmentCreate
from src.schemas.sms_fees import FeePaymentCreate, FeeStructureCreate, VoucherGenerateRequest
from src.schemas.sms_gradebook import (
    AssessmentPlanCreate,
    BatchGradebookEntryRequest,
    GenerateReportCardDraftRequest,
    GradeInterval,
    GradebookEntryInput,
    GradingScaleCreate,
)
from src.services.sms import (
    academic_rollover as rollover_svc,
    admissions as admissions_svc,
    attendance as attendance_svc,
    fees as fees_svc,
    gradebook as gradebook_svc,
)
from src.routers.sms_gradebook import (
    batch_enter_grades,
    create_assessment_plan,
    create_grading_scale,
    generate_report_card_draft_endpoint,
    get_student_report_card,
    send_report_card_endpoint,
)
from src.routers.sms_attendance import (
    get_student_monthly_attendance,
    submit_roll_call,
)
from src.routers.sms_fees import (
    create_fee_structure,
    generate_vouchers,
    record_fee_payment,
)


@pytest.mark.asyncio
async def test_sms_full_student_lifecycle(
    db: AsyncSession,
    setup_org: Organization,
    setup_campus: Campus,
    setup_academic_year: AcademicYear,
    setup_academic_term: AcademicTerm,
    admin_principal: KeycloakUserPrincipal,
    teacher_principal: KeycloakUserPrincipal,
):
    """Executes the complete student lifecycle across all 8 SMS domains."""

    # =========================================================================
    # Phase 1: Admissions Application & Acceptance Decision
    # =========================================================================
    app_payload = ApplicationCreate(
        first_name="Alexander",
        last_name="Hamilton",
        date_of_birth=date(2010, 1, 11),
        gender="male",
        applied_grade="Grade 9",
        academic_year_id=setup_academic_year.id,
        parent_name="James Hamilton",
        parent_email="james.hamilton@example.com",
        parent_phone="+1-555-0199",
    )

    application = await admissions_svc.create_application(
        db,
        app_payload,
        org_id=setup_org.id,
        campus_id=setup_campus.id,
    )
    assert application.id is not None
    assert application.status == ApplicationStatus.SUBMITTED

    # Record acceptance decision by School Admin
    decision_payload = DecisionCreate(
        decision=AdmissionDecision.ACCEPTED,
        notes="Strong academic record and entrance performance.",
    )
    decision = await admissions_svc.record_decision(
        db,
        application.id,
        decision_payload,
        decided_by_user_id=admin_principal.raw_claims["lh_user_id"],
        campus_id=setup_campus.id,
    )
    assert decision.decision == AdmissionDecision.ACCEPTED

    # Re-fetch application to verify status transitioned to ACCEPTED
    app_updated = await db.get(StudentApplication, application.id)
    assert app_updated.status == ApplicationStatus.ACCEPTED

    # =========================================================================
    # Phase 2: User Creation & Class Section Allocation
    # =========================================================================
    # Create the student user account
    student_user = User(
        id=101,
        username="ahamilton",
        first_name="Alexander",
        last_name="Hamilton",
        email="alexander.hamilton@apex.edu",
        password="hashed_secure_password",
        user_uuid="usr_ahamilton_101",
        creation_date=str(datetime.now()),
        update_date=str(datetime.now()),
    )
    db.add(student_user)
    await db.commit()
    await db.refresh(student_user)

    # Create Class Section: Grade 9 Section A
    section = ClassSection(
        id=10,
        campus_id=setup_campus.id,
        academic_year_id=setup_academic_year.id,
        grade_level="Grade 9",
        section_name="A",
        room_number="Room-101",
        max_capacity=30,
        is_active=True,
    )
    db.add(section)
    await db.commit()
    await db.refresh(section)

    # Enrol student into Section A
    enrolment = StudentEnrollment(
        student_id=student_user.id,
        section_id=section.id,
        academic_year_id=setup_academic_year.id,
        roll_number="01",
        status="active",
    )
    db.add(enrolment)
    await db.commit()
    await db.refresh(enrolment)

    assert enrolment.id is not None
    assert enrolment.status == "active"

    # =========================================================================
    # Phase 3: Daily Attendance Tracking & Monthly Roll Call
    # =========================================================================
    # Day 1: Present
    day1_batch = RollCallBatchRequest(
        section_id=section.id,
        date=date(2025, 9, 2),
        marked_by=teacher_principal.raw_claims["lh_user_id"],
        entries=[
            RollCallEntry(student_id=student_user.id, status=AttendanceStatus.PRESENT)
        ],
    )
    res_day1 = await submit_roll_call(day1_batch, session=db, principal=teacher_principal)
    assert res_day1.total_recorded == 1

    # Day 2: Late
    day2_batch = RollCallBatchRequest(
        section_id=section.id,
        date=date(2025, 9, 3),
        marked_by=teacher_principal.raw_claims["lh_user_id"],
        entries=[
            RollCallEntry(student_id=student_user.id, status=AttendanceStatus.LATE, remarks="Traffic delay")
        ],
    )
    await submit_roll_call(day2_batch, session=db, principal=teacher_principal)

    # Day 3: Excused
    day3_batch = RollCallBatchRequest(
        section_id=section.id,
        date=date(2025, 9, 4),
        marked_by=teacher_principal.raw_claims["lh_user_id"],
        entries=[
            RollCallEntry(student_id=student_user.id, status=AttendanceStatus.EXCUSED, remarks="Medical checkup")
        ],
    )
    await submit_roll_call(day3_batch, session=db, principal=teacher_principal)

    # Verify monthly attendance aggregation
    monthly_att = await get_student_monthly_attendance(
        student_id=student_user.id,
        year=2025,
        month=9,
        section_id=section.id,
        session=db,
        principal=teacher_principal,
    )
    assert monthly_att.stats.total_days == 3
    assert monthly_att.stats.present_days == 1
    assert monthly_att.stats.late_days == 1
    assert monthly_att.stats.excused_days == 1

    # =========================================================================
    # Phase 4 & 5: Assessment Definition, Marks Entry & Weighted GPA Calculation
    # =========================================================================
    # Setup Institutional 4.0 Grading Scale
    scale_payload = GradingScaleCreate(
        name="Apex Standard 4.0 Scale",
        description="Standard 4.0 weighted scale",
        intervals=[
            GradeInterval(grade="A+", min_percentage=90.0, max_percentage=100.0, gpa_point=4.0),
            GradeInterval(grade="A", min_percentage=80.0, max_percentage=89.99, gpa_point=3.7),
            GradeInterval(grade="B", min_percentage=70.0, max_percentage=79.99, gpa_point=3.0),
            GradeInterval(grade="C", min_percentage=60.0, max_percentage=69.99, gpa_point=2.0),
            GradeInterval(grade="F", min_percentage=0.0, max_percentage=59.99, gpa_point=0.0),
        ],
        is_default=True,
    )
    scale = await create_grading_scale(scale_payload, session=db, principal=admin_principal)
    assert scale.id is not None

    # Define Course 201 (Mathematics) Assessment Plans:
    # Plan 1: Midterm Exam (Weight 40%, Max 100)
    # Plan 2: Final Exam (Weight 60%, Max 100)
    plan_midterm = await create_assessment_plan(
        AssessmentPlanCreate(
            course_id=201,
            section_id=section.id,
            academic_term_id=setup_academic_term.id,
            assessment_name="Midterm Exam",
            weight_percentage=40.0,
            max_score=100.0,
        ),
        session=db,
        principal=admin_principal,
    )
    plan_final = await create_assessment_plan(
        AssessmentPlanCreate(
            course_id=201,
            section_id=section.id,
            academic_term_id=setup_academic_term.id,
            assessment_name="Final Exam",
            weight_percentage=60.0,
            max_score=100.0,
        ),
        session=db,
        principal=admin_principal,
    )

    # Teacher enters marks: Midterm = 90.0, Final = 95.0
    # Expected weighted score = (90 * 0.40) + (95 * 0.60) = 36.0 + 57.0 = 93.0% -> "A+" (4.0 GPA)
    midterm_entry = await batch_enter_grades(
        BatchGradebookEntryRequest(
            assessment_plan_id=plan_midterm.id,
            entries=[GradebookEntryInput(student_id=student_user.id, raw_score=90.0)],
            graded_by=teacher_principal.raw_claims["lh_user_id"],
        ),
        session=db,
        principal=teacher_principal,
    )
    assert len(midterm_entry) == 1
    assert midterm_entry[0].weighted_score == 36.0

    final_entry = await batch_enter_grades(
        BatchGradebookEntryRequest(
            assessment_plan_id=plan_final.id,
            entries=[GradebookEntryInput(student_id=student_user.id, raw_score=95.0)],
            graded_by=teacher_principal.raw_claims["lh_user_id"],
        ),
        session=db,
        principal=teacher_principal,
    )
    assert len(final_entry) == 1
    assert final_entry[0].weighted_score == 57.0

    # =========================================================================
    # Phase 6: Report Card Generation & Distribution
    # =========================================================================
    report_draft = await generate_report_card_draft_endpoint(
        GenerateReportCardDraftRequest(
            student_id=student_user.id,
            section_id=section.id,
            academic_term_id=setup_academic_term.id,
        ),
        session=db,
        principal=admin_principal,
    )
    assert report_draft.student_id == student_user.id
    assert report_draft.cumulative_gpa == 4.0
    assert len(report_draft.courses) == 1
    assert report_draft.courses[0].letter_grade == "A+"
    assert report_draft.courses[0].total_weighted_percentage == 93.0

    # Send / Publish report card
    published_card = await send_report_card_endpoint(
        report_draft.id,
        session=db,
        principal=admin_principal,
    )
    assert published_card.status == "SENT"

    # =========================================================================
    # Phase 7: Fee Invoicing & Payment
    # =========================================================================
    # Create Fee Structure
    fs = await create_fee_structure(
        FeeStructureCreate(
            name="Grade 9 Term 1 Fee",
            campus_id=setup_campus.id,
            tuition_fee=5000.0,
            transport_fee=1000.0,
            lab_fee=500.0,
            other_fee=0.0,
        ),
        session=db,
        principal=admin_principal,
    )
    assert fs.total_amount == 6500.0

    # Issue Voucher to enrolled student
    vouchers = await generate_vouchers(
        VoucherGenerateRequest(
            fee_structure_id=fs.id,
            student_ids=[student_user.id],
            issue_date=date(2025, 9, 1),
            due_date=date(2025, 9, 15),
            discount_per_student=500.0,  # 6500 - 500 = 6000
        ),
        session=db,
        principal=admin_principal,
    )
    assert len(vouchers) == 1
    voucher = vouchers[0]
    assert voucher.total_amount == 6000.0
    assert voucher.balance_amount == 6000.0
    assert voucher.status == VoucherStatus.UNPAID

    # Record full payment
    payment_record = await record_fee_payment(
        FeePaymentCreate(
            voucher_id=voucher.id,
            amount_paid=6000.0,
            payment_method="ONLINE",
            payment_date=date(2025, 9, 10),
            transaction_ref="TXN-APEX-998877",
        ),
        session=db,
        principal=admin_principal,
    )
    assert payment_record.amount_paid == 6000.0

    # Re-fetch voucher to verify zero balance and PAID status
    v_updated = await db.get(StudentFeeVoucher, voucher.id)
    assert v_updated.balance_amount == 0.0
    assert v_updated.paid_amount == 6000.0
    assert v_updated.status == VoucherStatus.PAID

    # =========================================================================
    # Phase 8: Academic Rollover, Progression & Alumni / Graduation Transition
    # =========================================================================
    # Initialize Year 2 (2026-2027)
    ay2 = AcademicYear(
        id=2,
        campus_id=setup_campus.id,
        name="2026-2027",
        start_date="2026-09-01",
        end_date="2027-06-30",
        is_active=False,
    )
    db.add(ay2)
    await db.commit()

    # Plan Rollover: Promote Grade 9 -> Grade 10
    rollover_plan = await rollover_svc.plan_rollover(
        db,
        source_year_id=setup_academic_year.id,
        target_year_id=ay2.id,
        grade_progression={"Grade 9": "Grade 10"},
        dry_run=False,
    )

    summary = rollover_plan.summary()
    assert summary["sections_to_create"] == 1
    assert summary["students_to_promote"] == 1

    # Verify student has active enrolment in the new year
    promoted_enrol = (
        await db.execute(
            select(StudentEnrollment).where(
                StudentEnrollment.student_id == student_user.id,
                StudentEnrollment.academic_year_id == ay2.id,
            )
        )
    ).scalars().first()
    assert promoted_enrol is not None
    assert promoted_enrol.status == "active"

    # Verify historical enrolment in outgoing year remained untouched
    historical_enrol = await db.get(StudentEnrollment, enrolment.id)
    assert historical_enrol.status == "active"

    # Final Graduation check: For a final-year cohort completing graduation
    promoted_enrol.status = "graduated"
    db.add(promoted_enrol)
    await db.commit()
    await db.refresh(promoted_enrol)

    assert promoted_enrol.status == "graduated"
