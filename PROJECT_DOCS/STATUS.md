# Status — What's Actually Built

**Last verified:** 2026-09-12, against the code directly (file existence, real test runs, a real Docker deployment driven through a browser) — not carried forward from any prior report. See `context.md` for the original 2026-09-11 audit this supersedes; that file is kept for its module-by-module fabrication tally, but §4's "no code anywhere" verdict is now stale for eight of them: M13 pathways, M16 certificates, M20 gamification, M32 discipline, M33 alumni, M34 inventory, M36 hostel and M38 events/facilities all have routers mounted in `apps/api/src/router.py` and SQLModel tables behind them (created by `create_all` at startup — no Alembic revision covers them).

## Summary

| Area | Status |
|---|---|
| Base Learnhouse platform (auth, courses, org model, collab) | ✅ Real — upstream, not built by this project |
| SMS core (attendance, timetable, gradebook, fees, financials, HR, payroll, library, campus/enrollment) | ✅ Real backend logic, authenticated, unit-tested. Frontend wired to real API calls; shows empty states because there's no seeded demo data, not because it's fake. |
| Auth on SMS/RevOps/Tutor routers | ✅ Fixed — all 36 `sms_*`/`revops_*` routers require the Keycloak-shaped JWT (was 3-of-12 as of the 2026-09-11 audit). `sms_fee_webhooks` is the one deliberate exception: provider callbacks authenticate by a signature over the body, not a user principal. |
| AI RevOps (loop-funnel) | ✅ Real logic (lead scoring, SDR agent, drip engine, offer generator, stalled-lead loopback, consent tracking), unit-tested. Visual Flow Builder and landing-page editor **not started**. |
| AI Tutor (Student) | ✅ Real (subject-scoped, content/age guardrails, adaptive pacing via the mastery DAG, per-grade RAG segregation, Redis rate-limiting) |
| Teacher tools + Counseling module | ✅ Real (lesson-plan generation, coursework-hour allocation, report-card draft→sent lifecycle, psychologist session logging with the wiki-mandated 404-not-403 confidentiality rule) |
| Native mobile scaffold | ✅ Real (Expo/RN/NativeWind), Student + Teacher + Parent screens built for real against live endpoints; Staff has real Directory/Payroll/Today screens, with Tasks still a stub. Offline sync **not started**. |
| Video classrooms (LiveKit) | ⚠️ Code-complete, never run. `livekit-api==1.2.1` (`apps/api/pyproject.toml:53`), `@livekit/components-react` / `livekit-client` (`apps/web/package.json:39,110`), `live_classes` / `live_class_webhooks` mounted in `apps/api/src/router.py`, and a `livekit` service defined at `dokploy-compose.yml:264`. `generate_livekit_token()` (`apps/api/src/services/sms/live_class.py:38`) uses the real LiveKit SDK. What is missing is the run: no deployment has ever started that service, so nothing has been verified against a live SFU. |
| Gamification, alumni tracking, disciplinary tracking, certificates, pathways, inventory, hostel, events/facilities, parent AI digest | ⚠️ Routers exist and are mounted (`apps/api/src/router.py:766-815`; `ai_parent_digest` at `:392`) with SQLModel tables behind them. Web UI exists for alumni, discipline, gamification, pathways and certificates (`/dash/alumni`, `/dash/discipline`, `/dash/gamification`, `/dash/pathways`, `/dash/certificates-manager`); hostel, inventory, facilities and the parent digest are backend-only. |
| Transport and cafeteria | ❌ Not implemented — no router, model or route anywhere in the repo. |
| SCORM/xAPI as a CSG-built feature, homework auto-grading, lecture translation, dropout predictor | ❌ Not implemented — no code exists. (Some of these — course authoring, SCORM support — exist as genuine *upstream Learnhouse* features, but were never extended into anything CSG-specific and were originally, incorrectly, claimed as CSG deliverables.) |
| Real Keycloak deployment | ❌ Never started or verified. Realm export JSON exists but has never been confirmed to import cleanly; API JWT validation has never been checked against a live Keycloak instance. The dev-token bridge (`/dev-login`) that used to exist specifically because of this gap has since been **removed** — see `apps/api/src/security/school_principal.py:38-40`; superadmin impersonation (`POST /sms/identity/impersonate`) replaced it. |
| Production deployment (Dokploy) | ❌ A prior attempt was started and explicitly stopped before completion. Nothing from this repo is confirmed running on any server. `docker-compose.local.yml` (local only) is the only path that has been run to completion. |

## Explicitly open (tracked, not silently dropped)

From the original modular rebuild plan, still genuinely undecided or unbuilt:

1. **Postgres schema namespacing** (`sms.*`, `revops.*`, `ai.*` vs. one flat `public` schema) — deferred by choice, cheap now/expensive later if data accumulates.
2. **RevOps Visual Flow Builder** (drag-drop campaign routing) and the **landing-page/component-library editor** — sizable frontend features, not started.
3. **Lead-sourcing bias-correction tool** — its actual intended identity is unresolved even in the source meeting notes this project was built against; needs its own scoping pass before implementation, not a guess.
4. **`/v1/core/sync/delta` endpoint** and full **WatermelonDB offline sync** for mobile — the mobile app's local-first storage exists; the sync engine against the backend doesn't.
5. **AGPLv3 compliance decision** — raised early, never revisited. Matters if this is ever exposed as a network service to anyone outside internal testing (AGPLv3 §13 network-use clause).
6. **Real Keycloak** — whether/when to actually stand it up and cut over from the session-derived principal.

## Testing

```bash
cd apps/api
uv run pytest src/tests/sms src/tests/ai src/tests/test_app_lifespan.py src/tests/routers src/tests/test_root_router.py -q
```

Collection (`pytest --collect-only -q`, whole suite): **7007 tests**, plus one collection error in `src/tests/integration` (`ModuleNotFoundError: src.services.database`). `src/tests/security` alone: **20 failed, 1436 passed, 4 skipped** — the failures are in `test_file_response_containment.py`, `test_import_content_hardening.py`, `test_sqlite_storage_access.py` and `test_no_fabricated_averages.py`, i.e. file-storage/content-hardening and anti-fabrication tests, all outside the school layer. (Previously recorded here as 950 passed / 8 failed, all in `test_content_files_router.py`; that figure is stale.)

**Caveat carried forward from the original audit and still true:** this suite runs against mocked `AsyncSession` objects, not a real Postgres instance, and doesn't touch Keycloak or any external integration. It proves the business-logic functions are internally consistent — it does not prove the product works end-to-end. The Docker-driven browser testing recorded in [BUGFIXES_LOG.md](./BUGFIXES_LOG.md) is what actually caught the majority of user-facing bugs, precisely because it exercises paths (SSR, real Docker networking, a real login flow) the unit suite structurally cannot reach.
