import logging
from typing import List, Optional
from sqlalchemy import select, and_, or_
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_timetable import ClassPeriod, TimetableSchedule, TimetableSubstitution
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


async def create_substitution(
    session: AsyncSession,
    schedule_id: int,
    substitution_date: str,
    substitute_teacher_id: int,
    reason: Optional[str] = None,
    created_by: Optional[int] = None,
) -> TimetableSubstitution:
    """Assign a substitute teacher to one recurring slot on one date.

    Raises ValueError with a human-readable message on any rejection; the
    router maps those to 404/409 rather than this layer importing HTTP
    concerns.
    """
    schedule = await session.get(TimetableSchedule, schedule_id)
    if schedule is None:
        raise ValueError(f"Timetable schedule with ID {schedule_id} does not exist.")

    if substitute_teacher_id == schedule.teacher_id:
        raise ValueError(
            "The substitute is already the teacher assigned to this slot — no substitution needed."
        )

    # Reject a second active substitution for the same slot/date rather than
    # silently stacking rows, which would leave "who is actually covering?"
    # ambiguous.
    existing_stmt = select(TimetableSubstitution).where(
        and_(
            TimetableSubstitution.schedule_id == schedule_id,
            TimetableSubstitution.substitution_date == substitution_date,
            TimetableSubstitution.is_active.is_(True),
        )
    )
    existing = (await session.execute(existing_stmt)).scalars().first()
    if existing is not None:
        raise ValueError(
            f"An active substitution already exists for this slot on {substitution_date} "
            f"(substitute teacher ID {existing.substitute_teacher_id}). Cancel it first."
        )

    # The substitute must be free in their OWN permanent timetable for this
    # slot. Reuses the same collision detector the permanent timetable uses
    # (passing exclude_schedule_id so the slot being covered is not reported
    # as a clash against itself), then keeps only the teacher-clash findings:
    # room and section are unchanged by a substitution, so a pre-existing
    # room/section clash on the original slot is not this operation's fault
    # and must not block covering a sick teacher.
    clashes = await detect_timetable_clashes(
        session=session,
        section_id=schedule.section_id,
        course_id=schedule.course_id,
        teacher_id=substitute_teacher_id,
        day_of_week=schedule.day_of_week,
        period_id=schedule.period_id,
        room_number=schedule.room_number,
        academic_term_id=schedule.academic_term_id,
        exclude_schedule_id=schedule_id,
    )
    teacher_clashes = [c for c in clashes if c.clash_type == ClashType.TEACHER_DOUBLE_BOOKED]
    if teacher_clashes:
        raise ValueError(
            "Substitute teacher is already booked at this time: "
            + "; ".join(c.description for c in teacher_clashes)
        )

    # A substitute already covering a DIFFERENT slot at the same time on the
    # same date is invisible to the permanent-timetable check above, since
    # that cover lives only in this table.
    same_day_stmt = select(TimetableSubstitution).where(
        and_(
            TimetableSubstitution.substitute_teacher_id == substitute_teacher_id,
            TimetableSubstitution.substitution_date == substitution_date,
            TimetableSubstitution.is_active.is_(True),
        )
    )
    for other in (await session.execute(same_day_stmt)).scalars().all():
        other_schedule = await session.get(TimetableSchedule, other.schedule_id)
        if other_schedule is not None and other_schedule.period_id == schedule.period_id:
            raise ValueError(
                f"Substitute teacher is already covering another class at period "
                f"{schedule.period_id} on {substitution_date}."
            )

    substitution = TimetableSubstitution(
        schedule_id=schedule_id,
        substitution_date=substitution_date,
        original_teacher_id=schedule.teacher_id,
        substitute_teacher_id=substitute_teacher_id,
        reason=reason,
        created_by=created_by,
    )
    session.add(substitution)
    await session.commit()
    await session.refresh(substitution)
    return substitution


async def cancel_substitution(
    session: AsyncSession,
    substitution_id: int,
) -> TimetableSubstitution:
    """Deactivate a substitution, restoring the original teacher for that date.

    Soft-cancels (is_active=False) rather than deleting, so the record of who
    was asked to cover — and that it was called off — survives.
    """
    substitution = await session.get(TimetableSubstitution, substitution_id)
    if substitution is None:
        raise ValueError(f"Substitution with ID {substitution_id} does not exist.")
    if not substitution.is_active:
        raise ValueError("This substitution has already been cancelled.")

    substitution.is_active = False
    session.add(substitution)
    await session.commit()
    await session.refresh(substitution)
    return substitution


async def list_substitutions(
    session: AsyncSession,
    schedule_id: Optional[int] = None,
    substitute_teacher_id: Optional[int] = None,
    substitution_date: Optional[str] = None,
    include_cancelled: bool = False,
) -> List[TimetableSubstitution]:
    """List substitutions, active-only unless `include_cancelled`."""
    conditions = []
    if schedule_id is not None:
        conditions.append(TimetableSubstitution.schedule_id == schedule_id)
    if substitute_teacher_id is not None:
        conditions.append(TimetableSubstitution.substitute_teacher_id == substitute_teacher_id)
    if substitution_date is not None:
        conditions.append(TimetableSubstitution.substitution_date == substitution_date)
    if not include_cancelled:
        conditions.append(TimetableSubstitution.is_active.is_(True))

    stmt = select(TimetableSubstitution)
    if conditions:
        stmt = stmt.where(and_(*conditions))
    result = await session.execute(stmt)
    return list(result.scalars().all())


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


async def scan_timetable_conflicts(
    session: AsyncSession,
    section_id: Optional[int] = None,
    teacher_id: Optional[int] = None,
    academic_term_id: Optional[int] = None,
    campus_section_ids: Optional[List[int]] = None,
) -> "tuple[List[ClashDetail], int]":
    """Find conflicts that ALREADY EXIST across a timetable.

    Returns (conflicts, slots_scanned). The count is returned rather than
    derived by the caller so "0 conflicts" can be distinguished from "0 slots
    looked at" -- a clean timetable and an empty one are different answers.

    `detect_timetable_clashes` answers "would this one proposed slot conflict?"
    and runs on write. It cannot answer "is our timetable sound?", which is the
    question that matters once slots have been created with enforce_no_clash
    disabled, imported in bulk, or invalidated by a later edit elsewhere.

    Groups every slot by (day, period) and reports teacher, room and section
    double-bookings within each group. Each conflicting PAIR is reported once,
    not twice, so a scheduler sees one problem rather than two halves of one.
    """
    conditions = []
    if section_id is not None:
        conditions.append(TimetableSchedule.section_id == section_id)
    if teacher_id is not None:
        conditions.append(TimetableSchedule.teacher_id == teacher_id)
    if academic_term_id is not None:
        conditions.append(TimetableSchedule.academic_term_id == academic_term_id)
    if campus_section_ids is not None:
        # Empty list means "this caller may see no sections" -- which must
        # return nothing, not everything. Conflating [] with None is how a
        # campus-scoped view becomes an org-wide one.
        conditions.append(TimetableSchedule.section_id.in_(campus_section_ids))

    stmt = select(TimetableSchedule)
    if conditions:
        stmt = stmt.where(and_(*conditions))
    slots = list((await session.execute(stmt)).scalars().all())

    grouped: dict = {}
    for slot in slots:
        grouped.setdefault((slot.day_of_week, slot.period_id), []).append(slot)

    conflicts: List[ClashDetail] = []
    for (day, period_id), group in grouped.items():
        for i, a in enumerate(group):
            for b in group[i + 1:]:
                if a.teacher_id == b.teacher_id:
                    conflicts.append(
                        ClashDetail(
                            clash_type=ClashType.TEACHER_DOUBLE_BOOKED,
                            description=(
                                f"Teacher (ID: {a.teacher_id}) is timetabled for both "
                                f"section {a.section_id} and section {b.section_id} on "
                                f"{day}, period {period_id}."
                            ),
                            conflicting_schedule_id=b.id,
                            day_of_week=day,
                            period_id=period_id,
                            academic_term_id=a.academic_term_id,
                            teacher_id=a.teacher_id,
                            room_number=a.room_number,
                            section_id=a.section_id,
                        )
                    )
                if (
                    a.room_number
                    and b.room_number
                    and a.room_number.strip().lower() == b.room_number.strip().lower()
                ):
                    conflicts.append(
                        ClashDetail(
                            clash_type=ClashType.ROOM_DOUBLE_BOOKED,
                            description=(
                                f"Room '{a.room_number}' is booked by both section "
                                f"{a.section_id} and section {b.section_id} on {day}, "
                                f"period {period_id}."
                            ),
                            conflicting_schedule_id=b.id,
                            day_of_week=day,
                            period_id=period_id,
                            academic_term_id=a.academic_term_id,
                            teacher_id=a.teacher_id,
                            room_number=a.room_number,
                            section_id=a.section_id,
                        )
                    )
                if a.section_id == b.section_id:
                    conflicts.append(
                        ClashDetail(
                            clash_type=ClashType.SECTION_DOUBLE_BOOKED,
                            description=(
                                f"Section {a.section_id} has two courses "
                                f"({a.course_id} and {b.course_id}) on {day}, "
                                f"period {period_id}."
                            ),
                            conflicting_schedule_id=b.id,
                            day_of_week=day,
                            period_id=period_id,
                            academic_term_id=a.academic_term_id,
                            teacher_id=a.teacher_id,
                            room_number=a.room_number,
                            section_id=a.section_id,
                        )
                    )
    return conflicts, len(slots)
