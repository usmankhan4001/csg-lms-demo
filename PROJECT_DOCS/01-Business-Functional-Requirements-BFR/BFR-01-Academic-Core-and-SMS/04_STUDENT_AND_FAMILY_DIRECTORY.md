# Business Requirements: Student Master & Family Network Directory

**Requirement ID:** BFR-ACAD-004  
**Domain:** Academic Core & School Operations (SMS)  
**Stakeholders:** Registrars, School Nurses, Counselors, Homeroom Teachers, Campus Security, Parents  
**Classification:** Pure Business Requirements Specification  

---

## 1. Business Need & Operational Overview

In an educational institution, a student is not just a digital user account; a student is a minor learner whose physical safety, health, family relationships, legal custody, and emergency protocols must be strictly maintained. Furthermore, tuition billing requires clear identification of the primary financial sponsor, and daily gate operations require verification of who is authorized to pick up the child.

The **Student Master & Family Network Directory** serves as the authoritative, permanent institutional repository for all student profiles and family relationships. It manages unique student identifiers, official roll numbers, emergency health records, legal custody rights, and family communication chains.

---

## 2. Core Business Capabilities & Rules

### 2.1 Permanent Student Master Record
- **Student Identifiers:** Every admitted student is assigned:
  - *Permanent Student ID:* Unique institutional identifier that never changes across years or campuses.
  - *Admission Number / Roll Number:* Grade/cohort-specific sequence number used for daily classroom roll calls and state exams.
- **Core Demographic Information:** Legal first/middle/last name, preferred name, date of birth, biological sex/gender, nationality, native language, and residential home address.
- **Student Enrollment Status:** Tracks the student's institutional standing:
  - `Applicant`: Undergoing admissions review.
  - `Enrolled / Active`: Officially matriculated and actively participating in classes.
  - `On Leave / Suspended`: Temporarily absent due to medical leave or disciplinary suspension.
  - `Withdrawn / Transferred`: Formally exited the institution prior to graduation.
  - `Graduated / Alum`: Completed all graduation requirements; permanent archival record.
- **Student Category:** Classification for reporting and tuition billing (Day Scholar, Boarder, Scholarship Recipient, Special Needs / IEP).

### 2.2 Health, Safety & Special Needs (IEP) Records
- **Medical Profile:** Blood group, verified allergies (e.g., severe peanut allergy, penicillin), chronic medical conditions (asthma, diabetes, epilepsy), and emergency medication guidelines (e.g., EpiPen location).
- **Special Educational Needs (IEP / 504 Plan):** Indicates active accommodation plans, required testing accommodations (e.g., +50% extra time), and designated learning support specialists.
- **Strict Clinical Wall Isolation:** General medical alerts (allergies, asthma) are visible to teachers and nurses; however, confidential psychological and therapeutic counseling records are strictly restricted to licensed school psychologists.

### 2.3 Family & Guardian Network
- **Relational Family Linking:** Links one or more students to one or more parents/guardians, correctly handling siblings, blended families, and legal guardianships.
- **Guardian Profile Attributes:** Full legal name, relation to student (Mother, Father, Step-Parent, Grandparent, Legal Guardian, Sponsor), primary phone number, secondary emergency phone, verified email address, occupation, and employer.
- **Crucial Legal Designations & Rights:**
  - *Legal Custody:* Indicates whether the guardian holds legal custody over the student.
  - *Authorized Physical Pickup:* Explicit list of individuals permitted to pick up the child from campus gates at dismissal (security gate personnel enforce this list).
  - *Emergency Contact Order:* Sequential priority (1st call, 2nd call, 3rd call) for school nurses and administrators during medical emergencies.
  - *Primary Billing Guardian:* The designated parent/guardian responsible for tuition invoices, payment plans, and financial communications.

---

## 3. Business Validation Invariants & Edge Cases

| Invariant ID | Business Rule Description | Violation Outcome |
|---|---|---|
| **VAL-STU-001** | Every active minor student must be linked to at least one primary guardian with verified contact numbers and legal custody. | System prevents student matriculation until guardian profile is verified. |
| **VAL-STU-002** | Campus gate security cannot release a student to any individual not explicitly designated on the Authorized Pickup List. | Immediate gate alert triggered; security holds student and contacts primary guardian. |
| **VAL-STU-003** | When legal court custody orders restrict parental contact (e.g., protective restraining orders), the system must immediately flag the student record. | Red alert banner displayed on administrative profiles; unauthorized parent portal access revoked. |

---

## 4. Operational User Workflows

### 4.1 Student Onboarding & Family Linking (Registrar)
1. Upon admissions contract signing, the Registrar opens the new student profile for "Emily Chen".
2. The system auto-generates Student ID `STU-2026-0842` and Roll Number `10-A-14`.
3. The Registrar links Emily's profile to her parents: Father (Primary Billing Contact, 1st Emergency Priority) and Mother (Legal Custody, Authorized Pickup).
4. The School Nurse inputs Emily's asthma diagnosis and verifies inhaler storage in the health clinic.
5. Emily's homeroom teacher immediately sees the medical alert flag on the daily classroom roster.

---

## 5. Business Value & Strategic Impact
- **Uncompromised Child Protection:** Guarantees that emergency medical protocols and pickup custody rules are accessible instantly to authorized staff.
- **Accurate Financial Accountability:** Eliminates billing disputes by explicitly binding tuition contracts to the legally designated primary billing guardian.
- **Streamlined Family Communications:** Automatically routes school broadcasts, attendance alerts, and report cards to all authorized guardians simultaneously.
