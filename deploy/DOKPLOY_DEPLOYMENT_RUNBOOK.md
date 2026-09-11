# CSG-LMS Enterprise: Dokploy & Hetzner Cloud Production Deployment Runbook

This runbook provides complete, end-to-end instructions for deploying **CSG-LMS** to production using **Dokploy** on **Hetzner Cloud** or **Proxmox VE**.

---

## 1. Stack Architecture & Topology

```
                                  INTERNET
                                      │
                         [ Traefik Reverse Proxy (SSL) ]
                                      │
    ┌──────────────────┬──────────────┴──────────────┬──────────────────┐
    │                  │                             │                  │
    ▼                  ▼                             ▼                  ▼
[ web:3000 ]      [ api:9000 ]                 [ auth:8080 ]      [ collab:4000 ]
app.csginfotech.com api.csginfotech.com        auth.csginfotech.com collab.csginfotech.com
 Next.js 15 App   FastAPI (Python 3.14/3.12)    Keycloak 26 IAM     Hocuspocus (CRDT)
 Standalone       (Alembic + RLS Multi-Campus) (PKCE + RBAC)       (Yjs WebSockets)
    │                  │                             │                  │
    └──────────────────┼─────────────────────────────┼──────────────────┘
                       │                             │
            ┌──────────┴──────────┐       ┌──────────┴──────────┐
            ▼                     ▼       ▼                     ▼
    [ postgres:5432 ]       [ redis:6379 ]               [ Object Storage ]
    PostgreSQL 16 +          Redis 7.2 Cache               Cloudflare R2 /
    pgvector & RLS           & Realtime PubSub             AWS S3 Bucket
```

---

## 2. Prerequisites & Server Sizing

| Environment | Recommended Hetzner Cloud Plan | vCPU | RAM | Storage |
|---|---|---|---|---|
| **Production (Medium)** | **CPX31** / **CCX23** (Dedicated) | 4 vCPU | 8–16 GB | 160 GB NVMe |
| **Production (Large / High Concurrency)** | **CCX33** (Dedicated AMD/Intel) | 8 vCPU | 32 GB | 240 GB NVMe |
| **Proxmox VM** | KVM Guest (Ubuntu 24.04 LTS) | 4–8 vCPU | 16 GB | 150 GB ZFS/LVM |

### Required Operating System Packages
- Ubuntu 24.04 LTS or Debian 12
- Docker Engine `26.x+` & Docker Compose `v2.27+`
- Dokploy `v0.8.x+` installed on port `3000` (or behind Traefik)

---

## 3. DNS Configuration

Point the following **A / AAAA Records** to your Hetzner Server Public IPv4 / IPv6:

| Subdomain | Type | Target | Purpose |
|---|---|---|---|
| `app.csginfotech.com` | `A` | `<SERVER_IP>` | Next.js 15 Web Application |
| `api.csginfotech.com` | `A` | `<SERVER_IP>` | FastAPI REST & GraphQL API |
| `auth.csginfotech.com` | `A` | `<SERVER_IP>` | Keycloak 24/26 OIDC IAM Server |
| `collab.csginfotech.com` | `A` | `<SERVER_IP>` | Hocuspocus CRDT Collab WebSocket |
| `cdn.csginfotech.com` | `CNAME` | `<R2_OR_S3_ENDPOINT>` | Static Assets & User Uploads |

---

## 4. One-Click Deployment via Dokploy

### Step 4.1: Create a New Project in Dokploy
1. Log into your Dokploy dashboard at `http://<SERVER_IP>:3000` or `https://dokploy.csginfotech.com`.
2. Click **Create Project** -> Name: `CSG-LMS-Production`.
3. Inside the project, click **Create Service** -> Select **Compose**.

### Step 4.2: Configure the Compose Stack
1. In the Compose editor, paste the contents of `dokploy-compose.yml` (or select Git Repository deployment pointing to `main`).
2. Set the **Compose File Path** to `dokploy-compose.yml`.

### Step 4.3: Add Environment Variables
Click on the **Environment** tab in Dokploy and paste your configured variables from `.env.production.example`.

> [!IMPORTANT]
> Ensure all passwords and secrets are generated using cryptographic random values:
> ```bash
> openssl rand -hex 32
> ```

---

## 5. Keycloak Realm Initialization & Role Configuration

The stack auto-imports the pre-configured realm from `deploy/keycloak/realm-export-csg-lms.json` on the first container startup.

### Pre-Configured Realm Specifications:
- **Realm Name**: `csg-lms`
- **Clients**:
  1. `csg-lms-web`: Public OIDC Client (PKCE `S256` enabled, standard authorization code flow, Web Origins configured for `https://app.csginfotech.com`).
  2. `csg-lms-api`: Bearer-only Resource Server verifying access tokens and audience claims.
- **Configured Realm Roles**:
  - `SUPER_ADMIN`: Full multi-tenant governance, system settings, global metrics.
  - `SCHOOL_ADMIN`: Campus-level academic administration, faculty oversight, reporting.
  - `TEACHER`: Course authoring, assignments, grading, interactive boards.
  - `STUDENT`: Course consumption, quizzes, peer collaborative sessions.
  - `PARENT`: Student gradebook, attendance reports, academic alerts.
  - `STAFF`: Tuition fee invoicing, payments, financial ledger reconciliation.

### Default Seed Accounts:
All seed accounts have the initial password: `Password123!`

| Role | Email / Username | Attributes |
|---|---|---|
| **SUPER_ADMIN** | `superadmin@csginfotech.com` | `org_id: 1, campus_id: 1` |
| **SCHOOL_ADMIN** | `principal@csginfotech.com` | `org_id: 1, campus_id: 1` |
| **TEACHER** | `teacher@csginfotech.com` | `org_id: 1, campus_id: 1` |
| **STUDENT** | `student@csginfotech.com` | `org_id: 1, campus_id: 1` |
| **PARENT** | `parent@csginfotech.com` | `org_id: 1, campus_id: 1` |
| **STAFF** | `accountant@csginfotech.com` | `org_id: 1, campus_id: 1` |

---

## 6. Database Migrations & Multi-Campus RLS

### Automated Alembic Migrations
The `api` container automatically executes `alembic upgrade head` before binding the ASGI server.

To manually run or inspect migrations from the CLI:
```bash
# Check current migration revision
docker compose -f docker-compose.prod.yml exec api alembic current

# Run pending migrations
docker compose -f docker-compose.prod.yml exec api alembic upgrade head

# Rollback one revision if necessary
docker compose -f docker-compose.prod.yml exec api alembic downgrade -1
```

### PostgreSQL Row-Level Security (RLS) Verification
Verify that PostgreSQL multi-campus isolation policies are active:
```bash
docker compose -f docker-compose.prod.yml exec postgres psql -U learnhouse -d learnhouse -c "\d"
```

---

## 7. Automated Stack Health Check

A comprehensive diagnostic healthcheck script is included in `deploy/scripts/healthcheck.py`.

Run the healthcheck anytime to verify all stack layers:
```bash
# Standard terminal output
python deploy/scripts/healthcheck.py --env-file .env.production

# JSON output for CI/CD or monitoring webhooks
python deploy/scripts/healthcheck.py --env-file .env.production --json
```

### What the healthcheck validates:
1. **PostgreSQL 16**: Port connectivity, latency, pgvector capability.
2. **Redis 7.2**: Auth authentication, memory metrics, RESP PING response.
3. **Keycloak 24/26**: OIDC OpenID Configuration discovery & JWKS active keys.
4. **FastAPI Backend**: `/api/v1/health` JSON payload response.
5. **Collab Server**: Hocuspocus `/health` status and Yjs WebSocket availability.
6. **Next.js Web**: HTTP status and standalone bundle readiness.
7. **SSL / TLS Certificates**: Expiration date and Let's Encrypt validation across all 4 hostnames.

---

## 8. Backup & Disaster Recovery Procedures

### 8.1 Automated Nightly PostgreSQL Backup
Create a cron job on the host machine:
```bash
# /etc/cron.daily/backup-csg-lms-db
#!/bin/bash
BACKUP_DIR="/var/backups/csg-lms"
mkdir -p "$BACKUP_DIR"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# Execute pg_dump with custom compressed format
docker exec csg-lms-postgres pg_dump -U learnhouse -F c -b -v -f "/var/lib/postgresql/data/backup_${TIMESTAMP}.dump" learnhouse

# Move to host backup directory and keep last 14 days
docker cp csg-lms-postgres:/var/lib/postgresql/data/backup_${TIMESTAMP}.dump "$BACKUP_DIR/"
docker exec csg-lms-postgres rm "/var/lib/postgresql/data/backup_${TIMESTAMP}.dump"
find "$BACKUP_DIR" -name "*.dump" -mtime +14 -delete
```

### 8.2 Database Restore Procedure
```bash
docker cp /var/backups/csg-lms/backup_YYYYMMDD_HHMMSS.dump csg-lms-postgres:/tmp/restore.dump
docker exec -i csg-lms-postgres pg_restore -U learnhouse -d learnhouse --clean --if-exists /tmp/restore.dump
```

---

## 9. ISO 27001, FERPA/COPPA & Security Compliance

1. **Non-Root Execution**: All containers (`api`, `web`, `collab`, `keycloak`) run under unprivileged service users (`UID 10001` / `UID 1001`).
2. **Multi-Campus Isolation**: JWT tokens include `campus_id` and `org_id` claims, strictly validated on all data access queries.
3. **FERPA/COPPA Child Safety**: Student PII is masked, password hashes use PBKDF2-SHA256 with 27,500 iterations, and tokens expire in 30 minutes.
4. **Audit Trails**: All authentication and privilege escalation events are recorded in the central audit log.
5. **TLS 1.3 Strict Transport Security**: Forced HTTPS, HSTS preload header (`max-age=31536000`), no-sniff MIME type guards, and iframe clickjacking protections.
