#!/usr/bin/env python3
"""
CSG LMS - Cross-Platform Integration Test Runner
================================================
Runs integration tests against real PostgreSQL if available, or in-memory
SQLite fallback. Works across Windows, macOS, and Linux.
"""

import os
import sys
import subprocess
from pathlib import Path


def main():
    script_dir = Path(__file__).resolve().parent
    root_dir = script_dir.parent
    api_dir = root_dir / "apps" / "api"

    print("=" * 60)
    print(" Starting CSG LMS API Integration Test Suite")
    print("=" * 60)

    # Set up environment
    env = os.environ.copy()
    env["TESTING"] = "true"
    env["LEARNHOUSE_DISABLE_EE"] = "1"
    env["LEARNHOUSE_DEMO_ENABLED"] = "0"
    env["LEARNHOUSE_AUTH_JWT_SECRET_KEY"] = "integration-test-secret-key-32chars-min!"

    # Ensure api_dir is on PYTHONPATH
    current_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{api_dir}{os.pathsep}{current_pythonpath}" if current_pythonpath else str(api_dir)

    pg_url = env.get("TEST_DATABASE_URL") or env.get("POSTGRES_TEST_URL") or env.get("DATABASE_URL")
    if pg_url and ("postgres" in pg_url or "postgresql" in pg_url):
        print(f"Targeting PostgreSQL database: {pg_url}")
    else:
        print("No PostgreSQL database URL configured; using high-speed async SQLite fallback.")

    test_target = "src/tests/integration"
    extra_args = sys.argv[1:]

    # Check for uv / poetry / python -m pytest
    cmd = [sys.executable, "-m", "pytest", test_target, "-v", "--tb=short"] + extra_args

    print(f"Running command: {' '.join(cmd)} (cwd: {api_dir})")
    print("-" * 60)

    result = subprocess.run(cmd, cwd=str(api_dir), env=env)
    if result.returncode == 0:
        print("=" * 60)
        print(" [PASS] Integration Test Suite Completed Successfully!")
        print("=" * 60)
    else:
        print("=" * 60)
        print(f" [FAIL] Integration Tests Failed with exit code {result.returncode}")
        print("=" * 60)

    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
