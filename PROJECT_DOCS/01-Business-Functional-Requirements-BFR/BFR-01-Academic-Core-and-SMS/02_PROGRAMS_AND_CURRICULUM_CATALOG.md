# Business Requirements: Programs & Curriculum Catalog

**Requirement ID:** BFR-ACAD-002  
**Domain:** Academic Core & School Operations (SMS)  
**Stakeholders:** Academic Deans, Curriculum Directors, Department Heads, Guidance Counselors  
**Classification:** Pure Business Requirements Specification  

---

## 1. Business Need & Operational Overview

Schools do not simply teach isolated classes; they offer structured curricula, certification tracks, and degree programs designed to meet national standards or international accreditation bodies (e.g., Cambridge IGCSE, International Baccalaureate, American High School Diploma, National Curriculum). 

The **Programs & Curriculum Catalog** module provides the master definition of all educational offerings. It defines overarching Academic Programs, manages the catalog of Subject Courses, tracks credit weights, specifies prerequisite dependencies, and structures sequential **Syllabus Topics** that dictate week-by-week classroom instruction.

---

## 2. Core Business Capabilities & Rules

### 2.1 Academic Programs & Educational Tracks
- **Program Master:** Define institutional educational programs (e.g., "Middle Years Programme", "IB Diploma Programme", "Advanced Placement High School Track").
- **Curricular Requirements:** Every program must specify:
  - Department / Division (Primary, Middle, High School, Vocational).
  - Duration in academic years (e.g., 4-year High School Program).
  - Total credit requirement for graduation (e.g., 24 Credits).
  - Minimum cumulative GPA required for graduation (e.g., 2.0 on 4.0 scale).
  - Mandatory Core Courses versus Elective Course allowances.

### 2.2 Subject Course Catalog
- **Course Master:** Catalog every academic subject (e.g., "Biology 101", "World History", "Algebra II", "Literature & Composition").
- **Course Properties:**
  - Unique Course Code and Course Title.
  - Credit Value (e.g., 1.0 Full Year Credit, 0.5 Semester Credit).
  - Academic Department (Sciences, Humanities, Mathematics, Arts).
  - Course Classification: Mandatory Core, General Elective, Honors, Advanced Placement (AP).
  - Maximum weekly instructional periods (e.g., 5 periods per week).
- **Prerequisite Rules:** Define academic prerequisites (e.g., "Student must pass Algebra I with at least a C before enrolling in Algebra II").

### 2.3 Syllabus Topics & Learning Objectives Catalog
- **Syllabus Breakdown:** Each course must be divided into an ordered sequence of **Syllabus Topics** and Units (e.g., Course "Biology 101" $\to$ Unit 1: "Cellular Structure", Unit 2: "Photosynthesis & Respiration", Unit 3: "Genetics").
- **Topic Attributes:** Each topic defines estimated instructional duration (hours/weeks), pedagogical learning outcomes, core vocabulary, and recommended instructional materials.
- **AI Tutoring Anchor:** This topic hierarchy serves as the mandatory semantic ground truth for the embedded Socratic AI tutor—ensuring AI explanations match the exact topic currently being taught in class.

---

## 3. Business Validation Invariants & Edge Cases

| Invariant ID | Business Rule Description | Violation Outcome |
|---|---|---|
| **VAL-PRG-001** | A course cannot be designated as its own prerequisite or form a circular dependency chain (e.g., Course A requires B, B requires A). | System blocks circular prerequisite assignment and alerts the curriculum director. |
| **VAL-PRG-002** | Total credits of mandatory core courses cannot exceed the total graduation credits of the parent program. | System warns administrator of curricular credit overflow. |
| **VAL-PRG-003** | A course cannot be deleted if active student enrollments, attendance records, or historical grades are linked to it. | System prevents hard deletion; course must be retired/archived instead. |

---

## 4. Operational User Workflows

### 4.1 Curriculum Definition Workflow (Curriculum Lead)
1. The Curriculum Lead creates the program "American High School Track" requiring 24 credits.
2. The Lead creates the course "AP Chemistry", assigning 1.0 credit, science department classification, and prerequisites of "General Chemistry" and "Algebra II".
3. The Lead maps the 8 standard College Board syllabus units into the course topic catalog with expected completion weeks.
4. The Lead publishes the course to the master catalog, making it available for student course scheduling.

---

## 5. Business Value & Strategic Impact
- **Accreditation Alignment:** Directly satisfies international accreditation audits (Cognia, IB, AdvancED) requiring published curriculum frameworks.
- **Student Pathway Transparency:** Provides students and parents with complete clarity on graduation requirements and prerequisite paths.
- **Pedagogical Alignment:** Ensures all sections of the same subject across different teachers follow the identical master syllabus.
