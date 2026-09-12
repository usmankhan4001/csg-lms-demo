# Local Setup — Docker (Verified Runbook)

This is the only deployment path that has actually been run end-to-end and tested through a real browser. It brings up Postgres + Redis + the API + the web app — **not** Keycloak (see [ARCHITECTURE.md](./ARCHITECTURE.md#auth-two-systems-not-one) for why).

## 1. Start the stack

```bash
cd learnhouse-dev
docker compose -f docker-compose.local.yml up --build -d
```

Wait for all four containers to report healthy:

```bash
docker ps --format '{{.Names}}\t{{.Status}}'
```

## 2. Log in

Go to **`http://localhost:3000/login`** — not `/auth/login` (that 404s; see [BUGFIXES_LOG.md](./BUGFIXES_LOG.md) entry on `proxy.ts`).

Seeded superadmin account (from `docker-compose.local.yml`'s `LEARNHOUSE_INITIAL_ADMIN_EMAIL`/`_PASSWORD`, created automatically by `LEARNHOUSE_AUTO_INSTALL`):

- Email: `admin@csg.dev`
- Password: `AdminPassword123!`

This logs you into **Learnhouse's native auth** — courses, org picker, the base platform. It does **not** by itself get you into the CSG SMS dashboards.

## 3. Enter a CSG portal (Student / Teacher / Parent / Campus Admin)

From `/home`, click any of the "Unified Role Portals" links (Student Hub, Teacher Hub, Parent Portal), or use the role switcher in the sidebar/header once inside a portal. These now route through `/dev-login?role=X`, which:

1. Takes your current Learnhouse superadmin session,
2. Calls the backend's dev-only token-minting endpoint,
3. Stores the result, and
4. Redirects you into the portal.

You can also do this manually: visit `http://localhost:3000/dev-login` and pick a role.

**Why this extra step exists:** the SMS/RevOps backend routers authenticate with a Keycloak-shaped JWT, and no real Keycloak server has ever been deployed for this project. See [ARCHITECTURE.md](./ARCHITECTURE.md#auth-two-systems-not-one).

## 4. Stopping / resetting

```bash
docker compose -f docker-compose.local.yml down          # stop, keep data
docker compose -f docker-compose.local.yml down -v        # stop and wipe Postgres/Redis volumes
```

## Known-benign noise

- A `403` on an SMS endpoint scoped to a different role (e.g. testing `/teacher` with a `STUDENT` token) is expected — not a bug.
- `net::ERR_ABORTED` on `*.js?_rsc=...` requests in the browser console is a normal Next.js prefetch being cancelled by navigation — not a bug.
- A `404` on `/new` from the `/home` org picker's "Create organization" link is a real, pre-existing gap (that page is SaaS/multi-tenancy-only; this deployment runs single-tenancy/OSS) — not something introduced by this project's changes.
- The 8 failing tests in `apps/api/src/tests/routers/test_content_files_router.py` predate this project's work and are unrelated to it (confirmed via `git stash` A/B testing).

## Backend test suite

```bash
cd apps/api
uv run pytest src/tests/sms src/tests/ai src/tests/test_app_lifespan.py src/tests/routers src/tests/test_root_router.py -q
```
