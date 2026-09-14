# Work log

What was built, in order, with commit hashes. Grouped by phase rather than
strictly by time, because several phases overlapped.

The commit messages themselves are the detailed record — they carry the
reasoning, the corrections, and the things that were deliberately *not* built.
`git log` is worth reading directly.

---

## Phase 0 — Foundations and structure

Before this, the school layer was a set of pages that largely did not call the
backend, living in a **second app shell** parallel to Learnhouse's own.

| Commit | What |
|---|---|
| `f89e010` | Attendance attached as a real Learnhouse dash module — the pattern proof |
| `657312f` | Every school module folded into Learnhouse's own shells |
| `880001f` | The school could never actually be created — fixed the setup chain |
| `c7e36f6` | Student enrolment into sections, so downstream modules have rosters |
| `7c6030f` | School dialogs rendered broken (Learnhouse `DialogContent` has no padding); nav grouped |
| `2c5aa4e` | The dead second app shell retired — `/student`, `/teacher`, `/parent` were still returning 200 |

The retirement in `2c5aa4e` needed care: `proxy.ts` redirected every
authenticated login to exactly those routes, so deleting them without repointing
would have 404'd every user at sign-in.

## Phase 0b — Migration history repair

| Commit | What |
|---|---|
| `7cb9375` | **Alembic had never once run successfully** in this project |

`alembic_version` did not exist. Every startup, `alembic upgrade head` failed
with "Multiple head revisions are present" and the entrypoint swallowed it. The
entire schema had been built by `create_all`. Ten branched heads were merged, a
duplicate revision id renamed, and the database baselined.

This mattered later: it is what made the `TYPE_LIVECLASS` enum, the attendance
period column and the fee instalment columns deliverable at all.

---

## Phase 1 — Security

A systemic audit, not a one-off fix.

| Commit | What |
|---|---|
| `9fc3e5b` | Anyone could clear any family's fees — every write in the fees router was open |
| `fcc2071` | **Any student could mint a live-class host token** with `room_admin` and `room_record` |
| `2c5aa4e` | 31 write endpoints accepted a `principal` and never used it |
| `2ca8121` | The sweep completed — 31 → **0** |
| `2d4d3ab` | Shared campus-scoping helpers, because `require_campus_access` misses request bodies |
| `87e9e6a` | **Every teacher could see which child disclosed self-harm** |
| `94ee214` | A live Gemini API key removed from tracked config |

The live-class one is the sharpest: `is_teacher` came from the request body, so
flipping one boolean granted the ability to moderate and **record a room full of
children**.

Five impersonation holes were closed alongside — `graded_by`, `approved_by`,
filing leave in a colleague's name, and a `fine_amount` override that let anyone
close someone else's library loan and zero their own fine.

---

## Phase 2 — Data-model corrections

Three faults that corrupted records every day they ran. Both affected tables held
**zero rows** at the time, which is why these came before features.

| Commit | What |
|---|---|
| `713af3c` | Attendance period dimension, grade-change history, sections scoped to academic year |

1. **Attendance had no period.** The unique key was `(student_id, section_id,
   date)`, so in a school running 6–8 periods, **taking period 5's register
   silently overwrote period 1's**. A student absent first thing and present
   after lunch ended the day looking present.
2. **Grade changes were unrecoverable** — one row per student per assessment,
   updated in place.
3. **Sections were not year-scoped**, which structurally blocked academic year
   rollover — the one operation every school performs annually.

Migration `03447a484193` delivered both columns and applied cleanly through the
container entrypoint — the first time migrations in this project did real work
rather than being repaired.

---

## Phase 3 — Compliance and deployability

The controls a regulator or insurer asks for first, none of which existed.

| Commit | What |
|---|---|
| `89c0bf2` | **Backups, restore and school onboarding** — there had been no backup tooling of any kind |
| `c06149a` | Parental consent for minors' AI, and a GDPR export that was not a lie |

`scripts/` had held exactly one file. A disk failure would have destroyed every
grade, fee record, attendance mark and counselling note. The restore was
**actually tested** — and the test caught two real bugs in the script on its
first run.

The GDPR export had been labelled "Full GDPR data export" while touching **zero**
school tables. It now covers 37, validated by a test asserting every declared
column exists on its model — which immediately caught a key mismatch that would
have silently returned nothing.

---

## Phase 4 — Operator layer

The machinery existed; the controls did not.

| Commit | What |
|---|---|
| `7268112` | Module toggles a school admin can actually flip |
| `1910d60` | School settings — grading scales and fee policy were hardcoded Python constants |

Eleven feature toggles were enforced by the backend and **nothing could change
them** — disabling a module meant hand-editing org config JSON in Postgres.

---

## Phase 5 — Module-by-module completion

Each module taken from "a page that exists" to "a product with its own screens,
flows and states".

| Commit | Module |
|---|---|
| `3707fb1` | Admissions → six screens (leads, detail, offers, campaigns, worklist) |
| `bf91794` | The admissions funnel closed — auto-acknowledge, channel routing, offer acceptance |
| `66c5f9f` | Admissions **application lifecycle** — documents, verification, assessment, decision |
| `66ffea1` | Attendance → excuses, pastoral queue, audit trail, bulk marking |
| `436094c` | Attendance UI → five screens |
| `10e2260` | **The honour-roll fabrication was still live, in the router** |
| `e8ed0c1` | Report-card studio, grade history UI |
| `a32e218` | Fees → instalments, reminders, reconciliation, concessions, refunds |
| `26516f8` | Timetable → assisted generation, lesson logs, conflict scanning |
| `1868b45` | Counselling UI — 9 endpoints that no counsellor could open |
| `f79ad2f` | Exam seating and resits, library holds |
| `bed54da` | Staff offboarding, appraisals, payroll separation of duties |

Notable finds along the way:

- **`10e2260`** — a GPA endpoint returning `4.0`, `"Good Standing"`,
  `honor_roll: true` for a student with **zero grades**, live in a *router*
  (which is why sweeps of the service file kept missing it). Worse, the real code
  path raised `AttributeError` on a field that does not exist, so **the only path
  that ever returned anything was the fabricated one.**
- The same commit found a parent opening their child's **sent** report card
  silently **rewriting** it — the generator upserts, and it backed a GET a parent
  could call.
- **`bf91794`** — a 9pm WhatsApp enquiry sat untouched until a human opened the
  CRM, and a phone-only family could never be contacted at all.

---

## Phase 6 — Information architecture

| Commit | What |
|---|---|
| `dcc092a` | One entry per module, a school dashboard, and the live-classes window |

The sidebar had reached **55 entries**, 31 of them sub-screens appended as flat
siblings as each module was built. Collapsed to 41 — the school section went 31 →
16 — with each module opening a tab strip.

The same commit replaced Learnhouse's course-authoring landing page with a
role-aware school dashboard, and added the live-classes management window (the
backend was complete; there had been no way to schedule a class or reach a
recording).

---

## Live classes, across phases

| Commit | What |
|---|---|
| `c129cef` | LiveKit rooms, webhooks, initial UI |
| `6c43b2b` | ICE candidates advertised the Docker-internal IP — nothing ever connected |
| `5ab2cd8` | Chat, plus Boards and Playgrounds embedded as in-class tools |
| `b8f27cc` | Scheduling and recording services |
| `dcc092a` | The management window |

Live class is also a first-class **course activity** (`TYPE_LIVECLASS`), which
required an enum migration — and was blocked until the Alembic repair in
`7cb9375` made migrations work at all.

---

## Mobile

| Commit | What |
|---|---|
| `0197c94` | Parent portal screens |
| `e28a22a` | **The app could not authenticate at all** |
| `68d6b2e` | Staff Today and Payroll built against real endpoints |

The auth break was total: the app pasted a locally-minted dev JWT, but
`dev_tokens.py` had been deleted and the principal now required a real session,
so every authenticated screen 401'd.

Two screens remain honest stubs because the backend does not exist for them.

---

## Testing

Backend test count over the session: **465 → 707**, all passing.

Three separate tests were found **asserting flaws as expected behaviour**:

1. A parent digest test pinning a hardcoded `96.0%` attendance.
2. `test_full_vision_pillars.py` demanding `unweighted_gpa == 4.0` for a student
   with no grades.
3. A payroll test walking generate → pay with **no approval step**, encoding the
   self-dealing path.

In each case the test was fixed, never the check.

Several agents proved their tests discriminate by **mutation** — removing the
guard, confirming exactly the expected test failed, then restoring. One caught a
**false negative** in its own `tsc` canary because the value it typed was `any`.
