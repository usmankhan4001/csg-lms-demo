# LearnHouse · System Architecture & Entity-Relationship Documentation

This document contains the complete **Entity-Relationship Diagram (ERD)**, **C4 Multi-Level Architecture Models**, and **System Workflow Details** for the LearnHouse platform.

---

## 1. Entity-Relationship Diagram (ERD)

The diagram below captures the complete database schema implemented across SQLModel / SQLAlchemy models in `apps/api/src/db/`:

```mermaid
erDiagram
    %% ============================================================
    %% 1. IDENTITY & MULTI-TENANCY
    %% ============================================================
    ORGANIZATION ||--o{ USER_ORGANIZATION : "members"
    USER ||--o{ USER_ORGANIZATION : "memberships"
    ROLE ||--o{ USER_ORGANIZATION : "assigned_to"
    ORGANIZATION ||--o{ ROLE : "defines"
    ORGANIZATION ||--o| ORGANIZATION_CONFIG : "configured_by"
    ORGANIZATION ||--o{ USERGROUP : "owns"
    USERGROUP ||--o{ USERGROUP_USER : "has_members"
    USER ||--o{ USERGROUP_USER : "belongs_to"
    USERGROUP ||--o{ USERGROUP_RESOURCE : "locks/gates"
    USER ||--o{ USER_MFA : "authenticates_with"
    USER ||--o{ USER_AUDIT_EVENT : "generates"
    ORGANIZATION ||--o{ API_TOKEN : "scoped_to"
    ORGANIZATION ||--o{ WEBHOOK : "triggers"
    ORGANIZATION ||--o{ CUSTOM_DOMAIN : "maps_to"

    ORGANIZATION {
        int id PK
        string org_uuid UK
        string slug UK
        string name
        string email
        boolean explore
        boolean is_demo
        json socials
        json links
        json scripts
    }

    USER {
        int id PK
        string user_uuid UK
        string username
        string email UK
        string password
        boolean is_superadmin
        boolean email_verified
        string signup_method
        json details
        json profile
        jsonb extra_metadata
    }

    ROLE {
        int id PK
        int org_id FK
        string role_uuid
        string role_type
        string name
        json rights "Granular CRUD + Own flags"
    }

    USER_ORGANIZATION {
        int id PK
        int user_id FK
        int org_id FK
        int role_id FK
    }

    USERGROUP {
        int id PK
        int org_id FK
        string usergroup_uuid
        string name
        string description
    }

    USERGROUP_RESOURCE {
        int id PK
        int usergroup_id FK
        int org_id FK
        string resource_uuid
    }

    %% ============================================================
    %% 2. COURSE STRUCTURE & LEARNING OBJECTS
    %% ============================================================
    ORGANIZATION ||--o{ COURSE : "hosts"
    COURSE ||--o{ COURSE_CHAPTER : "orders"
    CHAPTER ||--o{ COURSE_CHAPTER : "assigned_to"
    COURSE ||--o{ CHAPTER : "contains"
    CHAPTER ||--o{ ACTIVITY : "contains"
    COURSE ||--o{ ACTIVITY : "contains"
    ACTIVITY ||--o{ BLOCK : "composed_of"
    ACTIVITY ||--o{ ACTIVITY_VERSION : "versioned_as"
    COURSE ||--o{ RESOURCE_AUTHOR : "authored_by"
    USER ||--o{ RESOURCE_AUTHOR : "authors"

    COURSE {
        int id PK
        int org_id FK
        string course_uuid UK
        string name
        string thumbnail_type "image|video|both"
        string thumbnail_image
        string thumbnail_video
        boolean public
        boolean published
        boolean open_to_contributors
        jsonb seo
        jsonb extra_metadata
    }

    CHAPTER {
        int id PK
        int org_id FK
        int course_id FK
        string chapter_uuid UK
        string name
        string lock_type "public|authenticated|restricted"
        jsonb extra_metadata
    }

    ACTIVITY {
        int id PK
        int org_id FK
        int course_id FK
        string activity_uuid UK
        string name
        string activity_type "VIDEO|DOCUMENT|DYNAMIC|ASSIGNMENT|SCORM|CUSTOM"
        string activity_sub_type
        string lock_type "public|authenticated|restricted"
        json content
        json details
        boolean published
        int current_version
        int last_modified_by_id FK
    }

    BLOCK {
        int id PK
        int org_id FK
        int course_id FK
        int chapter_id FK
        int activity_id FK
        string block_uuid
        string block_type "QUIZ|VIDEO|PDF|IMAGE|AUDIO|CUSTOM"
        json content
    }

    %% ============================================================
    %% 3. ASSIGNMENTS, SUBMISSIONS & CERTIFICATIONS
    %% ============================================================
    ACTIVITY ||--o| ASSIGNMENT : "configures"
    ASSIGNMENT ||--o{ ASSIGNMENT_TASK : "consists_of"
    ASSIGNMENT_TASK ||--o{ ASSIGNMENT_TASK_SUBMISSION : "receives"
    USER ||--o{ ASSIGNMENT_TASK_SUBMISSION : "submits"
    ASSIGNMENT ||--o{ ASSIGNMENT_USER_SUBMISSION : "tracks_overall"
    USER ||--o{ ASSIGNMENT_USER_SUBMISSION : "completes"
    COURSE ||--o| CERTIFICATIONS : "awards"
    CERTIFICATIONS ||--o{ CERTIFICATE_USER : "issues"
    USER ||--o{ CERTIFICATE_USER : "earns"

    ASSIGNMENT {
        int id PK
        int org_id FK
        int course_id FK
        int chapter_id FK
        int activity_id FK
        string assignment_uuid UK
        string title
        string grading_type "ALPHABET|NUMERIC|PERCENTAGE|PASS_FAIL|GPA_SCALE"
        boolean auto_grading
        boolean anti_copy_paste
        boolean show_correct_answers
        boolean allow_retries
        int max_retries
        float pass_threshold_percentage
        boolean ungraded
        string solution
        string solution_reveal "NEVER|ON_SUBMISSION|AFTER_GRADING"
        string due_date
    }

    ASSIGNMENT_TASK {
        int id PK
        int assignment_id FK
        string assignment_task_uuid
        string title
        string assignment_type "FILE_SUBMISSION|QUIZ|FORM|CODE|SHORT_ANSWER|NUMBER_ANSWER|CUSTOM"
        json contents
        int max_grade_value
    }

    ASSIGNMENT_TASK_SUBMISSION {
        int id PK
        int user_id FK
        int assignment_task_id FK
        string assignment_task_submission_uuid
        json task_submission
        int grade
        string task_submission_grade_feedback
        boolean manually_graded
    }

    ASSIGNMENT_USER_SUBMISSION {
        int id PK
        int user_id FK
        int assignment_id FK
        string assignmentusersubmission_uuid
        string submission_status "PENDING|SUBMITTED|GRADED|LATE|NOT_SUBMITTED"
        int grade
        int attempt_number
        string overall_feedback
    }

    CERTIFICATIONS {
        int id PK
        int course_id FK
        string certification_uuid UK
        json config
    }

    CERTIFICATE_USER {
        int id PK
        int user_id FK
        int certification_id FK
        string user_certification_uuid UK
    }

    %% ============================================================
    %% 4. PROGRESSION (TRAILS)
    %% ============================================================
    ORGANIZATION ||--o{ TRAIL : "tracks"
    USER ||--o{ TRAIL : "owns"
    TRAIL ||--o{ TRAIL_RUN : "has"
    COURSE ||--o{ TRAIL_RUN : "run_for"
    TRAIL_RUN ||--o{ TRAIL_STEP : "records"
    ACTIVITY ||--o{ TRAIL_STEP : "completed_step"

    TRAIL {
        int id PK
        int org_id FK
        int user_id FK
        string trail_uuid
    }

    TRAIL_RUN {
        int id PK
        int trail_id FK
        int course_id FK
        int user_id FK
        int org_id FK
        string status "IN_PROGRESS|COMPLETED|PAUSED|CANCELLED"
        json data
    }

    TRAIL_STEP {
        int id PK
        int trailrun_id FK
        int activity_id FK
        int user_id FK
        boolean complete
        boolean teacher_verified
        string grade
        json data
    }

    %% ============================================================
    %% 5. COMMUNITY, COLLAB & ENGAGEMENT
    %% ============================================================
    ORGANIZATION ||--o{ COMMUNITY : "manages"
    COURSE ||--o| COMMUNITY : "links_optional"
    COMMUNITY ||--o{ DISCUSSION : "contains"
    USER ||--o{ DISCUSSION : "authors"
    DISCUSSION ||--o{ DISCUSSION_COMMENT : "replies"
    USER ||--o{ DISCUSSION_COMMENT : "comments"
    DISCUSSION ||--o{ DISCUSSION_VOTE : "voted_by"
    DISCUSSION ||--o{ DISCUSSION_REACTION : "reacted_by"

    ORGANIZATION ||--o{ BOARD : "owns"
    BOARD ||--o{ BOARD_MEMBER : "collaborators"
    USER ||--o{ BOARD_MEMBER : "joined"
    ORGANIZATION ||--o{ PLAYGROUND : "hosts"
    COURSE ||--o| PLAYGROUND : "linked_for_rag"
    ORGANIZATION ||--o{ PODCAST : "produces"
    PODCAST ||--o{ PODCAST_EPISODE : "contains"

    COMMUNITY {
        int id PK
        int org_id FK
        int course_id FK
        string community_uuid UK
        string name
        boolean public
        json moderation_words
        json moderation_settings
    }

    DISCUSSION {
        int id PK
        int community_id FK
        int org_id FK
        int author_id FK
        string discussion_uuid UK
        string title
        text content
        string label "general|question|idea|announcement|showcase"
        int upvote_count
        boolean is_pinned
        boolean is_locked
    }

    BOARD {
        int id PK
        int org_id FK
        int created_by FK
        string board_uuid UK
        string name
        boolean public
        blob ydoc_state "Binary Yjs CRDT State"
    }

    BOARD_MEMBER {
        int id PK
        int board_id FK
        int user_id FK
        string role "owner|editor|viewer"
    }

    PLAYGROUND {
        int id PK
        int org_id FK
        int course_id FK
        int created_by FK
        string playground_uuid UK
        string name
        string access_type "public|authenticated|restricted"
        text html_content
    }

    PODCAST {
        int id PK
        int org_id FK
        string podcast_uuid
        string name
        boolean public
        boolean published
        jsonb seo
    }

    PODCAST_EPISODE {
        int id PK
        int podcast_id FK
        int org_id FK
        string episode_uuid
        string title
        string audio_file
        int duration_seconds
        int episode_number
    }
```

---

## 2. C4 Model Architecture Diagrams

### 2.1 C4 Level 1: System Context Diagram

Describes how external actors and cloud services interact with the LearnHouse platform.

```mermaid
flowchart TD
    subgraph Users ["Actors & User Personas"]
        Learner["Learner / Student<br><i>(Browser / Mobile)</i>"]
        Instructor["Instructor / Author<br><i>(Course Creator & Grader)</i>"]
        OrgAdmin["Organization Admin<br><i>(Tenant Management & Config)</i>"]
        SuperAdmin["Superadmin / Host<br><i>(Global Platform Admin)</i>"]
        Visitor["Anonymous Visitor<br><i>(Public catalog & demo)</i>"]
    end

    subgraph LearnHouseSystem ["LearnHouse Platform"]
        LearnHouse["<b>LearnHouse System</b><br>Multi-tenant LMS, Course Builder, Real-time Collab, Interactive Code & AI Teaching Assistant"]
    end

    subgraph ExternalServices ["External Systems & Cloud Services"]
        LLMs["<b>AI / LLM Providers</b><br>(OpenAI, Anthropic, Gemini, Groq, Ollama)"]
        S3Storage["<b>S3 / Object Storage</b><br>(AWS S3, MinIO, Cloudflare R2)"]
        EmailService["<b>Email & Transactional Delivery</b><br>(Resend, SMTP, Loops)"]
        StripePayments["<b>Stripe Billing & Subscriptions</b>"]
        RedisServer["<b>Redis Cache & Pub/Sub</b>"]
        PostgresDB["<b>PostgreSQL Database</b>"]
        ZapierWebhooks["<b>Zapier & Webhook Consumers</b>"]
        SentryMonitoring["<b>Sentry Error Tracking & APM</b>"]
    end

    Learner -->|"Takes courses, submits tasks, discusses"| LearnHouse
    Instructor -->|"Builds courses, grades, hosts podcasts"| LearnHouse
    OrgAdmin -->|"Configures branding, RBAC, billing, usergroups"| LearnHouse
    SuperAdmin -->|"System health, instance metrics, license"| LearnHouse
    Visitor -->|"Explores catalog, tries playground demo"| LearnHouse

    LearnHouse -->|"Generates quiz/magicblocks, RAG search"| LLMs
    LearnHouse -->|"Streams videos, audio, PDFs, SCORM zips"| S3Storage
    LearnHouse -->|"Sends enrollment nudges, OTP, verification"| EmailService
    LearnHouse -->|"Manages tiers, plans, invoices"| StripePayments
    LearnHouse -->|"Reads/writes persistent data"| PostgresDB
    LearnHouse -->|"Realtime state cache, rate limiting, pubsub"| RedisServer
    LearnHouse -->|"Dispatches course & user lifecycle events"| ZapierWebhooks
    LearnHouse -->|"Reports uncaught exceptions & perf spans"| SentryMonitoring
```

---

### 2.2 C4 Level 2: Container Diagram

Describes the individual application containers and how they communicate.

```mermaid
flowchart TB
    ClientBrowser["Client Web Browser / CLI"]

    subgraph Container_LearnHouse ["LearnHouse Deployment Host / Docker / K8s"]
        
        NginxProxy["<b>Nginx Gateway / Reverse Proxy</b><br><i>[Container: C / Nginx]</i><br>Port 80/443<br>Routes /api/v1, /collab, /content, /"]
        
        WebApp["<b>Web Frontend Application</b><br><i>[Next.js 16 + React 19 + Turbopack]</i><br>Port 8000<br>SSR/SSG, TipTap rich text, CodeMirror, Video.js"]
        
        ApiApp["<b>Backend REST API</b><br><i>[FastAPI + Python 3.14 + Uvicorn]</i><br>Port 9000<br>Authentication, RBAC, Course engine, AI Orchestrator, File delivery"]
        
        CollabServer["<b>Realtime Collaboration Server</b><br><i>[Hocuspocus + Bun / Node.js]</i><br>Port 4000<br>WebSocket CRDT state synchronization for live Boards"]
        
        LearnHouseCLI["<b>LearnHouse CLI</b><br><i>[TypeScript + Bun CLI]</i><br>Local stack deployment & management"]
    end

    subgraph DataStorage ["Data & Cache Storage"]
        PostgresContainer[("<b>PostgreSQL / SQLite</b><br>Relational models, JSONB, constraints")]
        RedisContainer[("<b>Redis Broker</b><br>Collab Ydoc cache, rate limiter, session stores")]
        LocalStorage[("<b>Local Media / S3 Store</b><br>Uploaded assets, SCORM zips, documents")]
    end

    ClientBrowser -->|"HTTP / HTTPS"| NginxProxy
    ClientBrowser -->|"WebSocket /collab"| NginxProxy
    LearnHouseCLI -->|"REST API / Docker API"| ApiApp

    NginxProxy -->|"WebSocket Upgrade"| CollabServer
    NginxProxy -->|"GET / POST (/api/v1, /content)"| ApiApp
    NginxProxy -->|"GET / SSR (/)"| WebApp

    WebApp -->|"Internal fetch / Data fetching"| ApiApp
    CollabServer -->|"Auth validation & Debounced DB flush (PUT /ydoc)"| ApiApp
    CollabServer -->|"Ydoc binary state cache"| RedisContainer
    ApiApp -->|"Session cache & rate limits"| RedisContainer
    ApiApp -->|"SQL queries via SQLModel / SQLAlchemy"| PostgresContainer
    ApiApp -->|"Direct read / write"| LocalStorage
```

---

### 2.3 C4 Level 3: Backend API Component Diagram

Details the internal components of the `apps/api` FastAPI service.

```mermaid
flowchart TD
    subgraph FastApiCore ["FastAPI Core Layer (app.py)"]
        GZipMiddleware["Selective GZip Middleware"]
        CorsMiddleware["CORS & EE Middlewares"]
        LifespanEvents["Lifespan Startup / Shutdown Manager"]
        RouterRoot["API Router (/api/v1)"]
    end

    subgraph SecurityModule ["Security & Authentication Layer"]
        JWTAuth["JWT Authenticator & Refresh Tokens"]
        RBAC["RBAC Engine & Permission Evaluator"]
        TokenAuth["API Token & Superadmin Token Guard"]
        PlanGuard["Plan Tier Verification (Personal/Standard/Pro)"]
        MFAGuard["TOTP Multi-Factor Authentication"]
    end

    subgraph FunctionalRouters ["API Routers & Controllers"]
        AuthRouter["auth & mfa routers"]
        OrgsRouter["orgs, custom_domains & config"]
        CoursesRouter["courses, chapters, activities, blocks"]
        AssignRouter["assignments, tasks & auto-grading"]
        CertRouter["certifications & user certificates"]
        TrailsRouter["trails, trail_runs & steps"]
        CommunityRouter["communities & discussions"]
        CollabRouter["boards, playgrounds & ydoc sync"]
        MediaRouter["media, content_files & streaming"]
        AIRouter["ai, magicblocks, rag, scenarios, quiz"]
        EventsRouter["webhooks & zapier integrations"]
    end

    subgraph DomainServices ["Service & Business Logic Layer"]
        CourseService["Course Lifecycle & Versioning Service"]
        GradingService["Auto-Grading & Math Evaluation Engine"]
        ProgressService["Trail Progress & Certificate Trigger"]
        BoardService["Board Yjs State Persistence Service"]
        AIService["AI Service (Multi-provider LLM connector + RAG)"]
        WebhookService["Webhook Dispatcher & Queue Runner"]
        MediaService["Media Handler & S3 Pre-signed URL Manager"]
    end

    subgraph DBRepository ["Data Access & SQLModel Layer"]
        SQLModelEntities["SQLModel DB Models"]
        AlembicMigrations["Alembic Migrations Engine"]
        EnginePool["SQLAlchemy Async / Sync Engine"]
    end

    %% Wiring
    LifespanEvents --> RouterRoot
    RouterRoot --> GZipMiddleware --> CorsMiddleware
    CorsMiddleware --> SecurityModule

    SecurityModule --> FunctionalRouters

    CoursesRouter --> CourseService
    AssignRouter --> GradingService
    TrailsRouter --> ProgressService
    CertRouter --> ProgressService
    CollabRouter --> BoardService
    AIRouter --> AIService
    EventsRouter --> WebhookService
    MediaRouter --> MediaService

    DomainServices --> SQLModelEntities
    SQLModelEntities --> EnginePool
```

---

### 2.4 C4 Level 3: Realtime Collaboration Flow (Sequence Diagram)

Illustrates the real-time CRDT updates across learners, the Hocuspocus server, Redis cache, and PostgreSQL persistence.

```mermaid
sequenceDiagram
    autonumber
    actor LearnerA as Learner A (Browser)
    actor LearnerB as Learner B (Browser)
    participant Nginx as Nginx Proxy
    participant Collab as Collab Server (Hocuspocus)
    participant Redis as Redis Cache
    participant API as FastAPI Backend
    participant DB as PostgreSQL

    LearnerA->>Nginx: WS Connect /collab?token=JWT&doc=board:{uuid}
    Nginx->>Collab: Upgrade connection
    Collab->>Collab: Rate limit verification (per IP)
    Collab->>API: GET /api/v1/boards/{uuid}/membership (Verify Bearer token)
    API-->>Collab: 200 OK (Membership role: editor)
    
    Collab->>Redis: GET collab:ydoc:{uuid}
    alt Cache Miss in Redis
        Collab->>API: GET /api/v1/boards/{uuid}/ydoc (Internal key)
        API->>DB: SELECT ydoc_state FROM board
        DB-->>API: Binary state
        API-->>Collab: Binary ydoc stream
        Collab->>Redis: SETEX collab:ydoc:{uuid} 3600s
    else Cache Hit in Redis
        Redis-->>Collab: Cached binary ydoc state
    end
    Collab-->>LearnerA: Initial Sync step 1 & 2

    LearnerB->>Nginx: WS Connect /collab
    Nginx->>Collab: Authenticate & Join room
    Collab-->>LearnerB: Synced document state

    LearnerA->>Collab: Yjs CRDT update (Draw element / add card)
    Collab->>LearnerB: Broadcast CRDT binary delta
    Collab->>Redis: Immediate write to Redis buffer
    Collab->>Collab: Debounce 5s timer for DB persistence
    
    Note over Collab,API: Debounce timer fires (5000ms)
    Collab->>API: PUT /api/v1/boards/{uuid}/ydoc (Binary stream)
    API->>DB: UPDATE board SET ydoc_state = :data
    DB-->>API: Confirmed
```

---

### 2.5 C4 Level 4: Deployment & Process Topology

Shows how the monolithic container and micro-service stacks are deployed with PM2 and Nginx.

```mermaid
flowchart LR
    subgraph HostServer ["Host Machine / Cloud VM"]
        subgraph Ports ["Published Ports"]
            P80["Port 80 / 443<br>(Public HTTP/HTTPS)"]
            P9000["Port 9000<br>(FastAPI Direct)"]
            P4000["Port 4000<br>(Collab WebSocket)"]
        end

        subgraph DockerContainer ["LearnHouse All-in-One Container (Alpine 3.24)"]
            StartScript["/app/start.sh"]
            PM2["PM2 Process Manager"]
            
            subgraph Processes ["Supervised Processes"]
                NginxProc["Nginx Gateway<br><i>Port 80</i>"]
                NextProc["Next.js Standalone Runner<br><i>Bun / Port 8000</i>"]
                FastApiProc["FastAPI Uvicorn Workers<br><i>Python / Port 9000</i>"]
                CollabProc["Hocuspocus Server<br><i>Bun / Port 4000</i>"]
            end

            StartScript --> PM2
            PM2 --> NginxProc
            PM2 --> NextProc
            PM2 --> FastApiProc
            PM2 --> CollabProc
        end

        subgraph ExternalBackends ["Connected Infrastructure"]
            PG[(PostgreSQL 16+)]
            RD[(Redis 7+)]
            S3[(Object Storage / Local)]
        end
    end

    P80 --> NginxProc
    P9000 --> FastApiProc
    P4000 --> CollabProc

    NginxProc -->|Internal HTTP| NextProc
    NginxProc -->|Internal HTTP| FastApiProc
    NginxProc -->|Internal WS| CollabProc

    FastApiProc --> PG
    FastApiProc --> RD
    FastApiProc --> S3
    CollabProc --> RD
    CollabProc --> FastApiProc
```
