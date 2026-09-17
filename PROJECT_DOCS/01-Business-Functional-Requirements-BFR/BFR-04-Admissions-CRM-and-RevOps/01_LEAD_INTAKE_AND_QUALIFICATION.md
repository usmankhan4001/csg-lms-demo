# Business Requirements: Admissions Lead Intake & Qualification

**Requirement ID:** BFR-ADM-001  
**Domain:** Admissions, CRM & RevOps  
**Stakeholders:** Admissions Directors, Marketing Managers, Admissions Counselors, Inquiring Parents  
**Classification:** Pure Business Requirements Specification  

---

## 1. Business Need & Operational Overview

Attracting, nurturing, and enrolling prospective families is the lifeblood of tuition-dependent independent schools, international academies, and private education networks. When parents inquire about admissions outside school operating hours or on weekends, delayed staff responses often result in lost enrollments to competing schools. 

The **Admissions Lead Intake & Qualification** module manages the top-of-funnel student recruitment lifecycle. It captures prospective family inquiries across multiple channels, provides 24/7 conversational engagement via an intelligent Admissions Assistant, assesses academic and geographic eligibility, scores lead enrollment propensity, and schedules guided campus tours.

---

## 2. Core Business Capabilities & Rules

### 2.1 Omnichannel Lead Capture
- **Multi-Source Capture:** Captures admissions inquiries seamlessly from Web inquiry forms, WhatsApp business messaging, walk-in reception logs, educational agency portals, and social media campaigns.
- **Lead Profile Attributes:** Inquiring parent name, relationship, contact phone, email, prospective student name, birth date, target grade level, target academic year, current school, and geographic residential zone.

### 2.2 24/7 Conversational AI Admissions Assistant
- **Immediate Response SLA:** Inquiries receive an empathetic, personalized response within 60 seconds regardless of time of day or weekend.
- **Curriculum & FAQ Guidance:** Conversational AI answers parent questions regarding educational tracks (e.g., "Do you offer the IB Diploma?"), tuition fee ranges, extracurricular athletics, transportation bus coverage, and admissions deadlines.
- **Automated Tour Scheduling:** Seamlessly connects to admissions staff calendars, allowing parents to book physical campus tours or virtual open-house webinars with automated calendar invites and reminder notifications.

### 2.3 Lead Qualification & Propensity Scoring (BANT Framework)
- **Academic Eligibility Screening:** Automatically verifies prospective student age against target grade level cutoff rules.
- **Propensity Scoring Algorithm:** Evaluates lead engagement, inquiry completeness, open-house attendance, and family timeline to assign a dynamic Lead Score (0–100):
  - *Cold Leads (<40):* Nurtured via automated educational email newsletters.
  - *Warm Leads (40–75):* Scheduled for campus tours and information sessions.
  - *Hot Leads (>75):* Prioritized for immediate one-on-one counselor outreach.

---

## 3. Business Validation Invariants & Edge Cases

| Invariant ID | Business Rule Description | Violation Outcome |
|---|---|---|
| **VAL-ADM-001** | An inquiry cannot be processed if the prospective student's date of birth does not meet the institutional minimum age requirement for the target grade level. | System advises parent of grade age guidelines; proposes appropriate age-eligible grade track. |
| **VAL-ADM-002** | Prospective family contact information must be verified for compliance with international anti-spam (CAN-SPAM / GDPR) consent rules. | Explicit consent checkbox required before automated marketing sequences commence. |
| **VAL-ADM-003** | When campus tour booking slots reach physical capacity (e.g., max 15 families per group), subsequent requests must offer alternate dates or waitlist spots. | Tour booking tool dynamically locks full time slots. |

---

## 4. Operational User Workflows

### 4.1 Inquiring Parent Engagement Workflow (Parent & Admissions AI)
1. At 9:30 PM on a Saturday, a prospective mother visits the school website seeking Grade 9 admission for her son.
2. The Admissions AI Assistant initiates a friendly chat, answering her questions regarding STEM programs and bus routes.
3. The mother requests a campus visit; the assistant checks live tour capacity and books her for "Tuesday at 10:00 AM".
4. The system automatically creates a qualified Lead record in the CRM, scores it at 85 (Hot Lead), and assigns it to Senior Admissions Counselor David.
5. Counselor David receives a calendar briefing on Monday morning ahead of the family's arrival.

---

## 5. Business Value & Strategic Impact
- **Increased Enrollment Conversion (+35%):** Instant, around-the-clock conversational response eliminates inquiry drop-off and dramatically boosts campus tour attendance.
- **Counselor Productivity:** Automates repetitive administrative scheduling, allowing admissions staff to focus entirely on high-touch family relationships.
- **Targeted Marketing ROI:** Real-time lead attribution reveals which advertising campaigns and educational channels produce the highest-yielding matriculated students.
