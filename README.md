# CSG LMS

A school management system, LMS and AI layer built on a fork of
[Learnhouse](https://github.com/learnhouse/learnhouse) (AGPLv3 — Next.js +
FastAPI + Postgres).

This is a **separate, non-commercial experiment**, distinct from the official
CSG-LMS product specified in the sibling `CSG-LMS.wiki` repository (a different
NestJS/Drizzle architecture). That wiki is read-only reference here.

> **Before assuming anything works, read
> [`PROJECT_DOCS/KNOWN_GAPS.md`](./PROJECT_DOCS/KNOWN_GAPS.md).** It is a
> complete, verified list of what is *not* done. This project has a history of
> overstating completeness — eight fabricated-data incidents were found and
> removed during the build, and three tests were found asserting flaws as
> expected behaviour. The gaps document exists so that history does not repeat.

## What it does

Twenty school modules attached to Learnhouse's own dashboard, sharing its auth,
org model and design system:

**School operations** — campus and academic structure with year rollover,
admissions (lead funnel *and* application lifecycle), attendance with periods and
a pastoral queue, timetable with assisted generation, gradebook with report
cards, exams with seating and resits, fees with instalments and reconciliation,
financials, staff and payroll, library, counselling, messaging, cross-module
reports, school settings.

**Live classes** — LiveKit video, in-room chat, and Learnhouse Boards and
Playgrounds embedded as classroom tools. Also available as a course activity.

**AI** — a Socratic tutor with crisis classification and content guardrails, an
admissions RevOps funnel (SDR, nurture, research, marketing, copywriting agents),
a mastery knowledge graph, and parental consent infrastructure for minors' AI
use.

**Clients** — web (staff and learner shells) and an Expo mobile app.

## Quick start

```bash
docker compose -f docker-compose.local.yml -f docker-compose.livekit.yml up --build -d
```

The API entrypoint runs `alembic upgrade head` on startup, so schema migrations
apply automatically.

| | |
|---|---|
| Web | http://localhost:3000 |
| API | http://localhost:8000 |

See [`PROJECT_DOCS/LOCAL_SETUP.md`](./PROJECT_DOCS/LOCAL_SETUP.md) for
credentials and the non-obvious setup step.

**A school must be set up before most modules show anything.** Create a campus
first — every other module scopes against one. `scripts/seed_school.py` can stand
one up from a config file (see `scripts/example_school.yml`), though it has not
yet been run end to end against a real database.

## Tests

```bash
cd apps/api && uv run pytest src/tests/ -q          # backend
cd apps/web && npx tsc --noEmit -p tsconfig.json    # web types
cd apps/mobile && npx tsc --noEmit                  # mobile types
```

The school modules are covered by `src/tests/sms/` and `src/tests/ai/`
(**707 passing**). A set of media/file-storage hardening tests fails in this
environment; they are outside the school layer.

> The suite has shown order sensitivity under `pytest-randomly` — tests that pass
> in isolation can fail in a randomised run because of shared database state. A
> green run is not proof on its own.

## Backup and restore

```bash
./scripts/backup.sh
./scripts/restore.sh <dump-file> --target <database>
```

The restore path has been genuinely tested (dump → restore into a scratch
database → row counts compared). See
[`PROJECT_DOCS/BACKUP_RESTORE.md`](./PROJECT_DOCS/BACKUP_RESTORE.md).

## Repository layout

```
apps/
├── api/       FastAPI + SQLModel + Postgres (pgvector) + Redis + arq worker
├── web/       Next.js — Learnhouse UI plus the school modules
├── mobile/    Expo / React Native / NativeWind
├── collab/    Hocuspocus/Yjs collaboration service (upstream)
├── cli/       upstream CLI
└── e2e/       Playwright
scripts/       backup.sh, restore.sh, seed_school.py
PROJECT_DOCS/  documentation — start here
docker-compose.local.yml     local stack
docker-compose.livekit.yml   LiveKit override (carries a required ICE fix)
dokploy-compose.yml          production, via Dokploy
```

## Documentation

| Document | What it covers |
|---|---|
| [KNOWN_GAPS.md](./PROJECT_DOCS/KNOWN_GAPS.md) | **Read first.** What is not done, verified. |
| [ARCHITECTURE.md](./PROJECT_DOCS/ARCHITECTURE.md) | Shells, identity, authorization, schema strategy |
| [MODULES.md](./PROJECT_DOCS/MODULES.md) | Every module: routes, API prefix, gating, completeness |
| [DECISIONS.md](./PROJECT_DOCS/DECISIONS.md) | Why things are built the way they are |
| [WORK_LOG.md](./PROJECT_DOCS/WORK_LOG.md) | What was built, with commit hashes |
| [LOCAL_SETUP.md](./PROJECT_DOCS/LOCAL_SETUP.md) | Runbook |
| [BACKUP_RESTORE.md](./PROJECT_DOCS/BACKUP_RESTORE.md) | Backup and restore |
| [BUGFIXES_LOG.md](./PROJECT_DOCS/BUGFIXES_LOG.md) | Earlier bug history |

Commit messages in this repository are unusually detailed — they carry the
reasoning behind each decision and the things deliberately *not* built.
`git log` is worth reading directly.

## Status

Not ready for a real school with real children's data. The blockers are listed in
[KNOWN_GAPS.md](./PROJECT_DOCS/KNOWN_GAPS.md); the largest are that **email is
unconfigured by default** (so crisis alerts and fee reminders reach nobody out of
band), **no independent security review has been done**, and **offline sync does
not exist**, which blocks the mobile product.

## License

Base platform licensed under AGPLv3 (see `LICENSE`). Anything derived from it and
run as a network service must make its source available to users of that service
(AGPLv3 §13). This has not been formally addressed for this project.
