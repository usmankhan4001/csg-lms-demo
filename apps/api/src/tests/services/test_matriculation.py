"""
Unit & Integration Tests for Automated Matriculation Handshake, BANT Scoring & Curriculum RAG
=============================================================================================
Phase 3 RevOps Verification Suite:
- BANT 5-factor lead scoring & tiering (HOT, WARM, COLD, NURTURE)
- Grounded Curriculum RAG knowledge base & admissions counselor
- Contract 1: Automated Matriculation Handshake
- Non-repudiable audit events, fee installment schedules, idempotency & error handling
"""

import datetime
import pytest
from fastapi import HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_campus import AcademicYear, Campus, ClassSection, StudentEnrollment
from src.db.sms_fees import FeeStructure, StudentFeeVoucher, VoucherStatus
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
    LeadOrigin,
    LeadSource,
    LeadStage,
    OfferStatus,
    ScholarshipOffer,
)
from src.db.user_organizations import UserOrganization
from src.db.users import User
from src.schemas.sms_matriculation import (
    BANTQualifyRequest,
    CounselorQueryRequest,
    MatriculationHandshakeRequest,
)
from src.services.ai.bant_scoring import (
    BANTTier,
    calculate_bant_score,
    score_authority_factor,
    score_budget_factor,
    score_need_factor,
    score_timeline_factor,
)
from src.services.ai.curriculum_rag import (
    add_campus_knowledge_doc,
    query_curriculum_rag,
)
from src.services.sms.matriculation import execute_matriculation_handshake
from src.routers.sms_matriculation import (
    get_matriculation_status,
    post_counselor_query,
    post_matriculation_handshake,
    post_qualify_lead_bant,
)
from src.tests.sms._principals import SUPERADMIN


# ---------------------------------------------------------------------------
# Test Helpers
# ---------------------------------------------------------------------------

async def _setup_school_environment(db: AsyncSession, org_id: int, code: str = "MATRIC-01"):
    """Bootstraps a complete multi-tenant campus, academic year, and class section."""
    campus = Campus(name="Matriculation Academy", code=code, org_id=org_id)
    db.add(campus)
    await db.commit()
    await db.refresh(campus)

    year = AcademicYear(name="2026-2027 Academic Session", campus_id=campus.id, is_active=True)
    section = ClassSection(grade_level="Grade 9", section_name="Alpha", campus_id=campus.id)
    db.add(year)
    db.add(section)
    await db.commit()
    await db.refresh(year)
    await db.refresh(section)

    section.academic_year_id = year.id
    db.add(section)
    await db.commit()
    await db.refresh(section)

    return campus, year, section


async def _create_test_lead(
    db: AsyncSession,
    campus_id: int,
    parent_name: str = "Tariq Mahmood",
    student_name: str = "Zainab Mahmood",
    email: str = "tariq.mahmood@family.com",
    stage: LeadStage = LeadStage.OFFER_SENT,
) -> AdmissionsLead:
    """Inserts a test admissions lead into the database."""
    lead = AdmissionsLead(
        campus_id=campus_id,
        parent_name=parent_name,
        student_name=student_name,
        email=email,
        phone="+92-300-9876543",
        grade_applying_for="Grade 9",
        source=LeadSource.WEBSITE_FORM,
        origin=LeadOrigin.INBOUND,
        stage=stage,
        budget_range="$12,000 - $15,000",
        whatsapp_consent=True,
        email_consent=True,
        notes="High academic performer interested in Cambridge IGCSE track.",
    )
    db.add(lead)
    await db.commit()
    await db.refresh(lead)
    return lead


# ---------------------------------------------------------------------------
# 1. BANT 5-Factor Lead Qualification Tests
# ---------------------------------------------------------------------------

def test_bant_factor_budget_scoring():
    """Verify budget scoring logic across high, medium, low, and stated budget values."""
    signals: list[str] = []
    risks: list[str] = []

    # High readiness
    score_high = score_budget_factor({"budget_fit": "high", "expected_fee": 10000}, signals, risks)
    assert score_high == 25.0
    assert any("Full fee" in s for s in signals)

    # Stated budget matching expected
    signals.clear()
    score_stated = score_budget_factor({"stated_budget": 12000, "expected_fee": 10000}, signals, risks)
    assert score_stated == 25.0

    # Scholarship dependent with fee concern
    signals.clear()
    risks.clear()
    score_low = score_budget_factor({"budget_fit": "scholarship_dependent", "fee_concern": True}, signals, risks)
    assert score_low == 5.0  # 10.0 - 5.0 penalty
    assert any("Price Sensitivity" in r for r in risks)


def test_bant_factor_authority_scoring():
    """Verify decision maker identity, verified reachability, and compliance opt-ins."""
    signals: list[str] = []
    risks: list[str] = []

    full_authority = {
        "parent_name": "Dr. Sarah Jenkins",
        "email": "sarah.jenkins@hospital.org",
        "phone": "+1-415-555-0199",
        "whatsapp_consent": True,
        "email_consent": True,
        "relationship": "mother",
    }
    score_auth = score_authority_factor(full_authority, signals, risks)
    assert score_auth >= 23.0
    assert any("Decision Maker" in s for s in signals)
    assert any("Compliance Verified" in s for s in signals)


def test_bant_factor_need_scoring():
    """Verify milestone high-demand grade levels and curriculum tracks."""
    signals: list[str] = []
    risks: list[str] = []

    high_need = {
        "grade_applying_for": "Grade 9",
        "student_name": "Hamza Ali",
        "curriculum_preference": "Cambridge IGCSE",
        "notes": "Relocating from abroad, seeking advanced STEM track.",
        "previous_school": "Dubai International Academy",
    }
    score_need = score_need_factor(high_need, signals, risks)
    assert score_need == 25.0
    assert any("Curriculum Need" in s for s in signals)
    assert any("Urgent Academic Need" in s for s in signals)


def test_bant_factor_timeline_scoring():
    """Verify immediate vs long-range timeline scoring."""
    signals: list[str] = []
    risks: list[str] = []

    immediate = {"start_timeline": "Immediate / Fall 2026"}
    score_imm = score_timeline_factor(immediate, signals, risks)
    assert score_imm == 25.0

    delayed = {"start_timeline": "exploring for next year"}
    risks.clear()
    score_del = score_timeline_factor(delayed, signals, risks)
    assert score_del <= 10.0
    assert any("Extended Timeline" in r for r in risks)


def test_bant_tier_classification_hot_warm_cold_nurture():
    """Verify aggregate scoring and tier assignments: HOT, WARM, COLD, NURTURE."""
    # 1. HOT Tier (>= 80)
    hot_lead = {
        "parent_name": "Khadija Begum",
        "student_name": "Usman Begum",
        "email": "khadija@domain.com",
        "phone": "+92-321-1234567",
        "grade_applying_for": "Grade 11",
        "budget_fit": "high",
        "stated_budget": 15000,
        "start_timeline": "immediate",
        "whatsapp_consent": True,
        "email_consent": True,
        "curriculum_preference": "IB Diploma",
        "notes": "Relocating next month, urgent admission required.",
    }
    res_hot = calculate_bant_score(hot_lead)
    assert res_hot.total_score >= 80.0
    assert res_hot.tier == BANTTier.HOT
    assert "Priority Admissions Action" in res_hot.recommended_next_action

    # 2. WARM Tier (60-79)
    warm_lead = {
        "parent_name": "Farhan Saeed",
        "student_name": "Aydin Saeed",
        "email": "farhan@saeed.com",
        "phone": "+92-333-5551234",
        "grade_applying_for": "Grade 4",
        "budget_fit": "standard",
        "start_timeline": "next semester",
        "whatsapp_consent": True,
        "email_consent": False,
    }
    res_warm = calculate_bant_score(warm_lead)
    assert 60.0 <= res_warm.total_score <= 79.0
    assert res_warm.tier == BANTTier.WARM

    # 3. COLD Tier (40-59)
    cold_lead = {
        "parent_name": "Inquirer",
        "student_name": "Child",
        "email": "inquiring@test.com",
        "phone": "+92-300-0000000",
        "grade_applying_for": "Grade 3",
        "budget_fit": "low",
        "start_timeline": "exploring",
    }
    res_cold = calculate_bant_score(cold_lead)
    assert 40.0 <= res_cold.total_score <= 59.0
    assert res_cold.tier == BANTTier.COLD

    # 4. NURTURE Tier (< 40)
    nurture_lead = {
        "parent_name": "Unknown",
        "student_name": "",
        "email": "",
        "phone": "",
        "grade_applying_for": "",
        "start_timeline": "future",
    }
    res_nurture = calculate_bant_score(nurture_lead)
    assert res_nurture.total_score < 40.0
    assert res_nurture.tier == BANTTier.NURTURE


# ---------------------------------------------------------------------------
# 2. Curriculum RAG Knowledge Base Tests
# ---------------------------------------------------------------------------

def test_curriculum_rag_tuition_and_scholarship_queries():
    """Verify grounded retrieval for tuition fees, quarterly installments, and sibling discounts."""
    # Query tuition fees
    res_fee = query_curriculum_rag("What is the quarterly tuition fee schedule for High School?")
    assert res_fee.confidence >= 0.6
    assert len(res_fee.citations) > 0
    assert any(c.category == "tuition" for c in res_fee.citations)
    assert "quarterly" in res_fee.answer.lower()
    assert len(res_fee.suggested_followups) > 0

    # Query sibling discount
    res_sibling = query_curriculum_rag("Do you offer a sibling discount for a second child?")
    assert res_sibling.confidence >= 0.6
    assert any("15%" in fact or "sibling" in fact.lower() for fact in res_sibling.grounded_facts)


def test_curriculum_rag_syllabus_and_policy_queries():
    """Verify grounded retrieval for IB Diploma, Cambridge A-Levels, and Cognia accreditation."""
    res_ib = query_curriculum_rag("Tell me about the IB Diploma subjects and Theory of Knowledge")
    assert any(c.doc_id == "KB-CURR-IB-01" for c in res_ib.citations)
    assert "Theory of Knowledge" in res_ib.answer or "IB" in res_ib.answer

    res_policy = query_curriculum_rag("What is the minimum attendance requirement and Cognia accreditation?")
    assert any("85%" in fact or "attendance" in fact.lower() for fact in res_policy.grounded_facts)


def test_curriculum_rag_custom_document_indexing():
    """Verify adding custom campus-specific documents to the active knowledge base."""
    custom_doc = {
        "doc_id": "KB-ROBOTICS-CLUB-01",
        "title": "NASA Robotics & AI Olympiad Specialization Program",
        "category": "curriculum",
        "grade_levels": ["Grade 9", "Grade 10", "Grade 11", "Grade 12"],
        "keywords": ["robotics", "nasa", "olympiad", "artificial intelligence", "coding"],
        "content": "Our campus hosts the Regional NASA Rover & Robotics AI Lab equipped with humanoid robotics kits and VEX competition arenas.",
    }
    doc_id = add_campus_knowledge_doc(custom_doc)
    assert doc_id == "KB-ROBOTICS-CLUB-01"

    res = query_curriculum_rag("Do you have a NASA robotics or AI club for high school?")
    assert any(c.doc_id == "KB-ROBOTICS-CLUB-01" for c in res.citations)
    assert "NASA" in res.answer or "Robotics" in res.answer


# ---------------------------------------------------------------------------
# 3. Contract 1: Automated Matriculation Handshake Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_execute_matriculation_handshake_end_to_end(db: AsyncSession, org):
    """
    Comprehensive Contract 1 verification:
    1. Creates student and parent permanent User accounts with org membership.
    2. Assigns SMSUserRole (STUDENT, PARENT) and StudentGuardian parent-child link.
    3. Enrolls student in ClassSection and AcademicYear.
    4. Generates FeeInstallmentPlan and 4 quarterly StudentFeeVouchers.
    5. Emits SMSPersonProvisioningEvent and FeeChangeEvent audit trails.
    6. Moves AdmissionsLead stage to ENROLLED with timeline activity log.
    """
    campus, year, section = await _setup_school_environment(db, org.id, code="MATRIC-E2E")
    lead = await _create_test_lead(db, campus.id, email="father.e2e@example.com")

    result = await execute_matriculation_handshake(
        db_session=db,
        lead_id=lead.id,
        section_id=section.id,
        tuition_plan_id=None,
        payment_terms={
            "student_email": "zainab.student@school.edu",
            "parent_email": "father.e2e@example.com",
            "roll_number": "RN-2026-0901",
            "installment_count": 4,
            "relationship": "father",
        },
        actor_user_id=101,
    )

    assert result.created_student is True
    assert result.created_parent is True
    assert result.created_enrollment is True
    assert result.already_matriculated is False

    # 1. Verify Student Account & Org Membership
    student = await db.get(User, result.student_user.id)
    assert student is not None
    assert student.email == "zainab.student@school.edu"
    assert student.first_name == "Zainab"

    student_org = (
        await db.exec(
            select(UserOrganization).where(
                UserOrganization.user_id == student.id,
                UserOrganization.org_id == org.id,
            )
        )
    ).first()
    assert student_org is not None

    # 2. Verify Parent Account & Org Membership
    parent = await db.get(User, result.parent_user.id)
    assert parent is not None
    assert parent.email == "father.e2e@example.com"
    assert parent.first_name == "Tariq"

    parent_org = (
        await db.exec(
            select(UserOrganization).where(
                UserOrganization.user_id == parent.id,
                UserOrganization.org_id == org.id,
            )
        )
    ).first()
    assert parent_org is not None

    # 3. Verify Roles
    student_role = (
        await db.exec(
            select(SMSUserRole).where(
                SMSUserRole.user_id == student.id,
                SMSUserRole.role == SchoolRole.STUDENT,
            )
        )
    ).first()
    assert student_role is not None
    assert student_role.campus_id == campus.id
    assert student_role.is_active is True

    parent_role = (
        await db.exec(
            select(SMSUserRole).where(
                SMSUserRole.user_id == parent.id,
                SMSUserRole.role == SchoolRole.PARENT,
            )
        )
    ).first()
    assert parent_role is not None
    assert parent_role.campus_id == campus.id
    assert parent_role.is_active is True

    # 4. Verify StudentGuardian Link
    guardian_link = (
        await db.exec(
            select(StudentGuardian).where(
                StudentGuardian.guardian_user_id == parent.id,
                StudentGuardian.student_id == student.id,
            )
        )
    ).first()
    assert guardian_link is not None
    assert guardian_link.is_primary_contact is True
    assert guardian_link.relationship == "father"

    # 5. Verify StudentEnrollment
    enrollment = await db.get(StudentEnrollment, result.enrollment.id)
    assert enrollment is not None
    assert enrollment.student_id == student.id
    assert enrollment.section_id == section.id
    assert enrollment.academic_year_id == year.id
    assert enrollment.roll_number == "RN-2026-0901"
    assert enrollment.status == "active"

    # 6. Verify Fee Schedule & Quarterly Vouchers
    plan = await db.get(FeeInstallmentPlan, result.installment_plan.id)
    assert plan is not None
    assert plan.student_id == student.id
    assert plan.installment_count == 4
    assert plan.status == InstallmentPlanStatus.ACTIVE

    vouchers = (
        await db.exec(
            select(StudentFeeVoucher)
            .where(StudentFeeVoucher.student_id == student.id)
            .order_by(StudentFeeVoucher.installment_number.asc())
        )
    ).all()
    assert len(vouchers) == 4
    for idx, v in enumerate(vouchers, start=1):
        assert v.installment_plan_id == plan.id
        assert v.installment_number == idx
        assert v.status == VoucherStatus.UNPAID
        assert v.total_amount > 0.0
        assert v.balance_amount == v.total_amount
        assert "Q" in v.voucher_no

    # 7. Verify Audit Trails
    student_prov_event = (
        await db.exec(
            select(SMSPersonProvisioningEvent).where(
                SMSPersonProvisioningEvent.subject_user_id == student.id,
                SMSPersonProvisioningEvent.role == SchoolRole.STUDENT.value,
            )
        )
    ).first()
    assert student_prov_event is not None
    assert student_prov_event.action == PersonProvisioningAction.CREATED

    parent_prov_event = (
        await db.exec(
            select(SMSPersonProvisioningEvent).where(
                SMSPersonProvisioningEvent.subject_user_id == parent.id,
                SMSPersonProvisioningEvent.role == SchoolRole.PARENT.value,
            )
        )
    ).first()
    assert parent_prov_event is not None
    assert parent_prov_event.linked_student_id == student.id

    fee_events = (
        await db.exec(
            select(FeeChangeEvent).where(
                FeeChangeEvent.student_id == student.id,
                FeeChangeEvent.action == FeeChangeAction.VOUCHER_CREATED,
            )
        )
    ).all()
    assert len(fee_events) == 4

    # 8. Verify Lead Funnel Transition
    refreshed_lead = await db.get(AdmissionsLead, lead.id)
    assert refreshed_lead.stage == LeadStage.ENROLLED

    stage_logs = (
        await db.exec(
            select(LeadActivityLog).where(
                LeadActivityLog.lead_id == lead.id,
                LeadActivityLog.activity_type == ActivityType.STAGE_CHANGE,
            )
        )
    ).all()
    assert len(stage_logs) >= 1
    assert "Matriculation Handshake Completed" in stage_logs[-1].summary


@pytest.mark.asyncio
async def test_matriculation_handshake_idempotency(db: AsyncSession, org):
    """Executing matriculation handshake twice converges cleanly without duplicate rows."""
    campus, year, section = await _setup_school_environment(db, org.id, code="MATRIC-IDEM")
    lead = await _create_test_lead(db, campus.id, email="repeat.parent@example.com")

    terms = {
        "student_email": "repeat.child@school.edu",
        "parent_email": "repeat.parent@example.com",
    }

    first = await execute_matriculation_handshake(
        db_session=db,
        lead_id=lead.id,
        section_id=section.id,
        payment_terms=terms,
    )
    assert first.already_matriculated is False

    second = await execute_matriculation_handshake(
        db_session=db,
        lead_id=lead.id,
        section_id=section.id,
        payment_terms=terms,
    )
    assert second.already_matriculated is True
    assert second.student_user.id == first.student_user.id
    assert second.parent_user.id == first.parent_user.id
    assert second.enrollment.id == first.enrollment.id
    assert second.installment_plan.id == first.installment_plan.id
    assert len(second.vouchers) == len(first.vouchers)

    # Ensure no duplicate student users
    students = (
        await db.exec(select(User).where(User.email == "repeat.child@school.edu"))
    ).all()
    assert len(students) == 1


@pytest.mark.asyncio
async def test_matriculation_handshake_applies_accepted_scholarship_offer(db: AsyncSession, org):
    """When lead has an accepted scholarship offer, the discount is factored into generated fee vouchers."""
    campus, year, section = await _setup_school_environment(db, org.id, code="MATRIC-SCHOL")
    lead = await _create_test_lead(db, campus.id, email="scholarship.parent@example.com")

    # Attach accepted 20% scholarship offer
    offer = ScholarshipOffer(
        lead_id=lead.id,
        campus_id=campus.id,
        tuition_discount_percentage=20.0,
        final_tuition_amount=9600.0,
        valid_until=datetime.date.today() + datetime.timedelta(days=30),
        status=OfferStatus.ACCEPTED,
    )
    db.add(offer)
    await db.commit()

    result = await execute_matriculation_handshake(
        db_session=db,
        lead_id=lead.id,
        section_id=section.id,
        payment_terms={"student_email": "scholar.child@school.edu"},
    )

    assert len(result.vouchers) == 4
    for v in result.vouchers:
        assert v.discount > 0.0
        assert "20% scholarship applied" in (v.remarks or "")


@pytest.mark.asyncio
async def test_matriculation_handshake_rejects_lost_lead_and_invalid_section(db: AsyncSession, org):
    """Verify validation boundaries: rejecting LOST leads and non-existent sections."""
    campus, year, section = await _setup_school_environment(db, org.id, code="MATRIC-ERR")
    lead = await _create_test_lead(db, campus.id, email="lost.parent@example.com", stage=LeadStage.LOST)

    # Rejects LOST lead
    with pytest.raises(HTTPException) as exc_lost:
        await execute_matriculation_handshake(
            db_session=db,
            lead_id=lead.id,
            section_id=section.id,
        )
    assert exc_lost.value.status_code == 409

    # Rejects non-existent section
    lead.stage = LeadStage.OFFER_SENT
    db.add(lead)
    await db.commit()

    with pytest.raises(HTTPException) as exc_sec:
        await execute_matriculation_handshake(
            db_session=db,
            lead_id=lead.id,
            section_id=999999,
        )
    assert exc_sec.value.status_code == 400


# ---------------------------------------------------------------------------
# 4. Router Endpoints Verification Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_matriculation_router_endpoints(db: AsyncSession, org):
    """Verify HTTP router handlers for handshake, BANT qualification, counselor query, and status."""
    campus, year, section = await _setup_school_environment(db, org.id, code="MATRIC-RTR")
    lead = await _create_test_lead(db, campus.id, email="router.parent@example.com")

    # 1. Test POST /sms/matriculation/leads/{lead_id}/qualify-bant
    bant_resp = await post_qualify_lead_bant(
        lead_id=lead.id,
        payload=BANTQualifyRequest(stated_budget=15000.0, start_timeline="immediate"),
        session=db,
        principal=SUPERADMIN,
    )
    assert bant_resp.total_score >= 80.0
    assert bant_resp.tier == BANTTier.HOT

    # 2. Test POST /sms/matriculation/counselor/query
    counselor_resp = await post_counselor_query(
        payload=CounselorQueryRequest(query="What is the admission and tuition policy?"),
        session=db,
        principal=SUPERADMIN,
    )
    assert counselor_resp.confidence >= 0.5
    assert len(counselor_resp.citations) > 0

    # 3. Test POST /sms/matriculation/handshake
    handshake_resp = await post_matriculation_handshake(
        payload=MatriculationHandshakeRequest(
            lead_id=lead.id,
            section_id=section.id,
            student_email="router.student@school.edu",
            parent_email="router.parent@example.com",
            installment_count=4,
        ),
        session=db,
        principal=SUPERADMIN,
    )
    assert handshake_resp.status == "matriculated"
    assert handshake_resp.student.email == "router.student@school.edu"
    assert handshake_resp.parent.email == "router.parent@example.com"
    assert handshake_resp.fee_schedule.vouchers_count == 4

    # 4. Test GET /sms/matriculation/leads/{lead_id}/status
    status_resp = await get_matriculation_status(
        lead_id=lead.id,
        session=db,
        principal=SUPERADMIN,
    )
    assert status_resp.is_matriculated is True
    assert status_resp.vouchers_count == 4
    assert status_resp.section_id == section.id
