from fastapi import APIRouter, Depends
from src.routers import admin as admin_router_module
from src.routers import analytics as analytics_router_module
from src.routers import audit as audit_router_module
from src.routers import code_execution
from src.routers import code_submissions
from src.routers import health
from src.routers import demo as demo_router_module
from src.routers import instance
from src.routers import plans
from src.routers import usergroups
from src.routers import dev, trail, users, auth, orgs, roles, search
from src.routers import (
    sms_attendance,
    sms_campus,
    sms_counseling,
    sms_fees,
    sms_financials,
    sms_gradebook,
    sms_hr,
    sms_identity,
    sms_library,
    sms_payroll,
    sms_revops,
    sms_teacher_tools,
    sms_timetable,
    live_classes,
)
from src.routers import mfa as mfa_router_module
from src.routers import monitoring
from src.routers import nudges as nudges_router_module
from src.routers import stream
from src.routers import api_tokens
from src.routers import webhooks
from src.routers.integrations import zapier as zapier_integration
from src.routers.ai import ai, magicblocks, courseplanning, rag, images, quiz, assignment_gen, scenario, audio
from src.routers import ai_tutor as ai_tutor_router_module
from src.routers import ai_student_profile as ai_student_profile_router_module
from src.routers.boards import boards_playground
from src.routers.orgs import ai_credits
from src.routers.orgs import custom_domains
from src.routers.orgs import packs
from src.routers.orgs import org_plan
from src.routers.courses import chapters, courses, assignments, certifications
from src.routers.folders import folders as folders_router_module
from src.routers.media import media as media_router_module
from src.routers.courses import migration as migration_router_module
from src.routers.communities import communities as communities_router_module
from src.routers.communities import discussions as discussions_router_module
from src.routers.courses.activities import activities, blocks
from src.routers.podcasts import podcasts as podcasts_router_module
from src.routers.podcasts import episodes as episodes_router_module
from src.routers.boards import boards as boards_router_module
from src.routers.playgrounds import playgrounds as playgrounds_router_module
from src.routers.playgrounds import playgrounds_generator as playgrounds_generator_router
from src.core.ee_hooks import register_ee_routers
from src.core.deployment_mode import get_deployment_mode
from src.services.dev.dev import isDevModeEnabledOrRaise
from src.routers.utils import router as utils_router
from src.security.auth import get_current_user
from src.security.api_token_utils import (
    get_authenticated_non_api_token_user,
    require_authenticated_user_or_api_token,
    require_non_api_token_user,
)
from src.security.features_utils.plan_check import require_plan, require_plan_for_boards, require_plan_for_certifications, require_plan_for_community, require_plan_for_usergroups, require_plan_for_playgrounds


v1_router = APIRouter(prefix="/api/v1")

# Helper dependency to reject API token access (still admits AnonymousUser —
# use on routers that contain at least one deliberately-public endpoint).
async def get_non_api_token_user(user = Depends(get_current_user)):
    """Dependency that rejects API token access."""
    return await require_non_api_token_user(user)


# Alias used by routers that have zero public endpoints. Requires a real
# authenticated session AND rejects API tokens. See F-2 in the security
# audit for context: the plain ``get_non_api_token_user`` silently admits
# anonymous callers, which is the wrong default for admin-only or
# billing/compute-sensitive routes.
require_authenticated_user = get_authenticated_non_api_token_user

# API Routes
v1_router.include_router(
    users.router,
    prefix="/users",
    tags=["users"],
    dependencies=[Depends(get_non_api_token_user)]
)
v1_router.include_router(
    usergroups.router,
    prefix="/usergroups",
    tags=["usergroups"],
    # Admit API tokens (headless enrollment/usergroup management) while still
    # rejecting anonymous callers — same pattern as /assignments. `usergroups`
    # is already an allowed API-token resource type in the RBAC layer
    # (rbac.py authorization_verify_api_token_permissions), and every handler
    # authorizes through usergroups.rbac_check, which has an APITokenUser branch
    # enforcing the token's usergroups rights + org boundary. The two handlers
    # that authorize against a placeholder uuid (create, get-by-resource) get an
    # explicit token org-boundary check in the service layer.
    dependencies=[
        Depends(require_authenticated_user_or_api_token),
        Depends(require_plan_for_usergroups("standard", "User Groups")),
    ],
)
v1_router.include_router(auth.router, prefix="/auth", tags=["auth"])
# Two-factor: enrollment/management plus the /auth/login/mfa challenge.
v1_router.include_router(mfa_router_module.router, prefix="/auth", tags=["auth"])
v1_router.include_router(
    orgs.router,
    prefix="/orgs",
    tags=["orgs"],
    dependencies=[Depends(get_non_api_token_user)]
)
v1_router.include_router(
    ai_credits.router,
    prefix="/orgs",
    tags=["ai-credits"],
    dependencies=[Depends(require_authenticated_user)]
)
v1_router.include_router(
    roles.router,
    prefix="/roles",
    tags=["roles"],
    dependencies=[Depends(require_authenticated_user)]
)
v1_router.include_router(
    api_tokens.router,
    prefix="/orgs",
    tags=["api-tokens"],
    dependencies=[Depends(require_authenticated_user), Depends(require_plan("pro", "API Access"))]
)
v1_router.include_router(
    webhooks.router,
    prefix="/orgs",
    tags=["webhooks"],
    dependencies=[Depends(require_authenticated_user), Depends(require_plan("pro", "Webhooks"))]
)
v1_router.include_router(
    zapier_integration.router,
    prefix="/integrations/zapier",
    tags=["integrations", "zapier"],
)
v1_router.include_router(
    custom_domains.router,
    prefix="/orgs",
    tags=["custom-domains"],
    dependencies=[Depends(require_authenticated_user), Depends(require_plan("standard", "Custom Domains"))]
)
# Public domain resolution endpoint (no auth required)
v1_router.include_router(
    custom_domains.public_router,
    prefix="/orgs",
    tags=["custom-domains"],
)
# Public unsubscribe endpoints (no auth — the HMAC token in the link is the
# authorisation; a nudge recipient may have no session at all)
v1_router.include_router(
    nudges_router_module.public_router,
    prefix="/emails",
    tags=["emails"],
)
# Email delivery feedback from the provider (protected by a shared secret).
# Bounces and complaints have to reach us or a dead address is mailed forever.
v1_router.include_router(
    nudges_router_module.internal_router,
    prefix="/internal/emails",
    tags=["emails-internal"],
)
# Internal domain listing endpoint (protected by internal key)
v1_router.include_router(
    custom_domains.internal_router,
    prefix="/internal",
    tags=["custom-domains-internal"],
)
# Internal packs endpoint (protected by platform key)
v1_router.include_router(
    packs.internal_router,
    prefix="/internal/packs",
    tags=["packs-internal"],
)
# Org-facing packs endpoint (user auth, admin only)
v1_router.include_router(
    packs.router,
    prefix="/orgs",
    tags=["packs"],
    dependencies=[Depends(require_authenticated_user)],
)
# Internal cloud plan-state endpoint (protected by cloud internal key).
# SaaS-only: absent in oss/ee deployments. Extracted into a function so the
# SaaS-only branch is unit-testable without reloading the module.
def _mount_saas_only_routers(target_router: APIRouter) -> None:
    if get_deployment_mode() == 'saas':
        target_router.include_router(
            org_plan.internal_router,
            prefix="/cloud_internal",
            tags=["cloud-internal"],
        )


_mount_saas_only_routers(v1_router)
v1_router.include_router(
    blocks.router,
    prefix="/blocks",
    tags=["blocks"],
    # Mixed router: public course pages legitimately fetch block media as
    # anonymous visitors. Anonymous access is gated per-handler: GET block
    # handlers run RBAC + org-membership checks in the service layer; POST
    # block handlers (creates) require ownership via check_resource_access.
    dependencies=[Depends(get_non_api_token_user)]
)
v1_router.include_router(
    admin_router_module.router,
    prefix="/admin",
    tags=["admin"],
)
v1_router.include_router(courses.router, prefix="/courses", tags=["courses"])
v1_router.include_router(
    migration_router_module.router,
    prefix="/courses",
    tags=["migration"],
    dependencies=[Depends(require_authenticated_user)]
)
v1_router.include_router(search.router, prefix="/search", tags=["search"])
v1_router.include_router(
    assignments.router,
    prefix="/assignments",
    tags=["assignments"],
    # Admit API tokens (headless assignments) while still rejecting anonymous.
    # Individual handlers gate access: authoring + grading go through
    # authorize_assignment_access (assignments rights bucket), while learner
    # /me + submission endpoints keep _block_api_tokens (session-only).
    dependencies=[Depends(require_authenticated_user_or_api_token)]
)
v1_router.include_router(chapters.router, prefix="/chapters", tags=["chapters"])
v1_router.include_router(activities.router, prefix="/activities", tags=["activities"])
v1_router.include_router(
    folders_router_module.router, prefix="/folders", tags=["folders"]
)
v1_router.include_router(
    media_router_module.router, prefix="/media", tags=["media"]
)
v1_router.include_router(
    communities_router_module.router,
    prefix="/communities",
    tags=["communities"],
    dependencies=[Depends(require_plan_for_community("standard", "Communities"))]
)
v1_router.include_router(
    discussions_router_module.router,
    tags=["discussions"],
    dependencies=[Depends(require_plan_for_community("standard", "Communities"))]
)
v1_router.include_router(
    podcasts_router_module.router,
    prefix="/podcasts",
    tags=["podcasts"]
)
v1_router.include_router(
    episodes_router_module.router,
    prefix="/podcasts",
    tags=["podcasts", "episodes"]
)
v1_router.include_router(
    certifications.router,
    prefix="/certifications",
    tags=["certifications"],
    dependencies=[Depends(require_plan_for_certifications("pro", "Certifications"))]
)
v1_router.include_router(
    boards_router_module.router,
    prefix="/boards",
    tags=["boards"],
    dependencies=[Depends(get_non_api_token_user), Depends(require_plan_for_boards("personal", "Boards"))]
)
v1_router.include_router(
    boards_router_module.internal_router,
    prefix="/boards",
    tags=["boards-internal"],
)
v1_router.include_router(
    trail.router,
    prefix="/trail",
    tags=["trail"],
    dependencies=[Depends(require_authenticated_user)]
)
v1_router.include_router(
    ai.router,
    prefix="/ai",
    tags=["ai"],
    dependencies=[Depends(require_authenticated_user)]
)
v1_router.include_router(
    magicblocks.router,
    prefix="/ai",
    tags=["ai", "magicblocks"],
    dependencies=[Depends(require_authenticated_user)]
)
v1_router.include_router(
    courseplanning.router,
    prefix="/ai",
    tags=["ai", "courseplanning"],
    dependencies=[Depends(require_authenticated_user)]
)
v1_router.include_router(
    rag.router,
    prefix="/ai",
    tags=["ai", "rag"],
    dependencies=[Depends(require_authenticated_user)]
)
v1_router.include_router(
    images.router,
    prefix="/ai",
    tags=["ai", "images"],
    dependencies=[Depends(require_authenticated_user)]
)
v1_router.include_router(
    audio.router,
    prefix="/ai",
    tags=["ai", "audio"],
    dependencies=[Depends(require_authenticated_user)]
)
v1_router.include_router(
    quiz.router,
    prefix="/ai",
    tags=["ai", "quiz"],
    dependencies=[Depends(require_authenticated_user)]
)
v1_router.include_router(
    assignment_gen.router,
    prefix="/ai",
    tags=["ai", "assignment-gen"],
    dependencies=[Depends(require_authenticated_user)]
)
v1_router.include_router(
    scenario.router,
    prefix="/ai",
    tags=["ai", "scenario"],
    dependencies=[Depends(require_authenticated_user)]
)
v1_router.include_router(
    ai_tutor_router_module.router,
    prefix="/ai",
    tags=["ai", "ai-tutor"],
)
v1_router.include_router(
    ai_student_profile_router_module.router,
    prefix="/ai",
    tags=["ai", "student-profile"],
)
v1_router.include_router(
    boards_playground.router,
    prefix="/boards",
    tags=["boards", "boards-playground"],
    dependencies=[Depends(require_authenticated_user), Depends(require_plan_for_boards("personal", "Boards"))]
)
v1_router.include_router(
    playgrounds_router_module.router,
    prefix="/playgrounds",
    tags=["playgrounds"],
    dependencies=[Depends(require_authenticated_user), Depends(require_plan_for_playgrounds("personal", "Playgrounds"))]
)
v1_router.include_router(
    playgrounds_generator_router.router,
    prefix="/playgrounds",
    tags=["playgrounds", "playgrounds-generator"],
    dependencies=[Depends(require_authenticated_user), Depends(require_plan_for_playgrounds("personal", "Playgrounds"))]
)

v1_router.include_router(
    analytics_router_module.router,
    prefix="/analytics",
    tags=["analytics"],
    dependencies=[Depends(require_authenticated_user)],
)

# Per-student audit & analytics (org-admin only; enforced inside the router)
v1_router.include_router(
    audit_router_module.router,
    prefix="/audit",
    tags=["audit"],
    dependencies=[Depends(require_authenticated_user)],
)

v1_router.include_router(
    code_execution.router,
    prefix="/code",
    tags=["code-execution"],
    dependencies=[Depends(require_authenticated_user)],
)

v1_router.include_router(
    code_submissions.router,
    prefix="/code/submissions",
    tags=["code_submissions"],
    dependencies=[Depends(require_authenticated_user)],
)

# Instance info (public, no auth)
v1_router.include_router(instance.router, prefix="/instance", tags=["instance"])
# Demo: /demo/status is public (the onboarding page calls it before the
# visitor has done anything); /demo/enter resolves the user itself.
v1_router.include_router(demo_router_module.router, prefix="/demo", tags=["demo"])

# Sentry feedback relay (rejects API tokens; works for both anonymous and
# authenticated callers so the in-app feedback modal keeps working everywhere)
v1_router.include_router(
    monitoring.router,
    prefix="/monitoring",
    tags=["monitoring"],
    dependencies=[Depends(get_non_api_token_user)],
)

# Plan limits (public, no auth — used by frontend pricing pages)
v1_router.include_router(plans.router, prefix="/plans", tags=["plans"])

# Register EE Routers if available
register_ee_routers(v1_router)

v1_router.include_router(
    health.router,
    prefix="/health",
    tags=["health"],
    dependencies=[Depends(get_non_api_token_user)]
)

# Dev Routes
v1_router.include_router(
    dev.router,
    prefix="/dev",
    tags=["dev"],
    dependencies=[Depends(isDevModeEnabledOrRaise), Depends(get_non_api_token_user)],
)

v1_router.include_router(
    utils_router,
    prefix="/utils",
    tags=["utils"],
    dependencies=[Depends(require_authenticated_user)]
)

# Video Streaming Routes
v1_router.include_router(
    stream.router,
    prefix="/stream",
    tags=["stream"],
    dependencies=[Depends(get_non_api_token_user)]
)

# Academic SMS Routes (Attendance, Leave Requests, Timetable & Conflict Solver)
#
# NOTE on auth (fixed as part of the CSG-LMS dashboard-rewrite Step 0): these
# 8 routers (all except sms_campus, which was already correct) used to carry
# BOTH this router-mount-level `require_authenticated_user_or_api_token`
# (Learnhouse's own native session/API-token auth, from src/security/auth.py)
# AND a per-handler `Depends(get_current_user_principal)` (Keycloak OIDC,
# from src/core/keycloak_auth.py) inside every single endpoint in each of
# these router files. Both read the *same* `Authorization: Bearer <token>`
# header but expect mutually incompatible token formats/secrets -- a request
# could satisfy at most one of them, so these routers were unreachable over
# HTTP by any caller once the Keycloak per-handler gate was added (the
# existing src/tests/sms/test_sms_auth.py suite didn't catch this because it
# mounts each router standalone, bypassing this file's wrapper entirely).
# sms_campus.py never had this wrapper, which is what the per-handler
# Keycloak checks alone were always meant to be for. Removing the redundant
# wrapper here makes these consistent with sms_campus and restores a
# Keycloak-only Bearer token as sufficient, matching every handler's own
# `get_current_user_principal` dependency. See
# src/tests/routers/test_sms_router_mount_auth.py for a regression test
# against the real composed `v1_router` (not a bare per-router test app).
v1_router.include_router(
    sms_attendance.router,
    prefix="/sms/attendance",
    tags=["sms-attendance"],
)

v1_router.include_router(
    sms_timetable.router,
    prefix="/sms/timetable",
    tags=["sms-timetable"],
)

v1_router.include_router(
    sms_campus.router,
    prefix="/sms",
    tags=["sms-campus"],
)

v1_router.include_router(
    sms_identity.router,
    prefix="/sms",
    tags=["sms-identity"],
)

v1_router.include_router(
    sms_gradebook.router,
    prefix="/sms/gradebook",
    tags=["sms-gradebook"],
)

v1_router.include_router(
    sms_fees.router,
    prefix="/sms/fees",
    tags=["sms-fees"],
)

v1_router.include_router(
    live_classes.router,
    prefix="/live",
    tags=["live-classes"],
    # Unlike the routers above, live_classes.py has NO per-handler Keycloak
    # dependency at all -- this mount-level wrapper is its only auth gate, not
    # a redundant second one. Do not remove it under the same "double-gate"
    # fix applied to sms_revops.router above; that would leave it unauthenticated.
    dependencies=[Depends(require_authenticated_user_or_api_token)],
)

v1_router.include_router(
    sms_financials.router,
    prefix="/sms/financials",
    tags=["sms-financials"],
)

v1_router.include_router(
    sms_hr.router,
    prefix="/sms/hr",
    tags=["sms-hr"],
)

v1_router.include_router(
    sms_payroll.router,
    prefix="/sms/payroll",
    tags=["sms-payroll"],
)

v1_router.include_router(
    sms_library.router,
    prefix="/sms/library",
    tags=["sms-library"],
)

v1_router.include_router(
    sms_revops.router,
    prefix="/revops",
    tags=["sms-revops"],
)

# Phase 4: Counseling / Wellbeing / Career Guidance (new module) and the
# Teacher Module additions (lesson plans + coursework-hour allocation,
# gated behind the existing sms_gradebook toggle). Mounted the same way as
# the 8 SMS routers above -- feature-toggle dependency lives INSIDE each
# router file (require_tutor_counseling_feature / require_sms_gradebook_feature),
# and NOT repeated here at the mount level, so as not to reintroduce the
# double-auth-gate bug documented above.
v1_router.include_router(
    sms_counseling.router,
    prefix="/sms/counseling",
    tags=["sms-counseling"],
)

v1_router.include_router(
    sms_teacher_tools.router,
    prefix="/sms/teacher-tools",
    tags=["sms-teacher-tools"],
)


