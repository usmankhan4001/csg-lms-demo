#!/usr/bin/env python3
"""
==============================================================================
CSG-LMS Production PostgreSQL Automated Backup & Retention Tool
==============================================================================
Provides automated, verified pg_dump backups with local and S3/R2 retention.

Usage:
    python scripts/backup_postgres.py
    python scripts/backup_postgres.py --env-file .env.production
    python scripts/backup_postgres.py --retention-days 14 --s3-bucket my-backup-bucket
    python scripts/backup_postgres.py --verify-only /var/backups/csg-lms/dumpfile.dump
==============================================================================
"""

import os
import sys
import time
import json
import shutil
import hashlib
import argparse
import datetime
import subprocess
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path


class Color:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


def log_info(msg: str) -> None:
    print(f"{Color.CYAN}ℹ [backup-postgres]{Color.RESET} {msg}")


def log_ok(msg: str) -> None:
    print(f"{Color.GREEN}✔ [backup-postgres]{Color.RESET} {msg}")


def log_warn(msg: str) -> None:
    print(f"{Color.YELLOW}⚠ [backup-postgres]{Color.RESET} {msg}", file=sys.stderr)


def log_err(msg: str) -> None:
    print(f"{Color.RED}✖ [backup-postgres] ERROR:{Color.RESET} {msg}", file=sys.stderr)


def load_env_file(filepath: str) -> Dict[str, str]:
    """Parse key-value pairs from .env or .env.production."""
    env_vars: Dict[str, str] = {}
    if not os.path.exists(filepath):
        return env_vars
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                env_vars[k] = v
    return env_vars


def calculate_sha256(filepath: str) -> str:
    """Compute SHA-256 hex digest of a file."""
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def human_size(bytes_val: int) -> str:
    """Format bytes as human readable size."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if bytes_val < 1024.0:
            return f"{bytes_val:.2f} {unit}"
        bytes_val /= 1024.0
    return f"{bytes_val:.2f} PB"


class PostgresBackupManager:
    def __init__(self, config: Dict[str, Any]):
        self.host = config.get("host", "localhost")
        self.port = str(config.get("port", "5432"))
        self.user = config.get("user", "learnhouse")
        self.password = config.get("password", "")
        self.database = config.get("database", "learnhouse")
        self.backup_dir = Path(config.get("backup_dir", "/var/backups/csg-lms"))
        self.retention_days = int(config.get("retention_days", 14))

        self.s3_bucket = config.get("s3_bucket")
        self.s3_endpoint = config.get("s3_endpoint")
        self.s3_access_key = config.get("s3_access_key")
        self.s3_secret_key = config.get("s3_secret_key")
        self.s3_region = config.get("s3_region", "auto")
        self.s3_prefix = config.get("s3_prefix", "postgres-backups")
        self.s3_retention_days = int(config.get("s3_retention_days", 30))
        self.verbose = config.get("verbose", False)

    def check_prerequisites(self) -> Tuple[bool, List[str]]:
        errors = []
        if not shutil.which("pg_dump"):
            errors.append("pg_dump command not found on PATH. Install postgresql-client.")
        if not shutil.which("pg_restore"):
            errors.append("pg_restore command not found on PATH.")
        if not self.password:
            errors.append("Database password is not set (POSTGRES_PASSWORD or PGPASSWORD).")
        try:
            self.backup_dir.mkdir(parents=True, exist_ok=True)
            test_file = self.backup_dir / ".write_test"
            test_file.touch()
            test_file.unlink()
        except Exception as e:
            errors.append(f"Backup directory {self.backup_dir} is not writable: {e}")
        return (len(errors) == 0, errors)

    def run_backup(self) -> Dict[str, Any]:
        """Execute pg_dump with integrity check and manifest creation."""
        timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        filename = f"csg-lms-{self.database}-{timestamp}.dump"
        dump_path = self.backup_dir / filename
        meta_path = self.backup_dir / f"{filename}.meta.json"

        env = os.environ.copy()
        env["PGPASSWORD"] = self.password

        log_info(f"Starting pg_dump for database '{self.database}' at {self.host}:{self.port}...")
        start_time = time.perf_counter()

        cmd = [
            "pg_dump",
            "--host", self.host,
            "--port", self.port,
            "--username", self.user,
            "--dbname", self.database,
            "--format=custom",
            "--compress=9",
            "--no-owner",
            "--no-privileges",
            "--file", str(dump_path)
        ]

        try:
            res = subprocess.run(
                cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )
        except subprocess.CalledProcessError as e:
            if dump_path.exists():
                dump_path.unlink()
            err_msg = e.stderr.strip() or str(e)
            log_err(f"pg_dump failed: {err_msg}")
            return {
                "success": False,
                "error": f"pg_dump failed: {err_msg}",
                "timestamp": timestamp
            }

        duration = time.perf_counter() - start_time

        if not dump_path.exists() or dump_path.stat().st_size == 0:
            if dump_path.exists():
                dump_path.unlink()
            log_err("pg_dump produced an empty or missing output file.")
            return {
                "success": False,
                "error": "Empty dump produced",
                "timestamp": timestamp
            }

        # Verify dump integrity
        log_info("Verifying dump TOC integrity via pg_restore...")
        verify_ok, toc_count, verify_err = self.verify_dump(str(dump_path))
        if not verify_ok:
            if dump_path.exists():
                dump_path.unlink()
            log_err(f"Dump verification failed: {verify_err}")
            return {
                "success": False,
                "error": f"Verification failed: {verify_err}",
                "timestamp": timestamp
            }

        size_bytes = dump_path.stat().st_size
        size_str = human_size(size_bytes)
        sha256_hash = calculate_sha256(str(dump_path))

        manifest = {
            "database": self.database,
            "host": self.host,
            "port": int(self.port),
            "timestamp": timestamp,
            "file_name": filename,
            "file_path": str(dump_path.resolve()),
            "size_bytes": size_bytes,
            "size_human": size_str,
            "sha256": sha256_hash,
            "toc_entries": toc_count,
            "duration_seconds": round(duration, 2),
            "status": "VERIFIED_SUCCESS",
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }

        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        log_ok(f"Backup created & verified: {filename} ({size_str}, {toc_count} TOC entries, SHA256: {sha256_hash[:16]}...)")

        # S3 Upload
        s3_status = None
        if self.s3_bucket and self.s3_access_key and self.s3_secret_key:
            log_info(f"Uploading backup to s3://{self.s3_bucket}/{self.s3_prefix}/{filename}...")
            s3_status = self.upload_to_s3(str(dump_path), str(meta_path))

        # Local Pruning
        pruned_count = self.prune_local()

        manifest["s3_upload"] = s3_status
        manifest["local_pruned"] = pruned_count
        manifest["success"] = True
        return manifest

    def verify_dump(self, dump_path: str) -> Tuple[bool, int, Optional[str]]:
        """Verify dump file integrity using pg_restore --list."""
        cmd = ["pg_restore", "--list", dump_path]
        try:
            res = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )
            toc_lines = [line for line in res.stdout.splitlines() if ";" in line]
            if len(toc_lines) == 0:
                return (False, 0, "No TOC entries found in dump.")
            return (True, len(toc_lines), None)
        except subprocess.CalledProcessError as e:
            return (False, 0, e.stderr.strip() or str(e))
        except Exception as e:
            return (False, 0, str(e))

    def upload_to_s3(self, dump_path: str, meta_path: Optional[str] = None) -> Dict[str, Any]:
        """Upload dump and metadata to S3 / Cloudflare R2 / MinIO."""
        filename = Path(dump_path).name
        s3_key = f"{self.s3_prefix}/{filename}".lstrip("/")
        meta_key = f"{self.s3_prefix}/{filename}.meta.json".lstrip("/")

        try:
            import boto3
            from botocore.config import Config

            session_kwargs = {
                "aws_access_key_id": self.s3_access_key,
                "aws_secret_access_key": self.s3_secret_key,
            }
            if self.s3_region:
                session_kwargs["region_name"] = self.s3_region

            client_kwargs = {}
            if self.s3_endpoint:
                client_kwargs["endpoint_url"] = self.s3_endpoint

            s3_client = boto3.client(
                "s3",
                **session_kwargs,
                config=Config(signature_version="s3v4"),
                **client_kwargs
            )

            # Upload dump
            s3_client.upload_file(dump_path, self.s3_bucket, s3_key)
            log_ok(f"Uploaded dump to s3://{self.s3_bucket}/{s3_key}")

            # Upload metadata manifest
            if meta_path and os.path.exists(meta_path):
                s3_client.upload_file(meta_path, self.s3_bucket, meta_key)
                log_ok(f"Uploaded manifest to s3://{self.s3_bucket}/{meta_key}")

            # Prune old S3 backups
            s3_pruned = self.prune_s3(s3_client)

            return {
                "uploaded": True,
                "bucket": self.s3_bucket,
                "key": s3_key,
                "pruned": s3_pruned
            }
        except ImportError:
            log_warn("boto3 is not installed. Attempting upload via AWS CLI...")
            if shutil.which("aws"):
                env = os.environ.copy()
                env["AWS_ACCESS_KEY_ID"] = self.s3_access_key or ""
                env["AWS_SECRET_ACCESS_KEY"] = self.s3_secret_key or ""
                if self.s3_region:
                    env["AWS_DEFAULT_REGION"] = self.s3_region

                cmd_args = ["aws", "s3", "cp", dump_path, f"s3://{self.s3_bucket}/{s3_key}"]
                if self.s3_endpoint:
                    cmd_args.extend(["--endpoint-url", self.s3_endpoint])
                subprocess.run(cmd_args, env=env, check=True)
                log_ok(f"Uploaded via AWS CLI to s3://{self.s3_bucket}/{s3_key}")
                return {"uploaded": True, "bucket": self.s3_bucket, "key": s3_key}
            else:
                log_err("Neither boto3 nor aws CLI is available for S3 upload.")
                return {"uploaded": False, "error": "No S3 tool available"}
        except Exception as e:
            log_err(f"S3 upload failed: {e}")
            return {"uploaded": False, "error": str(e)}

    def prune_local(self) -> int:
        """Prune local dumps older than retention_days."""
        if self.retention_days <= 0:
            return 0
        cutoff = time.time() - (self.retention_days * 86400)
        pruned_count = 0

        for item in self.backup_dir.glob(f"csg-lms-{self.database}-*.dump*"):
            if item.is_file():
                if item.stat().st_mtime < cutoff:
                    try:
                        item.unlink()
                        pruned_count += 1
                        if self.verbose:
                            log_info(f"Pruned local backup: {item.name}")
                    except Exception as e:
                        log_warn(f"Failed to prune {item.name}: {e}")

        if pruned_count > 0:
            log_info(f"Pruned {pruned_count} local backup file(s) older than {self.retention_days} days.")
        return pruned_count

    def prune_s3(self, s3_client: Any) -> int:
        """Prune remote S3 backups older than s3_retention_days."""
        if self.s3_retention_days <= 0:
            return 0
        cutoff_date = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=self.s3_retention_days)
        pruned_count = 0

        try:
            paginator = s3_client.get_paginator("list_objects_v2")
            prefix = f"{self.s3_prefix}/csg-lms-{self.database}-"
            for page in paginator.paginate(Bucket=self.s3_bucket, Prefix=prefix):
                for obj in page.get("Contents", []):
                    last_modified = obj.get("LastModified")
                    if last_modified and last_modified < cutoff_date:
                        key = obj["Key"]
                        s3_client.delete_object(Bucket=self.s3_bucket, Key=key)
                        pruned_count += 1
                        if self.verbose:
                            log_info(f"Pruned S3 object: {key}")
            if pruned_count > 0:
                log_info(f"Pruned {pruned_count} remote S3 backup file(s) older than {self.s3_retention_days} days.")
        except Exception as e:
            log_warn(f"S3 pruning warning: {e}")
        return pruned_count


def main():
    parser = argparse.ArgumentParser(description="CSG-LMS PostgreSQL Automated Backup & Retention Tool")
    parser.add_argument("--env-file", default=".env.production", help="Path to environment file")
    parser.add_argument("--host", help="PostgreSQL host")
    parser.add_argument("--port", help="PostgreSQL port")
    parser.add_argument("--user", help="PostgreSQL user")
    parser.add_argument("--database", help="PostgreSQL database name")
    parser.add_argument("--backup-dir", help="Local backup directory path")
    parser.add_argument("--retention-days", type=int, help="Local retention days")
    parser.add_argument("--s3-bucket", help="S3 Bucket Name")
    parser.add_argument("--s3-endpoint", help="S3 Endpoint URL (for Cloudflare R2 / MinIO)")
    parser.add_argument("--s3-prefix", help="S3 Storage prefix")
    parser.add_argument("--s3-retention-days", type=int, help="S3 retention days")
    parser.add_argument("--upload-only", help="Upload a specific existing dump file to S3")
    parser.add_argument("--meta-file", help="Path to metadata JSON for upload-only")
    parser.add_argument("--verify-only", help="Verify integrity of an existing dump file")
    parser.add_argument("--json", action="store_true", help="Output JSON results")
    parser.add_argument("--verbose", action="store_true", help="Verbose debug logging")

    args = parser.parse_args()

    # Load environment variables
    env_vars = load_env_file(args.env_file)
    if not env_vars and os.path.exists(".env"):
        env_vars = load_env_file(".env")

    # Combine CLI args and env vars
    config = {
        "host": args.host or env_vars.get("POSTGRES_HOST") or env_vars.get("PGHOST") or "localhost",
        "port": args.port or env_vars.get("POSTGRES_PORT") or env_vars.get("PGPORT") or "5432",
        "user": args.user or env_vars.get("POSTGRES_USER") or env_vars.get("PGUSER") or "learnhouse",
        "password": os.environ.get("POSTGRES_PASSWORD") or env_vars.get("POSTGRES_PASSWORD") or env_vars.get("PGPASSWORD") or "",
        "database": args.database or env_vars.get("POSTGRES_DB") or env_vars.get("PGDATABASE") or "learnhouse",
        "backup_dir": args.backup_dir or env_vars.get("BACKUP_DIR") or "/var/backups/csg-lms",
        "retention_days": args.retention_days or int(env_vars.get("RETENTION_DAYS", 14)),
        "s3_bucket": args.s3_bucket or env_vars.get("S3_BUCKET_NAME") or env_vars.get("AWS_S3_BUCKET"),
        "s3_endpoint": args.s3_endpoint or env_vars.get("S3_ENDPOINT_URL") or env_vars.get("AWS_ENDPOINT_URL"),
        "s3_access_key": env_vars.get("S3_ACCESS_KEY_ID") or env_vars.get("AWS_ACCESS_KEY_ID"),
        "s3_secret_key": env_vars.get("S3_SECRET_ACCESS_KEY") or env_vars.get("AWS_SECRET_ACCESS_KEY"),
        "s3_region": env_vars.get("S3_REGION") or env_vars.get("AWS_DEFAULT_REGION", "auto"),
        "s3_prefix": args.s3_prefix or env_vars.get("S3_PREFIX", "postgres-backups"),
        "s3_retention_days": args.s3_retention_days or int(env_vars.get("S3_RETENTION_DAYS", 30)),
        "verbose": args.verbose
    }

    manager = PostgresBackupManager(config)

    # Handle verify-only
    if args.verify_only:
        ok, toc_count, err = manager.verify_dump(args.verify_only)
        if ok:
            log_ok(f"Verification PASSED: {args.verify_only} ({toc_count} TOC entries)")
            sys.exit(0)
        else:
            log_err(f"Verification FAILED: {err}")
            sys.exit(1)

    # Handle upload-only
    if args.upload_only:
        res = manager.upload_to_s3(args.upload_only, args.meta_file)
        if args.json:
            print(json.dumps(res, indent=2))
        sys.exit(0 if res.get("uploaded") else 1)

    # Standard Backup Flow
    ok, errors = manager.check_prerequisites()
    if not ok:
        for err in errors:
            log_err(err)
        sys.exit(1)

    result = manager.run_backup()
    if args.json:
        print(json.dumps(result, indent=2))

    sys.exit(0 if result.get("success") else 1)


if __name__ == "__main__":
    main()
