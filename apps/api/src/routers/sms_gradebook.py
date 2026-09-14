import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import and_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.events.database import get_db_session
from src.core.keycloak_auth import (
    KeycloakUserPrincipal,
    SCHOOL_ADMIN,
    SUPER_ADMIN,
    TEACHER,
    get_current_user_principal,
    require_roles,
)
from src.db.sms_gradebook import (
    AssessmentPlan,
    GradeChangeAction,
    GradeChangeEvent,
    GradebookEntry,
    GradingScale,
    TermReportCard,
)
from src.schemas.sms_gradebook import (
    AssessmentPlanCreate,
    AssessmentPlanRead,
    BatchGradebookEntryRequest,
    BatchReportCardDraftRequest,
    BatchReportCardOutcome,
    BatchReportCardResponse,
    BatchReportCardSendRequest,
    CourseGradeSummary,
    GenerateReportCardDraftRequest,
    GradebookEntryRead,
    GradeChangeEventRead,
    GradeHistoryResponse,
    GradingScaleCreate,
    GradingScaleRead,
    RecalculateReportCardsRequest,
    ReportCardDraftUpdate,
    SectionGradebookEntriesResponse,
    StudentTermReportCardResponse,
    TermReportCardRecordRead,
)
from src.security.features_utils.dependencies import require_sms_gradebook_feature
from src.security.school_ownership import (
    assert_owns_section_or_privileged,
    require_own_student_or_privileged,
    require_org_id,
)
from src.services.sms.gradebook import (
    ReportCardAlreadySentError,
    ReportCardNotFoundError,
    ReportCardNotSentError,
    batch_generate_report_card_drafts,
    batch_send_report_cards,
    calculate_cumulative_gpa,
    generate_report_card_draft,
    generate_student_term_report_card,
    get_report_card_for_viewer,
    list_report_cards,
    recalculate_report_cards,
    render_report_card_pdf,
    resolve_letter_and_gpa,
    send_report_card,
    update_report_card_draft,
)
from src.db.sms_campus import AcademicTerm
from src.db.users import User
from src.services.notifications import resolve_guardians_of
from src.services.sms.school_events import (
    REPORT_CARD_SENT,
    raise_school_event,
    student_display_name,
)

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(require_sms_gradebook_feature)])

# Roles that may generate/edit/send a report-card draft. Per the product
# decision, the TEACHER approves and sends -- SCHOOL_ADMIN/SUPER_ADMIN are
# included as administrative overrides, not a required second approval step.
REPORT_CARD_STAFF_ROLES = [TEACHER, SCHOOL_ADMIN, SUPER_ADMIN]

# Who may author the gradebook at all. Every write below was previously gated
# only by `get_current_user_principal` -- i.e. ANY authenticated user -- so a
# STUDENT could define assessment plans and enter their own marks. The role
# gate is necessary but NOT sufficient for grade entry: TEACHER is not a
# blanket permission over every section, so batch_enter_grades additionally
# asserts the caller owns the section (see below).
_GRADING_STAFF = [TEACHER, SCHOOL_ADMIN, SUPER_ADMIN]

# A grading scale is school-wide configuration, not classroom work: one
# careless edit reletters every grade in the school, so teachers are excluded.
_GRADING_CONFIG = [SCHOOL_ADMIN, SUPER_ADMIN]


async def _assert_may_grade_section(
    principal: KeycloakUserPrincipal,
    section_id: int,
    session: AsyncSession,
) -> None:
    """A teacher may only author grades for a section they actually teach.

    The role gate alone is not enough: TEACHER is not a blanket permission
    over every section, any more than it is a blanket permission to host any
    live class. Single-sources `assert_owns_section_or_privileged` (the same
    check `GET /entries` uses) and only localises the message, whose default
    wording is attendance-specific.
    """
    try:
        await assert_owns_section_or_privileged(principal, section_id, session)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_403_FORBIDDEN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only enter grades for a section you teach.",
            ) from exc
        raise


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
        # A row with no graded credits carries gpa=0.0 only because the
        # column is NOT NULL -- report it as absent, not as a zero GPA.
        cumulative_gpa=record.gpa if record.total_credits > 0 else None,
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
    principal: KeycloakUserPrincipal = Depends(require_roles(_GRADING_CONFIG)),
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
    principal: KeycloakUserPrincipal = Depends(require_roles(_GRADING_STAFF)),
) -> AssessmentPlanRead:
    # A plan carries the weighting every grade in the section is computed
    # against, so a teacher may only add one to a section they actually teach.
    # A NULL section_id is a course-wide plan; that is an administrative act.
    if payload.section_id is not None:
        await _assert_may_grade_section(principal, payload.section_id, session)
    elif not (principal.is_superadmin or principal.has_role(SCHOOL_ADMIN)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only a school admin can create a course-wide assessment plan.",
        )

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
    principal: KeycloakUserPrincipal = Depends(require_roles(_GRADING_STAFF)),
) -> List[GradebookEntryRead]:
    # Verify plan exists
    plan_stmt = select(AssessmentPlan).where(AssessmentPlan.id == payload.assessment_plan_id)
    plan = (await session.execute(plan_stmt)).scalar_one_or_none()
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assessment plan with ID {payload.assessment_plan_id} not found.",
        )

    # This endpoint was reachable by ANY authenticated user: it took
    # `principal` and never referenced it, so a STUDENT could enter grades for
    # any assessment plan, including their own. Role-gated above; here the
    # plan's own section decides whether THIS teacher may mark it.
    if plan.section_id is not None:
        await _assert_may_grade_section(principal, plan.section_id, session)
    elif not (principal.is_superadmin or principal.has_role(SCHOOL_ADMIN)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only a school admin can grade a course-wide assessment plan.",
        )

    # Attribution follows the authenticated grader, never the request body:
    # `graded_by` was client-supplied, so marks could be attributed to another
    # teacher. Same class as the live-class token taking participant identity
    # from the payload.
    grader_id = (principal.raw_claims or {}).get("lh_user_id") or payload.graded_by

    saved_entries: List[GradebookEntry] = []
    # (entry, action, previous_raw_score, previous_letter_grade) captured
    # BEFORE mutation -- once `existing.raw_score` is reassigned the old mark
    # is gone from memory as well as from the row.
    pending_history: List[tuple] = []

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
            prev_raw = existing.raw_score
            prev_letter = existing.letter_grade
            existing.raw_score = item.raw_score
            existing.max_score = plan.max_score
            existing.weighted_score = weighted_score
            existing.letter_grade = letter
            existing.gpa_point = gpa_pt
            existing.remarks = item.remarks
            existing.graded_by = grader_id
            session.add(existing)
            saved_entries.append(existing)
            pending_history.append(
                (existing, GradeChangeAction.CHANGED, prev_raw, prev_letter)
            )
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
                graded_by=grader_id,
            )
            session.add(entry)
            saved_entries.append(entry)
            pending_history.append((entry, GradeChangeAction.CREATED, None, None))

    # Flush so newly-created entries get their primary keys, then write the
    # trail. Both the grades and their history land in the SAME transaction
    # and commit together below: a crash cannot leave a mark changed with no
    # record of the change, which is the only property that makes this an
    # audit trail rather than a best-effort log.
    await session.flush()
    for entry, action, prev_raw, prev_letter in pending_history:
        session.add(
            GradeChangeEvent(
                gradebook_entry_id=entry.id,
                student_id=entry.student_id,
                assessment_plan_id=plan.id,
                section_id=plan.section_id,
                action=action,
                previous_raw_score=prev_raw,
                new_raw_score=entry.raw_score,
                previous_letter_grade=prev_letter,
                new_letter_grade=entry.letter_grade,
                max_score=entry.max_score,
                changed_by_user_id=grader_id,
                reason=payload.reason,
            )
        )

    await session.commit()
    for e in saved_entries:
        await session.refresh(e)

    return [GradebookEntryRead.model_validate(e) for e in saved_entries]


@router.get(
    "/entries",
    response_model=SectionGradebookEntriesResponse,
    summary="Read Saved Grades for a Section",
    description=(
        "Marks already recorded for a section, so the grade-entry matrix can "
        "pre-load instead of starting blank. Returns ONLY entries that exist: "
        "a student with no mark for an assessment is simply absent from the "
        "list, never zero-filled, because 'not marked yet' and 'scored 0' mean "
        "opposite things on a report card."
    ),
    responses={403: {"description": "You can only read grades for a section you teach"}},
)
async def list_section_gradebook_entries(
    section_id: int = Query(..., description="Class section to read marks for"),
    assessment_plan_id: Optional[int] = Query(
        None, description="Restrict to a single assessment plan"
    ),
    academic_term_id: Optional[int] = Query(None, description="Restrict to one academic term"),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> SectionGradebookEntriesResponse:
    # Same authorization the roll-call endpoint uses, single-sourced rather
    # than reimplemented: SUPER_ADMIN/SCHOOL_ADMIN pass, a teacher must
    # actually own the section. Only the message is localised to grades --
    # the helper's own wording is attendance-specific.
    try:
        await assert_owns_section_or_privileged(principal, section_id, session)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_403_FORBIDDEN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only read grades for a section you teach.",
            ) from exc
        raise

    # Which assessment plans belong to this section? A plan with a NULL
    # section_id is course-wide and applies here too -- the same rule the
    # matrix uses client-side when deciding which columns to render.
    plan_conditions = [
        (AssessmentPlan.section_id == section_id) | (AssessmentPlan.section_id.is_(None))
    ]
    if isinstance(assessment_plan_id, int):
        plan_conditions.append(AssessmentPlan.id == assessment_plan_id)
    if isinstance(academic_term_id, int):
        plan_conditions.append(
            (AssessmentPlan.academic_term_id == academic_term_id)
            | (AssessmentPlan.academic_term_id.is_(None))
        )

    plan_ids = list(
        (
            await session.execute(select(AssessmentPlan.id).where(and_(*plan_conditions)))
        ).scalars().all()
    )

    if not plan_ids:
        return SectionGradebookEntriesResponse(
            section_id=section_id, assessment_plan_ids=[], entries=[]
        )

    entries = (
        await session.execute(
            select(GradebookEntry).where(GradebookEntry.assessment_plan_id.in_(plan_ids))
        )
    ).scalars().all()

    return SectionGradebookEntriesResponse(
        section_id=section_id,
        assessment_plan_ids=plan_ids,
        entries=[GradebookEntryRead.model_validate(e) for e in entries],
    )


@router.get(
    "/entries/{entry_id}/history",
    response_model=GradeHistoryResponse,
    summary="Read the Change History of One Mark",
    description=(
        "Append-only audit trail for a single gradebook entry: what the mark "
        "was, what it became, who changed it and when. Answers the question a "
        "grade dispute actually asks -- 'this was 72 last week, who changed "
        "it to 41?' -- which the entry row alone cannot, because it is "
        "updated in place. "
        "STAFF ONLY. Students and parents cannot read this even for their own "
        "marks: the current grade is already visible to them, whereas the "
        "trail names the individual member of staff behind every correction "
        "and may carry an internal reason ('suspected collusion, under "
        "review'). Disclosure is a conversation a school has with a family, "
        "not an API response."
    ),
    responses={
        403: {"description": "You can only read history for a section you teach"},
        404: {"description": "No such gradebook entry"},
    },
)
async def get_grade_history(
    entry_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_GRADING_STAFF)),
) -> GradeHistoryResponse:
    entry = (
        await session.execute(select(GradebookEntry).where(GradebookEntry.id == entry_id))
    ).scalar_one_or_none()
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Gradebook entry with ID {entry_id} not found.",
        )

    plan = (
        await session.execute(
            select(AssessmentPlan).where(AssessmentPlan.id == entry.assessment_plan_id)
        )
    ).scalar_one_or_none()

    # Same ownership rule as authoring the mark: whoever may write it may read
    # how it changed. Deliberately reuses `_assert_may_grade_section` rather
    # than inventing a second rule that could drift away from it.
    if plan is not None and plan.section_id is not None:
        await _assert_may_grade_section(principal, plan.section_id, session)
    elif not (principal.is_superadmin or principal.has_role(SCHOOL_ADMIN)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only a school admin can read history for a course-wide assessment plan.",
        )

    events = (
        await session.execute(
            select(GradeChangeEvent)
            .where(GradeChangeEvent.gradebook_entry_id == entry_id)
            .order_by(GradeChangeEvent.created_at, GradeChangeEvent.id)
        )
    ).scalars().all()

    return GradeHistoryResponse(
        gradebook_entry_id=entry_id,
        student_id=entry.student_id,
        assessment_plan_id=entry.assessment_plan_id,
        events=[GradeChangeEventRead.model_validate(e) for e in events],
    )


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
    principal: KeycloakUserPrincipal = Depends(require_own_student_or_privileged()),
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

    # Sending is the moment the family is entitled to know. No dedupe window is
    # needed: `send_report_card` raises ReportCardAlreadySentError on a second
    # attempt, so this line is unreachable twice for the same card.
    await _announce_report_card(session, record, principal)

    return _to_record_read(record)


async def _announce_report_card(session, record, principal) -> None:
    """Tell the student and their guardians that a report card was released.

    Best-effort by construction: `raise_school_event` cannot propagate, so a
    mail outage cannot undo a send that is already committed. A teacher who
    pressed Send must never see a 500 and press it again.
    """
    student_id = getattr(record, "student_id", None)
    if student_id is None:
        return

    recipients = []
    try:
        student = await session.get(User, student_id)
        if student is not None:
            recipients.append(student)
        recipients.extend(await resolve_guardians_of(session, student_id))
    except Exception:
        logger.warning(
            "Could not resolve who to tell about report card %s; it was sent "
            "but nobody was notified.",
            getattr(record, "id", None),
            exc_info=True,
        )
        return

    if not recipients:
        logger.warning(
            "Report card %s was sent but the student has no account and no "
            "linked guardian, so nobody can be told.",
            getattr(record, "id", None),
        )
        return

    term_name = None
    term_id = getattr(record, "academic_term_id", None)
    if term_id is not None:
        try:
            term = await session.get(AcademicTerm, term_id)
            term_name = getattr(term, "name", None)
        except Exception:
            # A missing term name costs one sentence, not the message: the
            # fabric drops the paragraph that needed it. Better a short true
            # message than "your report card for Term None".
            logger.warning("Could not resolve term name for report card %s", term_id)

    await raise_school_event(
        session,
        event_key=REPORT_CARD_SENT.key,
        org_id=principal.org_id,
        recipients=recipients,
        context={
            "student_name": await student_display_name(session, student_id),
            "term_name": term_name,
            # Deliberately NOT sent: gpa, letter_grade, remarks, ai_narrative.
            # A mark in an email subject line is read by whoever is holding the
            # phone. The family opens the portal for the result itself.
        },
        campus_id=principal.campus_id,
        related_kind="report_card",
        related_id=getattr(record, "id", None),
    )


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


@router.get(
    "/report-card/{report_card_id}/pdf",
    summary="Download a Report Card as PDF",
    description=(
        "Returns the SENT report card as a downloadable PDF, rendered from the "
        "same stored data the JSON endpoint returns. A DRAFT is never "
        "exportable -- not even for staff, who may still read it in-app: a PDF "
        "is detachable and carries no further authorization once saved."
    ),
    response_class=Response,
    responses={
        200: {"content": {"application/pdf": {}}, "description": "The rendered report card"},
        404: {"description": "Report card not found (or not visible to this caller)"},
        409: {"description": "Report card is still a DRAFT and cannot be exported"},
    },
)
async def download_report_card_pdf_endpoint(
    report_card_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> Response:
    # Same visibility gate as the JSON endpoint above, so a PARENT/STUDENT
    # cannot even learn a draft exists.
    is_staff = principal.has_any_role(REPORT_CARD_STAFF_ROLES)
    record = await get_report_card_for_viewer(session, report_card_id, is_staff)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report card not found.")

    try:
        pdf_bytes = render_report_card_pdf(record)
    except ReportCardNotSentError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    filename = f"report-card-{record.student_id}-term-{record.academic_term_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Whole-section term-end operations ──


@router.get(
    "/report-cards",
    response_model=List[TermReportCardRecordRead],
    summary="List Report Cards for a Section",
    description=(
        "Enumerate persisted report cards, so a teacher can see a whole "
        "section's draft/sent state at term end. Nothing else could answer "
        "'which cards in this section are still drafts?' -- a single card was "
        "reachable by id and a single student's by (student, term), but a "
        "section was not visible at a glance. STAFF ONLY: a parent reaches "
        "their own child's card through the by-id endpoint, which enforces the "
        "sent-only rule."
    ),
    responses={403: {"description": "You can only list report cards for a section you teach"}},
)
async def list_report_cards_endpoint(
    section_id: int = Query(..., description="Class section to list report cards for"),
    academic_term_id: Optional[int] = Query(None, description="Restrict to one term"),
    status_filter: Optional[str] = Query(
        None, alias="status", description="Restrict to 'draft' or 'sent'"
    ),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_GRADING_STAFF)),
) -> List[TermReportCardRecordRead]:
    await _assert_may_grade_section(principal, section_id, session)
    records = await list_report_cards(
        session=session,
        section_id=section_id,
        academic_term_id=academic_term_id,
        status_filter=status_filter,
    )
    return [_to_record_read(r) for r in records]


@router.post(
    "/report-cards/batch-draft",
    response_model=BatchReportCardResponse,
    summary="Draft Report Cards for a Whole Section",
    description=(
        "Generates or refreshes a DRAFT report card for every ACTIVELY enrolled "
        "student in the section. Already-sent cards are skipped and reported, "
        "never regenerated. A student with no graded credits is reported as "
        "`drafted_ungraded` rather than being given a zero -- collapsing that "
        "into a plain success would let a teacher send a section believing "
        "every card carried a grade."
    ),
    responses={403: {"description": "You can only draft report cards for a section you teach"}},
)
async def batch_draft_report_cards_endpoint(
    payload: BatchReportCardDraftRequest,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(REPORT_CARD_STAFF_ROLES)),
) -> BatchReportCardResponse:
    await _assert_may_grade_section(principal, payload.section_id, session)
    outcomes = await batch_generate_report_card_drafts(
        session=session,
        section_id=payload.section_id,
        academic_term_id=payload.academic_term_id,
        generate_narrative=payload.generate_narrative,
    )
    return BatchReportCardResponse(
        results=[BatchReportCardOutcome(**o) for o in outcomes]
    )


@router.post(
    "/report-cards/batch-send",
    response_model=BatchReportCardResponse,
    summary="Send Named Report Cards",
    description=(
        "Sends an EXPLICIT list of report card ids. Deliberately NOT keyed on a "
        "section: a section is a moving target, and 'send this section' would "
        "fan out to whoever happens to be enrolled at the moment the button is "
        "pressed -- including a student added since the teacher last looked. A "
        "report card sent to thirty families cannot be recalled, so the caller "
        "must name each card it sends. One bad id is reported, not raised, so "
        "it cannot abort a term-end run half-way through."
    ),
)
async def batch_send_report_cards_endpoint(
    payload: BatchReportCardSendRequest,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(REPORT_CARD_STAFF_ROLES)),
) -> BatchReportCardResponse:
    # Each named card is checked against the section it belongs to, so a
    # teacher cannot send another section's cards by passing their ids.
    for report_card_id in payload.report_card_ids:
        record = await session.get(TermReportCard, report_card_id)
        if record is not None:
            await _assert_may_grade_section(principal, record.section_id, session)

    outcomes = await batch_send_report_cards(
        session=session,
        report_card_ids=payload.report_card_ids,
        sent_by=principal.sub,
    )
    return BatchReportCardResponse(
        results=[BatchReportCardOutcome(**o) for o in outcomes]
    )


@router.post(
    "/report-cards/recalculate",
    response_model=BatchReportCardResponse,
    summary="Recalculate Draft Report Cards After Marks Change",
    description=(
        "Recomputes DRAFT report cards for a section -- for when a late mark "
        "lands or an assessment weighting changes. Explicit and idempotent: "
        "recomputing twice over unchanged marks yields the same numbers. "
        "SENT cards are SKIPPED and reported, never silently recomputed: a "
        "family has already been shown that document, and changing it "
        "underneath them without anybody deciding to is precisely the silent "
        "mutation this must not perform. The teacher's narrative is not "
        "regenerated -- this recomputes numbers, and a hand-edited comment "
        "must survive."
    ),
    responses={403: {"description": "You can only recalculate for a section you teach"}},
)
async def recalculate_report_cards_endpoint(
    payload: RecalculateReportCardsRequest,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(REPORT_CARD_STAFF_ROLES)),
) -> BatchReportCardResponse:
    await _assert_may_grade_section(principal, payload.section_id, session)
    outcomes = await recalculate_report_cards(
        session=session,
        section_id=payload.section_id,
        academic_term_id=payload.academic_term_id,
    )
    return BatchReportCardResponse(
        results=[BatchReportCardOutcome(**o) for o in outcomes]
    )


# ── GPA & Transcript Services (M05) ──

@router.get(
    "/students/{student_id}/gpa",
    summary="Calculate Student Cumulative GPA",
    description=(
        "Cumulative GPA and standing from the student's graded coursework. "
        "Returns null GPA, standing and honor_roll when the student has no "
        "graded courses -- absence of grades is not a 0.0 and not an F. "
        "Weighted GPA was REMOVED: it added +0.5 per course as 'standard "
        "honors weighting', but nothing in the model marks a course as "
        "honours, so it inflated every GPA on a distinction this system "
        "cannot make."
    ),
)
async def calculate_student_gpa(
    student_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_own_student_or_privileged()),
) -> dict:
    """Cumulative GPA, computed by the one grading engine.

    This handler previously carried its own implementation that was both
    fabricating and broken -- see `calculate_cumulative_gpa`'s docstring. The
    logic now lives in the service beside the report-card engine so a
    transcript and a report card cannot disagree about the same student.

    `weighted_gpa` is deliberately GONE rather than reimplemented. The old one
    added +0.5 to every course on the basis that it was "standard honors
    weighting" -- but nothing in this data model marks a course as AP or
    honours, so it inflated every student's GPA on a distinction the system
    cannot actually make. Restoring it needs an honours flag on the course
    first.
    """
    return await calculate_cumulative_gpa(session=session, student_id=student_id)


@router.get(
    "/students/{student_id}/transcript",
    summary="Generate Official Academic Transcript",
    description="Compiles official transcript record with term-by-term course breakdown, credits, and verification hash.",
)
async def generate_official_transcript(
    student_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_own_student_or_privileged()),
) -> dict:
    gpa_info = await calculate_student_gpa(student_id, session, principal)

    # Fetch sent report cards for term history
    report_cards = (
        await session.execute(
            select(TermReportCard)
            .where(
                and_(
                    TermReportCard.student_id == student_id,
                    TermReportCard.status == "sent",
                )
            )
            .order_by(TermReportCard.id.desc())
        )
    ).scalars().all()

    terms_history = []
    for rc in report_cards:
        terms_history.append({
            "term_id": rc.academic_term_id,
            "gpa": rc.gpa,
            "letter_grade": rc.letter_grade,
            "credits_earned": rc.total_credits,
            "courses": rc.course_summaries or [],
            "certified_date": rc.sent_at.isoformat() if rc.sent_at else None,
        })

    # This previously emitted a "verification_seal" that was an UNKEYED
    # sha256 over student_id and the GPA -- both printed on the transcript
    # itself. Anyone holding the document could recompute the seal for any
    # student id and any GPA they liked, so it verified nothing while the
    # document simultaneously claimed "OFFICIAL". A seal that invites reliance
    # it cannot support is worse than no seal, so it is gone rather than
    # reworked: signing it properly (HMAC under auth_jwt_secret_key, as
    # webhooks/crypto.py does) would only mean something alongside a
    # verification endpoint that recomputes it, and there is none.
    return {
        "student_id": student_id,
        "org_id": require_org_id(principal),
        "document_type": "ACADEMIC_TRANSCRIPT_EXPORT",
        "issuing_authority": "CSG LMS Academic Registrar",
        "cumulative_summary": gpa_info,
        "terms_history": terms_history,
        "status": "UNVERIFIED_EXPORT",
        "verification_note": (
            "This export carries no cryptographic signature and is not a "
            "certified transcript. Confirm its contents with the school "
            "registrar before relying on them."
        ),
    }

