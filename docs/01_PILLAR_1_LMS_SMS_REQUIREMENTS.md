# Business Functional Requirements Specification
# Pillar 1: Core Platform Foundation, Learning Management System (LMS) & School Management System (SMS)

**Document Reference:** CSG-BFR-P1-001  
**Target Scope:** Core Platform Foundation & Modules M01 through M20  
**Version:** 1.0.0 (Authoritative Master Specification)  
**Classification:** Business & Product Requirements (Strict Zero-Code & Zero-DDL Implementation Exclusion)  
**Compliance Standards:** ISO/IEC/IEEE 29148 (Requirements Engineering), ISO 27001 (Information Security), ISO 27018 (Cloud PII Privacy), FERPA (Family Educational Rights and Privacy Act), Cognia Accreditation Standards  

---

## 1. Executive Overview & Academic Operational Paradigm

### 1.1 Architectural Vision
The CSG Learning Management System (CSG-LMS) operational core embodies an enterprise-grade digital backbone engineered to power institutional education. Functioning as a unified operating system for Pre-K through Grade 12 academies, higher-education faculties, and multi-campus educational networks, Pillar 1 integrates academic administration, lifecycle student record management, instructional delivery, billing governance, statutory human resources, and compliance assurance.

The platform unifies two traditionally disparate software categories:
1. **The Learning Management System (LMS)**: Drives pedagogic orchestration, virtual live classrooms, rubric-based coursework evaluations, secure computer-based testing with item psychometrics, digital library holdings, and educational tool interoperability.
2. **The School Management System (SMS)**: Operates statutory institutional mechanics, including prospective student admissions, period-level attendance, multi-variable timetable constraint solving, tuition billing with compounding late-interest management, double-entry general ledger accounting, staff payroll with progressive tax withholding, transport logistics telemetry, and institutional accreditation self-study dossiers.

### 1.2 Academic Operations & Platform Tenets
Pillar 1 operates under four non-negotiable operational tenets:
- **Academic Rigor & Equity**: Grading, ranking, and admissions models must be mathematically transparent, auditable, and resilient against bias or distortion (such as penalizing first-time students who lack prior academic history).
- **Institutional Multi-Tenancy**: Every educational institution operates within an impermeable organizational boundary with dedicated entitlement licensing, custom academic calendars, and localized operational policies.
- **Fail-Closed Governance**: Administrative, financial, and evaluation actions follow explicit deny-by-default rules. Disabled modules, expired licenses, or unverified privileges reject operations immediately without disclosing internal systemic states.
- **Ethical & Clinical Data Safeguarding**: Student records, family financial telemetry, and clinical mental health case files are partitioned by strict confidentiality boundaries, preventing administrative overreach or unauthorized disclosure.

---

## 2. The 7-Persona Academic Framework & Clinical Data Isolation Guardrail

### 2.1 Persona Definitions and Operational Scopes

The platform governs all interactions through seven mutually exclusive, standardized academic personas:

```
+-------------------------------------------------------------------------------+
|                       7-PERSONA GOVERNANCE TAXONOMY                           |
+-------------------------------------------------------------------------------+
|                                                                               |
|   [SUPER_ADMIN]      Multi-tenant platform operator; global infrastructure    |
|         |            compliance, tenant provisioning, system SLA uptime.      |
|         v                                                                     |
|   [SCHOOL_ADMIN]     Institutional executive (Principal, Registrar, Bursar);  |
|         |            academic setup, staff policies, digital report card sign.|
|         +-----------------------+-----------------------+                     |
|         |                       |                       |                     |
|         v                       v                       v                     |
|     [TEACHER]                [STAFF]              [PSYCHOLOGIST]              |
|   Instructional leader;   Operational teams;    Licensed clinician;           |
|   curriculum, exams,      admissions, finance,  wellbeing, crisis triage,     |
|   rubrics, live classes.  library, transport.   clinical notes (ISOLATED).    |
|         |                       |                                             |
|         +-----------+-----------+                                             |
|                     |                                                         |
|                     v                                                         |
|                 [STUDENT] <===================> [PARENT]                      |
|             Primary learner;             Legal guardian; tuition settlement,  |
|             coursework, exams, badges.   absence excuses, privacy consent.    |
|                                                                               |
+-------------------------------------------------------------------------------+
```

1. **SUPER_ADMIN (Platform Operator)**:
   - *Operational Scope*: Possesses cross-tenant governance, provisioning institutional organizations, enforcing global licensing tiers, inspecting infrastructure health metrics, auditing multi-tenant data boundaries, and triggering emergency operational kill-switches.
   - *Security Requirement*: Mandatory hardware-backed Multi-Factor Authentication (MFA/TOTP), session anomaly inspection, and read-only cross-tenant administrative access.

2. **SCHOOL_ADMIN (Institutional Executive — Principal, Registrar, Bursar, HR Director)**:
   - *Operational Scope*: Holds top-tier authority within a specific institutional tenant. Configures academic years, terms, and grading scales; oversees staff hiring, department allocation, and payroll disbursement; authorizes fee schedules; signs official transcripts; and resolves institutional exceptions.
   - *Security Requirement*: Mandatory MFA/TOTP, role-delegation logging, and segregation-of-duties enforcement (barred from approving self-authored change requests).

3. **TEACHER (Instructional Leader & Assessor)**:
   - *Operational Scope*: Manages assigned course sections; conducts live interactive virtual classrooms; authors assignments, exams, and grading rubrics; records period attendance; submits report card marks; and monitors student academic progress.
   - *Security Requirement*: Scoped strictly to assigned courses, periods, and enrolled cohorts; prohibited from inspecting cross-departmental records or unassigned students.

4. **STUDENT (Primary Learner)**:
   - *Operational Scope*: Accesses learning materials, participates in live virtual lectures, submits coursework, sits for proctored examinations, reviews personal grades and attendance records, borrows library media, and interacts with educational software tools.
   - *Security Requirement*: Scoped exclusively to personal academic records; low-friction biometric or password authentication on trusted devices.

5. **PARENT (Legal Guardian & Financial Sponsor)**:
   - *Operational Scope*: Manages family profile; monitors academic progression and attendance for linked children; settles tuition invoices via hosted checkout; applies for installment agreements; submits medical absence excuse requests; and grants statutory legal/AI consent for minors.
   - *Security Requirement*: Scoped strictly to legally linked dependents; prohibited from viewing other learners or unlinked institutional records.

6. **STAFF (Operational Support Specialist — Admissions Officer, Accountant, Librarian, Bus Driver)**:
   - *Operational Scope*: Executes specialized day-to-day administrative functions within assigned operational domains (e.g., screening admission documents, recording journal vouchers, processing library book loans, operating transport routes).
   - *Security Requirement*: Least-privilege departmental role assignment; session tracking; strictly bounded access to departmental tools.

7. **PSYCHOLOGIST (Licensed Mental Health Counselor & Clinical Evaluator)**:
   - *Operational Scope*: Manages student emotional wellbeing; conducts specialized developmental and psychological evaluations; authors confidential clinical case notes; coordinates Individualized Education Programs (IEP); triages mental health crises; and oversees confidential counseling communications.
   - *Security Requirement*: The most restricted persona on the platform, protected by the Clinical Data Isolation Guardrail.

### 2.2 The Psychologist Clinical Data Isolation Guardrail
Under international student privacy mandates (FERPA, HIPAA where applicable, ISO 27018, and GDPR Article 9 special-category data), mental health records cannot be treated as general student academic data. CSG-LMS enforces a strict, architectural, and procedural barrier around clinical files:

- **Absolute Clinical Confidentiality**: Psychological assessments, crisis triage records, psychotherapeutic case notes, and mental health counseling logs are accessible **exclusively** by users authenticated under the active `PSYCHOLOGIST` persona.
- **Categorical Denial for Administrative & Academic Personas**: School Principals (`SCHOOL_ADMIN`), Teachers (`TEACHER`), Admissions Staff (`STAFF`), and Parents (`PARENT`) are categorically blocked from viewing, searching, or decrypting clinical notes. Any access attempt by unauthorized personas results in an immediate authorization failure, emits a high-priority security audit event, and logs the incident.
- **Client-Side Cryptographic Boundary**: Clinical case notes are encrypted on the client device prior to network dispatch using authenticated symmetric encryption (AES-256-GCM). The platform persistence plane stores only encrypted payloads and wrapped key envelopes. Decryption keys are derived exclusively from the licensed psychologist's authenticated session credentials. Neither database administrators nor platform super administrators possess the cryptographic means to read stored clinical notes.
- **Minor Parental Consent Enforcement**: In accordance with minor protection laws, no formal psychological evaluation may be initiated for a student under the age of majority without explicit, digitally timestamped parental consent. The system halts clinical assessment workflows in an un-consented state until verified parent authorization is registered.
- **Anonymized Institutional Escalation**: When a clinical evaluation indicates acute safety risks, the system permits the psychologist to emit high-priority operational alerts to the School Principal without disclosing clinical notes or diagnostic narratives. The notification communicates only the mandatory protective action and urgency tier.
- **Immutable Clinical Audit Trail**: Every access event, note modification, consent verification, and decryption operation generates an immutable audit entry capturing the psychologist's identity, timestamp, IP address, and access justification.
- **Statutory Retention & Cryptographic Shredding**: In compliance with legal record retention mandates, clinical files are preserved for exactly 7 years following a student's legal age of majority. Upon reaching retention expiration, records undergo cryptographic shredding—the master key envelopes are destroyed, rendering historical ciphertext permanently unrecoverable across all storage tiers and backup archives.

---

## 3. Core Platform Foundation Functional Requirements

### 3.1 Authentication, Identity Lifecycle & Session Management
- **Centralized Identity & Single Sign-On (SSO)**: The platform provides unified authentication across web portals and mobile applications. Users authenticate once to access all licensed academic and administrative modules permitted by their assigned persona.
- **Mandatory Multi-Factor Authentication (MFA/TOTP)**:
  - MFA is mandatory for administrative personas (`SUPER_ADMIN`, `SCHOOL_ADMIN`) and recommended for staff handling financial or clinical records.
  - Enrollment requires time-based one-time password (TOTP) applications or FIDO2/WebAuthn hardware tokens.
  - Authentication challenges require valid second-factor verification prior to granting access to administrative control consoles. Administrative accounts are issued single-use cryptographic recovery codes stored securely off-platform.
- **Low-Friction Quick-Login for Students and Parents**:
  - Native mobile clients support biometric quick-login (Touch ID, Face ID, Android Biometric Prompt) bound to local device hardware keys following initial primary authentication.
  - Quick-login tokens enforce a maximum lifetime of 30 days before requiring full primary credential re-authentication.
- **Session Tracking & Remote Invalidation**:
  - The identity subsystem maintains an active inventory of concurrent user sessions, capturing device fingerprint, client user-agent, IP geolocation, and creation timestamps.
  - Users can view active sessions and selectively terminate sessions on lost or unfamiliar devices.
  - School Administrators can terminate all active sessions for any institutional user immediately upon employee resignation, student suspension, or credential compromise.
- **Centralized Token Revocation**:
  - When an account is suspended, its password updated, or an administrative session reset triggered, all issued access and refresh tokens are invalidated instantaneously across all gateway proxies and edge caches.

### 3.2 Multi-Tenancy Architecture & Entitlement Governance
- **Strict Tenant Boundaries**:
  - Educational institutions operate as distinct organizational tenants. All operational, academic, demographic, and financial records are logically partitioned by an immutable institutional identifier.
  - Data queries, background jobs, and event consumers operate strictly within the authenticated tenant boundary. Cross-tenant record leakage is structurally prohibited.
- **Per-Tenant Functional Entitlements**:
  - Platform administrators license functional modules (e.g., M01 through M20) on a per-tenant basis according to institutional service tier agreements (`Standard`, `Premium`, `Enterprise`).
- **Fail-Closed Module Gating**:
  - If an institution has not licensed or enabled a specific module, all user interactions targeting that module fail closed. The platform returns a standard "Not Found" response, preventing unauthorized callers from enumerating whether a feature exists or probing institutional license limits.
- **Inter-Module Dependency Verification**:
  - The entitlement engine validates prerequisite functional dependencies. A module cannot be activated if its mandatory operational foundations are disabled (e.g., M05 Gradebook cannot be active if M07 Timetable is disabled).
- **Emergency Functional Kill-Switch**:
  - Platform administrators possess real-time control to disable any malfunctioning or breached module across a specific tenant or globally without requiring system redeployment or platform downtime.

### 3.3 Omnichannel Notification & Alerting Engine
- **Multi-Channel Dispatching**:
  - The notification engine delivers messages across five synchronized channels: Mobile Push (iOS APNs / Android FCM), In-App Notification Center, SMS Gateway, Institutional Email, and WhatsApp Business API.
- **Contextual Mobile Deep Linking**:
  - Push notifications encapsulate structured deep-link navigation parameters, directing users directly to the actionable UI view (e.g., opening an overdue assignment, launching a live virtual classroom, or viewing a newly posted tuition invoice).
- **Device Token Hygiene & Tenant Scoping**:
  - Push notification device tokens are registered exclusively within the user's institutional context.
  - Device tokens reporting delivery failure, uninstallation, or expiration from mobile push gateways are pruned immediately to maintain routing efficiency.
- **Priority-Tiered Routing & Delivery SLAs**:
  - Notifications are classified into four delivery tiers: `Low` (informational digests), `Normal` (course updates, daily homework), `High` (same-day schedule changes, fee payment receipts), and `Emergency/Crisis` (urgent safety alerts, child distress, bus breakdown).
  - High-priority notifications guarantee delivery attempt dispatch within 5 seconds; Emergency/Crisis alerts guarantee dispatch within 2 seconds.
- **Quiet Hours & Emergency Override Rules**:
  - Standard notifications respect user-configured quiet hours (e.g., 21:00 to 07:00 local school time), queuing non-urgent alerts until the morning delivery window.
  - **Emergency Crisis Override**: Notifications flagged with an emergency priority or originating from student crisis triage (severity score $\ge 8$) strictly bypass quiet-hours suppression, emitting audible high-priority device alerts and immediate multi-channel dispatches (SMS and Mobile Push).

### 3.4 Feature Flags & Hierarchical Overrides
- **Four-Tier Configuration Precedence**:
  - System operational toggles, numerical thresholds, and business rules resolve dynamically through a 4-tier hierarchy:
    $$\text{Platform Baseline Defaults} \to \text{Tenant Organization Overrides} \to \text{Functional Module Overrides} \to \text{Environment Overrides}$$
  - A value defined at a more specific level supersedes broader configurations.
- **Segregation of Duties & Two-Person Rule**:
  - Critical platform configuration changes (e.g., altering tax bracket tables, changing student retention rules, or modifying proctoring anomaly thresholds) require submission of a formal change proposal.
  - The author of a configuration change is barred from approving their own request. Approval requires formal sign-off by an independent administrative reviewer.
- **Pre-Apply Snapshot Backup & Rollback**:
  - Prior to applying a new configuration version, the system captures an immutable snapshot of the active state. If downstream validation or service propagation fails, the system executes an automated rollback to the snapshot state, emitting administrative alerts.

---

## 4. Pillar 1 Module-by-Module Deep Functional Specifications (M01 – M20)

```
+---------------------------------------------------------------------------------------------------+
|                           PILLAR 1: LMS & SMS MODULE TAXONOMY (M01 - M20)                         |
+------------------------------------+----------------------------------+---------------------------+
| Academic & Learning (LMS)          | School Operations & Admin (SMS)  | Governance & Platform     |
+------------------------------------+----------------------------------+---------------------------+
| M01 Admissions & Enrollment        | M06 Attendance Tracking          | M16 Cognia Evidence       |
| M02 Live Virtual Classrooms        | M07 Timetable & Scheduling       | M17 Platform Admin        |
| M03 Assignments & Rubrics          | M08 Fee Management & Billing     | M18 User & Role Mgmt      |
| M04 Examinations & Proctoring      | M09 Financial Mgmt & GL          | M19 Reports & Analytics   |
| M05 Gradebook & Transcripts        | M10 HR & Staff Management        | M20 Settings & Calendars  |
| M12 Digital Library & Tools        | M11 Payroll Processing           |                           |
| M13 Communication Hub              | M15 Transport Logistics          |                           |
| M14 Psychological & Crisis Triage  |                                  |                           |
+------------------------------------+----------------------------------+---------------------------+
```

---

### M01: Admissions & Student Enrollment

#### Business Purpose & Scope
The Admissions module governs the prospective student intake pipeline from initial inquiry through application submission, documentation verification, entrance examination, standardized interview scoring, committee review, admission offer issuance, tuition deposit collection, and formal LMS/SMS matriculation.

#### Actor Roles & Trigger Events
- **Prospective Student / Parent**: Initiates application; uploads identity and academic documentation; accepts admission offer; pays enrollment deposit.
- **Admissions Officer (Staff)**: Verifies uploaded certificates; reviews eligibility; schedules entrance exams and interviews; tracks admissions quota.
- **School Administrator (Principal / Admissions Director)**: Authorizes grade-level capacities; evaluates committee recommendations; approves final admission offers and waitlist promotions.
- **School Psychologist**: Conducts developmental readiness screenings for early-years candidates and applicants flagged with specialized educational support needs.
- **Trigger Events**: Application submitted online; entrance examination completed; interview rubric scored; committee evaluation finalized; deposit payment confirmed.

#### Core Functional Capabilities & User Stories
- **Multi-Stage Digital Application Intake**: Captures student demographic information, target grade level (Pre-K through Grade 12), prior educational transcripts, and mandatory compliance uploads (birth certificate, immunization records, passport/national ID, legal guardianship documents).
- **Automated Lead Readiness Scoring**: Aggregates examination, interview, prior academic performance, and profile completeness into an objective composite admission score ($S_{adm}$).
- **Standardized Multi-Criteria Interview Rubric**: Evaluators assess candidate communication, social development, and academic readiness using structured rubric scales, rescaled into a standardized 100-point index.
- **Capacity-Controlled Waitlist Governance**: Automatically ranks qualified applicants against real-time grade-level seat quotas. Candidates exceeding capacity are placed on a prioritized waitlist based on composite score and application timestamp.
- **Automated Matriculation Handoff**: Upon receipt of the non-refundable enrollment deposit, the system transitions the applicant to matriculated status, creates student and parent records in User Management (M18), sets up tuition billing schedules in Fee Management (M08), and establishes cumulative academic records in Gradebook (M05).

#### End-to-End Business Workflows & State Machine Lifecycles
```
[DRAFT] ---> [SUBMITTED] ---> [UNDER_REVIEW] ---> [INTERVIEWED] ---> [OFFERED] ---> [ENROLLED]
                 |                  |                   |                |
                 v                  v                   v                v
            [WITHDRAWN]         [REJECTED]          [WAITLISTED]     [EXPIRED/DECLINED]
```
- `DRAFT`: Applicant is assembling personal details and uploading documents; edits freely allowed.
- `SUBMITTED`: Application formally filed with proof of application fee; documents locked against modification without officer authorization.
- `UNDER_REVIEW`: Admissions staff verifying documentation authenticity and eligibility criteria.
- `INTERVIEWED`: Entrance examination and structured interview rubrics recorded.
- `WAITLISTED`: Qualified candidate placed in rank-ordered waitlist pending seat availability.
- `OFFERED`: Formal acceptance offer extended with tuition deposit deadline.
- `ENROLLED`: Deposit settled; student matriculated into institutional student directory.
- Terminal Alternative States: `REJECTED` (candidate fails criteria), `WITHDRAWN` (parent terminates application), `EXPIRED` (offer deadline lapses without deposit payment).

#### Domain Validation Rules, Invariants & Mathematical Formulations
- **Composite Lead Score Formulation**:
  $$S_{adm} = 0.35\,S_{exam} + 0.30\,S_{interview} + 0.20\,S_{gpa} + 0.15\,S_{profile}$$
  - $S_{exam}$: Entrance examination percentile rank ($0.00 - 100.00$).
  - $S_{interview}$: Standardized interview score ($0.00 - 100.00$).
  - $S_{gpa}$: Prior academic GPA normalized to a 100-point scale ($S_{gpa} = 25 \times \text{prior\_gpa}$ for a 4.00 scale).
  - $S_{profile}$: Profile completeness and catchment fit index ($0.00 - 100.00$).
- **Dynamic Weight Renormalization Rule (First-Time & Early-Years Applicants)**:
  First-time applicants (e.g., entering Kindergarten or Pre-K) lack prior academic transcripts, meaning `prior_gpa` is null. Setting $S_{gpa} = 0$ while keeping static weights would artificially cap applicants at 80 points, unfairly penalizing them. The platform dynamically renormalizes surviving weights over the present criteria:
  $$S_{adm} = \frac{\sum_{k \in K} w_k S_k}{\sum_{k \in K} w_k} \qquad K = \{\,k : S_k \text{ is present}\,\}$$
  When $S_{gpa}$ is absent, the surviving sum $\sum w_k = 0.80$, scaling surviving weights to: exam 43.75%, interview 37.50%, and profile fit 18.75%.
- **Minimum Criteria Invariant**: At least two evaluation components must be present to compute $S_{adm}$. If fewer than two components are available, $S_{adm}$ evaluates to `NULL` and the application is routed to an administrative queue for manual review.
- **Interview Rubric Rescaling Formulation**:
  Evaluators score academic readiness ($r_{acad}$) and communication ($r_{comm}$) on an integer scale from 1 to 5. Because 1 represents the baseline floor rather than zero competence, scores are rescaled:
  $$S_{interview} = \frac{\left(\frac{r_{acad} + r_{comm}}{2}\right) - 1}{4} \times 100$$
- **Operational Invariants**:
  - Name strings must contain 2–255 characters (letters, spaces, hyphens).
  - Offer expiration dates must be strictly greater than offer issue dates.
  - Uploaded documentation files must not exceed 5 MB per artifact.

#### Cross-Module Interactions & Data Flow
- **Fee Management (M08)**: Application submission generates an application fee invoice; acceptance offer issues an enrollment deposit invoice. Deposit settlement triggers matriculation.
- **Exams (M04)**: Generates entrance examination test schedules and receives exam percentile scores ($S_{exam}$).
- **Psychological Assessment (M14)**: Developmental screening flags or applicant IEP histories route candidates to the psychologist for confidential evaluation.
- **User & Role Management (M18)**: Matriculation provisions active student and parent credentials.
- **Communication Hub (M13)**: Dispatches interview scheduling invitations, offer letters, and deadline reminders via email and SMS.

---

### M02: Live Virtual Classrooms

#### Business Purpose & Scope
The Live Virtual Classrooms module orchestrates real-time digital instruction, interactive video lectures, attendance correlation, automated engagement tracking, in-session comprehension polling, server-side moderated chat, and class recording archival.

#### Actor Roles & Trigger Events
- **Teacher**: Schedules virtual classes; launches live video streams; shares screen/whiteboard; administers comprehension polls; moderates interactive chat; ends session.
- **Student**: Joins live lectures; responds to comprehension polls; posts questions in moderated chat; views archived session recordings.
- **School Administrator**: Audits virtual instruction delivery; inspects attendance and engagement metrics; reviews quarantined chat violations.
- **School Psychologist**: Reviews student social engagement scores and classroom withdrawal indicators.
- **Trigger Events**: Class scheduled on master timetable; teacher starts session; student joins or leaves room; poll launched; message flagged by filter; class concluded.

#### Core Functional Capabilities & User Stories
- **Schedule Conflict Detection**: Verifies proposed virtual class timeframes against master teacher and cohort schedules (M07) to prevent double-booking.
- **Automated Connection Telemetry & Attendance Logging**: Tracks student active connection duration via heartbeat telemetry, calculating exact active attendance minutes ($T_{active} = \sum [t_{leave} - t_{join}]$).
- **Multi-Dimensional Engagement Scoring**: Analyzes student participation duration, responsiveness to in-class comprehension polls, and constructive chat participation to compute an engagement index ($E_{class}$).
- **In-Class Comprehension Polling**: Enables teachers to launch instant multiple-choice polls. Restricts students to exactly one vote per poll and renders real-time aggregated response distributions.
- **Server-Side Moderated Chat & Toxicity Quarantining**: Real-time chat messages pass through an automated profanity and harassment filter. Toxic messages are quarantined from student view and surfaced exclusively to the teacher for moderation.
- **Automated Recording Lifecycle**: Captures live video feeds, processes them into adaptive streaming archives, and restricts access strictly to enrolled course section members.

#### End-to-End Business Workflows & State Machine Lifecycles
```
[SCHEDULED] ---> [LIVE] ---> [ENDED] ---> [ARCHIVED]
      |
      v
 [CANCELLED]

Poll Lifecycle:   [DRAFT] ---> [ACTIVE] ---> [CLOSED]
```
- `SCHEDULED`: Class established on section calendar with assigned video room.
- `LIVE`: Host teacher opens room; student connections accepted; telemetry active.
- `ENDED`: Teacher terminates session; participants disconnected; attendance and engagement metrics aggregated.
- `ARCHIVED`: Session recording processed and published to section library for revision.
- `CANCELLED`: Session called off prior to launch; notification dispatched to cohort.

#### Domain Validation Rules, Invariants & Mathematical Formulations
- **Engagement Index Formulation**:
  $$E_{class} = 0.60 \left(\frac{T_{active}}{T_{total}}\right) + 0.25 \left(\frac{N_{polls}}{N_{total\_polls}}\right) + 0.15 \left(\frac{N_{chat}}{10}\right)$$
  - $T_{active} / T_{total}$: Proportion of scheduled class duration the student was actively connected.
  - $N_{polls} / N_{total\_polls}$: Fraction of launched comprehension polls answered by the student (defaults to 1.0 if $N_{total\_polls} = 0$).
  - $N_{chat} / 10$: Ratio of approved chat contributions, capped at a maximum of 10 to prevent chat spamming incentives.
  - $E_{class}$ is clamped strictly within the range $[0.00, 1.00]$.
- **Abrupt Disconnection Handling**: If a student disconnects unexpectedly (browser close, network drop $> 30$ seconds), the heartbeat monitor marks disconnection, credits attendance up to the last verified heartbeat, and preserves session integrity.
- **Operational Invariants**:
  - Class session duration must be between 5 and 240 minutes.
  - Scheduled end time must be strictly greater than start time.
  - In-class chat message length is restricted to 1–2,000 characters.

#### Cross-Module Interactions & Data Flow
- **Timetable & Scheduling (M07)**: Ingests scheduled class periods and validates room/teacher availability.
- **Attendance Tracking (M06)**: Feeds verified active connection minutes to determine period presence (present, late, absent).
- **Digital Library (M12)**: Stores and streams post-class lecture recordings.
- **Psychological Assessment (M14)**: Alerts counselors when a student exhibits a sustained drop in engagement scores or persistent classroom withdrawal.

---

### M03: Assignments & Rubric-Based Grading

#### Business Purpose & Scope
The Assignments module manages coursework authoring, multi-criteria weighted rubric configuration, chunked file submission intake, automated late-penalty decay calculations, plagiarism scanning integration, and teacher grading workflows.

#### Actor Roles & Trigger Events
- **Teacher**: Authors assignment requirements; defines multi-criteria grading rubrics; publishes coursework to student cohorts; evaluates submissions; provides feedback.
- **Student**: Inspects assignment briefs and rubrics; uploads coursework submissions via chunked transfer; reviews grades and rubric feedback.
- **Parent**: Monitors upcoming homework deadlines, submission status, and received grades.
- **School Administrator**: Audits grading turnaround timelines; reviews academic integrity and plagiarism escalations.
- **School Psychologist**: Monitors chronic submission delays and procrastination telemetry as indicators of academic distress.
- **Trigger Events**: Assignment published; submission deadline reached; student submits work; plagiarism scan completed; teacher records rubric evaluation.

#### Core Functional Capabilities & User Stories
- **Multi-Criteria Weighted Rubric Authoring**: Enables teachers to define structured grading rubrics comprising named criteria (e.g., Thesis, Methodology, Analysis, Mechanics). Each criterion specifies performance levels, point scales, and percentage weights.
- **Resumable Chunked Submission Intake**: Supports multi-part file uploads with chunk-level verification, enabling students on unstable network connections to resume interrupted uploads seamlessly.
- **Mathematical Late-Penalty Decay Engine**: Automatically assesses late-submission point deductions based on calendar days elapsed past the due date.
- **Academic Integrity & Plagiarism Scanning**: Analyzes submitted text against institutional corpora and external academic databases, generating similarity percentage reports. Submissions exhibiting similarity $\ge 30\%$ are routed to an administrative integrity queue.
- **Blind & Anonymous Evaluation Mode**: Supports anonymized grading views where student identities are masked to eliminate unconscious evaluator bias during scoring.

#### End-to-End Business Workflows & State Machine Lifecycles
```
[DRAFT] ---> [PUBLISHED] ---> [OPEN] ---> [CLOSED] ---> [GRADED]
   |               |
   +-------+-------+
           |
           v
      [CANCELLED]
```
- `DRAFT`: Teacher configuring assignment instructions, attachments, and rubrics.
- `PUBLISHED`: Assignment scheduled with future open date and visible on student calendars.
- `OPEN`: Assignment active; student submissions accepted.
- `CLOSED`: Due date passed; late submissions accepted only under late penalty rules.
- `GRADED`: All enrolled submissions scored; marks published to Gradebook (M05).

#### Domain Validation Rules, Invariants & Mathematical Formulations
- **Rubric Weight Invariant**:
  $$\sum_{i=1}^{n} w_i = 100.00\%$$
  The sum of all criterion percentage weights must equal exactly 100.00%. Rubric authoring with weights summing to any other value (e.g., 99.50% or 100.50%) is rejected with validation code `M03_RUBRIC_WEIGHT_SUM`.
- **Weighted Rubric Grade Formulation**:
  $$\text{Grade}_{raw} = \sum_{i=1}^{n} \left(\frac{\text{score}_i}{\text{max\_points}_i} \times w_i\right) \times \text{Assignment Max Points}$$
- **Mathematical Late-Penalty Decay Formulation**:
  $$P_{final} = P_{earned} \times (1 - 0.05 \times \text{days\_late}) \quad \text{for } \text{days\_late} \le 5, \quad \text{otherwise } 0$$
  - Submissions receive a 5% point deduction per 24-hour period past the deadline up to 5 days.
  - Submissions received greater than 5 days (120 hours) late earn exactly zero credit ($P_{final} = 0.00$), while preserving the submission file for instructional review.
- **Operational Invariants**:
  - Due date must be in the future at the time of assignment publishing.
  - Maximum assignable points must be between 0.01 and 1,000.00.
  - Submission file attachments are restricted to a maximum of 100 MB per file.

#### Cross-Module Interactions & Data Flow
- **Timetable & Scheduling (M07)**: Binds assignments to active course sections and academic term dates.
- **Gradebook (M05)**: Automatically seeds assignment components and exports finalized weighted scores.
- **Digital Library (M12)**: Enables teachers to link registered digital library assets and educational software tools into assignment briefs.
- **Cognia Accreditation Evidence (M16)**: Archives exemplary, average, and struggling student work samples as accredited continuous improvement evidence.
- **Communication Hub (M13)**: Emits push and SMS alerts for upcoming deadlines and graded assignment publication.

---

### M04: Examinations & Online Proctoring

#### Business Purpose & Scope
The Examinations module governs formal summative testing, item psychometrics, automated test paper compilation via Item Response Theory (IRT), secure computer-based test delivery, automated proctoring anomaly triage, cryptographic submission nonce verification, and administrative grade voiding.

#### Actor Roles & Trigger Events
- **Teacher**: Contributes calibrated questions to institutional item banks; configures exam parameters; reviews proctoring anomaly recordings; grades open-response items.
- **Student**: Launches secure timed examination sessions; undergoes camera and browser proctoring verification; submits responses.
- **School Administrator**: Approves examination timetables; establishes pass/fail criteria; arbitrates academic integrity challenges; executes formal grade voiding.
- **School Psychologist**: Authorizes official test accommodations (e.g., 1.5x time multipliers or distraction-free environments) for students with documented IEPs.
- **Trigger Events**: Exam start window arrives; student opens testing client; proctoring telemetry flags anomaly; exam time expires; student submits answers; admin voids paper.

#### Core Functional Capabilities & User Stories
- **Psychometric IRT 2PL Test Paper Generation**: Assembles balanced examination papers from question banks by calibrating question difficulty ($b_j$) and discrimination ($a_j$) against target cohort ability ($\theta_i$) using the 2-Parameter Logistic IRT model. Papers use deterministic audit seeds to ensure reproducible test forms.
- **Automated Multi-Modal Proctoring Triage**: Continuously monitors testing sessions for integrity anomalies: loss of facial detection, multiple faces present, browser tab/window switching, unauthorized copy-paste actions, and external speech audio.
- **Automatic Proctoring Blockage Threshold**: When cumulative anomaly confidence reaches or exceeds 0.85, the exam session is locked automatically, preventing submission pending manual inspection and clearance by a School Administrator.
- **Cryptographic Replay-Protected Submission Nonce**: Every exam session generates a unique, single-use cryptographic submission nonce consumed atomically upon final submission. Re-submission attempts using an identical nonce are rejected with `M04_NONCE_REPLAY`.
- **Administrative Grade Voiding Protocol**: In cases of substantiated cheating or examination disruption, administrators execute a formal voiding workflow that nullifies marks, records mandatory administrative justifications, and archives pre-void grade snapshots in the audit ledger.

#### End-to-End Business Workflows & State Machine Lifecycles
```
[DRAFT] ---> [SCHEDULED] ---> [ACTIVE] ---> [CLOSED] ---> [FINALIZED]
                   |                           |
                   v                           v
              [CANCELLED]                   [VOIDED]
```
- `DRAFT`: Authoring questions, psychometric metadata, and test structure.
- `SCHEDULED`: Exam window established on master calendar; student rosters assigned.
- `ACTIVE`: Testing window open; students sitting for proctored exam.
- `CLOSED`: Testing session ended; automated grading executed; anomaly reviews pending.
- `FINALIZED`: All anomaly flags resolved; marks committed to Gradebook (M05).
- `VOIDED`: Administrative cancellation nullifying exam results with mandatory audit log.

#### Domain Validation Rules, Invariants & Mathematical Formulations
- **Item Response Theory (IRT) 2-Parameter Logistic (2PL) Formulation**:
  $$P(X_{ij} = 1 | \theta_i) = \frac{1}{1 + e^{-a_j (\theta_i - b_j)}}$$
  - $P(X_{ij} = 1 | \theta_i)$: Probability of candidate $i$ with latent trait ability $\theta_i$ answering question $j$ correctly.
  - $a_j$: Discrimination parameter of item $j$ ($a_j > 0$).
  - $b_j$: Difficulty parameter of item $j$ ($-\infty < b_j < \infty$).
- **IEP Accommodation Timing Formulation**:
  $$T_{allotted} = T_{standard} \times M_{iep}$$
  - Accommodations multipliers ($M_{iep} \in \{1.25, 1.50, 2.00\}$) are verified server-side. Client devices cannot manipulate exam timers.
- **Operational Invariants**:
  - Total exam marks must be positive (between 1.00 and 1,000.00); passing mark must be $\le$ total marks.
  - Question types restricted to: Multiple Choice (MCQ), Multi-Select, Short Answer, Essay, and True/False.
  - Final submission timestamp must occur within scheduled exam boundaries.

#### Cross-Module Interactions & Data Flow
- **Timetable & Scheduling (M07)**: Reserves examination periods and resolves cohort scheduling conflicts.
- **Gradebook (M05)**: Receives finalized summative examination marks for report card compilation.
- **Psychological Assessment (M14)**: Consumes clinical testing accommodation authorizations (IEP timing extensions).
- **Cognia Accreditation Evidence (M16)**: Exports assessment validity studies, item psychometric distributions, and proctoring audit logs.

---

### M05: Gradebook, Transcripts & Academic Standing

#### Business Purpose & Scope
The Gradebook module aggregates academic evaluations across coursework, live classrooms, and summative examinations; computes weighted and unweighted Grade Point Averages (GPA); enforces course rigor bonuses; detects cognitive decline patterns; and issues digitally signed report cards and official transcripts.

#### Actor Roles & Trigger Events
- **Teacher**: Enters and verifies section assignment and exam marks; compiles term averages; authors student narrative comments.
- **School Administrator (Principal / Registrar)**: Configures institutional grade scales; reviews cognitive drop alerts; applies digital signatures to report cards; authorizes historical transcript corrections.
- **Student / Parent**: Inspects published term report cards, cumulative GPAs, and longitudinal transcripts.
- **School Psychologist**: Reviews students flagged for severe academic performance decline (cognitive drops) to assess stress, burnout, or learning barriers.
- **Trigger Events**: Term grading window closes; teacher submits section marks; GPA computation executes; cognitive drop threshold breached; Principal applies digital signature; report cards published.

#### Core Functional Capabilities & User Stories
- **Multi-Tier Grade Scale Translation**: Maps raw numerical percentages into institutional letter grades ($A+, A, B, \dots, F$) and GPA point values ($0.00 - 4.00$).
- **Weighted & Unweighted GPA Calculation**: Computes cumulative term and career GPAs, factoring course credit hours and academic course rigor bonuses for Honors and Advanced Placement (AP) / International Baccalaureate (IB) coursework.
- **The 4.500 Weighted GPA Policy Ceiling**: Restricts weighted GPA calculations to a hard ceiling of 4.500. Transcripts visibly record `GPA_CAPPED` whenever a student's raw weighted score reaches or exceeds this bound.
- **Failing Grade Rigor Bonus Withholding**: Enforces academic integrity: rigor bonuses are strictly withheld if a student fails a course ($g_i = 0.00$), preventing inflation of failing marks.
- **Automated Cognitive Drop Detection Engine**: Continuously evaluates student performance against rolling historical averages. A term percentage drop $\ge 15\%$ triggers an automated academic review flag and halts report card distribution pending review by the School Psychologist.
- **Principal Digital Signature Requirement**: Official report cards cannot be released to parents or students without formal verification and an authenticated digital signature from the School Principal.

#### End-to-End Business Workflows & State Machine Lifecycles
```
[ENTERED] ---> [VERIFIED] ---> [POSTED] ---> [PUBLISHED]
                    ^              |
                    |              v
                    +------- [REVISED]
```
- `ENTERED`: Teacher enters component marks and formative comments.
- `VERIFIED`: Department head or registrar verifies grade distributions and completeness.
- `POSTED`: Final term marks locked; GPA calculations executed; cognitive drop scan runs.
- `PUBLISHED`: Principal signs report cards; releases views to students and parents.
- `REVISED`: Formal post-publication grade appeal approved; marks updated and re-verified.

#### Domain Validation Rules, Invariants & Mathematical Formulations
- **Unweighted and Weighted GPA Formulations**:
  $$GPA_u = \frac{\sum_{i=1}^{n} g_i \times c_i}{\sum_{i=1}^{n} c_i} \qquad GPA_w = \min\left(4.500, \frac{\sum_{i=1}^{n} (g_i + b_i) \times c_i}{\sum_{i=1}^{n} c_i}\right)$$
  - $g_i$: Grade point value associated with the course final letter grade ($0.00 \le g_i \le 4.00$).
  - $b_i$: Course rigor bonus ($b_{standard} = 0.00, b_{honors} = 0.50, b_{ap/ib} = 1.00$).
  - $c_i$: Course credit hours ($c_i > 0$).
  - If $g_i = 0.00$ (Grade `F`), then $b_i = 0.00$ (rigor bonus withheld).
  - If $\sum c_i = 0$ (no graded credits), GPA is recorded as `NULL`, never 0.000.
- **Rounding Protocol**: Quotients are rounded half-up to exactly 3 decimal places once, at the conclusion of computation, preventing intermediate rounding distortions.
- **Cognitive Drop Detection Formulation**:
  $$\Delta_{drop} = \overline{P}_{rolling\_3\_term} - P_{current\_term}$$
  - When $\Delta_{drop} \ge 15.00\%$, the system flags `COGNITIVE_DROP_ALERT`, suspends public release, and routes the profile to the School Psychologist.

#### Cross-Module Interactions & Data Flow
- **Assignments (M03) & Exams (M04)**: Ingests component coursework and examination marks.
- **Psychological Assessment (M14)**: Routes cognitive drop alerts to counselors for intervention.
- **Communication Hub (M13)**: Sends push and email notifications to parents upon report card publishing.
- **Cognia Accreditation Evidence (M16)**: Exports multi-year longitudinal grade distribution and transcript analytics.

---

### M06: Attendance Tracking & Truancy Management

#### Business Purpose & Scope
The Attendance module oversees daily period-by-period classroom presence, biometric physical check-in integrations, anti-replay verification, late arrival penalties, parental absence excuse workflows, and automated truancy escalation.

#### Actor Roles & Trigger Events
- **Teacher**: Marks period-level attendance rosters as present, late, absent, or excused.
- **Attendance Officer (Staff)**: Audits biometric gate logs; verifies medical certificates; processes parent absence requests.
- **Parent**: Submits digital absence excuse requests with supporting medical documentation.
- **Student**: Checks in via physical biometric gate scanners or mobile attendance portals.
- **School Administrator**: Audits school-wide attendance compliance; initiates truancy interventions.
- **School Psychologist**: Intervenes in chronic absenteeism cases to address school refusal or home distress.
- **Trigger Events**: Class period commences; biometric scanner transmits check-in; parent submits doctor note; unexcused absence threshold breached.

#### Core Functional Capabilities & User Stories
- **Period-Level Roster Marking**: Teachers mark student presence across standard operational statuses: `present`, `late`, `absent`, or `excused`. Submissions are committed atomically across the section roster.
- **Cumulative Attendance Percentage Formulation**: Calculates institutional attendance where late arrivals receive half credit, reflecting partial academic participation.
- **Biometric Anti-Replay Nonce Verification**: Biometric gate scanners transmit check-in events utilizing unique, single-use cryptographic nonces. Duplicate nonces are rejected (`M06_NONCE_REPLAY`), preventing badge-sharing or packet replay.
- **Parent Absence Excuse & Medical Documentation Workflow**: Parents submit digital absence excuse requests specifying dates, mandatory reasons, and optional doctor certificates. Staff approval converts unexcused absences into excused records.
- **Automated Truancy Escalation Engine**: Continuously tracks cumulative and consecutive unexcused absences. When institutional thresholds are breached, the system dispatches truancy warnings to parents and routes student profiles to the School Psychologist.

#### End-to-End Business Workflows & State Machine Lifecycles
```
Session:   [OPEN] ---> [MARKED] ---> [LOCKED]

Excuse:    [SUBMITTED] ---> [REVIEWED] ---> [APPROVED] ---> [EXCUSED]
                                 |
                                 v
                            [REJECTED]
```
- `OPEN`: Period active; attendance roster awaiting submission.
- `MARKED`: Teacher has recorded presence; editable until end of instructional day.
- `LOCKED`: Roster locked against manual edits; modifications require administrator override.
- `SUBMITTED`: Parent filed digital absence excuse with optional doctor note.
- `APPROVED`: Staff validated documentation; status converted to `EXCUSED`.
- `REJECTED`: Excuse rejected; absence remains unexcused and counts toward truancy.

#### Domain Validation Rules, Invariants & Mathematical Formulations
- **Cumulative Attendance Percentage Formulation**:
  $$A_{\%} = \left(\frac{N_{present} + 0.5 \times N_{late}}{N_{total\_sessions}}\right) \times 100\%$$
  - $A_{\%}$ is clamped strictly between $0.00\%$ and $100.00\%$.
- **Retrospective Excuse Submission Limit**: Digital absence excuse requests submitted more than 30 calendar days past the absence date are rejected with validation code `VAL_EXCUSE_EXPIRED`. Retrospective approvals past 30 days require formal authorization from the School Principal.
- **Operational Invariants**:
  - Attendance session date cannot be set in the future.
  - Period numbers must be integers between 1 and 8.
  - Combination of section, academic date, and period number must be unique per institution.

#### Cross-Module Interactions & Data Flow
- **Timetable & Scheduling (M07)**: Ingests master section rosters and scheduled instructional periods.
- **Live Virtual Classrooms (M02)**: Receives active connection telemetry to reconcile virtual attendance.
- **Transport Logistics (M15)**: Correlates morning bus boarding logs with classroom period-1 attendance.
- **Psychological Assessment (M14)**: Routes chronic absenteeism alerts to counselors for intervention.
- **Communication Hub (M13)**: Dispatches instant SMS and push absence alerts to parents.

---

### M07: Master Timetable & Substitute Scheduling

#### Business Purpose & Scope
The Timetable module operates constraint-driven master schedule generation, conflict-free room and instructor allocations, cognitive workload balancing, emergency teacher substitution rosters, and versioned immutable schedule publishing.

#### Actor Roles & Trigger Events
- **School Administrator (Principal / Academic Scheduler)**: Defines institutional scheduling rules, initiates timetable generation runs, resolves scheduling conflicts, and publishes master timetables.
- **Teacher**: Inspects personal teaching schedules; submits planned leave requests; accepts emergency substitute assignments.
- **Student / Parent**: Inspects personalized weekly cohort class schedules.
- **Staff (Facilities Coordinator)**: Manages classroom physical capacity and specialized laboratory allocations.
- **School Psychologist**: Recommends cognitive pacing adjustments for neurodivergent or struggling cohorts.
- **Trigger Events**: Academic term setup; scheduling solver run initiated; teacher leave approved; emergency substitution confirmed; schedule version published.

#### Core Functional Capabilities & User Stories
- **Constraint-Driven Master Timetable Optimization**: Resolves multi-variable scheduling constraints across teachers, student cohorts, rooms, and time periods, minimizing a penalty cost function ($N_{hard\_conflicts}$, $N_{teacher\_gaps}$, $N_{room\_moves}$).
- **Cognitive Workload Balancing Policy**: Automatically schedules cognitively intensive subjects (e.g., Mathematics, Physics, Chemistry) into peak morning periods (Periods 1–3), avoiding consecutive double-block intensive subjects without intervening physical activity or nutrition breaks.
- **Emergency Teacher Substitution Engine**: When a teacher's leave request is approved (M10 HR), the system automatically queries the qualified staff registry to identify available substitutes without schedule conflicts, dispatching substitution assignments dynamically.
- **Versioned & Immutable Schedule Publishing**: Timetables are published as immutable versions. Once published, operational adjustments require either a formal substitute assignment or a superseding published version.
- **Physical Room Capacity Validation**: Validates that assigned classrooms satisfy the physical capacity requirements of the enrolled student section ($C_{room} \ge N_{enrolled}$).

#### End-to-End Business Workflows & State Machine Lifecycles
```
Timetable:     [DRAFT] ---> [GENERATED] ---> [PUBLISHED] ---> [SUPERSEDED]

Substitution:  [PROPOSED] ---> [CONFIRMED] ---> [ACTIVE] ---> [RESOLVED]
                                     |
                                     v
                                [CANCELLED]
```
- `DRAFT`: Academic parameters, period blocks, and curriculum hours being configured.
- `GENERATED`: Solver has generated a conflict-free schedule awaiting administrative review.
- `PUBLISHED`: Schedule active; visible to teachers, students, and parents; strictly immutable.
- `SUPERSEDED`: Replaced by a newer published timetable version.
- `PROPOSED`: Substitute candidate matched against absent teacher's schedule.
- `CONFIRMED`: Substitute teacher confirms availability; notification sent to section.

#### Domain Validation Rules, Invariants & Mathematical Formulations
- **Optimization Penalty Cost Function**:
  $$\text{Penalty} = 1,000 \times N_{hard\_conflicts} + 10 \times N_{teacher\_gaps} + 5 \times N_{room\_moves}$$
  - $N_{hard\_conflicts}$: Number of teacher or room double-bookings (must equal 0 for valid generation).
  - $N_{teacher\_gaps}$: Unassigned idle periods between teaching blocks in an instructor's day.
  - $N_{room\_moves}$: Instances where a student cohort changes rooms between consecutive non-lab periods.
- **Operational Invariants**:
  - Exactly one active master timetable permitted per academic term.
  - Instructional days restricted to standard academic week (Monday through Friday).
  - Substitute teacher must possess valid subject accreditation and cannot be the absent teacher.

#### Cross-Module Interactions & Data Flow
- **HR & Staff Management (M10)**: Consumes approved staff leave events to trigger substitute workflows.
- **Attendance Tracking (M06) & Live Classes (M02)**: Feeds daily period structures, teacher assignments, and room allocations.
- **Exams (M04)**: Allocates conflict-free examination blocks within term calendar windows.
- **Communication Hub (M13)**: Dispatches real-time timetable alteration and substitute alerts.

---

### M08: Fee Management, Invoicing & Stripe Payments

#### Business Purpose & Scope
The Fee Management module governs institutional tuition fee structures, cohort batch invoicing, online payment settlement via Stripe, compound late fee accruals, structured installment financing agreements, and financial distress triage.

#### Actor Roles & Trigger Events
- **Bursar / Accountant (Staff)**: Configures fee schedules; generates batch term invoices; manages discount policies; authorizes refunds and debt write-offs.
- **Parent / Student**: Inspects tuition invoices; selects installment financing plans; makes credit card or bank payments via hosted checkout; downloads tax receipts.
- **School Administrator**: Approves institutional fee structures, write-off thresholds, and payment policies.
- **School Psychologist**: Intervenes in cases of acute family financial distress impacting student emotional wellbeing.
- **Trigger Events**: Academic term billing cycle commences; student matriculates; payment webhook confirms settlement; invoice overdue milestone reached; installment missed.

#### Core Functional Capabilities & User Stories
- **Automated Batch Invoicing**: Generates term invoices encompassing tuition, laboratory fees, transportation, meal plans, and extracurricular fees across enrolled cohorts.
- **Stripe Hosted Checkout & Idempotent Webhook Settlement**: Processes digital payments via hosted checkout sessions. Enforces webhook cryptographic signature validation and payment deduplication to ensure exact, idempotent balance settlement.
- **Bounded Compound Late-Payment Interest Engine**: Accrues compound interest on overdue balances while enforcing strict consumer protection caps to prevent debt spiraling.
- **Structured Installment Financing Plans**: Enables institutions to break down annual tuition invoices into $N$ customized monthly or quarterly installment milestones, tracking payments per milestone.
- **Family Financial Distress Triage Referral**: Automatically routes accounts overdue for $\ge 30$ days or exhibiting $\ge 2$ missed installments to the School Psychologist and Family Support team to explore financial aid and counseling.

#### End-to-End Business Workflows & State Machine Lifecycles
```
[DRAFT] ---> [ISSUED] ---> [DUE] ---> [PARTIALLY_PAID] ---> [PAID]
                           |
                           v
                       [OVERDUE] ---> [WRITTEN_OFF]
```
- `DRAFT`: Invoice items, discounts, and fee categories being compiled.
- `ISSUED`: Invoice finalized and published to parent portal; payment window open.
- `DUE`: Invoice payable without penalty up to the published due date.
- `PARTIALLY_PAID`: Partial settlement recorded; balance remains outstanding.
- `PAID`: Full invoice balance settled; receipt issued; ledger notified.
- `OVERDUE`: Payment past due date; flat fee assessed; compound interest accrual active.
- `WRITTEN_OFF`: Debt declared uncollectible by administrator; balance zeroed; audit logged.

#### Domain Validation Rules, Invariants & Mathematical Formulations
- **Compound Late Fee Formulation**:
  $$F_{late} = P_{balance} \times \left(1 + \frac{r}{12}\right)^{m} - P_{balance} + F_{flat}$$
  - $P_{balance}$: Outstanding balance at evaluation ($\text{Total Amount} - \text{Discounts} - \sum \text{Paid}$).
  - $r$: Annual nominal interest rate (tenant configuration, default $0.05$).
  - $m$: Number of completed 30-day periods past due date: $m = \lfloor (d_{now} - d_{due}) / 30 \rfloor$, capped at 12.
  - $F_{flat}$: Flat administrative late fee (default $\$25.00$), assessed once per overdue invoice.
- **Consumer Protection Balance Ceiling**:
  $$F_{late} \le \min\left(0.25 \times P_{balance}, F_{max}\right)$$
  - Late fees are capped at a maximum of 25% of the outstanding balance and at the institutional absolute ceiling $F_{max}$.
  - When $m = 0$ (invoice 1–29 days late), interest is $\$0.00$ and only $F_{flat}$ is assessed.
  - Invoices overdue beyond one year ($m = 12$) cease compounding and require administrative write-off evaluation.
- **Operational Invariants**:
  - Total invoice amount must be greater than zero; discounts cannot exceed total fees.
  - Deletion of issued invoices is strictly prohibited; adjustments require credit notes or formal write-offs.
  - Payment transactions require unique 24-hour idempotency keys.

#### Cross-Module Interactions & Data Flow
- **Admissions (M01)**: Receives accepted applicants to generate initial enrollment deposit invoices.
- **Financial Management (M09)**: Exports settled fee collections as balanced double-entry journal vouchers.
- **Psychological Assessment (M14)**: Alerts counselors to families experiencing acute financial distress.
- **Communication Hub (M13)**: Sends automated invoice delivery notifications and payment receipts.

---

### M09: Financial Management & General Ledger

#### Business Purpose & Scope
The Financial Management module operates the institutional general ledger, double-entry journal vouchers, chart of accounts, departmental budget tracking, mental health funding allocations, and fiscal period closing governance.

#### Actor Roles & Trigger Events
- **CFO / Bursar (School Administrator)**: Oversees chart of accounts; approves budget allocations; monitors departmental variances; authorizes fiscal period closings.
- **Finance Officer (Staff)**: Enters journal entries; reconciles bank accounts; generates trial balances.
- **Super Administrator**: Conducts cross-tenant financial compliance audits; authorizes emergency fiscal period reopenings.
- **School Psychologist**: Directs allocated student mental health program funds.
- **Trigger Events**: Fee collection settled; payroll disbursed; journal voucher submitted; department budget threshold reached; monthly or annual fiscal period closed.

#### Core Functional Capabilities & User Stories
- **Double-Entry Bookkeeping Invariant Enforcement**: Enforces that every journal voucher satisfies the fundamental accounting balance equation ($\sum \text{Debits} - \sum \text{Credits} = 0.00$). Unbalanced entries are rejected prior to persistence.
- **Immutable Ledger & Reversing Entries**: Posted journal vouchers are strictly immutable. Deletion or direct alteration is prohibited; accounting corrections must be executed via formal reversing entries referencing the original transaction.
- **Hierarchical Chart of Accounts**: Organizes accounts across five statutory classes: Assets, Liabilities, Equity, Revenues, and Expenses.
- **Departmental Budget Variance & Threshold Alerts**: Tracks expenditures against approved departmental budgets, generating automated alerts at 75% and 90% utilization, and enforcing a hard block on unbudgeted commitments at 100%.
- **Automated Mental Health Program Budget Earmarking**: When an academic department reaches 75% budget expenditure, the system automatically earmarks a 5% mental health sub-budget allocation to support student wellbeing initiatives co-supervised by the School Psychologist.
- **Fiscal Period Closing Governance**: Governs monthly and annual accounting period closings, locking all underlying ledger rows and generating final trial balances and balance sheets.

#### End-to-End Business Workflows & State Machine Lifecycles
```
Journal Voucher:  [DRAFT] ---> [POSTED] ---> [REVERSED]

Fiscal Period:    [OPEN] ---> [CLOSING] ---> [CLOSED]
```
- `DRAFT`: Voucher lines entered; debits and credits being balanced.
- `POSTED`: Balanced voucher committed to ledger; accounts updated; strictly immutable.
- `REVERSED`: Correcting entry posted; original entry flagged as reversed with audit link.
- `OPEN`: Period active; daily journal transactions accepted.
- `CLOSING`: Period under reconciliation; new general transactions blocked.
- `CLOSED`: Period finalized; balance sheets generated; reopening barred without Super Admin sign-off.

#### Domain Validation Rules, Invariants & Mathematical Formulations
- **Fundamental Accounting Invariant**:
  $$\sum_{k=1}^{n} \text{Debit}_k - \sum_{k=1}^{n} \text{Credit}_k = 0.00$$
  - Every transaction must balance to the cent. An entry with debits of $\$10,000.00$ and credits of $\$9,999.99$ is rejected with validation code `M09_DEBIT_CREDIT_INVARIANT`, returning the exact discrepancy ($0.01$) in error telemetry.
- **Budget Threshold Alerts**:
  - Alert 1 (Informational): $\text{Spend} \ge 0.75 \times \text{Budget}$.
  - Alert 2 (Warning): $\text{Spend} \ge 0.90 \times \text{Budget}$.
  - Alert 3 (Hard Stop): $\text{Spend} \ge 1.00 \times \text{Budget}$ (subsequent purchase commitments blocked).
- **Operational Invariants**:
  - Transaction date must lie within an active, open fiscal period.
  - Debit and credit values must be non-negative; exactly one side must be positive per journal line.
  - Closed fiscal periods cannot be reopened without multi-signature authorization from the Super Admin.

#### Cross-Module Interactions & Data Flow
- **Fee Management (M08)**: Consumes student tuition fee collections for revenue account crediting.
- **Payroll (M11)**: Ingests monthly staff salary disbursement figures for expense account debiting.
- **Psychological Assessment (M14)**: Allocates and monitors designated mental health support budgets.
- **Cognia Accreditation Evidence (M16)**: Exports verified financial stability audits and operational ledgers.

---

### M10: Human Resources & Staff Management

#### Business Purpose & Scope
The HR module manages the institutional staff lifecycle, employee personnel files, employment contracts, monthly leave accruals, multi-step leave approvals, performance appraisals, and educator burnout monitoring.

#### Actor Roles & Trigger Events
- **HR Director / Principal (School Administrator)**: Approves employment contracts; authorizes staff leave; conducts annual performance appraisals; manages department assignments.
- **Teacher / Staff Employee**: Maintains professional profile; submits leave requests; views leave balances; participates in annual self-appraisals.
- **School Psychologist**: Conducts confidential wellness check-ins for staff flagged with acute burnout markers.
- **Trigger Events**: Employee onboarded; contract renewal milestone reached; leave request submitted; leave approved; annual appraisal cycle launched; burnout workload threshold breached.

#### Core Functional Capabilities & User Stories
- **Comprehensive Employee Lifecycle Management**: Tracks employee demographic data, statutory tax identifiers, educational credentials, emergency contacts, and institutional department assignments.
- **Contract Lifecycle & Renewal Alerts**: Governs permanent, fixed-term, and probationary contracts, tracking start/end dates, agreed salary terms, and renewal notification timelines.
- **Automated Fractional Leave Accrual Engine**: Accrues annual vacation and sick leave on a monthly basis, validating that requested leave durations do not exceed current accrued balances.
- **Multi-Step Leave Approval Workflow**: Routes employee leave requests through direct supervisors and HR administration. Approved teacher leave events trigger automated substitute scheduling in Timetable (M07).
- **Weighted Staff Performance Appraisals**: Evaluates teaching and operational staff using a multi-criteria rubric: Teaching Effectiveness (40%), Professionalism & Collaboration (30%), and Student Learning Outcomes (30%).
- **Educator Wellness & Burnout Triage**: Monitors workload stress markers (consecutive overtime, substitute teaching frequency, sentiment in institutional communications) to alert the School Psychologist for confidential wellness check-ins.

#### End-to-End Business Workflows & State Machine Lifecycles
```
Leave Request:  [SUBMITTED] ---> [APPROVED] ---> [TAKEN] ---> [CLOSED]
                     |
                     +-------+-------+
                             |
                             v
                    [REJECTED/CANCELLED]
```
- `SUBMITTED`: Employee submitted leave dates and mandatory justification.
- `APPROVED`: Supervisor and HR authorized leave; substitute workflow triggered.
- `TAKEN`: Leave period elapsed; attendance presence records updated.
- `CLOSED`: Leave cycle completed; final balance deducted.
- `REJECTED`: Leave denied due to institutional blackout dates or staffing shortages.

#### Domain Validation Rules, Invariants & Mathematical Formulations
- **Monthly Leave Accrual Formulation**:
  $$L_{accrued} = \text{Months\_Worked} \times \left(\frac{\text{Annual\_Entitlement}}{12}\right)$$
  - Requested leave duration cannot exceed current accrued balance ($L_{requested} \le L_{accrued}$); requests exceeding balance are rejected with `M10_INSUFFICIENT_BALANCE`.
- **Annual Leave Carry-Forward Cap Policy**:
  - Maximum annual leave carry-forward to subsequent fiscal years is capped at exactly 5 days. Unused leave exceeding 5 days is forfeited at year-end with an immutable audit entry.
- **Performance Appraisal Weighted Formulation**:
  $$\text{Score}_{appraisal} = 0.40\,S_{teaching} + 0.30\,S_{conduct} + 0.30\,S_{outcomes}$$
- **Operational Invariants**:
  - Employee codes must be unique per institutional tenant.
  - Hire dates cannot be set in the future.
  - Employment contract end dates must be strictly greater than start dates.

#### Cross-Module Interactions & Data Flow
- **Timetable & Scheduling (M07)**: Approved teacher leaves automatically trigger the emergency substitute teacher allocation workflow.
- **Payroll Processing (M11)**: Exports base contract salary terms, unpaid leave days, and benefit selections.
- **Attendance Tracking (M06)**: Synchronizes approved staff leave with daily staff attendance logs.
- **Psychological Assessment (M14)**: Confidential staff burnout alerts route directly to counselors.

---

### M11: Staff Payroll Processing

#### Business Purpose & Scope
The Payroll module governs monthly employee compensation, progressive income tax withholding, statutory deductions, multi-stage approval workflows, pay slip generation, period locking, and ISO 27018 salary confidentiality.

#### Actor Roles & Trigger Events
- **Principal / Bursar (School Administrator)**: Initiates monthly payroll calculation runs; reviews gross-to-net deductions; authorizes payroll disbursements.
- **Payroll Specialist (Staff)**: Configures tax brackets; manages loan deductions; reconciles banking batches.
- **Super Administrator**: Authorizes emergency payroll overrides and oversees compensation compliance.
- **Teacher / Staff Employee**: Accesses personal encrypted pay slips and tax withholding summaries.
- **Trigger Events**: Monthly payroll cycle opened; calculations executed; approvals completed; banking disbursement batch released; period locked.

#### Core Functional Capabilities & User Stories
- **Comprehensive Gross-to-Net Pay Engine**: Computes monthly compensation across base pay, allowances, progressive income tax withholding, statutory pension contributions, and voluntary deductions.
- **Progressive Income Tax Calculation**: Evaluates annualized gross income against jurisdictional piecewise-linear tax brackets, prorating tax withholding on a monthly basis.
- **Statutory Social Security Contribution Ceilings**: Calculates pension and social security contributions, enforcing statutory monthly contribution caps ($C_s$).
- **Non-Negative Net Pay Guarantee & Deduction Carry-Forward**: Clamps net pay at zero, guaranteeing that employees never receive negative pay slips. Deductions exceeding earnings are carried forward to the subsequent pay cycle (`DEDUCTION_CARRIED`).
- **Four-Stage Approval & Immutable Period Lock**: Payroll progresses through four sequential stages: `DRAFT` $\to$ `APPROVED` $\to$ `LOCKED` $\to$ `PAID`. Once marked locked or paid, recalculations are strictly barred.
- **ISO 27018 Salary Confidentiality & PII Masking**: Salary figures are classified as high-sensitivity PII. Salary data is strictly excluded from general system logs, monitoring pipelines, and API headers. Pay slips are rendered as encrypted documents accessible only to the employee and authorized payroll officers.

#### End-to-End Business Workflows & State Machine Lifecycles
```
[DRAFT] ---> [APPROVED] ---> [LOCKED] ---> [PAID]
```
- `DRAFT`: Payroll run generated; earnings and deductions calculated; variances flagged.
- `APPROVED`: HR and Bursar verify deductions and sign off on disbursement totals.
- `LOCKED`: Payroll locked against recalculations; bank payment files generated.
- `PAID`: Funds disbursed; encrypted pay slips published; ledger journal entries committed.

#### Domain Validation Rules, Invariants & Mathematical Formulations
- **Net Pay Formulation**:
  $$P_{net} = \underbrace{\left(P_{basic} + \sum_{a} A_a\right)}_{P_{gross}} - \left(T + S + \sum_{d} D_d\right)$$
  - $P_{basic}$: Monthly basic salary ($P_{basic} \ge 0$).
  - $A_a$: Monthly allowances (housing, transport, academic leadership).
  - $T$: Progressive income tax withholding.
  - $S$: Statutory employee social security contribution ($S = r_s \times \min(P_{gross}, C_s)$).
  - $D_d$: Deductions (health insurance, loans, unpaid leave).
- **Progressive Income Tax Formulation**:
  $$T_{annual} = \sum_{b} r_b \times \max\left(0, \min(12 P_{gross}, u_b) - l_b\right) \qquad T = \frac{T_{annual}}{12}$$
  - Where band $b$ spans $[l_b, u_b)$ at marginal tax rate $r_b$.
  - Missing tax tables trigger `VAL_TAX_TABLE_MISSING`; runs fail closed rather than defaulting to zero tax.
- **Non-Negative Net Pay Guarantee**:
  $$P_{net} = \max\left(0.00, P_{gross} - (T + S + \sum D_d)\right)$$
  - When total deductions exceed gross pay, $P_{net} = 0.00$, and the unrecovered balance $\Delta_{deduct}$ is carried forward to the next pay cycle with flag `DEDUCTION_CARRIED`.
- **Rounding Protocol**: $T$, $S$, and each deduction line $D_d$ are rounded half-up to 2 decimal places independently prior to subtraction, ensuring printed pay slip line items sum perfectly to the cent.

#### Cross-Module Interactions & Data Flow
- **HR & Staff Management (M10)**: Consumes employee base salary, contract terms, and unpaid leave days.
- **Financial Management (M09)**: Injects total payroll disbursements as balanced journal vouchers into the general ledger.
- **Communication Hub (M13)**: Sends secure notifications to staff informing them of pay slip availability.

---

### M12: Digital Library & Educational Tool Registry

#### Business Purpose & Scope
The Digital Library module oversees physical and digital book cataloging, barcoded inventory, student/staff lending transactions, overdue fine assessments, digital rights management (DRM) for e-book streaming, bibliotherapy curation, and the sandboxed integration of 24 educational software tools.

#### Actor Roles & Trigger Events
- **Librarian (Staff)**: Catalogs physical/digital media; processes checkouts and check-ins; inspects physical condition; manages reserves and fines.
- **Student / Teacher**: Searches catalog; reserves media; checks out physical books; streams digital e-books; launches approved educational tools.
- **School Psychologist**: Curates therapeutic reading lists (bibliotherapy) for students experiencing emotional or behavioral challenges.
- **Trigger Events**: Media cataloged; book checked out or returned; loan period lapses; e-book stream requested; bibliotherapy reading plan assigned; educational tool launched.

#### Core Functional Capabilities & User Stories
- **Multi-Format Catalog Management**: Catalogs physical volumes and digital e-books, validating standard ISBN-10/13 formats, authors, genres, and educational grade-level classifications.
- **Barcoded Copy & Lending Lifecycle**: Tracks physical book copies via unique barcodes. Enforces copy availability states: checkout requires `AVAILABLE` status.
- **Automated Overdue Lending Fines Engine**: Automatically calculates daily overdue fines upon book return, routing assessed penalties to Fee Management (M08) for billing collection.
- **Secure E-Book Streaming Tokens (DRM)**: Issues signed, time-limited streaming tokens (5-minute TTL) for digital literature, revoking access automatically upon loan expiration to enforce digital lending rights.
- **Bibliotherapy & Wellbeing Reading Lists**: Provides a dedicated workflow for the School Psychologist to prescribe tailored reading selections supporting anxiety management, bereavement, and social-emotional growth.
- **Sandboxed Registry of 24 Approved Educational Tools**: Integrates and monitors 24 certified educational software tools (e.g., PhET Interactive Simulations, Scratch, GeoGebra). Tracks student engagement duration and monitors URL link health with automated broken-link detection.

#### End-to-End Business Workflows & State Machine Lifecycles
```
Book Copy:    [AVAILABLE] ---> [CHECKED_OUT] ---> [OVERDUE] ---> [RETURNED] ---> [AVAILABLE]
                                     |
                                     v
                                  [LOST]
```
- `AVAILABLE`: Copy on shelf, available for loan or reservation.
- `CHECKED_OUT`: Loan active; due date established.
- `OVERDUE`: Due date passed; daily fines accruing.
- `RETURNED`: Book inspected and checked in; fines assessed.
- `LOST`: Declared missing; replacement cost invoice generated.

#### Domain Validation Rules, Invariants & Mathematical Formulations
- **Daily Overdue Fine Formulation**:
  $$\text{Fine} = \text{Days\_Overdue} \times \$0.50$$
  - Overdue fines are assessed automatically at check-in and committed to the student's billing account.
- **Operational Invariants**:
  - ISBN values must validate against standard 10 or 13-digit checksum algorithms.
  - Copy barcodes must be unique per institutional tenant.
  - Active reservations expire after 48 hours if uncollected.
  - Streaming e-books without an active, approved loan record is blocked with `VAL_NO_ACTIVE_LOAN`.

#### Cross-Module Interactions & Data Flow
- **Fee Management (M08)**: Routes overdue library fines and lost book replacement costs to student accounts.
- **Assignments (M03)**: Enables teachers to embed registered educational software tools directly into coursework briefs.
- **Psychological Assessment (M14)**: Collaborates with counselors on therapeutic bibliotherapy assignments.
- **Communication Hub (M13)**: Dispatches loan due-date reminders and overdue alerts.

---

### M13: Communication Hub & Omnichannel Messaging

#### Business Purpose & Scope
The Communication Hub unifies institutional communications across role-targeted broadcast bulletins, secure direct messaging between teachers and parents, second-factor emergency SMS alerts, encrypted confidential counseling channels, and delivery rate analytics.

#### Actor Roles & Trigger Events
- **School Administrator (Principal / Communications Lead)**: Issues school-wide broadcast announcements; schedules community bulletins; authorizes emergency SMS alerts.
- **Teacher**: Communicates with parents regarding academic progress; publishes classroom bulletins.
- **Parent**: Receives institutional announcements; messages teachers; accesses confidential counseling channels.
- **School Psychologist**: Conducts end-to-end encrypted consultations with parents regarding student wellbeing.
- **Trigger Events**: Broadcast scheduled; direct message sent; emergency broadcast triggered; message read receipt registered.

#### Core Functional Capabilities & User Stories
- **Role-Targeted Scheduled Broadcasts**: Authors and schedules announcements targeted to specific personas (e.g., all parents, specific grade-level teachers, entire school community).
- **Client-Side Encrypted Confidential Channels**: Provides end-to-end encrypted messaging channels for parent-psychologist consultations. Plaintext is inaccessible to server administrators.
- **Two-Factor Authorized Emergency SMS Blasting**: Campus-wide emergency alerts (e.g., weather closures, safety incidents) require secondary two-factor authentication (2FA) verification prior to multi-gateway dispatch.
- **Delivery Rate Analytics & Read Tracking**: Tracks delivery confirmations and read receipts across channels, computing institutional communication reach ($R_{deliv}$).
- **Automated Thread Lifecycle Archival**: Inactive messaging threads are automatically archived after 90 days of inactivity, maintaining clean inboxes while preserving full historical auditability.

#### End-to-End Business Workflows & State Machine Lifecycles
```
Broadcast:  [DRAFT] ---> [SCHEDULED] ---> [BROADCASTING] ---> [SENT] ---> [ARCHIVED]
```
- `DRAFT`: Author compiling message body, attachments, and recipient target criteria.
- `SCHEDULED`: Message queued for future release window.
- `BROADCASTING`: Multi-channel dispatch in progress across Push, SMS, and Email gateways.
- `SENT`: Dispatched to all recipients; delivery and read telemetry active.
- `ARCHIVED`: Message archived for historical records.

#### Domain Validation Rules, Invariants & Mathematical Formulations
- **Delivery Effectiveness Formulation**:
  $$R_{deliv} = \left(\frac{N_{delivered}}{N_{dispatched}}\right) \times 100\%$$
- **Operational Invariants**:
  - Broadcast body text length capped at 10,000 characters.
  - Emergency SMS dispatches require secondary 2FA verification code confirmation.
  - Recipient phone numbers must comply with international E.164 formatting.
  - Scheduled broadcast dispatch times must be set in the future.

#### Cross-Module Interactions & Data Flow
- **Universal Notification Backbone**: Delivers alerts and notifications for all other platform modules (M01–M12, M14–M20).
- **Psychological Assessment (M14)**: Carries high-priority crisis intervention alerts to leadership with quiet-hours bypass.
- **Transport Logistics (M15)**: Delivers real-time bus arrival geofence alerts to parents.

---

### M14: Psychological Assessment & Crisis Triage

#### Business Purpose & Scope
The Psychological Assessment module provides a strictly confidential clinical operating environment for licensed School Psychologists to conduct developmental screenings, author client-side encrypted case notes, manage parental consent for minors, triage emergency mental health crises, and execute statutory record retention and cryptographic shredding.

#### Actor Roles & Trigger Events
- **School Psychologist**: Sole clinical persona authorized to conduct assessments, author clinical case notes, manage intervention plans, and triage crises.
- **School Administrator (Principal)**: Receives anonymized crisis escalation alerts requiring institutional protective support.
- **Parent**: Grants verified digital consent for minor student psychological assessments.
- **Trigger Events**: Referral received; parent consent granted; clinical note authored; crisis triage scored; retention milestone reached.

#### Core Functional Capabilities & User Stories
- **Exclusive Clinical Workspace & Confidentiality (FERPA / ISO 27018)**: Clinical case notes are encrypted client-side using AES-256-GCM. The platform database never stores plaintext or decryption keys. Unauthorized access attempts by non-psychologist personas (`TEACHER`, `SCHOOL_ADMIN`, `STAFF`) are denied immediately (403 Forbidden) and logged as security violations.
- **Verified Digital Parental Consent for Minors**: Psychological evaluations for minor students require verified digital parental consent prior to initiating assessments. Evaluations cannot transition to active status without timestamped parental authorization.
- **10-Point Emergency Crisis Triage Protocol**: Evaluates student crisis and distress reports on a 1–10 severity scale. A severity score $\ge 8$ immediately triggers high-priority emergency alerts to school leadership and crisis teams, bypassing quiet hours.
- **Immutable Decryption Audit Ledger**: Every view and decryption of a clinical note generates an immutable audit record detailing the actor, access purpose, timestamp, and device.
- **Statutory Retention & Cryptographic Shredding**: In compliance with FERPA, clinical records are retained for exactly 7 years following a student's legal age of majority. Upon reaching retention expiration, records are permanently shredded by destroying the master wrapped encryption keys.

#### End-to-End Business Workflows & State Machine Lifecycles
```
[SCHEDULED] ---> [IN_PROGRESS] ---> [COMPLETED] ---> [UNDER_REVIEW] ---> [FINALIZED] ---> [ARCHIVED] ---> [PURGED]
```
- `SCHEDULED`: Evaluation scheduled; awaiting verified digital parental consent.
- `IN_PROGRESS`: Parental consent verified; clinical testing and observation active.
- `COMPLETED`: Clinical observations finished; diagnostic notes compiled.
- `UNDER_REVIEW`: Psychologist reviewing intervention strategies and accommodation recommendations.
- `FINALIZED`: Clinical report signed; parent consultation documented; accommodations exported.
- `ARCHIVED`: Student graduated; file sealed in 7-year post-majority retention vault.
- `PURGED`: Retention period expired; master encryption keys destroyed (crypto-shredded).

#### Domain Validation Rules, Invariants & Mathematical Formulations
- **Parental Consent Invariant**:
  $$\text{Can Transition to } IN\_PROGRESS \iff \text{Parental Consent Verified} = \text{TRUE}$$
- **Crisis Triage Protocol**:
  $$\text{Severity Score} \ge 8 \implies \text{Trigger Real-Time Emergency Alert} + \text{Quiet-Hours Bypass}$$
  - Crisis cases cannot be finalized without documented parent contact (`parent_contacted = true`).
- **Operational Invariants**:
  - All non-psychologist personas are categorically barred from decrypting clinical notes (403 Forbidden).
  - Key rotation requires atomic re-wrapping of all active note encryption keys.

#### Cross-Module Interactions & Data Flow
- **Admissions (M01)**: Receives developmental screening flags for prospective students.
- **Attendance Tracking (M06)**: Consumes chronic absenteeism alerts to identify school refusal patterns.
- **Gradebook (M05)**: Consumes cognitive drop alerts ($\ge 15\%$ decline) to intervene in student academic burnout.
- **Fee Management (M08)**: Receives acute family financial distress referrals.
- **Examinations (M04)**: Authorizes official testing accommodations (e.g., 1.5x time extensions).
- **Communication Hub (M13)**: Dispatches emergency crisis alerts bypassing quiet hours.

---

### M15: Transport Logistics & Fleet Tracking

#### Business Purpose & Scope
The Transport Logistics module oversees school bus fleet management, driver vehicle maintenance, route optimization with sequential geocoded waypoints, student seat capacity allocations, real-time GPS telemetry, and parent arrival notifications.

#### Actor Roles & Trigger Events
- **Transport Coordinator / Bus Driver (Staff)**: Configures bus routes; monitors fleet maintenance; drives assigned vehicles; streams GPS telemetry.
- **Parent**: Monitors live bus location on an interactive map; receives stop arrival and departure push notifications; tracks student boarding.
- **School Administrator**: Oversees transport safety compliance, student allocations, and vehicle licensing.
- **Trigger Events**: Bus route run begins; GPS telemetry stream received; geofence boundary crossed; telemetry signal lost; vehicle service mileage reached.

#### Core Functional Capabilities & User Stories
- **Sequential Waypoint Route Management**: Defines ordered bus routes with geocoded waypoints, scheduled arrival/departure windows, and automated transit duration calculations.
- **Vehicle Capacity & Student Seat Allocation**: Allocates students to specific bus routes and seats. Enforces strict vehicle capacity limits ($N_{allocated} \le C_{vehicle}$) and validates pickup and dropoff timing ($t_{pickup} < t_{dropoff}$).
- **Real-Time GPS Telemetry & Geofence Push Alerts**: Ingests vehicle GPS coordinates in real time, validating coordinate plausibility and speed. Detects geofence boundary crossings (`bus_arrived_at_stop`), triggering instant parent push notifications.
- **Telemetry Loss & Signal Gap Detection**: Automatically detects vehicle telemetry signal loss ($> 60$ seconds of silence), raising operational alerts to transport dispatch coordinators.
- **Vehicle Preventive Maintenance Lifecycles**: Monitors bus odometer mileage against service thresholds, scheduling preventive inspections and managing maintenance status.

#### End-to-End Business Workflows & State Machine Lifecycles
```
Vehicle:   [ACTIVE] ---> [MAINTENANCE] ---> [OUT_OF_SERVICE] ---> [RETIRED]

Route Run: [SCHEDULED] ---> [IN_PROGRESS] ---> [COMPLETED]
```
- `ACTIVE`: Vehicle inspected, licensed, and operating on assigned routes.
- `MAINTENANCE`: Bus undergoing scheduled servicing; replaced by backup fleet vehicle.
- `OUT_OF_SERVICE`: Vehicle grounded due to mechanical failure or safety inspection hold.
- `RETIRED`: Decommissioned from institutional service.

#### Domain Validation Rules, Invariants & Mathematical Formulations
- **Vehicle Capacity Invariant**:
  $$\sum \text{Allocated Students} \le \text{Licensed Seating Capacity}$$
  - Route allocations exceeding licensed capacity are rejected with validation code `M15_CAPACITY_EXCEEDED`.
- **Telemetry Silence Alert**:
  $$\Delta t_{silence} > 60 \text{ seconds} \implies \text{Raise Telemetry Gap Alert}$$
- **Operational Invariants**:
  - Student pickup time must be strictly before dropoff time ($t_{pickup} < t_{dropoff}$).
  - GPS coordinates must lie within plausible geographic bounding boxes; speed readings must be non-negative.
  - A student cannot be allocated to conflicting concurrent bus routes.

#### Cross-Module Interactions & Data Flow
- **Admissions (M01)**: Enrolls new students into transport routing rosters upon matriculation.
- **Attendance Tracking (M06)**: Synchronizes morning bus arrival scans with period-1 classroom rosters.
- **HR & Staff Management (M10)**: Synchronizes driver leave and license certifications.
- **Communication Hub (M13)**: Dispatches instant geofence stop arrival alerts to parents.

---

### M16: Cognia Accreditation Evidence & Continuous Improvement

#### Business Purpose & Scope
The Cognia Accreditation module coordinates institutional self-study, accreditation standards alignment (Cognia / AdvancED), digital evidence collection with cryptographic integrity verification, multi-evaluator review queues, Accreditation Maturity Index calculation, and self-review conflict-of-interest prevention.

#### Actor Roles & Trigger Events
- **Principal / Accreditation Lead (School Administrator)**: Manages standards framework; establishes review cycles; assigns evaluators; compiles final self-study dossiers.
- **Teacher / Staff Employee**: Submits educational artifacts, lesson plans, student work samples, and survey results linked to specific standards.
- **Super Administrator**: Conducts multi-school network accreditation benchmarking.
- **Trigger Events**: Accreditation cycle launched; evidence artifact uploaded; review assigned; rubric scored; cycle finalized.

#### Core Functional Capabilities & User Stories
- **Cognia Standards Hierarchy**: Catalogs accreditation standards across core educational domains (Culture of Learning, Leadership for Learning, Engagement of Learning), defining 1–8 rubric criteria per standard.
- **Dual-Checksum Cryptographic Verification**: Collects digital evidence artifacts, enforcing dual client and server SHA-256 checksum verification to guarantee uncompromised file integrity.
- **Accreditation Review Cycles & Maturity Scoring**: Governs review cycles tied to academic years. Computes the composite Accreditation Maturity Index ($M_{cognia}$) upon cycle completion.
- **Independent Review Queue & Self-Review Conflict Guard**: Evaluators score evidence artifacts against standard rubrics. Enforces a strict conflict-of-interest rule: evaluators are barred from reviewing evidence artifacts that they personally authored.
- **Automated Self-Study Accreditation Dossier**: Automatically compiles cycle statistics, maturity scores, rubric distributions, and evidence artifacts into an audit-ready, digitally signed PDF dossier.

#### End-to-End Business Workflows & State Machine Lifecycles
```
Evidence:  [UPLOADED] ---> [UNDER_REVIEW] ---> [APPROVED] ---> [ARCHIVED]
                                 |
                                 v
                            [REJECTED]

Cycle:     [OPEN] ---> [IN_PROGRESS] ---> [CLOSED]
```
- `UPLOADED`: Artifact submitted by staff; dual SHA-256 verified.
- `UNDER_REVIEW`: Assigned to independent evaluator for rubric grading.
- `APPROVED`: Artifact validated as meeting accreditation standard criteria.
- `REJECTED`: Artifact returned to author with required improvement notes.
- `CLOSED`: Review cycle finalized; maturity score computed; dossier locked.

#### Domain Validation Rules, Invariants & Mathematical Formulations
- **Accreditation Maturity Index Formulation**:
  $$M_{cognia} = \frac{1}{N} \sum_{i=1}^{N} \text{RubricScore}_i \quad (1.00 - 4.00)$$
  - Where $\text{RubricScore}_i$ represents the evaluated score across all standards in the cycle.
- **Evaluator Conflict-of-Interest Invariant**:
  $$\text{Author ID} == \text{Reviewer ID} \implies \text{REJECT (VAL\_SELF\_REVIEW\_FORBIDDEN)}$$
- **Operational Invariants**:
  - Review cycles cannot transition to `CLOSED` while evidence items remain in `UNDER_REVIEW` or `REJECTED` states.
  - Evidence files capped at 10 MB per artifact.
  - Evidence archive records are retained for 7 years to satisfy accreditation audit cycles.

#### Cross-Module Interactions & Data Flow
- **Assignments (M03)**: Ingests authenticated student coursework samples and plagiarism records.
- **Exams (M04)**: Ingests examination validity studies and proctoring integrity records.
- **Psychological Assessment (M14)**: Consumes anonymized mental health governance and wellbeing compliance evidence.
- **Reports & Analytics (M19)**: Aggregates longitudinal student retention and academic performance reports.

---

### M17: Platform Administration & Multi-Tenant Supervision

#### Business Purpose & Scope
The Platform Administration module operates the multi-tenant cloud control plane, institutional tenant provisioning, subscription plan quota enforcement, system SLA uptime monitoring, security anomaly detection, tenant suspension, and session revocation.

#### Actor Roles & Trigger Events
- **Super Administrator**: Sole platform operator persona authorized to provision, configure, monitor, suspend, and decommission institutional tenants.
- **Trigger Events**: New school onboarded; subscription tier updated; monthly SLA window evaluated; security incident detected; suspension order executed.

#### Core Functional Capabilities & User Stories
- **Institutional Tenant Provisioning Engine**: Provisions complete school tenant environments with isolated database schemas, subdomain assignment, subscription plan tier (`Standard`, `Premium`, `Enterprise`), and student account quotas (`max_students`).
- **Continuous SLA Uptime Monitoring**: Evaluates tenant system availability against service level agreements, tracking monthly uptime percentages. Tenant status automatically degrades from `Healthy` to `Degraded` if monthly uptime falls below 99.9%.
- **Security Anomaly Detection & Incident Triage**: Ingests platform telemetry to identify anomalous patterns (authentication failure spikes, brute-force attempts, mass data export signals), triaging incidents by severity (`Info`, `Warning`, `Critical`).
- **Enforced Tenant Suspension & Session Revocation**: Suspends non-compliant or delinquent institutional tenants, instantly revoking all active user sessions across web and mobile.
- **Reactivation Security Gate**: Reversal of tenant suspension is strictly blocked until all open critical security anomalies are resolved and closed.

#### End-to-End Business Workflows & State Machine Lifecycles
```
[PROVISIONING] ---> [ACTIVE] ---> [SUSPENDED] ---> [DECOMMISSIONED]
                       ^               |
                       +---------------+ (Reactivation)
```
- `PROVISIONING`: Tenant database schema, default roles, and storage buckets being configured.
- `ACTIVE`: Institutional operations active; user logins and processing running normally.
- `SUSPENDED`: School locked out; all active user sessions revoked; incoming requests blocked.
- `DECOMMISSIONED`: Tenant permanently terminated; data archived and crypto-shredded.

#### Domain Validation Rules, Invariants & Mathematical Formulations
- **Monthly SLA Uptime Formulation**:
  $$\text{Uptime}_{\%} = \left(1 - \frac{\text{Downtime\_Minutes}}{\text{Total\_Month\_Minutes}}\right) \times 100\%$$
  - Tenant status degrades to `Degraded` if $\text{Uptime}_{\%} < 99.90\%$.
- **Reactivation Security Gate Invariant**:
  $$\text{Active Critical Security Anomalies} > 0 \implies \text{Block Reactivation (PLT\_CRITICAL\_ANOMALY)}$$
- **Operational Invariants**:
  - Tenant subdomains must be globally unique across the entire cloud platform.
  - Only `SUSPENDED` tenants can be transitioned to `DECOMMISSIONED` (irreversible terminal state).
  - Operations creating accounts exceeding tenant subscription student quotas are rejected.

#### Cross-Module Interactions & Data Flow
- **User & Role Management (M18)**: Initializes institutional roles and administrator accounts during tenant provisioning.
- **Settings & Configuration (M20)**: Injects platform default configuration templates into newly provisioned tenants.
- **Communication Hub (M13)**: Informs institutional leadership of suspension or reactivation actions.
- **Reports & Analytics (M19)**: Streams operational platform health and uptime KPIs.

---

### M18: User Identity & Role-Based Access Control (RBAC)

#### Business Purpose & Scope
The User & Role Management module operates the core identity directory, user lifecycle management, 7-persona system roles, custom role hierarchies with cycle detection, multi-factor authentication (MFA), session token revocation, and passphrase entropy validation.

#### Actor Roles & Trigger Events
- **Super Administrator**: Oversees cross-tenant identity policies; manages global administrative assignments.
- **School Administrator**: Provisions school staff, teachers, students, and parents; creates custom institutional roles; manages MFA enforcement; revokes user sessions.
- **All Users (7 Personas)**: Manage personal credentials; enroll MFA devices; view active sessions.
- **Trigger Events**: User invited or onboarded; custom role created; MFA enrolled; session terminated; passphrase updated.

#### Core Functional Capabilities & User Stories
- **Standard 7-Persona System Roles**: Seeds and enforces the immutable foundational roles (`SUPER_ADMIN`, `SCHOOL_ADMIN`, `TEACHER`, `STUDENT`, `PARENT`, `STAFF`, `PSYCHOLOGIST`) per tenant.
- **Custom Role Creation with Acyclic Inheritance**: Enables administrators to author specialized operational roles (e.g., "Department Head", "Admissions Officer", "Bus Monitor") that inherit permissions from existing roles. Enforces cycle detection algorithms to ensure the role inheritance graph remains strictly acyclic.
- **Least-Privilege RBAC Resolution Engine**: Computes effective user permissions by uniting direct grants and inherited permissions. Follows an explicit deny-by-default policy (unassigned actions are denied).
- **Multi-Factor Authentication (MFA) Enforcement**: Supports TOTP (authenticator apps) and WebAuthn (biometric hardware keys). Mandatory for administrative users prior to performing privileged actions.
- **Centralized Session Tracking & Instant Revocation**: Tracks concurrent user login sessions, device metadata, and expiration timestamps. Administrators can revoke individual sessions or execute a global logout across all devices.
- **Mathematical Passphrase Strength Validation**: Enforces robust passphrase complexity by calculating Shannon entropy across submitted credentials.

#### End-to-End Business Workflows & State Machine Lifecycles
```
User:     [UNASSIGNED] ---> [ASSIGNED] ---> [ACTIVE] ---> [SUSPENDED]

Session:  [ACTIVE] ---> [REVOKED]
```
- `UNASSIGNED`: Identity invitation created; waiting for user onboarding.
- `ASSIGNED`: Role and institutional affiliations mapped to identity.
- `ACTIVE`: Primary credential established; MFA enrolled; logins permitted.
- `SUSPENDED`: Access blocked immediately; active sessions invalidated.

#### Domain Validation Rules, Invariants & Mathematical Formulations
- **Shannon Entropy Passphrase Formulation**:
  $$H(P) = -\sum_{i=1}^{k} p_i \log_2(p_i)$$
  - Where $p_i$ is the frequency of character $i$ within passphrase $P$ of length $L$.
  - Passphrases failing the minimum entropy threshold are rejected during registration.
- **Acyclic Role Inheritance Invariant**:
  $$\text{Cycle}(Role_{target} \to \dots \to Role_{target}) = \text{TRUE} \implies \text{REJECT (VAL\_ROLE\_CYCLE)}$$
  - Custom roles cannot inherit from themselves directly or transitively.
- **Operational Invariants**:
  - Email addresses must conform to RFC 5322 format and be unique within an institution.
  - System roles are protected and cannot be deleted or modified.
  - Session revocation takes effect immediately across all edge proxies.

#### Cross-Module Interactions & Data Flow
- **Identity & Authorization Authority**: Provides authentication and authorization resolution across all platform modules (M01–M20).
- **Psychological Assessment (M14)**: Enforces clinical data isolation barriers against non-psychologist personas.
- **HR & Staff Management (M10)**: Synchronizes employee status updates and departmental role assignments.

---

### M19: Reports, Business Intelligence & Data Warehouse Sync

#### Business Purpose & Scope
The Reports & Analytics module oversees operational and analytical reporting, student retention rate modeling, asynchronous priority job queues, scheduled report dispatches, interactive KPI dashboards, time-limited report sharing, and automated document retention purging.

#### Actor Roles & Trigger Events
- **School Administrator**: Designs custom reports; views executive KPI dashboards; schedules recurring report dispatches; analyzes school performance trends.
- **Teacher**: Generates section grade distribution curves, attendance analyses, and student progress summaries.
- **Staff Employee**: Generates operational reports (e.g., bus route manifests, fee collection summaries).
- **Super Administrator**: Conducts cross-institutional network benchmarking.
- **School Psychologist**: Reviews confidential wellbeing and counseling caseload aggregate analytics.
- **Trigger Events**: Report execution requested; scheduled report cron triggers; background report job completes; retention policy purge executed.

#### Core Functional Capabilities & User Stories
- **Student Retention Rate Modeling**: Calculates institutional cohort retention across academic periods, excluding new admissions to measure true institutional continuity.
- **Asynchronous Priority Job Queue**: Dispatches long-running report generation jobs to background worker queues, ranking jobs by dynamic priority scores factoring age, remaining retries, and deadline urgency.
- **Scheduled Report Dispatching**: Supports cron-driven report generation schedules, automatically formatting reports as CSV or PDF and delivering them via email or secure download links.
- **Permission-Gated Time-Limited Report Sharing**: Exported report artifacts require authentication and are shared via signed cryptographic tokens valid for at most 90 days.
- **Automated Retention & Document Purging**: Retains report artifacts for a configurable policy window (default 12 months) before permanently purging expired files with audit logging.
- **Interactive Executive KPI Dashboards**: Provides customizable dashboard widgets (KPI cards, trends, heatmaps) with threshold alerting when institutional metrics decline below targets.

#### End-to-End Business Workflows & State Machine Lifecycles
```
[DRAFTED] ---> [QUEUED] ---> [RUNNING] ---> [COMPLETED]
                  |             |
                  v             v
             [CANCELLED]     [FAILED] (Max 3 retries)
```
- `DRAFTED`: Report parameters, filters, and output format configured.
- `QUEUED`: Enqueued in priority background job queue awaiting worker execution.
- `RUNNING`: Query execution and document compilation in progress.
- `COMPLETED`: Report document generated; signed access token issued.
- `FAILED`: Execution error encountered; retried up to 3 times before failing.

#### Domain Validation Rules, Invariants & Mathematical Formulations
- **Student Retention Rate Formulation**:
  $$R_{retention} = \left(\frac{N_{enrolled\_end} - N_{new}}{N_{enrolled\_start}}\right) \times 100\%$$
  - $N_{enrolled\_start}$: Initial cohort enrollment count at the start of the academic period ($N_{enrolled\_start} > 0$).
  - $N_{enrolled\_end}$: Total active enrollment at the conclusion of the period.
  - $N_{new}$: Newly admitted students entering during the period (excluded from retention).
  - If $N_{enrolled\_start} = 0$, the formula aborts with `VAL_REPORT_PARAMS`, preventing divide-by-zero crashes.
- **Dynamic Job Queue Priority Score Formulation**:
  $$S_{job} = 0.5 \left(\frac{1}{\text{age\_min} + 1}\right) + 0.3 \left(\frac{\text{retries\_left}}{\text{max\_retries}}\right) + 0.2 (\text{deadline\_urgency})$$
  - Background workers dequeue and execute jobs in descending order of $S_{job}$.
- **Operational Invariants**:
  - Report sharing tokens cannot exceed a lifetime of 90 days.
  - Downloads of purged reports return an explicit "Purged" status.
  - Access to report outputs is strictly scoped to the user's role and departmental permissions.

#### Cross-Module Interactions & Data Flow
- **Universal Data Aggregator**: Ingests operational data from all academic and administrative modules (M01–M16).
- **Communication Hub (M13)**: Delivers scheduled report artifacts and download notifications.
- **Platform Administration (M17)**: Feeds institutional uptime, usage, and operational KPIs.

---

### M20: Settings, Configuration Management & Academic Calendars

#### Business Purpose & Scope
The Settings & Configuration module operates the organization-wide configuration plane, 4-tier setting inheritance, two-person change approval workflows, pre-apply backups with automatic rollback, validation hysteresis deadbands, master academic calendar publishing, and Audit Completeness Index monitoring.

#### Actor Roles & Trigger Events
- **School Administrator**: Configures institutional policies; authors academic terms and holiday calendars; requests configuration updates.
- **Super Administrator**: Reviews and approves critical configuration change requests; manages tenant-level feature flag overrides.
- **Trigger Events**: Configuration change proposed; change request approved; configuration version applied; validation failure triggers rollback; academic calendar term published.

#### Core Functional Capabilities & User Stories
- **Hierarchical Configuration Resolution Engine**: Resolves configuration settings across a 4-tier hierarchy: Platform Baseline Defaults $\to$ Organization Overrides $\to$ Module Overrides $\to$ Environment Overrides. More specific levels supersede broader defaults.
- **Two-Person Change Approval Workflow**: Critical configuration changes require formal submission of a change request. Enforces a strict segregation-of-duties policy: the change author is barred from approving their own change request (`VAL_APPROVER_CONFLICT`).
- **Pre-Apply Snapshot Backup & Automated Rollback**: Prior to activating a new configuration version, the system creates an immutable backup of the active version. If propagation or validation fails, the system automatically rolls back to the prior version and records the failure.
- **Conflict Resolution Scoring for Concurrent Edits**: Scores overlapping change requests targeting identical key sets, prioritizing the higher-scoring proposal while returning the lower-scoring request to draft for rebasing.
- **Validation Hysteresis Deadband**: Implements a 10% deadband threshold on numerical configuration triggers to prevent rapid alert or policy oscillation around borderline values.
- **Master Academic Calendar & School Day Model**: Manages institutional calendar terms, calculating actual instructional school days by subtracting weekends and published holidays.
- **Audit Completeness Index (ACI) Monitoring**: Continuously monitors configuration mutation records, verifying that 100% of mutations possess complete audit records.

#### End-to-End Business Workflows & State Machine Lifecycles
```
[DRAFT] ---> [PENDING_APPROVAL] ---> [APPROVED] ---> [APPLYING] ---> [APPLIED]
                     |                                   |
                     v                                   v
                 [REJECTED]                        [ROLLED_BACK]
```
- `DRAFT`: Administrative user editing setting keys and values.
- `PENDING_APPROVAL`: Change proposal submitted; awaiting independent reviewer sign-off.
- `APPROVED`: Authorized by independent administrator; queued for propagation.
- `APPLYING`: Snapshot created; setting values propagating across tenant services.
- `APPLIED`: Propagation confirmed; active version incremented.
- `ROLLED_BACK`: Propagation failure detected; prior snapshot restored automatically.

#### Domain Validation Rules, Invariants & Mathematical Formulations
- **School Day Calendar Formulation**:
  $$D_{school} = D_{total} - (D_{weekends} + D_{holidays})$$
  - Where $D_{total}$ is the total calendar span of the term.
  - Spans where $D_{weekends} + D_{holidays} \ge D_{total}$ are rejected with validation code `VAL_CALENDAR_TERM`.
- **Concurrent Change Conflict Score Formulation**:
  $$S_{conflict} = 0.4\,N_{keys} + 0.4 \left(\frac{|A \cap B|}{\max(|A|, |B|)}\right) + 0.2 \left(\frac{\delta_{min}}{1440}\right)$$
  - Where $A$ and $B$ are key sets of two overlapping proposals, and $\delta_{min}$ is the age difference in minutes. The request with the higher score proceeds.
- **Validation Hysteresis Deadband**:
  - A threshold configuration trigger $H$ toggles only when value $V > H + \Delta$ on the rising edge and $V < H - \Delta$ on the falling edge, with $\Delta = 0.10 \times H$. Values within $[H - \Delta, H + \Delta]$ do not flip, preventing alert oscillation.
- **Audit Completeness Index (ACI)**:
  $$\text{ACI} = \left(\frac{N_{audited}}{N_{mutations}}\right) \times 100\% \ge 99.99\%$$
- **Segregation-of-Duties Invariant**:
  $$\text{Author ID} == \text{Approver ID} \implies \text{REJECT (VAL\_APPROVER\_CONFLICT)}$$

#### Cross-Module Interactions & Data Flow
- **Timetable (M07) & Exams (M04)**: Consumes published master academic terms, school days, and holiday calendars.
- **Platform Administration (M17)**: Coordinates tenant-level feature flag overrides and entitlement rollouts.
- **Universal Configuration Authority**: Injects operational parameters and policy thresholds into all functional modules (M01–M19).

---

## 5. Pillar 1 Master Features Inventory Table

The following master inventory specifies all 80 discovered business functional features comprising Core Foundation and Modules M01 through M20:

| # | Domain / Module | Feature Name | Business Purpose & Description | Input Parameters | System Output | Validation & Error Behavior | Source Trace |
|---|---|---|---|---|---|---|---|
| 1 | Core Foundation | Identity & OIDC SSO | Unified identity authentication across web and mobile via standard OIDC federation. | User credentials, authorization code | Authenticated session, user identity claims | 401 Unauthorized on invalid credentials | AUTH_FLOWS.md §1-4 |
| 2 | Core Foundation | Mandatory Admin MFA | Enforces TOTP/WebAuthn second-factor authentication for Super and School Admins. | TOTP 6-digit code / WebAuthn assertion | Activated administrative session | 403 Forbidden until second factor verified | AUTH_FLOWS.md §8 |
| 3 | Core Foundation | Tenant Data Boundary | Logical isolation of all records by institutional tenant boundary. | Authenticated tenant identity | Tenant-isolated data scope | 404 Not Found on cross-tenant attempts | CORE_ARCH.md §5 |
| 4 | Core Foundation | Centralized Push Gateway | Multi-tenant push notification dispatcher across iOS (APNs) and Android (FCM). | User IDs, title, body, priority, deepLink | Dispatched push notifications | Expired/dead device tokens evicted | FCM_PUSH.md §1-4 |
| 5 | Core Foundation | Quiet Hours Crisis Override | Emergency alerts bypass user quiet hours with real-time dispatch (< 2s SLA). | Alert with priority = 'crisis' | Immediate device dispatch | Downgraded to standard if priority < crisis | FCM_PUSH.md §1 |
| 6 | Core Foundation | Feature Flag Entitlement | Per-tenant module licensing and instant emergency kill-switch. | Module ID, tenant ID, enable flag | Module route registration / toggle | 404 Not Found if module disabled | FEATURE_FLAGS.md §1-6 |
| 7 | Core Foundation | 7-Persona RBAC | Granular role-based authorization across 7 academic personas. | User persona role, target action | Authorized execution | 403 Forbidden on permission denial | PLAT-FR-012 |
| 8 | Core Foundation | Clinical Data Separation | AES-256-GCM client-side encryption of mental health notes; psychologist access only. | Clinical case notes | Encrypted ciphertext envelope | 403 Forbidden to non-psychologists | PLAT-FR-005 |
| 9 | Core Foundation | Offline Sync Reconciliation | Local mutation caching and conflict resolution for field mobile personas. | Local mutations, sync timestamps | Reconciled server state | Conflict resolution screen on collision | PLAT-FR-003 |
| 10 | M01 Admissions | Lead Score Calculation | Weighted composite readiness score with dynamic renormalization for missing GPA. | Exam percentile, interview, GPA, profile | Lead score $S_{adm}$ (0.00–100.00) | Aborts to NULL if < 2 criteria present | M01/03_MATHEMATICAL |
| 11 | M01 Admissions | Standardized Interview | Evaluator 1–5 rubric scoring rescaled mathematically to a 0–100 index. | Rubric ratings (1–5 integers) | Standardized interview score | 422 Unprocessable if rubric out of range | M01/03_MATHEMATICAL |
| 12 | M01 Admissions | Admission State Machine | Manages prospective student lifecycle from draft through interview to matriculation. | Application mutation triggers | Updated application status | 409 Conflict on invalid state transition | M01/05_STATE_MACHINE |
| 13 | M02 Live Classes | WebRTC Attendance Log | Correlates connection/disconnection heartbeats to calculate active minutes. | Room join/leave timestamps | Calculated active attendance minutes | 404 if session not found | M02/02_FUNCTIONAL |
| 14 | M02 Live Classes | Attendant Engagement Score | Multi-factor engagement index measuring active time, poll answers, and chat. | Active minutes, polls, chat count | Engagement score $E_{class}$ (0.00–1.00) | Clamped strictly between 0.00 and 1.00 | M02/03_MATHEMATICAL |
| 15 | M02 Live Classes | In-Class Polls | Real-time comprehension polling with single response constraint per student. | Poll question, options, student vote | Real-time aggregated poll metrics | 409 Conflict on duplicate vote attempt | M02/02_FUNCTIONAL |
| 16 | M02 Live Classes | Chat Moderation | Server-side profanity filtering and automated toxicity quarantining. | Chat message text | Approved message / Quarantined flag | 422 if toxic; routed to teacher review | M02/02_FUNCTIONAL |
| 17 | M03 Assignments | Rubric-Based Grading | Authoring multi-criteria rubrics with enforced 100.00% weight sum. | Criteria list, weights, max points | Validated grading rubric | 422 if sum of weights != 100.00% | M03/02_FUNCTIONAL |
| 18 | M03 Assignments | Resumable File Upload | Chunked upload transfer allowing resume after network disconnection. | File chunks, chunk sequence, hashes | Assembled submission document | 422 on chunk hash mismatch | M03/02_FUNCTIONAL |
| 19 | M03 Assignments | Late Penalty Decay | Automated 5%/day score deduction; zero credit past 5 days late. | Earned points, submission timestamp | Adjusted final assignment grade | 0 points awarded if days_late > 5 | M03/03_MATHEMATICAL |
| 20 | M03 Assignments | Plagiarism Scanning | Detects text similarity against internal and external student corpora. | Submission text | Similarity percentage report | Escalated to review queue if >= 30% | M03/02_FUNCTIONAL |
| 21 | M04 Exams | IRT Paper Generation | Calibrates exam paper difficulty using 2-parameter logistic IRT model. | Question bank items, target difficulty | Deterministic exam paper | 422 if bank items insufficient | M04/03_MATHEMATICAL |
| 22 | M04 Exams | Automated Proctoring | Real-time anomaly detection (face loss, tab switch, copy-paste, audio). | Webcam/browser anomaly telemetry | Anomaly flags, confidence score | Submission locked if confidence >= 0.85 | M04/02_FUNCTIONAL |
| 23 | M04 Exams | Session Nonce Protection | Prevents replay attacks during exam submission using single-use nonces. | Unique submission nonce | Atomically consumed submission | 409 Conflict on reused nonce | M04/02_FUNCTIONAL |
| 24 | M04 Exams | Exam Grade Voiding | Administrative score invalidation protocol with mandatory reason and snapshot. | Exam session ID, void reason, admin auth | Voided exam status, audit record | 403 Forbidden if not School Admin | M04/02_FUNCTIONAL |
| 25 | M05 Gradebook | Weighted / Unweighted GPA | Term GPA calculation factoring Honors (+0.5) and AP/IB (+1.0) rigor. | Course grades, credit hours, rigor bonus | Unweighted GPA, Weighted GPA | Capped at 4.500; no bonus on grade F | M05/03_MATHEMATICAL |
| 26 | M05 Gradebook | Cognitive Drop Detection | Flags students whose term percentage drops >= 15% below rolling average. | Term percentage, 3-term rolling average | Academic probation flag, Psych alert | Report card held pending review | M05/02_FUNCTIONAL |
| 27 | M05 Gradebook | Principal Report Card Sign-off | Digital cryptographic signature requirement before report card publishing. | Finalized term grades, Principal signature | Published official report card PDF | 422 Unprocessable if signature missing | M05/02_FUNCTIONAL |
| 28 | M06 Attendance | Roster Period Attendance | Period-level attendance marking across present, late, absent, excused. | Section ID, period, date, student statuses | Committed attendance session | 409 Conflict on duplicate session | M06/02_FUNCTIONAL |
| 29 | M06 Attendance | Attendance Percentage | Formula where late arrivals receive 0.5 attendance credit. | Present count, late count, total sessions | Attendance percentage | Clamped between 0.0% and 100.0% | M06/03_MATHEMATICAL |
| 30 | M06 Attendance | Parent Absence Excuse | Digital excuse submission with medical note attachment and approval flow. | Excuse date range, reason, doctor note | Approved / rejected excuse | 422 if retrospective > 30 days | M06/02_FUNCTIONAL |
| 31 | M06 Attendance | Truancy Escalation | Automatic warning alerts when unexcused absences breach thresholds. | Cumulative unexcused absence count | Truancy alert to parent and psychologist | Triggered at configured threshold | M06/02_FUNCTIONAL |
| 32 | M07 Timetable | Constraint Schedule Solver | Optimization minimizing teacher double-booking, gaps, and room moves. | Teachers, rooms, sections, periods | Conflict-free master timetable | 409 Conflict with conflict coordinates | M07/03_MATHEMATICAL |
| 33 | M07 Timetable | Cognitive Workload Balancing | Schedules high-intensity subjects (Math/Physics) into morning periods 1–3. | Subject intensity classification | Balanced period schedule | Fallback warning on tight constraints | M07/02_FUNCTIONAL |
| 34 | M07 Timetable | Emergency Teacher Substitution | Identifies qualified substitute teachers upon approved staff leave. | Absent teacher, date range, assigned classes | Assigned substitute schedule | 409 Conflict if substitute has conflict | M07/02_FUNCTIONAL |
| 35 | M08 Fee Management | Batch Invoice Generation | Automated grade-level invoice compilation for enrolled cohorts. | Grade fee structure, term, student IDs | Generated batch invoices | 422 on invalid fee structure | M08/02_FUNCTIONAL |
| 36 | M08 Fee Management | Stripe Hosted Checkout | Webhook-settled digital payment processing with signature deduplication. | Invoice ID, payer details | Settled invoice, payment receipt | Webhook rejected on bad signature | M08/02_FUNCTIONAL |
| 37 | M08 Fee Management | Compound Late Interest | Overdue interest accrual with 25% balance ceiling and flat fee. | Outstanding balance, overdue days, rate | Accrued late fee amount | Capped at min(0.25*balance, F_max) | M08/03_MATHEMATICAL |
| 38 | M08 Fee Management | Financial Distress Triage | Flags families with >= 30 days overdue or >= 2 missed installments. | Invoice overdue status, installment history | Counseling referral flag to Psychologist | Automatic routing upon threshold | M08/02_FUNCTIONAL |
| 39 | M09 Financial Mgmt | Double-Entry Bookkeeping | Balanced journal entry verification requiring sum of debits = credits. | Debit lines, credit lines, accounts | Posted general ledger journal entry | 422 if Debits != Credits | M09/03_MATHEMATICAL |
| 40 | M09 Financial Mgmt | Budget Variance Monitoring | Departmental spend tracking with alerts at 75%, 90%, and 100% caps. | Department budget, posted expense entries | Variance percentage, threshold alerts | 100% blocks further commitments | M09/02_FUNCTIONAL |
| 41 | M09 Financial Mgmt | Mental Health Fund Allocation | Automatically allocates 5% to mental health sub-budget at 75% department spend. | Department 75% budget trigger | Earmarked counseling support budget | Evaluated by Psychologist | M09/02_FUNCTIONAL |
| 42 | M09 Financial Mgmt | Fiscal Period Closing | Locks accounting periods, generating closing balance sheets. | Fiscal period ID, admin authorization | Closed fiscal period | Reopening requires Super Admin | M09/02_FUNCTIONAL |
| 43 | M10 HR | Annual Leave Accrual | Monthly leave accrual computation based on tenure and annual quota. | Months worked, annual entitlement | Updated accrued leave balance | Rejected if requested > balance | M10/03_MATHEMATICAL |
| 44 | M10 HR | Multi-Step Leave Approval | Supervisor and HR approval workflow with automated substitute handoff. | Leave request dates, reason | Approved leave, timetable notification | 409 if requested without balance | M10/02_FUNCTIONAL |
| 45 | M10 HR | Staff Performance Appraisal | Weighted appraisal scoring across teaching (40%), conduct (30%), outcomes (30%). | Rubric scores per dimension | Composite appraisal rating | 422 if criteria missing | M10/02_FUNCTIONAL |
| 46 | M10 HR | Educator Burnout Triage | Identifies workload stress indicators to schedule wellness consultations. | Overtime, substitute load, sentiment | Proactive wellness outreach alert | Confidential notes encrypted | M10/02_FUNCTIONAL |
| 47 | M11 Payroll | Progressive Tax Withholding | Piecewise linear tax withholding across annualized gross income brackets. | Gross earnings, jurisdictional tax bands | Monthly tax withholding amount | Fails if tax table unconfigured | M11/03_MATHEMATICAL |
| 48 | M11 Payroll | Non-Negative Net Pay | Formula subtracting taxes, social security, and deductions; clamps at 0. | Basic salary, allowances, deductions | Net pay slip amount | Excess deductions carried forward | M11/03_MATHEMATICAL |
| 49 | M11 Payroll | Payroll Period Lock | Locks paid periods preventing recalculations or alterations of history. | Payroll run month, admin approval | Locked/Paid payroll status | 409 Conflict on recalculation attempt | M11/02_FUNCTIONAL |
| 50 | M11 Payroll | Salary Confidentiality | ISO 27018 compensation privacy; salary data excluded from logs/headers. | Payroll processing operations | Encrypted employee pay slips | System logs strip all salary fields | M11/02_FUNCTIONAL |
| 51 | M12 Digital Library | Barcoded Inventory Lending | Checkout/return tracking with availability state validation. | Book copy barcode, borrower ID | Active loan record | 409 Conflict if copy not available | M12/02_FUNCTIONAL |
| 52 | M12 Digital Library | Overdue Library Fines | Daily overdue fine assessment at $0.50 per day overdue. | Return date, loan due date | Assessed library fine amount | Fines routed to M08 billing | M12/03_MATHEMATICAL |
| 53 | M12 Digital Library | Secure E-Book Streaming | Time-limited signed streaming tokens (5-minute TTL) for digital titles. | Borrower ID, active digital loan | 5-minute signed stream token | Revoked upon loan return | M12/02_FUNCTIONAL |
| 54 | M12 Digital Library | 24 Educational Tool Registry | Sandboxed iframe integration and usage telemetry for 24 digital tools. | Tool URL, student session, tool name | Usage duration, interaction metrics | Broken links flagged within 1 hr | FRD §3.2, M12/01 |
| 55 | M13 Communication | Role-Targeted Broadcasts | Targeted announcements scheduled and dispatched by persona groups. | Target roles, message title, body | Dispatched broadcast feed | 422 if body > 10,000 characters | M13/02_FUNCTIONAL |
| 56 | M13 Communication | E2E Confidential Chat | Client-side encrypted direct messaging for parent-psychologist consultation. | Encrypted message ciphertext | Delivered message | Plaintext unavailable to server | M13/02_FUNCTIONAL |
| 57 | M13 Communication | Emergency 2FA SMS Blast | Multi-provider SMS alert dispatch requiring two-factor authorization. | Alert text, emergency 2FA code | Multi-gateway SMS dispatch | 403 Forbidden if 2FA unconfirmed | M13/02_FUNCTIONAL |
| 58 | M14 Psych Assessment | Clinical Confidentiality | Client-side AES-256-GCM encryption of case notes; exclusive psychologist access. | Clinical assessment notes | Wrapped encrypted note | 403 Forbidden to all non-psychologists | M14/02_FUNCTIONAL |
| 59 | M14 Psych Assessment | Minor Consent Capture | Mandatory digital parental consent prior to initiating minor evaluations. | Student ID, Parent consent signature | Authorized assessment session | 422 if consent missing | M14/02_FUNCTIONAL |
| 60 | M14 Psych Assessment | 10-Point Crisis Triage | Triage protocol where severity >= 8 triggers immediate leadership alert. | Distress report, severity rating (1–10) | Urgent crisis alert dispatch | Requires parent contact | M14/02_FUNCTIONAL |
| 61 | M14 Psych Assessment | Cryptographic Shredding | Permanent key destruction after 7-year post-majority retention expiration. | Retention purge trigger | Destroyed master key; purged record | Unrecoverable data shredding | M14/02_FUNCTIONAL |
| 62 | M15 Transport | Waypoint Route Manager | Sequential geocoded bus stop definitions with transit duration recalculation. | Route stops, sequence indices | Optimized route timeline | 422 on duplicate sequence | M15/02_FUNCTIONAL |
| 63 | M15 Transport | Fleet Capacity Allocation | Allocates students to bus seats enforcing licensed vehicle capacity limits. | Student ID, route ID, seat number | Confirmed route manifest | 409 Conflict if bus capacity exceeded | M15/02_FUNCTIONAL |
| 64 | M15 Transport | GPS Telemetry & Geofence | Real-time vehicle coordinate tracking with stop arrival push alerts. | Ingested GPS points, speed | Bus arrival/departure alerts | Telemetry gap > 60s raises alert | M15/02_FUNCTIONAL |
| 65 | M16 Cognia Evidence | Dual-Checksum Verification | Client and server SHA-256 validation for uploaded accreditation artifacts. | Artifact file, client SHA-256 hash | Verified evidence artifact | 422 on checksum mismatch | M16/02_FUNCTIONAL |
| 66 | M16 Cognia Evidence | Accreditation Maturity Index | Weighted mean evaluation across all standards (1.00–4.00 scale). | Evaluated standard rubric scores | Cycle Maturity Index score | Cycle blocked if evidence pending | M16/03_MATHEMATICAL |
| 67 | M16 Cognia Evidence | Reviewer Self-Review Guard | Prevents evaluators from reviewing accreditation artifacts they uploaded. | Evidence uploader ID, reviewer ID | Authorized evaluation queue | 403 Forbidden if uploader == reviewer | M16/02_FUNCTIONAL |
| 68 | M17 Platform Admin | Institutional Provisioning | Creates tenant environments with subdomain, plan tier, and student quotas. | School name, subdomain, tier, max seats | Provisioned tenant instance | 409 Conflict on duplicate subdomain | M17/02_FUNCTIONAL |
| 69 | M17 Platform Admin | SLA Uptime Monitoring | Real-time monthly service availability tracking; flags status below 99.9%. | Service health ping telemetry | Monthly uptime percentage | Degraded status if uptime < 99.9% | M17/03_MATHEMATICAL |
| 70 | M17 Platform Admin | Tenant Suspension Protocol | Disables delinquent/breached schools and revokes active sessions. | Tenant ID, suspension reason | Suspended status, session revocation | Reversal blocked on open issues | M17/02_FUNCTIONAL |
| 71 | M18 User & Role Mgmt | Custom Role Hierarchies | Allows authoring specialized roles with acyclic inheritance validation. | Role name, parent role, permissions | Validated custom role definition | 409 Conflict on circular role inheritance | M18/02_FUNCTIONAL |
| 72 | M18 User & Role Mgmt | Session Revocation Engine | Administrative and self-service remote session termination. | Target user ID, session ID | Invalidated access token | Immediate session cutoff | M18/02_FUNCTIONAL |
| 73 | M18 User & Role Mgmt | Password Entropy Check | Mathematical validation of passphrase strength via Shannon entropy. | Passphrase string | Entropy score | Rejected if entropy below standard | M18/03_MATHEMATICAL |
| 74 | M19 Reports & Analytics | Student Retention Rate | Analytical model measuring cohort retention excluding new admissions. | Start enrollment, end count, new count | Retention rate percentage | Rejected if start count == 0 | M19/03_MATHEMATICAL |
| 75 | M19 Reports & Analytics | Dynamic Job Cost Priority | Priority ranking based on job age, retries left, and deadline urgency. | Job creation time, retry count, deadline | Priority queue score | Dequeued in descending order | M19/03_MATHEMATICAL |
| 76 | M19 Reports & Analytics | Time-Limited Report Sharing | Sharing report exports via signed cryptographic tokens valid for <= 90 days. | Report ID, recipient, expiration date | Signed access URL token | 410 Gone on access after expiration | M19/02_FUNCTIONAL |
| 77 | M20 Settings & Config | Hierarchical Config Engine | Resolves settings across platform, org, module, and env override tiers. | Configuration key, tenant context | Effective setting value and tier | 409 on same-level conflict | M20/02_FUNCTIONAL |
| 78 | M20 Settings & Config | Two-Person Approval Guard | Mandatory separation of duties preventing authors from approving changes. | Change request ID, approver ID | Approved configuration version | 409 Conflict if author == approver | M20/04_VALIDATION |
| 79 | M20 Settings & Config | Snapshot Backup & Rollback | Automated backup before activation with immediate rollback on failure. | Incoming configuration payload | Restored active version on failure | Alert emitted on rollback | M20/02_FUNCTIONAL |
| 80 | M20 Settings & Config | School Day Calendar Model | Computes instructional days by subtracting weekends and holidays from span. | Term start date, end date, holiday list | Calculated school instructional days | 422 if holidays >= total span | M20/03_MATHEMATICAL |

---

## 6. Pillar 1 Edge Cases & Operational Failure Modes Table

The following master edge case specification articulates the 34 concrete boundary conditions, exception triggers, and business remediation behaviors across the Core Platform and Pillar 1:

| # | Module / Domain | Trigger Condition / Boundary Input | System Response & Enforced Business Behavior | Operational Remediation & Audit |
|---|---|---|---|---|
| 1 | M01 Admissions | First-time applicant without prior schooling history (`prior_gpa` is null). | System dynamically renormalizes surviving weights over entrance exam, interview, and profile fit ($S_{adm} = \sum w_k S_k / 0.80$). No penalty is assessed for having no prior school. | Candidate score reaches full potential ($0–100$ scale); calculation logged in admissions audit trail. |
| 2 | M01 Admissions | Application submitted with fewer than 2 evaluation components present. | System aborts lead score computation, records $S_{adm} = \text{NULL}$, and routes application to manual admissions review. Never derives a score from a single component. | Status set to `MANUAL_REVIEW_PENDING`; notification sent to Admissions Director. |
| 3 | M02 Live Classes | Student disconnects abruptly (closes browser window or network drops $> 30$ seconds). | Heartbeat monitor records disconnection, credits attendance minutes up to the last confirmed heartbeat, and gracefully closes the telemetry stream without corrupting session data. | Partial attendance recorded; student can reconnect and resume session telemetry. |
| 4 | M02 Live Classes | In-class chat message contains profanity or prohibited harassment terms. | Server-side profanity filter immediately intercepts and quarantines the message, hiding it from peer students and displaying it exclusively in the teacher moderation console. | Message marked `QUARANTINED`; teacher can approve, delete, or mute student with audit log. |
| 5 | M03 Assignments | Submission received 5 days and 2 hours (122 hours) past published deadline. | Elapsed duration exceeds the 5-day penalty window ($days\_late > 5$); late penalty decay formula sets $P_{final} = 0.00$, awarding zero credit while preserving the submission artifact. | Grade recorded as 0.00; submission file retained for instructional review; parent notified. |
| 6 | M03 Assignments | Rubric authoring submitted with criterion weights summing to 99.50% or 100.50%. | System rejects rubric authoring with validation code `M03_RUBRIC_WEIGHT_SUM`, preventing assignment publishing until criterion weights sum to exactly 100.00%. | Author presented with exact sum discrepancy and required to rebalance weights. |
| 7 | M04 Exams | Student webcam loss or browser tab-switching anomaly confidence reaches $\ge 0.85$. | Exam session is locked immediately; submission attempts return a proctoring blockage error; student cannot proceed without administrative clearance. | School Administrator inspects proctoring video snapshot and issues unlock or void decision. |
| 8 | M04 Exams | Student attempts to resubmit exam answers using a previously consumed session nonce. | System detects duplicate nonce usage and atomically rejects the request (`M04_NONCE_REPLAY`), preventing tampering with already submitted responses. | Replay attempt blocked; security incident logged with client IP and device signature. |
| 9 | M05 Gradebook | Student takes all Advanced Placement (AP) courses and achieves maximum grades (raw weighted GPA 5.000). | System enforces the institutional weighted GPA ceiling rule, clamping the score at exactly 4.500 and visibly printing `GPA_CAPPED` on the official transcript. | Report card and transcript display 4.500 with explanatory policy annotation. |
| 10 | M05 Gradebook | Student fails an AP course (earns letter grade `F` / 0.00 GPA points). | Course credit hours are included in the GPA denominator to reflect failure, and the +1.00 AP course rigor bonus is strictly withheld, preventing inflation of failing grades. | Course marked 0.00 points; rigor bonus withheld; transcript reflects accurate academic standing. |
| 11 | M05 Gradebook | Student's current term percentage drops by 18% compared to rolling 3-term average. | System triggers cognitive drop alert ($\ge 15\%$ decline), suspends public report card release, and routes the profile to the School Psychologist for burnout review. | Report card release held; confidential counseling case opened; Principal notified. |
| 12 | M06 Attendance | Parent attempts to submit a digital medical absence excuse 45 days after the absence date. | System rejects retrospective excuse submission exceeding the 30-day window (`VAL_EXCUSE_EXPIRED`); requires formal School Administrator override to permit late filing. | Parent prompted to contact School Registrar for formal exception review. |
| 13 | M06 Attendance | Biometric gate scanner attempts to submit an identical verification nonce twice. | System rejects duplicate nonce as a replay attempt (`M06_NONCE_REPLAY`), ensuring every physical presence mark represents an authenticated live scan. | Duplicate entry discarded; hardware scanner health check initiated. |
| 14 | M07 Timetable | Timetable generation request creates an overlap for a teacher or room in the same period. | Constraint solver detects hard conflict ($Penalty \ge 1,000$), aborts schedule commit, and returns exact conflict coordinates (day, period, teacher, room). | Administrator presented with conflict visualizer to reassign teacher or classroom. |
| 15 | M07 Timetable | School Administrator attempts to edit or delete a published master timetable. | Published timetable versions are strictly immutable; system rejects direct mutations; modifications require either an emergency substitution or a new published version. | Mutation blocked; prompt suggests launching substitute workflow or drafting version N+1. |
| 16 | M08 Fee Management | Invoice paid 1 day past due date ($m = \lfloor 1/30 \rfloor = 0$). | Family is charged only the standard flat late fee ($25.00); no compound interest is assessed for partial monthly durations, protecting families from unfair charges. | Statement reflects flat fee; zero compound interest; receipt issued upon settlement. |
| 17 | M08 Fee Management | Invoice remains overdue for 800 days with compounding late interest. | Completed months parameter $m$ is capped at 12; compound interest ceases growing; late fee is capped at 25% of balance; account flagged for write-off review. | Accrual stopped; account placed in administrative debt recovery queue. |
| 18 | M09 Financial Mgmt | Journal voucher submitted with debits totaling $10,000.00 and credits $9,999.99. | System rejects voucher with `M09_DEBIT_CREDIT_INVARIANT`, returning exact discrepancy ($0.01$) in error details; zero ledger rows are committed. | Finance Officer prompted to balance entry to the cent before resubmitting. |
| 19 | M09 Financial Mgmt | Academic department reaches 75% expenditure of allocated annual budget. | System automatically triggers a 5% sub-budget reallocation specifically designated for student mental health initiatives, co-managed by the School Psychologist. | Earmarked funds transferred to counseling budget; department head notified of 75% cap. |
| 20 | M10 HR | Employee with 10 days of accrued annual leave requests 14 days of continuous leave. | System rejects request with `M10_INSUFFICIENT_BALANCE`; requires employee to reduce duration or submit an unpaid leave request. | Request blocked; employee portal displays accrued balance and unpaid options. |
| 21 | M10 HR | Employee with 8 days unused annual leave reaches conclusion of fiscal year. | Annual carry-forward policy permits a maximum of 5 days to transfer to next year; the remaining 3 days are forfeited with an immutable audit log entry. | 5 days transferred to next year's opening balance; 3 days forfeited; audit entry logged. |
| 22 | M11 Payroll | Deductions, tax withholding, and loan repayments exceed employee monthly gross pay. | System clamps net pay at exactly $0.00$ (never emits negative salary); unrecovered deduction balance is carried forward to subsequent pay cycle with audit flag. | Pay slip generated at $0.00$; carried deduction balance flagged on subsequent pay run. |
| 23 | M11 Payroll | Administrative attempt to recalculate payroll for a period marked `LOCKED` or `PAID`. | System rejects recalculation attempt (`VAL_PERIOD_LOCKED`); modifications require explicit Super Admin audit override and formal reopening justification. | Mutation blocked; historical disbursement records and tax withholding protected. |
| 24 | M12 Digital Library | Student attempts to stream an e-book without an active, approved digital loan record. | System denies signed stream token generation (`VAL_NO_ACTIVE_LOAN`), enforcing digital rights management and publisher circulation limits. | Token generation rejected; student prompted to place title on digital reserve. |
| 25 | M13 Communication | School Administrator attempts to trigger emergency campus-wide SMS alert. | System blocks immediate dispatch, requiring secondary two-factor authentication (2FA) verification code to prevent accidental or malicious emergency blasts. | Administrator prompted for 2FA code; upon validation, multi-gateway broadcast begins. |
| 26 | M14 Psych Assessment | Teacher or School Administrator attempts to view clinical psychological case notes. | System categorically denies access with 403 Forbidden and logs security violation; clinical notes are decryptable only under active `PSYCHOLOGIST` credentials. | Access blocked; security event logged; no metadata or notes disclosed. |
| 27 | M14 Psych Assessment | Student crisis triage evaluation records a severity score of 9 out of 10. | System triggers high-priority emergency alert, bypassing quiet hours; dispatches instant push notifications to crisis team; prevents case finalization until parent is contacted. | Real-time alerts dispatched; case locked in `UNDER_REVIEW` until parent contact verified. |
| 28 | M15 Transport | School bus GPS telemetry loses connection for 90 consecutive seconds. | Ingestion engine flags telemetry gap exceeding the 60-second limit, alerting dispatch coordinators to verify driver status and vehicle route adherence. | Alert surfaced on dispatch console; automated driver status check triggered. |
| 29 | M16 Cognia Evidence | Evaluator attempts to review an accreditation evidence document that they authored. | System rejects review action (`VAL_SELF_REVIEW_FORBIDDEN`), enforcing strict accreditation separation of duties and eliminating evaluation bias. | Review action blocked; artifact routed to independent evaluator queue. |
| 30 | M17 Platform Admin | Super Admin attempts to reverse suspension on a tenant with open critical security alerts. | System blocks reactivation (`PLT_CRITICAL_ANOMALY`); requires all critical security incidents to be resolved and closed before tenant can return to active status. | Reactivation blocked; prompt displays list of open critical security anomalies. |
| 31 | M18 User & Role Mgmt | Administrator creates custom role with circular inheritance (Role A $\to$ Role B $\to$ Role A). | Role inheritance validation engine detects cycle and aborts creation with `VAL_ROLE_CYCLE`, preventing infinite permission resolution loops. | Role creation rejected; admin prompted to author acyclic role inheritance hierarchy. |
| 32 | M19 Reports & Analytics | Report requested for cohort where initial enrollment count $N_{enrolled\_start} = 0$. | System catches potential divide-by-zero condition in retention formula and rejects parameter set with `VAL_REPORT_PARAMS` instead of crashing pipeline. | Report generation halted with user-friendly error indicating invalid cohort size. |
| 33 | M20 Settings & Config | School Administrator creates configuration change request and attempts to approve it. | Segregation-of-duties engine detects that author matches approver, blocking approval with `VAL_APPROVER_CONFLICT`; requires distinct administrative sign-off. | Approval blocked; notification sent to secondary administrator for independent review. |
| 34 | M20 Settings & Config | Configuration propagation fails midway through fan-out to operational services. | Distributed lock catches failure; system initiates immediate automated rollback to previous active configuration snapshot, emitting rollback alert. | Active configuration restored to pre-change snapshot; administrative failure alert emitted. |

---

## 7. Cross-Module Data Flow & Platform Invariants

### 7.1 Cross-Module Communication Architecture
Within Pillar 1, modules interact through synchronous in-process domain events and validated service interfaces:
- **Zero Direct Cross-Module Database Access**: A module cannot inspect or modify records belonging to another module's domain. Cross-domain interactions occur strictly via published domain contracts.
- **Transactional Outbox & Event Reliability**: State mutations triggering cross-module actions (e.g., student matriculation in M01 creating an invoice in M08) commit the entity state and outbound domain event atomically in a single transaction, guaranteeing event delivery.
- **Fail-Closed Entitlement Enclosure**: If Module A dispatches an event consumed by Module B, but Module B is disabled for that institutional tenant, the event consumer skips processing safely without failing the upstream publisher.

### 7.2 Universal Platform Invariants
1. **Tenant Isolation Invariant**: No query, transaction, background job, or analytical report may execute without an authenticated, immutable `organization_id` tenant parameter.
2. **Clinical Privacy Invariant**: Clinical case notes, psychological diagnoses, and mental health counseling logs are decryptable exclusively by authenticated users holding the `PSYCHOLOGIST` role.
3. **Immutability of Historical Financials & Grades**: Posted general ledger journal vouchers (M09), locked payroll disbursements (M11), and Principal-signed published report cards (M05) cannot be deleted or altered in place. Revisions require formal compensating entries or versioned superseding documents.
4. **Audit Completeness Invariant**: Every administrative action, security privilege grant, grade revision, configuration update, and clinical note access must produce an immutable audit entry retained for a minimum of 7 years, maintaining an Audit Completeness Index $\text{ACI} \ge 99.99\%$.
