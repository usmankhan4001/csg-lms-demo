# Business Requirements: Cohorts, Batches & Two-Tier Enrollment

**Requirement ID:** BFR-ACAD-005  
**Domain:** Academic Core & School Operations (SMS)  
**Stakeholders:** Academic Deans, Registrars, Homeroom Teachers, Subject Instructors, Students  
**Classification:** Pure Business Requirements Specification  

---

## 1. Business Need & Operational Overview

In any functioning school, students do not float independently; they belong to specific class cohorts (e.g., "Grade 10 - Section A - Class of 2029") under the care of a designated Homeroom Teacher. Furthermore, to participate in classes, students require a **Two-Tier Enrollment** model:
1. **Tier 1 (Program Matriculation):** Official institutional enrollment in an academic program for the school year (e.g., enrolled in "High School Diploma, Grade 10" for 2026–2027).
2. **Tier 2 (Course Enrollment):** Registration in specific subject courses for the active term (e.g., enrolled in Biology 101, World History, and Algebra II).

The **Cohorts, Batches & Two-Tier Enrollment** module governs cohort grouping and generates the official student rosters that drive daily attendance, gradebooks, and timetable schedules.

---

## 2. Core Business Capabilities & Rules

### 2.1 Student Batches & Class Sections
- **Batch Definition:** A batch represents an administrative cohort of students progressing through a grade level together (e.g., "Grade 9-A", "Grade 9-B", "Year 12 Science").
- **Batch Master Attributes:**
  - Associated Academic Program and Grade Level.
  - Designated **Class Teacher / Homeroom Mentor** responsible for cohort pastoral care, daily morning roll call, and parent conferences.
  - Designated **Physical Homeroom** (primary classroom base).
  - Maximum student cohort capacity (e.g., 25 students).

### 2.2 Tier 1: Program Matriculation (Institutional Standing)
- **Program Matriculation Record:** Binds a student to an approved Academic Program and Academic Year.
- **Matriculation Lifecycle:**
  - `Matriculated`: Student is formally accepted and assigned to an academic grade cohort.
  - `Active`: Student is currently studying in the program.
  - `Promoted`: Student has successfully completed the year's credits and rolled over to the next grade.
  - `Retained / Repeating`: Student has not met academic standards and must repeat the grade level.
  - `Completed / Graduated`: Student has fulfilled all graduation requirements.

### 2.3 Tier 2: Course Enrollment (Subject Rosters)
- **Course Enrollment Record:** Registers an active student into a specific subject course for a specific term and batch (e.g., John Doe is enrolled in "Physics 101, Section A, Fall 2026").
- **Enrollment Classifications:**
  - `Standard Enrolled`: Regular student taking the course for credit and grade.
  - `Audit`: Student attending for enrichment without earning academic credit.
  - `Dropped / Withdrawn`: Student removed from the course prior to withdrawal cutoffs.
  - `Incomplete`: Extended deadline granted for medical or extraordinary reasons.
- **Automated Roster Generation:** Active course enrollments automatically generate the official student rosters that populate teacher gradebooks, live virtual classrooms, and assignment submission portals.

---

## 3. Business Validation Invariants & Edge Cases

| Invariant ID | Business Rule Description | Violation Outcome |
|---|---|---|
| **VAL-ENR-001** | A student cannot enroll in a Tier 2 course unless they hold an active Tier 1 Program Matriculation for that academic term. | Course enrollment blocked; registrar must complete program matriculation first. |
| **VAL-ENR-002** | A student cannot enroll in an advanced course without having verified passing grades in all prerequisite courses. | Enrollment blocked by academic prerequisite check; requires Dean's manual waiver. |
| **VAL-ENR-003** | Total enrolled students in a batch or course section cannot exceed the maximum batch capacity or the assigned room capacity. | System flags section overflow and prompts registrar to open a new section. |

---

## 4. Operational User Workflows

### 4.1 End-of-Year Mass Promotion Workflow (Registrar)
1. At the end of the academic year, the Registrar opens the **Mass Promotion Tool**.
2. The system evaluates all students in "Grade 9-A" against minimum passing credits and GPA thresholds.
3. 24 of 25 students meet graduation criteria and are queued for promotion into "Grade 10-A" for the upcoming Academic Year.
4. One student with deficient credits is flagged for summer school remediation.
5. Upon administrative confirmation, the system creates the next-year Tier 1 Program Matriculations and assigns homeroom teachers.

---

## 5. Business Value & Strategic Impact
- **Operational Clarity:** Homeroom and subject teachers always have clean, unambiguous rosters of participating students.
- **Audit-Proof Cohort Records:** Maintains an unbroken historical paper trail of every grade cohort and course enrollment for transcript generation and state reporting.
- **Automated Promotion:** Replaces weeks of manual spreadsheet data-entry with a streamlined, 1-click cohort progression engine.
