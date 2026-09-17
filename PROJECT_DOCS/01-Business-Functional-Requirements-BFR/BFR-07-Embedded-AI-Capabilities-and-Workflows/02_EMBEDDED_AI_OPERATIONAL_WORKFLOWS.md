# Business Requirements: Embedded AI Operational Workflows

**Requirement ID:** BFR-AI-002  
**Domain:** Embedded Artificial Intelligence  
**Stakeholders:** Teachers, Admissions Counselors, Guidance Counselors, Schedulers, Students  
**Classification:** Pure Business Requirements Specification  

---

## 1. Operational Overview

To ensure that AI functions smoothly and transparently within the institution, every embedded AI tool must have clear operational inputs, algorithmic processing rules, human-in-the-loop oversight, and auditable outputs.

This document specifies the operational workflows for the five primary embedded AI engines:
1. **The Conversational Admissions Agent**
2. **The Constraint-Based Timetable Clash Solver**
3. **The Predictive Dropout & Truancy Early-Warning Model**
4. **The Course-Grounded Socratic AI Tutor**
5. **The Automated Rubric Grading Assistant**

---

## 2. Detailed AI Operational Workflows

### 2.1 The Conversational Admissions Agent (RevOps)
```
┌──────────────────┐     ┌───────────────────┐     ┌───────────────────┐     ┌───────────────────┐
│ Parent Inquires  │ ===>│ AI Verifies Age & │ ===>│ AI Books Guided   │ ===>│ CRM Prioritizes   │
│ via WhatsApp/Web │     │ Eligibility Rules │     │ Campus Tour Slot  │     │ Lead for Staff    │
└──────────────────┘     └───────────────────┘     └───────────────────┘     └───────────────────┘
```
1. **Parent Inquiry:** Inquiring family submits a question or initiates chat on the school website at any hour.
2. **Eligibility Screening:** AI asks the prospective student's date of birth and current school grade, verifying institutional age eligibility cutoffs.
3. **Curriculum Matching:** AI answers questions regarding educational tracks (e.g., IB vs AP), tuition fees, extracurricular activities, and bus routes.
4. **Automated Tour Booking:** AI presents available campus tour time slots, confirms parent selection, and transmits calendar invitations.
5. **CRM Prioritization:** Lead record is automatically created in the Admissions CRM, scored for enrollment propensity, and assigned to a counselor.

---

### 2.2 The Timetable Clash Solver Engine (Operations)
```
┌──────────────────┐     ┌───────────────────┐     ┌───────────────────┐     ┌───────────────────┐
│ Input Constraints│ ===>│ AI Evaluates      │ ===>│ Solves Zero Hard  │ ===>│ Scheduler Reviews │
│ (Rooms, Faculty) │     │ Multi-Period Matrix│    │ Clashes (<3 mins) │     │ & Publishes       │
└──────────────────┘     └───────────────────┘     └───────────────────┘     └───────────────────┘
```
1. **Constraint Ingestion:** Ingests faculty maximum teaching loads, course period requirements, student cohort batches, and classroom capacities.
2. **Constraint Satisfaction:** Algorithmic solver iterates across schedule matrices, enforcing zero hard conflicts (no teacher, room, or batch clashes).
3. **Soft Optimization:** Optimizes for pedagogical distribution (math and science scheduled in morning periods, minimizing teacher travel between campus buildings).
4. **Human Review:** The Timetable Scheduler inspects the clash-free schedule heatmap and confirms publication with 1-click.

---

### 2.3 The Predictive Dropout & Truancy Early-Warning Model (Student Care)
```
┌──────────────────┐     ┌───────────────────┐     ┌───────────────────┐     ┌───────────────────┐
│ Ingests Daily    │ ===>│ Detects Multi-Week│ ===>│ Triggers Early    │ ===>│ Counselor Outreach│
│ Attendance & Grds│     │ Negative Trends   │     │ Risk Alert        │     │ & Academic Support│
└──────────────────┘     └───────────────────┘     └───────────────────┘     └───────────────────┘
```
1. **Continuous Data Ingestion:** Model monitors weekly period attendance, homework submission frequency, and weighted assessment scores.
2. **Risk Scoring:** When an enrolled student exhibits a combination of declining attendance (>3 unexcused absences in a month) and falling homework completion (<70%), the student's risk index elevates.
3. **Early Warning Dispatch:** Before the student fails a course or drops out, the system alerts the designated Guidance Counselor: *"Student Alex Rivera flagged for early academic disengagement risk."*
4. **Proactive Intervention:** Counselor schedules an empathetic check-in with the student and family, establishing a targeted academic support plan.

---

### 2.4 The Course-Grounded Socratic AI Tutor (Pedagogy)
```
┌──────────────────┐     ┌───────────────────┐     ┌───────────────────┐     ┌───────────────────┐
│ Student Asks for │ ===>│ AI Verifies Active│ ===>│ Refuses Direct Ans│ ===>│ Student Achieves  │
│ Homework Help    │     │ Course Topic      │     │ Provides Scaffolding│   │ Genuine Mastery   │
└──────────────────┘     └───────────────────┘     └───────────────────┘     └───────────────────┘
```
1. **Student Inquiry:** Student initiates tutoring session for "Grade 10 Chemistry - Stoichiometry".
2. **Curriculum Grounding:** AI queries the student's active course enrollment, verifying that Chapter 5 (Molar Mass) is the current syllabus unit.
3. **Socratic Response:** When the student asks *"What is the answer to problem 3?"*, the AI replies: *"Let's look at the balanced equation first. How many moles of Oxygen do you see on the reactant side?"*
4. **Step-by-Step Scaffolding:** Guides the student through progressive hint ladders until the student derives the correct solution independently.

---

### 2.5 The Automated Rubric Grading Assistant (Assessment)
```
┌──────────────────┐     ┌───────────────────┐     ┌───────────────────┐     ┌───────────────────┐
│ Student Submits  │ ===>│ AI Analyzes Essay │ ===>│ Drafts Rubric &   │ ===>│ Teacher Approves  │
│ Coursework Essay │     │ Against Rubric    │     │ Qualitative Notes │     │ or Overrides Score│
└──────────────────┘     └───────────────────┘     └───────────────────┘     └───────────────────┘
```
1. **Submission Processing:** Student submits a 1,500-word historical analysis essay.
2. **Rubric Evaluation:** AI evaluates the essay text against the teacher's approved 4-tier rubric (Thesis, Historical Accuracy, Textual Evidence, Structure).
3. **Draft Feedback Generation:** AI drafts preliminary rubric category selections and writes paragraph-level constructive suggestions.
4. **Teacher Review Gate:** The instructor opens the speed-grader console, reviews the AI-generated draft, adjusts scores where appropriate, adds personal encouragement, and approves publication.

---

## 3. Business Value & Strategic Impact
- **Transparent Human-in-the-Loop AI:** Guarantees that AI never makes unilateral high-stakes decisions; teachers, deans, and counselors always retain final editorial and grading authority.
- **Proactive Educational Care:** Transforms pastoral care from reactive crisis management to early proactive intervention.
- **Pedagogical Integrity:** Eliminates the student cheating epidemic by enforcing pure Socratic questioning.
