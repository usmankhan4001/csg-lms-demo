# 🔍 360° Production Readiness Audit — `learnhouse-dev`

**Date:** 2026-09-14  
**Auditor:** Antigravity Deep-Dive (code-level, not self-reported)  
**Verdict:** ⚠️ **NOT production-ready.** Solid prototype with real logic and good engineering discipline — but 4 critical blockers and ~12 significant gaps must be addressed before a real deployment.

> [!NOTE]
> **Corrections applied 2026-09-16.** Several findings in this audit were factually wrong when written and have been corrected in place, marked with ~~strikethrough~~ and a **Correction** note. **B4 (no Alembic migrations) is retracted outright** — it was one of the five blockers and it does not hold. Parts of **B2** and **B3** (missing LiveKit npm dependency; no LiveKit service in `dokploy-compose.yml`) are also retracted. The remaining blockers (B1 no real Keycloak, B3 no completed production deployment, B5 AGPLv3) stand. Counts in §2 and §G6 were stale and have been refreshed.

---

## Executive Summary

```
┌─────────────────────────────────────────────────────────────────┐
│                    PRODUCTION READINESS SCORE                   │
├──────────────────────────┬──────────────────────────────────────┤
│  Backend Logic & Auth    │  ████████░░  ~80%  (real, tested)   │
│  Frontend UI & UX        │  ███████░░░  ~70%  (functional)     │
│  Integration Coherence   │  ██████░░░░  ~60%  (gaps remain)    │
│  Deployment Readiness    │  ████░░░░░░  ~40%  (local only)     │
│  Mobile App              │  ████░░░░░░  ~40%  (scaffold only)  │
│  E2E / QA Coverage       │  █████░░░░░  ~50%  (mocked DB)      │
│  Security Hardening      │  ██████░░░░  ~60%  (auth done, etc) │
├──────────────────────────┼──────────────────────────────────────┤
│  OVERALL                 │  █████░░░░░  ~55-60%                │
└──────────────────────────┴──────────────────────────────────────┘
```

---

## 🚫 CRITICAL BLOCKERS (Must-Fix Before Any Real Deployment)

### B1. No Real Keycloak — Auth Runs on a Dev Bridge

- **Finding:** [school_principal.py](file:///d:/Apps/CSG%20Venture/learnhouse-dev/apps/api/src/security/school_principal.py) builds `KeycloakUserPrincipal` by looking up `SMSUserRole` from the **Learnhouse session** — it no longer needs a Keycloak JWT at all. But this means:
  - There is **no real OIDC identity provider** — Keycloak has never been deployed, and the realm-export JSON (`deploy/keycloak/realm-export-csg-lms.json`) has never been verified to import cleanly.
  - Password policies, MFA enforcement, account lockout, and SSO federation that a real Keycloak provides are **absent for SMS users**.
  - The `SMSUserRole` table is the only source of truth for "who is a TEACHER vs STUDENT" — it has no self-service provisioning UI; roles must be inserted via API or database.

> [!CAUTION]
> A real production deployment MUST either stand up Keycloak (as the wiki specifies) or build a proper role-provisioning admin UI on top of the current `SMSUserRole` model. The current system has no mechanism for a school administrator to self-service create teacher/student accounts with appropriate roles.

### B2. LiveKit Video Classrooms — Infrastructure Not Deployed

- **Finding:** The codebase has been **substantially upgraded** since the original `context.md` audit:
  - Backend: `livekit-api==1.2.1` is in [pyproject.toml](file:///d:/Apps/CSG%20Venture/learnhouse-dev/apps/api/pyproject.toml#L53). [live_classes.py](file:///d:/Apps/CSG%20Venture/learnhouse-dev/apps/api/src/routers/live_classes.py) router exists with real room lifecycle + token generation. [live_class_webhooks.py](file:///d:/Apps/CSG%20Venture/learnhouse-dev/apps/api/src/routers/live_class_webhooks.py) handles server-verified attendance from LiveKit events. There are **4 dedicated test files** for live classes.
  - Frontend: [LiveClassRoom.tsx](file:///d:/Apps/CSG%20Venture/learnhouse-dev/apps/web/modules/sms/live-class/components/LiveClassRoom.tsx) imports `@livekit/components-react` (`LiveKitRoom`, `VideoConference`) — **real WebRTC UI**, not a mock.
  - Compose: [docker-compose.livekit.yml](file:///d:/Apps/CSG%20Venture/learnhouse-dev/docker-compose.livekit.yml) exists as a **proper override file** with `livekit/livekit-server:v1.9.1`, ICE config, webhook wiring, etc.

- **BUT:** ~~`@livekit/components-react` and `@livekit/components-styles` are **NOT in `apps/web/package.json`** — the import will fail at build time.~~ **Correction (2026-09-16): incorrect.** All three packages are already declared in `apps/web/package.json` — `@livekit/components-react` `^2.9.24`, `@livekit/components-styles` `^1.2.0`, `livekit-client` `^2.22.3` — so the import resolves and there is no npm blocker. ~~No production LiveKit deployment exists in `dokploy-compose.yml`.~~ **Also incorrect:** `dokploy-compose.yml:264` defines a `livekit` service (`livekit/livekit-server:v1.9.1`) with a healthcheck and the `50200-50250/udp` media range.
- **Still true:** the LiveKit compose override has never been tested end-to-end, and `LIVEKIT_API_KEY` / `LIVEKIT_API_SECRET` deliberately have no committed fallback, so live classes fail closed unless they are set in the environment.

> [!WARNING]
> The LiveKit integration is ~85% code-complete and has never been run end-to-end. The previously-claimed **missing npm dependency blocker does not exist** — the packages are installed. The real remaining work is running it: `docker compose -f docker-compose.local.yml -f docker-compose.livekit.yml up --build` with real LiveKit credentials.

### B3. No Production Deployment Has Ever Completed

- **Finding:** [docker-compose.local.yml](file:///d:/Apps/CSG%20Venture/learnhouse-dev/docker-compose.local.yml) is the **only** path that has ever been run to completion. The production compose files (`docker-compose.prod.yml`, `dokploy-compose.yml`) have never been started. No Traefik TLS, no real domain, ~~no Keycloak service, no LiveKit service in production~~.

> [!NOTE]
> **Correction (2026-09-16).** The second half of that sentence was wrong. `dokploy-compose.yml:264` **does** define a `livekit` service. The Keycloak half is correct for that file — `dokploy-compose.yml` has no Keycloak; Keycloak is defined in `docker-compose.prod.yml:71` (`quay.io/keycloak/keycloak:26.1.0`) instead. Neither has been started.

> [!CAUTION]
> Nothing from this repo has been confirmed running on any server. The entire system is localhost-only validated.

### B4. ~~No Real Database Migrations (Alembic)~~ — RETRACTED (this was not a blocker)

> [!NOTE]
> **Correction (2026-09-16): this blocker was factually wrong and is retracted.** Alembic is fully wired up. `apps/api/alembic.ini` exists with `script_location = migrations`, and `apps/api/migrations/versions/` holds **77 revisions on a single head** (`c5d6e7f8a9b0`, which revises `f9a0b1c2d3e4`). The production entrypoint runs `alembic upgrade head` before starting uvicorn (`apps/api/docker-entrypoint.prod.sh:89-99`). The original finding searched for an `alembic/` directory; the real path is `migrations/`. The original text is kept below, struck through, so the audit's reasoning stays auditable.

- ~~**Finding:** `alembic==1.19.1` is a dependency, but I found no `alembic/versions/` migration folder or `alembic.ini` in the API source. The app relies on SQLModel/SQLAlchemy's `metadata.create_all()` at startup — which creates tables but **cannot handle schema changes** (adding columns, changing types, data migrations) for an existing production database.~~

> [!IMPORTANT]
> **What is still true.** The schema was, historically, built by `SQLModel.metadata.create_all()` rather than by migrations, because `alembic upgrade head` was failing on ten branched heads and the entrypoint swallowed the error (`apps/api/migrations/versions/a1c4e90d77b3_merge_ten_branched_heads.py`). The heads have since been merged and the database baselined. A fresh deployment should still be *verified* with `alembic current` / `alembic upgrade head` rather than assumed — the entrypoint's failure-swallowing is a real, separate risk.

### B5. AGPLv3 License Compliance

- **Finding:** The base is a fork of [Learnhouse](https://github.com/learnhouse/learnhouse) under **AGPLv3** ([LICENSE](file:///d:/Apps/CSG%20Venture/learnhouse-dev/LICENSE)). Per §13, if this is ever run as a network service accessible to users outside the dev team, the **complete source code** (including all CSG modifications) must be made available to those users.

> [!CAUTION]
> Deploying this to real school users as a proprietary SaaS would violate AGPLv3. Options: keep it fully open-source, get a commercial license from Learnhouse, or rewrite the non-original components on a permissive base.

---

## ✅ WHAT'S GENUINELY GOOD (Credit Where Due)

### 1. Backend Architecture & Code Quality — Solid

| Strength | Evidence |
|---|---|
| **Layered module structure** | Clean `routers/ → services/ → db/` separation across ~25+ SMS/AI modules |
| **Real business logic** | Gradebook: weighted GPA aggregation with grade history ([sms_gradebook.py](file:///d:/Apps/CSG%20Venture/learnhouse-dev/apps/api/src/services/sms/gradebook.py) — 39KB). Timetable: conflict detection + auto-generation ([timetable_generation.py](file:///d:/Apps/CSG%20Venture/learnhouse-dev/apps/api/src/services/sms/timetable_generation.py)). Fees: challan generation + reminders. Payroll: salary calculation + approval workflow. RevOps: lead scoring, SDR agent, drip engine, offer generator. AI Tutor: subject-scoped, guardrailed, mastery DAG pacing. |
| **Comprehensive test suite** | **200+ test files** across `tests/sms/`, `tests/ai/`, `tests/services/`, `tests/security/`, `tests/routers/` — covering SMS modules, AI services, security edge cases, and router mount correctness |
| **Auth is properly wired** | All 12+ SMS routers use `get_current_user_principal` (confirmed by examining [router.py](file:///d:/Apps/CSG%20Venture/learnhouse-dev/apps/api/src/router.py) lines 482-710 — the double-gate bug was identified AND fixed with a regression test) |
| **Per-org feature toggles** | Proper `FeatureName` literal type with `require_*_feature()` dependencies per router ([dependencies.py](file:///d:/Apps/CSG%20Venture/learnhouse-dev/apps/api/src/security/features_utils/dependencies.py)) |
| **Role-based access** | 7 school roles (`SUPER_ADMIN`, `SCHOOL_ADMIN`, `TEACHER`, `STUDENT`, `PARENT`, `STAFF`, `PSYCHOLOGIST`) with per-endpoint `require_roles()` enforcement. **Correction (2026-09-16):** these are **not** Keycloak realm roles — there is no Keycloak. They are the values of the `SchoolRole` enum in `apps/api/src/db/sms_identity.py:29-36`, granted per-user via `SMSUserRole` rows. The `KeycloakUserPrincipal.realm_roles` field is populated from those rows (`school_principal.py:188`). |
| **Event bus architecture** | In-process pub/sub ([event_bus.py](file:///d:/Apps/CSG%20Venture/learnhouse-dev/apps/api/src/core/event_bus.py)) for cross-module communication without tight coupling |
| **Superadmin impersonation** | Production-grade, audited QA tool ([school_principal.py](file:///d:/Apps/CSG%20Venture/learnhouse-dev/apps/api/src/security/school_principal.py#L36-L67)) with signed JWT cookies, 2-hour expiry, fail-safe decoding |

### 2. Frontend — Rich Dashboard Surface

| Area | Count | Examples |
|---|:---:|---|
| **Admin/Dash pages** | **88 page.tsx files** (was 73 when this audit was written) | Admissions CRM, attendance (bulk/digest/excuses/history/pastoral), exams (resits/seating), gradebook (report-cards, per-student), timetable (conflicts/generate/lessons), counseling (career), live-classes, revops (config/knowledge), school-settings, reports, financials, HR, payroll |
| **Learner pages** | **25 page.tsx files** | Courses, library, AI tutor, communities, playgrounds, podcasts, boards, certificates, search, trail |
| **Shared components** | **27 SMS module folders** (was 14 when this audit was written) | Each with `api.ts`, `types.ts`, and real interactive components (RollCallRoster, GradebookMatrix, AdmissionsCRMBoard, TimetableGrid, LiveClassRoom, etc.) |
| **API client** | Centralized | [api-client.ts](file:///d:/Apps/CSG%20Venture/learnhouse-dev/apps/web/lib/api/api-client.ts) — normalized error handling (`ApiError` with `kind` classification), automatic Bearer token attachment via session bridge, runtime config resolution |

### 3. Integration Coherence — Auth Flow Is Now Unified

The **biggest architectural win** since the original audit: the dual-auth nightmare (Learnhouse session vs. dev Keycloak JWT) has been **resolved**. The flow is now:

```
Browser → Learnhouse login (/login) → real session cookie 
    → AuthContext stores access token → session-token-bridge.ts
    → api-client.ts attaches Bearer token to SMS API calls
    → Backend: get_current_user (Learnhouse auth) 
    → school_principal.py resolves SMSUserRole from the real user
    → KeycloakUserPrincipal shape preserved for all 90+ SMS call sites
```

No separate `/dev-login`, no manual token minting, no localStorage JWT. This is a **clean, single-auth-system** now.

### 4. Upstream Learnhouse Features — All Intact

| Upstream Feature | Status | Notes |
|---|:---:|---|
| Course authoring (TipTap block editor) | ✅ Real | Fully functional content creation |
| Real-time collaboration (Hocuspocus/Yjs) | ✅ Real | Separate `apps/collab/` service, properly built in Dockerfile |
| Code execution sandboxes | ✅ Real | `code_execution.py` router |
| Assignments & grading | ✅ Real | **24 E2E Playwright tests** covering quiz, short-answer, file submission, manual grading, formative mode |
| SCORM import & player | ✅ Real | **4 E2E tests** + upstream frontend (`apps/web/ee/services/scorm/`) |
| Communities & discussions | ✅ Real | Full CRUD + moderation |
| Boards, playgrounds, podcasts | ✅ Real | All with plan-gated dependencies |
| Media upload (S3/R2) | ✅ Real | Full upload pipeline with file validation |
| Multi-language (i18n) | ✅ Real | RTL support with **3 dedicated E2E tests** |
| Analytics (Tinybird) | ✅ Real | With a mock service for local dev ([deploy/tinybird-mock/](file:///d:/Apps/CSG%20Venture/learnhouse-dev/deploy/tinybird-mock)) |
| RBAC, API tokens, webhooks | ✅ Real | Full implementation with plan-tier gating |
| MFA/2FA | ✅ Real | [mfa.py](file:///d:/Apps/CSG%20Venture/learnhouse-dev/apps/api/src/routers/mfa.py) — 32KB router |
| CSRF protection | ✅ Real | [csrf.py](file:///d:/Apps/CSG%20Venture/learnhouse-dev/apps/api/src/security/csrf.py) with path-based exemptions for webhooks |

---

## ⚠️ SIGNIFICANT GAPS (Non-Critical but Important)

### G1. Mobile App — Scaffold, Not Product

[apps/mobile/](file:///d:/Apps/CSG%20Venture/learnhouse-dev/apps/mobile) has:
- ✅ **Real navigation structure**: `RootNavigator` with persona-based tab navigation (Student, Teacher, Parent, Staff stacks)
- ✅ **Real screens built**: Student (Home, Timetable, Attendance, AI Coach, Assignments), Teacher (Today, Classes, RollCall, Gradebook), Parent (Home, Children, Fees, Messages), Staff (Today, Directory, Payroll, Tasks)
- ✅ **API client layer**: Typed modules for attendance, campus, fees, gradebook, identity, messages, payroll, timetable
- ❌ **No offline sync**: WatermelonDB + `/v1/core/sync/delta` not implemented
- ❌ **No push notifications**: FCM integration absent
- ❌ **Never tested on a real device**: No CI/CD for mobile builds

### G2. Tests Run Against Mocked DB — No Integration Tests

All 200+ pytest tests use mocked `AsyncSession` objects, not a real Postgres instance. This means:
- Schema correctness (foreign keys, constraints, indexes) is untested
- Multi-tenant RLS isolation is untested
- Real async query behavior (deadlocks, transaction rollbacks) is untested
- The **E2E Playwright suite** (assignments + SCORM + RTL) is the only real integration path, and it only covers upstream Learnhouse features, not CSG SMS modules

### G3. Missing CSG Modules (16 from Original Spec)

> [!NOTE]
> **Correction (2026-09-16).** "Remain unbuilt" was wrong for 8 of the 14 modules listed below. All 8 now have routers mounted in `apps/api/src/router.py:765-815`. Five also have real UI; three are API-only with no frontend yet. The table is annotated per row; the 6 genuinely-absent modules are unchanged.

These were identified as fabricated in the original audit:

| Module | Name | Status (verified 2026-09-16) | Effort Estimate |
|---|---|---|---|
| M13 | Course Bundling & Curricular Pathways | ✅ **Built** — router mounted (`router.py:795`), UI at `/dash/pathways` | Medium |
| M15 | Plagiarism Detection | ❌ Still absent — no router, no UI | Large (needs 3rd-party or ML) |
| M16 | Certificate PDF Generator (backend) | ✅ **Built** — router mounted (`router.py:777`), UI at `/dash/certificates-manager` | Small-Medium |
| M20 | Gamification, Badges & Leaderboards | ✅ **Built** — router mounted (`router.py:783`), UI at `/dash/gamification` | Medium |
| M32 | Disciplinary Incident Tracking | ✅ **Built** — router mounted (`router.py:765`), UI at `/dash/discipline` | Small |
| M33 | Alumni Tracking | ✅ **Built** — router mounted (`router.py:771`), UI at `/dash/alumni` | Small |
| M34 | Inventory & Procurement | ⚠️ **Partial** — router mounted (`router.py:811`), **no UI** | Medium |
| M35 | Transport & Fleet GPS | ❌ Still absent — no router, no UI | Large |
| M36 | Hostel & Dormitory | ⚠️ **Partial** — router mounted (`router.py:804`), **no UI** | Medium |
| M37 | Cafeteria POS & Smart Cards | ❌ Still absent — no router, no UI | Large |
| M38 | Event Management & Facility Booking | ⚠️ **Partial** — router mounted (`router.py:789`), **no UI** | Medium |
| M41 | Real-Time Lecture Translation | ❌ Still absent — no router, no UI | Large (needs streaming ASR+TTS) |
| M46 | Automated Homework Grading | ❌ Still absent — no router, no UI | Medium-Large |
| M49 | Dropout Predictor | ❌ Still absent — no router, no UI | Medium (needs historical data + ML) |

### G4. No Postgres RLS (Row-Level Security)

The wiki mandates tenant isolation via Postgres RLS keyed on `organization_id` from the verified JWT claim. The actual implementation uses **application-level filtering** (`WHERE organization_id = :org_id` in queries). This works but:
- A bug in any single query can leak cross-tenant data
- There is no database-level safety net
- It differs materially from the wiki's architectural spec

### G5. No Observability Stack

The wiki specifies OpenTelemetry. The codebase has:
- ✅ Sentry SDK (`sentry-sdk[fastapi]==2.68.1`) for error tracking
- ❌ No OpenTelemetry traces, metrics, or logs
- ❌ No structured logging framework
- ❌ No health dashboard beyond the basic `/health` endpoint

### G6. Proxy.ts Routing Fragility

[proxy.ts](file:///d:/Apps/CSG%20Venture/learnhouse-dev/apps/web/proxy.ts) (Next.js 16's middleware) is **639 lines** of routing rules (was 632 when this audit was written). Any new top-level CSG route that isn't explicitly listed in its passthrough set will 404. The `ROLE_PORTAL_PATHS` mapping (line 274-279) now correctly routes to `/my-school` and `/dash` (matching the Learnhouse shell split), but:
- Adding new portal paths requires editing proxy.ts
- ~~No automated test validates these routing rules~~ **Correction (2026-09-16): partly incorrect.** `apps/web/tests/unit/proxy.test.ts` does exercise `proxy()` directly, including all four `ROLE_PORTAL_PATHS` redirects (§0b). What is still true: it covers the role-portal redirects only — the passthrough set and the rewrite rules are untested.
- The interaction between proxy.ts rewrites and Next.js route groups is subtle and error-prone

---

## 📊 User Flow Audit

### Flow 1: Login → SMS Dashboard (Admin)

```
✅ /login → Learnhouse native auth → session cookie
✅ proxy.ts reads LH_role cookie → redirects to /dash
✅ /dash renders org admin dashboard (Learnhouse's built-in)
✅ Sidebar shows SMS modules (attendance, timetable, gradebook, fees, etc.)
✅ Each module page calls api-client.ts → Bearer token → backend
✅ Backend resolves school_principal → enforces role access
```

**Verdict:** ✅ This flow works end-to-end in Docker.

### Flow 2: Teacher → Roll Call → Grade Entry

```
✅ Teacher logs in → LH_role=TEACHER → /dash
✅ /dash/attendance → RollCallRoster component → POST /sms/attendance/sessions
✅ /dash/gradebook → GradebookMatrix → grade entry with weighted GPA
✅ /dash/gradebook/report-cards → ReportCardPanel → draft/publish lifecycle
```

**Verdict:** ✅ Backend logic is real and tested. UI components exist. Needs real demo data to validate visually.

### Flow 3: Parent → Check Fees → Check Child's Grades

```
✅ Parent logs in → LH_role=PARENT → /my-school
✅ /my-school → calls GET /sms/me → returns children_ids
✅ Fee checking: modules/sms/fees/ → PayVoucherDialog
✅ Child context: useSchoolSession + getChildContext(studentId) per child
```

**Verdict:** ✅ Flow is architecturally sound. Guardian→child linkage uses `StudentGuardian` DB model.

### Flow 4: Live Video Class (Teacher Starts → Student Joins)

```
✅ Teacher dashboard → "Start Live Class" → POST /live/rooms
✅ Token generation → livekit-api creates real LiveKit token
✅ Frontend imports @livekit/components-react — dependency IS in package.json (corrected 2026-09-16)
⚠️ LiveKit server not in the local compose — requires the override file (it IS in dokploy-compose.yml:264)
❌ Never tested end-to-end
```

**Verdict:** ❌ 85% code-complete and never run end-to-end. **Correction (2026-09-16):** it will *not* fail at npm build — the LiveKit packages are declared in `apps/web/package.json`. The blocker is verification, not a missing dependency.

### Flow 5: AI Tutor Conversation

```
✅ Student navigates to /ai-tutor (or org-scoped equivalent)
✅ Backend: socratic_tutor.py (27KB) with subject scoping, age guardrails, mastery DAG
✅ Content guardrails (content_guardrails.py, 10KB) + crisis classifier (13KB)
✅ Redis rate limiting on tutor sessions
✅ Knowledge graph (concept prerequisites, per-grade RAG segregation)
```

**Verdict:** ✅ This is one of the most complete features — real LLM integration via OpenRouter/Gemini.

### Flow 6: Admissions CRM Pipeline

```
✅ /dash/admissions → AdmissionsCRMBoard (Kanban drag-drop)
✅ Lead detail → LeadDetailDialog with scoring, notes, stage transitions
✅ /dash/admissions/applications → NewApplicationDialog
✅ /dash/revops/config → lead scoring weights, nurture cadence
✅ /dash/revops/knowledge → knowledge base management
✅ Backend: 8 AI services (lead scoring, SDR agent, drip engine, etc.)
```

**Verdict:** ✅ Full pipeline from lead capture to enrollment. Visual Flow Builder (drag-drop campaign routing) is **not started**.

---

## 🏗️ Deployment Architecture Assessment

### What Exists

| Artifact | Status | Notes |
|---|:---:|---|
| [Dockerfile](file:///d:/Apps/CSG%20Venture/learnhouse-dev/Dockerfile) | ✅ Real | Multi-stage (5 stages), Alpine-based, non-root user, proper layer caching |
| [docker-compose.local.yml](file:///d:/Apps/CSG%20Venture/learnhouse-dev/docker-compose.local.yml) | ✅ Tested | Postgres + Redis + API + Web + Tinybird-mock. Only path run to completion. |
| [docker-compose.livekit.yml](file:///d:/Apps/CSG%20Venture/learnhouse-dev/docker-compose.livekit.yml) | ⚠️ Exists | Proper LiveKit override file, never run |
| docker-compose.prod.yml | ⚠️ Exists | Defines Keycloak service, never started |
| dokploy-compose.yml | ⚠️ Exists | Production artifact, never deployed |
| deploy/keycloak/realm-export | ⚠️ Exists | Never imported into a running Keycloak |
| deploy/scripts/healthcheck.py | ✅ Exists | Basic health check |

### What's Missing for Production

1. **TLS termination** — Traefik labels exist in compose but never tested with real certs
2. **Database backups** — ~~No backup strategy, no pg_dump cron~~ **Correction (2026-09-16): incorrect.** `scripts/backup.sh` (verified, compressed, retention-pruned `pg_dump`), `scripts/restore.sh`, `scripts/backup_postgres.py` and `scripts/backup_postgres.sh` all exist, and [BACKUP_RESTORE.md](./BACKUP_RESTORE.md) documents a restore verified on 2026-09-13 plus a sample cron entry. What is still true: **no schedule is actually installed anywhere** — the cron line is documentation, not a running job.
3. **Log aggregation** — No ELK/Loki/CloudWatch integration
4. **CI/CD pipeline** — ~~No GitHub Actions or Azure Pipeline for automated testing + deployment~~ **Correction (2026-09-16): incorrect.** `.github/workflows/` contains 10 workflows, including `api-tests.yaml`, `e2e.yaml`, `web-lint.yaml`, `api-lint.yaml`, `cli-tests.yaml`, `cli-publish.yaml`, `release.yaml`, `build-community.yaml`, `lockfiles.yaml` and `notify-infra.yaml`. What is still true: none of them **deploy** — there is no CD job.
5. **Environment secret management** — API keys in compose env vars, not a vault
6. **Rate limiting at the edge** — Redis rate limiting exists for AI tutor only, not API-wide
7. **CDN / media storage** — S3/R2 configuration exists but is untested in production

---

## 📋 Prioritized Action Plan

### Phase 0: Minimum Viable Deployment (1-2 weeks)

- [x] ~~Install `@livekit/components-react @livekit/components-styles livekit-client` in `apps/web/`~~ — already present in `apps/web/package.json`; nothing to install (corrected 2026-09-16)
- [ ] Run full `docker compose -f docker-compose.local.yml -f docker-compose.livekit.yml up --build` and verify video classrooms work
- [ ] Create an SMS role-provisioning admin UI (or CLI script) so a school admin can assign TEACHER/STUDENT/PARENT roles without touching the database
- [ ] ~~Set up Alembic migrations for the existing schema~~ — already set up: 77 revisions, single head `c5d6e7f8a9b0`, `alembic upgrade head` runs in the entrypoint (corrected 2026-09-16). Replace with: verify `alembic upgrade head` succeeds against a clean database and that the entrypoint no longer swallows migration failure.
- [ ] Run the full pytest suite: verify current pass rate, fix any regressions
- [ ] Seed demo data for a realistic school (50 students, 10 teachers, 3 sections, term schedule, fee plans)

### Phase 1: Production Hardening (2-4 weeks)

- [ ] Deploy with `docker-compose.prod.yml` on a real Hetzner/Dokploy server
- [ ] Stand up Keycloak and verify the realm export imports cleanly
- [ ] Add TLS via Traefik + Let's Encrypt
- [ ] Set up automated database backups
- [ ] Configure Sentry for both API and web error tracking
- [ ] Add basic health monitoring (uptime checks)

### Phase 2: Quality & Completeness (4-8 weeks)

- [ ] Build E2E Playwright tests for SMS flows (attendance, gradebook, fees)
- [ ] Add integration tests against a real Postgres (not mocked DB)
- [ ] ~~Build the 5 smallest missing modules (M32 Discipline, M33 Alumni, M16 Certificates, M13 Course Bundling, plus Visual Flow Builder)~~ — **Correction (2026-09-16):** M32, M33, M16 and M13 are all built and mounted (see G3). Remaining work here is the Visual Flow Builder, UI for the three API-only modules (M34 Inventory, M36 Hostel, M38 Events), and the 6 genuinely-absent modules.
- [ ] Mobile: test on real iOS/Android devices, fix platform-specific issues
- [ ] Add structured logging and basic OpenTelemetry traces

---

> [!IMPORTANT]
> **Bottom line:** This is a **serious, well-engineered prototype** with ~25 working backend modules, 88 dashboard pages, a clean auth unification, and a disciplined testing culture. It is NOT production-ready primarily because (1) no deployment has ever completed, (2) there is no real identity provider (no Keycloak — roles live in `SMSUserRole` with no self-service provisioning UI), and (3) the AGPLv3 license creates legal risk for commercial use.
>
> **Correction (2026-09-16):** two of the four reasons originally given here were wrong and have been removed. The LiveKit frontend dependency is **not** missing (it is in `apps/web/package.json`), and database migration management **does** exist (77 Alembic revisions, single head, run by the container entrypoint). Addressing the Phase 0 items above would get this to a **demonstrable MVP** suitable for internal demos and pilot testing.
