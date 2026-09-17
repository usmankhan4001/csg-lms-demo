# Business Requirements: Gradebook, Report Cards & Transcripts

**Requirement ID:** BFR-EVAL-004  
**Domain:** Academic Assessment & Evaluation  
**Stakeholders:** School Principals, Academic Deans, Registrars, Teachers, Students, Parents  
**Classification:** Pure Business Requirements Specification  

---

## 1. Business Need & Operational Overview

The culmination of an academic term is the compilation of the official **Gradebook**, the generation of formal **Term Report Cards**, and the maintenance of the permanent **Academic Transcript**. These documents are legal academic credentials that represent the student's institutional standing, determine honor roll recognition, govern athletic eligibility, and serve as the basis for university admissions.

The **Gradebook, Report Cards & Transcripts** module converts continuous course assessment results into standardized letter grades, computes cumulative Grade Point Averages (GPA), manages teacher narrative commentary, and produces official, tamper-evident academic records.

---

## 2. Core Business Capabilities & Rules

### 2.1 Standardized Institutional Grading Scales
- **Grading Scale Configuration:** The institution defines master grading scale conversion matrices:
  - *Standard 4.0 Scale:* Letter Grade, Percentage Interval, Grade Point Value (e.g., A+ = 97–100% / 4.0, A = 93–96% / 4.0, B = 83–86% / 3.0, F = <60% / 0.0).
  - *Weighted Honors / AP Scale:* Provides weighted grade point bumps (e.g., AP course A = 5.0 GPA value) to reward advanced coursework rigor.
  - *Standards-Based Mastery Scale:* Exemplary, Proficient, Developing, Emerging.

### 2.2 Cumulative Grade Point Average (GPA) Formulation
- **Term GPA Computation:**
  $$\text{Term GPA} = \frac{\sum (\text{Course Grade Point} \times \text{Course Credits})}{\sum \text{Total Course Credits Attempted}}$$
- **Cumulative Longitudinal GPA:** Computed across all completed terms and academic years to track the student's permanent high school academic standing.
- **Class Rank & Honor Roll:** Automated calculation of cohort decile rankings, Valedictorian/Salutatorian candidates, and Dean's Honor Roll distinctions.

### 2.3 Official Term Report Cards
- **Report Card Elements:**
  - Student Legal Name, Student ID, Grade Level, Batch/Section, Homeroom Teacher.
  - Course-by-course breakdown: Subject, Credit Value, Teacher Name, Numerical Score, Letter Grade.
  - Attendance Summary: Days Present, Days Absent (Excused vs Unexcused), Times Tardy.
  - Teacher Narrative Evaluations: Qualitative strengths, areas for academic growth, and behavioral comments.
  - Principal Signature and Institutional Embossed Seal.
- **Publication & Parent Sign-Off:** Digital publication via the Parent Portal with automated read-receipt tracking and parent electronic acknowledgment.

### 2.4 Official Academic Transcripts & Permanent Records
- **Longitudinal Transcript:** Cumulative chronological summary of all courses taken, credits attempted versus earned, term-by-term GPAs, standardized test scores (SAT/ACT/AP), and graduation status.
- **Tamper-Evident Digital Security:** Printable official transcripts feature unique verification QR codes, document UUIDs, and digital watermarks to prevent forgery during university admissions audits.

---

## 3. Business Validation Invariants & Edge Cases

| Invariant ID | Business Rule Description | Violation Outcome |
|---|---|---|
| **VAL-GRD-001** | Report cards cannot be generated or published while any course taken by the student has an unsubmitted final grade. | System blocks report card generation; highlights pending teacher grade submissions. |
| **VAL-GRD-002** | Once an Academic Term is formally closed, all grades on that term's report card become read-only. | Grade editing locked; any retrospective correction requires an audited Dean override. |
| **VAL-GRD-003** | Courses marked with "Incomplete" (due to illness) do not factor into cumulative GPA until resolved into a final letter grade within the institution's 30-day grace period. | GPA calculation temporarily excludes incomplete credit weights. |

---

## 4. Operational User Workflows

### 4.1 End-of-Term Report Card Generation Workflow (Dean & Registrar)
1. At the end of the Fall Semester, the Academic Dean reviews the Gradebook Submission Console.
2. All 65 teachers have submitted finalized grades across 240 course sections.
3. The Dean clicks "Lock Term Grades" and authorizes report card generation.
4. The system compiles report cards for all 850 students, computing term GPAs and honor rolls in under 2 minutes.
5. Parents receive a notification: *"Your student's official Fall 2026 Report Card is now available for review in the Parent Portal."*

---

## 5. Business Value & Strategic Impact
- **Flawless University Admissions Readiness:** Transcripts meet the highest global secondary school standards, guaranteeing acceptance by international credential evaluators.
- **Elimination of Administrative Bottlenecks:** Replaces weeks of manual paper report card collation with an automated, 1-click digital distribution engine.
- **Holistic Student Evaluation:** Marries quantitative GPA metrics with rich qualitative teacher narratives, giving families a comprehensive picture of student growth.
