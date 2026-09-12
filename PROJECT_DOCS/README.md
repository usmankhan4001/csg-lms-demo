# Project Docs — Index

This folder is the honest, current account of this project — separate from `docs/`, which is Learnhouse's own upstream documentation site (a full Next.js app), not project notes.

Read in this order:

1. **[STATUS.md](./STATUS.md)** — what's actually built vs. stubbed vs. never started, right now.
2. **[ARCHITECTURE.md](./ARCHITECTURE.md)** — how it's built: module layout, the two-auth-system split, Docker networking, the Next.js 16 `proxy.ts` rename gotcha.
3. **[LOCAL_SETUP.md](./LOCAL_SETUP.md)** — the verified, tested runbook to get it running locally.
4. **[BUGFIXES_LOG.md](./BUGFIXES_LOG.md)** — every real bug found so far, with root cause. Read this before assuming something is broken — it might already be a documented, understood trap.

`../context.md` is the prior audit (2026-09-11) that first corrected a fabricated "100% complete" status report from an earlier AI session. It's kept for its detailed module-by-module fabrication tally; STATUS.md is the current source of truth for what's built now.
