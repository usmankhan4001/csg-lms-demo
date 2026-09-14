# Decision log

Decisions taken during the build, with the reasoning that produced them. Most
are here because the obvious choice was wrong for a reason that only shows up in
a real school.

Format: **context → decision → why → consequence.**

---

## 1. Each fee instalment is its own voucher

**Context.** Schools in this market bill in instalments. The model had one
voucher per bill with no schedule.

**Decision.** An instalment plan is a parent record; each instalment is a real
`StudentFeeVoucher` belonging to it.

**Why.** Late-fee accrual reads `due_date` **per voucher**. Modelled as a single
voucher carrying a schedule, accrual would have read the one due date and charged
late fees against *the whole year's fee* the day the first instalment slipped.

**Consequence.** Payments, receipts, the ledger and accrual needed zero changes.
"Paid 1 of 3" is a count of child vouchers and the plan total is a sum of their
stored amounts — no second balance calculation exists, so nothing can drift from
what the voucher says. The split front-loads its rounding remainder so the final
instalment is never a strange number a family queries.

---

## 2. Approving an absence note converts ABSENT → EXCUSED

**Context.** A parent sends a note. Either the attendance record changes, or an
excuse row sits alongside it and every reader applies the rule.

**Decision.** Approval converts the record. Only `ABSENT` converts.

**Why.** The attendance formula already counts `EXCUSED` as present-equivalent,
so approving a note and still reporting the child absent means the school has not
really approved anything. More importantly it keeps **one source of truth**: the
annotate alternative forces every reader — monthly sheet, parent digest, report
card, streak detector, any future export — to join and reapply the rule, and one
of them will forget, and then two screens disagree about the same child.

**Consequence.** Reversible and auditable — the original `ABSENT` survives in the
change trail with the reviewer and their reason. `LATE` deliberately does not
convert: silently upgrading it would erase a real punctuality record.

---

## 3. Attendance is editable with history, not locked

**Context.** A register is a legal record. The obvious control is a lock.

**Decision.** Registers stay editable; an append-only `AttendanceChangeEvent`
records what changed, who changed it, when, and optionally why.

**Why.** Teachers genuinely misclick, and a lock turns every correction into an
admin request. The real problem was never that registers could change — it was
that nothing recorded the change.

**Consequence.** The trail is written in the **same transaction** as the
register, so a crash cannot leave a register changed with no record. Attribution
follows the authenticated caller, never the client-supplied `marked_by`. An
unchanged re-submission is not logged — a teacher pressing save twice must not
bury real corrections in noise.

---

## 4. Report-card batch send takes explicit ids, never a section

**Context.** A teacher wants to send a whole section's report cards.

**Decision.** `batch-send` accepts a list of report-card ids.

**Why.** A section is a moving target — "send this section" fans out to whoever
is enrolled at press time, including a student added since the teacher last
looked. Thirty report cards cannot be recalled.

**Consequence.** The UI selects ids explicitly, only drafts are selectable, and
`drafted_ungraded` is a separate outcome shown four different ways so nobody
sends a section believing every card carries a grade.

---

## 5. Timetable generation is assisted, not solved

**Context.** Every section was hand-built each term.

**Decision.** Greedy, deterministic, first-fit placement. No backtracking, no
optimisation. Unplaceable periods are reported, never invented.

**Why.** Full timetabling is a constraint-satisfaction problem. A solver that
quietly produces a subtly-wrong timetable is **more dangerous than none** — the
school trusts the output and discovers the fault in week one, with two classes in
one room.

**Consequence.** `dry_run` defaults to true on both the schema and the API
client, so a week cannot be written by omission. Candidates are validated against
the *same* `detect_timetable_clashes` the write path uses. Deliberately not
attempted: teacher-gap minimisation, room capacity, consecutive blocks, lunch
protection, part-time availability.

*Subtlety worth keeping:* a dry run writes nothing, so without in-run bookkeeping
every occurrence would be offered the same first free slot and **the preview
would promise a timetable that cannot exist**. Within-run reservations fix it.

---

## 6. The grade-change trail snapshots integers, not foreign keys

**Context.** An audit trail naturally references the rows it describes.

**Decision.** `sms_grade_change_event` stores `student_id`,
`assessment_plan_id` and `section_id` as plain integers.

**Why.** `GradebookEntry.assessment_plan_id` is `ondelete=CASCADE`. An FK-linked
trail would be **destroyed by deleting the assessment plan** — precisely when it
matters most.

**Consequence.** The trail outlives the rows it describes. The same reasoning was
reused for `AttendanceChangeEvent` rather than inventing a second audit idiom.

---

## 7. Teachers are excluded from safety incidents but included in pastoral flags

**Context.** Both surfaces concern a named child at risk. The instinct is to gate
them identically.

**Decision.** `ai_oversight._SAFEGUARDING` excludes TEACHER outright. Attendance
pastoral concerns **include** TEACHER, scoped to their own sections.

**Why.** An AI safety incident reveals something a child typed in private and
never told their teacher — **its existence is the disclosure**. An absence streak
is the opposite: the teacher marked those registers themselves, so they already
know. Hiding the flag would withhold the prompt to act from the one adult who
sees the child daily, and chasing an absent tutee is the most basic pastoral duty
a school has.

**Consequence.** A teacher sees their own tutees' flags, never the whole school's
at-risk list, and the UI states which scope they are seeing so three concerns
cannot be misread as the school having three.

*Load-bearing detail:* empty scope `[]` means "no sections, return nothing";
`None` means unrestricted. Conflating them would hand a teacher with no sections
the entire school.

---

## 8. Crisis screening runs even without AI consent

**Context.** A guardian refuses AI consent. Does crisis detection still run on
that child's messages?

**Decision.** Tutoring is withheld; **screening still runs**, crisis resources
are still shown, and a counsellor is still notified. Controlled by
`crisis_override_enabled`, tested both ways.

**Why.** This turned on a fact, not a value judgement. `classify_prompt_safety()`
is a **synchronous local regex** — no model call, no network, no third-party
processor. A guardian refusing "AI" is refusing the LLM tutoring that genuinely
ships their child's words outside the building. Disabling a local pattern match
buys that family **no privacy from anyone**, while costing the child the one
mechanism that would notice them saying they want to die.

**Consequence.** This does override an explicit parental decision, which is why
it is a flag a school can turn off rather than a hidden default. The alert
carries triage metadata only — never the student's words.

---

## 9. The library does not separate titles from copies — and says so

**Context.** `LibraryBook` tracks `total_copies` and `available_copies` as
counters. There is no per-copy row, accession number or barcode.

**Decision.** Left as-is, and the limitation is stated in the model, the types
and the UI.

**Why.** Adding per-copy identity is a real modelling change. Papering over it —
letting a hold appear to reserve a specific copy — would promise something the
system cannot deliver.

**Consequence.** A hold queues for a **title**. Stock-taking, per-copy condition,
and "which copy did this child lose" are unavailable and documented as such.

---

## 10. Learnhouse features are toggled, never forked

**Context.** Some upstream features (podcasts, communities) are marginal for a
school.

**Decision.** Disable them per-org through the existing feature-toggle system.
Never delete or fork the code.

**Why.** A removed feature is a permanent merge conflict with upstream. A
disabled one costs nothing.

**Consequence.** The same principle drove composing Boards and Playgrounds into
live classes as **iframes of the real routes** rather than reimplementing them —
same Yjs collaboration, same permissions, no divergent copy to maintain.

---

## 11. Confidential records return 404, never 403

**Context.** Counselling records, and AI safety incidents.

**Decision.** An unauthorised caller gets an empty result or a 404 — never
"access denied".

**Why.** *Access denied confirms the record exists.* A teacher must not be able
to learn that a child is seeing a counsellor.

**Consequence.** The UI has no permission-denied branch on any confidential read:
"No sessions recorded" is the single rendering for both "this child has never
been seen" and "you may not see this". It propagates further than expected — the
GDPR **retention statement** had to be silenced too, because "2 counselling
sessions retained" leaks exactly what the 404 protects.

Page titles carry no student identifier, since titles land in browser history and
screenshots.

---

## 12. Payroll enforces separation of duties

**Context.** Three payroll endpoints composed into a path where one person could
set their own salary structure, generate their slip and mark it paid.

**Decision.** Prepare → review → approve → pay. `approve_slips` refuses when the
approver is the preparer; `assert_payable` gates the pay endpoint.

**Why.** Narrowing the role was a stopgap — it made the self-dealing path require
a more senior person, not a second person.

**Consequence.** Refusal is an **outcome, not an exception**, so one refused slip
does not abort a thirty-slip run. A pre-existing test was found asserting the old
path as expected behaviour; the test was fixed, never the check.

---

## 13. Absence of data is never rendered as zero

**Context.** This codebase shipped eight fabricated-data incidents that had to be
torn out, including a `4.0` GPA with `honor_roll: true` for a student with zero
grades, a persisted `"F"` for a student with no marks, a parent digest inventing
attendance and teacher praise, and attendance reporting `0%` when no register had
been taken.

**Decision.** Rates, grades and derived figures return `null` with a stated
reason when there is no data. Counts stay as counts.

**Why.** "0% attendance" tells a parent their child attended nothing. The truth
is nobody marked a register. Those demand opposite actions. A count of zero — "0
leads" — is a real answer and is *not* nulled.

**Consequence.** It propagates through the UI: `"Not recorded"` with the
backend's reason as a hint, tone neutral rather than positive. Tightening these
types is what exposed two latent `.toFixed()` crashes on parent-facing pages — a
backend that used to lie had been keeping its callers honest by accident.

---

## 14. Schema strategy: new tables via `create_all`, new columns via Alembic

**Context.** `SQLModel.metadata.create_all` runs at app boot and creates missing
**tables**. It never `ALTER`s an existing one.

**Decision.** Additive new tables land automatically. **Any new column on an
existing table requires an Alembic migration.**

**Why.** Without it, the code and every existing database silently disagree and
the module 500s at runtime.

**Consequence.** This rule has bitten repeatedly and is called out prominently in
ARCHITECTURE.md. A related trap: **do not declare a ForeignKey in a migration to
a table that `create_all` builds at boot** — Alembic runs first in the entrypoint,
so the constraint would exist on fresh databases and be absent on migrated ones.

---

## 15. Campus scoping needed its own helpers

**Context.** `require_campus_access` exists and sounds sufficient.

**Decision.** Added `resolve_scoped_campus_id` (reads narrow) and
`assert_campus_allowed` (writes naming a campus fail loudly) in
`src/security/school_ownership.py`.

**Why.** `require_campus_access` reads only path and query params — a `campus_id`
in the request **body is never checked**. And it rejects only an *explicit*
mismatch, so an unscoped request gave a campus-bound admin org-wide reach by
omitting the field. `generate_batch_salary_slips` filtered on
`payload.campus_id`: omit it and it generated slips for every campus.

**Consequence.** One shared implementation rather than each module growing its
own. An inverted case needed a dedicated guard in school settings:
`campus_id = None` is the **org-wide row every campus inherits**, so a
campus-bound admin writing it would change every other campus — an escalation
dressed as an omitted query parameter.

---

## 16. Each module is one nav entry with internal tabs

**Context.** The sidebar reached **55 entries**, 31 of them sub-screens appended
as flat siblings as each module was built.

**Decision.** One entry per module, opening a shell with its own tab strip. Tab
definitions live once in `apps/web/lib/school-modules.ts`.

**Why.** The flat structure actively hid which screens belonged together —
Attendance sat beside History, Absence notes, At-risk and Bulk marking as though
they were peers.

**Consequence.** 41 entries; the school section went 31 → 16. **Per-tab gating
survived**: a teacher opening Timetable still cannot see Generate. The module
root matches *exactly*, not by prefix — a prefix match would leave "Roll-call"
lit while you are on History. A module resolving to fewer than two visible tabs
renders no strip at all.

---

## 17. Unavailable is not the same as failed

**Context.** S3 is unconfigured, so class recording cannot work.

**Decision.** Recording reports `UNAVAILABLE` with a stated reason, distinct from
`FAILED`. The toggle is disabled with an explanation rather than hidden.

**Why.** Telling a teacher their recording *broke* when nobody ever configured
storage sends them chasing the wrong problem. Offering a button that cannot work
teaches people the buttons lie.

**Consequence.** The same distinction was applied to nurture channels: a
phone-only family with no SMS provider configured surfaces as **UNAVAILABLE**
rather than a silent `SKIPPED` that reads like a delivery decision. A school can
see "we cannot contact these families at all".

---

## 18. Identity and attribution come from the authenticated caller

**Context.** Several endpoints accepted `is_teacher`, `graded_by`, `approved_by`,
`participant_id`, `student_id` and `marked_by` from the request body.

**Decision.** All of them now derive from the authenticated principal.

**Why.** `is_teacher` in a live-class token body granted `room_admin` **and**
`room_record` — a student could flip one boolean and gain the ability to record a
room full of children. `approved_by` let a caller attribute their own approval to
someone else, defeating the audit column's entire purpose.

**Consequence.** Where a response echoes these values, it echoes what was
*granted*, not what was requested — a client told `is_teacher: true` while
holding a participant token would otherwise render host controls that every
action then fails against.
