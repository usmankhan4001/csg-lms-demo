# Business Requirements: Automated Matriculation Handshake

**Requirement ID:** BFR-ADM-003  
**Domain:** Admissions, CRM & RevOps  
**Stakeholders:** Admissions Directors, Registrars, Bursars, Homeroom Teachers, IT Administrators, Enrolled Families  
**Classification:** Pure Business Requirements Specification  

---

## 1. Business Need & Operational Overview

In traditional schools, the transition from an accepted admissions applicant to an officially enrolled student is fraught with manual paperwork, duplicate data re-entry, lost medical notes, and billing discrepancies. Registrars must re-type student names into legacy student databases, bursars manually set up tuition invoices, and homeroom teachers receive student names days after classes have begun.

The **Automated Matriculation Handshake** module bridges the commercial recruitment domain (Admissions / RevOps) and the operational institutional domain (Academic Core / SMS). It orchestrates an instant, automated, multi-domain onboarding process the moment an enrollment contract is executed and the registration deposit is confirmed.

---

## 2. Core Business Capabilities & Rules

### 2.1 The Automated Matriculation Handshake
When an admissions contract is signed and the deposit is verified, the system executes the 6-step **Matriculation Handshake**:

```
THE AUTOMATED MATRICULATION HANDSHAKE
┌────────────────────────────────────────────────────────────────────────┐
│ TRIGGER: Admissions Offer Contract Digitally Signed & Deposit Cleared   │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ STEP 1: CREATE PERMANENT STUDENT MASTER RECORD                         │
│ • Promotes Applicant to 'Enrolled / Active' Student                    │
│ • Issues Permanent Institutional Student ID (e.g., STU-2026-0842)      │
│ • Allocates Grade Roll Number based on cohort sequence                 │
├────────────────────────────────────────────────────────────────────────┤
│ STEP 2: ESTABLISH FAMILY & GUARDIAN CUSTODY NETWORK                    │
│ • Links verified Parent records to Student Master Profile              │
│ • Confirms Legal Custody, Authorized Pickup List, and Emergency Priority│
│ • Binds the Primary Billing Guardian to the financial account          │
├────────────────────────────────────────────────────────────────────────┤
│ STEP 3: TIER 1 PROGRAM MATRICULATION & BATCH PLACEMENT                 │
│ • Enrolls student into official Academic Program (e.g., High School)   │
│ • Places student into target Cohort Batch (e.g., Grade 10-A)           │
│ • Assigns Homeroom Mentor / Class Teacher                              │
├────────────────────────────────────────────────────────────────────────┤
│ STEP 4: GENERATE FINANCIAL FEE SCHEDULE & TERM INVOICING               │
│ • Instantiates itemized annual fee structure (Tuition, Lab, Bus)       │
│ • Applies verified scholarships and sibling discounts                  │
│ • Schedules term installment due dates and issues initial invoice      │
├────────────────────────────────────────────────────────────────────────┤
│ STEP 5: INITIALIZE DIGITAL IDENTITY & LMS PORTAL ACCESS                │
│ • Provisions Student Single-Sign-On (SSO) email and portal login       │
│ • Provisions Parent Portal access for all authorized guardians         │
├────────────────────────────────────────────────────────────────────────┤
│ STEP 6: DISPATCH CAMPUS ONBOARDING WELCOME PACKAGE                     │
│ • Sends automated welcome briefing with uniform guidelines & timetable │
│ • Alerts School Nurse of any flagged medical allergies                 │
│ • Alerts Homeroom Teacher of incoming new cohort member                │
└────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Reversal & Cancellation Protocol
- **Enrollment Rescission / Pre-Start Withdrawal:** If a family cancels enrollment prior to the first day of classes:
  - The student's status transitions from `Enrolled / Active` to `Withdrawn Prior to Start`.
  - Batch seat is immediately released back to the admissions waitlist.
  - Fee schedule is recalculated based on non-refundable deposit terms, issuing appropriate refund credits.
  - Portal accounts are deactivated to prevent unauthorized institutional access.

---

## 3. Business Validation Invariants & Edge Cases

| Invariant ID | Business Rule Description | Violation Outcome |
|---|---|---|
| **VAL-MAT-001** | The Matriculation Handshake cannot execute until the minimum required enrollment deposit has cleared the financial gateway. | System holds applicant in "Offer Accepted - Pending Deposit"; matriculation deferred. |
| **VAL-MAT-002** | The student cannot be assigned to a batch whose active student count has already reached its approved maximum cohort capacity. | System prompts registrar to select an alternate parallel section (e.g., Batch 10-B) or authorize section expansion. |
| **VAL-MAT-003** | Incomplete medical clearance documentation (e.g., unverified statutory immunizations) flags the newly created student profile with a "Medical Hold". | Student profile created but flagged; physical campus entry restricted until health office clears hold. |

---

## 4. Operational User Workflows

### 4.1 Automated Onboarding Handshake Execution
1. On June 12 at 4:00 PM, parent Marcus Wright signs the digital enrollment agreement for his daughter Chloe (Grade 9) and pays the $1,500 registration deposit.
2. The payment gateway verifies the transaction and emits the contract execution signal.
3. The system executes the Matriculation Handshake within 3 seconds:
   - Chloe Wright becomes Student `STU-2026-1104` in Batch `Grade 9-B`.
   - Marcus Wright is registered as Primary Billing Contact; Mrs. Wright is registered as Primary Emergency Contact.
   - The Fall 2026 tuition fee schedule is created with 3 installment dates.
   - Chloe's student email and Marcus's parent portal credentials are generated and emailed.
4. Homeroom Teacher Ms. Jenkins receives an automated notification: *"New student Chloe Wright added to Grade 9-B starting August 25."*

---

## 5. Business Value & Strategic Impact
- **Zero Administrative Paperwork:** Eliminates 100% of manual data re-keying between admissions and the academic registrar office.
- **Flawless Family Experience:** Families receive instant portal credentials, fee statements, and welcome materials seconds after signing.
- **Accurate Day-One Readiness:** Guarantees that every child has a verified classroom seat, teacher roster entry, emergency card, and fee schedule before the first day of school.
