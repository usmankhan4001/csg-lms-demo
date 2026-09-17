# Business Requirements: Itemized Fees & Installment Schedules

**Requirement ID:** BFR-OPS-001  
**Domain:** Institutional Administration & Finance  
**Stakeholders:** Chief Financial Officers, Bursars, Finance Managers, Billing Guardians  
**Classification:** Pure Business Requirements Specification  

---

## 1. Business Need & Operational Overview

Tuition billing in an independent or private school is rarely a simple single flat fee. Tuition structures vary by campus, grade level, curriculum track, and student category (Day Scholar vs Boarder). Furthermore, schools assess itemized operational fees (laboratory apparatus, examination registration, bus transport, annual caution deposits), offer sibling and scholarship discounts, and support diverse payment preferences (annual lump-sum, semester installments, or monthly payment plans).

The **Itemized Fees & Installment Schedules** module governs the institutional fee catalog, automated invoice generation, flexible payment installment plans, late payment penalty calculations, and parent payment reconciliation.

---

## 2. Core Business Capabilities & Rules

### 2.1 Multi-Category Itemized Fee Structures
- **Fee Categories:** Institutions define distinct fee line items:
  - *Tuition Fee:* Core instructional charge, configured per Grade Level and Academic Year.
  - *Admission / Registration Fee:* One-time non-refundable fee assessed upon initial matriculation.
  - *Laboratory & STEM Material Fee:* Specialized charge for science and technical coursework.
  - *Transportation Base Fee:* Zone-based fee assessed for school bus riders.
  - *Boarding / Residential Fee:* Housing and meal plan charges for boarding students.
  - *Refundable Caution / Security Deposit:* Held in escrow until the student withdraws or graduates.
- **Tuition Adjustments & Discounts:**
  - *Sibling Discounts:* Automated percentage reduction applied to younger siblings (e.g., 10% for 2nd child, 20% for 3rd child).
  - *Merit & Need-Based Scholarships:* Percentage or fixed-amount fee waivers approved by the scholarship committee.

### 2.2 Flexible Payment Installment Schedules
- **Payment Plan Options:** Parents select from approved payment cadences:
  - *Annual Upfront:* 100% tuition due before the first day of school (optionally incentivized by a 3% early-bird discount).
  - *Term Installments:* Balanced split across academic terms (e.g., 50% Fall, 50% Spring; or 33.3% per trimester).
  - *Monthly Payment Plan:* 10 equal monthly deductions across the instructional school year.
- **Installment Mechanics:** Each installment specifies an exact Due Date, Grace Period (e.g., 5 business days), and automated Late Payment Penalty (e.g., 1.5% monthly compound fee or fixed $50 late charge).

### 2.3 Automated Invoicing & Parent Account Statements
- **Invoice Generation:** Invoices are automatically generated and dispatched to the designated Primary Billing Guardian 30 days prior to each installment due date.
- **Omnichannel Payment Processing:** Parents pay online via integrated credit card, ACH bank transfer, or record verified offline cash/wire receipts.
- **Real-Time Account Statement:** Parents access an itemized digital ledger displaying total billed tuition, payments credited, outstanding balance, and upcoming installment dates.

---

## 3. Business Validation Invariants & Edge Cases

| Invariant ID | Business Rule Description | Violation Outcome |
|---|---|---|
| **VAL-FEE-001** | Total installment amounts across a scheduled payment plan must equal exactly the net annual tuition after authorized discounts. | Plan generation blocked; system prompts bursar to resolve rounding discrepancies. |
| **VAL-FEE-002** | Late payment penalties cannot be assessed prior to the expiration of the official contractual grace period date. | System prevents premature late-fee calculation. |
| **VAL-FEE-003** | When a student withdraws mid-term, tuition refund calculations must adhere strictly to the institution's published prorated refund schedule. | System auto-computes proration and generates refund adjustment invoice. |

---

## 4. Operational User Workflows

### 4.1 Fee Schedule Configuration & Invoice Dispatch (Bursar)
1. At the start of the fiscal year, the Bursar sets the Grade 10 Tuition Fee at $12,000, Science Lab Fee at $600, and Caution Deposit at $1,000.
2. For student Michael Chang, the system applies a 10% sibling discount, setting net tuition to $10,800.
3. The parents select the 3-Term Installment Plan.
4. The system schedules three installments of $4,133 due on August 15, December 1, and March 15.
5. On July 15, the initial invoice is automatically generated and emailed to the father with an integrated "Pay Now" link.

---

## 5. Business Value & Strategic Impact
- **Accelerated Cash Flow & Revenue Recovery (+18%):** Automated installment generation and scheduled reminders drastically reduce overdue receivables and bad debt.
- **Complete Billing Transparency:** Itemized family ledgers eliminate parent confusion and billing disputes regarding what fees were charged.
- **Operational Automation:** Replaces manual billing spreadsheets with a fully automated recurring invoicing engine.
