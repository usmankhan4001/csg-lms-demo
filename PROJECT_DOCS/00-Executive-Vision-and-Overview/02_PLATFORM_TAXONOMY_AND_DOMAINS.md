# Platform Taxonomy & The Four Core Operational Domains

**Document Reference:** CSG-EXEC-002  
**Classification:** Business Architecture Taxonomy  
**Version:** 2.0.0  

---

## 1. Deconstruction of Legacy Fragmentation

Earlier system architectures fragmented platform specifications into 50 granular modules and three arbitrary technical pillars. An objective systems analysis reveals that this fragmentation created severe operational blind spots:
- Cross-cutting technical plumbing (such as WebSockets, Redis session managers, and LLM routers) was erroneously treated as standalone business modules.
- Natural functional twins (such as Assignments, Exams, and Gradebooks) were split into disconnected silos.
- The central academic master backbone (Academic Years, Terms, Programs, Courses, Campuses, Classrooms, Cohorts, and Rosters) was completely omitted.

To achieve enterprise-grade institutional cohesion, CSG-LMS consolidates all capabilities into **Four Business Operational Domains**, supported by a **Cross-Cutting AI & Platform Foundation Layer**.

---

## 2. The Four Business Operational Domains

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                   CSG-LMS FOUR BUSINESS OPERATIONAL DOMAINS                            │
├────────────────────────────┬────────────────────────────┬──────────────────────────────────────────────┤
│ DOMAIN 1: ACADEMIC CORE    │ DOMAIN 2: CURRICULUM,      │ DOMAIN 3: ADMISSIONS, CRM    │
│ & SCHOOL OPERATIONS (SMS)  │ LEARNING & EVALUATION (LMS)│ & REVOPS                     │
│ • Academic Years & Terms   │ • Course & Chapter Delivery│ • Omnichannel Lead Intake    │
│ • Programs & Courses       │ • Interactive Content Blks │ • Lead Scoring & Nurturing   │
│ • Syllabus Topics Catalog  │ • Real-time Collab Boards  │ • Campus Tour Scheduling     │
│ • Campuses & Classrooms    │ • Learning Trails & Badges │ • Entrance Exam Evaluation   │
│ • Student Master Records   │ • Multi-Task Assignments   │ • Admissions Offer Letters   │
│ • Family & Custody Network │ • Computer-Based Exams     │ • Automated Matriculation    │
│ • Cohorts & Class Batches  │ • Weighted Assessment Plans│   Handshake into SMS Core    │
│ • Timetable Matrix Engine  │ • Standardized Grade Scales│                              │
│ • Period Batch Attendance  │ • Official Report Cards    │ DOMAIN 4: INSTITUTIONAL      │
│ • Student Behavioral Logs  │ • Transcripts & Records    │ ADMINISTRATION & FINANCE     │
│                            │                            │ • Itemized Fee Structures    │
│                            │                            │ • Term Installment Plans     │
│                            │                            │ • Staff HR & Contracts       │
│                            │                            │ • Monthly Payroll Engine     │
│                            │                            │ • Transport Fleet Management │
│                            │                            │ • Cognia Accreditation & AMI │
├────────────────────────────┴────────────────────────────┴──────────────────────────────────────────────┤
│ 🛠️ SHARED PLATFORM FOUNDATION & EMBEDDED ARTIFICIAL INTELLIGENCE:                                      │
│ • Dynamic RBAC & Custom Role Governance (Zero Hardcoded Personas)                                      │
│ • High-Throughput Application-Level Multi-Tenancy (Zero PostgreSQL RLS Overhead)                       │
│ • Embedded Business AI: Admissions Conversational Agent, Timetable Clash Solver,                       │
│   Predictive Dropout Early-Warning Model, Course-Grounded Socratic Tutor, Formative Rubric Assistant  │
└────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Domain Responsibility & Boundary Matrix

### Domain 1: Academic Core & School Operations (SMS Core)
- **Primary Stakeholders:** School Principals, Academic Deans, Registrars, Homeroom Teachers, Campus Facilities Coordinators.
- **Mandate:** Establishes the institutional reality of the school. Owns multi-year academic calendars, curriculum programs, course catalog, campus facilities, physical classrooms, student demographic masters, family custody trees, batch sections, master timetables, and period-by-period attendance tracking.

### Domain 2: Curriculum Delivery, Learning & Evaluation (LMS & Assessment)
- **Primary Stakeholders:** Subject Teachers, Department Heads, Students, Curriculum Developers.
- **Mandate:** Manages the pedagogical interaction between teachers and students. Built upon the LearnHouse foundation, it delivers rich multimedia course chapters, interactive collaborative whiteboards (`BOARD`), assignments with automated grading, timed secure examinations, curriculum-weighted continuous assessment plans, official term report cards, and academic transcripts.

### Domain 3: Admissions, CRM & RevOps
- **Primary Stakeholders:** Admissions Directors, Marketing Teams, Prospective Parents, Academic Evaluation Panels.
- **Mandate:** Manages the student acquisition journey from initial marketing inquiry to enrollment. Features 24/7 conversational lead qualification, campus tour booking, entrance examination scoring, and automated **Matriculation**—instantly converting accepted applicants into permanent student records, assigning cohorts, and generating tuition billing.

### Domain 4: Institutional Administration, Finance & Compliance
- **Primary Stakeholders:** Chief Financial Officers, Bursars, Human Resources Managers, Transport Directors, Accreditation Coordinators.
- **Mandate:** Ensures institutional sustainability, fiscal health, and regulatory compliance. Manages multi-category fee structures (Tuition, Lab, Bus, Caution), term installment schedules, automated invoicing, faculty employment contracts, payroll generation, transport bus fleet routes, and continuous Cognia accreditation evidence assembly.
