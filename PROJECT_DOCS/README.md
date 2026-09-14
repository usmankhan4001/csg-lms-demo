# Project docs — index

The verified account of this project. Separate from `docs/`, which is
Learnhouse's own upstream documentation site.

Everything here was checked against the code. Where a claim could not be
verified, it says so.

## Read in this order

1. **[KNOWN_GAPS.md](./KNOWN_GAPS.md)** — what is **not** done. Read this first.
   This project has a documented history of overstating completeness; this file
   exists to counter it.
2. **[MODULES.md](./MODULES.md)** — every module: what it does, its routes, its
   API prefix, its role gating, and its honest completeness.
3. **[ARCHITECTURE.md](./ARCHITECTURE.md)** — the two frontend shells, the
   identity model, the three authorization layers, feature toggles, and the
   schema strategy (**new columns require an Alembic migration** — this has
   bitten repeatedly).
4. **[DECISIONS.md](./DECISIONS.md)** — why things are built the way they are.
   Eighteen decisions with their reasoning, mostly cases where the obvious choice
   was wrong for a reason only visible in a real school.
5. **[WORK_LOG.md](./WORK_LOG.md)** — what was built, in order, with commit
   hashes.

## Reference

- **[LOCAL_SETUP.md](./LOCAL_SETUP.md)** — the runbook to get it running locally.
- **[BACKUP_RESTORE.md](./BACKUP_RESTORE.md)** — backup and restore procedure.
  The restore path has genuinely been tested.
- **[BUGFIXES_LOG.md](./BUGFIXES_LOG.md)** — earlier bug history with root
  causes. Worth checking before assuming something is broken.
- **[STATUS.md](./STATUS.md)** — an earlier point-in-time status snapshot.
  Superseded by KNOWN_GAPS.md and MODULES.md, kept for history.
- `../context.md` — the 2026-09-11 audit that first corrected a fabricated
  "100% complete" report from an earlier session. Historical.

## On the commit history

Commit messages in this repository are long and carry the real reasoning —
including corrections, things deliberately not built, and cases where an
instruction turned out to be wrong. They are the primary source for
DECISIONS.md and WORK_LOG.md, and are worth reading directly:

```bash
git log --format='%h %s%n%b' | less
```

## The standing rule

**Absence of data is never rendered as a value.** A rate with no data is
`null` with a stated reason, not `0%`. A student with no grades has no GPA, not
`4.0` and not `"F"`. A count of zero is a real answer and is not nulled.

Eight violations of this were found and removed during the build. If you are
adding a screen, this is the rule most likely to catch you.
