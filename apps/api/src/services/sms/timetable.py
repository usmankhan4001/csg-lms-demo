import logging
from typing import List, Optional
from sqlalchemy import select, and_, or_
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_timetable import ClassPeriod, TimetableSchedule
from src.schemas.sms_timetable import (
    ClashDetail,
    ClashType,
    ClashCheckResponse,
    TimetableSlotDetail,
)

logger = logging.getLogger(__name__)


async def detect_timetable_clashes(
    session: AsyncSession,
    section_id: int,
    course_id: int,
    teacher_id: int,
    day_of_week: str,
    period_id: int,
    room_number: Optional[str] = None,
    academic_term_id: Optional[int] = None,
    exclude_schedule_id: Optional[int] = None,
) -> List[ClashDetail]:
    """
    Timetable Conflict Solver Logic.
    
    Checks for scheduling collisions:
    1. Teacher Double-Booking: Teacher cannot teach two classes at the same period & day.
    2. Room Double-Booking: A room cannot host two classes simultaneously.
    3. Section Double-Booking: A section/class cannot attend two courses simultaneously.
    """
    normalized_day = day_of_week.upper()
    clashes: List[ClashDetail] = []

    # Build base conditions matching the time slot
    base_slot_conditions = [
        TimetableSchedule.day_of_week == normalized_day,
        TimetableSchedule.period_id == period_id,
    ]

    # If academic_term_id is specified, conflict occurs within the same term or when unassigned
    if academic_term_id is not None:
        term_condition = or_(
            TimetableSchedule.academic_term_id == academic_term_id,
            TimetableSchedule.academic_term_id.is_(None),
        )
        base_slot_conditions.append(term_condition)

    # Base query for all schedules at this slot
    stmt = select(TimetableSchedule).where(and_(*base_slot_conditions))
    if exclude_schedule_id is not None:
        stmt = stmt.where(TimetableSchedule.id != exclude_schedule_id)

    result = await session.execute(stmt)
    existing_schedules = result.scalars().all()

    for existing in existing_schedules:
        # 1. Teacher double-booked clash
        if existing.teacher_id == teacher_id:
            clashes.append(
                ClashDetail(
                    clash_type=ClashType.TEACHER_DOUBLE_BOOKED,
                    description=(
                        f"Teacher (ID: {teacher_id}) is already assigned to section {existing.section_id} "
                        f"(course {existing.course_id}) on {normalized_day}, period {period_id}."
                    ),
                    conflicting_schedule_id=existing.id,
                    day_of_week=existing.day_of_week,
                    period_id=existing.period_id,
                    academic_term_id=existing.academic_term_id,
                    teacher_id=existing.teacher_id,
                    room_number=existing.room_number,
                    section_id=existing.section_id,
                )
            )

        # 2. Room double-booked clash
        if (
            room_number
            and existing.room_number
            and existing.room_number.strip().lower() == room_number.strip().lower()
        ):
            clashes.append(
                ClashDetail(
                    clash_type=ClashType.ROOM_DOUBLE_BOOKED,
                    description=(
                        f"Room '{room_number}' is already occupied by section {existing.section_id} "
                        f"on {normalized_day}, period {period_id}."
                    ),
                    conflicting_schedule_id=existing.id,
                    day_of_week=existing.day_of_week,
                    period_id=existing.period_id,
                    academic_term_id=existing.academic_term_id,
                    teacher_id=existing.teacher_id,
                    room_number=existing.room_number,
                    section_id=existing.section_id,
                )
            )

        # 3. Section double-booked clash
        if existing.section_id == section_id:
            clashes.append(
                ClashDetail(
                    clash_type=ClashType.SECTION_DOUBLE_BOOKED,
                    description=(
                        f"Section {section_id} already has course {existing.course_id} "
                        f"scheduled on {normalized_day}, period {period_id}."
                    ),
                    conflicting_schedule_id=existing.id,
                    day_of_week=existing.day_of_week,
                    period_id=existing.period_id,
                    academic_term_id=existing.academic_term_id,
                    teacher_id=existing.teacher_id,
                    room_number=existing.room_number,
                    section_id=existing.section_id,
                )
            )

    return clashes


async def check_schedule_clashes(
    session: AsyncSession,
    section_id: int,
    course_id: int,
    teacher_id: int,
    day_of_week: str,
    period_id: int,
    room_number: Optional[str] = None,
    academic_term_id: Optional[int] = None,
    exclude_schedule_id: Optional[int] = None,
) -> ClashCheckResponse:
    """Convenience validator returning ClashCheckResponse."""
    clashes = await detect_timetable_clashes(
        session=session,
        section_id=section_id,
        course_id=course_id,
        teacher_id=teacher_id,
        day_of_week=day_of_week,
        period_id=period_id,
        room_number=room_number,
        academic_term_id=academic_term_id,
        exclude_schedule_id=exclude_schedule_id,
    )
    has_clash = len(clashes) > 0
    message = (
        f"Found {len(clashes)} timetable conflict(s)."
        if has_clash
        else "No timetable clashes detected."
    )
    return ClashCheckResponse(
        has_clash=has_clash,
        clashes=clashes,
        message=message,
    )


async def fetch_timetable_slots(
    session: AsyncSession,
    filter_conditions: list,
) -> List[TimetableSlotDetail]:
    """Execute a query joining TimetableSchedule and ClassPeriod."""
    stmt = (
        select(
            TimetableSchedule,
            ClassPeriod.period_number,
            ClassPeriod.start_time,
            ClassPeriod.end_time,
        )
        .outerjoin(ClassPeriod, TimetableSchedule.period_id == ClassPeriod.id)
        .where(and_(*filter_conditions))
        .order_by(TimetableSchedule.day_of_week, ClassPeriod.period_number, TimetableSchedule.period_id)
    )
    result = await session.execute(stmt)
    slots: List[TimetableSlotDetail] = []
    for sched, p_num, s_time, e_time in result.all():
        slots.append(
            TimetableSlotDetail(
                id=sched.id,
                section_id=sched.section_id,
                course_id=sched.course_id,
                teacher_id=sched.teacher_id,
                day_of_week=sched.day_of_week,
                period_id=sched.period_id,
                period_number=p_num,
                start_time=s_time,
                end_time=e_time,
                room_number=sched.room_number,
                academic_term_id=sched.academic_term_id,
            )
        )
    return slots


async def get_student_timetable_slots(
    session: AsyncSession,
    section_id: int,
    academic_term_id: Optional[int] = None,
) -> List[TimetableSlotDetail]:
    """Retrieve all timetable slots for a given section."""
    conditions = [TimetableSchedule.section_id == section_id]
    if academic_term_id is not None:
        conditions.append(
            or_(
                TimetableSchedule.academic_term_id == academic_term_id,
                TimetableSchedule.academic_term_id.is_(None),
            )
        )
    return await fetch_timetable_slots(session, conditions)


async def get_teacher_timetable_slots(
    session: AsyncSession,
    teacher_id: int,
    academic_term_id: Optional[int] = None,
) -> List[TimetableSlotDetail]:
    """Retrieve all timetable slots for a given teacher."""
    conditions = [TimetableSchedule.teacher_id == teacher_id]
    if academic_term_id is not None:
        conditions.append(
            or_(
                TimetableSchedule.academic_term_id == academic_term_id,
                TimetableSchedule.academic_term_id.is_(None),
            )
        )
    return await fetch_timetable_slots(session, conditions)
