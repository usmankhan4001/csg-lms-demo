# Reconciliation Plan — Requirements vs. Current System

How to take the system from its current state to the "full-fledged" target described
in the two requirement documents. Every row below was verified against code, not
inferred from documentation.

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
would build the wrong thing in the wrong place. This plan maps both onto the real
codebase.

> **Read this before planning work.** Several claims in both source documents are
> false for the current code — most importantly the research report's central claim
> that the academic backbone is "completely missing". It is built. Believing
> otherwise would waste an entire phase.

---

## 1. Reconciliation — Doc A: Enterprise SMS architecture

| Requirement | Doc claims | Actual state | Verdict |
|---|---|---|---|
| Academic backbone (years, terms, campuses, sections, enrolment) | "Completely missing" | `Campus`, `AcademicYear`, `AcademicTerm`, `ClassSection`, `StudentEnrollment` in `apps/api/src/db/sms_campus.py` | ✅ Satisfied — **doc is wrong** |
| Handshake #1 — Matriculation | Broken | `services/sms/matriculation.py`: users, roles, guardian link, enrolment, vouchers | ✅ Satisfied |
| Handshake #2 — Fee schedule from enrolment | Broken | Same handshake generates vouchers | ✅ Satisfied |
| Handshake #3 — Roster-backed attendance | Broken | `services/sms/attendance.py` never references `StudentEnrollment` | ⚠️ **Real gap** |
| Handshake #4 — Weighted assessment plans | Broken | `AssessmentPlan`, `GradingScale`, `GradebookEntry.weighted_score`, `TermReportCard` | ✅ Satisfied |
| Handshake #5 — Grounded AI tutor | Broken | `services/ai/socratic_tutor.py` is enrolment-scoped | ✅ Satisfied |
| Dynamic RBAC | Build it | `security/ems_rbac.py` complete and tested — **0 call sites** | ⚠️ **Built, unwired** |
| Programs / syllabus topics | Missing | No `Program`, no syllabus topics. Curriculum = Learnhouse `Course` + `SectionSubject` + `PathwayCourse` | ⚠️ Partial |
| Campuses / classrooms | Missing | `Campus` exists. **No Room/Classroom entity anywhere** | ⚠️ **Room missing** |
| Transport fleet & routes | Domain 4 | Not built | ❌ Missing |
| AI timetable constraint solver | ROI item | Conflict detection advisory, bypassable via `?enforce_no_clash=false`, no DB constraint | ❌ **Blocked on Room** |
| Dropout / absenteeism early warning | ROI item | Streak detector exists but counts *recorded dates*, not calendar days | ⚠️ Buggy |
| Substitute matcher | ROI item | `sms_timetable_substitution` exists | ⚠️ Partial |
| Enterprise event bus (RabbitMQ / outbox) | Infra | `arq` + Redis. No outbox. M32 not built | ❌ Missing (differently) |
| Keycloak identity | Infra | Not used. The **dormant HMAC path is the live production path** | ❌ Contradicted |
| Row-level security | Infra | No RLS. **90 tables have neither `org_id` nor `campus_id`** | ❌ Missing |
| §7 file paths | `apps/core`, `packages/database` | Do not exist | ❌ Wrong stack |

## 2. Reconciliation — Doc B: Live classes

| Requirement | Doc claims | Actual state | Verdict |
|---|---|---|---|
| Dedicated LiveKit SFU | Required | `livekit` service in `dokploy-compose.yml:166`; `docker-compose.livekit.yml` with ICE fix; `livekit-api` + React SDKs present | ✅ Satisfied |
| FastAPI as token issuer | Required | `routers/live_classes.py` mints tokens; `is_teacher` derived server-side | ✅ Satisfied |
| **"Verifies student enrollments"** | Required | `POST /live/rooms/{room_name}/token` gated by **authentication only** — any user joins any room at any school | ❌ **Explicitly not met** |
| Hocuspocus whiteboard | Required | Collab service live on 4000 | ✅ Satisfied |
| **LiveKit Egress** | Required | **No egress service in any compose file** | ❌ Missing |
| Composite recording → object storage | Required | `RecordingStatus`, `SetRecordingRequest`, `ShareRecordingRequest` — **metadata only, no recorder** | ❌ Missing |
| Recording → LMS chapter | Required | `sms_live_class_coursework` exists | ⚠️ Partial |
| **Attendance from active minutes (≥80% = Present)** | Advantage #3 | `LiveClassAttendanceLog.duration_minutes` exists. **No percentage, no threshold, no bridge to `StudentAttendance`** | ❌ Missing |
| Server-verified webhooks | Implied | `routers/live_class_webhooks.py` verifies the LiveKit signature — **better than the doc's design** | ✅ Exceeds |
| Video-first grid + sidebar UI | Required | `apps/web/app/live/[roomId]/page.tsx` exists; "Leave" links to `/teacher` / `/student`, which **404** | ⚠️ Partial |
| Polls / Q&A | Required | Not found | ❌ Missing |
| Schema `live_classes` / `live_attendance_logs` / `live_recordings` | Proposed | `sms_live_class_session` / `_attendance` / `_detail` / `_coursework` | ⚠️ Different names |
| FKs to `student_batches`, `instructors`, `students`, `course_schedules` | Proposed | **None of those tables exist** | ❌ Wrong schema |
| `MultiTenantBase` | Proposed | **Does not exist anywhere in `src/`** | ❌ Wrong |
| Ports 8000 / 9000 / 4000 / 7880 | Proposed | api 9000 ✓, collab 4000 ✓, livekit 7880 (published 7883) | ✅ Mostly matches |
| Next.js 16 + React 19 | Proposed | `next: ^16.2.9` ✓ | ✅ Satisfied |
| PM2, 6 processes | Proposed | `docker/start.sh` runs web/api/collab — **no livekit, no egress** | ⚠️ Partial |
| Nginx gateway | Proposed | Traefik via Dokploy | ⚠️ Different |

---

## 3. Reconciliation decisions — where doc and code disagree

| Conflict | Decision | Rationale |
|---|---|---|
| Doc B table names vs `sms_live_class_*` | **Code wins.** Amend the doc. | Renaming live tables buys a migration for no benefit |
| Doc B FKs to non-existent tables | **Map to real entities:** `class_section`, `user` + `StaffProfile`, `StudentEnrollment`, `sms_timetable_schedule` | Those tables should not be created |
| `MultiTenantBase` | **Drop it.** Use explicit `org_id` / `campus_id` | Matches the other 196 tables; a base class would be the only one |
| Doc A RabbitMQ / outbox | **Keep `arq`.** Do not add a broker | Four cron jobs do not justify a broker. The real gap is that no worker is deployed |
| Doc A Keycloak | **Do not add it.** Delete the dormant HMAC path and make auth fail closed | It authenticates nothing and is currently the production auth bypass |
| Doc B Nginx | **Keep Traefik** | Already the ingress; swapping is churn |
| Doc A "backbone missing" | **Amend the doc** | It is built |

---

## 4. Phased plan

### Phase 0 — Security gates (blocks everything)

Nothing below is safe until these close. Live classes especially: Doc B's core
security requirement is unmet, so scaling the feature scales the hole.

| # | Deliverable | Path |
|---|---|---|
| 0.1 | Gate `POST /demo/seed-sms` — currently mints a platform superadmin with a known password, unauthenticated | `apps/api/src/routers/demo.py:176-186` |
| 0.2 | Authenticate + ownership-check `GET /ai/tutor/history` | `apps/api/src/routers/ai_tutor.py:331-341` |
| 0.3 | Make authentication fail closed in production; remove the token-minting script from the image | `apps/api/src/core/keycloak_auth.py`, `.dockerignore` |
| 0.4 | Live-class authorization: caller must be the session teacher, a host, or enrolled in `live_session.section_id`. Org/campus-scope `GET /live/rooms/active` and `GET /live/classes/{id}` | `apps/api/src/routers/live_classes.py` |
| 0.5 | Deploy the `arq` worker — without it no scheduled job in either document runs | `dokploy-compose.yml`, `docker-compose.prod.yml`, `docker/start.sh` |
| 0.6 | Add the missing `apitoken.scopes` migration — token auth 500s on every deployed DB | `apps/api/migrations/versions/` |

**Gate:** no unauthenticated or cross-tenant path remains reachable; the worker is
deployed and its heartbeat observable.

### Phase 1 — Make the documents true

Amend both source documents to match the code: correct the "backbone missing"
claim, the live-class schema names, the FK targets, drop `MultiTenantBase`, drop
RabbitMQ and Keycloak. Also correct the stale claims already found in
`ARCHITECTURE.md`, `STATUS.md`, `KNOWN_GAPS.md` and `360_AUDIT_REPORT.md` (that
last one asserts no `alembic.ini` exists — it does).

**Gate:** no documentation claim contradicts the code.

### Phase 2 — Close Doc A's academic core

| Deliverable | Path |
|---|---|
| **Room / Classroom entity** + capacity — unlocks the timetable solver | new `db/sms_facilities.py`, or extend `sms_events_facilities.py` |
| Attendance validates active enrolment | `services/sms/attendance.py`, `routers/sms_attendance.py:277-311` |
| Fix absence-streak to calendar days | `services/sms/attendance.py:102-132` |
| `Program` + syllabus topics, or formalise `CurricularPathway` as the program | new tables / `db/sms_pathways.py` |
| Transport module | greenfield |
| Timetable conflict enforcement in the database | partial unique indexes on `sms_timetable_schedule` |

### Phase 3 — Close Doc B's live classes

| Deliverable | Path |
|---|---|
| **LiveKit Egress service**; wire `egress_ended` → recording row | new compose service, `docker/start.sh`, `routers/live_class_webhooks.py` |
| **Attendance bridge**: `duration_minutes` → percentage → `StudentAttendance` | new service consuming `LiveClassAttendanceLog`, applying the ≥80% rule |
| Recording → LMS chapter linkage | `db/sms_live_class.py` (`sms_live_class_coursework`) |
| Fix `/live/[roomId]` leave links | `apps/web/app/live/[roomId]/page.tsx:32` |
| Polls / Q&A | new tables + UI |
| In-class whiteboard modal | wire a Hocuspocus room per session |

### Phase 4 — Wire RBAC and tenancy

Decide: wire `require_permission` into routers, **or** delete it. Leaving it is the
worst option — it is a live admin surface over a role store that participates in no
authorization decision.

Then add `org_id` / `campus_id` to the 90 unscoped tables — fee vouchers,
attendance, grades, clinical notes and salaries first — and enable Postgres RLS.

### Phase 5 — The 4-domain reorganization

Last, not first. Collapse the seven navigation definitions to one
(`apps/web/lib/school-modules.ts`), group by Academic Core / Curriculum &
Evaluation / Admissions & CRM / Institutional Admin, and delete the ~11.3k lines of
dead code first so you are not reorganizing dead code.

---

## 5. Critical path

```
Room entity ──► timetable constraint solver
Attendance bridge ──► Doc B advantage #3 (zero-friction attendance)
Egress service ──► Doc B recording pipeline
RBAC decision ──► everything in Phase 4 and 5
Phase 0 ──► everything
```

## 6. Standing rules that apply to all of this

- **Absence of data is never rendered as a value.** A metric without data is `null`
  with an explanation, never `0%`. Several current defects violate this
  (`exam_psychometrics.py:117-118`, the grading band gap, `attendancePct ?? 0`).
- **New columns require an Alembic migration.** `create_all` never ALTERs.
- **Confidential records enforce 404-never-403.**
- **Never trust the body for identity or privilege.**
