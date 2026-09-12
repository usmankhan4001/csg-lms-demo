# Architecture — As It Actually Stands

This describes the system as verified in code, not as originally pitched. For the module-by-module build status, see [STATUS.md](./STATUS.md). For how bugs in this architecture were found, see [BUGFIXES_LOG.md](./BUGFIXES_LOG.md).

## What this is

A fork of [Learnhouse](https://github.com/learnhouse/learnhouse) (AGPLv3 — Next.js + FastAPI + Postgres + a Hocuspocus/Yjs collab service), with a second layer of custom "school SMS" and "AI RevOps/Tutor" modules added on top. The base Learnhouse course-authoring, collaboration, and org/auth system is upstream code, not something built for this project. The custom layer (`sms_*`, `revops_*`, `ai_tutor`, `ai_student_profile`, the CSG dashboard pages under `apps/web/app/(dashboard)`) is what this project actually built.

This is explicitly a **separate, non-commercial experiment**, kept apart from the "official" CSG-LMS product defined in the sibling `CSG-LMS.wiki` repository (NestJS/Drizzle/RabbitMQ, a different architecture entirely). That wiki is read-only reference here — nothing in it is modified by this project.

Because the base is AGPLv3, anything derived from it and run as a network service must make its source available to users of that service (AGPLv3 §13) — relevant if this is ever exposed beyond fully internal, non-networked use.

## Backend module layout

```
apps/api/src/
├── routers/
│   ├── sms_campus.py, sms_attendance.py, sms_timetable.py, sms_gradebook.py,
│   │   sms_fees.py, sms_financials.py, sms_hr.py, sms_payroll.py,
│   │   sms_library.py, sms_revops.py, sms_teacher_tools.py, sms_counseling.py
│   ├── ai_tutor.py, ai_student_profile.py
│   └── live_classes.py
├── db/            # SQLModel tables per module (sms_*.py, ai_knowledge_graph.py)
├── services/
│   ├── sms/       # business logic per SMS module
│   └── ai/        # socratic_tutor.py, crisis_classifier.py, knowledge_graph.py,
│                  # revops_lead_scoring.py, revops_sdr_agent.py, revops_drip_engine.py,
│                  # revops_offer_generator.py, content_guardrails.py
├── core/
│   ├── keycloak_auth.py       # JWT verification — see "Auth: two systems" below
│   ├── dev_tokens.py          # mints Keycloak-shaped JWTs locally for dev
│   ├── events.py              # in-process pub/sub event bus (Phase 0)
│   └── deployment_mode.py
└── security/features_utils/   # per-org feature toggles (resolve.py, dependencies.py)
```

All 12 SMS/RevOps/Tutor routers listed above are mounted with a Keycloak-auth dependency (verify: `grep -rl "Depends(keycloak_auth" src/routers/sms_*.py`) — this was **not** true earlier in the project; see the [BUGFIXES_LOG.md](./BUGFIXES_LOG.md) entry "No auth on 9 of 12 routers."

### Per-org feature toggles

Every SMS sub-module (not just the three pillars) has its own toggle, reusing Learnhouse's existing `OrganizationConfig`/`AdminToggles` JSON-blob mechanism (`apps/api/src/db/organization_config.py`) rather than inventing a new one. `resolve_feature()`/`resolve_all_features()` (`src/security/features_utils/resolve.py`) do the actual resolution; `require_<feature>_feature()` dependencies (`src/security/features_utils/dependencies.py`) gate routes. The frontend reads the same resolved-features payload to hide a disabled module's nav entry.

### Realm roles

`SUPER_ADMIN`, `SCHOOL_ADMIN`, `TEACHER`, `STUDENT`, `PARENT`, `STAFF`, `PSYCHOLOGIST` (`apps/api/src/core/keycloak_auth.py`'s `KeycloakRole` enum). Renamed from an earlier `CAMPUS_PRINCIPAL`/`ACCOUNTANT` naming to match the wiki's terminology.

## Frontend layout

```
apps/web/
├── app/
│   ├── (dashboard)/            # CSG portals: student/, teacher/, parent/, campus-admin/, admissions/
│   ├── auth/login/, home/      # Learnhouse's own native auth + org picker
│   ├── orgs/[orgslug]/         # Learnhouse's own org-scoped course/library/etc. pages
│   ├── dev-login/              # bridge from Learnhouse session -> CSG dev Keycloak token
│   └── api/auth/[...path]/     # server-side proxy to the FastAPI backend's /auth/*
├── components/navigation/      # RoleSidebar, PortalHeader (CSG-specific)
├── components/widgets/         # shared KpiCard/DataTable/SectionCard/EmptyState (7-state model)
├── lib/api/
│   ├── api-client.ts           # fetch wrapper for all sms_*/revops_* calls
│   ├── dev-token.ts            # dev Keycloak JWT storage/decoding (localStorage)
│   └── devLogin.ts             # mints + stores a dev token from a real Learnhouse session
├── proxy.ts                    # tenancy/routing proxy — see "The proxy.ts gotcha" below
└── services/config/config.ts   # runtime config resolution (see "Two backend URLs" below)
```

## Auth: two systems, not one

This is the single most important thing to understand about this codebase, and the source of most bugs found so far.

1. **Learnhouse native auth** (`components/Contexts/AuthContext.tsx`, `/auth/login`, `/api/auth/*`) — real, cookie-based, backed by the FastAPI backend's own user table. `admin@csg.dev` logs in here. This is what powers `/home`, `/orgs/[slug]/*`, course browsing, etc.

2. **Dev Keycloak-shaped JWT** (`lib/api/dev-token.ts`, `POST /api/v1/dev/mint_keycloak_token`) — a separate, dev-only token the SMS/RevOps/Tutor routers require, because they were built against a Keycloak-shaped `get_current_user_principal` dependency and **no real Keycloak server has ever been deployed for this project**. This token carries realm roles, `org_id`, `campus_id`, and convenience claims (`subject_id`, `section_id`, `children_ids`) the SMS pages use to answer "show me my data."

The two are bridged by `/dev-login` (`apps/web/app/dev-login/page.tsx` + `lib/api/devLogin.ts`): it takes your real Learnhouse access token, calls the mint endpoint (which independently requires a Learnhouse superadmin session), and stores the resulting JWT for `api-client.ts` to attach as a Bearer token on every SMS call.

**Safety property of the mint endpoint** (`apps/api/src/routers/dev.py::mint_keycloak_token`): it 404s outright (not 403 — it doesn't even reveal it exists) the instant this deployment looks like it's pointed at a real Keycloak server (`is_hmac_dev_verification_active()` in `keycloak_auth.py`). It's inert-by-construction in any real deployment, not just gated by an env flag.

**A real Keycloak service is defined** in `docker-compose.prod.yml` / `deploy/keycloak/realm-export-csg-lms.json`, but **it has never been started or verified end-to-end** — the realm-export JSON has never been confirmed to import cleanly, and the API's JWT validation has never been checked against a live Keycloak instance. That's why `docker-compose.local.yml` deliberately excludes it.

## Two backend URLs (Docker networking)

In `docker-compose.local.yml`, the web and API run as **separate containers**. This means "the backend URL" is not one value — it depends on who's asking:

| Caller | Correct URL | Why |
|---|---|---|
| Browser (client-side fetch) | `http://localhost:8000` (`NEXT_PUBLIC_LEARNHOUSE_BACKEND_URL`) | Reaches the API container via the host's port mapping. |
| Web container's own Node process (Server Components, Route Handlers, `proxy.ts`) | `http://api:9000` (`LEARNHOUSE_INTERNAL_API_URL`) | Docker-internal service DNS + the API's actual listen port. `localhost:8000` from *inside* the web container is the web container's own loopback — nothing listens there. |

`services/config/config.ts`'s `deriveAPIUrl()` picks the internal URL when running server-side (`typeof window === 'undefined'`) and the public one otherwise. Every server-only file that builds its own backend URL (rather than going through `deriveAPIUrl()`/`getServerAPIUrl()`) has to apply the same preference independently — three separate files needed this fix (see [BUGFIXES_LOG.md](./BUGFIXES_LOG.md)), because nothing enforces it structurally. **If you add a new server-side fetch to the FastAPI backend, check which URL you're using.**

## The `proxy.ts` gotcha (Next.js 16)

This project runs Next.js 16, where `middleware.ts` was renamed to **`proxy.ts`** (a real, breaking convention change — see `apps/web/AGENTS.md`'s standing warning that this is "not the Next.js you know"). `apps/web/proxy.ts` is the actual tenancy/routing layer:

- Rewrites bare `/login`, `/signup`, etc. to `/auth/login`, `/auth/signup` internally — hitting `/auth/login` **directly** bypasses this and falls through to the org-scoped catch-all, which 404s.
- Rewrites bare `/` (in single-tenancy mode) to `/orgs/{default_org_slug}/...` — so `app/(dashboard)/page.tsx` (the CSG portal-selector page mapped to bare `/`) is currently **unreachable**; nothing broken depends on it today, but don't assume `/` renders it.
- Explicitly passes through `/student`, `/teacher`, `/parent`, `/campus-admin`, `/admissions`, `/live`, and `/dev-login` without rewriting — any **new** CSG top-level route needs to be added to this list or it will 404 the same way `/auth/login` does when hit directly.

## Deployment status

`dokploy-compose.yml`, `docker-compose.prod.yml`, and the Keycloak realm export exist on disk but have never been run to completion — a prior Dokploy deployment attempt was stopped before finishing. `docker-compose.local.yml` (Postgres + Redis + API + Web, no Keycloak) is the only path that has actually been run and tested through a real browser; see [LOCAL_SETUP.md](./LOCAL_SETUP.md).
