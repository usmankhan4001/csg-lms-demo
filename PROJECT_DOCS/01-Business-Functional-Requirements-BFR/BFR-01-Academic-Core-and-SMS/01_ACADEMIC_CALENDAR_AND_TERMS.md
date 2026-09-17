# Business Requirements: Academic Calendar & Terms

**Requirement ID:** BFR-ACAD-001  
**Domain:** Academic Core & School Operations (SMS)  
**Stakeholders:** Academic Deans, School Principals, Registrars, Department Heads  
**Classification:** Pure Business Requirements Specification  

---

## 1. Business Need & Operational Overview

In any physical, hybrid, or online school, time is the foundational coordinate for all institutional operations. Without a structured academic calendar, an institution cannot define when classes begin and end, when attendance is mandatory, when exams take place, or when students progress to the next grade level.

The **Academic Calendar & Terms** module establishes the authoritative institutional timeline. It allows school administrators to configure multi-year academic cycles, partition school years into grading terms (semesters, trimesters, or quarters), define instructional days versus institutional holidays, and enforce term closure boundaries that lock finalized grades.

---

## 2. Core Business Capabilities & Rules

### 2.1 Multi-Year Academic Year Management
- **Academic Year Definition:** The institution must define multi-year cycles (e.g., "Academic Year 2026–2027") with explicit start and end dates.
- **Lifecycle States:** An Academic Year progresses through four distinct business states:
  - `Planning`: The calendar is being designed; courses, terms, and holidays are being configured. Student enrollments cannot yet be finalized.
  - `Active`: The official school year is underway. Daily attendance, timetables, and lesson delivery are operational. Only one Academic Year can be active per campus at any given time.
  - `Completed`: Instructional days have concluded; all final grades, report cards, and promotions are finalized. Data becomes read-only for standard users.
  - `Archived`: Historical record preserved permanently for state transcripts, audits, and alumni verification.

### 2.2 Academic Terms & Grading Periods
- **Term Partitioning:** Each Academic Year must be subdivided into discrete operational terms based on institutional policy:
  - *Semester Model:* Fall Term, Spring Term, Optional Summer Term.
  - *Trimester Model:* Term 1, Term 2, Term 3.
  - *Quarter Model:* Quarter 1, Quarter 2, Quarter 3, Quarter 4.
- **Term Attributes:** Every term must specify its start date, end date, course enrollment deadline, mid-term evaluation window, final examination week, and grade submission deadline.
- **Term Grade Locking:** Upon official term closure by the Academic Dean, teacher gradebooks for that term are automatically locked against further edits. Any subsequent grade changes require an audited administrative override.

### 2.3 Calendar Events, Holidays & Bell Schedule Profiles
- **Calendar Event Types:** Administrators can schedule institution-wide calendar events:
  - *Instructional Days:* Standard school days where attendance is mandatory.
  - *Official Holidays / Vacations:* Winter break, spring recess, national/religious holidays where school is closed and attendance is suspended.
  - *Professional Development Days:* Faculty training days where students have no classes.
  - *Examination Windows:* Designated testing periods with custom scheduling rules.
  - *Emergency Closure Days:* Weather emergencies, health closures, or unforeseen cancellations with automated notification to families.

---

## 3. Business Validation Invariants & Edge Cases

| Invariant ID | Business Rule Description | Violation Outcome |
|---|---|---|
| **VAL-CAL-001** | Term date ranges must fall strictly within the start and end dates of the parent Academic Year. | Creation rejected; system prompts administrator to adjust dates. |
| **VAL-CAL-002** | Consecutive terms within the same academic track cannot have overlapping instructional date ranges. | System flags overlapping dates and prevents activation. |
| **VAL-CAL-003** | Only one Academic Year may hold the `Active` status per campus or academic program at any given time. | Activating a new year requires formal archival of the previous active year. |
| **VAL-CAL-004** | An Academic Term cannot be closed if there are pending, ungraded assessment results or unapproved grade changes. | System generates a pre-closure audit report blocking closure until all grades are submitted. |

---

## 4. Operational User Workflows

### 4.1 Annual Calendar Setup Workflow (Registrar / Dean)
1. The Academic Dean navigates to the Academic Calendar portal and creates "Academic Year 2026–2027" in `Planning` status.
2. The Dean configures the terms: "Fall Semester" (Aug 25 – Dec 18) and "Spring Semester" (Jan 10 – May 28).
3. The Dean bulk-imports national holidays and school breaks from a regional calendar template.
4. Once faculty assignments and course schedules are linked, the Dean executes the "Activate Academic Year" command on the first day of school.

---

## 5. Business Value & Strategic Impact
- **Operational Predictability:** Provides teachers, parents, and students with an authoritative, single source of truth for the entire school year.
- **Statutory Compliance:** Automatically calculates and verifies total state-mandated instructional hours (e.g., 180 school days).
- **Audit Integrity:** Enforces tamper-evident grade locking at the end of each academic term, eliminating retroactive grade tampering.
