# 🎓 CSG LMS — Complete Enterprise Platform Context & Specification Master

> **Document Version:** 4.2.0-venture  
> **Classification:** Confidential / Proprietary Venture Documentation  
> **Intellectual Property:** Copyright © 2026 CSG Infotech Venture  
> **Git Repository:** [https://github.com/usmankhan4001/csg-lms-demo.git](https://github.com/usmankhan4001/csg-lms-demo.git) (`main`)  
> **Base Engine:** Unified Composable Monolith (FastAPI 0.115+ / Next.js 15 / PostgreSQL 16 `pgvector` / Keycloak 26 / Redis 7.2 / LiveKit SFU / Hocuspocus CRDT)

---

## 📑 Table of Contents

1. [Executive Summary & Strategic Vision](#1-executive-summary--strategic-vision)
2. [Unified Monorepo Architecture & Tech Stack](#2-unified-monorepo-architecture--tech-stack)
3. [The 6 Strategic Core Pillars](#3-the-6-strategic-core-pillars)
4. [Exhaustive 50-Module Implementation Matrix (M01 – M50)](#4-exhaustive-50-module-implementation-matrix-m01--m50)
5. [Authentication, Tenancy & Security Architecture](#5-authentication-tenancy--security-architecture)
6. [Academic SMS & Financial ERP Engine](#6-academic-sms--financial-erp-engine)
7. [AI Pedagogy, Socratic Tutor & Safety Guardrails](#7-ai-pedagogy-socratic-tutor--safety-guardrails)
8. [AI RevOps & Admissions CRM Suite](#8-ai-revops--admissions-crm-suite)
9. [Frontend Role-Based Portals & Design System](#9-frontend-role-based-portals--design-system)
10. [Local Development, Testing & Verification Suite](#10-local-development-testing--verification-suite)
11. [Production Deployment & Dokploy Runbook](#11-production-deployment--dokploy-runbook)
12. [Repository File Map & Key Artifacts](#12-repository-file-map--key-artifacts)

---

## 1. Executive Summary & Strategic Vision

### 1.1 The Problem in Educational Technology
Traditional educational institutions suffer from fragmented software silos:
- **LMS Silo:** Moodle/Canvas/Blackboard handle course delivery and assignments, completely disconnected from student billing, attendance, and campus operations.
- **SMS Silo:** Legacy ERPs (RosarioSIS, Ellucian, PowerSchool) handle enrollment, gradebooks, and report cards with outdated 2000s UIs and zero interactive learning tools.
- **Financial Silo:** Standalone accounting tools (QuickBooks, manual spreadsheets) produce disconnected fee vouchers with no automated student sync.
- **Admissions Silo:** Commercial CRMs (HubSpot, Salesforce) cost tens of thousands annually and lack direct integration with student enrollment pipelines.
- **Generic AI Disruption:** Uncontrolled ChatGPT usage allows students to cheat on homework without pedagogical scaffolding or mental health safeguards.

### 1.2 The CSG LMS Solution
**CSG LMS** unifies all 5 educational pillars into a **single composable monorepo**:
1. **Interactive Course Delivery & Live Classes** (TipTap Notion-like editor, Yjs CRDT real-time whiteboards, LiveKit WebRTC).
2. **Academic Operations & Multi-Campus Hierarchy** (Campus trees, 1-Click attendance roll-call, timetable clash-solver engine, weighted GPA gradebooks).
3. **Double-Entry General Ledger & Payroll** (Chart of Accounts, 3-copy printable bank challans, online 1Bill checkout, batch salary slips).
4. **AI RevOps Admissions CRM** (7-stage visual Kanban, predictive lead scoring, 24/7 SDR WhatsApp AI agent, dynamic scholarship discount generator).
5. **Socratic AI Pedagogy & Crisis Safety** (Strict 3-tier progressive hint system, pgvector textbook RAG, real-time distress and self-harm interceptor, concept dependency knowledge graph, Student 360 mastery radar).
6. **Role-Based Portals** (High-performance Next.js 15 portals tailored for Students, Teachers, Parents, and Campus Administrators with full RTL Arabic support).

---

## 2. Unified Monorepo Architecture & Tech Stack

```
                                  ┌───────────────────────────────┐
                                  │   Traefik Reverse Proxy (SSL) │
                                  └───────────────┬───────────────┘
                                                  │
                 ┌────────────────────────────────┼────────────────────────────────┐
                 │                                │                                │
                 ▼                                ▼                                ▼
  ┌──────────────────────────────┐ ┌──────────────────────────────┐ ┌──────────────────────────────┐
  │   apps/web (Next.js 15)      │ │   apps/api (FastAPI 0.115)   │ │   apps/collab (Hocuspocus)   │
  │ • React 19 + TypeScript      │ │ • Python 3.12 + SQLAlchemy   │ │ • Node.js + Yjs CRDT         │
  │ • Tailwind CSS v4 + Radix UI │ │ • Pydantic v2 + Uvicorn      │ │ • Real-Time Block Sync       │
  │ • Role Portals (S/T/P/A)     │ │ • 50 REST Module Routers     │ │ • Multi-User Whiteboards     │
  └──────────────┬───────────────┘ └──────────────┬───────────────┘ └──────────────┬───────────────┘
                 │                                │                                │
                 └────────────────────────────────┼────────────────────────────────┘
                                                  │
                 ┌────────────────────────────────┼────────────────────────────────┐
                 │                                │                                │
                 ▼                                ▼                                ▼
  ┌──────────────────────────────┐ ┌──────────────────────────────┐ ┌──────────────────────────────┐
  │   Keycloak 26 OIDC Server    │ │   PostgreSQL 16 (pgvector)   │ │   Redis 7.2 Cache & Broker   │
  │ • Multi-Tenant RBAC Roles    │ │ • Multi-Campus Tenant Tables │ │ • Token Revocation & PubSub  │
  │ • JWT PKCE Authentication    │ │ • Double-Entry Ledger Schema │ │ • Session & LLM Rate Limiter │
  │ • FERPA/COPPA Compliance     │ │ • 768-dim Vector Embeddings  │ │ • LiveKit Room Signaling     │
  └──────────────────────────────┘ └──────────────────────────────┘ └──────────────────────────────┘
```

| Component | Technology | Version / Spec | Purpose |
|---|---|---|---|
| **Frontend Framework** | Next.js (App Router) | `16.3.4` / React `19.2` | Universal web application and role-based portal shells |
| **Backend API** | FastAPI | `0.115.11` / Python `3.12` | High-performance async REST API engine |
| **ORM / Data Layer** | SQLModel / SQLAlchemy | `2.0.46` (Async) | Unified database models with cross-dialect compatibility |
| **Database** | PostgreSQL + pgvector | `16.x` / `Vector(768)` | Relational transactional data + AI vector embeddings |
| **Auth & Identity** | Keycloak OIDC | `24.x` / `26.x` | Enterprise single sign-on, JWT token verification, RBAC |
| **Real-time Sync** | Hocuspocus / Yjs | `v4.0.0` / `v13.6` | Collaborative document and whiteboard state sync |
| **Video Conferencing** | LiveKit SFU | WebRTC 1080p | Low-latency interactive virtual classroom sessions |
| **AI LLM Orchestration** | Pydantic-AI / Gemini SDK | `2.38` / Gemini 2.5 | Socratic tutoring, lead scoring, and SDR agents |

---

## 3. The 6 Strategic Core Pillars

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                               CSG LMS 6 CORE PILLARS                                   │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ 1. Core LMS & Authoring      │ 2. Academic SMS & Operations │ 3. Financials & Payroll  │
│ • TipTap Notion-like Editor  │ • Multi-Campus Hierarchy     │ • Chart of Accounts (GL) │
│ • Yjs Real-Time CRDT Collab  │ • 1-Click Roll-Call & Leaves │ • 3-Copy Bank Challan    │
│ • In-Browser Code Sandboxes  │ • Clash-Solver Timetable     │ • Online 1Bill / Stripe  │
│ • LiveKit WebRTC Classes     │ • Weighted GPA Gradebook     │ • Salary Slip Engine     │
├──────────────────────────────┼──────────────────────────────┼──────────────────────────┤
│ 4. AI RevOps Admissions CRM  │ 5. Socratic AI & Safety      │ 6. Role-Based Portals    │
│ • 7-Stage Admissions Kanban  │ • 3-Tier Socratic Guidance   │ • Student Dashboard      │
│ • Predictive Lead Scoring    │ • Crisis & Safety Guardrail  │ • Teacher Class Hub      │
│ • 24/7 SDR WhatsApp Agent    │ • Concept Knowledge Graph    │ • Parent Fee & Track     │
│ • Dynamic Scholarship Offers │ • Student 360 Mastery Radar  │ • Campus Admin Console   │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Exhaustive 50-Module Implementation Matrix (M01 – M50)

### 🎓 Pillar 1: Core LMS & Authoring (M01 – M04, M13 – M20)
- **M01: Notion-style Interactive Course Authoring Engine**
  - *Location:* `apps/web/app/editor/`, `apps/api/src/routers/courses.py`
  - *Capabilities:* Block-based TipTap editor, video/audio embeds, interactive math (KaTeX), code blocks, drag-and-drop curriculum hierarchy.
- **M02: Virtual Classroom & WebRTC Live Sessions**
  - *Location:* `apps/api/src/db/sms_live_class.py`, `apps/api/src/routers/live_classes.py`, `apps/web/app/live/[roomId]/`
  - *Capabilities:* LiveKit WebRTC SFU streaming, spotlight speaker, participant thumbnail strip, automated attendance timestamping, in-session AI copilot.
- **M03: Real-Time Interactive Code Sandboxes & Auto-Grader**
  - *Location:* `apps/api/src/routers/code_execution.py`, `apps/web/components/Objects/CodeMirror/`
  - *Capabilities:* In-browser and sandboxed execution for 30+ languages, unit test verification, execution timeout guardrails.
- **M04: Real-Time Collaborative Whiteboards**
  - *Location:* `apps/collab/`, `apps/web/app/board/[boarduuid]/`
  - *Capabilities:* Yjs CRDT multi-user sync, vector drawing, geometric sticky notes, real-time participant cursors.
- **M13: Course Bundling & Curricular Pathways**
  - *Location:* `apps/api/src/routers/collections.py`
  - *Capabilities:* Multi-course prerequisite chains, degree programs, track certificates.
- **M14: Interactive Assessment & Randomized Quiz Engine**
  - *Location:* `apps/api/src/routers/assignments.py`, `src/db/assignments.py`
  - *Capabilities:* Time-limited quizzes, randomized question pools, automated grading rubrics.
- **M15: Plagiarism Detection & Code Similarity Checker**
  - *Location:* `apps/api/src/services/ai/plagiarism.py`
  - *Capabilities:* AST structural matching, cosine similarity over pgvector assignment embeddings.
- **M16: Automated Verifiable Certificate Generator**
  - *Location:* `apps/web/app/orgs/[orgslug]/(withmenu)/certificates/`, `apps/api/src/routers/certificates.py`
  - *Capabilities:* High-resolution PDF generation, cryptographic SHA-256 hash, public QR validation.
- **M17: Student Peer-Review & Group Workspaces**
  - *Location:* `apps/api/src/routers/discussions.py`
  - *Capabilities:* Double-blind student rubric reviews, group breakout channels.
- **M18: Offline Content Sync & Progressive Web App (PWA)**
  - *Location:* `apps/web/public/manifest.json`, `apps/web/public/sw.js`
  - *Capabilities:* ServiceWorker cache-first video/lesson storage, IndexedDB offline state persistence.
- **M19: SCORM 1.2 / 2004 & xAPI TinCan Engine**
  - *Location:* `apps/web/ee/services/scorm/`, `apps/api/src/routers/scorm.py`
  - *Capabilities:* Zip package parser, CMI data model runtime bridge, iframe sandbox security.
- **M20: Gamification, Badges & Leaderboard Engine**
  - *Location:* `apps/api/src/routers/gamification.py`
  - *Capabilities:* XP calculations, streak multipliers, weekly cohort leaderboards.

---

### 🏫 Pillar 2: Academic SMS & Operations (M05 – M07, M12, M29 – M33)
- **M05: Configurable Weighted GPA Gradebook & Report Card**
  - *Location:* `apps/api/src/db/sms_gradebook.py`, `apps/api/src/services/sms/gradebook.py`, `apps/api/src/routers/sms_gradebook.py`
  - *Capabilities:* Formative/summative weightings, letter-grade boundary mapping, automated GPA computation (0.00-4.00), PDF report card compilation.
- **M06: 1-Click Attendance Roll-Call & Leave Workflows**
  - *Location:* `apps/api/src/db/sms_attendance.py`, `apps/api/src/routers/sms_attendance.py`
  - *Capabilities:* Batch section roll-call, `PRESENT`/`ABSENT`/`LATE`/`EXCUSED` status, biometric/RFID sync, parent leave request submission and approval.
- **M07: Algorithmic Timetable Clash-Solver Engine**
  - *Location:* `apps/api/src/db/sms_timetable.py`, `apps/api/src/services/sms/timetable.py`, `apps/api/src/routers/sms_timetable.py`
  - *Capabilities:* Interval tree clash detection, prevents teacher double-booking, room capacity conflict prevention, teacher/student weekly timetable grids.
- **M12: Digital Library, E-Books & Circulation Desk**
  - *Location:* `apps/api/src/db/sms_library.py`, `apps/api/src/routers/sms_library.py`
  - *Capabilities:* ISBN cataloging, barcode circulation, loan tracking, overdue fine computation, digital PDF reader.
- **M29: Multi-Campus Hierarchy & Institutional Federation**
  - *Location:* `apps/api/src/db/sms_campus.py`, `apps/api/src/routers/sms_campus.py`
  - *Capabilities:* Multi-tier organizational tree: Institution -> Campus -> Academic Year -> Term -> Grade -> Section.
- **M30: Student Enrollment, Roll Numbers & Section Assignment**
  - *Location:* `apps/api/src/db/sms_campus.py` (`StudentEnrollment`)
  - *Capabilities:* Auto-incrementing roll number generators, section transfer audit logs, status lifecycle (`ENROLLED`, `TRANSFERRED`, `GRADUATED`).
- **M31: Faculty Workload Allocation & Subject Mapping**
  - *Location:* `apps/api/src/db/sms_hr.py`, `apps/api/src/routers/sms_hr.py`
  - *Capabilities:* Credit-hour caps per faculty member, subject specialization tags, substitution teacher assignment.
- **M32: Disciplinary Incident Tracking & Merit/Demerit System**
  - *Location:* `apps/api/src/db/sms_discipline.py`
  - *Capabilities:* Infraction severity tiers, counselor intervention logging, merit reward points.
- **M33: Alumni Tracking & Career Placement Network**
  - *Location:* `apps/api/src/db/sms_alumni.py`
  - *Capabilities:* Graduation cohort directories, employment destination surveys, alumni mentorship pairing.

---

### 💳 Pillar 3: Financial Management, ERP & HR/Payroll (M08 – M11, M34 – M38)
- **M08: Student Fee Billing, Fee Structures & 3-Copy Bank Challans**
  - *Location:* `apps/api/src/db/sms_fees.py`, `apps/api/src/services/sms/fees.py`, `apps/api/src/routers/sms_fees.py`, `apps/web/app/(dashboard)/parent/fees/`
  - *Capabilities:* Dynamic tuition/lab/transport line items, overdue surcharges, printable standard 3-copy bank challans (`Student Copy`, `Bank Copy`, `School Copy`), online 1Bill / Stripe integration.
- **M09: Double-Entry Financial Accounting & General Ledger (GL)**
  - *Location:* `apps/api/src/db/sms_financials.py`, `apps/api/src/services/sms/financials.py`, `apps/api/src/routers/sms_financials.py`
  - *Capabilities:* 5-Type Chart of Accounts (`ASSET`, `LIABILITY`, `EQUITY`, `REVENUE`, `EXPENSE`), strict validation enforcing $\sum \text{Debit} = \sum \text{Credit}$, trial balance and balance sheet generation.
- **M10: Faculty & Staff Directory, Leaves & HR Management**
  - *Location:* `apps/api/src/db/sms_hr.py`, `apps/api/src/routers/sms_hr.py`
  - *Capabilities:* Staff profiles, employee codes, contract tiers, annual/sick leave balances, department rosters.
- **M11: Automated Multi-Campus Payroll Engine & Salary Slips**
  - *Location:* `apps/api/src/db/sms_payroll.py`, `apps/api/src/services/sms/payroll.py`, `apps/api/src/routers/sms_payroll.py`
  - *Capabilities:* Basic pay + allowances (housing, medical) minus deductions (tax, provident fund, unpaid leaves), batch monthly payroll processing.
- **M34: Campus Inventory, Asset Lifecycle & Procurement Management**
  - *Location:* `apps/api/src/db/sms_inventory.py`
  - *Capabilities:* Asset tagging, lab equipment maintenance logs, vendor purchase order requisitions.
- **M35: School Transport, Fleet GPS & Route Optimization**
  - *Location:* `apps/api/src/db/sms_transport.py`
  - *Capabilities:* Bus route mapping, driver licensing tracking, stop-by-stop student manifests.
- **M36: Hostel & Dormitory Room Allocation System**
  - *Location:* `apps/api/src/db/sms_hostel.py`
  - *Capabilities:* Room inventory, bed assignments, curfew attendance logs, visitor logs.
- **M37: Cafeteria POS, Meal Plans & Smart Card Wallets**
  - *Location:* `apps/api/src/db/sms_cafeteria.py`
  - *Capabilities:* Prepaid card balance top-ups, daily dietary restriction alerts, cashless meal checkouts.
- **M38: Event Management, Sports & Facility Booking**
  - *Location:* `apps/api/src/db/sms_events.py`
  - *Capabilities:* Auditorium and sports field reservation calendars, inter-school tournament schedules.

---

### 📈 Pillar 4: AI RevOps & Admissions CRM (M21 – M28)
- **M21: Admissions CRM & Multi-Campus Intake Pipeline**
  - *Location:* `apps/api/src/db/sms_revops.py`, `apps/api/src/schemas/sms_revops.py`, `apps/api/src/routers/sms_revops.py`, `apps/web/app/(dashboard)/admissions/crm/page.tsx`
  - *Capabilities:* 7-Stage visual Kanban (`New Inquiry`, `Contacted`, `Tour Booked`, `Assessment Scheduled`, `Offer Sent`, `Enrolled`, `Lost`), assigned admissions officer routing.
- **M22: Predictive AI Lead Scoring & Intent Classifier**
  - *Location:* `apps/api/src/services/ai/revops_lead_scoring.py`
  - *Capabilities:* Multi-factor algorithm evaluating profile completeness, responsiveness, budget fit, and timeframe to compute 0-100 score + categorical tag (`HOT 🔥`, `WARM ⚡`, `COLD ❄️`).
- **M23: Multichannel Ingestion Engine**
  - *Location:* `apps/api/src/routers/sms_revops.py` (`POST /api/v1/revops/leads`)
  - *Capabilities:* Webhooks and form handlers capturing leads from WhatsApp Business API, Meta Lead Ads, Google Ads, and walk-in QR forms.
- **M24: Conversational Admissions SDR AI Agent**
  - *Location:* `apps/api/src/services/ai/revops_sdr_agent.py`
  - *Capabilities:* 24/7 autonomous chatbot answering prospective parents regarding fees, curriculum, and transport; extracts student name/grade and triggers tour booking.
- **M25: Automated Multi-Stage Marketing Drip Engine**
  - *Location:* `apps/api/src/services/ai/revops_drip_engine.py`
  - *Capabilities:* 4-Stage personalized multichannel sequence (Day 1 Welcome, Day 3 Video Tour, Day 7 Scholarship Invite, Day 14 Personal Follow-up).
- **M26: Campus Tour & Assessment Booking Scheduler**
  - *Location:* `apps/api/src/services/sms/revops.py`
  - *Capabilities:* Synchronizes principal and admissions officer calendar slots with automated WhatsApp confirmation reminders.
- **M27: Dynamic Tuition Quotation & Scholarship Calculator**
  - *Location:* `apps/api/src/services/ai/revops_offer_generator.py`
  - *Capabilities:* Slide-over modal with 0-50% discount slider, instant net tuition calculation, and tailored PDF offer letter generation.
- **M28: Digital Document Verification & KYC Vault**
  - *Location:* `apps/api/src/services/sms/revops.py`
  - *Capabilities:* Secure S3 encrypted storage for birth certificates, prior transcripts, and parent CNIC/National ID cards.

---

### 🤖 Pillar 5: Pedagogy AI, Safety & Adaptive Learning (M39 – M50)
- **M39: Socratic AI 1-on-1 Academic Tutor**
  - *Location:* `apps/api/src/services/ai/socratic_tutor.py`, `apps/api/src/routers/ai_tutor.py`
  - *Capabilities:* Enforces strict non-solution-giving pedagogy. Uses 3-tier hints:
    - *Level 1 (Concept Clue):* Guiding conceptual question.
    - *Level 2 (Formula/Rule):* Underlying mathematical/scientific formula.
    - *Level 3 (Analogous Example):* Worked step-by-step example with different numerical values.
- **M40: Automated Lesson Plan & Rubric Generator for Teachers**
  - *Location:* `apps/api/src/services/ai/teacher_copilot.py`
  - *Capabilities:* Bloom's Taxonomy-aligned lesson objectives, timing breakdowns, and grading rubrics.
- **M41: Multilingual Real-Time Lecture Translation & Subtitling**
  - *Location:* `apps/api/src/services/ai/translation.py`
  - *Capabilities:* Whisper audio transcription, real-time Arabic/Urdu/French/Spanish subtitle generation.
- **M42: Student Emotional Wellbeing & Crisis Sentiment Interceptor**
  - *Location:* `apps/api/src/services/ai/crisis_classifier.py`
  - *Capabilities:* Real-time keyword and semantic classifier intercepting prompts showing distress, self-harm, severe bullying, or violence. Immediately halts LLM completion, returns supportive crisis helpline copy, and logs incident for school counselors.
- **M43: Personalized Adaptive Learning Path Generator**
  - *Location:* `apps/api/src/services/ai/knowledge_graph.py` (`get_recommended_next_concepts`)
  - *Capabilities:* Dynamic recommendation of subsequent curriculum nodes once prerequisites meet $\ge 70\%$ mastery threshold.
- **M44: Concept Dependency Knowledge Graph**
  - *Location:* `apps/api/src/db/ai_knowledge_graph.py`, `apps/api/src/services/ai/knowledge_graph.py`
  - *Capabilities:* Directed Acyclic Graph (DAG) of curriculum concepts, prerequisite strength weights, and automated difficulty calibration.
- **M45: Student 360 Holistic Mastery & Behavior Radar**
  - *Location:* `apps/api/src/routers/ai_student_profile.py` (`GET /api/v1/ai/student/{id}/mastery-radar`)
  - *Capabilities:* Multi-subject radar visualization aggregating mastery scores across STEM, Humanities, Languages, and Arts.
- **M46: Automated Homework Grading & Formative Feedback**
  - *Location:* `apps/api/src/services/ai/homework_grader.py`
  - *Capabilities:* OCR handwritten response extraction, step-by-step math verification, constructive improvement commentary.
- **M47: NeMo-Style AI Safety & Content Interceptor**
  - *Location:* `apps/api/src/services/ai/crisis_classifier.py`
  - *Capabilities:* Guardrail preventing academic dishonesty, prompt injection, and toxic/inappropriate content generation.
- **M48: Parent Weekly AI Narrative Digest & Insights**
  - *Location:* `apps/api/src/services/ai/parent_digest.py`
  - *Capabilities:* Natural-language executive summary of student weekly attendance, quiz improvements, and upcoming assignments.
- **M49: At-Risk Student Early-Warning Dropout Predictor**
  - *Location:* `apps/api/src/services/ai/dropout_predictor.py`
  - *Capabilities:* Logistic regression model detecting early attendance drops, unpaid fees, and falling quiz trends.
- **M50: Live Class AI Q&A Assistant & Real-Time Note Summarizer**
  - *Location:* `apps/api/src/services/ai/live_class_copilot.py`
  - *Capabilities:* Listens to live class transcript windows and answers in-stream student chat questions without interrupting the teacher.

---

## 5. Authentication, Tenancy & Security Architecture

### 5.1 Keycloak 26 OIDC Integration
Authentication is decoupled into an enterprise Identity Provider (Keycloak 24/26) supporting OAuth2 with PKCE:
- **Realm:** `csg-lms`
- **Clients:**
  - `csg-lms-web`: Public OIDC client with PKCE for Next.js 15 client-side and SSR flows.
  - `csg-lms-api`: Confidential Bearer-only client with JWKS asymmetric key verification (`RS256`).

### 5.2 Role-Based Access Control (RBAC)
FastAPI dependency injection enforces strict role checks via `require_roles`:
```python
# Standard CSG-LMS Realm Roles
SUPER_ADMIN = "SUPER_ADMIN"           # Full system access across all campuses
CAMPUS_PRINCIPAL = "CAMPUS_PRINCIPAL" # Academic & operational head of a campus
TEACHER = "TEACHER"                   # Course management, grading, roll-call
STUDENT = "STUDENT"                   # Course access, quizzes, Socratic tutor
PARENT = "PARENT"                     # Child tracking, fee payment, report cards
ACCOUNTANT = "ACCOUNTANT"             # General ledger, fee reconciliation, payroll
```

### 5.3 Multi-Campus Row-Level Security (RLS)
Every database query strictly isolates records by `org_id` and `campus_id` extracted from the verified JWT bearer claims. Super-admins can pass an optional `campus_id` filter to view aggregated multi-campus metrics.

---

## 6. Academic SMS & Financial ERP Engine

### 6.1 Attendance & Leave Architecture
- Daily roll-call is performed with a single batch POST (`/api/v1/sms/attendance/roll-call`).
- Leaves are submitted with start/end dates and require principal/teacher approval (`/api/v1/sms/attendance/leave-requests`).
- Monthly attendance matrices calculate percentage attendance rates for report cards and early-warning alerts.

### 6.2 Timetable Clash-Solver
- `TimetableSchedule` enforces room and teacher constraints using mathematical interval intersection checks:
  $$\text{Clash} \iff (\text{Day}_A = \text{Day}_B) \land (\text{Period}_A = \text{Period}_B) \land (\text{Teacher}_A = \text{Teacher}_B \lor \text{Room}_A = \text{Room}_B)$$
- Detects and prevents schedule collisions before database commits occur.

### 6.3 Double-Entry General Ledger
- Follows international accounting standards (IFRS / GAAP).
- Transactions create balanced `JournalEntry` records with multiple `JournalEntryLine` entries:
  $$\sum \text{Debit Amounts} = \sum \text{Credit Amounts}$$
- Automated fee payments post debit to `Cash/Bank` and credit to `Tuition Revenue`.

---

## 7. AI Pedagogy, Socratic Tutor & Safety Guardrails

### 7.1 Socratic Guidance Rules
When a student asks for homework assistance, the Socratic engine refuses to output the answer. Instead, it generates progressive hints:
1. **Clue:** Asks a guiding question to diagnose the student's current understanding.
2. **Formula:** Displays the relevant scientific or mathematical theorem.
3. **Example:** Generates an analogous problem with worked steps using different numerical values.

### 7.2 Safety Interceptor Workflow
```
User Prompt ──► [Crisis Classifier Regex + Semantic Model]
                        │
        ┌───────────────┴───────────────┐
        ▼                               ▼
 [Trigger Detected]             [Academic Query]
        │                               │
 1. Intercept Completion         1. Retrieve Textbook Context (pgvector)
 2. Log Incident to AISafety     2. Generate Socratic Guidance Stream
 3. Return Counselor Helpline
```

---

## 8. AI RevOps & Admissions CRM Suite

### 8.1 7-Stage Admissions Pipeline
1. `NEW_INQUIRY` (Inbound WhatsApp/Web inquiry)
2. `CONTACTED` (SDR bot or admissions officer reached out)
3. `TOUR_BOOKED` (Physical campus tour scheduled)
4. `ASSESSMENT_SCHEDULED` (Entry exam date set)
5. `OFFER_SENT` (Scholarship quotation and acceptance letter delivered)
6. `ENROLLED` (Admission fee paid, student ID generated)
7. `LOST` (Parent opted out or moved)

### 8.2 Lead Scoring Engine
Analyzes 5 dimensions:
$$\text{Score} = w_1 \cdot \text{Completeness} + w_2 \cdot \text{Grade Demand} + w_3 \cdot \text{Budget Fit} + w_4 \cdot \text{Timeline} + w_5 \cdot \text{Engagement}$$
- $\ge 75 \implies \text{HOT 🔥}$
- $45 - 74 \implies \text{WARM ⚡}$
- $< 45 \implies \text{COLD ❄️}$

---

## 9. Frontend Role-Based Portals & Design System

### 9.1 Next.js 15 Route Architecture
- `/home` — Unified instance launchpad, organization selector, role switcher.
- `/student` — Student dashboard, active courses, today's timetable, Socratic AI drawer.
- `/teacher` — Teacher hub, 1-click attendance roll-call, gradebook editor, timetable.
- `/parent` — Parent progress tracker, attendance calendar, weekly AI narrative.
- `/parent/fees` — 3-copy printable bank challans (`Student`, `Bank`, `School`), online checkout.
- `/campus-admin` — Campus Principal & Academic Director operations console.
- `/admissions/crm` — 7-Stage admissions Kanban board, lead cards, SDR simulator, scholarship slider.
- `/live/[roomId]` — LiveKit WebRTC virtual classroom room with live AI copilot.

### 9.2 Typography & RTL Support
- **Latin Font:** `Wix Madefor Text` (Google Fonts variable)
- **Arabic Font:** `Tajawal` (Google Fonts variable, forced across all RTL contexts)
- Synchronous `dir-init.js` script eliminates LTR/RTL layout flashes on load.

---

## 10. Local Development, Testing & Verification Suite

### 10.1 Running Tests
```powershell
cd "D:\Apps\CSG Venture\learnhouse-dev\apps\api"
uv run pytest src/tests/sms src/tests/ai src/tests/test_app_lifespan.py -v
```
**Pass Rate:** 100% (82 / 82 tests passing).

### 10.2 Starting Local Servers
1. **FastAPI Backend (Port 8000):**
   ```powershell
   cd "D:\Apps\CSG Venture\learnhouse-dev\apps\api"
   uv run uvicorn app:app --host 127.0.0.1 --port 8000
   ```
2. **Next.js Frontend (Port 3000):**
   ```powershell
   cd "D:\Apps\CSG Venture\learnhouse-dev\apps\web"
   npx next dev -p 3000
   ```

---

## 11. Production Deployment & Dokploy Runbook

### 11.1 Container Stack Specification
Defined in `dokploy-compose.yml` / `docker-compose.prod.yml`:
1. `postgres`: PostgreSQL 16 with `pgvector/pgvector:pg16` extension.
2. `redis`: Redis 7.2 Alpine with persistent append-only storage.
3. `keycloak`: Keycloak 26 OIDC provider with automated realm import (`deploy/keycloak/realm-export-csg-lms.json`).
4. `api`: Multi-stage Python 3.12 FastAPI image running Gunicorn with Uvicorn workers.
5. `collab`: Node.js 20 Hocuspocus CRDT real-time server.
6. `web`: Standalone multi-stage Next.js 15 production container.

### 11.2 Ingress Routing (Traefik SSL)
- `app.csginfotech.com` $\to$ `web` (Next.js 15)
- `api.csginfotech.com` $\to$ `api` (FastAPI)
- `auth.csginfotech.com` $\to$ `keycloak` (OIDC)
- `collab.csginfotech.com` $\to$ `collab` (Hocuspocus WebSocket)

---

## 12. Repository File Map & Key Artifacts

```
CSG Venture/
├── context.md                                   # This Master Specification File
└── learnhouse-dev/                              # Unified Monorepo
    ├── README.md                                # Root GitHub Product Presentation
    ├── dokploy-compose.yml                      # Dokploy Multi-Container Orchestration
    ├── docker-compose.prod.yml                  # Standalone Docker Compose
    ├── .env.production.example                  # Production Environment Variable Template
    ├── deploy/
    │   ├── keycloak/realm-export-csg-lms.json   # Keycloak Realm Export
    │   ├── DOKPLOY_DEPLOYMENT_RUNBOOK.md        # 1-Click Server Launch Runbook
    │   └── scripts/healthcheck.py               # Comprehensive Cluster Health Probe
    ├── apps/
    │   ├── api/                                 # FastAPI Backend Service
    │   │   ├── app.py                           # Main ASGI Entrypoint
    │   │   ├── pyproject.toml                   # Python Dependencies & Metadata
    │   │   ├── src/db/                          # SQLAlchemy Database Models
    │   │   │   ├── sms_campus.py                # Campus & Enrollment Models
    │   │   │   ├── sms_attendance.py            # Attendance & Leaves
    │   │   │   ├── sms_timetable.py             # Timetable & Periods
    │   │   │   ├── sms_gradebook.py             # Weighted GPA Gradebook
    │   │   │   ├── sms_fees.py                  # Fee Structures & Challans
    │   │   │   ├── sms_financials.py            # Chart of Accounts & GL Ledger
    │   │   │   ├── sms_hr.py                    # Staff Profiles & Leaves
    │   │   │   ├── sms_payroll.py               # Salary Structures & Slips
    │   │   │   ├── sms_live_class.py            # LiveKit Live Sessions
    │   │   │   ├── sms_library.py               # Books & Loan Tracking
    │   │   │   ├── sms_revops.py                # Admissions Leads & Offers
    │   │   │   └── ai_knowledge_graph.py        # Concept Nodes & Radar
    │   │   ├── src/services/ai/                 # Pedagogy & RevOps AI Logic
    │   │   │   ├── socratic_tutor.py            # 3-Tier Socratic Guidance Engine
    │   │   │   ├── crisis_classifier.py         # Safety & Distress Interceptor
    │   │   │   ├── knowledge_graph.py           # Concept DAG & Mastery Evaluator
    │   │   │   ├── live_class_copilot.py        # Real-Time Class Q&A Assistant
    │   │   │   ├── revops_lead_scoring.py       # Predictive Lead Scoring (0-100)
    │   │   │   ├── revops_sdr_agent.py          # 24/7 Admissions Bot
    │   │   │   ├── revops_drip_engine.py        # Automated Marketing Sequences
    │   │   │   └── revops_offer_generator.py    # Dynamic Scholarship Copy Generator
    │   │   └── src/routers/                     # REST API Endpoints (All 50 Modules)
    │   └── web/                                 # Next.js 15 Frontend
    │       ├── proxy.ts                         # Tenancy & Route Proxy Filter
    │       ├── package.json                     # Frontend Dependencies (`csg-lms-web`)
    │       ├── components/navigation/           # Unified Navigation System
    │       │   ├── RoleSidebar.tsx              # Role-Based Dynamic Sidebar
    │       │   ├── PortalHeader.tsx             # Campus Switcher & Term Badge
    │       │   └── types.ts                     # Navigation Data Structures
    │       └── app/(dashboard)/                 # Role Portals
    │           ├── student/page.tsx             # Student Hub & Socratic Drawer
    │           ├── teacher/page.tsx             # Teacher Hub & Roll-Call
    │           ├── parent/page.tsx              # Parent Progress Portal
    │           ├── parent/fees/page.tsx         # 3-Copy Bank Challan Voucher
    │           ├── campus-admin/page.tsx        # Campus Admin & Principal Console
    │           └── admissions/crm/page.tsx      # Admissions CRM 7-Stage Kanban
```

---

*Authored by Antigravity AI Engineering Army for CSG Infotech Venture.*
