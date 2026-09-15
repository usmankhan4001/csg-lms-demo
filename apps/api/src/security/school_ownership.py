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

from typing import Callable, List, Optional

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
    if principal.is_superadmin:
        return

    # A SCHOOL_ADMIN bypasses the "must teach it" rule, but NOT campus
    # isolation. This previously returned unconditionally, so a school admin
    # bound to campus 2 could take roll-call for, and enter grades against,
    # any section at any other campus in the org. ClassSection.campus_id is
    # non-optional, so it is a reliable authority.
    if principal.has_role(SCHOOL_ADMIN):
        if principal.campus_id is None:
            return  # org-level admin, no single campus to be bound to
        section_campus = (
            await db_session.execute(
                select(ClassSection.campus_id).where(ClassSection.id == section_id)
            )
        ).scalar_one_or_none()
        if section_campus is None or section_campus == principal.campus_id:
            return
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Multi-campus isolation policy prohibits cross-campus operations",
        )

    user_id = principal.raw_claims.get("lh_user_id")
    if user_id is not None:
        own_sections = await get_own_teacher_section_ids(user_id, db_session)
        if section_id in own_sections:
            return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You can only submit attendance for a section you teach.",
    )


# ---------------------------------------------------------------------------
# Campus scoping.
#
# `require_campus_access` (core/keycloak_auth.py) is weaker than its name
# suggests, in two ways that matter:
#
#   1. It reads only `request.path_params` and `request.query_params`, so a
#      campus_id carried in the request BODY is never checked at all.
#   2. It rejects only an EXPLICIT mismatch. An unscoped request -- no campus
#      anywhere -- returns the principal untouched, so a campus-bound admin
#      gets org-wide reach simply by omitting the field.
#
# Both were live: `generate_batch_salary_slips` filters on `payload.campus_id`,
# so omitting it generated salary slips for every active staff member across
# every campus. This resolves the campus a request actually operates on,
# closing both holes, and is the single implementation the modules should use.
# ---------------------------------------------------------------------------


def resolve_scoped_campus_id(
    principal: KeycloakUserPrincipal,
    requested: "int | None",
) -> "int | None":
    """The campus this request may act on.

    A campus-bound caller is pinned to their own campus whether they asked for
    another one or asked for none. Only a caller with no campus of their own
    (a SUPER_ADMIN, or an org-level admin) may operate org-wide, and only then
    does this return None meaning "all campuses".

    Returning the caller's campus rather than raising keeps unscoped requests
    working -- they simply narrow to what the caller is entitled to, which is
    almost always what they meant.
    """
    if principal.is_superadmin:
        return requested
    if principal.campus_id is not None:
        return principal.campus_id
    return requested


def assert_campus_allowed(
    principal: KeycloakUserPrincipal,
    requested: "int | None",
) -> None:
    """Reject an explicit cross-campus request outright.

    Use this where silently narrowing would be misleading -- a write that names
    a campus should fail loudly rather than quietly land somewhere else.
    """
    if principal.is_superadmin or requested is None:
        return
    if principal.campus_id is not None and principal.campus_id != requested:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Multi-campus isolation policy prohibits cross-campus operations",
        )


# ---------------------------------------------------------------------------
# Organisation scoping -- the tenant boundary one level above campus.
#
# Eighteen call sites across sms_cognia, sms_gradebook, sms_revops_config and
# sms_settings resolved their tenant as `principal.org_id or 1`: when a
# principal carried no organisation, every one of them silently read AND WROTE
# the data of organisation 1 -- whichever school happens to hold the lowest id.
# `update_settings_group` wrote another school's settings, `delete_knowledge_
# entry` deleted its records, and the transcript export stamped its name onto
# a document headed "OFFICIAL".
#
# `resolve_school_principal` leaves `org_id` None for an authenticated user
# holding zero SMSUserRole grants, and also for a SUPER_ADMIN on an instance
# where `_get_default_org_id` finds no organisation at all. Neither is a
# request that can be attributed to a school, so neither may proceed.
# ---------------------------------------------------------------------------


def require_org_id(principal: KeycloakUserPrincipal) -> int:
    """The organisation this request acts on, or refuse it.

    403 rather than 400, matching `assert_campus_allowed` above and
    `routers/notifications.py`: the request is well-formed and the caller is
    authenticated, so there is nothing for them to correct in it -- their
    account simply is not attached to a school. (Two SMS routers,
    sms_admissions and sms_ai_consent, answer 400 for the same condition.
    They are outside this change; the inconsistency is noted, not widened.)

    Never returns a fallback. A tenant that cannot be established is missing,
    not organisation 1.
    """
    if principal.org_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Forbidden: this account is not attached to a school "
                "organisation, so the request cannot be scoped to one."
            ),
        )
    return principal.org_id


def require_user_id(principal: KeycloakUserPrincipal) -> int:
    """The integer Learnhouse user id behind this request, or refuse it.

    `principal.sub` is the user's `user_uuid` STRING (see
    `security/school_principal.py`, which sets `sub=effective_user.user_uuid`).
    The integer id travels alongside it in `raw_claims["lh_user_id"]`.

    Two teacher-identity systems grew out of that split: `LessonPlan.teacher_id`
    and the two counselling `psychologist_id` columns stored the string, while
    timetable, live classes and section ownership stored the integer -- so a
    teacher's lesson plans and their timetable could not be joined, and "what is
    this teacher doing today" had no answer in SQL. Everything is converging on
    the integer, and this is the one place that reads it.

    403 rather than 400, for the same reason as `require_org_id` above: the
    request is well-formed and the caller is authenticated, so there is nothing
    for them to correct.

    Never returns a fallback. An unidentifiable caller is unknown, not user 1.
    """
    raw = principal.raw_claims or {}
    user_id = raw.get("lh_user_id")
    if not isinstance(user_id, int):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Forbidden: this request carries no Learnhouse user identity, "
                "so it cannot be attributed to a person."
            ),
        )
    return user_id


def get_user_id(principal: KeycloakUserPrincipal) -> Optional[int]:
    """The integer Learnhouse user id if this request carries one, else None.

    The lenient counterpart to `require_user_id`. Use this wherever the integer
    identity is being ADOPTED rather than depended on -- during the migration
    from the legacy `user_uuid` string (b7e2d41a9c38), a record is still fully
    attributable by its string column, so a missing integer must not refuse an
    otherwise valid write.

    None here means "not resolved", never "nobody". Callers must not treat it as
    a match: two records with NULL are not the same author.
    """
    raw = principal.raw_claims or {}
    user_id = raw.get("lh_user_id")
    return user_id if isinstance(user_id, int) else None
