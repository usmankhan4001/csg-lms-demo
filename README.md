# CSG LMS — Experimental Fork

An experiment in how far a fork of [Learnhouse](https://github.com/learnhouse/learnhouse) (AGPLv3 — Next.js + FastAPI + Postgres) can be extended toward a functioning School Management System + AI RevOps + AI Tutor platform, for internal, non-commercial evaluation.

This is **not** the official CSG-LMS product (that's a separate NestJS/Drizzle system, specified in the sibling `CSG-LMS.wiki` repository) — it's a parallel experiment to see what's achievable on top of an existing open-source LMS instead of building everything from zero.

**Read [`PROJECT_DOCS/README.md`](./PROJECT_DOCS/README.md) before assuming anything about this codebase.** It's the honest, current account of what's real, what's stubbed, and what's never been started — an earlier AI-assisted session on this project reported fabricated "100% complete" status for work that didn't exist, and the docs there exist specifically to replace that with something verified.

## Quick start

```bash
docker compose -f docker-compose.local.yml up --build -d
```

Then see [`PROJECT_DOCS/LOCAL_SETUP.md`](./PROJECT_DOCS/LOCAL_SETUP.md) for login credentials and how to reach the SMS dashboards (there's a real, non-obvious extra step — the doc explains why).

## What's actually here

- **Base platform**: real, working Learnhouse — course authoring, org/auth model, real-time collaboration. Upstream code, not built by this project.
- **Custom layer**: School Management System modules (attendance, timetable, gradebook, fees, financials, HR, payroll, library, multi-campus), an AI-driven RevOps admissions funnel, an AI Socratic tutor (student + teacher + counseling), and role-based portal UIs (Student/Teacher/Parent/Campus Admin). Backend logic and auth are real and unit-tested; see [`PROJECT_DOCS/STATUS.md`](./PROJECT_DOCS/STATUS.md) for exactly what's wired to real data vs. still empty for lack of seed data.
- **Not built**: video classrooms (no LiveKit dependency exists anywhere despite earlier claims), gamification, SCORM as a CSG feature, automated homework grading, lecture translation, and several other modules that were listed in an earlier fabricated spec but have zero code. Full list in [`PROJECT_DOCS/STATUS.md`](./PROJECT_DOCS/STATUS.md).

## Repository layout

```
learnhouse-dev/
├── apps/
│   ├── web/       # Next.js 16 frontend — Learnhouse's own pages + CSG (dashboard) portals
│   ├── api/       # FastAPI backend — Learnhouse's own routers + sms_*/revops_*/ai_* modules
│   ├── collab/    # Hocuspocus/Yjs real-time collaboration (upstream Learnhouse)
│   ├── mobile/    # Expo/React Native scaffold for the CSG portals
│   └── e2e/       # Playwright test scaffold
├── PROJECT_DOCS/  # This project's real, current documentation — start here
├── context.md     # The original fabrication-correcting audit (2026-09-11) — historical
├── docker-compose.local.yml   # The only deployment path actually run end-to-end
├── docker-compose.prod.yml    # Defined, never run to completion
└── dokploy-compose.yml        # Defined, never run to completion
```

## License

Base platform licensed under AGPLv3 (see `LICENSE`) — anything derived from it and run as a network service must make its source available to users of that service (AGPLv3 §13). This has not yet been formally addressed for this project; see the open items in [`PROJECT_DOCS/STATUS.md`](./PROJECT_DOCS/STATUS.md).
