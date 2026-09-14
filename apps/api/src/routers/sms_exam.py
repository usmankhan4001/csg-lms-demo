"""
School Examination Router (M04).

Scheduling, invigilation records, marking, and posting results into the
existing gradebook.

PROCTORING: this module records an invigilated exam; it does not proctor one.
There is no webcam monitoring, browser lockdown, screen capture or automated
cheating detection anywhere in this codebase, and the endpoints below should
not be described as providing any. `POST /{exam_id}/incidents` is a human
invigilator writing down what they observed.
"""

import datetime
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
    require_roles,
)
from src.db.sms_exam import (
    Exam,
    ExamIncident,
    ExamResult,
    ExamSectionSchedule,
    ExamStatus,
)
from src.schemas.sms_exam import (
    BatchExamResultRequest,
    ExamCreate,
    ExamIncidentCreate,
    ExamIncidentRead,
    ExamRead,
    ExamResultRead,
    ExamResultSummary,
    ExamSectionScheduleCreate,
    ExamSectionScheduleRead,
    ExamSittingUpdate,
    ExamUpdate,
    PostResultsResponse,
)
from src.db.sms_exam_extended import ResitStatus
from src.schemas.sms_exam_extended import (
    AllocateSeatsRequest,
    AllocateSeatsResponse,
    ApproveResitRequest,
    ResitCandidate,
    ResitRead,
    ScheduleResitRequest,
    SeatAllocationRead,
)
from src.services.sms.exam_extended import (
    ResitError,
    SeatingError,
    allocate_seats,
    approve_resit,
    list_resits,
    list_seats,
    schedule_resit,
    suggest_resit_candidates,
)
from src.security.features_utils.dependencies import require_sms_exam_feature
from src.services.sms.exam import (
    ExamNotFoundError,
    ExamNotGradebookLinkedError,
    ExamResultsAlreadyPostedError,
    _result_percentage,
    log_exam_incident,
    post_exam_results_to_gradebook,
    summarize_exam_results,
)

router = APIRouter(dependencies=[Depends(require_sms_exam_feature)])

EXAM_STAFF_ROLES = [TEACHER, SCHOOL_ADMIN, SUPER_ADMIN]
EXAM_ADMIN_ROLES = [SCHOOL_ADMIN, SUPER_ADMIN]


def _to_result_read(result: ExamResult, total_marks: float, pass_marks: float) -> ExamResultRead:
    pct = _result_percentage(result, total_marks)
    return ExamResultRead(
        id=result.id,
        exam_id=result.exam_id,
        student_id=result.student_id,
        marks_obtained=result.marks_obtained,
        attendance_status=result.attendance_status,
        percentage=pct,
        # None, not False: an unmarked student has not failed, they are unmarked.
        passed=(result.marks_obtained >= pass_marks) if result.marks_obtained is not None else None,
        remarks=result.remarks,
        marked_by=result.marked_by,
        marked_at=result.marked_at,
        posted_to_gradebook_at=result.posted_to_gradebook_at,
    )


@router.post(
    "/",
    response_model=ExamRead,
    status_code=status.HTTP_201_CREATED,
    summary="Schedule an Exam",
)
async def create_exam(
    payload: ExamCreate,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(EXAM_ADMIN_ROLES)),
) -> Exam:
    if payload.pass_marks > payload.total_marks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="pass_marks cannot exceed total_marks.",
        )

    exam = Exam(
        campus_id=payload.campus_id,
        academic_term_id=payload.academic_term_id,
        course_id=payload.course_id,
        title=payload.title,
        exam_type=payload.exam_type,
        exam_date=payload.exam_date,
        start_time=payload.start_time,
        duration_minutes=payload.duration_minutes,
        total_marks=payload.total_marks,
        pass_marks=payload.pass_marks,
        assessment_plan_id=payload.assessment_plan_id,
        instructions=payload.instructions,
        created_by=principal.raw_claims.get("lh_user_id"),
    )
    session.add(exam)
    await session.commit()
    await session.refresh(exam)
    return exam


@router.get(
    "/",
    response_model=List[ExamRead],
    summary="List Exams",
)
async def list_exams(
    campus_id: Optional[int] = Query(None),
    academic_term_id: Optional[int] = Query(None),
    course_id: Optional[int] = Query(None),
    exam_status: Optional[ExamStatus] = Query(None),
    upcoming_only: bool = Query(False, description="Only exams dated today or later"),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> List[Exam]:
    query = select(Exam)
    if campus_id is not None:
        query = query.where(Exam.campus_id == campus_id)
    if academic_term_id is not None:
        query = query.where(Exam.academic_term_id == academic_term_id)
    if course_id is not None:
        query = query.where(Exam.course_id == course_id)
    if exam_status is not None:
        query = query.where(Exam.status == exam_status)
    if upcoming_only:
        query = query.where(Exam.exam_date >= datetime.date.today())

    # Campus isolation, mirroring sms_campus.list_campuses: a non-superadmin
    # pinned to a campus never sees another campus's exam timetable.
    if principal.campus_id and not principal.is_superadmin and not principal.has_role(SCHOOL_ADMIN):
        query = query.where(Exam.campus_id == principal.campus_id)

    query = query.order_by(Exam.exam_date)
    return list((await session.execute(query)).scalars().all())


@router.get(
    "/{exam_id}",
    response_model=ExamRead,
    summary="Get an Exam",
)
async def get_exam(
    exam_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> Exam:
    exam = await session.get(Exam, exam_id)
    if exam is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")
    return exam


@router.patch(
    "/{exam_id}",
    response_model=ExamRead,
    summary="Update an Exam",
)
async def update_exam(
    exam_id: int,
    payload: ExamUpdate,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(EXAM_ADMIN_ROLES)),
) -> Exam:
    exam = await session.get(Exam, exam_id)
    if exam is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    if exam.status == ExamStatus.RESULTS_POSTED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Results for this exam have already been posted to the gradebook. "
                "Changing total_marks or the assessment plan now would leave "
                "recorded grades inconsistent with the exam they came from."
            ),
        )

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(exam, key, value)
    session.add(exam)
    await session.commit()
    await session.refresh(exam)
    return exam


@router.post(
    "/{exam_id}/sections",
    response_model=ExamSectionScheduleRead,
    status_code=status.HTTP_201_CREATED,
    summary="Schedule a Section to Sit an Exam",
)
async def schedule_section(
    exam_id: int,
    payload: ExamSectionScheduleCreate,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(EXAM_ADMIN_ROLES)),
) -> ExamSectionSchedule:
    exam = await session.get(Exam, exam_id)
    if exam is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    existing = (await session.execute(
        select(ExamSectionSchedule).where(
            and_(
                ExamSectionSchedule.exam_id == exam_id,
                ExamSectionSchedule.section_id == payload.section_id,
            )
        )
    )).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This section is already scheduled for this exam.",
        )

    sched = ExamSectionSchedule(
        exam_id=exam_id,
        section_id=payload.section_id,
        room_number=payload.room_number,
        invigilator_id=payload.invigilator_id,
    )
    session.add(sched)
    await session.commit()
    await session.refresh(sched)
    return sched


@router.get(
    "/{exam_id}/sections",
    response_model=List[ExamSectionScheduleRead],
    summary="List Sections Sitting an Exam",
)
async def list_exam_sections(
    exam_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> List[ExamSectionSchedule]:
    stmt = select(ExamSectionSchedule).where(ExamSectionSchedule.exam_id == exam_id)
    return list((await session.execute(stmt)).scalars().all())


@router.patch(
    "/sections/{schedule_id}/sitting",
    response_model=ExamSectionScheduleRead,
    summary="Record Actual Exam Start/End Times",
    description=(
        "The invigilator's record of when the room actually started and "
        "finished, which is often not the scheduled time."
    ),
)
async def record_sitting_times(
    schedule_id: int,
    payload: ExamSittingUpdate,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(EXAM_STAFF_ROLES)),
) -> ExamSectionSchedule:
    sched = await session.get(ExamSectionSchedule, schedule_id)
    if sched is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam schedule not found")

    if payload.actual_start_at is not None:
        sched.actual_start_at = payload.actual_start_at
    if payload.actual_end_at is not None:
        sched.actual_end_at = payload.actual_end_at
    session.add(sched)
    await session.commit()
    await session.refresh(sched)
    return sched


@router.post(
    "/{exam_id}/results",
    response_model=List[ExamResultRead],
    summary="Enter or Update Exam Results",
    description=(
        "Upserts per-student marks. A student may be recorded with no mark "
        "(marks_obtained omitted) -- that means 'not yet marked', and is never "
        "treated as a zero."
    ),
)
async def enter_results(
    exam_id: int,
    payload: BatchExamResultRequest,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(EXAM_STAFF_ROLES)),
) -> List[ExamResultRead]:
    exam = await session.get(Exam, exam_id)
    if exam is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    now = datetime.datetime.now(datetime.timezone.utc)
    marker = principal.raw_claims.get("lh_user_id")
    out: List[ExamResultRead] = []

    for item in payload.entries:
        if item.marks_obtained is not None and item.marks_obtained > exam.total_marks:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Student {item.student_id}: marks_obtained "
                    f"({item.marks_obtained}) exceeds the exam total "
                    f"({exam.total_marks})."
                ),
            )

        existing = (await session.execute(
            select(ExamResult).where(
                and_(ExamResult.exam_id == exam_id, ExamResult.student_id == item.student_id)
            )
        )).scalar_one_or_none()

        if existing is None:
            existing = ExamResult(
                exam_id=exam_id,
                student_id=item.student_id,
                marks_obtained=item.marks_obtained,
                attendance_status=item.attendance_status,
                remarks=item.remarks,
                marked_by=marker if item.marks_obtained is not None else None,
                marked_at=now if item.marks_obtained is not None else None,
            )
        else:
            existing.marks_obtained = item.marks_obtained
            existing.attendance_status = item.attendance_status
            existing.remarks = item.remarks
            if item.marks_obtained is not None:
                existing.marked_by = marker
                existing.marked_at = now
        session.add(existing)
        await session.flush()
        out.append(_to_result_read(existing, exam.total_marks, exam.pass_marks))

    await session.commit()
    return out


@router.get(
    "/{exam_id}/results",
    response_model=List[ExamResultRead],
    summary="List Exam Results",
)
async def list_results(
    exam_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(EXAM_STAFF_ROLES)),
) -> List[ExamResultRead]:
    exam = await session.get(Exam, exam_id)
    if exam is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")
    stmt = select(ExamResult).where(ExamResult.exam_id == exam_id)
    results = (await session.execute(stmt)).scalars().all()
    return [_to_result_read(r, exam.total_marks, exam.pass_marks) for r in results]


@router.get(
    "/{exam_id}/summary",
    response_model=ExamResultSummary,
    summary="Exam Result Statistics",
)
async def exam_summary(
    exam_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(EXAM_STAFF_ROLES)),
) -> ExamResultSummary:
    exam = await session.get(Exam, exam_id)
    if exam is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")
    return await summarize_exam_results(session, exam)


@router.post(
    "/{exam_id}/post-to-gradebook",
    response_model=PostResultsResponse,
    summary="Post Exam Results to the Gradebook",
    description=(
        "Writes marked results as GradebookEntry rows against the exam's "
        "assessment plan, so the existing weighted-GPA engine grades them. "
        "Unmarked and absent students are skipped, never written as zeros."
    ),
    responses={
        400: {"description": "Exam is not linked to an assessment plan"},
        409: {"description": "Results already posted"},
    },
)
async def post_to_gradebook(
    exam_id: int,
    force: bool = Query(False, description="Re-post results that were already posted"),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(EXAM_STAFF_ROLES)),
) -> PostResultsResponse:
    try:
        written, skipped, plan_id = await post_exam_results_to_gradebook(
            session=session,
            exam_id=exam_id,
            graded_by=principal.raw_claims.get("lh_user_id"),
            force=force,
        )
    except ExamNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ExamNotGradebookLinkedError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ExamResultsAlreadyPostedError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    return PostResultsResponse(
        exam_id=exam_id,
        entries_written=written,
        entries_skipped=skipped,
        already_posted=force,
        assessment_plan_id=plan_id,
        message=(
            f"{written} result(s) posted to the gradebook. "
            f"{skipped} skipped (unmarked, absent or exempt)."
        ),
    )


@router.post(
    "/{exam_id}/incidents",
    response_model=ExamIncidentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Log an Invigilation Incident",
    description=(
        "A human invigilator's written record of something observed in the "
        "exam room. This is not automated proctoring -- no monitoring of any "
        "kind is performed."
    ),
)
async def create_incident(
    exam_id: int,
    payload: ExamIncidentCreate,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(EXAM_STAFF_ROLES)),
) -> ExamIncident:
    exam = await session.get(Exam, exam_id)
    if exam is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    return await log_exam_incident(
        session=session,
        exam_id=exam_id,
        description=payload.description,
        severity=payload.severity,
        section_id=payload.section_id,
        student_id=payload.student_id,
        reported_by=principal.raw_claims.get("lh_user_id"),
    )


@router.get(
    "/{exam_id}/incidents",
    response_model=List[ExamIncidentRead],
    summary="List Invigilation Incidents",
)
async def list_incidents(
    exam_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(EXAM_STAFF_ROLES)),
) -> List[ExamIncident]:
    stmt = select(ExamIncident).where(ExamIncident.exam_id == exam_id).order_by(
        ExamIncident.reported_at.desc()
    )
    return list((await session.execute(stmt)).scalars().all())


# ─────────────────────────────────────────────────────────────────────────────
# Seating and resits (M04)
#
# Both refuse rather than guess. A seating clash and a duplicate resit are
# data-entry mistakes a school needs told about: an auto-reseated candidate
# turns up to find someone in their chair, which is worse than an error now.
#
# PROCTORING REMAINS OUT OF SCOPE, deliberately. This module records an
# INVIGILATED exam (see the module docstring) -- who sat where, who watched,
# what happened in the room. It does not observe candidates through a webcam,
# and nothing here quietly starts to.
# ─────────────────────────────────────────────────────────────────────────────


@router.post(
    "/sittings/{schedule_id}/seats",
    response_model=AllocateSeatsResponse,
    summary="Allocate Exam Seats",
    description=(
        "Allocates candidates to seats for one section's sitting. A clash is "
        "SKIPPED with a stated reason rather than resolved, so one bad row in "
        "a hall of 200 does not abort the allocation and nothing is silently "
        "moved. Set replace_existing to reseat deliberately."
    ),
)
async def allocate_exam_seats(
    schedule_id: int,
    payload: AllocateSeatsRequest,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(EXAM_STAFF_ROLES)),
) -> AllocateSeatsResponse:
    try:
        written, skipped = await allocate_seats(
            session=session,
            schedule_id=schedule_id,
            allocations=[
                (a.student_id, a.seat_label, a.notes) for a in payload.allocations
            ],
            allocated_by_user_id=(principal.raw_claims or {}).get("lh_user_id"),
            replace_existing=payload.replace_existing,
        )
    except SeatingError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return AllocateSeatsResponse(
        schedule_id=schedule_id,
        allocated=[SeatAllocationRead.model_validate(r) for r in written],
        skipped=skipped,
    )


@router.get(
    "/sittings/{schedule_id}/seats",
    response_model=List[SeatAllocationRead],
    summary="List Exam Seat Allocations",
)
async def list_exam_seats(
    schedule_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(EXAM_STAFF_ROLES)),
) -> List[SeatAllocationRead]:
    rows = await list_seats(session=session, schedule_id=schedule_id)
    return [SeatAllocationRead.model_validate(r) for r in rows]


@router.post(
    "/{exam_id}/resits",
    response_model=ResitRead,
    status_code=status.HTTP_201_CREATED,
    summary="Approve a Resit",
    description=(
        "Approves a second sitting. NEVER edits the original result: both "
        "sittings stay readable, so a school asked why a grade changed can "
        "show the record."
    ),
)
async def approve_exam_resit(
    exam_id: int,
    payload: ApproveResitRequest,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(EXAM_ADMIN_ROLES)),
) -> ResitRead:
    try:
        row = await approve_resit(
            session=session,
            original_exam_id=exam_id,
            student_id=payload.student_id,
            reason=payload.reason,
            reason_detail=payload.reason_detail,
            approved_by_user_id=(principal.raw_claims or {}).get("lh_user_id"),
        )
    except ResitError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return ResitRead.model_validate(row)


@router.patch(
    "/resits/{resit_id}/schedule",
    response_model=ResitRead,
    summary="Schedule an Approved Resit",
)
async def schedule_exam_resit(
    resit_id: int,
    payload: ScheduleResitRequest,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(EXAM_ADMIN_ROLES)),
) -> ResitRead:
    try:
        row = await schedule_resit(
            session=session, resit_id=resit_id, resit_exam_id=payload.resit_exam_id
        )
    except ResitError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return ResitRead.model_validate(row)


@router.get(
    "/resits",
    response_model=List[ResitRead],
    summary="List Resits",
)
async def list_exam_resits(
    original_exam_id: Optional[int] = Query(None),
    student_id: Optional[int] = Query(None),
    resit_status: Optional[ResitStatus] = Query(None),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(EXAM_STAFF_ROLES)),
) -> List[ResitRead]:
    rows = await list_resits(
        session=session,
        original_exam_id=original_exam_id,
        student_id=student_id,
        status=resit_status,
    )
    return [ResitRead.model_validate(r) for r in rows]


@router.get(
    "/{exam_id}/resit-candidates",
    response_model=List[ResitCandidate],
    summary="Suggest Resit Candidates",
    description=(
        "Candidates a school MAY want to offer a resit, each with the evidence "
        "from the record. Deliberately a suggestion, never an automatic "
        "approval: whether an absent child resits is a judgement about that "
        "child. A candidate who sat but has no mark is reported as an unmarked "
        "paper to chase, NOT as a failure."
    ),
)
async def suggest_exam_resit_candidates(
    exam_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(EXAM_STAFF_ROLES)),
) -> List[ResitCandidate]:
    rows = await suggest_resit_candidates(session=session, exam_id=exam_id)
    return [ResitCandidate(**r) for r in rows]
