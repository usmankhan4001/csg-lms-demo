"""
Communication Hub access rules (M13).

THE RULE THIS FILE EXISTS FOR: this is a messaging surface in a system with
children's accounts on it. An open user-to-user inbox would let any account
message any other, which is a safeguarding failure, not a missing feature.
So a conversation is only permitted where a *school relationship* already
justifies it, and that is checked here -- server-side, on every thread
creation and every reply -- not in the UI.

Permitted pairs:

  staff  <-> staff    always, within the same org.
  parent <-> staff    only when that staff member is connected to one of the
                      parent's OWN children (class teacher of a section the
                      child is enrolled in, or a subject teacher timetabled
                      to it), or is a SCHOOL_ADMIN / PSYCHOLOGIST / SUPER_ADMIN
                      -- the school office and the counsellor have to stay
                      reachable or parents have no route in at all.
  student <-> staff   same connection test, for the student themselves.

Everything else is refused, explicitly:

  parent  <-> parent   no school relationship exists between two families.
  student <-> student  peer messaging is the classic bullying vector; this
                       system has no moderation to make it safe.
  parent  <-> student  including their own child. Families do not need an
                       audited school channel to talk to each other, and
                       allowing it would make every other parent-student
                       pair look like a legitimate shape to a future reader.

The check is symmetric: `assert_may_message(a, b)` is the same question as
`assert_may_message(b, a)`, so a teacher opening a thread and a parent
replying to it are governed identically.
"""

import logging
from typing import List, Optional, Sequence, Set

from fastapi import HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_campus import ClassSection, StudentEnrollment
from src.db.sms_identity import SchoolRole, SMSUserRole
from src.db.sms_timetable import TimetableSchedule

logger = logging.getLogger(__name__)

STAFF_ROLES: Set[str] = {
    SchoolRole.TEACHER.value,
    SchoolRole.SCHOOL_ADMIN.value,
    SchoolRole.STAFF.value,
    SchoolRole.PSYCHOLOGIST.value,
    SchoolRole.SUPER_ADMIN.value,
}

# Staff a parent or student may always reach, regardless of which class the
# child is in. Without this a family has no way to contact the school office
# or a counsellor, which is worse than the risk it avoids.
ALWAYS_REACHABLE_ROLES: Set[str] = {
    SchoolRole.SCHOOL_ADMIN.value,
    SchoolRole.PSYCHOLOGIST.value,
    SchoolRole.SUPER_ADMIN.value,
}


async def get_school_roles(db_session: AsyncSession, org_id: int, user_id: int) -> Set[str]:
    """Active role names this user holds in this org."""
    result = await db_session.execute(
        select(SMSUserRole).where(
            SMSUserRole.user_id == user_id,
            SMSUserRole.org_id == org_id,
            SMSUserRole.is_active == True,  # noqa: E712
        )
    )
    roles: Set[str] = set()
    for grant in result.scalars().all():
        roles.add(grant.role.value if hasattr(grant.role, "value") else str(grant.role))
    return roles


async def get_children_ids(db_session: AsyncSession, guardian_user_id: int) -> List[int]:
    from src.db.sms_identity import StudentGuardian

    result = await db_session.execute(
        select(StudentGuardian).where(StudentGuardian.guardian_user_id == guardian_user_id)
    )
    return [link.student_id for link in result.scalars().all()]


async def staff_is_connected_to_student(
    db_session: AsyncSession, staff_user_id: int, student_id: int
) -> bool:
    """True when this staff member actually teaches this student.

    Connection means the staff member is the class teacher of a section the
    student is enrolled in, or is timetabled to teach that section. Both
    columns hold a Learnhouse `user.id` directly (not StaffProfile.id) --
    the convention every SMS table follows.
    """
    enrolment_res = await db_session.execute(
        select(StudentEnrollment).where(StudentEnrollment.student_id == student_id)
    )
    section_ids = [e.section_id for e in enrolment_res.scalars().all()]
    if not section_ids:
        return False

    homeroom_res = await db_session.execute(
        select(ClassSection).where(
            ClassSection.id.in_(section_ids),  # type: ignore[attr-defined]
            ClassSection.class_teacher_id == staff_user_id,
        )
    )
    if homeroom_res.scalars().first() is not None:
        return True

    timetable_res = await db_session.execute(
        select(TimetableSchedule).where(
            TimetableSchedule.section_id.in_(section_ids),  # type: ignore[attr-defined]
            TimetableSchedule.teacher_id == staff_user_id,
        )
    )
    return timetable_res.scalars().first() is not None


async def _staff_reachable_by(
    db_session: AsyncSession,
    org_id: int,
    staff_user_id: int,
    staff_roles: Set[str],
    student_ids: Sequence[int],
) -> bool:
    if staff_roles & ALWAYS_REACHABLE_ROLES:
        return True
    for student_id in student_ids:
        if await staff_is_connected_to_student(db_session, staff_user_id, student_id):
            return True
    return False


async def may_message(
    db_session: AsyncSession, org_id: int, user_a_id: int, user_b_id: int
) -> tuple[bool, Optional[str]]:
    """(allowed, reason_if_denied). Symmetric in a/b."""
    if user_a_id == user_b_id:
        return False, "You cannot start a conversation with yourself."

    roles_a = await get_school_roles(db_session, org_id, user_a_id)
    roles_b = await get_school_roles(db_session, org_id, user_b_id)

    if not roles_a or not roles_b:
        return False, "Both people need a school role in this organisation before they can message."

    a_staff = bool(roles_a & STAFF_ROLES)
    b_staff = bool(roles_b & STAFF_ROLES)

    if a_staff and b_staff:
        return True, None

    a_parent = SchoolRole.PARENT.value in roles_a
    b_parent = SchoolRole.PARENT.value in roles_b
    a_student = SchoolRole.STUDENT.value in roles_a
    b_student = SchoolRole.STUDENT.value in roles_b

    # Families and peers: refused outright. See module docstring.
    if (a_parent or a_student) and (b_parent or b_student):
        return False, "Messaging is only available between families and school staff."

    # Exactly one side is staff from here on.
    if a_staff:
        staff_id, staff_roles, other_parent, other_student, other_id = (
            user_a_id, roles_a, b_parent, b_student, user_b_id,
        )
    else:
        staff_id, staff_roles, other_parent, other_student, other_id = (
            user_b_id, roles_b, a_parent, a_student, user_a_id,
        )

    if other_parent:
        children = await get_children_ids(db_session, other_id)
        if not children:
            return False, "This parent has no linked children, so there is no teacher to contact."
        if await _staff_reachable_by(db_session, org_id, staff_id, staff_roles, children):
            return True, None
        return False, "You can only message staff who teach your own child."

    if other_student:
        if await _staff_reachable_by(db_session, org_id, staff_id, staff_roles, [other_id]):
            return True, None
        return False, "You can only message staff who teach you."

    return False, "Messaging is only available between families and school staff."


async def assert_may_message(
    db_session: AsyncSession, org_id: int, user_a_id: int, user_b_id: int
) -> None:
    """Raise 403 unless a school relationship permits this conversation."""
    allowed, reason = await may_message(db_session, org_id, user_a_id, user_b_id)
    if not allowed:
        logger.info(
            "Blocked message attempt org=%s from=%s to=%s (%s)", org_id, user_a_id, user_b_id, reason
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=reason)
