# Local Setup — Docker (Verified Runbook)

This is the only deployment path that has actually been run end-to-end and tested through a real browser. It brings up Postgres + Redis + the API + the web app — **not** Keycloak (see [ARCHITECTURE.md](./ARCHITECTURE.md#identity) for why).

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

> **Corrected 2026-09-16.** This section previously described a `/dev-login?role=X`
> dev-token bridge. That route no longer exists — it was removed along with the
> dev-only token minting it depended on (see
> `apps/api/src/security/school_principal.py:38-40`). There is no second login.

There is only the one Learnhouse login from step 2. Once you are signed in, the
web app calls `GET /sms/me`, buckets the first role it returns, and writes an
`LH_role` cookie (`apps/web/lib/api/school-role-cookie.ts`). `proxy.ts`
(lines 274-286) reads that cookie in single-tenancy mode and redirects `/`,
`/home` and `/login` to the matching shell:

| `LH_role` | Lands on |
|---|---|
| `TEACHER`, `ADMIN` | `/dash` |
| `STUDENT`, `PARENT` | `/my-school` |

The seeded superadmin has no `SMSUserRole` row, but `resolve_school_principal()`
injects `SUPER_ADMIN` for any `User.is_superadmin`
(`apps/api/src/security/school_principal.py:164-165`), so it lands on `/dash`.

If an account has no school role at all, no cookie is written and you stay on
`/home` — from there the "Unified Role Portals" links go straight to
`/my-school` and `/dash` (`apps/web/app/home/home.tsx:222-232`).

To grant a school role to an account:

```bash
python scripts/manage_roles.py assign --email teacher@csg.dev --role TEACHER --org-id 1
python scripts/manage_roles.py list --org-id 1
```

**Why roles are separate from login:** the SMS/RevOps routers authenticate with
a `KeycloakUserPrincipal` that is now built from your real Learnhouse session
plus your `SMSUserRole` rows — there is no Keycloak server and no second token.
See [ARCHITECTURE.md](./ARCHITECTURE.md#identity).

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
