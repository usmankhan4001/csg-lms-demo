# Architecture

How the system is built, verified against the code. For what each module does
see [MODULES.md](./MODULES.md); for why particular choices were made see
[DECISIONS.md](./DECISIONS.md); for what is missing see
[KNOWN_GAPS.md](./KNOWN_GAPS.md).

## What this is

A fork of [Learnhouse](https://github.com/learnhouse/learnhouse) (AGPLv3 —
Next.js + FastAPI + Postgres + a Hocuspocus/Yjs collab service), with a school
management layer and an AI layer added on top.

The base Learnhouse course-authoring, collaboration and org/auth system is
upstream code. The custom layer is the `sms_*` / `revops_*` / `ai_*` routers, the
school dash modules under `apps/web/app/orgs/[orgslug]/dash/`, and the Expo app.

Because the base is AGPLv3, anything derived from it and run as a network service
must make its source available to users of that service (AGPLv3 §13).

> **Note:** an older version of this document described the custom layer as
> living in `apps/web/app/(dashboard)`. That directory was **retired** — it was a
> second, parallel app shell that still rendered and had drifted out of sync. All
> school UI now lives inside Learnhouse's own shells.

## Repository layout

```
apps/
├── api/      FastAPI + SQLModel + Postgres (pgvector) + Redis + arq worker
├── web/      Next.js — Learnhouse UI plus the school modules
├── mobile/   Expo / React Native / NativeWind
├── collab/   Hocuspocus/Yjs collaboration service (upstream)
├── cli/      upstream CLI
└── e2e/      Playwright
scripts/      backup.sh, restore.sh, seed_school.py
PROJECT_DOCS/ these documents
```

## The two frontend shells

This is the single most important structural fact about the web app.

| Shell | Path | Who | Nav |
|---|---|---|---|
| **Staff** | `apps/web/app/orgs/[orgslug]/dash/` | admins, teachers, back office, counsellors | `DashLeftMenu` / `DashMobileMenu` |
| **Learner** | `apps/web/app/orgs/[orgslug]/(withmenu)/` | students, parents | `OrgMenu` |

School modules attach to the **staff** shell as ordinary dash modules — the same
way Learnhouse's own Courses, Boards and Playgrounds do. They inherit
`ClientAdminLayout`, the sidebar, and the command palette. The learner shell
carries `my-school`, the AI tutor surface, and Learnhouse's own learner features.

A third shell used to exist and was removed. Do not add a fourth.

### Module shells and tabs

Each school module is **one sidebar entry** that opens a page with its own tab
strip. Tab definitions live once in `apps/web/lib/school-modules.ts`; the strip
is rendered by `DashPageShell` via its `module` prop
(`apps/web/components/widgets/ModuleTabs.tsx`).

Access is **per tab**, not per module — a teacher opening Timetable cannot see
the admin-only Generate tab. A failing tab is not rendered at all.

## Identity

There is no Keycloak server. The name survives in the code because the principal
object and its dependency functions were kept while the implementation beneath
them was replaced.

```
Learnhouse session (real, cookie/bearer)
        │
        ▼
get_authenticated_user            apps/api/src/security/auth.py
        │
        ▼
resolve_school_principal          apps/api/src/security/school_principal.py
        │  reads SMSUserRole, injects SUPER_ADMIN when User.is_superadmin
        ▼
KeycloakUserPrincipal             (sub, org_id, campus_id, roles, raw_claims)
        │
        ▼
get_current_user_principal        apps/api/src/core/keycloak_auth.py
```

Because ~90 call sites depend on `get_current_user_principal` **by name**,
swapping the implementation beneath it required no changes to the routers.

Key tables (`apps/api/src/db/sms_identity.py`):

- **`SMSUserRole`** — `(user_id, org_id, campus_id, role)`. The source of truth
  for who is what, replacing Keycloak realm-role claims.
- **`StudentGuardian`** — the parent↔child link. `children_ids` must never be
  client-supplied; it resolves from here.

**`GET /api/v1/sms/me`** is the single identity source for both clients. It
returns roles, org, campus, `student_id`, `staff_id`, `section_id` and
`children_ids`.

> The real Learnhouse access token carries **no role claim** — its payload is
> `{sub, purpose, amr, exp, iat, type}` and `sub` is the email. Any client
> reading roles from the token will get nothing. Roles come from `/sms/me`.

## Authorization

Three layers, applied together:

1. **Role** — `require_roles([...])` as a FastAPI dependency. Each router defines
   its own constant (`_BURSAR`, `_HR_ADMIN`, `_SAFEGUARDING`, …) rather than
   sharing one list, because the right set genuinely differs per module.
2. **Ownership** — `apps/api/src/security/school_ownership.py`:
   `assert_owns_section_or_privileged`, `require_own_student_or_privileged`,
   `get_own_children_ids`.
3. **Campus scope** — `resolve_scoped_campus_id` (reads narrow to the caller's
   campus) and `assert_campus_allowed` (writes naming another campus fail
   loudly).

> **`require_campus_access` is weaker than its name.** It reads only
> `request.path_params` and `request.query_params` — a `campus_id` in the request
> **body is never checked** — and it rejects only an *explicit* mismatch, so an
> unscoped request gives a campus-bound admin org-wide reach. Use the
> `school_ownership` helpers.

**Never trust the body for identity or privilege.** `is_teacher`, `graded_by`,
`approved_by`, `participant_id`, `marked_by` and `student_id` were all accepted
from request payloads at various points and all now derive from the authenticated
principal.

## Feature toggles

Reuses Learnhouse's own per-org toggle system rather than inventing a parallel
one.

```
OrganizationConfig.config (JSON)
  └── admin_toggles.<feature>.disabled
        │
        ▼
resolve_feature / resolve_all_features    security/features_utils/resolve.py
        │
        ├─► require_<feature>_feature      → 403 at the router
        └─► org info response              → nav hides the entry
```

Adding a toggle needs **no migration** — it is a JSON blob. But a feature must be
registered in **both** `ALL_FEATURES` *and* the typed `AdminToggles` model, or it
becomes enforced-but-unsettable (this happened to `sms_exam`).

Administered at **Org settings → Modules** (`OrgEditModules`).

## Schema strategy — read this before adding a field

`SQLModel.metadata.create_all` runs at app boot
(`apps/api/src/core/events/database.py:417`) and creates **missing tables**. It
**never `ALTER`s an existing one.**

| Change | What to do |
|---|---|
| New table | Nothing. `import_all_models()` registers it; `create_all` builds it. |
| **New column on an existing table** | **Write an Alembic migration.** Without one, the code and every existing database silently disagree and the module 500s. |

Alembic head: **`2f4c13b60f5b`**, 71 revisions, single head. The container
entrypoint runs `alembic upgrade head` at startup.

Two traps that have already cost time:

- **Do not declare a `ForeignKey` in a migration to a table that `create_all`
  builds at boot.** Alembic runs *first* in the entrypoint, so the constraint
  would exist on fresh databases and be absent on migrated ones. Use a plain
  integer.
- **Do not declare `Index("ix_x_y", "y")` in `__table_args__` *and* `index=True`
  on the same column.** SQLAlchemy auto-names a column index identically, so
  `create_all` emits `CREATE INDEX` twice and **the API fails to boot.**

Uniqueness involving a nullable column needs care: `NULL != NULL` in SQL, so a
unique constraint spanning a nullable `campus_id` or `period_id` will not prevent
duplicate rows in the NULL case. Those are enforced read-before-write in the
service layer instead.

## Audit trails

Append-only, same shape in each case, written in the **same transaction** as the
change so a crash cannot leave a record altered with no trail:

| Table | Covers |
|---|---|
| `sms_grade_change_event` | mark changes |
| `AttendanceChangeEvent` | register corrections |
| fee change events | money mutations |
| `sms_data_subject_request` | GDPR exports and erasures |
| `SMSImpersonationEvent` | superadmin impersonation |

Identifying columns are **snapshotted integers, not foreign keys** — an
FK-linked trail would be destroyed by a `CASCADE` delete of the thing it
describes.

Note `UserAuditEvent` is upstream and scoped to *learner* actions; it is not the
school audit trail.

## Background jobs

`arq` against Redis, registered in `apps/api/src/core/worker.py`:

- weekly parent digest
- hourly nurture-sequence advance (RevOps)
- daily fee reminders (09:00 — deliberately not hourly; a balance changes on the
  scale of days)

All outbound mail routes through `services/notifications/service.py`, so a failed
send is a visible `NotificationDelivery` row rather than a swallowed log line.

## AI layer

```
services/ai/
├── socratic_tutor.py        tutor, enrolment-scoped, rate-limited
├── crisis_classifier.py     LOCAL regex — no model call, no network
├── crisis_alerts.py         counsellor/principal dispatch, triage metadata only
├── content_guardrails.py    age and subject appropriateness
├── knowledge_graph.py       mastery DAG
├── revops_*.py              SDR, drip, offers, research, marketing, copywriting
└── llm/                     provider abstraction + token budgets
```

`revops_model_router.py` enforces a per-org monthly token budget.

Two safety properties worth knowing:

- **`classify_prompt_safety()` is synchronous and local.** All network calls in
  `crisis_classifier.py` are in `log_safety_incident` (the DB write and alert
  dispatch), not the classification. This is why crisis screening can run even
  when AI consent is refused.
- **`log_safety_incident` downgrades `counselor_notified` to `False`** when
  delivery fails, so an undelivered alert never looks handled.

## Frontend conventions

Shared widgets in `apps/web/components/widgets/`:

- `DashPageShell` — page chrome, takes a `module` prop for the tab strip
- `SectionCard`, `DataTable`, `EmptyState`, `StatGrid`, `StatusChip`
- `SchoolDialog` / `SchoolField` — **use these for every dialog**

> Learnhouse's `DialogContent` ships with `gap-0` and **no padding**; each
> consumer supplies its own. A dialog written against shadcn defaults renders
> with the title overlapping the first field. `SchoolDialog` encodes the correct
> padding.

Data fetching is a small `useApiResource` hook — no SWR or React Query.

Every screen implements seven states: Default, Loading, Empty, Error, Offline,
Permission-denied, Success.

Ctrl+K is fed by `page.search.ts` files collected in
`apps/web/lib/dashboard-search/registry.ts`. Entries carry a `featureKey` and a
`schoolAccess` level so discovery gating matches the sidebar — a teacher cannot
find Payroll through search.

## Deployment

- **Local:** `docker-compose.local.yml` — api, web, postgres, redis, livekit,
  collab.
- **Production:** `dokploy-compose.yml` via Dokploy. The API entrypoint runs
  `alembic upgrade head` before starting.
- **LiveKit:** `docker-compose.livekit.yml` carries an ICE fix
  (`rtc.node_ip`) — without it LiveKit advertises its Docker-internal IP and
  participants never connect.
