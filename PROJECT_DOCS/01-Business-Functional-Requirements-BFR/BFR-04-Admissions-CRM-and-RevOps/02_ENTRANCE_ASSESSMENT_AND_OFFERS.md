# Business Requirements: Entrance Assessment & Admissions Offers

**Requirement ID:** BFR-ADM-002  
**Domain:** Admissions, CRM & RevOps  
**Stakeholders:** Admissions Directors, Faculty Interviewers, Academic Deans, Prospective Parents  
**Classification:** Pure Business Requirements Specification  

---

## 1. Business Need & Operational Overview

Selective and high-standard academic institutions require rigorous screening before admitting a prospective learner. The admissions committee must evaluate previous academic transcripts, administer standardized entrance examinations (mathematics, language literacy, cognitive ability), conduct student/family interviews, and issue legally binding Admissions Offers with customized tuition fee quotations.

The **Entrance Assessment & Admissions Offers** module governs application document verification, entrance exam scheduling and scoring, interview committee evaluations, scholarship grant calculations, and dynamic offer contract issuance.

---

## 2. Core Business Capabilities & Rules

### 2.1 Application Dossier & Document Verification
- **Application Dossier:** Tracks submission of mandatory admissions documentation:
  - Official prior school report cards and longitudinal transcripts (minimum 2 prior years).
  - Immunization and health clearance certificates.
  - Teacher recommendation forms and character references.
  - Government identity verification (passport or birth certificate).
- **Document Verification Workflow:** Admissions staff review submitted files, marking status as `Pending Verification`, `Verified`, or `Deficient / Resubmission Required`.

### 2.2 Entrance Examination & Interview Scoring
- **Entrance Testing Administration:** Schedules applicants for computer-based or on-campus entrance evaluations in Mathematics, English/Language Arts, and Logical Reasoning.
- **Faculty Interview Panel:** Admissions committee members conduct one-on-one student and family interviews, evaluating communication skills, academic motivation, and school cultural alignment using standardized rubrics.
- **Composite Admissions Index (CAI):** Computes an objective composite applicant score:
  $$\text{CAI} = (0.35 \times \text{Prior GPA}) + (0.45 \times \text{Entrance Exam}) + (0.20 \times \text{Interview Score})$$

### 2.3 Dynamic Admissions Offers & Contract Generation
- **Admissions Committee Decisions:**
  - `Admitted / Offered`: Applicant meets standards; official offer generated.
  - `Waitlisted`: Qualified applicant placed in ranked waitlist pending seat availability.
  - `Rejected`: Applicant does not meet institutional academic prerequisites.
- **Dynamic Offer Letter & Fee Schedule Quotation:**
  - Automatically calculates itemized annual tuition, registration deposit, laboratory fees, and bus transport costs based on the selected campus and grade level.
  - Incorporates approved financial aid, sibling discounts, or merit scholarship deductions.
  - Embeds legally binding enrollment terms and conditions with an electronic signature workflow.
- **Offer Expiry Window:** Offers enforce an acceptance deadline (e.g., 14 calendar days) with an automated seat forfeiture warning.

---

## 3. Business Validation Invariants & Edge Cases

| Invariant ID | Business Rule Description | Violation Outcome |
|---|---|---|
| **VAL-OFR-001** | An Admissions Offer cannot be issued to an applicant whose mandatory application documents are incomplete or unverified. | Offer generation blocked; system prompts admissions officer to resolve missing files. |
| **VAL-OFR-002** | Total admitted applicants across active offers cannot exceed the target batch seat capacity plus approved institutional over-offer tolerance. | System flags seat capacity overflow; triggers waitlist placement. |
| **VAL-OFR-003** | When an Admissions Offer deadline expires without signed contract or deposit, the offer shifts to "Expired" and the seat is released to the waitlist. | System auto-expires offer; notifies next ranked waitlist applicant. |

---

## 4. Operational User Workflows

### 4.1 Offer Issuance & Contract Signing Workflow (Admissions & Parent)
1. Following successful entrance testing (CAI: 91/100), Admissions Director Sarah approves the acceptance of applicant "Lucas Vance" for Grade 10.
2. The system generates an official Admissions Offer letter with itemized tuition, a 10% sibling discount, and an acceptance deadline of April 15.
3. Lucas's parents receive an email containing a secure link to the digital enrollment contract.
4. The father signs the contract digitally and pays the $1,000 non-refundable enrollment deposit via credit card.
5. The system marks the contract as "Accepted & Executed", immediately triggering the **Matriculation Handshake**.

---

## 5. Business Value & Strategic Impact
- **Rigorous Academic Selectivity:** Standardized composite scoring ensures transparent, merit-based admissions decisions aligned with school academic standards.
- **Zero Enrollment Leakage:** Automated offer expiration and ranked waitlist management ensure maximum classroom seat occupancy without over-enrollment.
- **Accelerated Contract Velocity:** Digital contract generation and integrated deposit processing reduce enrollment turnaround time from weeks to 48 hours.
