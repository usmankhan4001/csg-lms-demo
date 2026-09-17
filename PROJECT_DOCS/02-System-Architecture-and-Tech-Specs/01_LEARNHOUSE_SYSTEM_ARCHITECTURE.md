# System Architecture: The LearnHouse Foundation & Container Model

**Document Reference:** CSG-ARCH-001  
**Target Audience:** Software Engineers, System Architects, DevOps Leads  
**Classification:** Technical Architecture Specification (Grounded in LearnHouse)  
**Status:** Canonical Implementation Baseline  

---

## 1. Architectural Paradigm: Monolithic Modularity on LearnHouse

CSG-LMS adopts and extends the high-throughput, modern architecture of **LearnHouse** (`apps/api`, `apps/web`, `apps/collab`). The platform avoids premature microservice sprawl, deploying as a streamlined, high-performance composable modular monolith with dedicated real-time collaboration micro-daemons.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                             C4 LEVEL 2: EXPANDED CONTAINER ARCHITECTURE                │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│  [Actors: Students, Teachers, Principals, Admissions Counselors, Bursars, Parents]     │
│                                       │                                                │
│                                       ▼                                                │
│                 +---------------------------------------------+                        │
│                 |             CSG-LMS GATEWAY                 │                        │
│                 |          (Nginx Reverse Proxy)              │                        │
│                 +---------------------+-----------------------+                        │
│                                       |                                                │
│      +--------------------+-----------+------------+--------------------+              │
│      | HTTP / REST        | WS /collab             | WS/HTTP /livekit   | HTTP / SSR   │
│      v                    v                        v                    v              │
│  +---------------+  +------------------+     +-------------------+  +---------------+  │
│  |  FASTAPI CORE |  | HOCUSPOCUS BUN   |     | LIVEKIT SFU (Go)  |  | NEXT.JS WEB   |  │
│  | :9000 Internal|  | :4000 Internal   |     | :7880 / UDP 50000 |  | :8000 Internal|  │
│  +-------+-------+  +--------+---------+     +---------+---------+  +---------------+  │
│          |                   |                         |                               │
│          | Enqueue Jobs      | Sync Ydocs              | Record Egress                 │
│          v                   v                         v                               │
│  +---------------+  +------------------+     +-------------------+                     │
│  |  ARQ WORKER & |  | GOTENBERG ENGINE |     |  LIVEKIT EGRESS   |                     │
│  |  CRON DAEMON  |  | (Chromium :3000) |     |  (Chrome/FFmpeg)  |                     │
│  +-------+-------+  +--------+---------+     +---------+---------+                     │
│          |                   |                         |                               │
│          +-------------------+----+--------------------+                               │
│                                   |                                                    │
│                                   v                                                    │
│   +--------------------------------------------------------------------------------+   │
│   |                            DATA & PERSISTENCE LAYER                            │   │
│   | • PostgreSQL 16: Relational Models, App-Level Multi-Tenancy (Zero RLS overhead)|   │
│   | • Redis 7.2: Task Queues, Real-time Ydoc Cache, Token Bucket Limiting, Pub/Sub  │   │
│   | • S3 / MinIO Storage: Lesson Recordings, Generated PDF Gradecards & Transcripts|   │
│   +--------------------------------------------------------------------------------+   │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Container Topology & Component Responsibilities

### 2.1 Backend REST API Container (`apps/api`)
- **Technology:** Python 3.12+ / FastAPI / SQLModel / SQLAlchemy Async / Uvicorn.
- **Port:** `9000` (Internal).
- **Core Responsibilities:**
  - Dynamic RBAC authentication, JWT session lifecycle, and MFA verification.
  - Multi-tenant query filtering via `organization_id` dependency injection.
  - SMS Institutional Core: Academic Years, Terms, Programs, Courses, Campuses, Rooms, Batches, Students, Guardians, Timetable, Attendance.
  - LMS Content Engine: Course Chapters, Activities, Blocks, Assignments, Submissions, Trails.
  - Embedded AI Engine: Multi-provider LLM connectors (OpenAI, Anthropic, Gemini, Groq, Ollama) and pgvector RAG retriever.

### 2.2 Frontend Web Portal Container (`apps/web`)
- **Technology:** Next.js 16 (App Router) / React 19 / Turbopack / TailwindCSS / TipTap Rich Text / CodeMirror.
- **Port:** `8000` (Internal).
- **Core Responsibilities:**
  - High-performance Server-Side Rendered (SSR) institutional web portals.
  - Responsive, touch-optimized user interfaces for Teachers, Students, Parents, and Administrators.
  - TipTap rich-text lesson authoring canvas and embedded video playback.

### 2.3 Real-Time Collaboration Daemon (`apps/collab`)
- **Technology:** Hocuspocus / Bun / Node.js.
- **Port:** `4000` (Internal).
- **Core Responsibilities:**
  - WebSocket synchronization server for real-time collaborative Whiteboards (`BOARD`).
  - Binary Yjs Conflict-Free Replicated Data Type (CRDT) document synchronization.
  - Low-latency sub-50ms peer cursor streaming and debounced binary persistence to PostgreSQL.

### 2.4 Nginx Gateway & Reverse Proxy
- **Technology:** C / Nginx.
- **Ports:** `80` (HTTP) / `443` (HTTPS) / `5050` (Local Host).
- **Core Responsibilities:**
  - SSL/TLS termination and HTTP/2 protocol negotiation.
  - Route routing: `/api/v1/*` $\to$ FastAPI (Port 9000), `/collab/*` $\to$ Hocuspocus (Port 4000), `/*` $\to$ Next.js (Port 8000).
  - Rate limiting, DDoS packet inspection, and static asset caching.

### 2.5 LiveKit SFU Media Server & Egress Recorder
- **Technology:** Go / WebRTC / Pion (SFU) & Headless Chromium + GStreamer/FFmpeg (Egress).
- **Ports:** `7880` (Signaling) & UDP `50000–60000` (RTP Media).
- **Core Responsibilities:**
  - Broadcast-quality live interactive classrooms, video simulcast, and screen sharing.
  - Automated composite room recording to HLS/MP4 archived directly to S3/MinIO.
  - *(Refer to [05_REALTIME_COLLABORATION_AND_CRDT_ARCHITECTURE](file:///C:/Users/User/Documents/CSG-LMS.wiki/02-System-Architecture-and-Tech-Specs/05_REALTIME_COLLABORATION_AND_CRDT_ARCHITECTURE.md) for full protocol flow).*

### 2.6 Asynchronous Distributed Worker & Scheduled Cron Daemon
- **Technology:** Python 3.12+ / ARQ / Asyncio / Redis 7.2.
- **Core Responsibilities:**
  - Offloads CPU-intensive operations: 5D Timetable constraint solving (OR-Tools) and AI RAG chunking/vectorization.
  - Executes automated daily cron jobs: Midnight truancy evaluation, fee aging ledger calculations, and gradebook column locks.
  - *(Refer to [06_EVENT_DRIVEN_INTEGRATION_AND_HANDSHAKE_BUS](file:///C:/Users/User/Documents/CSG-LMS.wiki/02-System-Architecture-and-Tech-Specs/06_EVENT_DRIVEN_INTEGRATION_AND_HANDSHAKE_BUS.md) for worker queue topology).*

### 2.7 Gotenberg High-Fidelity Document & PDF Engine
- **Technology:** Docker / Gotenberg 8 / Headless Google Chrome / HTML5 / CSS3 Print.
- **Port:** `3000` (Internal).
- **Core Responsibilities:**
  - Pixel-perfect conversion of HTML5/Tailwind templates into official stamped multi-page PDF documents.
  - Renders official state monthly attendance registers, full cohort grade tabulation sheets, student ID badges, and bank fee challans with cryptographic verification QR codes.
  - *(Refer to [06_EVENT_DRIVEN_INTEGRATION_AND_HANDSHAKE_BUS](file:///C:/Users/User/Documents/CSG-LMS.wiki/02-System-Architecture-and-Tech-Specs/06_EVENT_DRIVEN_INTEGRATION_AND_HANDSHAKE_BUS.md) for rendering pipeline).*
