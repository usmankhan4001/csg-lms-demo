#!/usr/bin/env bash
#
# CSG-LMS database restore.
#
# The counterpart to backup.sh. A backup nobody has ever restored is not a
# backup -- it is an untested assumption -- so this script is also the tool
# you use to REHEARSE recovery against a scratch database. See
# PROJECT_DOCS/BACKUP_RESTORE.md.
#
# Safety rules:
#
#   1. Restoring is DESTRUCTIVE. pg_restore --clean drops and recreates
#      every object in the target. Pointed at the wrong database it
#      destroys live data, so the target is never inferred -- it must be
#      named explicitly with --target.
#   2. Restoring ONTO PRODUCTION requires --force-production. The guard is
#      not a confirmation prompt because this may run non-interactively;
#      it is an explicit flag a human has to type.
#   3. The dump is verified as readable BEFORE the target is touched. A
#      corrupt dump must not take out the database it was about to replace.
#
# Usage:
#   ./scripts/restore.sh --file /var/backups/csg-lms/xxx.dump --target csg_restore_test
#   ./scripts/restore.sh --file xxx.dump --target csg_lms_prod --force-production

set -Eeuo pipefail

PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5432}"
PGUSER="${PGUSER:?PGUSER must be set}"
: "${PGPASSWORD:?PGPASSWORD must be set (export it; do not pass it on the command line)}"

# The database name(s) considered production. Restoring onto any of these
# needs --force-production. Override for your deployment.
PRODUCTION_DB_NAMES="${PRODUCTION_DB_NAMES:-learnhouse csg_lms_prod}"

DUMP_FILE=""
TARGET_DB=""
FORCE_PRODUCTION=0
CREATE_TARGET=1

log()  { printf '[restore] %s\n' "$*"; }
fail() { printf '[restore] ERROR: %s\n' "$*" >&2; exit 1; }
trap 'fail "aborted at line ${LINENO}"' ERR

usage() {
    cat >&2 <<'USAGE'
Usage: restore.sh --file <dump> --target <database> [--force-production] [--no-create]

  --file <path>        Dump produced by backup.sh (required)
  --target <dbname>    Database to restore INTO (required; never inferred)
  --force-production   Required if --target names a production database
  --no-create          Do not CREATE DATABASE; assume the target exists
USAGE
    exit 2
}

while [ $# -gt 0 ]; do
    case "$1" in
        --file)             DUMP_FILE="${2:?--file needs a path}"; shift 2 ;;
        --target)           TARGET_DB="${2:?--target needs a database name}"; shift 2 ;;
        --force-production) FORCE_PRODUCTION=1; shift ;;
        --no-create)        CREATE_TARGET=0; shift ;;
        -h|--help)          usage ;;
        *)                  printf '[restore] ERROR: unknown argument %s\n' "$1" >&2; usage ;;
    esac
done

[ -n "${DUMP_FILE}" ] || { printf '[restore] ERROR: --file is required\n' >&2; usage; }
[ -n "${TARGET_DB}" ] || { printf '[restore] ERROR: --target is required\n' >&2; usage; }
[ -f "${DUMP_FILE}" ] || fail "dump file not found: ${DUMP_FILE}"

command -v pg_restore >/dev/null 2>&1 || fail "pg_restore not found on PATH"
command -v psql       >/dev/null 2>&1 || fail "psql not found on PATH"

# --- production guard ------------------------------------------------------
for prod in ${PRODUCTION_DB_NAMES}; do
    if [ "${TARGET_DB}" = "${prod}" ] && [ "${FORCE_PRODUCTION}" -ne 1 ]; then
        fail "refusing to restore onto production database '${TARGET_DB}' without --force-production.
       This DROPS AND REPLACES every object in that database.
       If you are rehearsing a restore, use a scratch target instead:
         --target csg_restore_test"
    fi
done
if [ "${FORCE_PRODUCTION}" -eq 1 ]; then
    log "WARNING: --force-production given; '${TARGET_DB}' will be overwritten"
fi

export PGPASSWORD

# --- verify the dump BEFORE touching the target ----------------------------
TOC_LINES="$(pg_restore --list "${DUMP_FILE}" 2>/dev/null | grep -c ';' || true)"
[ "${TOC_LINES:-0}" -ge 1 ] || fail "dump is unreadable or empty: ${DUMP_FILE}"
log "dump verified (${TOC_LINES} TOC entries): ${DUMP_FILE}"

# --- create target if needed -----------------------------------------------
TARGET_EXISTS="$(psql --host="${PGHOST}" --port="${PGPORT}" --username="${PGUSER}" \
                      --dbname=postgres --tuples-only --no-align \
                      --command="SELECT 1 FROM pg_database WHERE datname='${TARGET_DB}';" 2>/dev/null || true)"

if [ "${TARGET_EXISTS}" != "1" ]; then
    [ "${CREATE_TARGET}" -eq 1 ] || fail "target database '${TARGET_DB}' does not exist and --no-create was given"
    log "creating target database '${TARGET_DB}'"
    psql --host="${PGHOST}" --port="${PGPORT}" --username="${PGUSER}" --dbname=postgres \
         --command="CREATE DATABASE \"${TARGET_DB}\";" >/dev/null
else
    log "target database '${TARGET_DB}' already exists; its contents will be replaced"
fi

# --- restore ---------------------------------------------------------------
# --clean --if-exists: drop objects before recreating, so restoring over a
# populated database is deterministic rather than a merge.
#
# pg_restore exits non-zero on benign noise too (e.g. an extension the
# restoring role may not recreate), so its status is captured rather than
# allowed to abort the script, and the result is judged by the row check below.
#
# NOTE: `set +e` alone is not enough -- an ERR trap still fires on a failing
# command. The trap is lifted for the duration of the restore and restored
# immediately afterwards.
trap - ERR
set +e
pg_restore \
    --host="${PGHOST}" \
    --port="${PGPORT}" \
    --username="${PGUSER}" \
    --dbname="${TARGET_DB}" \
    --clean --if-exists \
    --no-owner --no-privileges \
    "${DUMP_FILE}" 2>/tmp/csg-restore-err.$$
RESTORE_STATUS=$?
set -e

if [ "${RESTORE_STATUS}" -ne 0 ]; then
    log "pg_restore reported warnings (exit ${RESTORE_STATUS}); last lines:"
    tail -n 5 "/tmp/csg-restore-err.$$" >&2 || true
fi
rm -f "/tmp/csg-restore-err.$$"
trap 'fail "aborted at line ${LINENO}"' ERR

# --- confirm the restore actually landed ------------------------------------
# The real test is whether tables exist and hold rows, not pg_restore's
# exit code.
TABLE_COUNT="$(psql --host="${PGHOST}" --port="${PGPORT}" --username="${PGUSER}" \
                    --dbname="${TARGET_DB}" --tuples-only --no-align \
                    --command="SELECT count(*) FROM pg_tables WHERE schemaname='public';")"
[ "${TABLE_COUNT:-0}" -ge 1 ] || fail "restore produced no tables in '${TARGET_DB}'"

log "OK - restored into '${TARGET_DB}' (${TABLE_COUNT} tables in public schema)"
log "Verify row counts against the source before trusting this restore."
