from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.events.database import get_db_session
from src.core.keycloak_auth import (
    KeycloakUserPrincipal,
    SCHOOL_ADMIN,
    SUPER_ADMIN,
    TEACHER,
    get_current_user_principal,
)
from src.db.sms_gradebook import (
    AssessmentPlan,
    GradebookEntry,
    GradingScale,
    TermReportCard,
)
from src.schemas.sms_gradebook import (
    AssessmentPlanCreate,
    AssessmentPlanRead,
    BatchGradebookEntryRequest,
    CourseGradeSummary,
    GenerateReportCardDraftRequest,
    GradebookEntryRead,
    GradingScaleCreate,
    GradingScaleRead,
    ReportCardDraftUpdate,
    StudentTermReportCardResponse,
    TermReportCardRecordRead,
)
from src.security.features_utils.dependencies import require_sms_gradebook_feature
from src.services.sms.gradebook import (
    ReportCardAlreadySentError,
    ReportCardNotFoundError,
    generate_report_card_draft,
    generate_student_term_report_card,
    get_report_card_for_viewer,
    resolve_letter_and_gpa,
    send_report_card,
    update_report_card_draft,
)

router = APIRouter(dependencies=[Depends(require_sms_gradebook_feature)])

# Roles that may generate/edit/send a report-card draft. Per the product
# decision, the TEACHER approves and sends -- SCHOOL_ADMIN/SUPER_ADMIN are
# included as administrative overrides, not a required second approval step.
REPORT_CARD_STAFF_ROLES = [TEACHER, SCHOOL_ADMIN, SUPER_ADMIN]


def _to_record_read(record: TermReportCard) -> TermReportCardRecordRead:
    """TermReportCard (DB row) -> TermReportCardRecordRead. Field names
    diverge deliberately (gpa -> cumulative_gpa, letter_grade ->
    overall_letter_grade, course_summaries -> courses) to match
    StudentTermReportCardResponse's existing public naming, so this can't be
    a plain `model_validate(record)` -- built explicitly instead."""
    return TermReportCardRecordRead(
        id=record.id,
        student_id=record.student_id,
        section_id=record.section_id,
        academic_term_id=record.academic_term_id,
        status=record.status,
        total_credits=record.total_credits,
        cumulative_gpa=record.gpa,
        overall_letter_grade=record.letter_grade,
        remarks=record.remarks,
        ai_narrative=record.ai_narrative,
        courses=[CourseGradeSummary(**c) for c in (record.course_summaries or [])],
        calculated_at=record.calculated_at,
        sent_at=record.sent_at,
        sent_by=record.sent_by,
    )


# ── Grading Scales ──

@router.post(
    "/scales",
    response_model=GradingScaleRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create Grading Scale",
)
async def create_grading_scale(
    payload: GradingScaleCreate,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> GradingScaleRead:
    scale = GradingScale(
        name=payload.name,
        description=payload.description,
        intervals=[i.model_dump() for i in payload.intervals],
        is_default=payload.is_default,
    )
    session.add(scale)
    await session.commit()
    await session.refresh(scale)
    return GradingScaleRead.model_validate(scale)


@router.get(
    "/scales",
    response_model=List[GradingScaleRead],
    summary="List Grading Scales",
)
async def list_grading_scales(
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> List[GradingScaleRead]:
    stmt = select(GradingScale)
    scales = (await session.execute(stmt)).scalars().all()
    return [GradingScaleRead.model_validate(s) for s in scales]


# ── Assessment Plans ──

@router.post(
    "/plans",
    response_model=AssessmentPlanRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create Assessment Plan",
    description="Define course/section assessment item with weighting percentage.",
)
async def create_assessment_plan(
    payload: AssessmentPlanCreate,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> AssessmentPlanRead:
    plan = AssessmentPlan(
        course_id=payload.course_id,
        section_id=payload.section_id,
        academic_term_id=payload.academic_term_id,
        assessment_name=payload.assessment_name,
        weight_percentage=payload.weight_percentage,
        max_score=payload.max_score,
    )
    session.add(plan)
    await session.commit()
    await session.refresh(plan)
    return AssessmentPlanRead.model_validate(plan)


@router.get(
    "/plans",
    response_model=List[AssessmentPlanRead],
    summary="List Assessment Plans",
)
async def list_assessment_plans(
    course_id: Optional[int] = Query(None, description="Filter by Course ID"),
    academic_term_id: Optional[int] = Query(None, description="Filter by Academic Term ID"),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> List[AssessmentPlanRead]:
    conditions = []
    if isinstance(course_id, int):
        conditions.append(AssessmentPlan.course_id == course_id)
    if isinstance(academic_term_id, int):
        conditions.append(AssessmentPlan.academic_term_id == academic_term_id)

    stmt = select(AssessmentPlan)
    if conditions:
        stmt = stmt.where(and_(*conditions))
    plans = (await session.execute(stmt)).scalars().all()
    return [AssessmentPlanRead.model_validate(p) for p in plans]


# ── Gradebook Entries ──

@router.post(
    "/entries/batch",
    response_model=List[GradebookEntryRead],
    summary="Batch Enter Grades",
    description="Enter or update scores for an assessment plan.",
)
async def batch_enter_grades(
    payload: BatchGradebookEntryRequest,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> List[GradebookEntryRead]:
    # Verify plan exists
    plan_stmt = select(AssessmentPlan).where(AssessmentPlan.id == payload.assessment_plan_id)
    plan = (await session.execute(plan_stmt)).scalar_one_or_none()
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assessment plan with ID {payload.assessment_plan_id} not found.",
        )

    saved_entries: List[GradebookEntry] = []

    for item in payload.entries:
        if item.raw_score > plan.max_score:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Raw score ({item.raw_score}) cannot exceed max score ({plan.max_score}).",
            )

        pct = (item.raw_score / plan.max_score * 100.0) if plan.max_score > 0 else 0.0
        weighted_score = (pct * plan.weight_percentage) / 100.0
        letter, gpa_pt = resolve_letter_and_gpa(pct)

        # Check existing
        existing_stmt = select(GradebookEntry).where(
            and_(
                GradebookEntry.student_id == item.student_id,
                GradebookEntry.assessment_plan_id == plan.id,
            )
        )
        existing = (await session.execute(existing_stmt)).scalar_one_or_none()

        if existing:
            existing.raw_score = item.raw_score
            existing.max_score = plan.max_score
            existing.weighted_score = weighted_score
            existing.letter_grade = letter
            existing.gpa_point = gpa_pt
            existing.remarks = item.remarks
            existing.graded_by = payload.graded_by
            session.add(existing)
            saved_entries.append(existing)
        else:
            entry = GradebookEntry(
                student_id=item.student_id,
                assessment_plan_id=plan.id,
                raw_score=item.raw_score,
                max_score=plan.max_score,
                weighted_score=weighted_score,
                letter_grade=letter,
                gpa_point=gpa_pt,
                remarks=item.remarks,
                graded_by=payload.graded_by,
            )
            session.add(entry)
            saved_entries.append(entry)

    await session.commit()
    for e in saved_entries:
        await session.refresh(e)

    return [GradebookEntryRead.model_validate(e) for e in saved_entries]


# ── Student Report Cards & GPA ──

@router.get(
    "/report-card/student/{student_id}",
    response_model=StudentTermReportCardResponse,
    summary="Generate Student Term Report Card & GPA",
    description="Calculate weighted GPA and compile complete term report card.",
)
async def get_student_report_card(
    student_id: int,
    section_id: int = Query(..., description="Student Section ID"),
    academic_term_id: int = Query(..., description="Academic Term ID"),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> StudentTermReportCardResponse:
    return await generate_student_term_report_card(
        session=session,
        student_id=student_id,
        section_id=section_id,
        academic_term_id=academic_term_id,
    )


# ── Report Card Draft -> Sent Distribution Lifecycle (Phase 4, Part A.4) ──
#
# TEACHER approves, then explicitly sends. The endpoint above
# (GET /report-card/student/{id}) is the pre-existing on-the-fly GPA preview;
# these endpoints add the persisted draft/sent lifecycle on top of the same
# TermReportCard row without changing that endpoint's behavior.

@router.post(
    "/report-card/student/{student_id}/draft",
    response_model=TermReportCardRecordRead,
    status_code=status.HTTP_201_CREATED,
    summary="Generate/Refresh a DRAFT Report Card",
    description=(
        "Recomputes GPA/grade data (reusing the existing calculation engine) and "
        "generates an AI-assisted narrative comment, producing/refreshing a DRAFT "
        "report card. Fails with 409 if the report card has already been sent."
    ),
)
async def generate_report_card_draft_endpoint(
    student_id: int,
    payload: GenerateReportCardDraftRequest,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> TermReportCardRecordRead:
    if not principal.has_any_role(REPORT_CARD_STAFF_ROLES):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only teachers or school admins can generate a report card.",
        )
    try:
        record = await generate_report_card_draft(
            session=session,
            student_id=student_id,
            section_id=payload.section_id,
            academic_term_id=payload.academic_term_id,
            generate_narrative=payload.generate_narrative,
        )
    except ReportCardAlreadySentError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return _to_record_read(record)


@router.patch(
    "/report-card/{report_card_id}",
    response_model=TermReportCardRecordRead,
    summary="Edit a DRAFT Report Card",
    description="Teacher edits to the narrative/remarks of a still-DRAFT report card. 409 once sent.",
)
async def update_report_card_draft_endpoint(
    report_card_id: int,
    payload: ReportCardDraftUpdate,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> TermReportCardRecordRead:
    if not principal.has_any_role(REPORT_CARD_STAFF_ROLES):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only teachers or school admins can edit a report card.",
        )
    try:
        record = await update_report_card_draft(
            session=session,
            report_card_id=report_card_id,
            ai_narrative=payload.ai_narrative,
            remarks=payload.remarks,
        )
    except ReportCardNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ReportCardAlreadySentError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return _to_record_read(record)


@router.post(
    "/report-card/{report_card_id}/send",
    response_model=TermReportCardRecordRead,
    summary="Send a Report Card",
    description=(
        "Explicit TEACHER-initiated send action -- the only thing that makes a "
        "report card visible to the PARENT role. Never happens automatically."
    ),
)
async def send_report_card_endpoint(
    report_card_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> TermReportCardRecordRead:
    if not principal.has_any_role(REPORT_CARD_STAFF_ROLES):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only teachers or school admins can send a report card.",
        )
    try:
        record = await send_report_card(
            session=session,
            report_card_id=report_card_id,
            sent_by=principal.sub,
        )
    except ReportCardNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ReportCardAlreadySentError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return _to_record_read(record)


@router.get(
    "/report-card/{report_card_id}",
    response_model=TermReportCardRecordRead,
    summary="Get a Report Card by ID",
    description=(
        "Teachers/admins may view a report card in any status. Every other "
        "role (PARENT, STUDENT, ...) can only view it once it has been SENT."
    ),
)
async def get_report_card_by_id_endpoint(
    report_card_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> TermReportCardRecordRead:
    is_staff = principal.has_any_role(REPORT_CARD_STAFF_ROLES)
    record = await get_report_card_for_viewer(session, report_card_id, is_staff)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report card not found.")
    return _to_record_read(record)
