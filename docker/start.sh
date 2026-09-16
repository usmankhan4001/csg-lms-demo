#!/bin/sh

# Set environment variables for proper Python logging
export PYTHONUNBUFFERED=1
export PYTHONIOENCODING=utf-8

# Wait for database and redis if connection strings point to external services
# (In docker-compose, depends_on handles this, but useful for standalone)
if [ -n "$LEARNHOUSE_SQL_CONNECTION_STRING" ]; then
    DB_HOST=$(echo "$LEARNHOUSE_SQL_CONNECTION_STRING" | sed -n 's/.*@\([^:]*\):\([0-9]*\)\/.*/\1/p')
    if [ -n "$DB_HOST" ] && [ "$DB_HOST" != "localhost" ] && [ "$DB_HOST" != "127.0.0.1" ] && [ "$DB_HOST" != "db" ]; then
        echo "Waiting for external database at $DB_HOST..."
        timeout 30 sh -c 'until nc -z '"$DB_HOST"' 5432; do sleep 1; done' || true
    fi
fi

# Start the services
# Use server-wrapper.js for runtime environment variable injection
pm2 start server-wrapper.js --cwd /app/web --name learnhouse-web > /dev/null 2>&1
pm2 start uv --cwd /app/api --name learnhouse-api -- run app.py
# arq worker: the ONLY thing that runs WorkerSettings.cron_jobs -- the weekly
# parent digest, the hourly nurture advance, the 09:00 fee reminders, and the
# 15-minute drain that is the sole deliverer of a quiet-hours notification.
# Without this process those jobs never fire and every deferred message stays
# "queued" forever, while the API healthcheck stays green. `uv run` matches how
# the api process above is started; arq is a project dependency (pyproject.toml)
# so it resolves from the same venv.
pm2 start uv --cwd /app/api --name learnhouse-worker -- run arq src.core.worker.WorkerSettings
pm2 start node --cwd /app/collab --name learnhouse-collab -- dist/index.js

# Check if the services are running and log the status
pm2 status

# Start Nginx in the background
nginx -g 'daemon off;' &

# Tail PM2 logs with proper formatting
pm2 logs --raw
