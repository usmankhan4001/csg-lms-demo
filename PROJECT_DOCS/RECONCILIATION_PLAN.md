# Reconciliation Plan — Requirements vs. Current System

How the system was taken from its audited state to the "full-fledged" target
described in the two requirement documents. Every row was verified against code,
not inferred from documentation.

**Status: Phases 0–5 complete.** Six commits, `839a21a` → `11373c8`. Section 5
records what is still open.

**Source documents being reconciled:**

- `final_research_report_enterprise_sms_architecture.md` — 4 business domains, 5
  handshakes, dynamic RBAC, AI ROI matrix, §7 action plan.
- `PROJECT_DOCS/09_EXPANDED_SYSTEM_ARCHITECTURE_AND_LIVE_CLASSES.md` — LiveKit SFU
  media service, end-to-end live class flow, classroom UI, live-class schema.

**Why this document exists:** both requirement documents were written against a
hypothetical stack. The research report names `apps/core` (NestJS) and
`packages/database/src/schema/academics.ts`; the live-classes doc names
`MultiTenantBase`, `student_batches`, `instructors`, `students` and
`course_schedules`. **None of these exist.** Executing either document literally
would have built the wrong thing in the wrong place. Both documents now carry
reconciliation notes pointing here.

> **Read this before planning work.** Several claims in both source documents were
> false for the code — most importantly the research report's central claim that
> the academic backbone was "completely missing". It was already built. Believing
> otherwise would have wasted an entire phase.

---

## 1. Reconciliation — Doc A: Enterprise SMS architecture

| Requirement | Doc claims | State at audit | Now |
|---|---|---|---|
| Academic backbone (years, terms, campuses, sections, enrolment) | "Completely missing" | Already built in `db/sms_campus.py` | ✅ Satisfied — **doc was wrong** |
| Handshake #1 — Matriculation | Broken | Already built | ✅ Satisfied |
| Handshake #2 — Fee schedule from enrolment | Broken | Already built | ✅ Satisfied |
| Handshake #3 — Roster-backed attendance | Broken | Never checked enrolment | ✅ **Fixed** — validates active enrolment, scoped to the section's academic year |
| Handshake #4 — Weighted assessment plans | Broken | Already built | ✅ Satisfied |
| Handshake #5 — Grounded AI tutor | Broken | Already built | ✅ Satisfied |
| Dynamic RBAC | Build it | Built, **0 call sites** | ✅ **Wired** — EMS assignments merged into the principal; `require_permission` gates fees, payroll, counselling, admissions, exports |
| Programs / syllabus topics | Missing | Absent | ✅ **Added** — `Program` + `SyllabusTopic` (`db/sms_curriculum.py`) |
| Campuses / classrooms | Missing | No Room entity | ✅ **Added** — `Classroom` with a required capacity |
| Transport fleet & routes | Domain 4 | Not built | ✅ **Built** — vehicles, routes, stops, assignments |
| AI timetable constraint solver | ROI item | Advisory, bypassable | ⚠️ **Partially** — clash bypass removed and slot uniqueness enforced in the database; the solver itself is still not built |
| Dropout / absenteeism early warning | ROI item | Counted recorded dates | ✅ **Fixed** — streaks break on gaps over a day |
| Substitute matcher | ROI item | `sms_timetable_substitution` exists | ⚠️ Partial |
| Enterprise event bus (RabbitMQ / outbox) | Infra | `arq`, no worker deployed | ⚠️ **Different by design** — `arq` retained, worker now deployed. No outbox |
| Keycloak identity | Infra | Dormant HMAC path | ✅ **Closed** — secret no longer defaults to a published value; HS256 refuses when unconfigured |
| Row-level security | Infra | No RLS, ~59 tables unscoped | ⚠️ **Partial** — `org_id`/`campus_id` added to the five most sensitive tables with a backfill; RLS not enabled, write paths not yet stamping |
| §7 file paths | `apps/core`, `packages/database` | Do not exist | ❌ Wrong stack — superseded by this plan |

## 2. Reconciliation — Doc B: Live classes

| Requirement | Doc claims | State at audit | Now |
|---|---|---|---|
| Dedicated LiveKit SFU | Required | Deployed | ✅ Satisfied |
| FastAPI as token issuer | Required | Working | ✅ Satisfied |
| **"Verifies student enrollments"** | Required | Authentication only | ✅ **Met** — host or active `StudentEnrollment` in the section, plus org/campus scope |
| Hocuspocus whiteboard | Required | Collab live, no in-class surface | ✅ **Built** — see caveat in §5 |
| **LiveKit Egress** | Required | No service anywhere | ✅ **Deployed** in both compose files |
| Composite recording → object storage | Required | Metadata only | ✅ **Implemented** — `room_started` dispatches, `egress_ended` persists |
| Recording → LMS chapter | Required | No linkage | ✅ **Linked** via `activity → chapter → course` |
| **Attendance from active minutes (≥80%)** | Advantage #3 | Not implemented | ✅ **Implemented** — explicit trigger with a preview, never overwrites a mark it did not write |
| Server-verified webhooks | Implied | Already correct | ✅ Exceeds the spec |
| Video-first grid + sidebar UI | Required | Leave links 404 | ✅ **Fixed** — `/dash` vs `/my-school`, derived from access level |
| Polls / Q&A | Required | Absent | ✅ **Built** — 5 tables, 10 endpoints |
| Schema names, `MultiTenantBase`, FK targets | Proposed | Do not match | ✅ **Reconciled** — doc annotated with the real mapping |

---

## 3. Reconciliation decisions — where doc and code disagreed

| Conflict | Decision |
|---|---|
| Doc B table names vs `sms_live_class_*` | **Code wins.** Doc annotated; no renaming |
| Doc B FKs to non-existent tables | **Mapped** to `class_section`, `user` + `StaffProfile`, `StudentEnrollment`, `sms_timetable_schedule` |
| `MultiTenantBase` | **Dropped.** Explicit `org_id` / `campus_id`, matching the other 196 tables |
| Doc A RabbitMQ / outbox | **`arq` retained.** Four cron jobs do not justify a broker |
| Doc A Keycloak | **Not added.** Dormant path made fail-closed instead |
| Doc B Nginx | **Traefik retained** |
| Doc A "backbone missing" | **Doc amended** |

---

## 4. Phases — all complete

### Phase 0 — Security gates ✅

`POST /demo/seed-sms` (unauthenticated superadmin mint), `GET /ai/tutor/history`
(unauthenticated transcript read), the production HMAC bypass, live-class
authorization, the missing `arq` worker, and the missing `apitoken.scopes`
migration.

### Phase 1 — Documentation ✅

False claims corrected across twelve documents, including a fabricated 360-audit
blocker asserting no `alembic.ini` exists. Both requirement specs annotated.

### Phase 2 — Academic core ✅

`Classroom` with required capacity, `Program` + `SyllabusTopic`, transport,
database-enforced timetable uniqueness, attendance enrolment validation, and the
calendar-day streak fix.

### Phase 3 — Live classes ✅

Egress service and recording lifecycle, recording→course linkage, polls and Q&A,
leave-link and host-detection fixes, and the whiteboard.

### Phase 4 — RBAC and tenancy ✅

EMS roles merged into the principal; `require_permission` wired into the five
highest-risk routers alongside `require_roles`. `org_id`/`campus_id` added to fee
vouchers, attendance, gradebook entries, clinical notes and salary slips with an
idempotent backfill that leaves orphans null rather than guessing a tenant.

### Phase 5 — Navigation and dead code ✅

17 unreachable frontend files deleted. `school-modules.ts` became the single
source of truth with a `domain` field covering the four business domains; both
menus and the Ctrl+K registry now derive from it. Confidentiality gating fixed on
the counselling Sessions tab and the AI-tutor oversight surface.

---

## 5. What remains

### Security

1. **Keycloak realm export** — `deploy/keycloak/realm-export-csg-lms.json` still
   contains a hardcoded client secret and **six users sharing one password hash
   and salt**, including `superadmin@`. Committed to the repository. Highest
   priority.
2. **Tenant columns are not yet used.** Write paths do not stamp `org_id`, so new
   rows get null. RLS is **not** enabled and the schema is not ready for it until
   the ~20 call sites listed by the Phase 4 work are updated.
3. **`calculate_cronbach_alpha` still returns `0.0`** for degenerate input — the
   same fabrication shape as the point-biserial bug that was fixed, but
   `cronbach_alpha` is a non-optional `float` in the schema, so fixing it is an
   API-contract change.

### Known gaps

- Egress file size is parsed but not persisted (needs a migration)
- Whiteboard: the collab server caps a document at 10 users, and students who are
  not board members fail collab auth. A true per-session whiteboard needs a second
  document prefix in `apps/collab`
- 19 search entries have untranslated titles (`locales/en.json` has no keys)
- Module-level nav gates are still duplicated in a `SCHOOL_MODULE_NAV` table in
  each menu; they belong in `school-modules.ts`
- `/dash/admissions/campaigns` and `/dash/school-settings/setup` are reachable but
  are not tabs in `SCHOOL_MODULES`
- `docker-compose.livekit.yml` (local) has no Egress service
- Polls have no realtime fan-out and no un-upvote

### Pre-existing test failures

- 8 in `test_content_files_router.py` — Windows path-separator assertions
- 2 in `test_full_vision_pillars.py::TestCogniaAccreditationM16`

### Not verified

None of the frontend work has been observed running. Type-check passes, but the
sidebar, mobile panel, Ctrl+K and the whiteboard have not been loaded in a
browser.

---

## 6. Standing rules that applied throughout

- **Absence of data is never rendered as a value.** A metric without data is
  `null` with an explanation, never `0%`.
- **New columns require an Alembic migration.** `create_all` never ALTERs.
- **Confidential records enforce 404-never-403.**
- **Never trust the body for identity or privilege.**
