"""
Tests for teacher oversight of AI tutoring (M46) and the daily session-time
limit (M39).

The kill switch is a safety control, so these assert not just that it blocks
but that it blocks for the RIGHT reasons and leaves an audit trail -- and,
critically, that an infrastructure failure denies rather than silently
granting access.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.db.ai_oversight import AITutorAccessBlock, AITutorTranscript
from src.services.ai.tutor_oversight import (
    TUTOR_DAILY_SESSION_MINUTES,
    build_tutor_session_key,
    check_tutor_access,
    check_tutor_session_limit,
    log_tutor_exchange,
)


# ---------------------------------------------------------------- kill switch

@pytest.mark.asyncio
async def test_access_allowed_when_no_block_exists(db):
    result = await check_tutor_access("501", db, section_ids=[7])
    assert result.is_allowed is True


@pytest.mark.asyncio
async def test_student_level_block_denies_access(db):
    db.add(AITutorAccessBlock(student_id=502, blocked_by_user_id=99, reason="Needs a break"))
    await db.commit()

    result = await check_tutor_access("502", db)

    assert result.is_allowed is False
    assert "student" in (result.reason or "")


@pytest.mark.asyncio
async def test_section_level_block_denies_every_student_in_it(db):
    db.add(AITutorAccessBlock(section_id=42, blocked_by_user_id=99, reason="Exam week"))
    await db.commit()

    # The student is not named on the block; they inherit it via their section.
    result = await check_tutor_access("503", db, section_ids=[42])

    assert result.is_allowed is False
    assert "section" in (result.reason or "")


@pytest.mark.asyncio
async def test_lifted_block_no_longer_denies(db):
    block = AITutorAccessBlock(student_id=504, blocked_by_user_id=99, is_active=False)
    db.add(block)
    await db.commit()

    result = await check_tutor_access("504", db)

    assert result.is_allowed is True


@pytest.mark.asyncio
async def test_block_is_auditable_who_and_why(db):
    """A kill switch nobody can account for is not a safety control."""
    db.add(
        AITutorAccessBlock(
            student_id=505, blocked_by_user_id=77, reason="Repeated misuse", org_id=1
        )
    )
    await db.commit()

    from sqlmodel import select

    row = (await db.exec(select(AITutorAccessBlock).where(AITutorAccessBlock.student_id == 505))).first()
    assert row.blocked_by_user_id == 77
    assert row.reason == "Repeated misuse"
    assert row.created_at is not None


@pytest.mark.asyncio
async def test_lookup_failure_denies_rather_than_granting(db):
    """Fails CLOSED. A DB error must never silently override a teacher's block."""
    broken = MagicMock()
    broken.execute = MagicMock(side_effect=RuntimeError("db down"))

    result = await check_tutor_access("506", broken)

    assert result.is_allowed is False
    assert result.is_indeterminate is True


@pytest.mark.asyncio
async def test_unidentifiable_student_is_not_blocked(db):
    """Anonymous/demo paths have nothing to block; they must not be denied."""
    assert (await check_tutor_access(None, db)).is_allowed is True
    assert (await check_tutor_access("not-a-number", db)).is_allowed is True


# ------------------------------------------------------------- session limit

def test_session_key_follows_project_convention():
    assert build_tutor_session_key(42, "1007") == "csg:42:1007:tutor:daily_session_seconds"
    assert build_tutor_session_key(None, "1007") == "csg:noorg:1007:tutor:daily_session_seconds"


def test_session_limit_fails_open_without_redis():
    """A cache outage must not lock every student out of tutoring."""
    with patch("src.services.ai.tutor_oversight.get_redis_client", return_value=None):
        result = check_tutor_session_limit("601", org_id=1)
    assert result.is_allowed is True


def test_first_exchange_of_the_day_starts_the_budget():
    fake = MagicMock()
    fake.get.return_value = None
    with patch("src.services.ai.tutor_oversight.get_redis_client", return_value=fake):
        result = check_tutor_session_limit("602", org_id=1)
    assert result.is_allowed is True
    assert fake.setex.called


def test_exceeding_the_daily_minutes_blocks():
    fake = MagicMock()
    # Already used the full 45 minutes.
    fake.get.return_value = str(TUTOR_DAILY_SESSION_MINUTES * 60)
    fake.ttl.return_value = 3600
    with patch("src.services.ai.tutor_oversight.get_redis_client", return_value=fake):
        result = check_tutor_session_limit("603", org_id=1)
    assert result.is_allowed is False
    assert result.retry_after_seconds == 3600
    # Must not keep charging time to a student already cut off.
    assert not fake.incrby.called


def test_under_the_limit_accrues_time():
    fake = MagicMock()
    fake.get.return_value = "600"  # 10 minutes used
    fake.incrby.return_value = 660
    fake.ttl.return_value = 1000
    with patch("src.services.ai.tutor_oversight.get_redis_client", return_value=fake):
        result = check_tutor_session_limit("604", org_id=1)
    assert result.is_allowed is True
    assert fake.incrby.called


def test_redis_error_fails_open():
    fake = MagicMock()
    fake.get.side_effect = RuntimeError("connection reset")
    with patch("src.services.ai.tutor_oversight.get_redis_client", return_value=fake):
        result = check_tutor_session_limit("605", org_id=1)
    assert result.is_allowed is True


# ---------------------------------------------------------------- transcripts

@pytest.mark.asyncio
async def test_exchange_is_recorded_for_teacher_review(db):
    await log_tutor_exchange(
        db, "701", "How do I factor x^2 - 9?", "answered", org_id=1, section_id=5
    )

    from sqlmodel import select

    row = (await db.exec(select(AITutorTranscript).where(AITutorTranscript.student_id == 701))).first()
    assert row is not None
    assert row.outcome == "answered"
    assert "factor" in row.prompt


@pytest.mark.asyncio
async def test_blocked_turns_are_recorded_too(db):
    """Oversight is worthless if only successful turns are visible."""
    await log_tutor_exchange(
        db, "702", "give me the exam answers", "blocked_safety", org_id=1, detail="CHEATING"
    )

    from sqlmodel import select

    row = (await db.exec(select(AITutorTranscript).where(AITutorTranscript.student_id == 702))).first()
    assert row.outcome == "blocked_safety"
    assert row.detail == "CHEATING"


@pytest.mark.asyncio
async def test_transcript_failure_never_breaks_the_session(db):
    """An audit-log outage must not deny a student their tutor."""
    broken = MagicMock()
    broken.add = MagicMock(side_effect=RuntimeError("disk full"))
    # Must not raise.
    await log_tutor_exchange(broken, "703", "hello", "answered")
