# Backup and Restore

This system holds children's academic records, fee ledgers, attendance marks
and counselling notes. Until these scripts existed there was **no backup
tooling of any kind** — a single disk failure destroyed all of it permanently.

Two scripts:

| Script | Purpose |
|---|---|
| `scripts/backup.sh` | Timestamped, compressed, verified `pg_dump` with retention |
| `scripts/restore.sh` | Restore a dump into a named target, with a production guard |

---

## Running a backup

Everything is configured by environment variable. **No credential has a
default** — an unset password fails rather than silently connecting as the
local OS user and producing a wrong or empty dump.

```bash
export PGHOST=localhost
export PGPORT=5432
export PGUSER=csg_lms
export PGDATABASE=csg_lms
export PGPASSWORD='...'          # export it; never pass it on the command line
export BACKUP_DIR=/var/backups/csg-lms
export RETENTION_DAYS=14

./scripts/backup.sh
```

Against a Dockerised Postgres, run it inside the container:

```bash
docker exec \
  -e PGUSER=csg_lms -e PGDATABASE=csg_lms -e PGPASSWORD='...' \
  -e BACKUP_DIR=/var/backups/csg-lms \
  <postgres-container> bash /path/to/backup.sh
```

### What it guarantees

- **Fails loudly.** Every failure path exits non-zero, so a cron job or
  Dokploy schedule reports it. A backup that silently does nothing is worse
  than no backup, because it buys false confidence.
- **Verifies what it wrote.** `pg_dump` can exit 0 having produced a
  truncated file if the disk fills. The dump's table of contents is read back
  with `pg_restore --list` before it counts as successful.
- **Removes partial files.** A half-written dump is deleted rather than left
  to be mistaken for a real backup.
- **Prunes only after success.** Deleting yesterday's good backup because
  today's failed is the classic way to lose everything.
- **Never echoes the password.** It reaches `pg_dump` via `PGPASSWORD` in the
  environment, never on the command line where `ps` would show it.

---

## Restoring

Restoring is **destructive** — `pg_restore --clean` drops and recreates every
object in the target. The target is therefore never inferred; you must name it.

```bash
export PGUSER=csg_lms
export PGPASSWORD='...'

# Rehearsal / verification (safe)
./scripts/restore.sh \
  --file /var/backups/csg-lms/csg-lms-csg_lms-20260913T195002Z.dump \
  --target csg_restore_test

# Real recovery onto production (requires the explicit flag)
./scripts/restore.sh --file <dump> --target csg_lms_prod --force-production
```

`PRODUCTION_DB_NAMES` (default: `learnhouse csg_lms_prod`) lists the databases
that require `--force-production`. Set it to match your deployment.

The dump is verified as readable **before** the target is touched, so a corrupt
dump cannot destroy the database it was about to replace.

---

## Verifying a backup is good

A backup nobody has ever restored is not a backup — it is an untested
assumption. Rehearse it on a schedule, not just after an incident.

```bash
# 1. Restore into a scratch database
./scripts/restore.sh --file <dump> --target csg_restore_test

# 2. Compare row counts against the source
for t in user organization campus class_section student_enrollment; do
  src=$(psql -U "$PGUSER" -d "$PGDATABASE"     -t -A -c "SELECT count(*) FROM \"$t\";")
  dst=$(psql -U "$PGUSER" -d csg_restore_test  -t -A -c "SELECT count(*) FROM \"$t\";")
  printf '%-20s source=%-6s restored=%-6s %s\n' "$t" "$src" "$dst" \
    "$([ "$src" = "$dst" ] && echo MATCH || echo MISMATCH)"
done

# 3. Drop the scratch database
psql -U "$PGUSER" -d postgres -c 'DROP DATABASE csg_restore_test;'
```

Extend the table list to whatever matters most to you — `student_attendance`,
`sms_gradebook_entry`, `student_fee_voucher` and the counselling tables are
the ones whose loss would be unrecoverable.

### Verified on 2026-09-13

A full round trip was performed against the running dev database:

| Table | Source | Restored | |
|---|---|---|---|
| `user` | 5 | 5 | MATCH |
| `organization` | 1 | 1 | MATCH |
| `campus` | 1 | 1 | MATCH |
| `class_section` | 1 | 1 | MATCH |
| `student_enrollment` | 1 | 1 | MATCH |

123 tables restored, 1467 TOC entries, 540K compressed. The scratch database
was dropped afterwards and the dev database was untouched.

---

## Scheduling

Daily, outside teaching hours. Via cron:

```cron
30 2 * * *  PGUSER=csg_lms PGDATABASE=csg_lms PGPASSWORD='...' \
            BACKUP_DIR=/var/backups/csg-lms RETENTION_DAYS=14 \
            /opt/csg-lms/scripts/backup.sh >> /var/log/csg-backup.log 2>&1
```

Dokploy can also run this as a scheduled task against the Postgres service.

**Three things worth doing beyond a nightly dump:**

1. **Copy backups off the machine.** A dump on the same disk as the database
   does not survive the failure it exists for. Ship to object storage or
   another host.
2. **Alert on failure.** The script exits non-zero; something has to be
   watching. A silent cron failure is indistinguishable from success until
   the day you need the backup.
3. **Rehearse quarterly.** Run the verification above on a real dump and
   confirm the row counts. Schema changes, extensions and role differences all
   break restores in ways only a real restore reveals.

---

## Related: school onboarding

`scripts/seed_school.py` stands up a school from a config file — organization,
campus, academic year, terms, sections, grading scale and one school admin.

```bash
export CSG_SEED_ADMIN_PASSWORD='...'     # never written to the config file
cd apps/api && uv run python ../../scripts/seed_school.py \
  --config ../../scripts/my_school.yml --dry-run   # then without --dry-run
```

It is idempotent (safe to re-run), validates the entire config before writing
anything, and leaves unspecified fields **unset** rather than inventing
plausible values. See `scripts/example_school.yml`.
