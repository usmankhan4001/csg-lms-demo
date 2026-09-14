"""
FastAPI dependencies for feature flag checks and admin authorization.

These dependencies can be added to routers or individual endpoints
to check if features are enabled before processing requests.
"""
from fastapi import Depends, HTTPException, Path, Request
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from src.core.events.database import get_db_session
from src.core.keycloak_auth import KeycloakUserPrincipal, get_current_user_principal
from src.db.organization_config import OrganizationConfig
from src.db.organizations import Organization
from src.db.courses.courses import Course
from src.db.user_organizations import UserOrganization
from src.db.users import AnonymousUser, APITokenUser, PublicUser
from src.security.auth import get_current_user, resolve_acting_user_id
from src.security.rbac.constants import ADMIN_ROLE_ID
from typing import Literal

FeatureName = Literal[
    "courses",
    "folders",
    "communities",
    "podcasts",
    "boards",
    "playgrounds",
    "ai",
    "payments",
    "usergroups",
    # CSG-LMS SMS / RevOps modules
    "sms_attendance",
    "sms_timetable",
    "sms_gradebook",
    "sms_fees",
    "sms_financials",
    "sms_hr_payroll",
    "sms_library",
    # M04 School examinations (scheduled, invigilated, marked into the
    # gradebook). Distinct from Learnhouse's own inline LMS quizzes.
    "sms_exam",
    # M19 cross-module reports. Its own toggle rather than reusing a source
    # module's: it reads four of them, so no single one owns it.
    "sms_reports",
    "revops",
    # Phase 4, Part B: Counseling / Wellbeing / Career Guidance module.
    # Part A (teacher module additions: lesson plans, coursework-hour
    # allocation, report-card draft/send lifecycle) deliberately reuses the
    # existing "sms_gradebook" toggle instead of adding a new key -- it's an
    # extension of that module, not a new one. See
    # src/routers/sms_teacher_tools.py and the report-card lifecycle
    # additions in src/routers/sms_gradebook.py.
    "tutor_counseling",
    # M34 Inventory & Procurement
    "sms_inventory",
    # M36 Hostel & Dormitory
    "sms_hostel",
]


# ============================================================================
# Admin authorization dependency
# ============================================================================

async def require_org_admin(
    org_id: int = Path(..., description="Organization ID"),
    current_user: PublicUser | AnonymousUser | APITokenUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> bool:
    """
    Dependency that verifies the current user is an admin (role_id=1)
    for the specified organization.

    Use this at the router level for endpoints that modify org configuration.

    Raises:
        HTTPException 401: If user is anonymous
        HTTPException 403: If user is not an admin for this org
        HTTPException 404: If organization not found
    """
    # Check for anonymous user
    if isinstance(current_user, AnonymousUser):
        raise HTTPException(
            status_code=401,
            detail="Authentication required to perform this action",
        )

    # Verify organization exists
    statement = select(Organization).where(Organization.id == org_id)
    org = (await db_session.execute(statement)).scalars().first()

    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    acting_user_id = resolve_acting_user_id(current_user)

    # Superadmin bypass
    from src.security.superadmin import is_user_superadmin
    if await is_user_superadmin(acting_user_id, db_session):
        return True

    # Check if user is admin in this organization
    statement = (
        select(UserOrganization)
        .where(UserOrganization.user_id == acting_user_id)
        .where(UserOrganization.org_id == org_id)
        .where(UserOrganization.role_id == ADMIN_ROLE_ID)
    )

    user_org = (await db_session.execute(statement)).scalars().first()

    if not user_org:
        raise HTTPException(
            status_code=403,
            detail="Only organization admins can enable or disable features",
        )

    return True


async def _check_feature_enabled(
    feature: FeatureName,
    org_id: int,
    db_session: AsyncSession,
) -> bool:
    """
    Internal helper to check if a feature is enabled for an organization.
    Uses resolve_feature() for unified 4-layer resolution.

    Returns:
        True if enabled

    Raises:
        HTTPException 403 if feature is disabled
    """
    from src.security.features_utils.resolve import resolve_feature

    statement = select(OrganizationConfig).where(OrganizationConfig.org_id == org_id)
    org_config = (await db_session.execute(statement)).scalars().first()

    if org_config is None:
        raise HTTPException(
            status_code=404,
            detail="Organization has no config",
        )

    resolved = resolve_feature(feature, org_config.config or {}, org_id)

    if not resolved["enabled"]:
        raise HTTPException(
            status_code=403,
            detail=f"{feature.capitalize()} feature is not enabled for this organization",
        )

    return True


# ============================================================================
# Dependencies for endpoints with org_id as path/query parameter
# ============================================================================

async def require_courses_feature_by_org_id(
    org_id: int,
    db_session: AsyncSession = Depends(get_db_session),
) -> bool:
    """
    Dependency that checks if courses feature is enabled.
    Use for endpoints that have org_id as a direct parameter.
    """
    return await _check_feature_enabled("courses", org_id, db_session)


# ============================================================================
# Dependencies for endpoints with org_slug as path parameter
# ============================================================================

async def require_courses_feature_by_org_slug(
    org_slug: str = Path(...),
    db_session: AsyncSession = Depends(get_db_session),
) -> bool:
    """
    Dependency that checks if courses feature is enabled.
    Use for endpoints that have org_slug as a path parameter.
    """
    statement = select(Organization).where(Organization.slug == org_slug)
    org = (await db_session.execute(statement)).scalars().first()

    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    return await _check_feature_enabled("courses", org.id, db_session)


# ============================================================================
# Dependencies for endpoints with course_uuid as path parameter
# ============================================================================

async def require_courses_feature_by_course_uuid(
    course_uuid: str = Path(...),
    db_session: AsyncSession = Depends(get_db_session),
) -> bool:
    """
    Dependency that checks if courses feature is enabled.
    Use for endpoints that have course_uuid as a path parameter.
    """
    statement = select(Course).where(Course.course_uuid == course_uuid)
    course = (await db_session.execute(statement)).scalars().first()

    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    return await _check_feature_enabled("courses", course.org_id, db_session)


# ============================================================================
# Dependencies for endpoints with activity_uuid as path parameter
# ============================================================================

async def require_courses_feature_by_activity_uuid(
    activity_uuid: str = Path(...),
    db_session: AsyncSession = Depends(get_db_session),
) -> bool:
    """
    Dependency that checks if courses feature is enabled.
    Use for endpoints that have activity_uuid as a path parameter.
    """
    from src.db.courses.activities import Activity

    statement = select(Activity).where(Activity.activity_uuid == activity_uuid)
    activity = (await db_session.execute(statement)).scalars().first()

    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")

    statement = select(Course).where(Course.id == activity.course_id)
    course = (await db_session.execute(statement)).scalars().first()

    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    return await _check_feature_enabled("courses", course.org_id, db_session)


# ============================================================================
# Router-level dependencies (auto-detect parameter type)
# ============================================================================

async def require_courses_feature(
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
) -> bool:
    """
    Router-level dependency that auto-detects the parameter type and checks
    if the courses feature is enabled.

    Checks in order: course_uuid, activity_uuid, org_slug, org_id
    If none found, allows the request (for endpoints that don't need the check).
    """
    path_params = request.path_params

    # Try course_uuid first
    if "course_uuid" in path_params:
        course_uuid = path_params["course_uuid"]
        statement = select(Course).where(Course.course_uuid == course_uuid)
        course = (await db_session.execute(statement)).scalars().first()
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
        return await _check_feature_enabled("courses", course.org_id, db_session)

    # Try activity_uuid
    if "activity_uuid" in path_params:
        from src.db.courses.activities import Activity
        activity_uuid = path_params["activity_uuid"]
        statement = select(Activity).where(Activity.activity_uuid == activity_uuid)
        activity = (await db_session.execute(statement)).scalars().first()
        if not activity:
            raise HTTPException(status_code=404, detail="Activity not found")
        statement = select(Course).where(Course.id == activity.course_id)
        course = (await db_session.execute(statement)).scalars().first()
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
        return await _check_feature_enabled("courses", course.org_id, db_session)

    # Try org_slug
    if "org_slug" in path_params:
        org_slug = path_params["org_slug"]
        statement = select(Organization).where(Organization.slug == org_slug)
        org = (await db_session.execute(statement)).scalars().first()
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found")
        return await _check_feature_enabled("courses", org.id, db_session)

    # Try org_id
    if "org_id" in path_params:
        try:
            org_id = int(path_params["org_id"])
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Invalid org_id format")
        return await _check_feature_enabled("courses", org_id, db_session)

    # No relevant parameter found, allow the request
    # (for endpoints that don't need the feature check)
    return True


async def require_boards_feature(
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
) -> bool:
    """
    Router-level dependency that auto-detects the parameter type and checks
    if the boards feature is enabled AND the org plan is Personal or higher
    (Standard is gated by the feature flag instead).

    Checks in order: board_uuid (path), org_id (path), org_id (query)
    """
    from src.security.features_utils.plan_check import get_org_plan
    from src.security.features_utils.plans import plan_meets_requirement

    path_params = request.path_params
    org_id = None

    if "board_uuid" in path_params:
        from src.db.boards import Board
        board_uuid = path_params["board_uuid"]
        statement = select(Board).where(Board.board_uuid == board_uuid)
        board = (await db_session.execute(statement)).scalars().first()
        if not board:
            raise HTTPException(status_code=404, detail="Board not found")
        org_id = board.org_id

    if org_id is None and "org_id" in path_params:
        try:
            org_id = int(path_params["org_id"])
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Invalid org_id format")

    if org_id is None:
        org_id_query = request.query_params.get("org_id")
        if org_id_query is not None:
            try:
                org_id = int(org_id_query)
            except (ValueError, TypeError):
                pass

    if org_id is None:
        return True

    # Check feature flag
    await _check_feature_enabled("boards", org_id, db_session)

    # Check plan (Personal+ or OSS)
    current_plan = await get_org_plan(org_id, db_session)
    if not plan_meets_requirement(current_plan, "personal"):
        raise HTTPException(
            status_code=403,
            detail="Boards requires a Personal plan or higher. "
            f"Your organization is currently on the {current_plan.capitalize()} plan.",
        )

    return True


async def require_playgrounds_feature(
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
) -> bool:
    """
    Router-level dependency that auto-detects the parameter type and checks
    if the playgrounds feature is enabled AND the org plan is Personal or higher
    (Standard is gated by the feature flag instead).

    Checks in order: playground_uuid (path), org_id (path), org_id (query)
    """
    from src.security.features_utils.plan_check import get_org_plan
    from src.security.features_utils.plans import plan_meets_requirement

    path_params = request.path_params
    org_id = None

    if "playground_uuid" in path_params:
        from src.db.playgrounds import Playground
        playground_uuid = path_params["playground_uuid"]
        statement = select(Playground).where(Playground.playground_uuid == playground_uuid)
        playground = (await db_session.execute(statement)).scalars().first()
        if playground:
            org_id = playground.org_id

    if org_id is None and "org_id" in path_params:
        try:
            org_id = int(path_params["org_id"])
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Invalid org_id format")

    if org_id is None:
        org_id_query = request.query_params.get("org_id")
        if org_id_query is not None:
            try:
                org_id = int(org_id_query)
            except (ValueError, TypeError):
                pass

    if org_id is None:
        return True

    # Check feature flag
    await _check_feature_enabled("playgrounds", org_id, db_session)

    # Check plan (Personal+ or non-SaaS mode)
    from src.core.deployment_mode import get_deployment_mode
    if get_deployment_mode() != 'saas':
        return True

    current_plan = await get_org_plan(org_id, db_session)
    if not plan_meets_requirement(current_plan, "personal"):
        raise HTTPException(
            status_code=403,
            detail="Playgrounds requires a Personal plan or higher. "
            f"Your organization is currently on the {current_plan.capitalize()} plan.",
        )

    return True


# ============================================================================
# CSG-LMS SMS / RevOps module dependencies
# ============================================================================
#
# require_courses_feature/require_boards_feature/require_playgrounds_feature
# above auto-detect the org from the REQUEST (course_uuid, board_uuid,
# org_slug, org_id path/query params) because those resources belong to a
# Learnhouse Organization directly.
#
# The SMS domain (attendance, timetable, gradebook, fees, financials, HR,
# payroll, library, admissions/RevOps) has no such org_id/org_slug of its
# own -- its resources are scoped only by campus_id (see src/db/sms_campus.py
# and the sms_* routers), and campuses aren't looked up by these endpoints'
# path/query params consistently enough to auto-detect from. Instead, the org
# scope comes from the authenticated Keycloak principal's own org_id claim,
# already resolved from the caller's JWT by get_current_user_principal (the
# same dependency the sms_* routers use for authentication) -- so an
# unauthenticated caller is rejected with 401 before the feature check ever
# runs, satisfying "auth AND feature-toggle" together.


async def _check_sms_feature_enabled(
    feature: FeatureName,
    principal: KeycloakUserPrincipal,
    db_session: AsyncSession,
) -> bool:
    """
    Shared helper for the CSG-LMS SMS/RevOps router-level feature dependencies.

    Mirrors require_courses_feature's "no relevant parameter found -> allow"
    fallback: a principal with no org_id (e.g. a token that doesn't carry a
    tenant scope) isn't gated by a per-org admin toggle.
    """
    if principal.org_id is None:
        return True
    return await _check_feature_enabled(feature, principal.org_id, db_session)


async def require_sms_attendance_feature(
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
    db_session: AsyncSession = Depends(get_db_session),
) -> bool:
    """Router-level dependency gating the SMS Attendance module behind its admin toggle."""
    return await _check_sms_feature_enabled("sms_attendance", principal, db_session)


async def require_sms_exam_feature(
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
    db_session: AsyncSession = Depends(get_db_session),
) -> bool:
    """Router-level dependency gating the SMS Exam module behind its admin toggle."""
    return await _check_sms_feature_enabled("sms_exam", principal, db_session)


async def require_sms_reports_feature(
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
    db_session: AsyncSession = Depends(get_db_session),
) -> bool:
    """Router-level dependency gating the M19 cross-module reports behind its admin toggle."""
    return await _check_sms_feature_enabled("sms_reports", principal, db_session)


async def require_sms_timetable_feature(
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
    db_session: AsyncSession = Depends(get_db_session),
) -> bool:
    """Router-level dependency gating the SMS Timetable module behind its admin toggle."""
    return await _check_sms_feature_enabled("sms_timetable", principal, db_session)


async def require_sms_gradebook_feature(
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
    db_session: AsyncSession = Depends(get_db_session),
) -> bool:
    """Router-level dependency gating the SMS Gradebook module behind its admin toggle."""
    return await _check_sms_feature_enabled("sms_gradebook", principal, db_session)


async def require_sms_fees_feature(
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
    db_session: AsyncSession = Depends(get_db_session),
) -> bool:
    """Router-level dependency gating the SMS Fees module behind its admin toggle."""
    return await _check_sms_feature_enabled("sms_fees", principal, db_session)


async def require_sms_financials_feature(
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
    db_session: AsyncSession = Depends(get_db_session),
) -> bool:
    """Router-level dependency gating the SMS Financials module behind its admin toggle."""
    return await _check_sms_feature_enabled("sms_financials", principal, db_session)


async def require_sms_hr_payroll_feature(
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
    db_session: AsyncSession = Depends(get_db_session),
) -> bool:
    """
    Router-level dependency gating the combined SMS HR + Payroll modules
    behind one admin toggle (shared by sms_hr.py and sms_payroll.py -- see
    sms_hr_payroll on AdminToggles for why they're combined).
    """
    return await _check_sms_feature_enabled("sms_hr_payroll", principal, db_session)


async def require_sms_library_feature(
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
    db_session: AsyncSession = Depends(get_db_session),
) -> bool:
    """Router-level dependency gating the SMS Library module behind its admin toggle."""
    return await _check_sms_feature_enabled("sms_library", principal, db_session)


async def require_revops_feature(
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
    db_session: AsyncSession = Depends(get_db_session),
) -> bool:
    """Router-level dependency gating the AI RevOps / Admissions module behind its admin toggle."""
    return await _check_sms_feature_enabled("revops", principal, db_session)


async def require_tutor_counseling_feature(
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
    db_session: AsyncSession = Depends(get_db_session),
) -> bool:
    """Router-level dependency gating the Counseling/Wellbeing/Career Guidance
    module (src/routers/sms_counseling.py) behind its admin toggle."""
    return await _check_sms_feature_enabled("tutor_counseling", principal, db_session)


async def require_sms_inventory_feature(
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
    db_session: AsyncSession = Depends(get_db_session),
) -> bool:
    """Router-level dependency gating the SMS Inventory & Procurement module behind its admin toggle."""
    return await _check_sms_feature_enabled("sms_inventory", principal, db_session)


async def require_sms_hostel_feature(
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
    db_session: AsyncSession = Depends(get_db_session),
) -> bool:
    """Router-level dependency gating the SMS Hostel & Dormitory module behind its admin toggle."""
    return await _check_sms_feature_enabled("sms_hostel", principal, db_session)

