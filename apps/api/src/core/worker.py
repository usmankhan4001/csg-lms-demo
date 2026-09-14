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

Registered work: `healthcheck_tick` (a trivial liveness placeholder proving
the registration mechanism fires) and `send_weekly_digests` (M48), the first
job in this system that runs without a user request. Further scheduled
features - a marketing drip-sequence engine, scheduled report distribution -
register their functions/cron jobs here the same way.
"""

import logging
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

from arq import cron
from arq.connections import RedisSettings

from config.config import get_learnhouse_config
from src.services.ai.parent_digest import send_weekly_digests
from src.services.ai.revops_nurture_runner import advance_nurture_sequences
from src.services.sms.fee_reminders import send_fee_reminders

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

    # On-demand job functions, enqueue-able by name.
    functions: list = [
        send_weekly_digests,
        advance_nurture_sequences,
        send_fee_reminders,
    ]

    # Scheduled jobs.
    cron_jobs: list = [
        cron(healthcheck_tick, minute=0),
        # Weekly parent digest (M48). Monday 06:00 UTC: after the school week
        # it reports on has closed, and early enough that parents have it
        # before the new week starts. This is the first job in this system
        # that acts without a user request, so note the constraint it lives
        # under -- the digest emails real families, and
        # services/ai/parent_digest.py therefore omits any figure it cannot
        # source from actual records rather than estimating one.
        cron(send_weekly_digests, weekday=0, hour=6, minute=0),
        # Admissions nurture (M25). Hourly on the half hour: drip stages are
        # scheduled in DAYS, so hourly is ample precision, and it keeps any
        # single run small rather than sending a day's worth at once. This
        # mails prospective parents, so the runner refuses to send to a lead
        # who opted out or who has already enrolled or declined, and records
        # every suppressed or failed attempt as a visible row.
        cron(advance_nurture_sequences, minute=30),
        # Fee reminders (M08). Daily at 09:00 UTC, deliberately not hourly: a
        # fee balance changes on the scale of days, and a more frequent job
        # would be a machine for harassing families. Before this, late fees
        # accrued automatically and NOBODY told the family -- the balance grew
        # silently until someone happened to open the ledger.
        #
        # Every send goes through the notification service, so the reminder is
        # readable in-app even when mail is unconfigured and a failed email is
        # a visible delivery row rather than a swallowed log line.
        # FeeReminderLog records what was actually delivered, not what was
        # intended, so a school can tell the difference.
        cron(send_fee_reminders, hour=9, minute=0),
    ]
