# Business Requirements: Computer-Based Exams & Question Banks

**Requirement ID:** BFR-EVAL-002  
**Domain:** Academic Assessment & Evaluation  
**Stakeholders:** Academic Deans, Exam Officers, Department Heads, Subject Instructors, Students  
**Classification:** Pure Business Requirements Specification  

---

## 1. Business Need & Operational Overview

Formal mid-term examinations, end-of-semester finals, and standardized benchmarking tests require a higher tier of security, timing control, and psychometric consistency than standard homework. Testing environments must prevent cheating, scramble questions dynamically, randomize answer choices, enforce strict time windows, and track testing anomalies.

The **Computer-Based Exams & Question Banks** module governs the creation of institutional question repositories, exam session orchestration, secure timed testing environments, and proctoring anomaly monitoring.

---

## 2. Core Business Capabilities & Rules

### 2.1 Institutional Question Banks
- **Question Repository:** Centralized repository of certified test items categorized by Academic Subject, Grade Level, Syllabus Topic, Cognitive Level (Bloom's Taxonomy), and Difficulty Index.
- **Item Types:** Multiple Choice (single/multi-select), Fill-in-the-Blank, Mathematical Equation Matching, Drag-and-Drop Sequencing, Diagram Labeling, and Free-Response Essays.
- **Dynamic Exam Generation:** Instructors can configure an exam template that dynamically draws questions from the bank (e.g., "Select 15 easy questions on Topic A, 10 medium questions on Topic B, and 5 hard questions on Topic C").

### 2.2 Exam Session Orchestration & Timers
- **Strict Time Windows:** Exams define an available testing window (e.g., Friday 9:00 AM – 12:00 PM) and a countdown session timer (e.g., 90 minutes).
- **Automated Submission upon Expiry:** When the countdown timer reaches 00:00, the exam auto-submits all recorded answers immediately.
- **Question & Answer Shuffling:** Questions appear in randomized sequence for each student, and multiple-choice answer options are scrambled to prevent adjacent peer copying.
- **Resilience to Disconnection:** If a student's network disconnects mid-exam, answers are saved locally in the browser; upon reconnecting, the student resumes from their exact saved state without loss of data or unfair time extension.

### 2.3 Security & Proctoring Monitoring
- **Secure Browser Lockout:** Exam client detects tab-switching, secondary monitor usage, copy-paste attempts, and background applications.
- **Proctoring Anomaly Log:** During remote testing, the system logs anomalous behavioral events (browser focus loss, tab change, face out of webcam frame, multiple faces detected) with exact timestamps for proctor review.
- **Special Accommodation Enforcements:** Students with verified IEP accommodations (e.g., +50% extra time, enlarged font display) automatically receive extended exam countdown timers without requiring manual proctor adjustments.

---

## 3. Business Validation Invariants & Edge Cases

| Invariant ID | Business Rule Description | Violation Outcome |
|---|---|---|
| **VAL-EXM-001** | An exam cannot be accessed by a student outside the officially scheduled testing time window. | System displays "Exam Closed" banner and disables entry. |
| **VAL-EXM-002** | Once an exam session has commenced, the countdown timer continues to elapse even if the student closes the browser window. | Prevents students from artificially pausing the exam clock by closing the browser. |
| **VAL-EXM-003** | When an exam session terminates (either manually or via timer expiry), the student's submission status shifts to "Locked" and cannot be reopened without Dean authorization. | Session locked; student barred from editing answers. |

---

## 4. Operational User Workflows

### 4.1 Mid-Term Exam Administration Workflow (Exam Officer & Student)
1. The Exam Officer creates the "Grade 11 Chemistry Mid-Term Exam", scheduled for Thursday at 9:00 AM.
2. The exam is configured to pull 40 randomized items from the certified Chemistry Question Bank with browser lockdown enabled.
3. At 9:00 AM, 60 students enter the testing hall and launch the exam on their laptops.
4. One student accidentally switches tabs to look up a formula; the system immediately flashes a warning banner: *"Warning 1 of 3: Browser focus lost. Event recorded in proctor log."*
5. At 10:30 AM, countdown timers expire, exams auto-submit, and multiple-choice sections are instantly graded.

---

## 5. Business Value & Strategic Impact
- **Rigorous Academic Validity:** Question randomization and bank pooling eliminate test leakage and adjacent peer cheating.
- **Instant Testing Turnaround:** Objective sections are scored instantly, allowing teachers and academic deans to review class score distributions within minutes of exam completion.
- **Fair Accommodations:** Automated accommodation timing guarantees full legal compliance with special needs (IEP) testing mandates.
