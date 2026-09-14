"""Assisted timetable generation.

SCOPE, STATED PLAINLY: this is assisted bulk placement, NOT a constraint
solver. It does not backtrack, does not optimise for teacher gaps or room
proximity, and makes no attempt at a globally optimal timetable.

That is a deliberate choice rather than a shortcut. Full timetabling is a
constraint-satisfaction problem, and a solver that quietly produces a
subtly-wrong timetable -- one teacher with no lunch, a lab class in a room
with no equipment -- is far more dangerous than no solver, because a school
will trust its output and only discover the fault in week one. What a school
actually needs first is to stop hand-typing forty slots per section per term.

So: greedy, deterministic, first-fit placement that validates every candidate
against the SAME clash detection the write path uses, and reports anything it
cannot place rather than inventing a home for it.

THE RULE THAT MATTERS: an unplaced period is reported as unplaced, with a
reason. It is never dropped silently and never forced into a slot that
conflicts. A generator that fills every gap by lying about availability
produces a timetable nobody can run.
"""

import logging
from typing import Dict, List, Optional, Sequence, Tuple

from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_campus import ClassSection
from src.db.sms_timetable import ClassPeriod, TimetableSchedule
from src.schemas.sms_timetable import (
    GenerationRequest,
    GenerationResponse,
    PlacedSlot,
    UnplacedSlot,
)
from src.services.sms.timetable import detect_timetable_clashes

logger = logging.getLogger(__name__)

# A school week. Saturday/Sunday are excluded from the DEFAULT only; a school
# that teaches on Saturday passes `days` explicitly rather than being told what
# its week looks like.
DEFAULT_TEACHING_DAYS: Tuple[str, ...] = (
    "MONDAY",
    "TUESDAY",
    "WEDNESDAY",
    "THURSDAY",
    "FRIDAY",
)


async def _resolve_period_ids(
    session: AsyncSession,
    section_id: int,
    explicit_period_ids: Optional[Sequence[int]],
) -> List[int]:
    """Which periods this section's day is built from.

    Explicit ids win. Otherwise the campus's own bell schedule is used, in
    period order -- guessing a period structure would be inventing the shape of
    someone's school day.
    """
    if explicit_period_ids:
        stmt = (
            select(ClassPeriod)
            .where(ClassPeriod.id.in_(list(explicit_period_ids)))
            .order_by(ClassPeriod.period_number.asc())
        )
        rows = (await session.execute(stmt)).scalars().all()
        return [p.id for p in rows if p.id is not None]

    section = (
        await session.execute(select(ClassSection).where(ClassSection.id == section_id))
    ).scalar_one_or_none()
    if section is None:
        return []

    stmt = select(ClassPeriod).order_by(ClassPeriod.period_number.asc())
    if section.campus_id is not None:
        stmt = stmt.where(ClassPeriod.campus_id == section.campus_id)
    rows = (await session.execute(stmt)).scalars().all()
    return [p.id for p in rows if p.id is not None]


async def generate_section_timetable(
    session: AsyncSession,
    payload: GenerationRequest,
) -> GenerationResponse:
    """Place each requirement's weekly periods into free slots for a section.

    Deterministic: requirements are processed in the order given, and each is
    offered candidate slots in (day, period) order. The same input therefore
    always produces the same timetable, which matters because a school will run
    this, look at the result, tweak an input and run it again.
    """
    days: List[str] = [
        d.value if hasattr(d, "value") else str(d).upper()
        for d in (payload.days or DEFAULT_TEACHING_DAYS)
    ]
    period_ids = await _resolve_period_ids(session, payload.section_id, payload.period_ids)

    requested_periods = sum(r.periods_per_week for r in payload.requirements)
    placed: List[PlacedSlot] = []
    unplaced: List[UnplacedSlot] = []

    if not period_ids:
        # No bell schedule means there is nothing to place INTO. Reporting every
        # period as unplaced with this reason is more useful than a 400, because
        # the caller sees the scale of what is blocked.
        for req in payload.requirements:
            for occurrence in range(1, req.periods_per_week + 1):
                unplaced.append(
                    UnplacedSlot(
                        course_id=req.course_id,
                        teacher_id=req.teacher_id,
                        occurrence=occurrence,
                        reason=(
                            "No class periods are defined for this campus, so there "
                            "are no slots to place lessons into. Define the bell "
                            "schedule first."
                        ),
                    )
                )
        return GenerationResponse(
            section_id=payload.section_id,
            academic_term_id=payload.academic_term_id,
            dry_run=payload.dry_run,
            requested_periods=requested_periods,
            placed=[],
            unplaced=unplaced,
            message="No class periods defined; nothing could be placed.",
        )

    # Slots claimed during THIS run. A dry run writes nothing, so without this
    # every occurrence would be offered the same first free slot and the preview
    # would claim a timetable that cannot exist.
    claimed: Dict[Tuple[str, int], bool] = {}
    # Same problem for the teacher: two sections' worth of placements in one run
    # must not both take Monday period 1 from the same teacher.
    teacher_claimed: Dict[Tuple[int, str, int], bool] = {}

    for req in payload.requirements:
        allowed_days = (
            [d.value if hasattr(d, "value") else str(d).upper() for d in req.preferred_days]
            if req.preferred_days
            else days
        )

        for occurrence in range(1, req.periods_per_week + 1):
            placement: Optional[Tuple[str, int]] = None
            # Collected so an unplaced period can say WHY rather than just "no
            # slot" -- a scheduler needs to know whether to free the teacher or
            # extend the day.
            blocking_reasons: List[str] = []

            for day in allowed_days:
                for period_id in period_ids:
                    if claimed.get((day, period_id)):
                        continue
                    if teacher_claimed.get((req.teacher_id, day, period_id)):
                        continue

                    clashes = await detect_timetable_clashes(
                        session=session,
                        section_id=payload.section_id,
                        course_id=req.course_id,
                        teacher_id=req.teacher_id,
                        day_of_week=day,
                        period_id=period_id,
                        room_number=req.room_number,
                        academic_term_id=payload.academic_term_id,
                    )
                    if clashes:
                        blocking_reasons.append(clashes[0].description)
                        continue

                    placement = (day, period_id)
                    break
                if placement is not None:
                    break

            if placement is None:
                # Deduplicate while preserving order: the same teacher clash
                # repeats across every candidate slot and would otherwise bury
                # the one distinct reason that matters.
                seen: List[str] = []
                for reason in blocking_reasons:
                    if reason not in seen:
                        seen.append(reason)
                detail = (
                    " Blocking conflicts: " + "; ".join(seen[:3])
                    if seen
                    else " Every candidate slot in the week was already taken."
                )
                unplaced.append(
                    UnplacedSlot(
                        course_id=req.course_id,
                        teacher_id=req.teacher_id,
                        occurrence=occurrence,
                        reason=(
                            "No free slot without a conflict." + detail
                        ).strip(),
                    )
                )
                continue

            day, period_id = placement
            claimed[(day, period_id)] = True
            teacher_claimed[(req.teacher_id, day, period_id)] = True

            schedule_id: Optional[int] = None
            if not payload.dry_run:
                schedule = TimetableSchedule(
                    section_id=payload.section_id,
                    course_id=req.course_id,
                    teacher_id=req.teacher_id,
                    day_of_week=day,
                    period_id=period_id,
                    room_number=req.room_number,
                    academic_term_id=payload.academic_term_id,
                )
                session.add(schedule)
                # Flush rather than commit per slot: the whole run lands as one
                # transaction, so a failure half-way cannot leave a section with
                # a partial week that nobody asked for.
                await session.flush()
                schedule_id = schedule.id

            placed.append(
                PlacedSlot(
                    course_id=req.course_id,
                    teacher_id=req.teacher_id,
                    day_of_week=day,
                    period_id=period_id,
                    room_number=req.room_number,
                    schedule_id=schedule_id,
                )
            )

    if not payload.dry_run and placed:
        await session.commit()

    if unplaced:
        message = (
            f"Placed {len(placed)} of {requested_periods} periods. "
            f"{len(unplaced)} could not be placed and are listed with reasons."
        )
    else:
        message = f"Placed all {len(placed)} requested periods."
    if payload.dry_run:
        message += " Dry run: nothing was saved."

    return GenerationResponse(
        section_id=payload.section_id,
        academic_term_id=payload.academic_term_id,
        dry_run=payload.dry_run,
        requested_periods=requested_periods,
        placed=placed,
        unplaced=unplaced,
        message=message,
    )
