# Business Requirements: Timetable & Course Scheduling Matrix

**Requirement ID:** BFR-ACAD-006  
**Domain:** Academic Core & School Operations (SMS)  
**Stakeholders:** Academic Deans, Timetable Schedulers, Department Heads, Faculty, Students  
**Classification:** Pure Business Requirements Specification  

---

## 1. Business Need & Operational Overview

Building an institutional timetable for a school with hundreds of students, dozens of teachers, and limited specialized classrooms is one of the most complex operational challenges in education. A single scheduling clash (e.g., a teacher assigned to two classes simultaneously, or a chemistry lab double-booked) disrupts entire school days. Furthermore, unexpected faculty illness requires immediate, seamless substitute teacher coverage.

The **Timetable & Course Scheduling Matrix** module manages the master weekly schedule. It balances institutional constraints across five dimensions: **Subject Course + Student Batch + Instructor + Physical Room + Time Slot**, while providing an automated **Emergency Substitution Assistant** for daily operational resilience.

---

## 2. Core Business Capabilities & Rules

### 2.1 The Master Scheduling Matrix
- **Five-Dimensional Scheduling Unit:** Every scheduled class slot is defined by:
  1. *Subject Course:* The academic curriculum unit being delivered.
  2. *Student Batch / Section:* The cohort attending the class.
  3. *Assigned Instructor:* The qualified faculty member leading the lesson.
  4. *Physical / Virtual Room:* The assigned classroom, science lab, or live video room.
  5. *Time Slot:* The day of the week and bell schedule period index (e.g., Monday, Period 3, 10:15 AM – 11:00 AM).

### 2.2 Hard & Soft Scheduling Constraints
- **Hard Constraints (Zero-Tolerance Violations):**
  - *No Teacher Clash:* An instructor cannot be scheduled to teach two different classes at the same time.
  - *No Room Clash:* A physical classroom or laboratory cannot be assigned to two classes simultaneously.
  - *No Batch Clash:* A student cohort cannot be scheduled for two concurrent subjects.
  - *Room Capacity Enforcement:* Enrolled student count cannot exceed physical room seating capacity.
  - *Specialized Room Requirement:* Science labs and art studios can only host subjects designated as requiring those spaces.
- **Soft Constraints (Optimization Targets):**
  - *Teacher Workload Balance:* Instructors should not exceed their contractual maximum teaching periods per week (e.g., max 22 periods/week).
  - *Cognitive Period Distribution:* Heavy academic subjects (e.g., Advanced Mathematics, Physics) are prioritized for morning periods rather than late afternoon periods.
  - *Minimizing Room Moves:* Teachers and cohorts should have minimized physical travel between distant buildings during the day.

### 2.3 Daily Emergency Teacher Substitution Assistant
- **Sick Leave & Absence Coverage:** When a faculty member reports unplanned absence:
  1. The system identifies all affected timetable slots for that day.
  2. Evaluates available, on-campus teachers who are free during those specific periods and qualified in the subject department.
  3. Recommends the optimal substitute teacher and alerts the Academic Dean for 1-click confirmation.
  4. Automatically updates the daily schedule, reassigns live classroom host rights, and notifies students and parents via push notification.

---

## 3. Business Validation Invariants & Edge Cases

| Invariant ID | Business Rule Description | Violation Outcome |
|---|---|---|
| **VAL-SCH-001** | Publication of an academic timetable is strictly barred if any hard constraint violation (teacher, room, or batch clash) exists. | System refuses publication; displays clash inspection report highlighting conflicts. |
| **VAL-SCH-002** | An emergency substitute teacher cannot be assigned to a slot if they already have an active teaching or proctoring assignment during that period. | Substitute selection disabled for that instructor. |
| **VAL-SCH-003** | Faculty weekly teaching loads cannot exceed contractual maximum limits without an audited administrative compensation override. | System warns scheduler of teacher overload condition. |

---

## 4. Operational User Workflows

### 4.1 Automated Timetable Generation Workflow (Scheduler)
1. The Timetable Scheduler inputs teacher availability rules, course weekly period requirements, and room capacities for the upcoming semester.
2. The scheduler runs the **AI Timetable Clash Solver Engine**.
3. The engine computes an optimal, conflict-free matrix across 45 teachers, 30 rooms, and 400 timetable slots in less than 3 minutes.
4. The scheduler reviews teacher gap distributions, makes minor manual adjustments, and clicks "Publish Master Timetable".
5. Student and faculty personal schedules on web and mobile apps update immediately.

---

## 5. Business Value & Strategic Impact
- **Administrative Time Savings:** Cuts institutional timetable generation time from weeks of manual spreadsheet trial-and-error down to minutes.
- **Zero Classroom Downtime:** The emergency substitution tool eliminates morning chaos when teachers fall ill, ensuring classes are covered seamlessly.
- **Optimized Faculty Well-being:** Enforces balanced teacher workload distribution, preventing teacher burnout and scheduling grievances.
