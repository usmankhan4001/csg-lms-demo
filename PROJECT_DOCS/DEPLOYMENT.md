# Deployment Runbook — First Production Boot

**Status: NO-GO pending the blockers in §6.** This document is the preparation for a
first deployment, not a record of one. Nothing described here has been executed.

This system has never been deployed. The Dokploy instance holds 12 projects and
none of them is this one. `dokploy-compose.yml` describes a target
(`lms-demo.csginfotech.co` / `api-demo.csginfotech.co`) that does not exist yet.
Local Docker is the entire operational history.

---

## 1. Config audit

### 1.1 Correction to the working assumption

The API reads **115 distinct environment variables**, not 122 — that figure counted
occurrences of the `LEARNHOUSE_*` pattern across files, not distinct names. Of those
115, `dokploy-compose.yml` sets **63**, leaving 86 unset. Almost all 86 have safe
in-code defaults; the ones that matter are below.

### 1.2 Variables that HARD-FAIL the boot if absent

`config/config.py` raises `ValueError` during startup for these. Failure is loud and
immediate, which is correct behaviour — but it means a missing value is a dead API,
not a degraded one.

| Variable | Condition | Set in compose |
|---|---|---|
| `LEARNHOUSE_AUTH_JWT_SECRET_KEY` | Must exist AND be ≥ 32 chars (config.py:280,285) | `${...}` — no default |
| `LEARNHOUSE_TENANCY` | Must be `multi`/`single` if set; otherwise inferred (config.py:389) | Not set — **inferred**, see §1.4 |
| `LEARNHOUSE_COOKIE_DOMAIN` | Rejected if a single-label parent like `.com` (config.py:420) | `.csginfotech.co` — valid |

### 1.3 Compose variables with NO fallback — must exist in the Dokploy `.env`

These are written `${VAR}` with no `:-default`. If absent they expand to an empty
string, which for the two connection strings produces a malformed URL rather than an
error:

- `POSTGRES_PASSWORD`
- `REDIS_PASSWORD`
- `LEARNHOUSE_AUTH_JWT_SECRET_KEY`
- `LEARNHOUSE_MEDIA_SECRET_KEY`
- `COLLAB_INTERNAL_KEY`

### 1.4 Tenancy is inferred, not declared — fix before deploying

`LEARNHOUSE_TENANCY` is unset, so config.py:389 infers it:

```
_multi_intent  = saas_mode OR (ee_available AND cookie_domain starts with ".")
tenancy        = "multi" if (_multi_intent AND real_domain AND NOT self_or_dev) else "single"
```

With the compose file's values — `LEARNHOUSE_COOKIE_DOMAIN=.csginfotech.co`,
`LEARNHOUSE_DOMAIN=csginfotech.co`, no `SELF_HOSTED`, no `DEVELOPMENT_MODE` —
everything hinges on `ee_available`. That is `os.path.isdir("ee")` relative to the
process working directory, which is `/app` in the container (`Dockerfile.prod:70`,
build context `./apps/api`). `apps/api/ee/` does not exist, so it resolves **False**
and tenancy lands on **single**.

That is the desired outcome, but it is arrived at by accident. Anyone who adds an
`ee/` directory silently flips the deployment to multi-tenant — changing routing,
the org-picker and the login flow.

**Recommendation: set `LEARNHOUSE_TENANCY=single` explicitly in the compose file.**
Not changed here; this lane does not own application behaviour.

### 1.5 Storage variable names — verified correct

The compose file uses the short `S3_*` spellings. `config.py:461` `_s3_env()` accepts
both those and the `LEARNHOUSE_S3_API_*` spellings for bucket, endpoint, credentials,
region, public domain and addressing style, so **no rename is needed**. The R2
endpoint-with-bucket-appended trap is detected and stripped at config.py:511.

**Two gaps:** compose sets no `S3_REGION` and no `S3_ADDRESSING_STYLE`. R2 normally
wants region `auto`; MinIO requires `path` addressing. Add both when the storage
values are filled in.

### 1.6 Defects found in the compose file

| # | Finding | Impact |
|---|---|---|
| 1 | `LEARNHOUSE_STORAGE_TYPE` defaults to `local` **and the `api` service mounts no volume** | Every uploaded file — avatars, course media, evidence — is destroyed on each redeploy. **Must be set to `s3api` with real credentials before any real use.** |
| 2 | `EMAIL_FROM_ADDRESS` defaults to `notifications@csginfotech.**com**` while every other domain is `csginfotech.**co**` | Mail sent from a domain the deployment does not control — SPF/DKIM will not align and delivery will fail or land in spam. Verify which domain is correct. |
| 3 | `LIVEKIT_API_KEY` / `LIVEKIT_API_SECRET` have **hardcoded defaults committed to the repo** (`csg_livekit_key`, `csg_livekit_secret_minimum_32_chars_2026`) | If not overridden, the deployment ships with publicly-known credentials. Anyone with the repo can mint LiveKit tokens. |
| 4 | Tinybird defaults point at `tinybird-mock:8080` with `mock_ingest_token` | Analytics in "production" writes to a mock. Harmless if intended, misleading if not. |
| 5 | `WORKERS` defaults to `4` | See §5 — interacts badly with known in-memory state. |

### 1.7 Keycloak — confirmed dead configuration

The brief asked whether Keycloak is a real dependency. **It is not.**

- **Frontend:** `NEXT_PUBLIC_KEYCLOAK_URL`, `_REALM` and `_CLIENT_ID` are set in the
  compose file and read by **zero** files in `apps/web`. Grep returns nothing.
- **Backend:** `get_current_user_principal` (keycloak_auth.py:469) builds the
  principal from the real authenticated Learnhouse session plus `SMSUserRole` grants.
  The token-decoding path is retained but unreferenced, documented as such in the file.
- **No `keycloak` service exists in the compose file.** Services are: postgres, redis,
  api, livekit, collab, tinybird-mock, web.

`auth-demo.csginfotech.co` therefore needs **no DNS record and no server**. The
concrete risk is someone provisioning a Keycloak instance believing it is required.
Recommend deleting the three `NEXT_PUBLIC_KEYCLOAK_*` lines — flagged, not done,
since application config is outside this lane.

---

## 2. Migration plan for a fresh database

### 2.1 Current state — verified

- `alembic heads` → **`2f4c13b60f5b` (head)**. Exactly one. The ten branched heads
  found earlier were merged; that merge holds.
- Migrations had **never run** in this project before that repair, so a fresh
  database is in fact the *best-understood* case — it is the upgrade path from an
  existing divergent database that carries no guarantees.

### 2.2 Order of operations at boot

`docker-entrypoint.prod.sh` runs, in order:

1. Wait for PostgreSQL (45 attempts × 2s)
2. Wait for Redis (same)
3. `alembic upgrade head`
4. `exec uvicorn app:app --workers ${WORKERS:-4}`

Then, during application startup, `src/core/events/database.py:417` runs
`SQLModel.metadata.create_all`.

So the real sequence is **Alembic first, `create_all` second.** This is the origin of
the standing trap: a migration must never declare a foreign key to a table that only
`create_all` builds, because at migration time that table does not yet exist.
`create_all` creates missing TABLES only — it never issues `ALTER`, so any new
*column* requires a migration.

### 2.3 The entrypoint silently swallows migration failure — BLOCKER

`docker-entrypoint.prod.sh:76-86`:

```bash
alembic upgrade head || {
    python -m alembic upgrade head || echo "⚠️ Migration check completed with warnings."
}
echo "✅ [CSG-LMS] Database schema is up to date."
```

The script sets `set -e`, but `||` chains suppress it. **If both Alembic attempts
fail, the script prints a warning, then prints "✅ Database schema is up to date" —
which is false — and boots the API anyway.** `create_all` then creates whatever
tables it can, and the deployment runs on a schema missing every `ALTER` the
migrations carry, including the two columns added this cycle
(`sms_student_attendance.period_id`, `class_section.academic_year_id`).

This is the same failure shape as the storage and email misconfiguration found
earlier today: broken, silent, and reporting success.

**This must be fixed before first deploy.** The migration step should fail the
container. Not changed here — `docker-entrypoint.prod.sh` is application source,
outside this lane's ownership.

---

## 3. Secrets inventory

Names and sources only. **No secret values appear in this document, and none should
be pasted into any file in this repository.**

| Secret | Source | Status |
|---|---|---|
| `POSTGRES_PASSWORD` | Generate; store in Dokploy env | Must be created |
| `REDIS_PASSWORD` | Generate; store in Dokploy env | Must be created |
| `LEARNHOUSE_AUTH_JWT_SECRET_KEY` | Generate, ≥32 chars (`secrets.token_urlsafe(32)`) | Must be created |
| `LEARNHOUSE_MEDIA_SECRET_KEY` | Generate | Must be created |
| `COLLAB_INTERNAL_KEY` | Generate; must match the `collab` service | Must be created |
| `LIVEKIT_API_KEY` / `LIVEKIT_API_SECRET` | Generate | **Repo defaults are public — must override** |
| `S3_ACCESS_KEY_ID` / `S3_SECRET_ACCESS_KEY` | Cloudflare R2 dashboard | Exists; proven working |
| `S3_ENDPOINT_URL` / `S3_BUCKET_NAME` | Cloudflare R2 | Exists; proven working |
| `RESEND_API_KEY` | Resend dashboard | **COMPROMISED — must be rotated, see §6** |
| `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `MISTRAL_API_KEY`, `GROQ_API_KEY` | Respective providers | Optional; AI features degrade without them |
| `SENTRY_DSN` | Sentry | Optional |

---

## 4. First-boot runbook

### 4.1 Before touching Dokploy

1. Rotate the Resend key (§6). Do not proceed without this.
2. Generate the five no-default secrets in §1.3 plus LiveKit's two.
3. Decide `EMAIL_FROM_ADDRESS` — `.co` or `.com` — and verify the sending domain in
   Resend.
4. Set `LEARNHOUSE_STORAGE_TYPE=s3api` with real R2 values. Leaving it `local`
   guarantees data loss (§1.6 #1).
5. Set `LEARNHOUSE_TENANCY=single` explicitly (§1.4).
6. Fix the entrypoint migration swallow (§2.3).

### 4.2 Boot order

Dokploy resolves this via `depends_on` + healthchecks: postgres and redis must be
healthy before api starts; api must be healthy before web starts. No manual
sequencing is required, but the dependency chain means **a failing api healthcheck
leaves web permanently unstarted** — check api first when the stack appears stuck.

### 4.3 Health checks that actually prove service

Check from **inside** the container network, not from a workstation. A host-side
`curl` returning `000` was previously misread as a dead API while the containers were
healthy and serving.

| Service | Check | Proves |
|---|---|---|
| postgres | `pg_isready` (compose healthcheck) | Accepting connections |
| redis | `redis-cli ping` (compose healthcheck) | Accepting connections |
| api | `curl -f http://localhost:9000/api/v1/health` from inside the container | Route exists (`router.py:109`) and the app booted |
| api schema | `alembic current` inside the container — must report `2f4c13b60f5b` | Migrations actually applied, not swallowed (§2.3) |
| web | `curl -f http://localhost:3000/` from inside the container | Next.js serving |
| public | `curl -I https://lms-demo.csginfotech.co` from outside | Traefik routing + TLS |

**`alembic current` is the single most important check on a first boot** and is not
part of any automated healthcheck. Run it manually.

### 4.4 Rollback

1. Dokploy redeploys the previous image tag — this reverts code, **not schema**.
2. Alembic migrations in this project have `downgrade()` bodies, but none have ever
   been executed. Treat a schema rollback as untested.
3. Because the first deploy targets an empty database, the practical rollback for
   deploy #1 is: stop the stack, drop the database, correct config, redeploy. That
   option disappears the moment real data exists.
4. There is no rehearsed restore (§6). Until there is, the rollback story for a
   populated database is incomplete and should be stated as such rather than assumed.

---

## 5. Multi-worker interaction — flagged

`WORKERS` defaults to 4, so uvicorn runs four independent processes. Two known pieces
of module-global state do not survive that:

- `src/routers/sms_cognia.py:102` `_EVIDENCE_STORE` — a Python list. Four workers means
  four different stores; a write served by worker 1 is invisible to workers 2–4, and
  all of it dies on restart. Already recorded as a defect; production makes it worse
  than local.
- The in-process event bus is per-process by construction. Any subscriber assumed to
  fire once per event will fire in only the worker that handled the request.

Neither blocks the boot. Both mean "it worked locally" does not transfer.

---

## 6. Go / no-go

### Blockers — deployment must not proceed

| # | Blocker | Owner |
|---|---|---|
| 1 | **Resend API key was pasted into a chat log.** Must be rotated in the Resend dashboard. No agent can do this. | Account owner |
| 2 | **Entrypoint swallows migration failure** and reports success (§2.3). | Application change |
| 3 | **`LEARNHOUSE_STORAGE_TYPE=local` with no volume** destroys all uploads on redeploy (§1.6 #1). | Config |
| 4 | **LiveKit credentials default to values committed in this repo** (§1.6 #3). | Config |

### Resolved / verified

- Alembic: exactly one head, confirmed.
- Storage config resolution: proven against real R2 and a real MinIO container,
  including the endpoint-with-bucket trap.
- Health endpoint exists and the compose healthcheck targets it correctly.
- Keycloak: confirmed dead config, no server needed.

### Unresolved, not blocking deploy #1

- **Backups: three scripts disagree and no restore has ever been rehearsed.** A backup
  nobody has restored from is a belief. This blocks going live with *real* data, even
  though it does not block a first boot.
- `EMAIL_FROM_ADDRESS` domain mismatch (§1.6 #2) — blocks email actually arriving.
- No CI; the full test suite takes ~68 minutes with no parallelism installed.
- Tenancy is inferred rather than declared (§1.4).
- No rehearsed rollback for a populated database (§4.4).

---

*Prepared by the deployment-readiness lane. Every claim above was read from the
committed source at the paths cited. Nothing was deployed, and no Dokploy resource was
created or modified.*
