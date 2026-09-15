"""
Automated Matriculation Handshake & Admissions Counselor Router
===============================================================
Phase 3 RevOps API:
- POST /sms/matriculation/handshake: Executes Contract 1 Automated Matriculation Handshake.
- POST /sms/matriculation/leads/{lead_id}/qualify-bant: 5-Factor BANT Lead Qualification.
- POST /sms/matriculation/counselor/query: 24/7 Grounded Curriculum RAG Admissions Counselor.
- GET /sms/matriculation/leads/{lead_id}/status: Real-time matriculation & fee status.
"""

from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.events.database import get_db_session
from src.core.keycloak_auth import (
    SCHOOL_ADMIN,
    STAFF,
    SUPER_ADMIN,
    KeycloakUserPrincipal,
    get_current_user_principal,
    require_roles,
)
from src.db.sms_campus import ClassSection, StudentEnrollment
from src.db.sms_fees import StudentFeeVoucher
from src.db.sms_identity import SchoolRole, SMSUserRole, StudentGuardian
from src.db.sms_revops import AdmissionsLead, LeadStage
from src.db.users import User
from src.schemas.sms_matriculation import (
    BANTQualifyRequest,
    BANTQualifyResponse,
    CounselorQueryRequest,
    CounselorQueryResponse,
    EnrollmentSummary,
    FeeScheduleSummary,
    MatriculationHandshakeRequest,
    MatriculationHandshakeResponse,
    MatriculationStatusResponse,
    ParentProfileSummary,
    StudentProfileSummary,
)
from src.security.features_utils.dependencies import require_revops_feature
from src.security.school_ownership import assert_campus_allowed
from src.services.ai.bant_scoring import calculate_bant_score
from src.services.ai.curriculum_rag import query_curriculum_rag
from src.services.sms.matriculation import execute_matriculation_handshake

_ADMISSIONS_ROLES = [SUPER_ADMIN, SCHOOL_ADMIN, STAFF]

router = APIRouter(dependencies=[Depends(require_revops_feature)])


@router.post(
    "/matriculation/handshake",
    response_model=MatriculationHandshakeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Execute Automated Matriculation Handshake (Contract 1)",
    description=(
        "Executes the atomic matriculation handshake: creates student & parent user accounts, "
        "assigns SMSUserRoles, creates parent-child guardian link, enrolls student in class section, "
        "generates structured quarterly fee vouchers, and records non-repudiable audit logs."
    ),
    responses={
        400: {"description": "Invalid section, campus, or academic year configuration"},
        404: {"description": "Admissions lead not found"},
        409: {"description": "Lead marked Lost"},
    },
)
async def post_matriculation_handshake(
    payload: MatriculationHandshakeRequest,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_ADMISSIONS_ROLES)),
) -> MatriculationHandshakeResponse:
    # Verify campus access
    section = await session.get(ClassSection, payload.section_id)
    if not section:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Class section {payload.section_id} not found.",
        )
    assert_campus_allowed(principal, section.campus_id)

    actor_id: Optional[int] = None
    if principal.raw_claims and "lh_user_id" in principal.raw_claims:
        actor_id = principal.raw_claims.get("lh_user_id")

    payment_terms: Dict[str, Any] = {
        "student_email": payload.student_email,
        "parent_email": payload.parent_email,
        "academic_year_id": payload.academic_year_id,
        "roll_number": payload.roll_number,
        "installment_count": payload.installment_count,
        "relationship": payload.relationship,
    }
    if payload.discount_percentage is not None:
        payment_terms["discount_percentage"] = payload.discount_percentage

    result = await execute_matriculation_handshake(
        db_session=session,
        lead_id=payload.lead_id,
        section_id=payload.section_id,
        tuition_plan_id=payload.tuition_plan_id,
        payment_terms=payment_terms,
        actor_user_id=actor_id,
    )

    return MatriculationHandshakeResponse(
        lead_id=result.lead.id,
        status="matriculated",
        student=StudentProfileSummary(
            id=result.student_user.id,
            name=f"{result.student_user.first_name} {result.student_user.last_name}".strip(),
            email=result.student_user.email,
            created=result.created_student,
        ),
        parent=ParentProfileSummary(
            id=result.parent_user.id,
            name=f"{result.parent_user.first_name} {result.parent_user.last_name}".strip(),
            email=result.parent_user.email,
            created=result.created_parent,
        ),
        enrollment=EnrollmentSummary(
            id=result.enrollment.id,
            section_id=result.enrollment.section_id,
            academic_year_id=result.enrollment.academic_year_id,
            status=result.enrollment.status,
            created=result.created_enrollment,
        ),
        fee_schedule=FeeScheduleSummary(
            installment_plan_id=result.installment_plan.id,
            installment_count=result.installment_plan.installment_count,
            vouchers_count=len(result.vouchers),
            total_invoiced=sum(v.total_amount for v in result.vouchers),
            voucher_numbers=[v.voucher_no for v in result.vouchers],
        ),
        already_matriculated=result.already_matriculated,
    )


@router.post(
    "/matriculation/leads/{lead_id}/qualify-bant",
    response_model=BANTQualifyResponse,
    summary="5-Factor BANT Lead Qualification",
    description=(
        "Scores admissions lead across Budget (25pts), Authority (25pts), Need (25pts), "
        "and Timeline (25pts) to assign HOT (>=80), WARM (60-79), COLD (40-59), or NURTURE (<40) tier."
    ),
)
async def post_qualify_lead_bant(
    lead_id: int,
    payload: Optional[BANTQualifyRequest] = None,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_ADMISSIONS_ROLES)),
) -> BANTQualifyResponse:
    stmt = select(AdmissionsLead).where(AdmissionsLead.id == lead_id)
    lead = (await session.execute(stmt)).scalar_one_or_none()
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Admissions lead {lead_id} not found.",
        )
    assert_campus_allowed(principal, lead.campus_id)

    lead_dict = {
        "id": lead.id,
        "campus_id": lead.campus_id,
        "parent_name": lead.parent_name,
        "student_name": lead.student_name,
        "email": lead.email,
        "phone": lead.phone,
        "grade_applying_for": lead.grade_applying_for,
        "grade": lead.grade_applying_for,
        "budget_range": lead.budget_range,
        "notes": lead.notes,
        "whatsapp_consent": lead.whatsapp_consent,
        "email_consent": lead.email_consent,
        "source": lead.source.value if hasattr(lead.source, "value") else str(lead.source),
        "stage": lead.stage.value if hasattr(lead.stage, "value") else str(lead.stage),
    }

    if payload:
        override_data = payload.model_dump(exclude_unset=True)
        lead_dict.update(override_data)

    result = calculate_bant_score(lead_dict)
    return BANTQualifyResponse.model_validate(result.model_dump())


@router.post(
    "/matriculation/counselor/query",
    response_model=CounselorQueryResponse,
    summary="24/7 Grounded Admissions Counselor (Curriculum RAG)",
    description=(
        "Grounds conversational queries against campus syllabi, quarterly tuition fee schedules, "
        "sibling discounts, and institutional policies with source citations."
    ),
)
async def post_counselor_query(
    payload: CounselorQueryRequest,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> CounselorQueryResponse:
    rag_result = query_curriculum_rag(
        query=payload.query,
        campus_id=payload.campus_id,
        grade_level=payload.grade_level,
        category=payload.category,
        top_k=payload.top_k,
    )
    return CounselorQueryResponse.model_validate(rag_result.model_dump())


@router.get(
    "/matriculation/leads/{lead_id}/status",
    response_model=MatriculationStatusResponse,
    summary="Get Lead Matriculation & Enrollment Status",
    description="Retrieves live matriculation records, student/parent account IDs, and generated fee vouchers.",
)
async def get_matriculation_status(
    lead_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> MatriculationStatusResponse:
    stmt = select(AdmissionsLead).where(AdmissionsLead.id == lead_id)
    lead = (await session.execute(stmt)).scalar_one_or_none()
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Admissions lead {lead_id} not found.",
        )

    assert_campus_allowed(principal, lead.campus_id)

    # Check if student exists
    student_user_id: Optional[int] = None
    parent_user_id: Optional[int] = None
    section_id: Optional[int] = None
    academic_year_id: Optional[int] = None
    vouchers_count = 0
    total_balance = 0.0

    # Look up parent by email
    parent = (await session.execute(select(User).where(User.email == lead.email))).scalars().first()
    if parent:
        parent_user_id = parent.id
        # Look up linked student
        link = (
            await session.execute(
                select(StudentGuardian).where(StudentGuardian.guardian_user_id == parent.id)
            )
        ).scalars().first()
        if link:
            student_user_id = link.student_id

    if student_user_id:
        enrollment = (
            await session.execute(
                select(StudentEnrollment).where(StudentEnrollment.student_id == student_user_id)
            )
        ).scalars().first()
        if enrollment:
            section_id = enrollment.section_id
            academic_year_id = enrollment.academic_year_id

        vouchers = (
            await session.execute(
                select(StudentFeeVoucher).where(StudentFeeVoucher.student_id == student_user_id)
            )
        ).scalars().all()
        vouchers_count = len(vouchers)
        total_balance = sum(v.balance_amount for v in vouchers)

    is_matriculated = (lead.stage == LeadStage.ENROLLED and student_user_id is not None)

    return MatriculationStatusResponse(
        lead_id=lead.id,
        student_name=lead.student_name,
        parent_name=lead.parent_name,
        stage=lead.stage.value if hasattr(lead.stage, "value") else str(lead.stage),
        is_matriculated=is_matriculated,
        student_user_id=student_user_id,
        parent_user_id=parent_user_id,
        section_id=section_id,
        academic_year_id=academic_year_id,
        vouchers_count=vouchers_count,
        total_balance=round(total_balance, 2),
    )
