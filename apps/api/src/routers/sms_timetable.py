import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.events.database import get_db_session
from src.core.keycloak_auth import (
    KeycloakUserPrincipal,
    get_current_user_principal,
    require_roles,
)
from src.db.sms_campus import ClassSection
from src.db.sms_timetable import ClassPeriod, DayOfWeek, TimetableSchedule
from src.schemas.sms_timetable import (
    ClassPeriodCreate,
    ClassPeriodRead,
    ClashCheckRequest,
    ClashCheckResponse,
    GenerationRequest,
    GenerationResponse,
    LessonLogCreate,
    LessonLogRead,
    StudentTimetableResponse,
    TeacherTimetableResponse,
    TimetableConflictScanResponse,
    TimetableScheduleCreate,
    TimetableScheduleRead,
    TimetableSlotDetail,
    TimetableSubstitutionCreate,
    TimetableSubstitutionRead,
)
from src.security.features_utils.dependencies import require_sms_timetable_feature
from src.security.school_ownership import (
    assert_campus_allowed,
    assert_owns_section_or_privileged,
    resolve_scoped_campus_id,
)
from src.services.sms.timetable import (
    cancel_substitution,
    check_schedule_clashes,
    create_substitution,
    detect_timetable_clashes,
    fetch_timetable_slots,
    get_student_timetable_slots,
    get_teacher_timetable_slots,
    list_substitutions,
    scan_timetable_conflicts,
)
from src.services.sms.timetable_generation import generate_section_timetable
from src.services.sms.timetable_lessons import (
    get_previous_lesson,
    list_lesson_logs,
    record_lesson_log,
)

# Building the timetable is scheduling: an admin function. A student or parent
# must not be able to invent periods or move a class.
_SCHEDULER = ["SUPER_ADMIN", "SCHOOL_ADMIN"]

# Substitutions are day-to-day cover, so teachers are included alongside
# admins -- arranging cover for a sick colleague is staffroom work, and the
# service already rejects a substitute who is not actually free.
_SUBSTITUTION_MANAGER = ["SUPER_ADMIN", "SCHOOL_ADMIN", "TEACHER", "STAFF"]

# A clash check writes nothing; it answers "would this slot conflict?". It is
# a POST only because it takes a body. Gating it as tightly as a write would
# stop a teacher sanity-checking cover before proposing it, so it matches the
# substitution audience rather than the scheduler one.
_CLASH_CHECKER = _SUBSTITUTION_MANAGER

from src.db.users import User
from src.services.sms.school_events import (
    SUBSTITUTION_ASSIGNED,
    raise_school_event,
)

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(require_sms_timetable_feature)])


# ── Class Periods ──

@router.post(
    "/periods",
    response_model=ClassPeriodRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create Class Period",
    description="Define a bell schedule period with start/end time for a campus.",
)
async def create_class_period(
    payload: ClassPeriodCreate,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_SCHEDULER)),
) -> ClassPeriodRead:
    # Fail loudly: a period created against another campus would silently
    # reshape that campus's school day.
    assert_campus_allowed(principal, payload.campus_id)
    period = ClassPeriod(
        campus_id=payload.campus_id,
        period_number=payload.period_number,
        start_time=payload.start_time,
        end_time=payload.end_time,
        name=payload.name,
    )
    session.add(period)
    await session.commit()
    await session.refresh(period)
    return ClassPeriodRead.model_validate(period)


@router.get(
    "/periods",
    response_model=List[ClassPeriodRead],
    summary="List Class Periods",
    description="Retrieve all configured class periods.",
)
async def list_class_periods(
    campus_id: Optional[int] = Query(None, description="Filter by Campus ID"),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> List[ClassPeriodRead]:
    stmt = select(ClassPeriod)
    # Narrow: an omitted filter previously returned every campus's periods.
    campus_id = resolve_scoped_campus_id(principal, campus_id if isinstance(campus_id, int) else None)
    if isinstance(campus_id, int):
        stmt = stmt.where(ClassPeriod.campus_id == campus_id)
    stmt = stmt.order_by(ClassPeriod.period_number.asc())
    result = await session.execute(stmt)
    periods = result.scalars().all()
    return [ClassPeriodRead.model_validate(p) for p in periods]


# ── Conflict Detection & Scheduling ──

@router.post(
    "/check-clashes",
    response_model=ClashCheckResponse,
    summary="Check Timetable Schedule Clashes",
    description="Inspect if a prospective timetable slot causes teacher or room double-booking collisions.",
)
async def check_clashes_endpoint(
    payload: ClashCheckRequest,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_CLASH_CHECKER)),
) -> ClashCheckResponse:
    day_str = payload.day_of_week.value if isinstance(payload.day_of_week, DayOfWeek) else str(payload.day_of_week)
    return await check_schedule_clashes(
        session=session,
        section_id=payload.section_id,
        course_id=payload.course_id,
        teacher_id=payload.teacher_id,
        day_of_week=day_str,
        period_id=payload.period_id,
        room_number=payload.room_number,
        academic_term_id=payload.academic_term_id,
        exclude_schedule_id=payload.exclude_schedule_id,
    )


@router.post(
    "/schedules",
    response_model=TimetableScheduleRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create Timetable Schedule Slot",
    description="Create a timetable schedule entry after validating against conflicts.",
)
async def create_timetable_schedule(
    payload: TimetableScheduleCreate,
    enforce_no_clash: bool = Query(True, description="Reject creation if clashes exist"),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_SCHEDULER)),
) -> TimetableScheduleRead:
    day_str = payload.day_of_week.value if isinstance(payload.day_of_week, DayOfWeek) else str(payload.day_of_week)

    # Verify period exists
    period_stmt = select(ClassPeriod).where(ClassPeriod.id == payload.period_id)
    period_res = await session.execute(period_stmt)
    if not period_res.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Class period with ID {payload.period_id} does not exist.",
        )

    # Check clashes
    should_enforce = enforce_no_clash if isinstance(enforce_no_clash, bool) else True
    clashes = await detect_timetable_clashes(
        session=session,
        section_id=payload.section_id,
        course_id=payload.course_id,
        teacher_id=payload.teacher_id,
        day_of_week=day_str,
        period_id=payload.period_id,
        room_number=payload.room_number,
        academic_term_id=payload.academic_term_id,
    )

    if should_enforce and clashes:
        descriptions = "; ".join([c.description for c in clashes])
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot schedule slot due to conflict(s): {descriptions}",
        )

    schedule = TimetableSchedule(
        section_id=payload.section_id,
        course_id=payload.course_id,
        teacher_id=payload.teacher_id,
        day_of_week=day_str.upper(),
        period_id=payload.period_id,
        room_number=payload.room_number,
        academic_term_id=payload.academic_term_id,
    )
    session.add(schedule)
    await session.commit()
    await session.refresh(schedule)
    return TimetableScheduleRead.model_validate(schedule)


@router.get(
    "/schedules",
    response_model=List[TimetableSlotDetail],
    summary="List Timetable Schedules",
    description="Retrieve timetable schedule slots with detailed period time info.",
)
async def list_timetable_schedules(
    section_id: Optional[int] = Query(None, description="Filter by Section ID"),
    teacher_id: Optional[int] = Query(None, description="Filter by Teacher ID"),
    academic_term_id: Optional[int] = Query(None, description="Filter by Academic Term ID"),
    day_of_week: Optional[DayOfWeek] = Query(None, description="Filter by Day of Week"),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> List[TimetableSlotDetail]:
    conditions = []
    if isinstance(section_id, int):
        conditions.append(TimetableSchedule.section_id == section_id)
    if isinstance(teacher_id, int):
        conditions.append(TimetableSchedule.teacher_id == teacher_id)
    if isinstance(academic_term_id, int):
        conditions.append(TimetableSchedule.academic_term_id == academic_term_id)
    if isinstance(day_of_week, (DayOfWeek, str)):
        val = day_of_week.value if isinstance(day_of_week, DayOfWeek) else str(day_of_week).upper()
        conditions.append(TimetableSchedule.day_of_week == val)

    return await fetch_timetable_slots(session, conditions)


# ── Student & Teacher Timetables ──

@router.get(
    "/student/{student_id}",
    response_model=StudentTimetableResponse,
    summary="Get Student Timetable",
    description="Fetch a student's weekly timetable based on their section.",
)
async def get_student_timetable(
    student_id: int,
    section_id: int = Query(..., description="Student's section ID"),
    academic_term_id: Optional[int] = Query(None, description="Filter by Academic Term ID"),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> StudentTimetableResponse:
    term_id = academic_term_id if isinstance(academic_term_id, int) else None
    slots = await get_student_timetable_slots(
        session=session,
        section_id=section_id,
        academic_term_id=term_id,
    )
    return StudentTimetableResponse(
        student_id=student_id,
        section_id=section_id,
        academic_term_id=term_id,
        slots=slots,
    )


@router.get(
    "/teacher/{teacher_id}",
    response_model=TeacherTimetableResponse,
    summary="Get Teacher Timetable",
    description="Fetch a teacher's weekly timetable.",
)
async def get_teacher_timetable(
    teacher_id: int,
    academic_term_id: Optional[int] = Query(None, description="Filter by Academic Term ID"),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> TeacherTimetableResponse:
    term_id = academic_term_id if isinstance(academic_term_id, int) else None
    slots = await get_teacher_timetable_slots(
        session=session,
        teacher_id=teacher_id,
        academic_term_id=term_id,
    )
    return TeacherTimetableResponse(
        teacher_id=teacher_id,
        academic_term_id=term_id,
        slots=slots,
    )


# ── Teacher Substitutions ──

@router.post(
    "/substitutions",
    response_model=TimetableSubstitutionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Assign a Substitute Teacher",
    description=(
        "Assigns a substitute to cover one recurring timetable slot on one "
        "specific date (a sick day, training, leave). The permanent schedule "
        "is left untouched, so the original teacher is restored automatically "
        "once the date passes or the substitution is cancelled. Rejected with "
        "409 if the substitute is already teaching or already covering another "
        "class in that period."
    ),
    responses={
        404: {"description": "Timetable schedule not found"},
        409: {"description": "Substitute is unavailable, or a substitution already exists"},
    },
)
async def create_substitution_endpoint(
    payload: TimetableSubstitutionCreate,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_SUBSTITUTION_MANAGER)),
) -> TimetableSubstitutionRead:
    try:
        substitution = await create_substitution(
            session=session,
            schedule_id=payload.schedule_id,
            substitution_date=payload.substitution_date,
            substitute_teacher_id=payload.substitute_teacher_id,
            reason=payload.reason,
            created_by=principal.raw_claims.get("lh_user_id"),
        )
    except ValueError as exc:
        message = str(exc)
        # "does not exist" is the service layer's only not-found signal; every
        # other rejection is a genuine scheduling conflict.
        if "does not exist" in message:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=message)

    # Tell the teacher they are covering. Best-effort: the substitution is
    # committed and stands regardless. Note this is the one schedule event
    # deliberately classed IMPORTANT rather than ROUTINE -- cover is arranged
    # the evening before or the morning of, and a message that waits for the
    # quiet-hours sweep arrives after the lesson it was about.
    substitute = None
    try:
        substitute = await session.get(User, payload.substitute_teacher_id)
    except Exception:
        logger.warning(
            "Could not load substitute teacher %s to notify them of cover on %s",
            payload.substitute_teacher_id,
            payload.substitution_date,
            exc_info=True,
        )

    if substitute is not None:
        await raise_school_event(
            session,
            event_key=SUBSTITUTION_ASSIGNED.key,
            org_id=principal.org_id,
            recipients=[substitute],
            context={
                "substitution_date": payload.substitution_date.isoformat()
                if hasattr(payload.substitution_date, "isoformat")
                else payload.substitution_date,
                # `reason` is deliberately not sent: it is usually "sick" or
                # "bereavement" about the ABSENT colleague, and is not the
                # substitute's business.
            },
            campus_id=principal.campus_id,
            related_kind="timetable_substitution",
            related_id=getattr(substitution, "id", None),
        )
    else:
        logger.warning(
            "Substitution %s assigned but teacher %s has no account, so they "
            "were not told.",
            getattr(substitution, "id", None),
            payload.substitute_teacher_id,
        )

    return TimetableSubstitutionRead.model_validate(substitution)


@router.get(
    "/substitutions",
    response_model=List[TimetableSubstitutionRead],
    summary="List Teacher Substitutions",
    description="Lists substitutions, optionally filtered by slot, substitute, or date. Active-only unless include_cancelled=true.",
)
async def list_substitutions_endpoint(
    schedule_id: Optional[int] = Query(None, description="Filter by timetable slot"),
    substitute_teacher_id: Optional[int] = Query(None, description="Filter by substitute teacher"),
    substitution_date: Optional[str] = Query(None, description="Filter by ISO date 'YYYY-MM-DD'"),
    include_cancelled: bool = Query(False, description="Include cancelled substitutions"),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> List[TimetableSubstitutionRead]:
    substitutions = await list_substitutions(
        session=session,
        schedule_id=schedule_id,
        substitute_teacher_id=substitute_teacher_id,
        substitution_date=substitution_date,
        include_cancelled=include_cancelled,
    )
    return [TimetableSubstitutionRead.model_validate(s) for s in substitutions]


@router.post(
    "/substitutions/{substitution_id}/cancel",
    response_model=TimetableSubstitutionRead,
    summary="Cancel a Teacher Substitution",
    description=(
        "Cancels a substitution, restoring the original teacher for that date. "
        "Soft-cancels rather than deleting, so the record of who was asked to "
        "cover stays auditable."
    ),
    responses={
        404: {"description": "Substitution not found"},
        409: {"description": "Substitution was already cancelled"},
    },
)
async def cancel_substitution_endpoint(
    substitution_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_SUBSTITUTION_MANAGER)),
) -> TimetableSubstitutionRead:
    try:
        substitution = await cancel_substitution(session=session, substitution_id=substitution_id)
    except ValueError as exc:
        message = str(exc)
        if "does not exist" in message:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=message)
    return TimetableSubstitutionRead.model_validate(substitution)


# ── Assisted Generation ──

@router.post(
    "/schedules/generate",
    response_model=GenerationResponse,
    summary="Generate a Section's Weekly Timetable (assisted)",
    description=(
        "Bulk-places a section's weekly lessons into free slots, validating "
        "every candidate against the same clash detection the write path uses. "
        "This is ASSISTED placement, not a constraint solver: it is greedy, "
        "deterministic and does not backtrack or optimise. Anything it cannot "
        "place without a conflict is returned in `unplaced` with a reason -- it "
        "is never dropped and never forced into a conflicting slot, because a "
        "timetable that looks complete but double-books a teacher is worse than "
        "one that says plainly it could not finish. "
        "Defaults to dry_run=true; nothing is written unless dry_run is "
        "explicitly false."
    ),
)
async def generate_timetable_endpoint(
    payload: GenerationRequest,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_SCHEDULER)),
) -> GenerationResponse:
    # Writing a whole week into a section is emphatically a section-scoped act.
    await assert_owns_section_or_privileged(principal, payload.section_id, session)
    return await generate_section_timetable(session=session, payload=payload)


# ── Existing-Conflict Scan ──

@router.get(
    "/conflicts",
    response_model=TimetableConflictScanResponse,
    summary="Scan an Existing Timetable for Conflicts",
    description=(
        "Reports double-bookings that ALREADY EXIST, as opposed to "
        "/check-clashes which asks whether one PROPOSED slot would conflict. "
        "Needed because slots can be created with enforce_no_clash=false, and "
        "because a later edit elsewhere can invalidate a slot that was sound "
        "when it was made."
    ),
)
async def scan_conflicts_endpoint(
    section_id: Optional[int] = Query(None, description="Restrict to one section"),
    teacher_id: Optional[int] = Query(None, description="Restrict to one teacher"),
    academic_term_id: Optional[int] = Query(None, description="Restrict to one term"),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_CLASH_CHECKER)),
) -> TimetableConflictScanResponse:
    # Campus-narrow an unscoped scan: without this a campus-bound scheduler
    # would see every other campus's conflicts, which are not theirs to fix and
    # not theirs to see.
    campus_section_ids: Optional[List[int]] = None
    scoped_campus = resolve_scoped_campus_id(principal, None)
    if scoped_campus is not None and section_id is None:
        rows = await session.execute(
            select(ClassSection.id).where(ClassSection.campus_id == scoped_campus)
        )
        campus_section_ids = [r for (r,) in rows.all()]
    if section_id is not None:
        await assert_owns_section_or_privileged(principal, section_id, session)

    conflicts, scanned = await scan_timetable_conflicts(
        session=session,
        section_id=section_id,
        teacher_id=teacher_id,
        academic_term_id=academic_term_id,
        campus_section_ids=campus_section_ids,
    )
    if scanned == 0:
        message = "No timetable slots matched this filter, so nothing was checked."
    elif conflicts:
        message = f"Found {len(conflicts)} conflict(s) across {scanned} scheduled slot(s)."
    else:
        message = f"No conflicts found across {scanned} scheduled slot(s)."
    return TimetableConflictScanResponse(
        scanned_slots=scanned,
        conflicts=conflicts,
        message=message,
    )


# ── Lesson Logs ──

@router.post(
    "/lessons",
    response_model=LessonLogRead,
    status_code=status.HTTP_201_CREATED,
    summary="Record What Was Taught",
    description=(
        "Records what was actually covered in one timetable slot on one date, "
        "plus homework set and a handover note for whoever takes the class "
        "next. Re-recording the same slot and date corrects the existing log "
        "rather than creating a second one. Distinct from an AI lesson PLAN, "
        "which is written beforehand and may never have been followed."
    ),
    responses={404: {"description": "Timetable slot not found"}},
)
async def record_lesson_endpoint(
    payload: LessonLogCreate,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_SUBSTITUTION_MANAGER)),
) -> LessonLogRead:
    caller_id = principal.raw_claims.get("lh_user_id") if principal.raw_claims else None
    try:
        log = await record_lesson_log(
            session=session,
            schedule_id=payload.schedule_id,
            lesson_date=payload.lesson_date,
            topic_covered=payload.topic_covered,
            # Attribution follows the authenticated caller, never the payload:
            # a lesson must not be attributable to a colleague who was not there.
            taught_by_user_id=caller_id,
            recorded_by_user_id=caller_id,
            homework_set=payload.homework_set,
            notes_for_next_teacher=payload.notes_for_next_teacher,
            lesson_plan_id=payload.lesson_plan_id,
        )
    except ValueError as exc:
        message = str(exc)
        if "does not exist" in message:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
    return LessonLogRead.model_validate(log)


@router.get(
    "/lessons",
    response_model=List[LessonLogRead],
    summary="List Lesson Logs",
    description="Lesson logs for a section or slot, most recent first.",
)
async def list_lessons_endpoint(
    section_id: Optional[int] = Query(None, description="Filter by section"),
    schedule_id: Optional[int] = Query(None, description="Filter by timetable slot"),
    date_from: Optional[str] = Query(None, description="ISO date YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="ISO date YYYY-MM-DD"),
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> List[LessonLogRead]:
    if section_id is not None:
        await assert_owns_section_or_privileged(principal, section_id, session)
    logs = await list_lesson_logs(
        session=session,
        section_id=section_id,
        schedule_id=schedule_id,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
    )
    return [LessonLogRead.model_validate(log) for log in logs]


@router.get(
    "/lessons/previous",
    response_model=Optional[LessonLogRead],
    summary="What Was Taught Last Lesson",
    description=(
        "The last logged lesson for a section before a given date -- the "
        "question a substitute teacher covering an unfamiliar class needs "
        "answered. Scoped by SECTION rather than slot, because the previous "
        "lesson may have been a different slot with a different teacher. "
        "Returns null when no log exists: that means nobody wrote one down, "
        "NOT that nothing was taught, and callers must say so."
    ),
)
async def previous_lesson_endpoint(
    section_id: int = Query(..., description="The section being covered"),
    before_date: str = Query(..., description="ISO date of the lesson you are covering"),
    course_id: Optional[int] = Query(None, description="Narrow to one subject"),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> Optional[LessonLogRead]:
    # A substitute is legitimately covering a class they do not own, so this
    # deliberately does NOT require section ownership -- the helper admits
    # teachers who teach the section, and a covering teacher needs it precisely
    # because they do not. Gated to authenticated school users; the content is
    # a topic and a homework note, not personal data about a child.
    log = await get_previous_lesson(
        session=session,
        section_id=section_id,
        before_date=before_date,
        course_id=course_id,
    )
    return LessonLogRead.model_validate(log) if log is not None else None
