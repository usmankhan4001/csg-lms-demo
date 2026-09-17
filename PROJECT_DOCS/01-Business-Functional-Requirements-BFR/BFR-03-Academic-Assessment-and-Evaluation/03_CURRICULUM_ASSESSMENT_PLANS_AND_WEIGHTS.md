# Business Requirements: Curriculum Assessment Plans & Weighted Grading

**Requirement ID:** BFR-EVAL-003  
**Domain:** Academic Assessment & Evaluation  
**Stakeholders:** Academic Deans, Department Heads, Subject Teachers, Students, Parents  
**Classification:** Pure Business Requirements Specification  

---

## 1. Business Need & Operational Overview

In an enterprise academic institution, a student's final course grade is never a simple raw average of test scores. Educational accreditation standards dictate that student learning must be evaluated through a structured, transparent **Assessment Plan** that balances **Formative Assessment** (continuous homework, quizzes, class participation) and **Summative Assessment** (mid-term exams, term papers, comprehensive final exams) using weighted percentages.

The **Curriculum Assessment Plans & Weighted Grading** module connects LearnHouse coursework tasks and computer-based exams to the institution's official grading formulas, calculating continuous student mastery and automated term grades.

---

## 2. Core Business Capabilities & Rules

### 2.1 The Course Assessment Plan Architecture
- **Plan Definition:** Every course in an active academic term must have an approved Assessment Plan (e.g., "AP Biology Assessment Plan - Fall 2026").
- **Weighted Criteria Breakdown:** The plan divides 100% total course weight across specific assessment categories:
  - *Homework & Classwork:* e.g., 15% of final grade.
  - *Quizzes & Formative Checkpoints:* e.g., 15% of final grade (optionally dropping the lowest single quiz score).
  - *Laboratory Practicals & Group Projects:* e.g., 20% of final grade.
  - *Mid-Term Examination:* e.g., 20% of final grade.
  - *Final Comprehensive Examination:* e.g., 30% of final grade.
  - **Total Weight Invariant:** The sum of all category weight percentages must equal exactly 100%.

### 2.2 Mathematical Grade Formulation
- **Category Score Aggregation:** The system calculates the percentage score for each category $c$:
  $$\text{Category Score } S_c = \frac{\sum \text{Points Earned in Category } c}{\sum \text{Max Points in Category } c} \times 100$$
- **Weighted Term Composite Grade:**
  $$\text{Final Course Grade } G = \sum_{c=1}^{n} \left( S_c \times \frac{\text{Weight}_c}{100} \right)$$
- **Handling Ungraded Items:** Formative practice tasks marked as "Ungraded" are excluded from category weight calculations.

### 2.3 Assessment Plan Approval & Locking
- **Curriculum Governance:** Teachers draft their assessment plans at the start of the term; plans require formal digital sign-off from the Department Head.
- **Mid-Term Modification Lock:** Once students have submitted graded work under an approved plan, category weights cannot be modified without an audited administrative override by the Academic Dean to prevent retroactive grading bias.

---

## 3. Business Validation Invariants & Edge Cases

| Invariant ID | Business Rule Description | Violation Outcome |
|---|---|---|
| **VAL-PLN-001** | The sum of all category percentage weights in an Assessment Plan must equal exactly 100.0%. | Plan submission blocked; system displays category percentage mismatch. |
| **VAL-PLN-002** | Every graded assignment, quiz, or exam must be explicitly mapped to one valid category in the active course Assessment Plan. | Assignment publication blocked until category is designated. |
| **VAL-PLN-003** | When a course Assessment Plan is modified mid-term via Dean override, all historical student composite scores must be recalculated automatically. | System recalculates cohort grade tallies and logs the audit event. |

---

## 4. Operational User Workflows

### 4.1 Assessment Plan Setup Workflow (Department Head & Teacher)
1. At the start of the semester, the Grade 10 English Teacher submits the assessment weighting proposal: Homework (20%), Essays (30%), Reading Quizzes (20%), Final Exam (30%).
2. The English Department Head reviews the plan, confirms it aligns with institutional departmental standards, and clicks "Approve Plan".
3. The Assessment Plan is locked. All 25 subsequent English assignments published throughout the semester automatically feed into their respective weighting buckets.
4. Students and parents view their real-time weighted grade breakdown at any point in the semester.

---

## 5. Business Value & Strategic Impact
- **Absolute Grade Transparency:** Eliminates student and parent grading disputes by providing a clear, mathematically defensible breakdown of how final grades are calculated.
- **Cognia / Accreditation Compliance:** Fully complies with international accreditation mandates requiring transparent, multi-criteria assessment frameworks.
- **Continuous Academic Monitoring:** Real-time weighted composites alert guidance counselors to academic struggles months before final report cards are issued.
