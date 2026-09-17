# Business Requirements: Assignments & Submission Tasks

**Requirement ID:** BFR-EVAL-001  
**Domain:** Academic Assessment & Evaluation  
**Stakeholders:** Subject Teachers, Teaching Assistants, Students, Academic Advisors  
**Classification:** Pure Business Requirements Specification (LearnHouse Foundation Revamped)  

---

## 1. Business Need & Operational Overview

Continuous formative coursework, homework, lab reports, and coding exercises are essential to reinforce classroom learning and assess ongoing student understanding. Instructors need a versatile assignment engine that supports diverse task types (from essay submissions to auto-graded code and mathematics), enforces academic integrity (anti-plagiarism, anti-copy-paste), and automates grading workflows.

The **Assignments & Submission Tasks** module, built upon the **LearnHouse Assignment & Task** architecture, governs the creation, scheduling, student submission, plagiarism checking, and grading of coursework assignments.

---

## 2. Core Business Capabilities & Rules

### 2.1 The LearnHouse Multi-Task Assignment Architecture
An assignment consists of an overarching envelope configuring grading rules, containing one or more specialized tasks:
- **Assignment Envelope (`ASSIGNMENT`):**
  - Title, instructional prompt, and associated Course/Chapter.
  - Due date, late submission cutoff grace period, and late penalty percentage rules.
  - Grading Type: Alphabetical (A–F), Numeric (0–100), Percentage, Pass/Fail, or GPA Scale.
  - Solution Reveal Rules: `Never`, `On Submission`, or `After Teacher Grading`.
  - Retry Policy: Maximum permitted submission attempts and pass threshold percentage.
- **Assignment Tasks (`ASSIGNMENT_TASK`):**
  - *File Submission:* Essays, research papers, lab spreadsheets, or art portfolios (PDF, Word, Images, Zip).
  - *Quiz / Form:* Multiple choice, multi-select, and short-answer prompts with auto-evaluation.
  - *Code Task:* Programming challenge evaluated against automated unit test suites.
  - *Number / Math Answer:* Mathematical calculation verified against numerical tolerance intervals.

### 2.2 Academic Integrity & Anti-Cheating Controls
- **Anti-Copy-Paste Guard:** Configurable setting that prevents pasting external text directly into writing prompts, forcing students to type their own responses.
- **Automated Plagiarism & Similarity Detection:** Submissions are automatically scanned against internet sources, previous student cohort archives, and external academic repositories to generate a Similarity Index score.
- **AI-Generated Text Detection:** Evaluates student essay text for AI syntactical markers, alerting the instructor to potential unacknowledged AI generation.

### 2.3 Grading & Feedback Workflow
- **Auto-Grading Engine:** Automatically scores quizzes, mathematical answers, and code unit tests upon submission, providing instant feedback.
- **Manual Rubric Grading:** For essays and open-ended projects, teachers evaluate submissions using standardized, multi-criteria rubrics.
- **Rich Qualitative Feedback:** Instructors attach inline annotations, text comments, audio voice feedback, and rubric performance breakdowns.

---

## 3. Business Validation Invariants & Edge Cases

| Invariant ID | Business Rule Description | Violation Outcome |
|---|---|---|
| **VAL-ASN-001** | Submissions received after the due date must be marked as "Late" and apply the configured late penalty deduction. | System calculates late score penalty and displays late flag to instructor. |
| **VAL-ASN-002** | A student cannot submit an assignment if their total submission attempts have reached the configured maximum retry limit. | Submission upload disabled; student informed that attempt limit is exhausted. |
| **VAL-ASN-003** | Auto-graded tasks cannot reveal solution keys to students until after the assignment's final due date has passed for the entire class. | Solution visibility gated until class-wide deadline expires. |

---

## 4. Operational User Workflows

### 4.1 Homework Submission & Grading Workflow (Student & Teacher)
1. A Grade 10 English student opens the "Literary Analysis: The Great Gatsby" assignment on their student portal.
2. The student reviews the 4-tier rubric (Thesis, Textual Evidence, Analysis, Mechanics) and uploads their 1,200-word essay.
3. The plagiarism checker processes the document, reporting an acceptable 4% similarity score.
4. The English teacher opens the speed-grader console, highlights two paragraphs with inline comments, selects rubric criteria, and awards 92/100.
5. The student and their parents receive a notification that the graded assignment and feedback are published.

---

## 5. Business Value & Strategic Impact
- **Significant Teacher Time Savings:** Automated grading of quizzes and code tasks frees teachers to focus on qualitative student mentoring.
- **Academic Integrity Protection:** Robust anti-plagiarism and copy-paste prevention protect institutional academic honesty standards.
- **Transparent Feedback Loops:** Clear rubric criteria eliminate student confusion over how their coursework is evaluated.
