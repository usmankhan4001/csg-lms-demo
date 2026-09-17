# System Architecture: Real-Time Collaboration & CRDT Architecture

**Document Reference:** CSG-ARCH-005  
**Target Audience:** Frontend Engineers, Realtime Backend Engineers  
**Classification:** Technical Architecture Specification  
**Status:** Canonical Implementation Baseline (LearnHouse Hocuspocus + Yjs)  

---

## 1. Technical Premise: Conflict-Free Replicated Data Types (CRDTs)

Collaborative learning tools—such as interactive classroom whiteboards (`BOARD`), simultaneous document editing, and multi-user diagramming—cannot rely on traditional HTTP REST requests or optimistic database locking. Network latencies and simultaneous edits cause race conditions, lost data, and jarring UI overwrites.

CSG-LMS inherits the high-performance real-time collaboration engine from **LearnHouse** (`apps/collab`), utilizing the **Hocuspocus WebSocket server** and **Yjs CRDTs (Conflict-Free Replicated Data Types)** with Redis caching and debounced PostgreSQL persistence.

---

## 2. Real-Time Collaboration Sequence & Architecture

```mermaid
sequenceDiagram
    autonumber
    actor StudentA as Student A (Browser)
    actor StudentB as Student B (Browser)
    participant Nginx as Nginx Proxy
    participant Collab as Collab Server (Hocuspocus)
    participant Redis as Redis Buffer Cache
    participant API as FastAPI Backend
    participant DB as PostgreSQL

    StudentA->>Nginx: WS Connect /collab?token=JWT&doc=board:{uuid}
    Nginx->>Collab: Upgrade connection
    Collab->>Collab: Token auth & rate limit verification
    Collab->>API: GET /api/v1/boards/{uuid}/membership
    API-->>Collab: 200 OK (Role: Editor)
    
    Collab->>Redis: GET collab:ydoc:{uuid}
    alt Cache Miss in Redis
        Collab->>API: GET /api/v1/boards/{uuid}/ydoc
        API->>DB: SELECT ydoc_state FROM board
        DB-->>API: Binary state
        API-->>Collab: Binary ydoc stream
        Collab->>Redis: SETEX collab:ydoc:{uuid} 3600s
    else Cache Hit in Redis
        Redis-->>Collab: Cached binary ydoc state
    end
    Collab-->>StudentA: Initial document sync

    StudentB->>Nginx: WS Connect /collab
    Nginx->>Collab: Authenticate & Join room
    Collab-->>StudentB: Synced document state

    StudentA->>Collab: Yjs CRDT binary delta (Draw line / add card)
    Collab->>StudentB: Broadcast binary delta (<20ms)
    Collab->>Redis: Immediate write to Redis buffer
    Collab->>Collab: Reset 5-second debounce timer
    
    Note over Collab,API: Debounce timer fires (5000ms idle)
    Collab->>API: PUT /api/v1/boards/{uuid}/ydoc (Binary stream)
    API->>DB: UPDATE board SET ydoc_state = :data
    DB-->>API: Persisted
```

---

## 3. Key Technical Specifications

### 3.1 Binary Yjs State Compression
- The collaborative canvas state is maintained in-memory as an optimized Yjs binary document (`Uint8Array`).
- Diffs transmitted over WebSockets are pure binary update vectors (typically <1 KB per mutation), achieving sub-20ms broadcast latencies even across mobile 4G networks.

### 3.2 Debounced Database Persistence
- High-frequency drawing events (e.g., freehand pen strokes generating 60 events/second) never hit the PostgreSQL database directly.
- The Hocuspocus daemon buffers updates in Redis and applies a **5-second sliding debounce timer**. Once whiteboard drawing activity pauses for 5 seconds, the accumulated binary state is flushed via `PUT /api/v1/boards/{uuid}/ydoc` to the `board.ydoc_state` column.

### 3.3 Ephemeral Awareness (Presence & Cursors)
- User mouse cursor coordinates, selection bounding boxes, and typing indicators are handled via Yjs Ephemeral Awareness states.
- Awareness states are broadcast directly across active WebSocket clients and are intentionally never persisted to database disk, minimizing storage overhead.

---

## 4. Real-Time Interactive Live Classes & WebRTC Media Architecture

### 4.1 The Need for a Dedicated WebRTC Media Server (LiveKit SFU)
While Hocuspocus and WebSockets excel at synchronized CRDT text and vector whiteboard state, real-time video and audio streaming requires raw UDP packet routing, real-time bandwidth probing, congestion control, and video simulcasting.

Running live video through FastAPI would saturate Python's ASGI event loop, while Hocuspocus lacks WebRTC media protocol stacks (RTP/RTCP, SRTP, ICE/STUN/TURN).

CSG-LMS integrates a dedicated **LiveKit WebRTC SFU (Selective Forwarding Unit)** daemon running alongside FastAPI and Hocuspocus:

| Real-Time Capability | Responsible Engine | Technology Stack | Core Operational Role |
|---|---|---|---|
| **Live Video & Audio SFU** | `LiveKit Server` | Go / WebRTC / Pion | Receives webcam, mic, and screen-sharing streams; forwards to subscribers via adaptive simulcast. |
| **Session Authorization & Tokens** | `FastAPI Backend` | Python / SQLModel | Validates timetable slots, checks student enrollment, and mints cryptographically signed LiveKit JWTs. |
| **Interactive Classroom Whiteboard** | `Hocuspocus Server`| Bun / Yjs CRDT | Manages the collaborative whiteboard canvas modal within the live classroom. |
| **Automated Server Recording** | `LiveKit Egress` | Headless Chrome / FFmpeg | Joins session silently, renders composite grid, transcodes to HLS/MP4, and uploads to S3/MinIO. |

### 4.2 End-to-End Live Class Operational Sequence

```mermaid
sequenceDiagram
    autonumber
    actor Teacher as Teacher (Host)
    actor Student as Student (Participant)
    participant Web as Next.js Web Portal
    participant API as FastAPI Backend
    participant LK as LiveKit SFU Server
    participant Egress as LiveKit Egress Recorder
    participant S3 as S3 / MinIO Storage
    participant DB as PostgreSQL 16

    Teacher->>Web: Clicks "Launch Virtual Classroom"
    Web->>API: POST /api/v1/live-classes/{id}/token (Teacher JWT)
    API->>DB: Verify teacher assignment & timetable slot
    API->>API: Mint LiveKit Token (canPublish: true, canPublishData: true)
    API-->>Web: Return LiveKit Room Token & Room UUID
    Teacher->>LK: Connect WebRTC via LiveKit Token (Port 7880 / UDP 50000-60000)
    LK-->>Teacher: Room Created, Active Publisher

    Student->>Web: Clicks "Join Live Class" from Timetable
    Web->>API: POST /api/v1/live-classes/{id}/token (Student JWT)
    API->>DB: Verify course enrollment
    API->>API: Mint LiveKit Token (canPublish: true, canSubscribe: true)
    API-->>Web: Return Student Token
    Student->>LK: Connect WebRTC
    LK-->>Teacher: ParticipantJoined Event
    LK-->>Student: Stream Teacher Video & Audio Feed

    Note over API,Egress: Automated Server-Side Recording
    LK->>API: Webhook: room_started
    API->>Egress: StartRoomCompositeEgress(layout: 'speaker-dark', output: S3)
    Egress->>LK: Join room as headless recorder
    Egress->>Egress: Record & transcode composite stream

    Teacher->>Web: Toggles "Collaborative Whiteboard" (Opens Hocuspocus CRDT canvas)
    Student->>Web: Collaborates live on whiteboard

    Teacher->>Web: Clicks "End Meeting for All"
    Web->>API: POST /api/v1/live-classes/{id}/end
    API->>LK: DeleteRoom
    LK->>API: Webhook: participant_left (Logs exact active minutes)
    API->>DB: Record attendance (≥80% active minutes = Present)
    Egress->>S3: Upload composite MP4 & HLS playlist
    Egress->>API: Webhook: egress_ended (recording_url, file_size, duration)
    API->>DB: Insert live_recordings row (Linked to LMS Course Chapter)
```

---

## 5. Classroom UI Architecture & Automated Composite Archival

### 5.1 Video-First Layout with Collapsible Sidebars
The live classroom adopts an institutional video-first layout (similar to Zoom / Google Meet):

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ [CSG-LMS] Grade 10 Biology · Period 3: Cell Mitosis          [Rec ● 00:42:15] [Leave] │
├────────────────────────────────────────────────────────────┬───────────────────────────┤
│                                                            │ 🗪 CHAT & Q&A | 📊 POLLS  │
│  ┌──────────────────────────┐  ┌────────────────────────┐  ├───────────────────────────┤
│  │                          │  │                        │  │ [Q&A Thread]              │
│  │     TEACHER VIDEO        │  │     STUDENT VIDEO 1    │  │ Michael: "Is ATP consumed │
│  │   (Active Speaker)       │  │                        │  │ during anaphase?"         │
│  │                          │  │                        │  │                           │
│  │  ┌──────────────────────────┐  ┌────────────────────────┐  │ [Active Live Poll]        │
│  │  │     STUDENT VIDEO 2      │  │     STUDENT VIDEO 3    │  │ "Identify the phase:"     │
│  │  └──────────────────────────  └────────────────────────┘  │ (•) Metaphase  [68%]      │
│  │                                                            │                           │
│  │                                                            │ [Open Whiteboard Modal]   │
│  │                                                            │ ↳ Launches Hocuspocus CRDT│
│  ├────────────────────────────────────────────────────────────┴───────────────────────────┤
│  │  [🎤 Mute] [📹 Camera] [🖥️ Share Screen] [✋ Raise Hand] [🎨 Whiteboard] [👥 26 Students]│
│  └────────────────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Automatic Attendance & Asynchronous Course Archive
1. **Zero-Friction Attendance:** WebRTC join/leave timestamps determine active instructional time. Students with $\ge 80\%$ duration are marked Present automatically in the day's attendance register.
2. **Automated LMS Archival:** Within 10 minutes of class conclusion, the LiveKit Egress recorder uploads the finalized composite MP4 and HLS stream to S3/MinIO and links the recording to the corresponding Course Chapter in the student LMS portal for asynchronous revision.
