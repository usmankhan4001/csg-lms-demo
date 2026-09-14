"""
Weekly parent digest (M48) -- computed from real records, and delivered.

WHY THIS FILE REPLACES THE PREVIOUS BEHAVIOUR: the digest endpoint in
`src/routers/ai_parent_digest.py` returned entirely hardcoded values --
"96.0%", 24 classes attended, topics like "Macbeth Act II" -- for every
student, ignoring the `student_id` it was given. That is harmless as an
unshipped stub and actively harmful the moment it is emailed: parents would
receive invented attendance figures and invented scores about their own
children, indistinguishable from real ones.

So the digest is computed here from actual attendance and tutor-transcript
rows, and any figure we cannot source is omitted rather than invented. A
short digest that is true beats a rich one that is fiction.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional

from sqlmodel import col, select

from src.db.ai_oversight import AITutorTranscript
from src.db.sms_attendance import AttendanceStatus, StudentAttendance
from src.db.sms_identity import StudentGuardian
from src.db.users import User
from src.services.sms.attendance import collapse_to_daily_status

logger = logging.getLogger(__name__)


@dataclass
class WeeklyDigest:
    student_id: int
    student_name: str
    week_start: date
    week_end: date
    days_recorded: int = 0
    days_present: int = 0
    days_absent: int = 0
    days_late: int = 0
    days_excused: int = 0
    tutor_sessions: int = 0
    topics: List[str] = field(default_factory=list)

    @property
    def has_content(self) -> bool:
        """Nothing happened this week worth mailing about."""
        return self.days_recorded > 0 or self.tutor_sessions > 0

    @property
    def attendance_rate(self) -> Optional[float]:
        if self.days_recorded == 0:
            return None
        effective = self.days_present + self.days_excused + (self.days_late * 0.5)
        return round((effective / self.days_recorded) * 100, 1)


async def compute_weekly_digest(
    db_session,
    student_id: int,
    week_start: Optional[date] = None,
) -> WeeklyDigest:
    """Build one student's digest from real attendance and tutor activity."""
    today = datetime.now(timezone.utc).date()
    start = week_start or (today - timedelta(days=7))
    end = start + timedelta(days=6)

    student = await db_session.get(User, student_id)
    name = f"Student #{student_id}"
    if student is not None:
        full = " ".join(filter(None, [student.first_name, student.last_name]))
        if full:
            name = full

    digest = WeeklyDigest(
        student_id=student_id, student_name=name, week_start=start, week_end=end
    )

    att_res = await db_session.execute(
        select(StudentAttendance).where(
            col(StudentAttendance.student_id) == student_id,
            col(StudentAttendance.date) >= start,
            col(StudentAttendance.date) <= end,
        )
    )
    # These fields are DAYS, and attendance can now be recorded per period, so
    # collapse to one verdict per date before counting. Counting rows would
    # tell a parent their child was recorded for 30 days in a five-day week
    # (six periods x five days) -- a fabricated figure of exactly the kind
    # this digest was rewritten to stop producing.
    for day_status in collapse_to_daily_status(att_res.scalars().all()).values():
        digest.days_recorded += 1
        if day_status == AttendanceStatus.PRESENT:
            digest.days_present += 1
        elif day_status == AttendanceStatus.ABSENT:
            digest.days_absent += 1
        elif day_status == AttendanceStatus.LATE:
            digest.days_late += 1
        elif day_status == AttendanceStatus.EXCUSED:
            digest.days_excused += 1

    # Tutor engagement: count answered turns only. Blocked ones are a safety
    # matter for the counsellor, not content for a parent newsletter.
    start_dt = datetime.combine(start, datetime.min.time()).replace(tzinfo=timezone.utc)
    end_dt = datetime.combine(end, datetime.max.time()).replace(tzinfo=timezone.utc)
    tut_res = await db_session.execute(
        select(AITutorTranscript).where(
            col(AITutorTranscript.student_id) == student_id,
            col(AITutorTranscript.outcome) == "answered",
            col(AITutorTranscript.created_at) >= start_dt,
            col(AITutorTranscript.created_at) <= end_dt,
        )
    )
    transcripts = tut_res.scalars().all()
    digest.tutor_sessions = len(transcripts)
    # The student's own words, truncated -- not an LLM-generated "topic",
    # which would be another layer of invention between parent and fact.
    digest.topics = [t.prompt[:80] for t in transcripts[:3]]

    return digest


def render_digest_html(d: WeeklyDigest) -> str:
    rate = d.attendance_rate
    rate_row = (
        f"<tr><td style='padding:4px 12px 4px 0;color:#666'>Attendance</td>"
        f"<td><strong>{rate}%</strong> ({d.days_present} present, {d.days_absent} absent, "
        f"{d.days_late} late, {d.days_excused} excused of {d.days_recorded} days)</td></tr>"
        if rate is not None
        else "<tr><td style='padding:4px 12px 4px 0;color:#666'>Attendance</td>"
        "<td>No attendance was recorded this week.</td></tr>"
    )

    topics_block = ""
    if d.topics:
        items = "".join(f"<li>{t}</li>" for t in d.topics)
        topics_block = (
            f"<p style='color:#444;margin-bottom:4px'>Questions they worked through with the AI tutor:</p>"
            f"<ul style='color:#444;margin-top:0'>{items}</ul>"
        )

    return f"""
    <div style="font-family:system-ui,-apple-system,Segoe UI,sans-serif;line-height:1.5">
      <h2 style="margin-bottom:4px">{d.student_name} — weekly summary</h2>
      <p style="margin-top:0;color:#666">{d.week_start.isoformat()} to {d.week_end.isoformat()}</p>
      <table style="border-collapse:collapse;margin:16px 0">
        {rate_row}
        <tr><td style="padding:4px 12px 4px 0;color:#666">AI tutor</td>
            <td><strong>{d.tutor_sessions}</strong> question{'' if d.tutor_sessions == 1 else 's'} this week</td></tr>
      </table>
      {topics_block}
      <p style="color:#888;font-size:12px">
        Sent by your school's CSG-LMS. Figures come from the school's own attendance
        and tutoring records; anything not recorded is left out rather than estimated.
      </p>
    </div>
    """


async def send_weekly_digests(ctx: Optional[dict] = None) -> dict:
    """arq job: email every guardian a digest for each of their children.

    Registered as a cron job in `src/core/worker.py`. This is the first real
    autonomous job in the system -- everything before it was request-driven --
    so it follows the conventions the crisis-alert path established: open its
    own DB session (jobs run outside request scope), off-load the synchronous
    send_email onto a thread, and never let one failure abort the batch.
    """
    from src.core.events.database import _async_session_factory
    from src.services.email.utils import send_email

    sent = 0
    skipped_empty = 0
    failed = 0

    async with _async_session_factory() as session:
        links_res = await session.execute(select(StudentGuardian))
        links = links_res.scalars().all()
        if not links:
            logger.info("Weekly parent digest: no guardian links exist, nothing to send")
            return {"sent": 0, "skipped_empty": 0, "failed": 0}

        # Cache per student: several guardians commonly share one child.
        digests: dict = {}

        for link in links:
            try:
                if link.student_id not in digests:
                    digests[link.student_id] = await compute_weekly_digest(session, link.student_id)
                digest = digests[link.student_id]

                if not digest.has_content:
                    skipped_empty += 1
                    continue

                guardian = await session.get(User, link.guardian_user_id)
                if guardian is None or not getattr(guardian, "email", None):
                    continue

                await asyncio.to_thread(
                    send_email,
                    guardian.email,
                    f"{digest.student_name}: weekly school summary",
                    render_digest_html(digest),
                )
                sent += 1
            except Exception:
                failed += 1
                logger.exception(
                    "Weekly digest failed for guardian %s / student %s",
                    link.guardian_user_id, link.student_id,
                )

    logger.info(
        "Weekly parent digest complete: %d sent, %d skipped (no activity), %d failed",
        sent, skipped_empty, failed,
    )
    return {"sent": sent, "skipped_empty": skipped_empty, "failed": failed}
