"""
Tests for the weekly parent digest (M48).

The bar here is higher than "does it send". The digest endpoint this replaces
returned hardcoded figures -- a 96% attendance rate and topics like "Macbeth
Act II" -- for every student, ignoring the student_id entirely. Emailing that
to families would mean inventing academic facts about real children. So these
tests assert the digest is computed from actual rows, and that a week with no
records produces no email rather than a plausible-looking one.
"""

from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from src.db.ai_oversight import AITutorTranscript
from src.db.sms_attendance import AttendanceStatus, StudentAttendance
from src.db.sms_identity import StudentGuardian
from src.db.users import User
from src.services.ai.parent_digest import (
    compute_weekly_digest,
    render_digest_html,
    send_weekly_digests,
)


async def _add_user(db, id_: int, email: str, first: str = "Real") -> User:
    u = User(
        id=id_,
        username=f"user{id_}",
        first_name=first,
        last_name=f"Child{id_}",
        email=email,
        password="hashed",
        user_uuid=f"uuid-{id_}",
        creation_date=str(datetime.now()),
        update_date=str(datetime.now()),
    )
    db.add(u)
    await db.commit()
    return u


def _last_week() -> date:
    return datetime.now(timezone.utc).date() - timedelta(days=7)


@pytest.mark.asyncio
async def test_digest_counts_real_attendance_not_invented_figures(db):
    start = _last_week()
    await _add_user(db, 801, "child801@test.com")
    for offset, status in enumerate(
        [
            AttendanceStatus.PRESENT,
            AttendanceStatus.PRESENT,
            AttendanceStatus.ABSENT,
            AttendanceStatus.LATE,
            AttendanceStatus.EXCUSED,
        ]
    ):
        db.add(
            StudentAttendance(
                student_id=801, section_id=1, date=start + timedelta(days=offset),
                status=status, marked_by=1,
            )
        )
    await db.commit()

    digest = await compute_weekly_digest(db, 801, week_start=start)

    assert digest.days_recorded == 5
    assert digest.days_present == 2
    assert digest.days_absent == 1
    assert digest.days_late == 1
    assert digest.days_excused == 1
    # (2 present + 1 excused + 0.5 late) / 5 = 70%
    assert digest.attendance_rate == 70.0


@pytest.mark.asyncio
async def test_attendance_rate_is_none_when_nothing_was_recorded(db):
    """No data must read as no data -- never as a default good number."""
    await _add_user(db, 802, "child802@test.com")
    digest = await compute_weekly_digest(db, 802, week_start=_last_week())

    assert digest.days_recorded == 0
    assert digest.attendance_rate is None
    assert digest.has_content is False


@pytest.mark.asyncio
async def test_digest_uses_the_students_real_name(db):
    await _add_user(db, 803, "child803@test.com", first="Ayesha")
    digest = await compute_weekly_digest(db, 803, week_start=_last_week())
    assert "Ayesha" in digest.student_name


@pytest.mark.asyncio
async def test_only_answered_tutor_turns_count_as_engagement(db):
    """A blocked safety message is a counsellor matter, not parent newsletter
    content."""
    start = _last_week()
    await _add_user(db, 804, "child804@test.com")
    when = datetime.combine(start + timedelta(days=1), datetime.min.time()).replace(
        tzinfo=timezone.utc
    )
    db.add(AITutorTranscript(student_id=804, prompt="How do fractions work?", outcome="answered", created_at=when))
    db.add(AITutorTranscript(student_id=804, prompt="something alarming", outcome="blocked_safety", created_at=when))
    await db.commit()

    digest = await compute_weekly_digest(db, 804, week_start=start)

    assert digest.tutor_sessions == 1
    assert any("fractions" in t for t in digest.topics)
    assert not any("alarming" in t for t in digest.topics)


@pytest.mark.asyncio
async def test_rendered_html_states_absence_of_data_plainly(db):
    await _add_user(db, 805, "child805@test.com")
    digest = await compute_weekly_digest(db, 805, week_start=_last_week())
    html = render_digest_html(digest)

    assert "No attendance was recorded" in html
    # No invented percentage anywhere.
    assert "%" not in html.split("Attendance")[1].split("</tr>")[0]


@pytest.mark.asyncio
async def test_job_emails_each_guardian_of_a_child_with_activity(db):
    start = _last_week()
    await _add_user(db, 810, "kid810@test.com")
    await _add_user(db, 811, "mum811@test.com")
    await _add_user(db, 812, "dad812@test.com")
    db.add(StudentGuardian(guardian_user_id=811, student_id=810))
    db.add(StudentGuardian(guardian_user_id=812, student_id=810))
    db.add(
        StudentAttendance(
            student_id=810, section_id=1, date=start, status=AttendanceStatus.PRESENT, marked_by=1
        )
    )
    await db.commit()

    class _Factory:
        def __call__(self):
            return self
        async def __aenter__(self):
            return db
        async def __aexit__(self, *a):
            return False

    with patch("src.core.events.database._async_session_factory", _Factory()), \
         patch("src.services.email.utils.send_email") as mock_send:
        result = await send_weekly_digests()

    assert result["sent"] == 2
    recipients = sorted(c.args[0] for c in mock_send.call_args_list)
    assert recipients == ["dad812@test.com", "mum811@test.com"]


@pytest.mark.asyncio
async def test_job_sends_nothing_for_a_week_with_no_activity(db):
    """Silence beats a cheerful email about a week that never happened."""
    await _add_user(db, 820, "kid820@test.com")
    await _add_user(db, 821, "parent821@test.com")
    db.add(StudentGuardian(guardian_user_id=821, student_id=820))
    await db.commit()

    class _Factory:
        def __call__(self):
            return self
        async def __aenter__(self):
            return db
        async def __aexit__(self, *a):
            return False

    with patch("src.core.events.database._async_session_factory", _Factory()), \
         patch("src.services.email.utils.send_email") as mock_send:
        result = await send_weekly_digests()

    assert result["sent"] == 0
    assert result["skipped_empty"] >= 1
    mock_send.assert_not_called()


@pytest.mark.asyncio
async def test_one_failed_send_does_not_abort_the_batch(db):
    start = _last_week()
    for sid, gid in ((830, 831), (840, 841)):
        await _add_user(db, sid, f"kid{sid}@test.com")
        await _add_user(db, gid, f"parent{gid}@test.com")
        db.add(StudentGuardian(guardian_user_id=gid, student_id=sid))
        db.add(
            StudentAttendance(
                student_id=sid, section_id=1, date=start,
                status=AttendanceStatus.PRESENT, marked_by=1,
            )
        )
    await db.commit()

    class _Factory:
        def __call__(self):
            return self
        async def __aenter__(self):
            return db
        async def __aexit__(self, *a):
            return False

    calls = {"n": 0}

    def flaky(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("smtp refused")
        return None

    with patch("src.core.events.database._async_session_factory", _Factory()), \
         patch("src.services.email.utils.send_email", side_effect=flaky):
        result = await send_weekly_digests()

    assert result["failed"] == 1
    assert result["sent"] == 1
