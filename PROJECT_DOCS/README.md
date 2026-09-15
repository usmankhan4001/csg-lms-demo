# Project Documentation Index

The verified, structured documentation for the LMS & School Management System codebase (`learnhouse-dev`).

---

## 🧭 Core Documentation (Read in this order)

1. **[SYSTEM_DIAGRAMS_AND_FEATURES.md](./SYSTEM_DIAGRAMS_AND_FEATURES.md)** — **Master Visual & Technical Reference**: High-level topology diagram, dual-shell frontend layout, security & auth sequence flow, complete database Entity-Relationship Diagram (ERD), and full feature matrix.
2. **[KNOWN_GAPS.md](./KNOWN_GAPS.md)** — Honest record of what is **not** done or currently mocked.
3. **[MODULES.md](./MODULES.md)** — Module-by-module documentation: routes, API prefixes, role gating, and technical completeness.
4. **[ARCHITECTURE.md](./ARCHITECTURE.md)** — Deep-dive on the two frontend shells, identity resolution, 3-layer authorization, feature toggles, background workers, and schema migration strategies.
5. **[DECISIONS.md](./DECISIONS.md)** — Architectural Decision Records (ADRs) and domain reasoning for critical design choices.
6. **[WORK_LOG.md](./WORK_LOG.md)** — Chronological engineering log of changes and commit hashes.

---

## 🛠️ Operations & Infrastructure Reference

- **[LOCAL_SETUP.md](./LOCAL_SETUP.md)** — Local development environment runbook.
- **[DEPLOYMENT.md](./DEPLOYMENT.md)** — Dokploy and Docker Swarm production deployment guide.
- **[DEMO_STACK.md](./DEMO_STACK.md)** — Demo instance setup, seeding, and teardown instructions.
- **[BACKUP_RESTORE.md](./BACKUP_RESTORE.md)** — Tested database backup and restore runbook.
- **[OBJECT_STORAGE.md](./OBJECT_STORAGE.md)** — Cloudflare R2, AWS S3, and MinIO storage configuration.
- **[360_AUDIT_REPORT.md](./360_AUDIT_REPORT.md)** — Code-level 360° production readiness audit report.
- **[BUGFIXES_LOG.md](./BUGFIXES_LOG.md)** — Bug history, root causes, and regressions prevented.
- **[STATUS.md](./STATUS.md)** — Historical point-in-time status snapshot.
- **[CONTEXT_HISTORICAL.md](./CONTEXT_HISTORICAL.md)** — Historical context log from early codebase audit.

---

## 📜 Standing Rules & Guidelines

- **Absence of data is never rendered as a value.** A metric without data is `null` with a clear explanation, never `0%`. A student with no grades has `null` GPA, not `0.0` or `"F"`.
- **New database columns require an Alembic migration.** `SQLModel.metadata.create_all` creates new tables on startup, but will **never ALTER existing tables**.
- **Confidential records enforce 404-never-403.** For safeguarding (Counselling, Child Protection), unauthorised queries return empty results or 404 to avoid confirming record existence.
