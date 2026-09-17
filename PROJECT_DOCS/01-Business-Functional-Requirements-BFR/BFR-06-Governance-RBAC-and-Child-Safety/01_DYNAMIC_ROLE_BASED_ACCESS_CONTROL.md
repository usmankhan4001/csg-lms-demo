# Business Requirements: Dynamic Role-Based Access Control (RBAC)

**Requirement ID:** BFR-GOV-001  
**Domain:** Governance, Security & Access Control  
**Stakeholders:** School Administrators, IT Directors, Compliance Officers, All Institutional Users  
**Classification:** Pure Business Requirements Specification  

---

## 1. Business Need & Operational Overview

In real-world educational institutions, user responsibilities do not conform to rigid, hardcoded user categories. An academic department head is an instructor, but requires administrative authority to approve lesson plans and review teacher gradebooks. An admissions officer needs access to prospective student records, but must be strictly blocked from viewing employee payroll or clinical psychological files. A bursar needs complete authority over tuition invoices, but should never have rights to edit student grades.

The **Dynamic Role-Based Access Control (RBAC)** module eliminates rigid, hardcoded persona systems. Built upon the flexible **LearnHouse Role & Rights** framework, it empowers institutional administrators to create custom institutional roles and assign fine-grained, hierarchical permission keys governing every operational capability.

---

## 2. Core Business Capabilities & Rules

### 2.1 Decimation of the Rigid 7-Persona System
- **No Hardcoded Personas:** The platform completely rejects hardcoded persona enums.
- **Custom Institutional Roles:** School administrators can define unlimited customized institutional roles:
  - *Academic Leadership:* Academic Dean, Curriculum Director, Department Head.
  - *Instructional Staff:* Lead Teacher, Subject Instructor, Homeroom / Class Mentor, Teaching Assistant, Substitute Teacher.
  - *Student Services:* Guidance Counselor, College Placement Advisor, School Nurse / Health Officer, Athletic Director.
  - *Business & Operations:* Admissions Director, Admissions Counselor, Bursar / Accountant, Registrar, Transport Coordinator, Facilities Manager.
  - *Core Community:* Student (Learner), Parent / Primary Guardian, Third-Party Financial Sponsor.

### 2.2 Hierarchical Permission Key Matrix
Access rights are governed by explicit permission keys formatted as:
$$\text{Domain} : \text{Resource} : \text{Action}$$

```
SAMPLE HIERARCHICAL PERMISSION MATRIX
┌──────────────────────┬─────────────────────────────────────────────────────────────────┐
│ DOMAIN               │ GRANULAR PERMISSION KEYS                                        │
├──────────────────────┼─────────────────────────────────────────────────────────────────┤
│ Academic Operations  │ academics:calendar:write     academics:program:manage           │
│                      │ academics:course:write       academics:batch:manage             │
│                      │ academics:batch:assign_teacher academics:roster:view            │
├──────────────────────┼─────────────────────────────────────────────────────────────────┤
│ Attendance           │ attendance:homeroom:mark     attendance:period:mark             │
│                      │ attendance:excuse:approve    attendance:audit:view              │
├──────────────────────┼─────────────────────────────────────────────────────────────────┤
│ Grading & Assessment │ assessment:plan:approve      grades:entry:submit                │
│                      │ grades:override:execute      reportcard:publish                 │
├──────────────────────┼─────────────────────────────────────────────────────────────────┤
│ Admissions & CRM     │ admissions:lead:write        admissions:offer:issue             │
│                      │ admissions:matriculate:do    admissions:contract:sign           │
├──────────────────────┼─────────────────────────────────────────────────────────────────┤
│ Finance & Fees       │ finance:structure:manage     finance:invoice:generate           │
│                      │ finance:waiver:approve       finance:ledger:audit               │
├──────────────────────┼─────────────────────────────────────────────────────────────────┤
│ Health & Clinical    │ health:medical:view          health:allergy:record              │
│                      │ psychology:notes:view        psychology:crisis:log              │
│                      │ (Psychology permissions strictly restricted to certified staff) │
└──────────────────────┴─────────────────────────────────────────────────────────────────┘
```

### 2.3 Strict Segregation of Duties (SOD)
The system enforces mandatory institutional segregation of duties to prevent fraud and conflicts of interest:
- **Finance vs Academics:** Users with rights to modify financial ledgers or issue tuition fee waivers cannot hold permissions to publish student grades or alter GPA calculations.
- **Admissions vs Matriculation:** Admissions counselors who negotiate tuition discounts cannot unilaterally execute final student matriculation without registrar sign-off.
- **Clinical Separation:** No administrative or teaching role can be granted permissions to view confidential psychological therapy case notes.

---

## 3. Business Validation Invariants & Edge Cases

| Invariant ID | Business Rule Description | Violation Outcome |
|---|---|---|
| **VAL-RBC-001** | A user cannot execute any administrative mutation without explicitly assigned, active permission keys for that specific domain action. | Action denied; security event logged in institutional audit trail. |
| **VAL-RBC-002** | Conflicting segregation-of-duties permissions (e.g., Grade Editing + Financial Waiver Authority) cannot be assigned to the same user role. | System blocks role configuration; flags segregation of duties violation. |
| **VAL-RBC-003** | Deactivating a user role immediately revokes all associated permissions across all active user sessions within 5 seconds. | Active session tokens invalidated; user permissions refreshed. |

---

## 4. Operational User Workflows

### 4.1 Custom Role Creation Workflow (Administrator)
1. The School Administrator needs to create a new role: "High School Department Head".
2. The administrator clones the standard "Subject Teacher" role.
3. The administrator adds elevated permission keys: `assessment:plan:approve`, `grades:cohort:review`, and `timetable:substitute:recommend`.
4. The administrator leaves financial and admissions permissions disabled.
5. The administrator assigns the new role to the 8 academic department chairs, immediately activating their elevated supervisory powers.

---

## 5. Business Value & Strategic Impact
- **Tailored Institutional Fit:** Adapts perfectly to the unique staffing structures of any private, public, charter, or international school network.
- **Robust Security & Fraud Prevention:** Strict segregation of duties eliminates internal fraud, unauthorized grade tampering, and billing corruption.
- **Effortless Compliance:** Simplifies external security and data privacy audits by providing clear, exportable role-permission matrices.
