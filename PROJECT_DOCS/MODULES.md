# Modules

One section per module. Routes, API prefix, role gating and honest completeness.
Everything here was verified against the code, not taken from commit messages.

**Prefixes are not uniform.** Most school modules mount under `/api/v1/sms/...`,
but **RevOps mounts at `/api/v1/revops`** and **live classes at `/api/v1/live`**.
A wrong prefix silently broke the admissions kanban for a release, so check
`apps/api/src/router.py` before writing a client.

## Role vocabulary

Seven school roles (`SchoolRole`, `apps/api/src/db/sms_identity.py`):
`SUPER_ADMIN`, `SCHOOL_ADMIN`, `TEACHER`, `STUDENT`, `PARENT`, `STAFF`,
`PSYCHOLOGIST`.

The frontend groups these into four access levels (`apps/web/lib/school-access.ts`):

| Level | Who |
|---|---|
| `administer` | SCHOOL_ADMIN / SUPER_ADMIN, or a user with no school role (so a fresh org can be set up) |
| `teach` | administer + TEACHER |
| `backOffice` | administer + STAFF |
| `counsel` | administer + PSYCHOLOGIST |

## Feature flags

Thirteen school modules are independently toggleable per organisation
(`ALL_FEATURES` in `apps/api/src/security/features_utils/resolve.py`):

```
sms_attendance  sms_timetable  sms_gradebook  sms_fees  sms_financials
sms_hr_payroll  sms_library    sms_exam       revops    sms_reports
tutor_counseling  sms_inventory  sms_hostel
```

`sms_inventory` and `sms_hostel` were added with M34/M36. Both are in
`DEFAULT_DISABLED_FEATURES` (`resolve.py:56`), so unlike the others they start
**off** until an org explicitly enables them.

Flip them at **Org settings → Modules** (`OrgEditModules`). Disabling hides the
nav entry *and* 403s the API; records are never deleted and reappear on
re-enable.

Note there is **no flag for live classes**, school settings, campus, admissions
applications or messages — those are always on. School settings is deliberately
unflagged: it is where toggles are administered, so gating it behind one would
let a school switch off the page that switches things back on.

---

## Campus & academic structure

| | |
|---|---|
| Routes | `/dash/campus` |
| API | `/api/v1/sms` (`sms_campus.py`) |
| Gating | `administer` |
| Flag | none (tenancy root, always on) |

Campuses, academic years, terms, class sections, and student enrolment. This is
the tenancy root — every other module scopes against a campus or a section, so
nothing else works until a campus exists. Includes an **academic year rollover**
service that creates next year's sections and promotes students; it only ever
CREATEs, so last year stays readable. Dry run defaults to true.

Grade progression is **supplied, never inferred** — `grade_level` is a free
string with no ordering, so guessing would work until it promoted a KG child
into Year 1.

**Not handled by rollover:** marking leavers graduated, teacher reassignment,
and repeat detection beyond an explicit hold-back list.

---

## School settings

| | |
|---|---|
| Routes | `/dash/school-settings` |
| API | `/api/v1/sms/settings` |
| Gating | `administer` |
| Flag | none, deliberately |

Per-org and per-campus configuration, keyed `(org_id, campus_id, group_key)`.
`campus_id IS NULL` is the org default; a campus row overrides it. Resolution is
**campus → org → code default**.

**Editable today:** school profile, grading policy, fee policy.
**Defined but not yet editable:** academic calendar, attendance policy, report
cards, notifications, AI tutor policy — labelled as such in the UI rather than
shipping controls that do nothing.

The defaults are the existing hardcoded constants, and tests import
`services/sms/fees.py` and `gradebook.py` directly to assert they still match,
so drift fails the suite.

---

## Admissions (RevOps + applications)

| | |
|---|---|
| Routes | `/dash/admissions` (CRM board), `/leads`, `/applications`, `/offers`, `/campaigns`, `/worklist` |
| API | **`/api/v1/revops`** (leads, offers, agents) and `/api/v1/sms/admissions` (applications) |
| Gating | `administer` |
| Flag | `revops` |

Two halves that are deliberately distinct:

**The lead funnel** (`sms_revops.py`, `revops_agents.py`) — enquiry capture via a
hardened webhook, dedup on email/phone, 5-factor scoring, a stage machine with a
STALLED loopback, consent capture that the drip engine genuinely enforces, and a
nurture cron. An inbound enquiry is now auto-acknowledged; before, it sat until
a human opened the CRM.

**The application lifecycle** (`sms_admissions.py`) — application record,
supporting documents *with verification state and a named verifier*, assessment,
and a decision trail. An application does **not** require a lead: a family can
walk in and apply having never been a tracked enquiry.

Children's identity documents are gated to admissions staff only. `TEACHER` is
excluded from every endpoint in that router. Document content is fetched as an
authenticated blob — `DocumentRead` carries no URL field, because a URL would be
copyable into browser history and screenshots.

**Not built:** M24 voice agent (deliberately deferred), deposit/signature
capture, any bank-specific import parser.

---

## Admissions Insights (RevOps analytics + config)

| | |
|---|---|
| Routes | `/dash/revops`, `/dash/revops/config` |
| API | `/api/v1/revops`, `/api/v1/sms/revops-admin` |
| Gating | `administer` |
| Flag | `revops` |

Funnel occupancy, conversion, stalled counts, consent status. Plus **M30 admin
config** — scoring weights, thresholds, nurture cadence, consent policy — and
**M34 knowledge base** with source citations.

Drip stage **copy** is deliberately not editable. That prose carries a
`MissingSchoolIdentity` guard that refuses to generate when the campus is
unknown rather than inventing a school name; outbound copy naming a fictional
campus has already been torn out of this codebase once.

---

## Attendance

| | |
|---|---|
| Routes | `/dash/attendance` + tabs: `/history`, `/excuses`, `/pastoral`, `/bulk` |
| API | `/api/v1/sms/attendance` |
| Gating | `teach` (pastoral is section-scoped for teachers) |
| Flag | `sms_attendance` |

Roll-call, history, absence notes, at-risk queue, bulk marking.

**Period-aware.** A register is keyed `(student_id, section_id, date, period_id)`.
`period_id` is nullable so a primary school's single daily register stays
first-class.

**Editable with history, not locked.** Teachers misclick, so corrections stay
possible — but an append-only `AttendanceChangeEvent` records what changed, who
changed it and when, written in the same transaction as the register.

**Approving an absence note converts** `ABSENT` → `EXCUSED` rather than
annotating alongside (see DECISIONS.md).

**Pastoral gating differs from AI safety incidents on purpose.** Teachers *are*
permitted to see absence flags — but only for their own sections.

---

## Timetable

| | |
|---|---|
| Routes | `/dash/timetable` + tabs: `/generate`, `/lessons`, `/conflicts` |
| API | `/api/v1/sms/timetable` |
| Gating | `teach`; `/generate` is `administer` |
| Flag | `sms_timetable` |

Week grid, periods, schedules, substitutions, clash detection, lesson logs.

**Generation is assisted, not solved** — greedy, deterministic, first-fit, no
backtracking. It reports what it cannot place rather than inventing a placement.
`dry_run` defaults to true.

**Not attempted:** teacher-gap minimisation, room capacity/equipment matching,
consecutive-period blocks, lunch protection, part-time availability.

`/lessons/previous` deliberately does **not** require section ownership — a
substitute is covering a class they do not own, which is exactly why they need it.

---

## Gradebook

| | |
|---|---|
| Routes | `/dash/gradebook` + tab `/report-cards`; `/dash/gradebook/students/[id]` |
| API | `/api/v1/sms/gradebook` |
| Gating | `teach`; grading scales are `administer` |
| Flag | `sms_gradebook` |

Grade matrix, assessment plans, grading scales, GPA, transcripts, report cards.

**Grade changes are auditable.** Append-only `sms_grade_change_event` records the
previous score, the new score, who changed it and when — attributed to the
authenticated caller, never a client-supplied `graded_by`.

**A sent report card is frozen.** Recalculate skips `SENT` cards rather than
silently changing a document a family has already read. Batch send takes explicit
ids, never a section.

`drafted_ungraded` is its own outcome, separated four ways in the UI, because a
teacher must not send thirty cards believing every one carries a grade.

**A student with no grades has no GPA** — `null`, not `0.0`, and not `"F"`.

---

## Exams

| | |
|---|---|
| Routes | `/dash/exams` + tabs `/seating`, `/resits` |
| API | `/api/v1/sms/exams` |
| Gating | `teach`; resits `administer` |
| Flag | `sms_exam` |

Exam scheduling, sittings, results, seating plans, resits.

**Exams and gradebook share ONE grading engine.** `services/sms/exam.py` imports
`resolve_letter_and_gpa` from `gradebook.py`; exam marks become ordinary
`GradebookEntry` rows. No second grading path exists, so a transcript and an exam
result cannot disagree.

**Proctoring is explicitly out of scope.** The module records an *invigilated*
exam and says so in its own docstring. This is documented rather than quietly
implied.

---

## Fees

| | |
|---|---|
| Routes | `/dash/fees` |
| API | `/api/v1/sms/fees` |
| Gating | `backOffice` (`_BURSAR`); concessions and refunds are `_BURSAR_LEAD` |
| Flag | `sms_fees` |

Fee structures, vouchers, payments, ledger, late-fee accrual, **instalment
plans**, **reminders**, **bank-transfer reconciliation**, **concessions** and
**refunds**.

Each instalment is a real voucher belonging to a plan (see DECISIONS.md).
Concessions carry a required reason and an authorising officer. Sibling discounts
attach to a **named** student, never inferred.

A clerk who can take a payment cannot waive one — concessions and refunds sit
above the ordinary bursar line.

**Not built:** any bank-specific import parser, a numeric match-confidence score,
or a payment gateway. Payments record money the office already took.

---

## Financials

| | |
|---|---|
| Routes | `/dash/financials` |
| API | `/api/v1/sms/financials` |
| Gating | `backOffice`; reversals `administer` |
| Flag | `sms_financials` |

Chart of accounts, journal entries, reversals, trial balance.

**Not built:** period close/lock — nothing prevents posting into a settled month.

---

## Staff & Payroll

| | |
|---|---|
| Routes | `/dash/hr`, `/dash/payroll` |
| API | `/api/v1/sms/hr`, `/api/v1/sms/payroll` |
| Gating | `administer` (`_HR_ADMIN`, `_PAYROLL_ADMIN`) |
| Flag | `sms_hr_payroll` |

Staff profiles, leave, salary structures, payroll runs, payslips, **offboarding**
and **appraisals**.

**Separation of duties on payroll.** `approve_slips` refuses when the approver is
the preparer, and `assert_payable` gates the pay endpoint. Prepare → review →
approve → pay.

**Salary reads are own-or-HR-admin.** `_assert_may_read_salary` lets a non-admin
read only their own slips and refuses a bare listing.

**Offboarding runs in one transaction** — partial offboarding is worse than none,
because it looks done. Sections go to a named successor or are released and
reported. Timetable slots cannot be released (`teacher_id` is NOT NULL) and come
back as `outstanding_timetable_slot_ids`.

**Gap:** appraisal `ACKNOWLEDGED` exists in the model with no endpoint — a staff
member cannot yet acknowledge reading their appraisal.

---

## School Library

| | |
|---|---|
| Routes | `/dash/school-library` + tab `/reservations` |
| API | `/api/v1/sms/library` |
| Gating | `backOffice` (`_LIBRARIAN`) |
| Flag | `sms_library` |

Catalogue, loans, returns, overdue fines, **holds queue**.

**The model does not separate titles from copies.** `LibraryBook` tracks
`total_copies`/`available_copies` as counters with no per-copy row, accession
number or barcode. The library knows it holds three copies and how many are out,
but not *which* copy a loan refers to. A hold therefore queues for a title. This
blocks stock-taking, per-copy condition, and "which copy did this child lose".

**No e-reader.** There is no file attachment on a book at all.

---

## Counselling

| | |
|---|---|
| Routes | `/dash/counseling` + tab `/career` |
| API | `/api/v1/sms/counseling` |
| Gating | `counsel` — PSYCHOLOGIST or leadership, deliberately **not** `teach` |
| Flag | `tutor_counseling` |

Session logging, clinical notes, parent-visible summaries, career guidance plans.

**This module enforces 404-never-403.** Where a record's existence is
confidential, an unauthorised caller gets an empty result — never "access
denied", because access denied confirms the record exists. The UI has no
permission-denied branch on any confidential read.

Clinical notes and `parent_visible_summary` are separate fields; the summary is
gated behind `share_summary_with_parent`.

**Gap: there is no caseload endpoint.** Every session read is keyed on a student
id, so a counsellor must arrive from somewhere. Attendance's pastoral queue is
the entry point.

Students render as ids here, not names — `GET /sms/identity/people` excludes
PSYCHOLOGIST, and pulling a student name list into a confidential context would
itself be a disclosure.

---

## Messages & notifications

| | |
|---|---|
| Routes | `/dash/messages` |
| API | `/api/v1/sms` (`notifications.py`) |
| Gating | anyone with a school role |
| Flag | none |

Threads, replies, in-app notifications, delivery records.

**Safeguarding rule, enforced server-side:** a parent may only message staff
connected to their own child — class teacher of, or timetabled to, a section
that child is enrolled in — plus admins and counsellors. Parent-to-parent and
student-to-student are refused. The rule is re-checked on every reply, not just
at thread creation.

A non-participant gets **404, not 403**: thread ids are small integers, and 403
would confirm a conversation about someone's child exists.

**Gaps:** no "start new conversation" picker (an unscoped recipient search would
leak which accounts exist), no real-time updates, no attachments.

---

## Reports

| | |
|---|---|
| Routes | `/dash/reports` |
| API | `/api/v1/sms/reports` |
| Gating | `administer` only (`_REPORT_ROLES`) |
| Flag | `sms_reports` |

Cross-module view over attendance, grades, fees and admissions. Reuses the
gradebook's own `resolve_letter_and_gpa` rather than a second grading engine.

**Null metrics carry a stated reason** — "No roll-call has been taken in this
period" — and never render as `0%`.

---

## Live classes

| | |
|---|---|
| Routes | `/dash/live-classes`, `/dash/live-classes/[classId]` |
| API | **`/api/v1/live`** |
| Gating | `teach`; host controls follow server-computed `can_host` |
| Flag | none |

Scheduling, cancel, start, recording, coursework attachment. In-room: LiveKit
video, session chat, and Learnhouse **Boards and Playgrounds** embedded as tools.
Also available as a course activity (`TYPE_LIVECLASS`).

**Recording is off by default and opt-in per class.** Sharing with students is a
separate decision. Student access is gated by actual enrolment in the section.

**Recording status has seven states.** `UNAVAILABLE` (no storage configured) is
deliberately distinct from `FAILED` — telling a teacher their recording broke
when nobody configured S3 sends them chasing the wrong problem.

**Chat is session-only.** LiveKit's `useChat` persists nothing, and the panel
says so rather than implying a history.

Boards and Playgrounds are embedded as **iframes of the real routes** — same Yjs
collaboration, same permissions, no divergent copy. They could not be mounted
directly because `BoardCanvas` is `h-screen` and `PlaygroundEditor` sizes to the
viewport.

---

## AI Tutor (staff oversight)

| | |
|---|---|
| Routes | `/dash/ai-tutor` |
| API | `/api/v1/ai/oversight`, `/api/v1/ai` |
| Gating | staff; **safety incidents are `counsel`-level only** |
| Flag | `tutor_counseling` |

Transcripts, access blocks, and AI safety incidents.

**Teachers cannot see safety incidents.** Knowing *that* a named child triggered
a self-harm escalation is itself the disclosure. Teachers keep transcript and
access-block oversight.

`prompt_snippet` is excluded from the read schema, so a student's words never
reach a teacher.

---

## Parental AI consent

| | |
|---|---|
| API | `/api/v1/sms/ai-consent` |
| Gating | staff; guardians resolved via `StudentGuardian` |
| Flag | none |

Three separable consent types: `AI_TUTOR`, `TRANSCRIPT_RETENTION`,
`WELLBEING_MONITORING`.

Default mode is **ADVISORY** — no record does not block, so existing pupils are
not locked out overnight, but a recorded **refusal blocks immediately**.
`GET /sms/ai-consent/missing` is the chase list that makes advisory defensible.

Crisis screening runs even without consent — see DECISIONS.md.

---

## Data subject rights (GDPR)

| | |
|---|---|
| API | `/api/v1/sms/data-subject` |
| Gating | SUPER_ADMIN/SCHOOL_ADMIN; parents for their own child; erasure is admin-only |
| Flag | none |

Export covers 37 tables across the school record. Erasure distinguishes what can
be deleted from what must be retained, each with a stated basis.

Confidential tables are **silently absent** for an unauthorised caller — not
queried, not counted, not mentioned — because "2 counselling sessions retained"
would leak exactly what the 404 rule protects.

---

## Cognia evidence

| | |
|---|---|
| API | `/api/v1/sms/cognia` |
| UI | **none reachable** |

Accreditation evidence export. A `CogniaEvidenceStudio` component exists at
`apps/web/modules/ems/cognia/CogniaEvidenceStudio.tsx`, but nothing imports it —
the only reference is the folder's own `index.ts` re-export — so it is dead code
and no route renders it. The export previously emitted a
hardcoded `COGNIA-VERIFIED-CSG-LMS-2026` seal asserting a real accreditation body
had endorsed it; that is removed and it now states plainly that it is an
unverified self-report.

---

## Teacher tools

| | |
|---|---|
| API | `/api/v1/sms/teacher-tools` |
| UI | partial |

AI lesson-plan generation and coursework-hour allocation. `LessonPlan` is linked
optionally from timetable lesson logs.

`LessonPlan.teacher_id` is a Keycloak `sub` **string** while every timetable table
keys teacher on the integer Learnhouse user id — they cannot be joined. Migration
`b7e2d41a9c38` fixed this by adding `LessonPlan.teacher_user_id` (integer
`user.id`) and backfilling it, so the join is now possible; the string column is
**legacy**, still written during the transition and dropped by a later migration
(`apps/api/src/db/sms_teacher_tools.py:46-58`).
