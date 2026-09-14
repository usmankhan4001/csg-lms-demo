#!/usr/bin/env bash
#
# CSG-LMS database backup.
#
# This system holds children's academic records, fee ledgers, attendance
# marks and counselling notes. Before this script existed there was no
# backup tooling of any kind, which meant a single disk failure destroyed
# all of it permanently.
#
# Design rules, each of which exists for a reason:
#
#   1. FAIL LOUDLY. A backup that silently does nothing is worse than no
#      backup at all, because it buys false confidence. Every failure path
#      exits non-zero so a cron job or Dokploy schedule reports it.
#   2. NEVER echo the password. It is passed to pg_dump via PGPASSWORD in
#      the environment, never on the command line (where it would show up
#      in `ps`) and never in log output.
#   3. VERIFY WHAT WAS WRITTEN. pg_dump can exit 0 having produced a
#      truncated file if the disk fills. The dump is listed back with
#      pg_restore -l before it is considered good.
#   4. PRUNE ONLY AFTER A VERIFIED SUCCESS. Deleting yesterday's good
#      backup because today's failed is the classic way to lose everything.
#
# Usage:
#   ./scripts/backup.sh
#
# Configuration is entirely by environment variable -- see the block below.
# Run it against a container by setting PGHOST to the mapped port, or run
# it inside the postgres container itself.

set -Eeuo pipefail

# --- configuration ---------------------------------------------------------
# No credential has a default. An unset password must fail, not silently try
# to connect as the local OS user and produce an empty or wrong dump.
PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5432}"
PGUSER="${PGUSER:?PGUSER must be set}"
PGDATABASE="${PGDATABASE:?PGDATABASE must be set}"
: "${PGPASSWORD:?PGPASSWORD must be set (export it; do not pass it on the command line)}"

BACKUP_DIR="${BACKUP_DIR:-/var/backups/csg-lms}"
# How many daily backups to keep. 14 is a fortnight: long enough that a
# problem noticed "sometime last week" is still recoverable.
RETENTION_DAYS="${RETENTION_DAYS:-14}"

TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DUMP_FILE="${BACKUP_DIR}/csg-lms-${PGDATABASE}-${TIMESTAMP}.dump"

log()  { printf '[backup] %s\n' "$*"; }
fail() { printf '[backup] ERROR: %s\n' "$*" >&2; exit 1; }

# Report the failing line rather than dying silently mid-script.
trap 'fail "aborted at line ${LINENO}"' ERR

# --- preflight -------------------------------------------------------------
command -v pg_dump    >/dev/null 2>&1 || fail "pg_dump not found on PATH"
command -v pg_restore >/dev/null 2>&1 || fail "pg_restore not found on PATH (needed to verify the dump)"

mkdir -p "${BACKUP_DIR}" || fail "cannot create backup directory ${BACKUP_DIR}"
[ -w "${BACKUP_DIR}" ]   || fail "backup directory ${BACKUP_DIR} is not writable"

log "backing up database '${PGDATABASE}' from ${PGHOST}:${PGPORT} as user '${PGUSER}'"

# --- dump ------------------------------------------------------------------
# Custom format (-Fc): compressed, and restorable selectively with
# pg_restore. Plain SQL would be larger and could not be partially restored.
#
# --no-owner / --no-privileges: the restore target may use a different role
# name than production. Ownership is re-established by the restoring user.
export PGPASSWORD
if ! pg_dump \
        --host="${PGHOST}" \
        --port="${PGPORT}" \
        --username="${PGUSER}" \
        --dbname="${PGDATABASE}" \
        --format=custom \
        --compress=9 \
        --no-owner \
        --no-privileges \
        --file="${DUMP_FILE}"; then
    # Remove the partial file so a half-written dump is never mistaken for a
    # real backup by the restore script or by a human reading the directory.
    rm -f "${DUMP_FILE}"
    fail "pg_dump failed; partial file removed"
fi

[ -s "${DUMP_FILE}" ] || { rm -f "${DUMP_FILE}"; fail "pg_dump produced an empty file"; }

# --- verify ----------------------------------------------------------------
# pg_restore -l reads the dump's table of contents. If the file is truncated
# or corrupt this fails, which catches the "disk filled up mid-dump" case
# that pg_dump itself can exit 0 on.
if ! TOC_LINES="$(pg_restore --list "${DUMP_FILE}" 2>/dev/null | grep -c ';' || true)"; then
    rm -f "${DUMP_FILE}"
    fail "dump verification failed: pg_restore could not read ${DUMP_FILE}"
fi
if [ "${TOC_LINES:-0}" -lt 1 ]; then
    rm -f "${DUMP_FILE}"
    fail "dump verification failed: table of contents is empty"
fi

SIZE="$(du -h "${DUMP_FILE}" | cut -f1)"
log "wrote ${DUMP_FILE} (${SIZE}, ${TOC_LINES} TOC entries)"

# --- prune -----------------------------------------------------------------
# Deliberately after verification: a failed backup must never cause an old
# good one to be deleted.
if [ "${RETENTION_DAYS}" -gt 0 ]; then
    PRUNED="$(find "${BACKUP_DIR}" -maxdepth 1 -name "csg-lms-${PGDATABASE}-*.dump" \
                   -type f -mtime "+${RETENTION_DAYS}" -print -delete | wc -l | tr -d ' ')"
    log "retention ${RETENTION_DAYS} days: pruned ${PRUNED} old backup(s)"
fi

REMAINING="$(find "${BACKUP_DIR}" -maxdepth 1 -name "csg-lms-${PGDATABASE}-*.dump" -type f | wc -l | tr -d ' ')"
log "OK - ${REMAINING} backup(s) retained in ${BACKUP_DIR}"
