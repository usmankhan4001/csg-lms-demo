# Business Requirements: Daily Attendance & Student Behavioral Logs

**Requirement ID:** BFR-ACAD-007  
**Domain:** Academic Core & School Operations (SMS)  
**Stakeholders:** Homeroom Teachers, Subject Instructors, Deans of Students, Attendance Officers, Parents  
**Classification:** Pure Business Requirements Specification  

---

## 1. Business Need & Operational Overview

Accurate attendance tracking is both a legal statutory requirement and a core pillar of student safety and academic accountability. Schools must track both daily homeroom attendance and period-by-period subject attendance. Furthermore, student conduct, commendations, counselor interactions, and disciplinary infractions must be recorded in an immutable institutional log to support pastoral care and parent-teacher alignment.

The **Daily Attendance & Student Behavioral Logs** module governs the recording, verification, and reporting of student presence, while maintaining the official **Student Incident Book** for behavioral tracking.

---

## 2. Core Business Capabilities & Rules

### 2.1 Multi-Mode Attendance Tracking
- **Two-Tier Attendance Model:**
  - *Daily Homeroom Attendance:* Taken during morning registration by the Homeroom Teacher (satisfies official state statutory attendance reporting).
  - *Period-by-Period Subject Attendance:* Taken at the start of each instructional class by the subject teacher (verifies classroom presence and identifies class-skipping).
- **Attendance Status Classifications:**
  - `Present`: Student is physically or virtually in class.
  - `Tardy / Late`: Student arrived after the bell schedule grace period (system records minutes late).
  - `Excused Absence`: Student is absent with an approved medical certificate or advance parental notice.
  - `Unexcused Absence`: Student is absent without authorized justification (triggers automated parent alerts).
  - `School-Sanctioned Activity`: Student is representing the school at an athletic competition, debate meet, or field trip.

### 2.2 Rapid Operational Attendance Tool
- **1-Click Rapid Entry:** Enables teachers to mark attendance for a 25-student batch in under 10 seconds using the "Mark All Present" toggle and individually adjusting exceptions (absent/tardy).
- **Automated Guardian Notification:** Marking an unexcused absence immediately dispatches an automated SMS/push alert to the primary guardian's mobile phone within 15 minutes of bell-ring.
- **Absence Excuse Workflow:** Parents can submit digital medical notes and excuse requests via the Parent Portal. Homeroom teachers and attendance officers review and approve excuses with 1-click verification.

### 2.3 Truancy Thresholds & Dropout Early-Warning Alerts
- **Attendance Rate Computation:** System calculates real-time cumulative attendance percentage:
  $$\text{Attendance Rate} = \frac{\text{Days / Periods Present}}{\text{Total School Days / Periods Held}} \times 100$$
- **Chronic Truancy Escalation:**
  - *Level 1 Warning (3 Unexcused Absences):* Automated advisory notice to parents.
  - *Level 2 Warning (5 Unexcused Absences):* Mandatory counselor outreach and student meeting.
  - *Level 3 Statutory Alert (<85% Cumulative Attendance):* Formal truancy review; academic credit withheld per state accreditation standards.

### 2.4 Student Incident Book & Behavioral Logging
- **Incident Categorization:**
  - *Commendations / Honors:* Academic excellence, leadership, citizenship, sportsmanship, peer support.
  - *Behavioral Concerns:* Disruptive classroom conduct, dress code infractions, mobile phone misuse.
  - *Disciplinary Infractions:* Academic dishonesty / cheating, bullying, vandalism, substance violations.
  - *Counselor & Pastoral Notes:* Non-clinical academic coaching notes (strictly distinct from confidential psychological therapy notes).
- **Action & Resolution Tracking:** Records administrative consequences (detention, loss of privileges, in-school suspension) and tracks resolution status (`Open`, `Under Review`, `Resolved`, `Escalated`).

---

## 3. Business Validation Invariants & Edge Cases

| Invariant ID | Business Rule Description | Violation Outcome |
|---|---|---|
| **VAL-ATT-001** | Attendance for an instructional period can only be submitted once per scheduled timetable slot unless an audited correction is filed. | System flags duplicate submission attempt; requires reason for amendment. |
| **VAL-ATT-002** | Attendance cannot be marked on dates designated as official school holidays or emergency campus closures in the Academic Calendar. | Attendance marking disabled on non-instructional dates. |
| **VAL-ATT-003** | Disciplinary suspension automatically sets the student's attendance to "Excused Suspension" for the duration of the penalty. | System auto-populates suspension status across all subject periods. |

---

## 4. Operational User Workflows

### 4.1 Daily Period Attendance Workflow (Teacher)
1. At 10:15 AM, the Biology teacher launches the **Student Attendance Tool** on their classroom tablet.
2. The roster for "Grade 10-A Biology" loads automatically.
3. The teacher clicks "Mark All Present", changes one student to "Tardy (10 mins)", and marks one absent student as "Unexcused".
4. The teacher clicks "Submit Attendance".
5. The absent student's mother immediately receives a push notification: *"Your child Michael was marked absent for Period 3 Biology at 10:17 AM. Please contact the attendance office if unexpected."*

---

## 5. Business Value & Strategic Impact
- **Real-Time Student Safety:** Parents and administrators know within minutes if a child failed to arrive at school.
- **Accreditation & Funding Compliance:** State education funding often depends on verified daily attendance audits; automated registers ensure 100% audit readiness.
- **Proactive Intervention:** Catching attendance declines early prevents chronic truancy and reduces dropout rates by over 15%.
