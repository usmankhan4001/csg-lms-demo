#!/bin/bash
set -e

# ==============================================================================
# CSG-LMS API Production Entrypoint
# ==============================================================================
# 1. Waits for PostgreSQL database readiness
# 2. Waits for Redis cache readiness
# 3. Executes Alembic database migrations (alembic upgrade head)
# 4. Boots high-concurrency Uvicorn ASGI server with non-root security context
# ==============================================================================

echo "=================================================================="
echo "🚀 [CSG-LMS API] Initializing Production Environment"
echo "=================================================================="

# Function to wait for a network service
wait_for_service() {
    local host=$1
    local port=$2
    local service_name=$3
    local max_attempts=45
    local attempt=1

    echo "⏳ Waiting for ${service_name} at ${host}:${port}..."
    
    while [ $attempt -le $max_attempts ]; do
        if nc -z "$host" "$port" 2>/dev/null || timeout 1 bash -c "cat < /dev/null > /dev/tcp/$host/$port" 2>/dev/null; then
            echo "✅ [CSG-LMS] ${service_name} is reachable and responding!"
            return 0
        fi
        echo "   [Attempt ${attempt}/${max_attempts}] ${service_name} not yet ready, waiting 2s..."
        sleep 2
        attempt=$((attempt + 1))
    done

    echo "❌ [FATAL] ${service_name} failed to become available after $((max_attempts * 2)) seconds"
    exit 1
}

# 1. Parse and wait for PostgreSQL
if [ -n "$LEARNHOUSE_SQL_CONNECTION_STRING" ]; then
    DB_HOST=$(echo "$LEARNHOUSE_SQL_CONNECTION_STRING" | sed -n 's/.*@\([^:]*\):\([0-9]*\)\/.*/\1/p')
    DB_PORT=$(echo "$LEARNHOUSE_SQL_CONNECTION_STRING" | sed -n 's/.*@\([^:]*\):\([0-9]*\)\/.*/\2/p')
    
    if [ -z "$DB_PORT" ]; then
        DB_PORT=5432
    fi
    
    if [ -n "$DB_HOST" ]; then
        wait_for_service "$DB_HOST" "$DB_PORT" "PostgreSQL Database"
    fi
fi

# 2. Parse and wait for Redis
REDIS_CONN="${LEARNHOUSE_REDIS_URL:-$LEARNHOUSE_REDIS_CONNECTION_STRING}"
if [ -n "$REDIS_CONN" ]; then
    if echo "$REDIS_CONN" | grep -q '@'; then
        REDIS_HOST=$(echo "$REDIS_CONN" | sed -n 's|.*@\([^:/]*\).*|\1|p')
        REDIS_PORT=$(echo "$REDIS_CONN" | sed -n 's|.*@[^:/]*:\([0-9]*\).*|\1|p')
    else
        REDIS_HOST=$(echo "$REDIS_CONN" | sed -n 's|redis://\([^:/]*\).*|\1|p')
        REDIS_PORT=$(echo "$REDIS_CONN" | sed -n 's|redis://[^:/]*:\([0-9]*\).*|\1|p')
    fi
    
    if [ -z "$REDIS_PORT" ]; then
        REDIS_PORT=6379
    fi
    if [ -z "$REDIS_HOST" ]; then
        REDIS_HOST="redis"
    fi
    
    wait_for_service "$REDIS_HOST" "$REDIS_PORT" "Redis Cache"
fi

# 3. Execute Alembic Migrations
#
# THIS MUST ABORT THE BOOT ON FAILURE. It previously did not: both attempts
# ended in `|| echo "...warnings."`, which exits 0, and the script then printed
# an unconditional "schema is up to date" and started the API.
#
# That is the worst possible failure mode here. `SQLModel.metadata.create_all`
# builds MISSING TABLES at boot but never ALTERs an existing one, so a container
# whose migrations failed still comes up, still serves traffic, and still passes
# its healthcheck -- while every column added by a migration is silently absent.
# Requests touching those columns fail one by one, in production, long after the
# deploy was declared green.
#
# A deployment that refuses to start is a page at 3am. A deployment that starts
# with the wrong schema is a corrupted database nobody notices for a week.
echo "📦 [CSG-LMS] Executing Database Migrations (alembic upgrade head)..."

run_migrations() {
    if command -v alembic >/dev/null 2>&1; then
        alembic upgrade head && return 0
        echo "⚠️  alembic on PATH failed; retrying via the python module..."
    fi
    python -m alembic upgrade head
}

if ! run_migrations; then
    echo "❌ [CSG-LMS] DATABASE MIGRATIONS FAILED -- refusing to start."
    echo "   The API is NOT starting, deliberately. Booting now would serve"
    echo "   traffic against a schema missing every migrated column, and the"
    echo "   healthcheck would report success while doing it."
    echo "   Inspect with:  docker compose exec api alembic current"
    echo "   and compare against:  docker compose exec api alembic heads"
    exit 1
fi
echo "✅ [CSG-LMS] Database schema is up to date."

# 4. Set Runtime Configuration
export PYTHONUNBUFFERED=1
export PYTHONIOENCODING=utf-8

PORT=${LEARNHOUSE_PORT:-9000}
HOST=${HOSTNAME:-0.0.0.0}
WORKERS=${WORKERS:-4}

echo "🌟 [CSG-LMS] Launching FastAPI Backend on ${HOST}:${PORT} with ${WORKERS} workers..."

# 5. Exec Uvicorn ASGI Server
exec uvicorn app:app \
    --host "$HOST" \
    --port "$PORT" \
    --workers "$WORKERS" \
    --timeout-keep-alive 600 \
    --access-log \
    --proxy-headers \
    --forwarded-allow-ips "*"
