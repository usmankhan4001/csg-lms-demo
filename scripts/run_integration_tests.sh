#!/usr/bin/env bash
# =============================================================================
# CSG LMS - Integration Test Runner
# =============================================================================
# Runs integration tests against real PostgreSQL if available, or in-memory
# SQLite fallback.
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
API_DIR="${ROOT_DIR}/apps/api"

echo "========================================================"
echo " Starting CSG LMS API Integration Test Suite"
echo "========================================================"

cd "${API_DIR}"

export TESTING="true"
export PYTHONPATH="${API_DIR}:${PYTHONPATH}"
export LEARNHOUSE_DISABLE_EE="1"
export LEARNHOUSE_DEMO_ENABLED="0"
export LEARNHOUSE_AUTH_JWT_SECRET_KEY="integration-test-secret-key-32chars-min!"

# Check if PostgreSQL URL is provided
if [ -n "${TEST_DATABASE_URL}" ] || [ -n "${POSTGRES_TEST_URL}" ] || [ -n "${DATABASE_URL}" ]; then
    echo "Using configured PostgreSQL database connection."
else
    echo "No PostgreSQL URL specified. Using SQLite async fallback."
fi

# Run pytest on integration test suite
if command -v uv &> /dev/null; then
    uv run pytest src/tests/integration -v --tb=short "$@"
elif command -v poetry &> /dev/null; then
    poetry run pytest src/tests/integration -v --tb=short "$@"
else
    pytest src/tests/integration -v --tb=short "$@"
fi

echo "========================================================"
echo " Integration Test Suite Completed Successfully!"
echo "========================================================"
