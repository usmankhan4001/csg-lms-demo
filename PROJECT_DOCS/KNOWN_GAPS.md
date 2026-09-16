# Known gaps

What is **not** done. This document exists because the project has a history of
overstating completeness — eight fabricated-data incidents were found and removed
during the build, and three separate tests were found asserting flaws as expected
behaviour. Everything here was verified against the code.

If you are evaluating this system, read this file before the others.

---

## Blocks deployment with real children's data

### No independent security review
Real vulnerabilities were found and fixed during the build — 31 write endpoints
with no authorization, a privilege escalation letting any student mint a
live-class host token with recording rights, open fee writes, and teachers able
to see which child disclosed self-harm. They were found by auditing. **Nobody
independent has reviewed the result.**

### Email is unconfigured by default
`RESEND_API_KEY` is empty. Crisis alerts, fee reminders, the parent digest and
nurture sequences all persist an in-app record and log a failed delivery row —
they do **not** reach anyone out of band. For a 2am self-harm disclosure, a
counsellor sees it when they next log in.

### Backups exist but the seed script is untested end to end
`scripts/backup.sh` and `scripts/restore.sh` are real and the **restore was
genuinely tested** — dumped, restored into a scratch database, row counts
compared. But `scripts/seed_school.py` has never been executed against a real
database; it compiles and its validation paths are tested, and it has
`--dry-run`. Run it once against a scratch database before trusting it.

### Migrations have one successful production-shaped run
Alembic had **never completed successfully** in this project's history until it
was repaired during this build (`7cb9375`). Head is now `c5d6e7f8a9b0`
(previously `2f4c13b60f5b`), 77 revisions, single head — confirmed with
`alembic heads` / `alembic history`. The dev database was **stamped** at a
baseline, which asserts the schema already matches those revisions — so any migration that
performed a *data* transformation is skipped for this database. Fine for dev; a
real decision for production.

---

## Not built at all

| Item | State |
|---|---|
| **M49 WebSocket streaming** | **Zero** `@router.websocket` routes anywhere. Nothing streams — messages refetch, tutor replies arrive whole. |
| **Offline sync** | No WatermelonDB dependency, no `/sync/delta` endpoint. A teacher taking roll-call with no signal loses the data. Specified across the module set; blocks the mobile product. |
| **M24 Voice agent** | Deliberately deferred per the client's own meeting notes. |
| **M43 Personalization engine** | No implementation. (The word "personalized" appears only in generated ad copy.) |
| **M50 Live-class QA/QC** | No implementation. |
| **M32 Integration & sync** | No implementation. |
| **WhatsApp / SMS provider** | None configured. A phone-only family **cannot be contacted at all** — this now surfaces as `UNAVAILABLE` rather than silently skipping, but the seam is unfilled. |
| **Payment gateway** | None. Fee payments record money the office already took. |
| **Digital reader** | The library has no file attachment on a book. It is a loans ledger. |
| **Financial period close** | Nothing prevents posting into a settled month. |
| **Transport (M15)** | Not built. |

---

## Built but incomplete

### Mobile
Two screens remain honest stubs because no backend exists for them:
- **Staff → Tasks** — there is no task model or endpoint anywhere in the API.
- **Student → Assignments** — assignments are keyed by `assignment_uuid`; there is
  no "my assignments across courses" endpoint.

Also: **MFA accounts cannot sign in on mobile.** The server returns a pending
token and there is no MFA screen. The app says so rather than appearing to work.

### Both menus have grown back since the collapse
The desktop sidebar was collapsed from 55 entries to 41 (one per module, with
tabs); it now renders ~50 distinct destinations. The mobile slide-up panel —
previously 27 flat entries — is now grouped under the same `PanelHeading`
sections and renders ~38 `PanelItem` entries. The tab strips already work on
mobile because they are rendered by the page, not the sidebar.

### Counselling has no caseload endpoint
Every session read is keyed on a student id, so a counsellor cannot list "my
sessions". Attendance's pastoral queue is wired as the entry point, but the
underlying gap is a backend one.

### Student names render as ids in several places
`StudentEnrollmentRead` carries no name. Attendance and gradebook work around
this with a client-side join against `GET /sms/identity/people`
(`modules/sms/attendance/useStudentNames.ts`) — it costs a round-trip and
resolves only students holding a role grant in the campus. Counselling
deliberately does **not** use it (see below). The real fix is the enrolment
endpoint joining `User`.

### Library does not distinguish titles from copies
`total_copies`/`available_copies` are counters. No per-copy row, accession number
or barcode. A hold queues for a *title*. Blocks stock-taking, per-copy condition
and "which copy did this child lose".

### Proctoring is out of scope, by design
`sms_exam.py` documents that it records an **invigilated** exam. This is stated
rather than quietly implied — but if you need proctoring, it is not here.

### Appraisal `ACKNOWLEDGED` has no endpoint
The status exists in the model (`sms_hr_extended.py:134`) and is documented as
"records that they have read it", but there is no route — a staff member cannot
acknowledge reading their appraisal.

### Cognia evidence has no reachable UI
`/api/v1/sms/cognia` exists. A `CogniaEvidenceStudio.tsx` was built under
`apps/web/modules/ems/cognia/` but is imported by nothing except that folder's
own `index.ts` — it is unreachable, not absent.

### The dynamic RBAC engine has no call sites
`require_permission` (`apps/api/src/security/ems_rbac.py:362`) is complete and
covered by `src/tests/security/test_ems_rbac.py`, but no router imports it —
every school route still gates on the static `require_roles(...)` helper. Until
something calls it, the engine is dead code and the permissions it models are
not actually enforced.

### AI surfaces are thin relative to their backends
The engines are wired and running, but several have little or no UI:
- `ai_student_profile` — 11 endpoints
- `ai_knowledge_graph` — 2 endpoints
- `ai_parent_digest` — 1 endpoint

The student-facing tutor chat on web historically lived only at a legacy lesson
URL that was not linked from the learner portal. Mobile has a proper
`AiCoachScreen`.

---

## Data-model residue

### Two identifier systems for staff
`LessonPlan.teacher_id` and `psychologist_id` are Keycloak `sub` **strings**,
while every other SMS table keys staff on the **integer Learnhouse user id**.
Migration `b7e2d41a9c38` added the integer counterparts — `teacher_user_id` on
`sms_lesson_plan` and `psychologist_user_id` on the counselling tables
(`apps/api/src/db/sms_counseling.py:73`) — so both are now joinable and the
string columns are legacy, written during the transition and to be dropped once
the backfill is confirmed. This is residue from the auth unification; there may
be more instances.

### Campus scoping is applied, not universal
Shared helpers exist (`resolve_scoped_campus_id`, `assert_campus_allowed`) and
were applied across the school routers, but several models carry no `campus_id`
of their own and are scoped only indirectly through a section or a student.

### Tenant isolation is service-layer only for most school tables
Of the 114 `table=True` models in `src/db/sms_*.py` / `src/db/ems_*.py`, 59 carry
neither `org_id` nor `campus_id` and 80 carry no `org_id` at all. Nothing at the
schema level prevents a cross-tenant read; isolation depends entirely on every
service-layer WHERE clause being correct, in every query, forever.

### No optimistic locking anywhere
Two staff editing the same record is last-write-wins.

### No per-copy, per-seat or per-room capacity enforcement
`max_capacity` on a class section is stored and, outside creation, largely
unread.

---

## Operational

### A live API key was reported in `docker-compose.local.yml`
Not reproducible against the current tree or its history: `git log -S"AIzaSy"`
returns only the initial release commit, and the only `AIzaSy…` string anywhere
is the placeholder at `.env.production.example:105`. `docker-compose.local.yml`
now reads `${LEARNHOUSE_GEMINI_API_KEY:-}` / `${GEMINI_API_KEY:-}` (`:113-114`).
This may have been true when written — `94ee214` removed a real key from
`apps/api/config/config.yaml` and flagged the compose file as still holding it —
but treat the key as burned and rotate it rather than assuming the file was
cleaned.

### Keycloak is defined in the prod compose and authenticates nothing
`get_current_user_principal` derives from a real Learnhouse session. The
`keycloak` service in `docker-compose.prod.yml:71` is still defined,
Traefik-exposed, and — because the API declares `depends_on: keycloak,
condition: service_healthy` (`docker-compose.prod.yml:182`) — **Keycloak failing
blocks the entire API from starting**, for no functional benefit. (It was removed
from `dokploy-compose.yml` in `2fe257f`; the prod compose is the remaining one.)
Documented rather than removed, because deleting a service from a deploy file is
an owner decision.

### Test-suite order sensitivity
Under `pytest-randomly` the suite has been observed failing tests that pass in
isolation and under `-p no:randomly`. Shared database state between files.
Pre-existing, not a code defect — but a green run is not proof on its own.

### Pre-existing failures outside the school modules
A set of media/file-storage hardening tests fail in this environment. They are
outside the school layer and were left alone.
