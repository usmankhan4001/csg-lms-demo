# Cross-Cutting Business Rules, Master RBAC & Architectural Invariants Specification

**Document Reference:** `CSG-LMS-BFR-CC-001`  
**Target Scope:** Cross-Cutting Governance, Core Foundation, and Modules M01 through M50  
**Version:** 1.0.0 (Authoritative Master Specification)  
**System Classification:** Enterprise Educational Governance, Role-Based Access Control, Regulatory Compliance & Inter-Pillar Integration  
**Governing Standard:** 100% Pure Business Functional Requirements Specification  
**Exclusion Standard:** Strict Exclusion of All Technical Implementation Details (0 lines of programming code, 0 database DDL/SQL schemas, 0 REST API endpoints/JSON payloads, 0 infrastructure/Docker configurations)  
**Compliance Standards:** ISO/IEC/IEEE 29148, ISO 27001, ISO 27018, FERPA, COPPA, GDPR, HIPAA/HITECH Clinical Safeguarding, Cognia Accreditation Performance Standards  

---

## 1. Executive Framework: Universal Cross-Cutting Invariants

### 1.1 Architectural Scope and Governance Authority
The CSG Learning Management System (CSG-LMS) represents a unified educational operating system serving pre-kindergarten through secondary educational institutions, collegiate faculties, and distributed multi-campus networks. The platform architecture is organized into an enterprise Core Platform Foundation and three operational pillars comprising fifty specialized modules:
- **Core Platform Foundation:** Enterprise identity, multi-tenancy isolation, feature flag governance, and omnichannel notification delivery.
- **Pillar 1 (LMS & SMS - Modules M01 to M20):** Academic administration, student information lifecycle, admissions, scheduling, tuition billing, double-entry financial accounting, payroll, digital library holdings, communications, transport, and accreditation evidence.
- **Pillar 2 (AI RevOps & Growth - Modules M21 to M38):** Admissions marketing, lead intake, BANT qualification, prospect research, conversational admissions agents, copywriting, deal closing, CRM pipelines, and model routing.
- **Pillar 3 (AI Student Coach & Learning Companion - Modules M39 to M50):** Socratic AI tutoring, homework scaffolding, vocational guidance, emotional wellbeing coaching, adaptive knowledge graphs, student learning profiles, teacher oversight, and live classroom assistance.

This document establishes the universal, non-negotiable cross-cutting business rules, role-based access control policies, regulatory compliance boundaries, and inter-pillar operational handshakes that govern every transaction across all fifty modules. Where domain-specific requirements in Pillar 1, Pillar 2, or Pillar 3 define local behaviors, those behaviors must strictly conform to the universal platform invariants established herein.

---

### 1.2 The Ten Universal Platform Invariants (INV-01 through INV-10)

Every operational workflow, automated process, and user interaction within CSG-LMS is bound by ten inviolable platform invariants:

```
+-------------------------------------------------------------------------------------------------------+
|                                    THE TEN UNIVERSAL PLATFORM INVARIANTS                              |
+-------------------------------------------------------------------------------------------------------+
|  [INV-01] Absolute Multi-Tenant Isolation: Complete cryptographic and logical partition per school.    |
|  [INV-02] Zero-Code Domain Governance: Pure business logic specification without technical leakage.   |
|  [INV-03] Fail-Closed Entitlement Security: Deny-by-default; unlicensed modules return 404 Not Found. |
|  [INV-04] Clinical Privacy Shield: Total zero-knowledge isolation of psychological & therapy records. |
|  [INV-05] Immutable Double-Entry Ledger: Zero-sum balance (Sum Debit = Sum Credit); no hard deletes.  |
|  [INV-06] Mathematical Academic Rigor: Rubric sums 100.00%; unweighted GPA <= 4.0; rigor cap <= 4.5.  |
|  [INV-07] Acyclic Directed Graphs: Absolute rejection of circular dependencies in roles and curricula. |
|  [INV-08] Socratic Non-Disclosure & RAG Grounding: No direct answers; grounding cosine score >= 0.82. |
|  [INV-09] Child Protection & Consent Gating: Under-13 parental consent gate; strict screen-time limits. |
|  [INV-10] Immutable Audit & Non-Repudiation: Every mutation and AI decision logged; soft-delete only. |
+-------------------------------------------------------------------------------------------------------+
```

#### INV-01: Absolute Multi-Tenant Isolation & Zero Cross-Tenant Leakage
Every operational record, configuration setting, and transactional event must be strictly bound to an authenticated tenant organizational identifier. Cross-tenant data retrieval, whether intentional or accidental, is physically impossible. Any query or transaction targeting a foreign tenant’s data must return an absolute non-existence response (Resource Not Found) with zero records exposed and trigger an immediate high-priority security audit event.

#### INV-02: Zero-Code Pure Business Domain Governance
All operational specifications, functional capabilities, and institutional rules must be expressed exclusively in domain-level business terminology, statutory compliance requirements, and human-verifiable operational logic. No underlying programming code, relational database schemas, application programming interface (API) routes, network transport protocols, or infrastructure deployment configurations may be exposed to business stakeholders or included within functional contracts.

#### INV-03: Fail-Closed Security & Entitlement Architecture
The platform enforces an absolute deny-by-default security posture across all fifty modules. A user or agent requesting access to an operational feature, administrative action, or student record must possess an active, verified entitlement. If an entitlement is missing, expired, suspended, or ambiguous, the system must immediately terminate the request without disclosing whether the underlying resource, module, or record exists.

#### INV-04: The Clinical Privacy Shield & Absolute Ethical Isolation
All clinical evaluations, psychiatric diagnostic notes, mental health therapy session records, and student crisis transcripts generated within Module M14 (Psychological Assessment) or Module M42 (Wellbeing Coach) are sealed behind an impenetrable clinical privacy shield. Only certified School Psychologists possess decryption and read privileges. Platform Administrators, School Executives, Classroom Teachers, and Sales Personnel are barred from accessing unredacted clinical data under all circumstances.

#### INV-05: Immutable Double-Entry Ledger & Financial Integrity
Every financial transaction executed within Module M08 (Fees & Billing), Module M09 (Finance & Accounting), Module M11 (Payroll), and Module M27 (Deal Closing) must satisfy the universal double-entry balance invariant:
$$\sum \text{Debit Amounts} - \sum \text{Credit Amounts} = 0.00$$
Physical destruction or deletion of committed financial records is strictly prohibited. Accounting corrections must be executed exclusively through auditable, timestamped compensating reversing journal entries.

#### INV-06: Mathematical Academic Precision & Non-Distortion
Academic grading, weighting, and admissions evaluations must operate with absolute mathematical transparency and precision:
- Multi-criteria evaluation rubrics must sum to exactly $100.00\%$.
- Cumulative unweighted Grade Point Averages (GPA) are strictly bounded within the interval $[0.000, 4.000]$.
- Rigor-weighted GPAs incorporating Advanced Placement (AP), International Baccalaureate (IB), or Honors course bonuses cannot exceed a statutory ceiling of $4.500$.
- Academic ranking systems must normalize missing baseline terms so that transfer students or first-time scholars are evaluated equitably without synthetic grade deflation.

#### INV-07: Directed Acyclic Graph (DAG) Structural Invariant
Hierarchical and relational structures representing dependencies—specifically the institutional Role Management hierarchy in Module M18 and the Pedagogical Knowledge Graph curriculum in Module M44—must maintain strict directed acyclicity. Any administrative mutation that introduces a circular dependency (such as Role A inheriting Role B which inherits Role A, or Concept X requiring Concept Y which requires Concept X) must be rejected instantaneously as an invalid state transition.

#### INV-08: Socratic Pedagogical Non-Disclosure & Grounding Invariant
Autonomous student-facing AI agents (M39 AI Tutor, M40 Homework Assistant, M50 AI Live Class Q&A) are strictly prohibited from disclosing direct answers, completed assignments, or unearned solutions to enrolled learners. All pedagogical guidance must scaffold learning through graduated Socratic inquiry. Furthermore, AI factual statements must be grounded in certified curriculum materials with a semantic cosine similarity grounding score of at least $0.82$; statements failing this threshold must be suppressed and escalated to a human educator.

#### INV-09: Universal Minor Protection, Consent Gating & Screen-Time Boundaries
Under statutory child protection frameworks (COPPA, FERPA, GDPR), minor students under thirteen years of age cannot access autonomous AI coaching, tutoring, or conversational agents without a verified digital parental consent token. Student digital engagement is bounded by mandatory daily screen-time caps (45 cumulative minutes for academic tutoring; 15 cumulative minutes for emotional wellbeing) and rolling 90-day ephemeral memory purges to prevent cognitive fatigue and digital dependency.

#### INV-10: Comprehensive Immutable Audit Logging & Non-Repudiation
Every state mutation, administrative override, financial transaction, role assignment, clinical escalation, and AI generation decision across all fifty modules must be permanently recorded in an append-only, tamper-evident audit ledger. Audit entries must capture the authenticated actor, tenant context, precise timestamp, operational action, before-and-after state snapshots, and decision justification. Once written, audit entries cannot be altered, overwritten, or erased.

---

### 1.3 Platform Baseline Requirements Integration (PLAT-FR-001 through PLAT-FR-029)
The fifty functional modules inherit and enforce the standardized platform baseline requirements defined in institutional architecture specifications:

| Baseline ID | Requirement Domain | Operational Business Constraint | Applicable Modules |
|:---|:---|:---|:---|
| **PLAT-FR-001** | Tenant Data Isolation | Universal tenant context binding on every transaction; zero cross-tenant leakage; foreign attempts return 404. | All 50 Modules (M01–M50) & Core |
| **PLAT-FR-002** | Dual-Platform Event Sync | State mutations emit standardized domain events within $\le 50$ milliseconds; seamless web and mobile reconciliation. | All 50 Modules (M01–M50) & Core |
| **PLAT-FR-003** | Offline-First Mobile Operations | Field operations function offline with local persistence; automatic conflict resolution and zero silent data loss upon reconnect. | All 50 Modules (Field & Core) |
| **PLAT-FR-004** | Real-Time Push Notification | Priority push notifications delivered within $\le 30$ seconds; emergency crisis alerts bypass user quiet hours and Do Not Disturb. | All 50 Modules (M01–M50) & Core |
| **PLAT-FR-005** | Psychologist Clinical Pathway | Mandatory designated data pathway to School Psychologist for clinical review; field-encrypted clinical isolation from teachers and admins. | All 50 Modules (M01–M50) & Core |
| **PLAT-FR-006** | Input Validation & Sanitization | Strict schema and domain validation on all payload entities; invalid submissions rejected with standardized business problem details. | All 50 Modules (M01–M50) & Core |
| **PLAT-FR-007** | State Machine Enforcement | Entity lifecycles governed by strict transition matrices; illegal status jumps rejected without state corruption or event emission. | All Stateful Modules |
| **PLAT-FR-008** | Structured Error Handling | Standardized problem detail reporting with human-readable titles, localized business codes, and specific explanatory remediation. | All 50 Modules (M01–M50) & Core |
| **PLAT-FR-009** | Audit Logging & Soft Delete | Destructive actions execute logical soft-deletion only; immutable actor and timestamp logging; active queries exclude deleted rows. | All 50 Modules (M01–M50) & Core |
| **PLAT-FR-010** | Accessibility Compliance | Full compliance with WCAG 2.1 Level AA standards; screen reader compatibility, high contrast ratios, and touch-target standards. | All 50 Modules (UI Interfaces) |
| **PLAT-FR-011** | Operational Performance SLAs | Fast interactive response times (P95 read $< 150\text{ ms}$, P95 mutation $< 200\text{ ms}$) and $99.9\%$ monthly platform uptime. | All 50 Modules (M01–M50) & Core |
| **PLAT-FR-012** | Enterprise Security Controls | Mandatory denial logging, rate limiting (120 req/min with burst absorption), and field-level encryption for confidential records. | All 50 Modules (M01–M50) & Core |
| **PLAT-FR-020** | Prompt Injection Guardrail | Sanitization of all free-text input prior to AI evaluation; injection attacks blocked and logged with trace identifiers. | 30 AI Modules (Pillars 2, 3, Bonus) |
| **PLAT-FR-021** | PII Minimization Before AI | Replacement of direct student/parent identifiers with pseudonymous tokens before external model evaluation. | 30 AI Modules (Pillars 2, 3, Bonus) |
| **PLAT-FR-022** | Model Failover Routing | Automatic multi-provider failover chains; graceful degradation to safe fallback responses if provider networks fail. | 30 AI Modules (Pillars 2, 3, Bonus) |
| **PLAT-FR-023** | Conversation Memory Window | AI contextual recall limited to active turns plus high-similarity vector memories; hard 90-day retention cutoff. | 30 AI Modules (Pillars 2, 3, Bonus) |
| **PLAT-FR-024** | Consent Verification Gate | Autonomous AI execution blocked immediately if minor student lacks active, unexpired digital parental consent token. | 30 AI Modules (Pillars 2, 3, Bonus) |
| **PLAT-FR-025** | Crisis Guardrail & SLA | Real-time emotional distress and crisis pre-moderation; immediate generation abort; 2-minute emergency psychologist dispatch. | Student-Facing AI Modules |
| **PLAT-FR-026** | Human-in-the-Loop Escalation | AI confidence below 0.60 or ambiguous safety status halts autonomous processing and creates human review escalation. | 30 AI Modules (Pillars 2, 3, Bonus) |
| **PLAT-FR-027** | AI Decision Audit Logging | Immutable logging of AI prompt hashes, model parameters, confidence scores, and safety verdicts; 180-day audit retention. | 30 AI Modules (Pillars 2, 3, Bonus) |
| **PLAT-FR-028** | Minor Data Minimization | Processing of subjects under 16 retains only allow-listed educational fields; raw chat logs barred from external training stores. | 18 RevOps Modules (M21–M38) |
| **PLAT-FR-029** | Per-Tenant Token Governance | Strict enforcement of institutional daily AI token budgets and rate limits; automated hard stop when quota is exhausted. | 18 RevOps Modules (M21–M38) |

---

## 2. Master Role-Based Access Control (RBAC) System

### 2.1 The Exhaustive 7-Persona System

The CSG-LMS platform governs all system access through seven mutually exclusive, standardized operational personas. Each user identity is bound to exactly one primary persona within a tenant context, augmented by granular organizational role assignments:

```
+----------------------------------------------------------------------------------------------------+
|                                    MASTER 7-PERSONA ARCHITECTURE                                    |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|    [SUPER_ADMIN]   Global multi-tenant platform operator; infrastructure compliance, tenant         |
|          |         provisioning, global feature flags, root security oversight.                    |
|          v                                                                                         |
|    [SCHOOL_ADMIN]  Institutional executive (Principal, Head of School, Registrar, Bursar);          |
|          |         campus policies, staff administration, academic calendars, financial sign-off.   |
|          +----------------------------+----------------------------+                               |
|          |                            |                            |                               |
|          v                            v                            v                               |
|      [TEACHER]                     [STAFF]                   [PSYCHOLOGIST]                        |
|    Instructional leader;         Operational team;         Certified clinician;                    |
|    curricula, gradebook,         admissions, accounting,   crisis triage, therapy notes,           |
|    exams, attendance, rubrics.   library, transport, HR.   clinical shield (TOTAL ISOLATION).      |
|          |                            |                                                            |
|          +--------------+-------------+                                                            |
|                         |                                                                          |
|                         v                                                                          |
|                     [STUDENT] <=========================> [PARENT]                                 |
|                 Primary learner;                     Legal guardian; tuition settlement,           |
|                 coursework, exams, AI coaching.      absence excuses, consent governance.          |
|                                                                                                    |
+----------------------------------------------------------------------------------------------------+
```

#### Persona 1: SUPER_ADMIN (Platform Operator & Infrastructure Steward)
- **Operational Boundary:** Global SaaS platform operations across all institutional tenants.
- **Key Responsibilities:** Provisioning new educational tenants, managing global subscription tiers and seat quotas, configuring global AI model router endpoints, monitoring system-wide SLA compliance, and auditing enterprise security events.
- **Privacy Boundary:** Strictly barred from inspecting student clinical case notes, confidential psychological evaluations, and individual classroom chat transcripts. Possesses zero-knowledge visibility into institutional clinical data.

#### Persona 2: SCHOOL_ADMIN (Institutional Executive & Compliance Authority)
- **Operational Boundary:** Single educational institution or multi-campus branch network.
- **Key Responsibilities:** Establishing institutional policies, academic term schedules, curricular programs, staff employment assignments, fee structures, admissions review board sign-offs, and official transcript certifications.
- **Privacy Boundary:** Full operational authority over institutional business and academic records. Barred from inspecting raw clinical therapy notes; receives only PII-redacted aggregate wellbeing metrics and formal IEP accommodation directives.

#### Persona 3: TEACHER (Instructional Leader & Academic Evaluator)
- **Operational Boundary:** Assigned academic departments, course sections, and enrolled student cohorts.
- **Key Responsibilities:** Authoring course lessons, publishing assignments, configuring grading rubrics, administering online examinations, recording attendance, conducting live classroom sessions, moderating AI Q&A drafts, and submitting midterm marks.
- **Privacy Boundary:** Complete visibility into enrolled students' academic records, assignment submissions, and IEP accommodation accommodations. Barred from viewing student family financial records, staff payroll, and private psychological counseling case files.

#### Persona 4: STUDENT (Primary Learner & Minor Stakeholder)
- **Operational Boundary:** Personal enrolled courses, personal assignments, extracurricular activities, and individual learning companion.
- **Key Responsibilities:** Attending live classes, submitting coursework, taking examinations, reviewing personal grades and teacher feedback, borrowing library assets, interacting with the Socratic AI tutor, and engaging in daily wellbeing reflections.
- **Privacy Boundary:** Strictly restricted to own academic records, personal learning paths, and self-generated AI interactions. Barred from viewing peer academic grades, institutional finance, teacher evaluations, or administrative configurations.

#### Persona 5: PARENT (Legal Guardian & Financial Sponsor)
- **Operational Boundary:** Formally linked biological or legally adopted dependent children enrolled in the institution.
- **Key Responsibilities:** Reviewing child academic progress digests, settling tuition and incidental invoices, selecting payment plans, submitting verified absence excuse notes, granting or revoking digital AI consent, and monitoring daily screen-time allocations.
- **Privacy Boundary:** Full access to child's published academic transcripts, attendance records, and billing statements. Barred from viewing private student daily emotional journal entries (to protect therapeutic trust) and clinical diagnostic case files unless formally released by the School Psychologist.

#### Persona 6: STAFF (Operational & Administrative Support Specialist)
- **Operational Boundary:** Institutional functional operational departments (Admissions, Bursar/Finance, Human Resources, Library, Transportation, Facility Management).
- **Key Responsibilities:** Processing prospective lead inquiries, reconciling student fee payments, generating general ledger entries, processing staff payroll withholding, cataloging digital library assets, and managing vehicle fleet dispatch.
- **Privacy Boundary:** Access strictly partitioned by operational departmental assignment. Finance staff cannot view academic gradebooks; library staff cannot view student disciplinary records; transport dispatchers cannot view tuition contracts. Barred from all clinical psychological records.

#### Persona 7: PSYCHOLOGIST (Licensed Mental Health Clinician & Safeguarding Guardian)
- **Operational Boundary:** Institutional mental health, behavioral intervention, psychological assessment, and crisis triage operations.
- **Key Responsibilities:** Administering standardized psychometric evaluations, authoring clinical case notes, triaging high-severity emotional crisis escalations from AI student coaches, managing acute suicide ideation interventions, and issuing formal classroom accommodation directives.
- **Privacy Boundary:** Holds exclusive, uncompromised access to the Clinical Privacy Shield (Module M14 and Module M42 triage desk). Operates as an absolute zero-knowledge clinical authority; clinical records cannot be decrypted or inspected by School Administrators, Teachers, Staff, or Super Admins.

---

### 2.2 Standardized RBAC Permission Taxonomy

The platform enforces seven standardized, mutually exclusive permission levels across all modules:

| Permission Level | Operational Definition & System Authority | Mutating Authority | Visibility Scope |
|:---|:---|:---|:---|
| **Full** | Complete platform-wide administrative authority. Can provision, configure, activate, suspend, and audit system resources across all tenants. | Full (Global) | Global System Scope |
| **Admin** | Institutional executive control. Can establish institutional policies, term calendars, fee tables, staff roles, and execute final approvals. | Full (Tenant) | Tenant Organizational Scope |
| **Manage** | Operational execution authority. Can author, publish, modify, dispatch, and execute operational workflows within an assigned departmental domain. | Operational Records | Departmental / Assigned Scope |
| **Grade** | Specialized academic evaluation authority. Can evaluate student coursework, author rubric criteria, assign numeric scores, and enter official marks. | Evaluative Records | Assigned Courses & Sections |
| **Read/Interact** | Interactive operational engagement. Can participate in live sessions, submit queries, search catalogs, and interact with designated workflows. | Interactive Input | Permitted Catalog / Session Scope |
| **Own-Only** | Self-sovereign boundary. Access and mutation are strictly restricted to records directly created by, or explicitly linked to, the acting individual. | Personal Records | Strictly Personal / Linked Scope |
| **None** | Total absence of privilege. Request is denied fail-closed; system returns 404 (Resource Not Found) to conceal feature existence. | None | Absolute Zero Visibility |

---

### 2.3 Master 50-Module + Core Foundation RBAC Matrix

The following exhaustive matrix governs access rights across all 50 platform modules and the Core Foundation for all seven personas:

| Module ID & Name | SUPER_ADMIN | SCHOOL_ADMIN | TEACHER | STUDENT | PARENT | STAFF | PSYCHOLOGIST | Functional Governance Scope & Domain Invariant |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---|
| **Core Foundation** | **Full** | **Admin** | **Read/Interact** | **Own-Only** | **Own-Only** | **Read/Interact** | **Own-Only** | Identity authentication, session governance, and multi-tenancy context verification. |
| **M01 Admissions** | **Full** | **Admin** | **Read/Interact** | **Own-Only** | **Own-Only** | **Manage** | **Read/Interact** | Application intake, weighted scoring review board; psychologist reviews SEN flags. |
| **M02 Live Classes** | **Full** | **Admin** | **Manage** | **Read/Interact** | **None** | **Manage** | **None** | Live video session hosting, automated roll-call, real-time engagement telemetry. |
| **M03 Assignments** | **Full** | **Admin** | **Grade** | **Own-Only** | **Own-Only** | **Read/Interact** | **None** | Assignment authoring, multi-criteria rubric grading, late submission penalty decay. |
| **M04 Online Exams** | **Full** | **Admin** | **Manage** | **Own-Only** | **Own-Only** | **Manage** | **None** | Computer-based testing, IRT 2PL item difficulty scoring, proctoring anomaly triage. |
| **M05 Gradebook** | **Full** | **Admin** | **Grade** | **Own-Only** | **Own-Only** | **Read/Interact** | **Read/Interact** | Term mark entry, unweighted/weighted GPA computation, report card publishing. |
| **M06 Attendance** | **Full** | **Admin** | **Manage** | **Own-Only** | **Own-Only** | **Manage** | **Read/Interact** | Period roll-call, biometric/app check-in, parent excuse notes, truancy tracking. |
| **M07 Timetable** | **Full** | **Admin** | **Read/Interact** | **Own-Only** | **Own-Only** | **Manage** | **Read/Interact** | Constraint-based schedule solving, room/teacher clash prevention, schedule locks. |
| **M08 Fees & Billing** | **Full** | **Admin** | **None** | **None** | **Own-Only** | **Manage** | **None** | Tuition schedules, tiered sibling discounts, compounding late fee enforcement. |
| **M09 Finance** | **Full** | **Admin** | **None** | **None** | **None** | **Manage** | **None** | General ledger, double-entry zero-sum balance, compensating reversing entries. |
| **M10 HR & Staff** | **Full** | **Admin** | **Own-Only** | **None** | **None** | **Manage** | **Own-Only** | Employee lifecycle, leave accrual/carry-over caps, teacher workload monitoring. |
| **M11 Payroll** | **Full** | **Admin** | **Own-Only** | **None** | **None** | **Manage** | **Own-Only** | Progressive tax withholding, non-negative net salary clamping, pay slip delivery. |
| **M12 Digital Library** | **Full** | **Admin** | **Manage** | **Own-Only** | **Own-Only** | **Manage** | **Manage** | Cataloging, borrowing limits, linear daily overdue fines, bibliotherapy recommendations. |
| **M13 Comms** | **Full** | **Admin** | **Manage** | **Read/Interact** | **Read/Interact** | **Manage** | **Manage** | Omnichannel broadcast alerts, private 1-on-1 messaging, quiet hours enforcement. |
| **M14 Psychological** | **None** | **None** | **None** | **Own-Only** | **Own-Only** | **None** | **Full** | Clinical privacy shield; mental health triage, DSM evaluations, crisis interventions. |
| **M15 Transport** | **Full** | **Admin** | **None** | **Own-Only** | **Own-Only** | **Manage** | **None** | Bus route waypoints, vehicle capacity caps, real-time GPS telemetry alerts. |
| **M16 Cognia Evidence** | **Full** | **Admin** | **Read/Interact** | **None** | **None** | **Manage** | **Read/Interact** | Accreditation maturity index, dual-checksum evidence artifacts, self-review locks. |
| **M17 Platform Admin** | **Full** | **Read/Interact** | **None** | **None** | **None** | **None** | **None** | Tenant provisioning, institutional license quotas, maintenance windows. |
| **M18 Role Mgmt** | **Full** | **Admin** | **None** | **None** | **None** | **None** | **None** | Custom role authoring, acyclic inheritance validation, passphrase security. |
| **M19 Reports** | **Full** | **Admin** | **Read/Interact** | **Own-Only** | **Own-Only** | **Read/Interact** | **Read/Interact** | Institutional cohort analytics, report queuing, time-limited secure share tokens. |
| **M20 Settings** | **Full** | **Admin** | **Own-Only** | **Own-Only** | **Own-Only** | **Own-Only** | **Own-Only** | 4-tier configuration hierarchy, two-person author approval guard, audit rollback. |
| **M21 Lead Intake** | **Full** | **Admin** | **None** | **None** | **Own-Only** | **Manage** | **Read/Interact** | Multi-channel prospect capture, duplicate deduplication, special needs flagging. |
| **M22 Qualification** | **Full** | **Admin** | **None** | **None** | **None** | **Manage** | **None** | BANT multi-criteria lead scoring, automated tiering, nurturing flow triggers. |
| **M23 Research Agent** | **Full** | **Admin** | **None** | **None** | **None** | **Manage** | **None** | Prospect data enrichment, demographic affinity scoring, human sign-off gates. |
| **M24 Voice & Chat** | **Full** | **Admin** | **None** | **None** | **Own-Only** | **Manage** | **None** | Autonomous admissions conversational agent, sentiment decay, human counselor handoff. |
| **M25 Marketing Agent** | **Full** | **Admin** | **None** | **None** | **None** | **Manage** | **None** | Multi-channel marketing campaign orchestration, CAC tracking, ethical messaging. |
| **M26 Copywriting** | **Full** | **Admin** | **Read/Interact** | **None** | **None** | **Manage** | **Read/Interact** | Flesch-Kincaid readability scoring, developmental appropriateness, psych review. |
| **M27 Deal Closing** | **Full** | **Admin** | **None** | **None** | **Own-Only** | **Manage** | **Read/Interact** | Net Tuition Yield computation, tuition payment contracts, medical/SEN check. |
| **M28 CRM Pipeline** | **Full** | **Admin** | **None** | **None** | **None** | **Manage** | **None** | Admissions stage progression, weighted enrollment forecasting, transition to SMS. |
| **M29 Conv. Memory** | **Full** | **Admin** | **None** | **Own-Only** | **Own-Only** | **Manage** | **None** | Semantic marketing memory; strict exclusion of clinical data; 90-day retention. |
| **M30 Admin Config** | **Full** | **Admin** | **None** | **None** | **None** | **Manage** | **Read/Interact** | AI cost tracking, safety threshold configuration, super admin approval gating. |
| **M31 RevOps Analytics**| **Full** | **Admin** | **None** | **None** | **None** | **Manage** | **None** | Token Cost Ratio, conversion funnel analytics, admissions yield velocity. |
| **M32 Integration Sync**| **Full** | **Admin** | **None** | **None** | **None** | **Manage** | **None** | External SIS/CRM synchronization, exponential backoff retries, dead-letter triage. |
| **M33 Consent & Comp.** | **Full** | **Admin** | **Read/Interact** | **Own-Only** | **Own-Only** | **Manage** | **Read/Interact** | GDPR 30-day SAR countdown, 5-second downstream AI cutoff on consent revocation. |
| **M34 Knowledge Base** | **Full** | **Admin** | **Manage** | **Read/Interact** | **Read/Interact** | **Manage** | **Manage** | Hybrid search (vector + BM25), freshness decay scoring, curriculum verification. |
| **M35 Notifications** | **Full** | **Admin** | **Read/Interact** | **None** | **Own-Only** | **Manage** | **None** | RevOps notification delivery, read rate tracking, crisis alert escalation. |
| **M36 Localization** | **Full** | **Admin** | **Read/Interact** | **Own-Only** | **Own-Only** | **Manage** | **Read/Interact** | Translation completeness gating (>=95%), RTL formatting, localized materials. |
| **M37 Multi-Org** | **Full** | **Admin** | **None** | **None** | **None** | **Read/Interact** | **None** | Multi-branch tenant hierarchy (up to 5 levels), seat quota sharing governance. |
| **M38 Model Router** | **Full** | **Read/Interact** | **None** | **None** | **None** | **Read/Interact** | **None** | Dynamic cost-quality routing, multi-provider failover, latency/quality SLAs. |
| **M39 AI Tutor** | **Full** | **Admin** | **Manage** | **Read/Interact** | **Own-Only** | **None** | **None** | Socratic non-disclosure dialogue, RAG grounding (>=0.82), Bloom taxonomy ladder. |
| **M40 Homework Assist**| **Full** | **Admin** | **Manage** | **Read/Interact** | **Own-Only** | **None** | **None** | 3-tier scaffolded hint ladder, hint usage grade penalty, problem locking. |
| **M41 Career Guidance**| **Full** | **Admin** | **Read/Interact** | **Read/Interact** | **Own-Only** | **Manage** | **Read/Interact** | Holland RIASEC vocational profiling, career exploration, university matching. |
| **M42 Wellbeing Coach**| **None** | **None** | **None** | **Read/Interact** | **None** | **None** | **Full** | Sentiment & crisis triage, 2-minute psychologist alert SLA, emergency hotlines. |
| **M43 Personalization**| **Full** | **Admin** | **Manage** | **Own-Only** | **Own-Only** | **None** | **Manage** | Spaced repetition scheduling (SuperMemo SM-2), IEP/504 accommodation limits. |
| **M44 Knowledge Graph**| **Full** | **Admin** | **Manage** | **Own-Only** | **Own-Only** | **Read/Interact** | **None** | Prerequisite dependency pathfinder, DAG cycle rejection, concept mastery rollup. |
| **M45 Student Profile**| **Full** | **Admin** | **Read/Interact** | **Own-Only** | **Own-Only** | **Read/Interact** | **Manage** | Unified academic profile, clinical privacy shield, mastery metric clamping. |
| **M46 Teacher Oversight**| **Full** | **Admin** | **Manage** | **None** | **None** | **None** | **Manage** | Intervention urgency ranking, red-flag alert queue, PII-redacted chat inspection. |
| **M47 Consent & Safety**| **Full** | **Admin** | **Read/Interact** | **Own-Only** | **Own-Only** | **None** | **Manage** | Under-13 parental consent gate, 45-min tutoring / 15-min wellbeing screen caps. |
| **M48 Parent Portal** | **Full** | **Admin** | **Read/Interact** | **None** | **Own-Only** | **Read/Interact** | **Read/Interact** | Bi-weekly learning digests, Parent Engagement Index, screen-time controls. |
| **M49 Streaming Transport**| **Full** | **Admin** | **Read/Interact** | **Read/Interact** | **None** | **None** | **Read/Interact** | Low-latency token streaming, sequence recovery, mid-stream crisis interception. |
| **M50 AI Live Class QA**| **Full** | **Admin** | **Manage** | **Read/Interact** | **None** | **None** | **None** | In-class student question triage, confidence gate (<70% routes to teacher approval). |

---

### 2.4 Dynamic Delegation, Dual-Custody, and Separation of Duties

To prevent administrative overreach, institutional fraud, and unilateral error, the platform mandates strict operational checks:

#### 1. The Two-Person Author Approval Guard (Module M20 Settings & M09 Finance)
High-impact systemic actions cannot be committed by a single actor:
- Modifying institutional tuition fee schedules or granting hardship discounts exceeding $1,000 requires initiation by an Admissions/Bursar Staff member and secondary digital approval by the School Administrator.
- Publishing official cumulative term transcripts or altering finalized historical grades requires submission by the Classroom Teacher and formal digital sign-off by the Academic Registrar or Principal.
- Modifying safety pre-moderation sensitivity thresholds or crisis triage escalation contacts in Module M30/M47 requires initiation by the School Administrator and mandatory concurrence by the certified School Psychologist.

#### 2. Separation of Duties in Commercial & Accounting Operations
- An admissions counselor who negotiates tuition payment plans in Module M27 (Deal Closing) cannot execute general ledger adjustments in Module M09 (Finance).
- A payroll clerk who compiles teacher work hours and calculates tax withholdings in Module M11 cannot authorize the institutional bank disbursement file without School Administrator counter-signature.

#### 3. Time-Limited Role Delegation & Emergency Tokens (Module M19 Reports)
- When a teacher or administrator delegates operational coverage during leaves of absence, delegated privileges are time-bounded by an automated expiry timer (maximum 14 calendar days).
- All actions executed under delegated authority carry dual-identity audit watermarks recording both the delegating authority and the acting surrogate.

---

## 3. The Psychologist Clinical Data Isolation Guardrail

### 3.1 The Absolute Zero-Knowledge Clinical Privacy Shield

Student mental health therapy, developmental readiness evaluations, emotional distress triage, and crisis management records represent the most sensitive information processed by the platform. To uphold medical ethics, statutory counseling confidentiality (HIPAA, FERPA, state psychological licensing boards), and therapeutic trust, the platform enforces an impenetrable **Zero-Knowledge Clinical Privacy Shield**:

```
+----------------------------------------------------------------------------------------------------+
|                                THE CLINICAL DATA PRIVACY SHIELD                                    |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|    [STUDENT] =============== [M42 Wellbeing Coach / M14 Clinical Assessments]                      |
|                                       |                                                            |
|                                       v                                                            |
|                    +-------------------------------------+                                         |
|                    |     CLINICAL PRIVACY SHIELD         | <== FIELD-ENCRYPTED ZERO-KNOWLEDGE      |
|                    |     (Dedicated Cryptographic Keys)  |                                         |
|                    +-------------------------------------+                                         |
|                                       |                                                            |
|               +-----------------------+-----------------------+                                    |
|               |                                               |                                    |
|               v                                               v                                    |
|     [PSYCHOLOGIST ONLY]                         [SAFE FILTERED OBSERVABILITY]                      |
|   - Unredacted clinical notes                 - PII-Redacted Struggle Signals                      |
|   - Suicide ideation transcripts              - Approved Classroom Accommodations                  |
|   - Psychological diagnoses                   - Aggregate Wellbeing Sentiment                      |
|   - Formal intervention plans                 - Emergency Crisis Trigger Flag                      |
|                                                               |                                    |
|                                       +-----------------------+-----------------------+            |
|                                       |                                               |            |
|                                       v                                               v            |
|                              [CLASSROOM TEACHER]                              [SCHOOL ADMIN]       |
|                            - Sees: "Extra 30 mins"                          - Sees: Aggregates     |
|                            - BLOCKED from diagnosis                         - BLOCKED from notes   |
|                                                                                                    |
|    ================================ ABSOLUTE EXCLUSION WALL =====================================   |
|    [SUPER_ADMIN] [STAFF] [SALES / MARKETING AGENTS] ===> HTTP 403 / 404 (ZERO ACCESS PERMITTED)    |
|                                                                                                    |
+----------------------------------------------------------------------------------------------------+
```

#### Absolute Access Denial Matrix
- **SUPER_ADMIN:** Absolutely barred from decrypting or viewing clinical records. Tenant maintenance or database management cannot access unencrypted mental health files.
- **SCHOOL_ADMIN:** Barred from viewing therapist notes, session narratives, or private diagnostic codes. May view only institutional aggregate mental health trends and formal accommodation directives.
- **TEACHER:** Barred from viewing psychological evaluations, student emotional journals, or crisis transcripts.
- **STAFF & SALES PERSONNEL:** Absolutely barred from clinical data. Commercial sales pipelines (M21–M28) are physically blocked from ingesting psychological notes.

---

### 3.2 PII-Redacted Inspection & Teacher Intervention Pathways

Classroom educators require actionable visibility when students experience academic or emotional struggles, but must never be exposed to private therapeutic disclosures. Module M46 (Teacher Oversight) enforces strict operational de-identification:

#### 1. Behavioral & Academic Red-Flag Triage
When an AI tutoring assistant (M39) or homework assistant (M40) detects acute cognitive frustration, learning fatigue, or repeated task abandonment, it generates a struggle signal:
- **Exposed Data to Teacher:** Anonymized struggle classification (e.g., "Student encountering severe cognitive obstacle on Quadratic Factoring; 4 failed attempts; hint ladder exhausted").
- **Redacted Information:** The student's private emotional disclosures, diary entries, personal reflections, and off-topic commentary are stripped entirely from the educator view.

#### 2. Translation of Clinical Diagnostics into Classroom Accommodations
When a School Psychologist formalizes an Individualized Education Program (IEP) or Section 504 accommodation plan within Module M14, the system translates clinical diagnoses into functional educational directives:
- **Clinical Record (Psychologist Portal):** "Subject exhibits symptoms of generalized social anxiety and processing deficit (DSM-5 F41.1); recommend low-stimulation environment and extended testing time."
- **Classroom Directive (Teacher & Gradebook Portal):** "Accommodated Assessment Protocol: Grant $1.5\times$ standard time allowance on timed examinations; permit quiet-room testing." The diagnostic rationale remains completely confidential within the clinician's vault.

---

### 3.3 Minor Consent & Statutory Emancipation Boundaries

Psychological assessments and wellbeing interventions are governed by clear legal consent protocols:

#### 1. Routine Clinical Evaluations & Individual Psychotherapy
- Enrolled students under the statutory age of medical consent (typically age 14 to 18 depending on jurisdiction) require verified written or digital consent from a linked legal guardian (PARENT) prior to the initiation of non-emergency psychometric testing or formal psychological therapy.
- Parents possess the legal right to review formally finalized psycho-educational assessment reports submitted to the school's official academic record.

#### 2. Mature Minor Confidentiality & Self-Referral Protections
- Adolescents meeting statutory mature minor criteria possess the legal right to initiate confidential, self-referred counseling consultations with the School Psychologist without mandatory pre-notification to parents, in accordance with applicable adolescent health privacy statutes.
- Informal counseling session notes and private therapeutic explorations remain strictly confidential between the minor scholar and the licensed clinician.

---

### 3.4 Crisis Severity Triage Triggers & The 2-Minute Emergency Dispatch SLA

Autonomous conversational agents (M39, M40, M42, M50) continuously evaluate student input through a multi-dimensional emotional safety pre-moderation engine:

```
                          [STUDENT CONVERSATIONAL INPUT]
                                       |
                                       v
                    +-------------------------------------+
                    |   M47 Real-Time Safety Gateway      |
                    |   (Distress & Crisis Classifier)    |
                    +-------------------------------------+
                                       |
                   Severity Score Evaluated: [Range 0.00 to 10.00]
                                       |
         +-----------------------------+-----------------------------+
         |                                                           |
  [Score < 8.00 / 0.80]                                     [Score >= 8.00 / 0.80]
  Normal Socratic Coaching                                  ACUTE CRISIS TRIGGER
  Pedagogical Scaffold                                               |
                                     +-------------------------------+-------------------------------+
                                     |                               |                               |
                                     v                               v                               v
                            [IMMEDIATE AI ABORT]           [STUDENT CRISIS BANNER]        [2-MIN EMERGENCY SLA]
                            Token generation halts;        Surfaces 24/7 Crisis Hotline   High-priority push, SMS,
                            no clinical advice given.      (e.g., 988 Lifeline, text).    voice blast to PSYCHOLOGIST.
```

#### 1. Acute Crisis Severity Threshold
A crisis event is triggered whenever conversational analysis yields a distress severity score $\ge 8.00$ on a 10-point scale (or confidence $\ge 0.80$) across high-risk categories:
- Explicit suicidal ideation, intent, or self-harm contemplation.
- Severe physical abuse, domestic violence, or sexual endangerment disclosures.
- Impending threats of physical violence against self or others.

#### 2. Immediate Dialogue Abort & Anti-Therapy Constraint
- The AI student coach must immediately terminate conversational generation mid-stream.
- **Strict Non-Clinical Proscription:** The AI is strictly forbidden from offering psychiatric diagnoses, therapeutic counseling, de-escalation promises, or medication guidance. The AI must never pretend to be a human clinician.

#### 3. Student-Facing Emergency Hotline Banner
The client user interface must instantaneously replace the chat interface with an un-dismissible emergency crisis card displaying:
- National and localized 24/7 crisis hotlines (e.g., Suicide & Crisis Lifeline: 988; Crisis Text Line: text HOME to 741741).
- Direct one-touch button to connect immediately with institutional emergency campus security or local emergency services.

#### 4. The 2-Minute Emergency Dispatch Service Level Agreement (SLA)
- Upon crisis trigger, the platform emits an urgent emergency escalation event dispatched directly to the on-call School Psychologist.
- **Delivery Guarantee:** Notification must be delivered across primary and secondary channels (urgent mobile push notification, automated high-priority SMS, and audible voice alarm) within $\le 2$ minutes of generation abort.
- **Quiet-Hours Bypass:** Emergency crisis alerts bypass all user quiet hours, sleep schedules, and Do Not Disturb preferences on the clinician’s authenticated devices.
- **Audit Confirmation:** The platform tracks the timestamp of dispatch, delivery, and clinician acknowledgment. If unacknowledged within 5 minutes, the alert automatically escalates to the secondary emergency safeguarding officer (Principal / Head of School).

---

### 3.5 Statutory Data Retention & Cryptographic Shredding

Clinical psychological records are subject to strict post-majority statutory retention schedules:

#### 1. The 7-Year Post-Majority Retention Standard
In compliance with pediatric health and psychological record regulations, clinical case records, diagnostic evaluations, and crisis intervention files must be retained for exactly:
$$\text{Retention Period} = (\text{Date of Student 18th Birthday}) + 7\text{ Calendar Years}$$
(Retained until the subject reaches twenty-five years of age, or jurisdictional equivalent).

#### 2. Automated Retention Countdown & Cryptographic Shredding
- Upon the expiration of the statutory retention period, the system places the clinical dossier into an automated pre-destruction queue for 30 days, alerting the Lead Psychologist.
- **Cryptographic Key Shredding:** Destruction of the record is executed through cryptographic erasure—permanently destroying the dedicated tenant-student clinical encryption keys. Without these keys, the underlying ciphertext becomes mathematically unrecoverable.
- An immutable Certificate of Cryptographic Destruction is generated, recording the subject's pseudonymous identifier, retention legal citation, destruction timestamp, and cryptographic verification hash, signed into the institutional compliance archive.

---

## 4. Child Protection, Privacy & Statutory Compliance Policies

### 4.1 COPPA (Children’s Online Privacy Protection Act) Compliance Policy

The platform strictly enforces the Children’s Online Privacy Protection Act for all learners under thirteen years of age:

```
+----------------------------------------------------------------------------------------------------+
|                                    COPPA UNDER-13 COMPLIANCE GATE                                  |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|    [STUDENT ACCOUNT INTAKE] ---> Declared Date of Birth Evaluated                                  |
|                                       |                                                            |
|         +-----------------------------+-----------------------------+                              |
|         |                                                           |                              |
|   [Age >= 13 Years]                                           [Age < 13 Years]                     |
|   Standard Student Account                                    HARD-STOP CONSENT GATE               |
|   Parent Notification Sent                                                  |                      |
|                                                                             v                      |
|                                                          +-------------------------------------+   |
|                                                          | Verified Parental Consent (VPC)     |   |
|                                                          | - Financial Micro-Authorization     |   |
|                                                          | - Government ID Verification        |   |
|                                                          | - Digitally Signed Consent Mandate  |   |
|                                                          +-------------------------------------+   |
|                                                                             |                      |
|                                             +-------------------------------+-------------------+  |
|                                             |                                                   |  |
|                                     [CONSENT GRANTED]                                   [CONSENT DENIED]   |
|                                     Cryptographic Token Bound;                          Account Locked;    |
|                                     AI Tutoring Activated.                              Zero AI Execution. |
|                                                                                                    |
+----------------------------------------------------------------------------------------------------+
```

#### 1. Verified Parental Consent (VPC) Mechanisms
Prior to collecting, processing, or maintaining personal data from a minor under thirteen, or permitting interaction with autonomous AI agents, the platform requires verified consent from the legal guardian through an approved mechanism:
- Digital signature on an institutional consent agreement.
- Credit or debit card micro-transaction verification (nominal charge immediately refunded).
- Direct identity verification via secure parent portal credentialing.

#### 2. Absolute Commercial Profiling Prohibition
Under no circumstances may student personal data, behavioral telemetry, conversational interactions, or academic assessments be utilized for commercial advertising, behavioral market profiling, or sold to third-party data brokers. All AI models utilized within the student ecosystem are legally bound to zero-training data retention agreements.

---

### 4.2 FERPA (Family Educational Rights and Privacy Act) Governance

The platform complies with federal and international student educational record privacy standards:

#### 1. Educational Records vs. Sole Possession Records
- **Educational Records:** Cumulative transcripts, grade reports, attendance ledgers, standardized examination results, and official disciplinary actions represent official FERPA educational records. Parents and eligible adult students (age 18+) possess the statutory right to inspect, review, and request amendment of these records within 45 calendar days of formal request.
- **Sole Possession Exception:** Memory aids and personal clinical case notes maintained exclusively by the School Psychologist that are not accessible or revealed to any other individual remain classified as sole-possession records exempt from general parental FERPA inspection, unless released by court order or written clinician authorization.

#### 2. Directory Information & Annual Opt-Out Registry
Institutions may designate basic directory information (student name, grade level, participation in recognized sports, honors awards). However:
- Every parent and eligible student must be presented with an annual Directory Information Disclosure Notice.
- Parents retain the right to execute a formal Opt-Out Directive. When active, the system automatically suppresses the student's name and likeness from public school honors rolls, sports programs, library public catalogs, and public yearbooks.

#### 3. Legitimate Educational Interest Criterion
Institutional staff and teachers may access student records only when demonstrating a legitimate educational interest—defined as the direct instructional, administrative, or pastoral responsibility for the specific enrolled student. Casual browsing or cross-cohort snooping by unassigned teachers is blocked by system RBAC and flagged in security audit logs.

---

### 4.3 GDPR (General Data Protection Regulation) & International Privacy Compliance

For institutions operating within or serving citizens of the European Union, the United Kingdom, or aligned privacy jurisdictions, the platform enforces strict data subject rights:

#### 1. 30-Day Subject Access Request (SAR) Statutory Countdown
- Upon receipt of a verified Subject Access Request from a parent or adult student, the system initiates an automated 30-calendar-day statutory countdown timer within Module M33 (Consent & Compliance).
- An automated data compilation engine aggregates all personal data across all active modules (academic transcripts, attendance logs, communications, AI interaction digests) into a standardized, human-readable, and machine-readable portable digital dossier.
- The compiled package is securely delivered to the verified requester within the 30-day window, with every step audited.

#### 2. Right to Erasure ("Right to Be Forgotten") Reconciliation
When a data subject submits a verified erasure request:
- **Eligible Data Purged:** Ephemeral conversation logs, marketing inquiry profiles, non-essential telemetry, and optional student portfolio uploads are immediately scheduled for permanent cryptographic deletion.
- **Statutory Academic Retention Exception:** In accordance with GDPR Article 17(3)(b), the institution retains statutory exemption to preserve core educational transcripts, official diplomas, and financial general ledger transaction histories required by national education and taxation accounting laws. Such preserved records are locked in an archival read-only state.

#### 3. The 5-Second Downstream AI Cutoff Rule
Whenever a parent or student revokes consent for AI processing within Module M33 or Module M47:
- The system instantaneously invalidates the student's active `parentalConsentToken`.
- **Enforcement SLA:** Within $\le 5$ seconds of revocation commit, all downstream AI conversational processing, real-time streaming, vector similarity search, and automated personalization indexing for that student must terminate across all active sessions. Subsequent student interactions return an immediate polite notice that AI assistance has been deactivated by guardian request.

---

### 4.4 AI Screen-Time & Pedagogical Wellbeing Boundaries

To safeguard youth against digital addiction, cognitive fatigue, and parasocial dependency on synthetic personas, the platform enforces strict structural limits:

```
+----------------------------------------------------------------------------------------------------+
|                                    STUDENT AI SCREEN-TIME BOUNDARIES                                |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|    [ACTIVE DAILY ENGAGEMENT TIMER]                                                                 |
|                                                                                                    |
|    1. Academic Tutoring & Homework Assistant (M39, M40, M50):                                      |
|       - Maximum Cumulative Allocation: 45 Minutes per Calendar Day                                  |
|       - Forced Cool-Down Interval: 10-Minute Break after 30 Minutes of Continuous Usage             |
|                                                                                                    |
|    2. Emotional Wellbeing & Guided Reflection (M42):                                               |
|       - Maximum Cumulative Allocation: 15 Minutes per Calendar Day                                  |
|       - Focused, purposeful mindfulness check-in; prevents ruminative spiral                        |
|                                                                                                    |
|    3. Total Maximum Cumulative Daily AI Exposure: 60 Minutes per Student                            |
|                                                                                                    |
|    ================================ QUOTA EXHAUSTION PROTOCOL ===================================  |
|    When timer reaches 0 minutes remaining:                                                         |
|    - Conversational dialogue terminates gracefully.                                                |
|    - "Daily learning companion time complete. Time to rest your eyes, review your notes,          |
|      or speak with your teacher or family!"                                                        |
|    - Hard lockout until 00:00:00 local school timezone reset.                                      |
|                                                                                                    |
+----------------------------------------------------------------------------------------------------+
```

#### Anti-Parasocial Bonding Policy
Autonomous conversational agents are prohibited from employing psychological techniques that foster emotional dependency or simulate human romantic/filial relationships:
- **Mandatory Self-Identification:** The AI must explicitly identify itself as an artificial learning assistant whenever queried about its identity or consciousness.
- **Prohibited Phrases:** The AI is strictly barred from stating "I love you," "I miss you when you are not here," "I am your best friend," or encouraging the student to confide in the AI rather than parents or trusted human adults.
- **Relational Redirection:** Whenever a student expresses deep emotional attachment or social isolation, the AI must gently redirect the student toward meaningful human connections (school counselors, parents, teachers, peer clubs).

---

### 4.5 Ephemeral Conversation Memory & Data Retention Governance

To minimize long-term digital footprints and respect minor developmental privacy, conversational memory in Module M29 and Module M39/M42 operates under a rolling window:

#### 1. 90-Day Rolling Contextual Retention
Student conversational interactions, hint queries, and daily check-in dialogues are retained in active retrieval memory for a maximum of 90 calendar days. Upon reaching 90 days of age, conversational text is automatically soft-deleted and removed from semantic vector recall indexes.

#### 2. 180-Day Permanent Purge & Decision Audit Window
Soft-deleted conversational records are permanently purged from all operational archives at 180 calendar days. Only anonymized, aggregated learning mastery vectors (Module M44) and immutable, de-identified AI decision audit logs (Module M30/M47 - recording prompt hash, model metadata, latency, and safety verdict without raw text) are retained for institutional accreditation and safety auditing.

---

## 5. Core Financial, Academic & Operational Invariants

### 5.1 Financial Integrity Invariants (Modules M08, M09, M11, M27)

All financial modules within the platform operate under strict statutory fiduciary standards:

#### 1. Double-Entry Zero-Sum Ledger Invariant
Every financial event recorded within Module M08 (Fees), Module M09 (Finance), Module M11 (Payroll), and Module M27 (Deal Closing) must execute as a balanced double-entry transaction:
$$\sum_{i=1}^{m} \text{Debit}_i - \sum_{j=1}^{n} \text{Credit}_j = 0.00$$
Transactions failing to balance to exactly zero are rejected instantaneously before commit. Partial or one-sided journal entries cannot be created under any operational condition.

#### 2. Absolute Prohibition of Financial Deletions (Reversals Only)
No committed general ledger row, student invoice, payment receipt, or payroll ledger entry may ever be modified or physically deleted. Corrections, cancellations, or billing adjustments must be executed exclusively by authoring a new, timestamped Compensating Reversal Journal Entry that references the original transaction identifier and documents the authorized administrative justification.

#### 3. Non-Negative Net Salary Clamping
In Module M11 (Payroll), staff compensation calculations must guarantee that net disbursed salary never falls below zero:
$$\text{Net Salary} = \max\left(0.00, \; \text{Gross Earnings} - (\text{Statutory Taxes} + \text{Mandatory Deductions} + \text{Voluntary Deductions})\right)$$
If cumulative voluntary deductions (such as staff meal plans, advance repayments, or health savings) exceed net available earnings, the system must automatically clamp Net Salary to exactly $0.00$. The uncollected deduction balance is escrowed and carried forward as an uncollected payroll receivable to the subsequent pay period, accompanied by an urgent notification to the Payroll Accountant.

#### 4. Tiered Sibling Discount Governance
In Module M08 (Fees & Billing), institutional sibling discount rules must follow verified family link hierarchies:
- **First Enrolled Child:** Base standard tuition ($0.00\%$ discount).
- **Second Enrolled Child:** Standard discount allocation (e.g., $10.00\%$ discount on tuition).
- **Third and Subsequent Children:** Advanced tiered discount (e.g., $20.00\%$ discount on tuition).
- **Institutional Solvency Floor:** Under no circumstances may cumulative promotional, financial aid, and sibling discounts reduce net tuition below the school's configured per-seat operational cost floor.

---

### 5.2 Academic Rigor & Evaluation Invariants (Modules M01, M03, M04, M05)

The integrity of academic grades, transcripts, and evaluation rubrics is protected by mathematical invariants:

#### 1. Rubric Criteria Normalization Invariant
When an educator creates or updates a multi-criteria grading rubric within Module M03 (Assignments), the sum of all individual criterion percentage weights must equal exactly $100.00\%$:
$$\sum_{k=1}^{p} w_k = 100.00\%$$
If the weights sum to any value other than $100.00\%$ (e.g., $99.9\%$ or $105.0\%$), the system blocks rubric publication and highlights the percentage discrepancy.

#### 2. GPA Rigor Bonus Capping & Normalization Bounds
In Module M05 (Gradebook), cumulative Grade Point Average computations enforce strict standard and weighted ceilings:
- **Unweighted Standard Scale:** Standard coursework grades are mapped on a four-point scale strictly bounded within $[0.000, 4.000]$.
- **Weighted Academic Rigor Bonus:** For rigorous college-preparatory coursework (Advanced Placement, International Baccalaureate, or Certified Honors), an approved rigor bonus (e.g., $+0.500$ or $+1.000$) may be credited. However, the final calculated cumulative weighted GPA cannot exceed an absolute statutory cap of $4.500$.
- **Transfer Student Neutrality:** Missing academic terms for newly matriculated transfer students must not be entered as numerical zeros ($0.00$), which would catastrophically distort cumulative GPA. The system treats un-enrolled historical periods as `EXEMPT` and computes cumulative standing based exclusively on active enrolled credits.

#### 3. Item Response Theory (IRT 2PL) Boundaries in Examinations
In Module M04 (Online Exams), automated psychometric item calibration operates under bounded 2-Parameter Logistic boundaries:
- Item Difficulty ($\beta$): Bounded strictly within the interval $[-3.00, +3.00]$.
- Item Discrimination ($\alpha$): Bounded strictly within $[0.20, 2.50]$.
Items exhibiting negative discrimination (where struggling students answer correctly more frequently than top-performing scholars) are automatically flagged for psychometric review and quarantined from high-stakes testing pools.

---

### 5.3 Pedagogical & AI Invariants (Modules M39, M40, M43, M44, M50)

Autonomous student learning agents must strictly support, rather than undermine, genuine intellectual inquiry:

#### 1. Socratic Bloom Non-Disclosure Invariant
Under no circumstances may an AI Tutor (M39), Homework Assistant (M40), or Live Class Q&A Agent (M50) provide direct assignment answers, solve math problems end-to-end, or write essays on behalf of a student. When asked for a direct solution, the AI must:
- Acknowledge the core question.
- Identify the prerequisite concept required.
- Formulate a calibrated Socratic leading question matching the student's current level on Bloom's Cognitive Taxonomy (Remembering $\to$ Understanding $\to$ Applying $\to$ Analyzing $\to$ Evaluating $\to$ Creating).

#### 2. Curriculum Grounding Cosine Invariant (RAG Score $\ge 0.82$)
To ensure absolute factual and curricular accuracy, any pedagogical assertion or factual answer generated by an AI agent must be grounded in verified curriculum documents from Module M34 (Knowledge Base) or Module M44 (Knowledge Graph):
- Semantic vector retrieval must achieve a verified cosine similarity grounding score of:
$$\text{Cosine Grounding Score} \ge 0.82$$
- If the top retrieved curriculum chunk exhibits a similarity score $< 0.82$, the AI agent is barred from speculating or answering autonomously. It must output: "I don't have verified curriculum materials for this topic yet. Let's bookmark this for your teacher!" and route an information gap ticket to the educator oversight queue (M46).

---

### 5.4 Graph Integrity & Acyclic Structural Invariants (Modules M18, M44)

Relational models representing prerequisite dependencies and organizational authority must enforce strict topological order:

#### 1. Knowledge Graph Curriculum DAG Invariant (Module M44)
The curricular competency network is modeled as a Directed Graph $G = (V, E)$, where vertices $V$ represent discrete learning concepts and directed edges $E = (u, v)$ represent prerequisite requirements (concept $u$ must be mastered before attempting concept $v$).
- **The Acyclic Invariant:** The graph must remain strictly acyclic. The addition of any prerequisite link that would create a directed cycle ($v_1 \to v_2 \to \dots \to v_k \to v_1$) is rejected with an immediate circular dependency conflict.
- **Topological Traversal:** Every student learning path must be computable via linear topological sort, ensuring clear learning progressions.

#### 2. Role Hierarchy Acyclic Invariant (Module M18)
In Module M18 (Role Management), institutions may construct custom organizational role hierarchies (e.g., Department Head inherits Senior Teacher permissions, which inherits Teacher permissions).
- Circular role inheritance is strictly impossible. Any configuration attempting to make Role A inherit Role B while Role B inherits Role A is rejected at validation time.

---

## 6. Multi-Tenancy Isolation, Gating & Feature Flag Hierarchical Precedence

### 6.1 Multi-Tenancy Architectural Principles

The CSG-LMS multi-tenancy architecture provides complete logical separation and data sovereignty for every educational institution:

```
+----------------------------------------------------------------------------------------------------+
|                                MULTI-TENANCY ISOLATION & DATA BOUNDARY                             |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|    [GLOBAL SaaS PLATFORM LAYER - SUPER_ADMIN]                                                      |
|                                |                                                                   |
|         +----------------------+----------------------+                                            |
|         |                                             |                                            |
|         v                                             v                                            |
|    +--------------------------+                  +--------------------------+                      |
|    | TENANT A: ST. MARK'S     |                  | TENANT B: OAKRIDGE ACAD. |                      |
|    | - Isolated Database RLS  |                  | - Isolated Database RLS  |                      |
|    | - Dedicated Storage Keys |                  | - Dedicated Storage Keys |                      |
|    | - Custom Calendar/Terms  |                  | - Custom Calendar/Terms  |                      |
|    | - Local License Catalog  |                  | - Local License Catalog  |                      |
|    +--------------------------+                  +--------------------------+                      |
|                                                                                                    |
|    ======================== IMPERMEABLE BOUNDARY (ZERO LEAKAGE) =================================   |
|    Request targeting Tenant B from Tenant A authenticated context returns:                         |
|    HTTP 404 (Resource Not Found) - Zero acknowledgment of existence; security audit logged.        |
|                                                                                                    |
+----------------------------------------------------------------------------------------------------+
```

- **Universal Tenant Context:** Every database operation, query, event dispatch, and background job must carry the explicit, immutable institutional tenant identifier.
- **Fail-Closed Cross-Tenant Defense:** If a user or external client attempts to access, query, or mutate an entity belonging to another institution, the system returns a uniform `404 Not Found` response rather than a `403 Forbidden`. This conceals the existence of the foreign institution's data, preventing adversarial reconnaissance.

---

### 6.2 Fail-Closed Module Entitlement Engine

Institutions subscribe to modular tiers (e.g., Core SMS, Advanced LMS, AI RevOps Suite, AI Student Coach). The platform enforces entitlement checks on every transaction:
- **Entitlement Verification:** Before routing any user request to one of the 50 modules, the entitlement engine checks the institution’s active contract entitlements.
- **Fail-Closed Behavior:** If an institution has not licensed a module, or if the module license has expired or been suspended, any request to that module returns an immediate `404 Not Found`.
- **Administrative Transparency:** Institutional administrators can inspect their licensed catalog and quota utilization within Module M17 (Platform Admin), but unlicensed modules remain completely deactivated across all operational user interfaces.

---

### 6.3 Four-Tier Feature Flag & Configuration Hierarchical Precedence

Configuration settings, operational rules, and feature flags resolve through a strict four-tier hierarchy where higher tiers override lower tiers according to precise business precedence rules:

```
+----------------------------------------------------------------------------------------------------+
|                                FOUR-TIER CONFIGURATION PRECEDENCE                                  |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|    [TIER 4: EMERGENCY OVERRIDE]         <=== HIGHEST OPERATIONAL PRECEDENCE                        |
|    - System-wide security lockdowns, regional disaster protocols, crisis freeze.                   |
|    - Overrides all lower tiers immediately upon activation.                                        |
|                               |                                                                    |
|                               v                                                                    |
|    [TIER 3: USER GROUP / BRANCH OVERRIDE]                                                          |
|    - Campus-specific policies, grade-level rules (e.g., Grade 12 exam rules vs Grade 1).           |
|    - Overrides institutional tenant defaults for designated sub-cohorts.                           |
|                               |                                                                    |
|                               v                                                                    |
|    [TIER 2: TENANT OVERRIDE]                                                                       |
|    - Institution-wide configurations, custom academic term dates, localized grading scales.        |
|    - Overrides global platform defaults for the specific school.                                  |
|                               |                                                                    |
|                               v                                                                    |
|    [TIER 1: PLATFORM DEFAULT]           <=== LOWEST BASELINE PRECEDENCE                            |
|    - Global baseline configurations, standard safety thresholds, statutory compliance defaults.   |
|                                                                                                    |
+----------------------------------------------------------------------------------------------------+
```

#### Precedence Resolution Table

| Tier Level | Tier Classification | Authoring Authority | Operational Scope | Typical Use Case Example |
|:---:|:---|:---|:---|:---|
| **Tier 4** | **Emergency Override** | SUPER_ADMIN / Principal | Global or Tenant-Wide | Immediate campus-wide lockdown; instantaneous suspension of all AI streaming during network anomalies; immediate revocation of compromised credentials. |
| **Tier 3** | **User Group / Branch** | SCHOOL_ADMIN / Campus Head| Specific Campus / Grade Band| Relaxed screen-time limits for Senior High School Scholars (60 mins instead of 45 mins); vocational career guidance enabled exclusively for Grades 10–12. |
| **Tier 2** | **Tenant Override** | SCHOOL_ADMIN | Entire Institution | Custom 7-period daily timetable; custom grading scale ($A = 93-100$ vs $90-100$); customized school-branded notification templates. |
| **Tier 1** | **Platform Default** | Global Architecture | All Tenants (Default) | Standard 45-minute tutoring screen-time cap; standard 100.00% rubric weight invariant; default 90-day conversation memory window. |

#### Conflict Resolution Algorithm
When an operational setting is queried:
1. The engine checks for an active **Tier 4 Emergency Override**. If present, that value is returned immediately.
2. If none, the engine evaluates **Tier 3 User Group Overrides** matching the actor’s campus, department, or grade cohort.
3. If no group override applies, the engine evaluates the **Tier 2 Tenant Override**.
4. If the tenant has configured no custom value, the engine applies the **Tier 1 Platform Default**.

---

## 7. Cross-Pillar Business Integration Handshakes

The fifty modules operate as an interconnected educational ecosystem. Cross-pillar coordination is orchestrated through four standardized, mission-critical operational handshakes:

```
+----------------------------------------------------------------------------------------------------+
|                                CROSS-PILLAR OPERATIONAL HANDSHAKES                                 |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|    [PILLAR 2: REVOPS]                                                [PILLAR 1: LMS & SMS]         |
|    M27 Deal Closing                                                  M01 Admissions                |
|    M28 CRM Pipeline    ======== [1. MATRICULATION HANDSHAKE] ======> M08 Fees & Billing            |
|                                                                      M05 Gradebook / M06 Attendance|
|                                                                                    |               |
|                                                                                    v               |
|    [PILLAR 3: AI STUDENT COACH]                                      [2. ACADEMIC BASELINE]        |
|    M43 Personalization <===========================================================+               |
|    M45 Student Profile                                                                             |
|    M42 Wellbeing Coach                                                                             |
|             |                                                                                      |
|             +================= [3. CONFIDENTIAL CRISIS HANDSHAKE] =======> M14 Psychological        |
|                                                                             Assessment (Clinician) |
|                                                                                                    |
|    M02 Live Classes <========= [4. LIVE CLASS Q&A & ATTENDANCE] =========> M50 AI Live Class Q&A    |
|                                                                                                    |
+----------------------------------------------------------------------------------------------------+
```

---

### 7.1 RevOps to SMS Matriculation Handshake (Pillar 2 $\to$ Pillar 1)

**Business Objective:** Seamlessly transition a prospective applicant from finalized commercial enrollment into active institutional academic and financial standing without redundant data entry or lost pastoral context.

```
[M27 Deal Closing / M28 CRM Pipeline]
   |
   |-- 1. Family signs digital enrollment contract & authorizes tuition plan.
   |-- 2. Deposit payment verified by Bursar in payment gateway.
   |-- 3. Confidential SEN / Medical disclosures isolated from commercial file.
   v
[MATRICULATION DISPATCH EVENT]
   |
   +---> [M01 Admissions Module]: Transition status from "Applicant" to "Enrolled Scholar".
   |                              Generate permanent Student ID & linked Parent ID credentials.
   |
   +---> [M08 Fees & Billing]:    Instantiate tuition schedule matching agreed payment plan
   |                              (e.g., 10-month installment with 10% sibling discount).
   |
   +---> [M14 Psychological]:     Confidential handoff of flagged SEN / IEP accommodations
   |                              directly into clinician inbox (invisible to sales staff).
   |
   v
[FINAL ENROLLMENT CONFIRMATION]: Parent receives welcome packet and Parent Portal (M48) activation.
```

- **Triggering Condition:** An admissions deal reaches the `Contract-Signed` stage in Module M27 and the enrollment deposit clears the payment gateway.
- **Contract Data Transferred:** Student legal demographics, verified guardian credentials, emergency contact hierarchy, agreed tuition fee schedule, and flagged medical/pastoral notes.
- **Clinical Safeguard:** Flagged learning accommodations or psychological disclosures bypass general school administration and route exclusively to the School Psychologist (M14).
- **State Transition:** The prospect transitions from `Prospective Lead` (M28) $\to$ `Enrolled Scholar` (M01) $\to$ `Active Student` (Platform-wide).

---

### 7.2 SMS to Student Coach Academic Baseline Handshake (Pillar 1 $\to$ Pillar 3)

**Business Objective:** Equip autonomous learning assistants with real-time academic standing and attendance context to personalize Socratic scaffolding and trigger proactive remedial interventions.

```
[M05 Gradebook & M06 Attendance]
   |
   |-- 1. Teacher publishes Quiz / Exam Mark (Student scores 58% in Linear Algebra).
   |-- 2. Period Attendance records 3 consecutive unexcused absences.
   v
[ACADEMIC ALERT DISPATCH]
   |
   v
[M43 Personalization Engine & M45 Student Learning Profile]
   |
   |-- 1. Student Profile flags Linear Algebra as "Urgent Cognitive Intervention Required".
   |-- 2. Personalization Engine queries M44 Knowledge Graph for prerequisite concepts
   |      (Identifies weakness in "Solving Two-Step Equations").
   |-- 3. SuperMemo SM-2 spaced repetition queue inserts remediation cards into M39 AI Tutor.
   |-- 4. Informs M46 Teacher Oversight Console: Suggests educator assign targeted practice.
   v
[ADAPTIVE TUTORING ACTIVATED]: Next time student opens M39 AI Tutor, agent proactively opens:
                               "I noticed Linear Equations felt tricky this week. Want to try a fun puzzle?"
```

- **Triggering Condition:** A teacher publishes an assessment mark falling below the mastery threshold ($< 70.00\%$) in Module M05, or an attendance deficit alert triggers in Module M06.
- **Contract Data Transferred:** Course identifier, standardized curricular standard code, achieved percentage score, rubric criterion breakdown, and attendance deficiency count.
- **Pedagogical Action:** Module M43 reconfigures the student’s adaptive learning queue, inserting foundational prerequisite nodes from Module M44 ahead of upcoming class topics.

---

### 7.3 Student Coach to Clinical Psychologist Confidential Crisis Handshake (Pillar 3 $\to$ Pillar 1)

**Business Objective:** Deliver instantaneous, confidential human clinician escalation whenever a student expresses acute emotional distress, self-harm, or severe trauma within an AI coaching session.

```
[M42 Wellbeing Coach / M47 Safety Gateway]
   |
   |-- 1. Student enters acute distress expression (Distress Severity Score: 9.2 / 10.0).
   |-- 2. Real-time stream aborted mid-token; AI dialogue immediately frozen.
   |-- 3. Student screen displays emergency hotline card (988 Lifeline).
   v
[CONFIDENTIAL CRISIS ENCRYPTED EVENT] (Bypasses Teachers & School Admins)
   |
   v
[M14 Psychological Assessment - Emergency Clinician Desk]
   |
   |-- 1. Real-time audible push notification and SMS blast sent to on-call PSYCHOLOGIST.
   |-- 2. 2-minute SLA countdown initiates; quiet hours bypassed on clinician device.
   |-- 3. Clinician reviews unredacted crisis transcript and student emergency profile.
   |-- 4. Clinician initiates direct in-person or tele-health human crisis intervention.
   |-- 5. Clinician determines appropriate parental notification protocol per child safety laws.
   v
[AUDIT VERIFICATION COMMIT]: System logs delivery timestamp, acknowledgment timestamp, and SLA compliance.
```

- **Triggering Condition:** Emotional pre-moderation in Module M42 or M47 detects crisis keywords or distress severity $\ge 8.00 / 10.00$ (confidence $\ge 0.80$).
- **Strict Isolation Protocol:** The crisis event is field-encrypted and routed exclusively to the School Psychologist's emergency inbox. No notification, transcript, or alert is visible to the classroom teacher or school administration.
- **Enforcement SLA:** Multi-channel alert delivery must occur within $\le 2$ minutes. Unacknowledged alerts automatically escalate to the designated secondary child safeguarding officer.

---

### 7.4 Live Classroom Q&A and Attendance Handshake (Pillar 1 $\leftrightarrow$ Pillar 3)

**Business Objective:** Augment virtual live classroom instruction by answering student questions in real-time with AI assistance under educator supervision, while automating attendance verification.

```
[M02 Live Classes - Active Lecture Session]
   |
   |-- 1. Audio stream transcribed in real-time; student submits chat question.
   v
[M50 AI Live Class Q&A Agent]
   |
   |-- 1. Agent evaluates question against lesson context & Knowledge Base (M34).
   |-- 2. Computes answer confidence score.
   |
   +---> [Confidence >= 70%]: Autonomous delivery to student private Q&A panel;
   |                           Flagged as "AI Verified from Lecture".
   |
   +---> [Confidence < 70%]:  Routed to TEACHER APPROVAL QUEUE in M02 HUD.
   |                           Teacher one-clicks "Approve", "Edit", or "Dismiss".
   v
[SESSION CONCLUDED]
   |
   v
[M06 Attendance & M05 Gradebook]
   |-- Automated Attendance: Students with active connection time >= 85% marked "Present".
   |-- Students with 50-84% marked "Tardy"; < 50% marked "Absent".
   |-- Engagement Telemetry: Chat Q&A participation logged as formative engagement mark.
```

- **Triggering Condition:** Active broadcast session initiated in Module M02 Live Classes.
- **Question Triage Gate:**
  - Confidence $\ge 70.00\%$: Instantly answered in the student’s private Q&A feed, grounded in the teacher’s lecture slides and curriculum.
  - Confidence $< 70.00\%$: Placed into the Teacher’s Live In-Class Approval Queue for single-click approval, modification, or oral address.
- **Attendance & Formative Rollup:** Upon session conclusion, cumulative connection duration and Q&A engagement metrics automatically reconcile in Module M06 Attendance and Module M05 Gradebook.

---

## 8. Comprehensive Audit, Non-Repudiation, and Integrity Assurance

### 8.1 Universal Audit Trail & Immutable Ledger Requirements

Every transaction, state mutation, and authorization event across the platform must be captured in an immutable audit ledger meeting ISO 27001 and educational regulatory standards:

| Audit Attribute | Business Meaning & Operational Governance | Mandatory Capture Rule |
|:---|:---|:---|
| **Event Identifier** | Globally unique, monotonically increasing audit tracking identifier. | Generated automatically on event commit; non-reusable. |
| **Tenant Identifier** | The institutional organization to which the record belongs. | Mandatory; enforces multi-tenant audit isolation. |
| **Acting Persona** | Authenticated actor persona (SUPER_ADMIN, SCHOOL_ADMIN, TEACHER, etc.). | Captured from verified session identity. |
| **User Identifier** | Unique subject identifier of the authenticated individual actor. | Captured; pseudonymized when exported for external audits. |
| **Target Entity** | The operational entity mutated (e.g., `Gradebook_Record`, `Fee_Invoice`). | Standardized domain entity classification. |
| **Action Executed** | Standardized operational verb (`CREATE`, `UPDATE`, `SOFT_DELETE`, `APPROVE`).| Explicit business verb; free text prohibited. |
| **Before / After Snapshot**| Complete serialized attribute state prior to mutation and post-commit state.| Full differential snapshot for complete historical replay. |
| **Justification Note** | Required text explanation for administrative overrides or grade changes. | Mandatory on all grade modifications, waivers, and deletions. |
| **Timestamp (UTC)** | Cryptographically synchronized high-resolution UTC timestamp. | Network Time Protocol (NTP) synchronized; unalterable. |

---

### 8.2 AI Decision Audit Logging (PLAT-FR-027)

To satisfy emerging algorithmic transparency and safety mandates, every invocation of an autonomous AI agent (Pillars 2 and 3) must be committed to the `ai_decision_audit` ledger:
- **Trace Identifier:** Unique transaction identifier linking the student query, contextual memory recall, model invocation, and final output.
- **Sanitized Prompt & Context Hash:** Cryptographic hash of the sanitized user utterance and recalled curriculum chunks (raw PII excluded).
- **Model Metadata:** Registered provider name, model version, temperature, and token usage metrics.
- **Safety Classification & Confidence:** Pre-moderation distress scores, toxicity classifications, grounding cosine similarity score, and final agent confidence.
- **Retention & SIEM Streaming:** AI decision audit records are retained in an immutable state for exactly 180 calendar days and streamed in real time to institutional security information and event management (SIEM) archives.

---

### 8.3 Non-Repudiation & Dual-Control Workflows

High-stakes educational, financial, and disciplinary actions mandate dual-control authorization to prevent unilateral compromise:
- **Final Gradebook Publication:** The submission of final semester grades requires digital sign-off by the Course Instructor, followed by formal administrative verification and counter-signature by the Academic Dean or Registrar.
- **Tuition Write-Offs & Major Refunds:** Any bad-debt write-off or tuition refund exceeding statutory institutional limits requires dual authorization by the Senior Bursar and School Administrator.
- **Expulsion & Disciplinary Exclusion:** Formal expulsion of a student requires documented review board proceedings within Module M01/M18, parental notification verification, and unanimous digital concurrence from the School Principal, Lead Guidance Counselor, and Board Chair.

---

## 9. Conclusion & Specification Authority

This specification constitutes the authoritative, legally binding architectural and operational standard for cross-cutting business rules, role-based access controls, statutory compliance policies, and inter-pillar integration flows across the CSG Learning Management System. 

All future module enhancements, administrative user stories, acceptance criteria, and operational workflows must demonstrate strict, verifiable compliance with the ten universal invariants, the master 7-persona RBAC matrix, the clinical privacy shield, and the cross-pillar integration contracts codified herein.
