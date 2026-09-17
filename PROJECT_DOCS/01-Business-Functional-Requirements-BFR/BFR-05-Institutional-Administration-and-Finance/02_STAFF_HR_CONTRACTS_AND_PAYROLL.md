# Business Requirements: Staff HR, Contracts & Payroll

**Requirement ID:** BFR-OPS-002  
**Domain:** Institutional Administration & Finance  
**Stakeholders:** Human Resources Directors, Bursars, School Principals, Faculty, Administrative Staff  
**Classification:** Pure Business Requirements Specification  

---

## 1. Business Need & Operational Overview

Faculty and administrative personnel represent an educational institution's most vital asset and its largest operational expenditure (typically 65–75% of school operating budgets). Schools must manage teacher credentialing, employment contracts, maximum weekly teaching period allocations, sick/personal leave requests, and monthly progressive payroll generation.

The **Staff HR, Contracts & Payroll** module governs the employee master directory, contractual workload compliance, leave request workflows, and monthly salary disbursement processing.

---

## 2. Core Business Capabilities & Rules

### 2.1 Employee Master Directory & Credentialing
- **Staff Records:** Maintains comprehensive personnel files for all faculty, administrators, nurses, security officers, and support staff.
- **Academic Credentials:** Tracks degrees, teaching certifications, state licenses, background check clearances, and CPR/First Aid certifications with automated expiration warning alerts.
- **Departmental Hierarchy:** Maps staff to Academic Departments (e.g., Mathematics, Humanities) and Administrative Units with designated reporting supervisors.

### 2.2 Employment Contracts & Teaching Workload Limits
- **Contract Management:** Tracks contract types (Full-Time Faculty, Part-Time Adjunct, Fixed-Term, Hourly Support), contract start/end dates, base annual salary, and tenure status.
- **Contractual Workload Rules:**
  - Defines maximum weekly instructional periods (e.g., 20 periods per week).
  - Specifies mandatory office hours, supervisory duties (recess, lunch, bus duty), and homeroom mentorship assignments.
  - Schedulers are barred from exceeding contractual workload limits without approved supplemental compensation agreements.

### 2.3 Leave Management & Substitute Triggers
- **Leave Types:** Sick leave, personal leave, bereavement, maternity/paternity, professional development, and sabbatical.
- **Leave Request Workflow:** Staff submit digital leave requests; department heads review and approve with 1-click.
- **Automated Timetable Handoff:** An approved faculty leave request automatically triggers the **Emergency Teacher Substitution Assistant** in the Timetable module, queuing qualified replacement teachers.

### 2.4 Monthly Progressive Payroll Engine
- **Salary Computation:** Automatically computes monthly gross pay based on contractual salary, stipend additions (department head stipend, athletic coach stipend), and overtime compensation.
- **Statutory & Voluntary Deductions:** Calculates income tax withholdings, social security/pension contributions, health insurance premiums, and retirement deductions.
- **Disbursement & Digital Payslips:** Generates direct deposit bank disbursement files and publishes confidential, password-protected digital payslips to the Employee Self-Service Portal.

---

## 3. Business Validation Invariants & Edge Cases

| Invariant ID | Business Rule Description | Violation Outcome |
|---|---|---|
| **VAL-PAY-001** | Staff members with expired statutory background checks or revoked teaching licenses cannot be assigned to active classroom rosters. | System flags credential alert; blocks teacher scheduling. |
| **VAL-PAY-002** | Total monthly payroll deductions cannot exceed statutory regulatory limits (e.g., maximum 50% of gross earnings). | System flags deduction cap violation; alerts payroll officer. |
| **VAL-PAY-003** | Final severance payroll for departing employees requires multi-sign-off clearance (Library books returned, campus keys surrendered, IT laptop checked in). | Final disbursement locked until all departments sign off on clearance. |

---

## 4. Operational User Workflows

### 4.1 Monthly Payroll Generation Workflow (Bursar / HR)
1. On the 25th of the month, the HR Director reviews approved leave requests and verifies that all staff substitute adjustments are recorded.
2. The Bursar launches the **Payroll Processing Tool**.
3. The system computes gross-to-net earnings across all 110 faculty and staff members, generating tax deductions and benefit withholdings in 45 seconds.
4. The Bursar audits the variance report comparing current payroll against the previous month.
5. Upon Chief Financial Officer approval, the electronic direct-deposit file is transmitted to the bank, and digital payslips are published to the staff portal.

---

## 5. Business Value & Strategic Impact
- **Statutory Regulatory Compliance:** Eliminates compliance risks by guaranteeing accurate tax withholdings and tracking teacher credential renewals.
- **Seamless Operational Continuity:** Direct linkage between faculty leave requests and timetable substitution prevents unattended classrooms.
- **Employee Trust & Retention:** Flawless, timely payroll and transparent digital payslips enhance faculty morale and job satisfaction.
