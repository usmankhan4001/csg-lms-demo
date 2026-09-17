# System Architecture: Deployment Topology & Process Management

**Document Reference:** CSG-ARCH-008  
**Target Audience:** DevOps Engineers, Site Reliability Engineers (SRE), Cloud Architects  
**Classification:** Technical Architecture Specification  
**Status:** Canonical Implementation Baseline (LearnHouse PM2 All-in-One)  

---

## 1. Deployment Paradigm: Supervised Monolithic Container

CSG-LMS adopts the streamlined **All-in-One Container Deployment Model** established by **LearnHouse** (`Dockerfile`, `docker/ecosystem.config.js`). 

Rather than requiring complex Kubernetes clusters with dozens of inter-dependent microservice pods for a single school deployment, the platform packages all core web, API, gateway, and real-time processes inside a single hardened Alpine Linux container managed by **PM2 (Process Manager 2)**.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              EXPANDED PRODUCTION DEPLOYMENT TOPOLOGY                   │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│                                  PUBLIC INTERNET                                       │
│                                         │                                              │
│                           Ports 80 / 443 / UDP 50000-60000                             │
│                                         ▼                                              │
│   +--------------------------------------------------------------------------------+   │
│   |                           NGINX REVERSE PROXY                                  |   │
│   |                              (Port 80/443)                                     |   │
│   +--------+------------------+---------------------+-------------------+----------+   │
│            |                  |                     |                   |              │
│   /api/v1/*|           /collab|             /livekit|                /* |              │
│            v                  v                     v                   v              │
│   +----------------+ +------------------+ +-------------------+ +-------------------+  │
│   | FASTAPI BACKEND| | HOCUSPOCUS SERVER| | LIVEKIT SFU       | | NEXT.JS FRONTEND  |  │
│   | (Python/Uvicorn| |   (Bun Engine)   | | (Go WebRTC SFU)   | | (Node Standalone) |  │
│   | Internal :9000 | |  Internal :4000  | | Internal :7880    | | Internal :8000    |  │
│   +--------+-------+ +--------+---------+ +---------+---------+ +-------------------+  │
│            |                  |                     |                                  │
│            | Enqueue Jobs     | Binary Ydoc Sync    | WebRTC Media                     │
│            v                  v                     v                                  │
│   +----------------+ +------------------+ +-------------------+                        │
│   | ARQ WORKER &   | | GOTENBERG ENGINE | | LIVEKIT EGRESS    |                        │
│   | CRON SCHEDULER | | (Chromium :3000) | | (Recording Worker)|                        │
│   +--------+-------+ +--------+---------+ +---------+---------+                        │
│            |                  |                     |                                  │
│            +------------------+----------+----------+                                  │
│                                          |                                             │
│   +--------------------------------------v-----------------------------------------+   │
│   | PM2 / DOCKER SUPERVISOR: Auto-restart on crash, log rotation, resource watchdog|   │
│   +--------------------------------------------------------------------------------+   │
│                                                                                        │
│   CONTAINER BOUNDARY                                                                   │
└──────────────────────────────────────────┬─────────────────────────────────────────────┘
                                            │
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                          EXTERNAL MANAGED CLOUD INFRASTRUCTURE                         │
│ • PostgreSQL 16 Managed DB (Amazon RDS / Self-hosted PG with pgvector)                 │
│ • Redis 7.2 Managed Cache (Amazon ElastiCache / Redis Cloud / Self-hosted)             │
│ • S3 Compatible Object Storage (AWS S3 / Cloudflare R2 / MinIO)                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. PM2 Process Supervision Configuration

All internal daemons are orchestrated via PM2 (`ecosystem.config.js`):

```javascript
module.exports = {
  apps: [
    {
      name: "nginx-gateway",
      script: "/usr/sbin/nginx",
      args: "-g 'daemon off;'",
      autorestart: true,
      max_restarts: 10
    },
    {
      name: "api-backend",
      cwd: "/app/apps/api",
      script: "poetry",
      args: "run uvicorn src.app:app --host 127.0.0.1 --port 9000 --workers 4",
      env: {
        PORT: 9000,
        PYTHONPATH: "/app/apps/api"
      },
      autorestart: true,
      max_memory_restart: "1G"
    },
    {
      name: "arq-worker",
      cwd: "/app/apps/api",
      script: "poetry",
      args: "run arq src.workers.WorkerSettings",
      env: {
        PYTHONPATH: "/app/apps/api"
      },
      autorestart: true,
      max_memory_restart: "1.5G"
    },
    {
      name: "arq-cron",
      cwd: "/app/apps/api",
      script: "poetry",
      args: "run python -m src.workers.cron_scheduler",
      env: {
        PYTHONPATH: "/app/apps/api"
      },
      autorestart: true,
      max_memory_restart: "512M"
    },
    {
      name: "collab-server",
      cwd: "/app/apps/collab",
      script: "bun",
      args: "run start",
      env: {
        PORT: 4000
      },
      autorestart: true,
      max_memory_restart: "512M"
    },
    {
      name: "web-frontend",
      cwd: "/app/apps/web",
      script: "server.js",
      env: {
        PORT: 8000,
        NODE_ENV: "production"
      },
      autorestart: true,
      max_memory_restart: "1G"
    }
  ]
};
```

---

## 3. Operational Advantages
- **Single-Command Local & Production Deployment:** An entire school network or regional staging environment deploys with a single command: `docker run -p 80:80 -e DATABASE_URL=... csg-lms:latest`.
- **Low Operational Footprint:** The combined Alpine container requires less than 2 GB of baseline RAM, allowing cost-effective hosting on modest cloud virtual machines.
- **Robust Process Isolation:** If the real-time Hocuspocus daemon or Next.js process experiences an unhandled memory exception, PM2 restarts the process within 1 second without impacting the FastAPI backend or dropping database connections.
