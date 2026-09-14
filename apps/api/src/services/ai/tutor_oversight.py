"""
Teacher oversight controls for the AI tutor (M46) and the daily session
time limit (M39).

Three concerns live here so `socratic_tutor.py` stays about pedagogy:

1. **Kill switch** -- is AI tutoring switched off for this student, or for a
   section they belong to.
2. **Daily session minutes** -- a time budget, distinct from the existing
   1000/day request COUNT in socratic_tutor.py.
3. **Transcript logging** -- so a teacher can review what was asked.

FAILURE SEMANTICS DIFFER BETWEEN 1 AND 2, DELIBERATELY:

- The kill switch is a SAFETY control a human explicitly set. If we cannot
  determine whether a block exists (DB error), we DENY and log loudly. A
  student losing their tutor for a few minutes is recoverable; silently
  overriding a teacher who switched AI off for a child in crisis is not.
- The session limit is a wellbeing/cost guardrail, not a safety boundary, so
  it FAILS OPEN on a Redis outage -- matching the existing request-count
  limiter's reasoning in socratic_tutor.py, which says the same in its own
  docstring.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.redis import get_redis_client
from src.db.ai_oversight import AITutorAccessBlock, AITutorTranscript

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. Kill switch
# ---------------------------------------------------------------------------

AI_DISABLED_MESSAGE = (
    "AI tutoring is currently switched off for you by your school. "
    "Please speak to your teacher if you think this is a mistake — they can turn it back on."
)


@dataclass
class TutorAccessResult:
    is_allowed: bool
    reason: Optional[str] = None
    # True when we could not determine access and denied defensively, so the
    # caller can distinguish "a teacher blocked this" from "we don't know".
    is_indeterminate: bool = False


async def check_tutor_access(
    student_id: Optional[str],
    db_session: Optional[AsyncSession],
    section_ids: Optional[List[int]] = None,
) -> TutorAccessResult:
    """Is AI tutoring permitted for this student right now?

    Denies when an active block targets the student directly OR any section
    they are enrolled in. See the module docstring for why a lookup failure
    denies rather than allows.
    """
    if db_session is None or not student_id:
        # No session to check against (anonymous/demo paths). Nothing has been
        # blocked because nothing is identifiable; allow, matching how the rest
        # of the tutor treats an unresolvable student.
        return TutorAccessResult(is_allowed=True)

    try:
        student_id_int = int(student_id)
    except (TypeError, ValueError):
        return TutorAccessResult(is_allowed=True)

    try:
        conditions = [col(AITutorAccessBlock.student_id) == student_id_int]
        if section_ids:
            conditions.append(col(AITutorAccessBlock.section_id).in_(section_ids))

        from sqlalchemy import or_

        result = await db_session.execute(
            select(AITutorAccessBlock).where(
                col(AITutorAccessBlock.is_active) == True,  # noqa: E712
                or_(*conditions),
            )
        )
        block = result.scalars().first()
        if block is not None:
            scope = "student" if block.student_id == student_id_int else "section"
            return TutorAccessResult(
                is_allowed=False,
                reason=f"AI tutoring blocked at {scope} level (block #{block.id})",
            )
        return TutorAccessResult(is_allowed=True)
    except Exception:
        # Fail CLOSED: see module docstring. A teacher's explicit block must
        # never be bypassed by an infrastructure error.
        logger.exception(
            "AI tutor access check FAILED for student %s -- denying access defensively", student_id
        )
        return TutorAccessResult(
            is_allowed=False,
            reason="Could not verify AI tutoring permissions",
            is_indeterminate=True,
        )


# ---------------------------------------------------------------------------
# 2. Daily session-minute limit (M39)
# ---------------------------------------------------------------------------

# Spec: "minor account 45-minute daily session limit".
#
# SCOPE NOTE, stated plainly rather than papered over: this codebase stores no
# date of birth or age anywhere (grepped date_of_birth/dob/birth_date across
# src/db -- zero hits), and `get_student_enrollment_scope` exposes grade_level
# and section_ids only. There is therefore no way to identify a "minor"
# account. The limit is applied to ALL enrolled students. For a school
# platform that is the safe default -- the population is overwhelmingly
# minors -- but it is an assumption, not a check.
TUTOR_DAILY_SESSION_MINUTES = 45

_SESSION_MODULE = "tutor"
_SESSION_KEY_NAME = "daily_session_seconds"

# Each tutor turn is charged this much thinking/reading time. The tutor is a
# streamed chat with no session open/close events, so wall-clock duration is
# not observable; charging a flat estimate per exchange is the honest
# approximation, and it is documented as such rather than presented as a
# measurement.
SECONDS_CHARGED_PER_EXCHANGE = 60


def build_tutor_session_key(org_id: Optional[int], student_id: str) -> str:
    """csg:{org_id}:{student_id}:tutor:daily_session_seconds

    Same convention as build_tutor_rate_limit_key in socratic_tutor.py.
    """
    org_part = str(org_id) if org_id is not None else "noorg"
    return f"csg:{org_part}:{student_id}:{_SESSION_MODULE}:{_SESSION_KEY_NAME}"


def _seconds_until_utc_midnight() -> int:
    now = datetime.now(timezone.utc)
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return max(1, int((tomorrow - now).total_seconds()))


@dataclass
class TutorSessionLimitResult:
    is_allowed: bool
    seconds_used: int
    limit_seconds: int
    retry_after_seconds: int


def check_tutor_session_limit(
    student_id: str,
    org_id: Optional[int] = None,
    max_minutes: int = TUTOR_DAILY_SESSION_MINUTES,
    charge_seconds: int = SECONDS_CHARGED_PER_EXCHANGE,
) -> TutorSessionLimitResult:
    """Rolling daily cumulative tutor minutes, reset at UTC midnight.

    Fails OPEN when Redis is unavailable -- a wellbeing guardrail should not
    take tutoring down for every student during a cache outage. Mirrors
    check_tutor_daily_rate_limit's stance and key/TTL conventions exactly.
    """
    limit_seconds = max_minutes * 60
    key = build_tutor_session_key(org_id, student_id)
    r = get_redis_client()
    if r is None:
        return TutorSessionLimitResult(True, 0, limit_seconds, 0)

    try:
        window = _seconds_until_utc_midnight()
        current = r.get(key)

        if current is None:
            r.setex(key, window, charge_seconds)
            return TutorSessionLimitResult(True, charge_seconds, limit_seconds, window)

        used = int(current)
        if used >= limit_seconds:
            ttl = r.ttl(key)
            return TutorSessionLimitResult(
                False, used, limit_seconds, ttl if ttl and ttl > 0 else window
            )

        new_used = r.incrby(key, charge_seconds)
        ttl = r.ttl(key)
        if ttl is None or ttl < 0:
            r.expire(key, window)
            ttl = window
        return TutorSessionLimitResult(True, new_used, limit_seconds, ttl)
    except Exception as e:
        logger.warning("Tutor session limit check failed for '%s', failing open: %s", key, e)
        return TutorSessionLimitResult(True, 0, limit_seconds, 0)


def session_limit_message(result: TutorSessionLimitResult) -> str:
    minutes = result.limit_seconds // 60
    return (
        f"You've reached today's {minutes} minutes of AI tutoring. "
        "Take a break — it'll be available again tomorrow. "
        "Your teacher can help in the meantime."
    )


# ---------------------------------------------------------------------------
# 3. Transcript logging
# ---------------------------------------------------------------------------

async def log_tutor_exchange(
    db_session: Optional[AsyncSession],
    student_id: Optional[str],
    prompt: str,
    outcome: str,
    org_id: Optional[int] = None,
    section_id: Optional[int] = None,
    course_id: Optional[str] = None,
    detail: Optional[str] = None,
) -> None:
    """Record one tutor turn for teacher review. Never raises: an audit-log
    failure must not break the student's session, so it is logged and
    swallowed."""
    if db_session is None or not student_id:
        return
    try:
        student_id_int = int(student_id)
    except (TypeError, ValueError):
        return

    try:
        db_session.add(
            AITutorTranscript(
                org_id=org_id,
                student_id=student_id_int,
                section_id=section_id,
                course_id=str(course_id) if course_id else None,
                prompt=prompt[:4000],
                outcome=outcome,
                detail=detail[:255] if detail else None,
            )
        )
        await db_session.commit()
    except Exception:
        logger.exception("Failed to record AI tutor transcript for student %s", student_id)
        try:
            await db_session.rollback()
        except Exception:
            pass
