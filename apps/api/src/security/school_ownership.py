"""
Server-side "is this actually your data" enforcement for SMS endpoints.

Before this file, `student_id`/`section_id` were trusted, client-supplied
path/query params with NO verification against the caller's identity --
confirmed by direct code audit: `KeycloakUserPrincipal` never carried
subject_id/section_id/children_ids server-side (those were pure frontend
JWT-decode convenience claims), so any authenticated principal of any role
could request any student's/section's data. See PROJECT_DOCS/ARCHITECTURE.md
and PROJECT_DOCS/BUGFIXES_LOG.md.

This mirrors the existing `require_campus_access()` dependency-factory shape
in src/core/keycloak_auth.py (403 on mismatch, SUPER_ADMIN/SCHOOL_ADMIN
bypass) rather than inventing a new pattern.

Deliberately NOT exhaustive: applied only to the endpoints backing real
frontend call sites today (see callers of this module). Every other
un-hardened student_id/section_id param is a tracked, documented gap --
adopt this same dependency there as each is actually exposed to a real
(non-superadmin) user, not all at once.
"""

from typing import Callable, List

from fastapi import Depends, HTTPException, Request, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.events.database import get_db_session
from src.core.keycloak_auth import SCHOOL_ADMIN, KeycloakUserPrincipal, get_current_user_principal
from src.db.sms_campus import ClassSection, StudentEnrollment
from src.db.sms_identity import StudentGuardian
from src.db.sms_timetable import TimetableSchedule


async def get_own_children_ids(user_id: int, db_session: AsyncSession) -> List[int]:
    result = await db_session.exec(select(StudentGuardian).where(StudentGuardian.guardian_user_id == user_id))
    return [g.student_id for g in result.all()]


async def get_own_teacher_section_ids(user_id: int, db_session: AsyncSession) -> List[int]:
    """Every section a teacher owns, whether as homeroom/class teacher
    (ClassSection.class_teacher_id) or as a subject teacher on the timetable
    (TimetableSchedule.teacher_id)."""
    class_result = await db_session.exec(select(ClassSection.id).where(ClassSection.class_teacher_id == user_id))
    timetable_result = await db_session.exec(
        select(TimetableSchedule.section_id).where(TimetableSchedule.teacher_id == user_id)
    )
    return list({*class_result.all(), *timetable_result.all()})


def require_own_student_or_privileged(student_id_param: str = "student_id") -> Callable[..., "KeycloakUserPrincipal"]:
    """
    Dependency factory: the caller must be the student themselves, a parent
    of that student, SCHOOL_ADMIN, or SUPER_ADMIN. Mirrors
    `require_campus_access()`'s shape exactly.
    """

    async def _student_ownership_checker(
        request: Request,
        principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
        db_session: AsyncSession = Depends(get_db_session),
    ) -> KeycloakUserPrincipal:
        if principal.is_superadmin or principal.has_role(SCHOOL_ADMIN):
            return principal

        target_raw = request.path_params.get(student_id_param) or request.query_params.get(student_id_param)
        if target_raw is None:
            return principal
        try:
            target_student_id = int(target_raw)
        except (ValueError, TypeError):
            return principal

        user_id = principal.raw_claims.get("lh_user_id")
        if user_id is not None and target_student_id == user_id:
            return principal

        if user_id is not None:
            children_ids = await get_own_children_ids(user_id, db_session)
            if target_student_id in children_ids:
                return principal

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access your own records (or your own children's).",
        )

    return _student_ownership_checker


async def assert_owns_section_or_privileged(
    principal: KeycloakUserPrincipal,
    section_id: int,
    db_session: AsyncSession,
) -> None:
    """Body-supplied equivalent of `require_own_student_or_privileged` for
    endpoints where the id-to-check only exists after the request body is
    parsed (e.g. batch roll-call's `payload.section_id`), so it can't be a
    plain FastAPI dependency reading path/query params."""
    if principal.is_superadmin or principal.has_role(SCHOOL_ADMIN):
        return

    user_id = principal.raw_claims.get("lh_user_id")
    if user_id is not None:
        own_sections = await get_own_teacher_section_ids(user_id, db_session)
        if section_id in own_sections:
            return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You can only submit attendance for a section you teach.",
    )
