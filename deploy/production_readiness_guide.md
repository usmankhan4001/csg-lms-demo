# CSG-LMS Enterprise: Dokploy & VPS Production Deployment Runbook

> **Target Infrastructure**: Dokploy (v0.8+), Hetzner Cloud VMs (CPX31/CCX23/CCX33), Proxmox KVM, or Bare-Metal Ubuntu 24.04 LTS.  
> **Security & Reliability**: Automated SSL/TLS (Traefik), Database Isolation (PostgreSQL 16 + pgvector), Redis 7.2 Caching, Real-Time WebRTC (LiveKit), CRDT Collaboration (Hocuspocus), and Automated S3/R2 Backup Retention.

---

## Table of Contents
1. [Architecture & Network Topology](#1-architecture--network-topology)
2. [VPS Server Sizing & OS Hardening](#2-vps-server-sizing--os-hardening)
3. [DNS Configuration](#3-dns-configuration)
4. [Dokploy Installation & Stack Setup](#4-dokploy-installation--stack-setup)
5. [Environment Variables Configuration](#5-environment-variables-configuration)
6. [LiveKit Real-Time WebRTC Media Setup](#6-livekit-real-time-webrtc-media-setup)
7. [Database Migrations & Initial Seeding](#7-database-migrations--initial-seeding)
8. [Automated PostgreSQL Backups & S3 Retention](#8-automated-postgresql-backups--s3-retention)
9. [Pre-Flight Verification & Health Monitoring](#9-pre-flight-verification--health-monitoring)
10. [Disaster Recovery & Rollback Procedures](#10-disaster-recovery--rollback-procedures)

---

## 1. Architecture & Network Topology

```
                                      INTERNET (HTTPS / WSS / WebRTC)
                                                     │
                                       [ Traefik Reverse Proxy (SSL) ]
                                                     │
        ┌─────────────────────────┬──────────────────┴──────────────┬─────────────────────────┐
        │                         │                                 │                         │
        ▼                         ▼                                 ▼                         ▼
   [ web:3000 ]              [ api:9000 ]                     [ collab:4000 ]           [ livekit:7880 ]
  ${APP_DOMAIN}             ${API_DOMAIN}                    ${COLLAB_DOMAIN}          ${LIVEKIT_DOMAIN}
  Next.js 15 Standalone     FastAPI Python 3.12              Hocuspocus CRDT           LiveKit Signaling
  (React 19 / Tailwind)     (Alembic + RLS Multi-Campus)     (Yjs WebSockets)          & Media Engine
        │                         │                                 │                         │
        └─────────────────────────┼─────────────────────────────────┼─────────────────────────┘
                                  │                                 │
                       ┌──────────┴──────────┐           ┌──────────┴──────────┐
                       ▼                     ▼           ▼                     ▼
               [ postgres:5432 ]       [ redis:6379 ] [ tinybird-mock:8080 ] [ Object Storage ]
               PostgreSQL 16 +         Redis 7.2 AOF  Mock Analytics         Cloudflare R2 /
               pgvector (768-dim)      Pub/Sub & Cache Engine                AWS S3 Bucket
```

### Published Ports & Traefik Routing Table:
| Service | Internal Port | Traefik Router | Public Hostname (Dynamic) | Description |
|---|---|---|---|---|
| `web` | `3000` | `csg-web` | `${APP_DOMAIN}` (e.g. `app.csginfotech.com`) | Next.js Frontend |
| `api` | `9000` | `csg-api` | `${API_DOMAIN}` (e.g. `api.csginfotech.com`) | FastAPI Backend REST & WS |
| `collab` | `4000` | `csg-collab` | `${COLLAB_DOMAIN}` (e.g. `collab.csginfotech.com`) | Hocuspocus CRDT Collaboration |
| `livekit` | `7880` | `csg-livekit` | `${LIVEKIT_DOMAIN}` (e.g. `livekit.csginfotech.com`) | LiveKit Signaling (WSS) |
| `livekit` | `7881` | Direct TCP | Published host `7881` | WebRTC TCP fallback |
| `livekit` | `50000-50100/udp` | Direct UDP | Published host `50000-50100/udp` | WebRTC Real-Time Media Audio/Video |
| `tinybird-mock`| `8080` | Internal | `http://tinybird-mock:8080` | Internal Mock Analytics |
| `postgres` | `5432` | Internal | `postgres:5432` | PostgreSQL 16 + pgvector |
| `redis` | `6379` | Internal | `redis:6379` | Redis 7.2 In-Memory Cache |

---

## 2. VPS Server Sizing & OS Hardening

### Hardware Specifications:
| Tier | Recommended Plan (Hetzner / Proxmox) | vCPU | RAM | Storage |
|---|---|---|---|---|
| **Production Baseline** | Hetzner **CPX31** / **CCX23** | 4 vCPU | 8–16 GB | 160 GB NVMe |
| **High Concurrency (Live Video + AI)** | Hetzner **CCX33** (Dedicated) | 8 vCPU | 32 GB | 240 GB NVMe |

### 2.1 OS Setup (Ubuntu 24.04 LTS)
```bash
# 1. Update system packages
sudo apt update && sudo apt upgrade -y

# 2. Install essential utilities
sudo apt install -y curl wget git htop ufw fail2ban jq postgresql-client

# 3. Configure UFW Firewall
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp comment 'SSH'
sudo ufw allow 80/tcp comment 'HTTP Let’s Encrypt'
sudo ufw allow 443/tcp comment 'HTTPS Traefik'
sudo ufw allow 7881/tcp comment 'LiveKit WebRTC TCP'
sudo ufw allow 50000:50100/udp comment 'LiveKit WebRTC Media UDP'
sudo ufw enable
```

### 2.2 Linux Kernel Optimization for WebSockets & WebRTC
Append to `/etc/sysctl.conf`:
```ini
# Maximum socket receive/send buffer for WebRTC video streams
net.core.rmem_max = 16777216
net.core.wmem_max = 16777216
net.core.rmem_default = 262144
net.core.wmem_default = 262144
net.ipv4.tcp_rmem = 4096 87380 16777216
net.ipv4.tcp_wmem = 4096 65536 16777216

# Increase max open files and connections
fs.file-max = 2097152
net.core.somaxconn = 32768
```
Apply with:
```bash
sudo sysctl -p
```

---

## 3. DNS Configuration

Point the following **A / AAAA Records** to your server's Public IP address in your DNS manager (e.g. Cloudflare, Namecheap, Route53):

| Hostname | Type | Target | Cloudflare Proxy | Purpose |
|---|---|---|---|---|
| `app.csginfotech.com` | `A` | `<SERVER_IP>` | DNS-Only or Proxied | Web Application |
| `api.csginfotech.com` | `A` | `<SERVER_IP>` | DNS-Only or Proxied | REST API & WebSockets |
| `collab.csginfotech.com` | `A` | `<SERVER_IP>` | DNS-Only (recommended for Yjs WSS) | CRDT Real-Time Sync |
| `livekit.csginfotech.com` | `A` | `<SERVER_IP>` | **DNS-Only (Grey Cloud)** | WebRTC Signaling & Media |

> [!IMPORTANT]
> `livekit.csginfotech.com` **MUST** be **DNS-Only (Grey Cloud)** if using Cloudflare DNS. Cloudflare Proxy does not forward raw UDP media ports (`50000-50100/udp`) required by WebRTC.

---

## 4. Dokploy Installation & Stack Setup

### 4.1 Install Dokploy on Server
```bash
curl -sSL https://dokploy.com/install.sh | sh
```
Access Dokploy web dashboard at `http://<SERVER_IP>:3000`. Complete the initial admin account setup.

### 4.2 Create Compose Application
1. In Dokploy dashboard, click **Projects** -> **Create Project** -> `CSG-LMS`.
2. Inside the project, click **Create Service** -> Select **Compose**.
3. Service Name: `csg-lms-production`.
4. Choose **Git Provider** (connect your repository) or **Raw Compose**.
5. Set Compose File Path: `dokploy-compose.yml`.

---

## 5. Environment Variables Configuration

In Dokploy under the **Environment** tab, configure the production variables:

```ini
# ==============================================================================
# CSG-LMS PRODUCTION ENVIRONMENT CONFIGURATION
# ==============================================================================
NODE_ENV=production
LEARNHOUSE_ENV=production

# ── Dynamic Domain Names ──────────────────────────────────────────────────────
APP_DOMAIN=app.csginfotech.com
API_DOMAIN=api.csginfotech.com
COLLAB_DOMAIN=collab.csginfotech.com
LIVEKIT_DOMAIN=livekit.csginfotech.com
KEYCLOAK_DOMAIN=auth.csginfotech.com

# ── Application URLs ──────────────────────────────────────────────────────────
LEARNHOUSE_URL=https://app.csginfotech.com
LEARNHOUSE_API_URL=https://api.csginfotech.com
LEARNHOUSE_COLLAB_URL=wss://collab.csginfotech.com
LIVEKIT_URL=wss://livekit.csginfotech.com

# ── Database (PostgreSQL 16 + pgvector) ────────────────────────────────────────
POSTGRES_DB=learnhouse
POSTGRES_USER=learnhouse
POSTGRES_PASSWORD=<GENERATE_SECURE_PASSWORD_32_CHARS>

# ── Redis 7.2 ─────────────────────────────────────────────────────────────────
REDIS_PASSWORD=<GENERATE_SECURE_PASSWORD_32_CHARS>

# ── Cryptographic Secrets ────────────────────────────────────────────────────
# Generate using: openssl rand -hex 32
LEARNHOUSE_AUTH_JWT_SECRET_KEY=<GENERATE_SECURE_SECRET_64_CHARS>
COLLAB_INTERNAL_KEY=<GENERATE_SECURE_SECRET_32_CHARS>
LEARNHOUSE_MEDIA_SECRET_KEY=<GENERATE_SECURE_SECRET_32_CHARS>

# ── LiveKit WebRTC Real-Time Video ───────────────────────────────────────────
LIVEKIT_API_KEY=csg_livekit_prod_key
LIVEKIT_API_SECRET=<GENERATE_SECURE_SECRET_32_CHARS>

# ── Tinybird Analytics (Pillar 2 / Admin Insights) ───────────────────────────
LEARNHOUSE_TINYBIRD_API_URL=http://tinybird-mock:8080
LEARNHOUSE_TINYBIRD_INGEST_TOKEN=mock_ingest_token
LEARNHOUSE_TINYBIRD_READ_TOKEN=mock_read_token

# ── S3 / Cloudflare R2 Storage (Optional) ────────────────────────────────────
LEARNHOUSE_STORAGE_TYPE=local
# S3_ENDPOINT_URL=https://<ACCOUNT_ID>.r2.cloudflarestorage.com
# S3_ACCESS_KEY_ID=<R2_ACCESS_KEY>
# S3_SECRET_ACCESS_KEY=<R2_SECRET_KEY>
# S3_BUCKET_NAME=csg-lms-production
# S3_PUBLIC_DOMAIN=cdn.csginfotech.com

# ── Automated Backup Configuration ───────────────────────────────────────────
BACKUP_DIR=/var/backups/csg-lms
RETENTION_DAYS=14
S3_BACKUP_ENABLED=false
```

---

## 6. LiveKit Real-Time WebRTC Media Setup

The `livekit` service is configured with:
1. `use_external_ip: true`: Dynamically resolves the server's public IPv4 via STUN servers to provide ICE candidates to browsers.
2. WebRTC UDP media port range: `50000-50100/udp`.
3. WebRTC TCP fallback port: `7881/tcp`.
4. Automated webhook callbacks to `http://api:9000/api/v1/live/webhooks` for real-time attendance tracking.

Verify LiveKit is running:
```bash
docker compose -f dokploy-compose.yml exec livekit wget -qO- http://localhost:7880/
```

---

## 7. Database Migrations & Initial Seeding

Once the stack containers are running:

### Step 7.1: Apply Alembic Migrations
```bash
# Execute inside the API container
docker compose -f dokploy-compose.yml exec api alembic upgrade head
```

### Step 7.2: Seed School Campus & SuperAdmin
```bash
# Seed initial organization, campus, academic calendar and superadmin
docker compose -f dokploy-compose.yml exec api python scripts/seed_school.py
```

---

## 8. Automated PostgreSQL Backups & S3 Retention

The repository includes both shell and Python automated backup tools with integrity verification:
- `scripts/backup_postgres.sh`: Fast bash script with zero-leakage `pg_dump`, `pg_restore` TOC verification, and local pruning.
- `scripts/backup_postgres.py`: Python tool with S3/R2 upload, SHA256 checksums, JSON manifests, and remote retention management.

### 8.1 Setup Automated Scheduled Backups via Dokploy Schedules or Cron
Add a daily backup schedule (at 02:00 AM UTC):

```bash
# Edit server crontab
sudo crontab -e
```
Add the cron entry:
```cron
0 2 * * * cd /path/to/learnhouse-dev && ./scripts/backup_postgres.sh >> /var/log/csg-lms-backup.log 2>&1
```

Or using the Python runner with Cloudflare R2 / AWS S3 offsite replication:
```cron
0 2 * * * cd /path/to/learnhouse-dev && python3 scripts/backup_postgres.py --env-file .env.production --retention-days 14 --s3-retention-days 30 >> /var/log/csg-lms-backup.log 2>&1
```

### 8.2 Database Restore Drill
To restore from a verified backup:
```bash
./scripts/restore.sh /var/backups/csg-lms/csg-lms-learnhouse-20260914T020000Z.dump
```

---

## 9. Pre-Flight Verification & Health Monitoring

Before announcing production launch, execute the pre-flight verification suite:

```bash
python3 scripts/verify_production_readiness.py --env-file .env.production
```

### Expected Output:
```
================================================================================
 CSG-LMS PRODUCTION READINESS & PRE-FLIGHT VERIFICATION REPORT
================================================================================

► 1. Security & Env Config
  [✔ PASS] POSTGRES_PASSWORD                  Configured with adequate entropy.
  [✔ PASS] REDIS_PASSWORD                     Configured securely.
  [✔ PASS] JWT Secret Key                     Valid secret (length 64 chars).
  [✔ PASS] Collab Internal Key                Configured securely.
  [✔ PASS] LiveKit Credentials                Production LiveKit API key and secret set.
  [✔ PASS] Application Domain                 Configured domain: app.csginfotech.com
  [✔ PASS] Local File Storage                 Using persistent local volume storage.

► 2. PostgreSQL & Vector
  [✔ PASS] Postgres TCP Socket       (1.2ms)  Connected to postgres:5432
  [✔ PASS] Postgres Auth & Handshake          Authenticated as 'learnhouse' on 'learnhouse'.
  [✔ PASS] PGVector Extension                 Vector extension installed (v0.7.0).
  [✔ PASS] Alembic DB Migrations              Active migration revision: 8f2a1d9c4e0b

► 3. Redis Cache & Pub/Sub
  [✔ PASS] Redis Ping & Auth         (0.8ms)  PING succeeded with PONG response.

► 4. LiveKit WebRTC Video
  [✔ PASS] LiveKit Signaling Port    (1.1ms)  Listening on livekit:7880
  [✔ PASS] LiveKit JWT Token Signing          Successfully signed standard LiveKit HS256 join token.

► 5. Application Services
  [✔ PASS] Collab Health Endpoint    (2.4ms)  HTTP 200 OK from collab:4000/health
  [✔ PASS] FastAPI Health Endpoint   (3.1ms)  HTTP 200 OK from /api/v1/health

► 6. System Resources & Disk
  [✔ PASS] Disk Space                         124.5 GB available (Total: 156.0 GB).
  [✔ PASS] Docker Socket                      Docker UNIX socket /var/run/docker.sock exists & accessible.

--------------------------------------------------------------------------------
SUMMARY: Total Checks: 17 | Passed: 17 | Warnings: 0 | Failed: 0
--------------------------------------------------------------------------------
✔ ALL CHECKS PASSED: Stack is 100% production ready for Dokploy deployment.
```

---

## 10. Disaster Recovery & Rollback Procedures

### 10.1 Zero-Downtime Rolling Update in Dokploy
1. Push updates to the `main` branch.
2. In Dokploy, click **Redeploy**.
3. Dokploy performs container healthcheck probing on the newly built image before swapping traffic in Traefik.

### 10.2 Emergency Rollback
If a deployment exhibits regressions:
```bash
# In Dokploy -> Compose -> Deployments -> Click 'Rollback to Previous Deployment'
# Or via CLI:
docker compose -f dokploy-compose.yml down
docker compose -f dokploy-compose.yml up -d --build
```
