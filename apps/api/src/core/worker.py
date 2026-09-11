"""
arq worker configuration skeleton.

-----------------------------------------------------------------------------
IMPORTANT: this module is NOT imported or run by the FastAPI app process.
arq workers run as a separate, standalone process alongside uvicorn. To run
the worker, start it independently (from the `apps/api` directory, with the
project's `uv` environment):

    arq src.core.worker.WorkerSettings

Nothing here executes automatically just because the API server is running;
the worker process above must be started (and kept running, e.g. via a
separate systemd unit / supervisor entry / container) for any registered
`functions` or `cron_jobs` to actually fire.
-----------------------------------------------------------------------------

This is infrastructure-only: `functions` is intentionally empty (nothing to
run on-demand yet) and `cron_jobs` contains exactly one trivial placeholder
job (`healthcheck_tick`) that proves the registration mechanism works
end-to-end. Future features - a marketing drip-sequence engine, scheduled
report distribution, weekly digests, etc. - should register their real
functions/cron jobs here later; none of that business logic is implemented
by this module.
"""

import logging
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

from arq import cron
from arq.connections import RedisSettings

from config.config import get_learnhouse_config

logger = logging.getLogger(__name__)


def _build_redis_settings() -> RedisSettings:
    """
    Build arq's RedisSettings from the same Redis connection string used by
    src.core.redis.get_redis_client(), so the worker process talks to the
    exact same Redis instance/config as the rest of the app (no separate,
    hardcoded connection info).
    """
    config = get_learnhouse_config()
    conn_string = config.redis_config.redis_connection_string
    if not conn_string:
        # Keep import-time behavior safe even when Redis isn't configured
        # in this environment (e.g. local dev without a redis_config entry):
        # fall back to arq's own defaults instead of raising.
        logger.debug("No redis_connection_string configured; using arq defaults")
        return RedisSettings()

    try:
        return RedisSettings.from_dsn(conn_string)
    except ValueError:
        # This project's default connection string uses a descriptive path
        # segment rather than a numeric db index (see config/config.yaml:
        # "redis://localhost:6379/learnhouse"). redis-py itself tolerates
        # that (it just falls back to database 0), but arq's from_dsn()
        # does an unguarded int() on the path and raises. Parse the DSN the
        # same way arq does, defaulting the database to 0 when the path
        # isn't a valid integer, instead of hardcoding a different
        # connection string.
        parsed = urlparse(conn_string)
        query_db = parse_qs(parsed.query).get("db")
        if query_db:
            database = int(query_db[0])
        else:
            try:
                database = int(parsed.path.lstrip("/")) if parsed.path else 0
            except ValueError:
                database = 0
        return RedisSettings(
            host=parsed.hostname or "localhost",
            port=parsed.port or 6379,
            ssl=parsed.scheme == "rediss",
            username=parsed.username,
            password=parsed.password,
            database=database,
        )


async def healthcheck_tick(ctx: dict) -> str:
    """
    Trivial placeholder cron job.

    This exists only to prove that arq's cron registration/execution
    mechanism works end-to-end. It is not a real feature - it simply logs
    and returns the current UTC timestamp. Safe to remove once real
    scheduled jobs (drip sequences, report distribution, digests, ...) are
    registered in `WorkerSettings.cron_jobs` instead.
    """
    now = datetime.now(timezone.utc).isoformat()
    logger.info("arq worker healthcheck tick at %s", now)
    return now


class WorkerSettings:
    """
    arq worker settings. Run this worker process with:

        arq src.core.worker.WorkerSettings
    """

    redis_settings = _build_redis_settings()

    # On-demand job functions. Empty for now - future features register
    # their enqueue-able functions here (e.g. `send_drip_email`,
    # `generate_scheduled_report`, `send_weekly_digest`).
    functions: list = []

    # Scheduled jobs. Only a placeholder today, to prove the wiring works.
    cron_jobs: list = [
        cron(healthcheck_tick, minute=0),
    ]
