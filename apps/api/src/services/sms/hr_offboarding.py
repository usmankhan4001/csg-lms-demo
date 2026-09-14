"""Staff offboarding: the cascade that `is_active = False` never performed.

Before this, deactivating a staff profile changed one boolean. The person kept
every `SMSUserRole` grant (so they could still sign in and act), remained
`ClassSection.class_teacher_id` on their sections, and stayed on every
`TimetableSchedule` row. A school that "offboarded" someone had done nothing
except hide them from a directory listing.

One asymmetry drives the design and is worth stating plainly:

  - `ClassSection.class_teacher_id` is NULLABLE, so a section CAN be released
    to unassigned.
  - `TimetableSchedule.teacher_id` is NOT NULL, so a slot CANNOT be. There is
    no "nobody teaches this" state to write.

So slots are either reassigned to a named successor or reported as
OUTSTANDING. They are never quietly left pointing at a departed employee with
no signal, and no successor is ever guessed -- who inherits a class is a
staffing decision, and picking one automatically would put a real teacher in
front of a class nobody chose them for.
"""

import datetime
from typing import List, Optional, Tuple

from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_campus import ClassSection
from src.db.sms_hr import StaffProfile
from src.db.sms_hr_extended import StaffOffboarding
from src.db.sms_identity import SMSUserRole
from src.db.sms_timetable import TimetableSchedule
from src.schemas.sms_hr_extended import StaffOffboardingRequest


async def _revoke_role_grants(session: AsyncSession, user_id: int) -> int:
    """Deactivate every active school role grant for this user.

    Deactivated rather than deleted: the grant is evidence that the person
    held that role during their employment, which matters when reviewing
    anything they did. A deleted grant makes their past actions unattributable.
    """
    rows = (
        await session.execute(
            select(SMSUserRole).where(
                SMSUserRole.user_id == user_id,
                SMSUserRole.is_active == True,  # noqa: E712
            )
        )
    ).scalars().all()

    for grant in rows:
        grant.is_active = False
        grant.updated_at = datetime.datetime.now(datetime.timezone.utc)
        session.add(grant)
    return len(rows)


async def _handle_sections(
    session: AsyncSession,
    user_id: int,
    successor_user_id: Optional[int],
) -> Tuple[int, int, List[str]]:
    """Reassign or release the sections this person is class teacher of.

    Returns (reassigned, released, warnings).
    """
    sections = (
        await session.execute(
            select(ClassSection).where(ClassSection.class_teacher_id == user_id)
        )
    ).scalars().all()

    reassigned = 0
    released = 0
    warnings: List[str] = []

    for section in sections:
        if successor_user_id is not None:
            section.class_teacher_id = successor_user_id
            reassigned += 1
        else:
            section.class_teacher_id = None
            released += 1
        session.add(section)

    if released:
        # Loud, because an unassigned section has no class teacher and nobody
        # is told by the absence itself.
        warnings.append(
            f"{released} class section(s) now have NO class teacher and need "
            f"reassigning."
        )
    return reassigned, released, warnings


async def _handle_timetable(
    session: AsyncSession,
    user_id: int,
    successor_user_id: Optional[int],
) -> Tuple[int, List[int], List[str]]:
    """Reassign timetable slots, or report the ones that cannot be released.

    Returns (reassigned, outstanding_slot_ids, warnings).
    """
    slots = (
        await session.execute(
            select(TimetableSchedule).where(TimetableSchedule.teacher_id == user_id)
        )
    ).scalars().all()

    reassigned = 0
    outstanding: List[int] = []
    warnings: List[str] = []

    for slot in slots:
        if successor_user_id is not None:
            slot.teacher_id = successor_user_id
            session.add(slot)
            reassigned += 1
        else:
            # teacher_id is NOT NULL -- there is no value meaning "nobody".
            # Reported rather than nulled, so the gap is visible work.
            if slot.id is not None:
                outstanding.append(slot.id)

    if outstanding:
        warnings.append(
            f"{len(outstanding)} timetable slot(s) still list this person as "
            f"the teacher. Timetable slots cannot be left unassigned, so they "
            f"must be reassigned or removed before the timetable is correct."
        )
    return reassigned, outstanding, warnings


async def offboard_staff_member(
    session: AsyncSession,
    staff: StaffProfile,
    payload: StaffOffboardingRequest,
    initiated_by_user_id: Optional[int],
) -> Tuple[StaffOffboarding, List[int], List[str]]:
    """Perform the full offboarding cascade in ONE transaction.

    Everything commits together. A partial offboarding -- roles revoked but
    sections still assigned, or the reverse -- is worse than none, because it
    looks done.
    """
    warnings: List[str] = []
    roles_revoked = 0
    sections_reassigned = 0
    sections_released = 0
    slots_reassigned = 0
    outstanding: List[int] = []

    if staff.user_id is None:
        # A profile with no Learnhouse user has nothing to revoke and cannot
        # own sections or slots, which are keyed on user id. Said out loud
        # rather than silently reporting zeros that look like a clean cascade.
        warnings.append(
            "This staff profile is not linked to a user account, so no access "
            "was revoked and no sections or timetable slots were checked."
        )
    else:
        if payload.revoke_roles:
            roles_revoked = await _revoke_role_grants(session, staff.user_id)
        else:
            warnings.append(
                "Role grants were left ACTIVE at the caller's request: this "
                "person can still sign in and act."
            )

        sections_reassigned, sections_released, section_warnings = await _handle_sections(
            session, staff.user_id, payload.successor_user_id
        )
        warnings.extend(section_warnings)

        slots_reassigned, outstanding, slot_warnings = await _handle_timetable(
            session, staff.user_id, payload.successor_user_id
        )
        warnings.extend(slot_warnings)

    staff.is_active = False
    session.add(staff)

    record = StaffOffboarding(
        staff_id=staff.id,
        staff_user_id=staff.user_id,
        campus_id=staff.campus_id,
        effective_date=payload.effective_date,
        reason=payload.reason,
        notes=payload.notes,
        roles_revoked=roles_revoked,
        sections_released=sections_released,
        sections_reassigned=sections_reassigned,
        timetable_slots_reassigned=slots_reassigned,
        timetable_slots_outstanding=len(outstanding),
        initiated_by_user_id=initiated_by_user_id,
    )
    session.add(record)

    await session.commit()
    await session.refresh(record)
    return record, outstanding, warnings
