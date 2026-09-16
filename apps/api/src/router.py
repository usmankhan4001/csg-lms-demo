from fastapi import APIRouter, Depends
from src.routers import admin as admin_router_module
from src.routers import analytics as analytics_router_module
from src.routers import audit as audit_router_module
from src.routers import code_execution
from src.routers import code_submissions
from src.routers import health
from src.routers import metrics
from src.routers import demo as demo_router_module
from src.routers import instance
from src.routers import plans
from src.routers import usergroups
from src.routers import dev, trail, users, auth, orgs, roles, search
from src.routers import (
    sms_attendance,
    sms_campus,
    sms_counseling,
    sms_curriculum,
    sms_fees,
    sms_fee_webhooks,
    sms_financials,
    sms_exam,
    sms_gradebook,
    sms_data_subject,
    sms_reports,
    sms_admissions,
    sms_settings,
    sms_ai_consent,
    sms_hr,
    sms_identity,
    sms_school_setup,
    sms_library,
    sms_payroll,
    sms_revops,
    sms_revops_config,
    revops_agents,
    sms_teacher_tools,
    sms_timetable,
    sms_cognia,
    sms_discipline,
    sms_alumni,
    sms_certificates,
    sms_gamification,
    sms_events_facilities,
    sms_pathways,
    sms_hostel,
    sms_inventory,
    sms_facilities,
    sms_transport,
    sms_section_subjects,
    sms_matriculation,
    sms_documents,
    sms_exports,
    live_classes,
    live_class_webhooks,
    sms_live_class_attendance,
)
from src.routers import ems_roles
from src.routers import mfa as mfa_router_module
from src.routers import monitoring
from src.routers import notifications as notifications_router_module
from src.routers import nudges as nudges_router_module
from src.routers import stream
from src.routers import api_tokens
from src.routers import webhooks
from src.routers.integrations import zapier as zapier_integration
from src.routers.ai import ai, magicblocks, courseplanning, rag, images, quiz, assignment_gen, scenario, audio
from src.routers import ai_tutor as ai_tutor_router_module
from src.routers import ai_student_profile as ai_student_profile_router_module
from src.routers import ai_knowledge_graph as ai_knowledge_graph_router_module
from src.routers import ai_parent_digest as ai_parent_digest_router_module
from src.routers import ai_oversight as ai_oversight_router_module
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
v1_router.include_router(health.router, prefix="/health", tags=["health"])
v1_router.include_router(metrics.router, tags=["metrics"])
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
    ai_knowledge_graph_router_module.router,
    prefix="/ai/knowledge-graph",
    tags=["ai", "knowledge-graph"],
)
v1_router.include_router(
    ai_parent_digest_router_module.router,
    prefix="/ai/parent",
    tags=["ai", "parent-digest"],
)
v1_router.include_router(
    ai_oversight_router_module.router,
    prefix="/ai/oversight",
    tags=["ai", "tutor-oversight"],
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

# First-run school setup. Deliberately NOT gated by `require_roles` at the
# mount: the caller bootstrapping a brand-new school holds no school roles yet
# (roles come only from SMSUserRole), so authorisation is decided per-handler
# against organisation ownership -- see routers/sms_school_setup.py.
v1_router.include_router(
    sms_school_setup.router,
    prefix="/sms",
    tags=["sms-school-setup"],
)

# Notifications (M35) + Communication Hub (M13). Mounted at /sms because every
# route is per-person school context, resolved from the same principal the
# other sms_* routers use -- see routers/notifications.py.
v1_router.include_router(
    notifications_router_module.router,
    prefix="/sms",
    tags=["notifications"],
)

v1_router.include_router(
    sms_gradebook.router,
    prefix="/sms/gradebook",
    tags=["sms-gradebook"],
)

# M19 cross-module reports. Mounted after the gradebook because it READS that
# module (and attendance/fees/admissions) rather than owning anything: it is
# the principal's single view, not a fifth source of truth.
v1_router.include_router(
    sms_reports.router,
    prefix="/sms/reports",
    tags=["sms-reports"],
)

# Data-subject access and erasure for the SCHOOL record. The platform's own
# export (services/admin/admin.py) covers the Learnhouse LMS record only and
# touches no sms_ table, so a family asking what the school holds about their
# child previously received course trails and nothing else. Deliberately NOT
# behind a feature toggle: a subject-access right cannot be switched off.
v1_router.include_router(
    sms_data_subject.router,
    prefix="/sms/data-subject",
    tags=["sms-data-subject"],
)

# CSG School Settings -- the operator layer. Grading scales and fee policy
# were hardcoded Python constants, so a school on a different scale needed a
# developer. Deliberately NOT behind a feature toggle: this is where toggles
# are administered, and gating it behind one creates a state a school cannot
# get out of without a database client.
v1_router.include_router(
    sms_settings.router,
    prefix="/sms/settings",
    tags=["sms-settings"],
)

# M01 Admissions -- the application lifecycle (applications, supporting
# documents, assessments, decisions). Distinct from RevOps, which is the LEAD
# funnel: this is what happens once a family actually applies. Holds children's
# identity and medical documents, so its router admits no TEACHER at all.
v1_router.include_router(
    sms_admissions.router,
    prefix="/sms/admissions",
    tags=["sms-admissions"],
)

# M47 Parental consent for a minor's AI use. Deliberately NOT behind a feature
# toggle: this is the control that governs whether children's words may be sent
# to a third-party LLM at all, and a school must never be able to switch off
# the surface that records it.
v1_router.include_router(
    sms_ai_consent.router,
    prefix="/sms/ai-consent",
    tags=["sms-ai-consent"],
)

# M30 RevOps Admin Config + M34 Knowledge Base -- the operator layer for the
# admissions funnel. Lead scoring weights, nurture cadence and consent policy
# were hardcoded Python constants, so a school could not change what
# "qualified" means for its own intake without a developer. Deliberately NOT
# behind a feature toggle, matching sms_settings: gating the controls behind
# the thing they control creates a state a school cannot escape.
v1_router.include_router(
    sms_revops_config.router,
    prefix="/sms/revops-admin",
    tags=["sms-revops-admin"],
)

# M04 School examinations. Mounted next to the gradebook because that is where
# exam marks end up: posting results writes ordinary GradebookEntry rows rather
# than grading independently, so there is still exactly one grading engine.
v1_router.include_router(
    sms_exam.router,
    prefix="/sms/exams",
    tags=["sms-exams"],
)
v1_router.include_router(
    sms_exam.router,
    prefix="/ems/academic/exams",
    tags=["ems-academic-exams"],
)


v1_router.include_router(
    sms_fees.router,
    prefix="/sms/fees",
    tags=["sms-fees"],
)

# Payment-provider callbacks. Mounted WITHOUT the fees router's feature/auth
# dependency: a provider webhook carries no user principal and authenticates
# by a signature over the raw body instead. See routers/sms_fee_webhooks.py.
v1_router.include_router(
    sms_fee_webhooks.router,
    prefix="/sms/fee-payments",
    tags=["sms-fee-payments"],
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
    live_class_webhooks.router,
    prefix="/live",
    tags=["live-classes"],
    # Deliberately NOT gated by require_authenticated_user_or_api_token like
    # live_classes.router above -- this is called by the LiveKit media
    # server itself (no Learnhouse session, no API token). Its own handler
    # verifies the LiveKit-signed request instead; see
    # routers/live_class_webhooks.py and security/csrf.py's matching
    # path-based CSRF exemption for this same route.
)

# Live-class telemetry -> school attendance register. Carries its own
# per-handler require_roles, so it is not double-gated at the mount.
v1_router.include_router(
    sms_live_class_attendance.router,
    prefix="/live",
    tags=["live-classes"],
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

# AI RevOps agents (M23 research, M25 marketing, M26 copywriting). Same
# `/revops` prefix as the CRM above, with every route under `/agents/...` so
# there is no path collision with the 16 CRM endpoints. Feature gating lives
# inside the router (require_revops_feature), not here, matching sms_revops
# and avoiding the double-auth-gate bug documented above.
v1_router.include_router(
    revops_agents.router,
    prefix="/revops",
    tags=["revops-agents"],
)

# Automated Matriculation Handshake, BANT Qualification & Curriculum RAG
v1_router.include_router(
    sms_matriculation.router,
    prefix="/sms",
    tags=["sms-matriculation"],
)
v1_router.include_router(
    sms_matriculation.router,
    prefix="/revops",
    tags=["sms-matriculation"],
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

v1_router.include_router(
    sms_cognia.router,
    prefix="/sms/cognia",
    tags=["sms-cognia"],
)

# M32 Disciplinary Incident Tracking
v1_router.include_router(
    sms_discipline.router,
    tags=["sms-discipline"],
)

# M33 Alumni Tracking
v1_router.include_router(
    sms_alumni.router,
    tags=["sms-alumni"],
)

# M16 Certificate PDF Generator & Verification
v1_router.include_router(
    sms_certificates.router,
    tags=["sms-certificates"],
)

# M20 Gamification, Badges & Leaderboards
v1_router.include_router(
    sms_gamification.router,
    tags=["sms-gamification"],
)

# M38 Campus Events & Facility Booking
v1_router.include_router(
    sms_events_facilities.router,
    tags=["sms-events-facilities"],
)

# M13 Curricular Pathways & Bundles
v1_router.include_router(
    sms_pathways.router,
    tags=["sms-pathways"],
)

# Domain 1: Campuses & Classrooms. The router carries its own /sms/facilities
# prefix, matching sms_events_facilities (a different module: venue booking).
v1_router.include_router(
    sms_facilities.router,
    tags=["sms-facilities"],
)

# Curriculum Masters: Programs (boards/qualifications) and Syllabus Topics.
# The router carries its own prefix (/sms/curriculum) and per-handler Keycloak
# role gates, so it is mounted bare -- same shape as sms_pathways.
v1_router.include_router(
    sms_curriculum.router,
    tags=["sms-curriculum"],
)

# M36 Hostel & Dormitory. The router was written, tested and campus-scoped but
# never mounted, so all 19 endpoints were unreachable over HTTP. Its own
# APIRouter already carries require_sms_hostel_feature.
v1_router.include_router(
    sms_hostel.router,
    prefix="/sms/hostel",
    tags=["sms-hostel"],
)

# M34 Inventory & Procurement. Same: 20 endpoints, never mounted.
v1_router.include_router(
    sms_inventory.router,
    prefix="/sms/inventory",
    tags=["sms-inventory"],
)

# M35 Transport Fleet & Routes. No sms_transport entry exists on AdminToggles,
# so unlike hostel/inventory this router mounts without a feature-flag
# dependency.
v1_router.include_router(
    sms_transport.router,
    prefix="/sms/transport",
    tags=["sms-transport"],
)

# CSG-EMS Dynamic RBAC & Role Management
v1_router.include_router(
    ems_roles.router,
)

# CSG-EMS Academic Curricular Bridge & Section-Subject Mapping
v1_router.include_router(
    sms_section_subjects.router,
)

# CSG-EMS Document Engine, Institutional Branding & Audit Trail
v1_router.include_router(
    sms_documents.router,
)

# CSG-EMS Universal Audited Data Export Engine
v1_router.include_router(
    sms_exports.router,
    prefix="/sms/exports",
    tags=["sms-exports"],
)




