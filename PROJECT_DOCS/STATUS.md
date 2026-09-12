# Status — What's Actually Built

**Last verified:** 2026-09-12, against the code directly (file existence, real test runs, a real Docker deployment driven through a browser) — not carried forward from any prior report. See `context.md` for the original 2026-09-11 audit this supersedes; that file is kept for its module-by-module fabrication tally (§4 there still accurately lists which of the originally-claimed 50 modules never had any code — that finding hasn't changed).

## Summary

| Area | Status |
|---|---|
| Base Learnhouse platform (auth, courses, org model, collab) | ✅ Real — upstream, not built by this project |
| SMS core (attendance, timetable, gradebook, fees, financials, HR, payroll, library, campus/enrollment) | ✅ Real backend logic, authenticated, unit-tested. Frontend wired to real API calls; shows empty states because there's no seeded demo data, not because it's fake. |
| Auth on SMS/RevOps/Tutor routers | ✅ Fixed — all 12 routers require the Keycloak-shaped JWT (was 3-of-12 as of the 2026-09-11 audit) |
| AI RevOps (loop-funnel) | ✅ Real logic (lead scoring, SDR agent, drip engine, offer generator, stalled-lead loopback, consent tracking), unit-tested. Visual Flow Builder and landing-page editor **not started**. |
| AI Tutor (Student) | ✅ Real (subject-scoped, content/age guardrails, adaptive pacing via the mastery DAG, per-grade RAG segregation, Redis rate-limiting) |
| Teacher tools + Counseling module | ✅ Real (lesson-plan generation, coursework-hour allocation, report-card draft→sent lifecycle, psychologist session logging with the wiki-mandated 404-not-403 confidentiality rule) |
| Native mobile scaffold | ✅ Real (Expo/RN/NativeWind), Student + Teacher screens built for real; Parent/Staff are stub shells. Offline sync **not started**. |
| Video classrooms (LiveKit) | ❌ Not implemented. No LiveKit dependency anywhere in the repo, no LiveKit service in the compose stack. `generate_livekit_token()` hand-crafts a JWT-shaped token with nothing running to redeem it against. |
| Gamification, SCORM/xAPI as a CSG-built feature, homework auto-grading, lecture translation, parent AI digest, dropout predictor, alumni tracking, disciplinary tracking, inventory/transport/hostel/cafeteria/events modules | ❌ Not implemented — no code exists. (Some of these — course authoring, SCORM support — exist as genuine *upstream Learnhouse* features, but were never extended into anything CSG-specific and were originally, incorrectly, claimed as CSG deliverables.) |
| Real Keycloak deployment | ❌ Never started or verified. Realm export JSON exists but has never been confirmed to import cleanly; API JWT validation has never been checked against a live Keycloak instance. The dev-token bridge (`/dev-login`) exists specifically because of this gap. |
| Production deployment (Dokploy) | ❌ A prior attempt was started and explicitly stopped before completion. Nothing from this repo is confirmed running on any server. `docker-compose.local.yml` (local only) is the only path that has been run to completion. |

## Explicitly open (tracked, not silently dropped)

From the original modular rebuild plan, still genuinely undecided or unbuilt:

1. **Postgres schema namespacing** (`sms.*`, `revops.*`, `ai.*` vs. one flat `public` schema) — deferred by choice, cheap now/expensive later if data accumulates.
2. **RevOps Visual Flow Builder** (drag-drop campaign routing) and the **landing-page/component-library editor** — sizable frontend features, not started.
3. **Lead-sourcing bias-correction tool** — its actual intended identity is unresolved even in the source meeting notes this project was built against; needs its own scoping pass before implementation, not a guess.
4. **`/v1/core/sync/delta` endpoint** and full **WatermelonDB offline sync** for mobile — the mobile app's local-first storage exists; the sync engine against the backend doesn't.
5. **AGPLv3 compliance decision** — raised early, never revisited. Matters if this is ever exposed as a network service to anyone outside internal testing (AGPLv3 §13 network-use clause).
6. **Real Keycloak** — whether/when to actually stand it up and cut over from the dev-token bridge.

## Testing

```bash
cd apps/api
uv run pytest src/tests/sms src/tests/ai src/tests/test_app_lifespan.py src/tests/routers src/tests/test_root_router.py -q
```

Last run: 950 passed, 8 failed. The 8 failures are all in `src/tests/routers/test_content_files_router.py`, confirmed pre-existing and unrelated to this project's work via `git stash`/`git checkout` A/B comparison against the very first commit.

**Caveat carried forward from the original audit and still true:** this suite runs against mocked `AsyncSession` objects, not a real Postgres instance, and doesn't touch Keycloak or any external integration. It proves the business-logic functions are internally consistent — it does not prove the product works end-to-end. The Docker-driven browser testing recorded in [BUGFIXES_LOG.md](./BUGFIXES_LOG.md) is what actually caught the majority of user-facing bugs, precisely because it exercises paths (SSR, real Docker networking, a real login flow) the unit suite structurally cannot reach.
