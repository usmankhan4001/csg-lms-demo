"""Scheduling, recording state and coursework for live classes.

`LiveClassSession` stays the room record. Everything a *scheduled* class needs
beyond that lives in `LiveClassSessionDetail`, a companion table -- see its
docstring for why extending the existing table with columns would not actually
apply in any environment that already has it.

A session with no detail row (a legacy ad-hoc room) reads as: scheduled or
ended by its own timestamps, not cancelled, not recording. That is the safe
interpretation, and it means nothing that already exists breaks.
"""

import datetime
import logging
import uuid
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from fastapi import HTTPException, status
from sqlalchemy import and_, desc, or_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.courses.activities import Activity
from src.db.courses.chapter_activities import ChapterActivity
from src.db.sms_campus import ClassSection, StudentEnrollment
from src.db.sms_live_class import (
    LiveClassCoursework,
    LiveClassSession,
    LiveClassSessionDetail,
    LiveClassStatus,
    RecordingStatus,
)
from src.services.sms.live_class_recording import (
    RecordingStorageUnavailable,
    parse_egress_ended,
    public_url_for,
    recording_is_available,
    start_recording,
    stop_recording,
)

logger = logging.getLogger(__name__)

# A recording that was already dispatched, or has already finished, must not be
# started again: a second egress would record the same class twice and orphan
# the first file. UNAVAILABLE is in here too -- retrying a deployment with no
# object storage on every participant join would just re-fail, and the reason
# is already recorded on the class.
_RECORDING_ALREADY_STARTED = frozenset(
    {
        RecordingStatus.RECORDING.value,
        RecordingStatus.PROCESSING.value,
        RecordingStatus.READY.value,
        RecordingStatus.UNAVAILABLE.value,
    }
)


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _aware(dt: Optional[datetime.datetime]) -> Optional[datetime.datetime]:
    """SQLite (tests) hands back naive datetimes where Postgres gives aware
    ones. Comparing the two raises, so normalise before any comparison."""
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=datetime.timezone.utc)


async def get_detail(
    session: AsyncSession, session_id: int
) -> Optional[LiveClassSessionDetail]:
    return (
        await session.execute(
            select(LiveClassSessionDetail).where(
                LiveClassSessionDetail.session_id == session_id
            )
        )
    ).scalar_one_or_none()


def derive_status(
    live: LiveClassSession, detail: Optional[LiveClassSessionDetail]
) -> str:
    """A class's lifecycle state.

    Cancellation is recorded explicitly; everything else follows from whether
    the room is still open and whether its start time has passed. Derived
    rather than stored so a legacy row without a detail row still reports
    something truthful.
    """
    if detail is not None and detail.status == LiveClassStatus.CANCELLED.value:
        return LiveClassStatus.CANCELLED.value
    if not live.is_active:
        return LiveClassStatus.ENDED.value
    start = _aware(live.start_time)
    if start is not None and start > _now():
        return LiveClassStatus.SCHEDULED.value
    return LiveClassStatus.LIVE.value


async def schedule_class(
    session: AsyncSession,
    *,
    title: str,
    teacher_id: int,
    start_time: datetime.datetime,
    end_time: Optional[datetime.datetime] = None,
    section_id: Optional[int] = None,
    course_id: Optional[int] = None,
    description: Optional[str] = None,
    recording_enabled: bool = False,
) -> Tuple[LiveClassSession, LiveClassSessionDetail]:
    """Create a scheduled class and its detail row.

    The LiveKit room is NOT created here -- a class scheduled for next week
    should not hold a room open for a week. The room is created when someone
    actually starts it.
    """
    if end_time is not None and _aware(end_time) <= _aware(start_time):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="End time must be after start time.",
        )
    if section_id is None and course_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A live class must belong to a class section or a course.",
        )

    live = LiveClassSession(
        title=title,
        teacher_id=teacher_id,
        section_id=section_id,
        course_id=course_id,
        room_name=f"class-{uuid.uuid4().hex[:10]}",
        start_time=start_time,
        end_time=end_time,
        is_active=True,
    )
    session.add(live)
    # Flush, not commit. The id is needed for the detail row below, but
    # committing here published the class separately from the row carrying its
    # status, description and recording state. An interruption in that window
    # left a scheduled live class with no detail at all -- it appears on the
    # timetable with no status and no indication whether it is being recorded,
    # and nothing later fills that in.
    await session.flush()

    # Requesting a recording on a deployment with no storage is recorded as
    # UNAVAILABLE with the reason, not quietly accepted. The teacher finds out
    # now, not after the class.
    rec_status = RecordingStatus.NOT_REQUESTED.value
    rec_note = None
    if recording_enabled and not recording_is_available():
        rec_status = RecordingStatus.UNAVAILABLE.value
        from src.services.sms.live_class_recording import get_recording_storage

        _, rec_note = get_recording_storage()
    elif recording_enabled:
        rec_status = RecordingStatus.PENDING.value

    detail = LiveClassSessionDetail(
        session_id=live.id,
        description=description,
        status=LiveClassStatus.SCHEDULED.value,
        recording_enabled=recording_enabled,
        recording_status=rec_status,
        recording_note=rec_note,
    )
    session.add(detail)
    await session.commit()
    await session.refresh(detail)
    return live, detail


async def list_classes(
    session: AsyncSession,
    *,
    upcoming: bool,
    section_id: Optional[int] = None,
    course_id: Optional[int] = None,
    teacher_id: Optional[int] = None,
    campus_id: Optional[int] = None,
    limit: int = 100,
) -> List[Tuple[LiveClassSession, Optional[LiveClassSessionDetail]]]:
    """Upcoming or past classes.

    "Upcoming" is a still-open room whose start time has not passed, or which
    is running now. "Past" is anything ended. Cancelled classes appear in
    neither list by default -- a cancelled class is not something a teacher is
    preparing for, nor a record of a class that happened.
    """
    conditions = []
    if section_id is not None:
        conditions.append(LiveClassSession.section_id == section_id)
    if course_id is not None:
        conditions.append(LiveClassSession.course_id == course_id)
    if teacher_id is not None:
        conditions.append(LiveClassSession.teacher_id == teacher_id)

    if campus_id is not None:
        # Sessions carry no campus of their own; it comes from the section.
        # A course-only class has no campus dimension, so it is left in rather
        # than silently dropped from a campus-scoped view.
        section_ids = (
            await session.execute(
                select(ClassSection.id).where(ClassSection.campus_id == campus_id)
            )
        ).scalars().all()
        conditions.append(
            or_(
                LiveClassSession.section_id.in_(section_ids),
                LiveClassSession.section_id.is_(None),
            )
        )

    conditions.append(
        LiveClassSession.is_active.is_(True) if upcoming else LiveClassSession.is_active.is_(False)
    )

    stmt = select(LiveClassSession).where(and_(*conditions))
    stmt = stmt.order_by(
        LiveClassSession.start_time if upcoming else desc(LiveClassSession.start_time)
    ).limit(limit)
    rows = (await session.execute(stmt)).scalars().all()

    out: List[Tuple[LiveClassSession, Optional[LiveClassSessionDetail]]] = []
    for live in rows:
        detail = await get_detail(session, live.id)
        if detail is not None and detail.status == LiveClassStatus.CANCELLED.value:
            continue
        out.append((live, detail))
    return out


async def cancel_class(
    session: AsyncSession,
    *,
    live: LiveClassSession,
    cancelled_by_user_id: int,
    reason: Optional[str] = None,
) -> LiveClassSessionDetail:
    """Cancel a scheduled class.

    Refuses to cancel a class that already ended: that would rewrite history,
    turning a class students attended into one that never happened.
    """
    if not live.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This class has already ended and cannot be cancelled.",
        )

    detail = await get_detail(session, live.id)
    if detail is None:
        detail = LiveClassSessionDetail(session_id=live.id)
        session.add(detail)

    detail.status = LiveClassStatus.CANCELLED.value
    detail.cancelled_reason = reason
    detail.cancelled_by_user_id = cancelled_by_user_id
    detail.cancelled_at = _now()
    live.is_active = False
    live.end_time = _now()
    session.add(live)
    await session.commit()
    await session.refresh(detail)
    return detail


async def set_recording_enabled(
    session: AsyncSession, *, live: LiveClassSession, enabled: bool
) -> LiveClassSessionDetail:
    """Teacher opt-in for recording this class."""
    detail = await get_detail(session, live.id)
    if detail is None:
        detail = LiveClassSessionDetail(session_id=live.id)
        session.add(detail)

    detail.recording_enabled = enabled
    if not enabled:
        detail.recording_status = RecordingStatus.NOT_REQUESTED.value
        detail.recording_note = None
    elif not recording_is_available():
        from src.services.sms.live_class_recording import get_recording_storage

        detail.recording_status = RecordingStatus.UNAVAILABLE.value
        _, detail.recording_note = get_recording_storage()
    else:
        detail.recording_status = RecordingStatus.PENDING.value
        detail.recording_note = None

    await session.commit()
    await session.refresh(detail)
    return detail


async def set_recording_shared(
    session: AsyncSession, *, live: LiveClassSession, shared: bool
) -> LiveClassSessionDetail:
    """Teacher's second, separate decision: may students see the recording.

    Deliberately not implied by the recording finishing. A class may be
    recorded for a teacher's own review and never shared.
    """
    detail = await get_detail(session, live.id)
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This class has no recording to share.",
        )
    detail.recording_shared_with_students = shared
    await session.commit()
    await session.refresh(detail)
    return detail


async def begin_recording_if_requested(
    session: AsyncSession, *, live: LiveClassSession
) -> Optional[LiveClassSessionDetail]:
    """Start egress when the teacher opted in. No-op otherwise."""
    detail = await get_detail(session, live.id)
    if detail is None or not detail.recording_enabled:
        return detail

    try:
        egress_id, object_key = await start_recording(live.room_name, live.id)
        detail.egress_id = egress_id
        detail.recording_status = RecordingStatus.RECORDING.value
        detail.recording_started_at = _now()
        # Stored now so the key survives even if the completion path is
        # missed; the URL is only resolved once the file is actually ready.
        detail.recording_object_key = object_key
        detail.recording_note = None
    except RecordingStorageUnavailable as exc:
        detail.recording_status = RecordingStatus.UNAVAILABLE.value
        detail.recording_note = str(exc)
    except Exception as exc:  # noqa: BLE001
        # A failed recording must never stop the class from running.
        logger.exception("Failed to start recording for room=%s", live.room_name)
        detail.recording_status = RecordingStatus.FAILED.value
        detail.recording_note = f"Recording could not be started: {exc}"

    await session.commit()
    await session.refresh(detail)
    return detail


async def begin_recording_on_room_start(
    session: AsyncSession, *, live: LiveClassSession
) -> Optional[LiveClassSessionDetail]:
    """Dispatch egress when the room actually opens, if the teacher opted in.

    Called from the `room_started` webhook rather than only from the teacher's
    "start class" call because LiveKit is the authority on when a room exists:
    it can open because a participant joined directly, with no API call at all.

    Idempotent. `start_live_class` may already have dispatched an egress for
    this session, and `room_started` fires on the first join -- without the
    guard every class would be recorded twice.
    """
    detail = await get_detail(session, live.id)
    if detail is None or not detail.recording_enabled:
        return detail
    if detail.recording_status in _RECORDING_ALREADY_STARTED:
        return detail
    return await begin_recording_if_requested(session, live=live)


async def complete_recording_from_egress(
    session: AsyncSession, *, live: LiveClassSession, egress_info
) -> Optional[LiveClassSessionDetail]:
    """Persist what `egress_ended` told us. The ONLY path that may set READY.

    Everything else -- the teacher ending the class, the room closing, a
    dispatch failure -- leaves the recording non-terminal or FAILED, because
    only LiveKit knows whether a file actually landed in storage. Marking a
    recording ready on anything weaker is how a student gets a link to
    nothing.
    """
    result = parse_egress_ended(egress_info)

    detail = await get_detail(session, live.id)
    if detail is None:
        # An egress for a session with no detail row: an ad-hoc room that never
        # opted in, or a row that is gone. Nothing to attach it to, and
        # creating one would claim a recording for a class that never asked.
        logger.warning(
            "egress_ended for room=%s (egress_id=%s) but the session has no "
            "detail row; nothing recorded",
            live.room_name,
            result.egress_id,
        )
        return None

    if not detail.recording_enabled:
        # An egress this class never asked for (recording is opt-in). Writing
        # FAILED here would tell a teacher their recording broke when they
        # never turned it on, so the event is ignored instead.
        logger.warning(
            "egress_ended for room=%s but recording is not enabled on this class; "
            "ignoring",
            live.room_name,
        )
        return detail

    if result.egress_id:
        detail.egress_id = result.egress_id
    if result.object_key:
        detail.recording_object_key = result.object_key
    if result.duration_seconds is not None:
        detail.recording_duration_seconds = result.duration_seconds
    detail.recording_completed_at = _now()

    # `result.file_size_bytes` is parsed but NOT stored: `sms_live_class_detail`
    # has no file-size column, and adding one needs an Alembic migration
    # (create_all creates missing tables, it never ALTERs an existing one).
    # Reported rather than faked -- see the deployment notes.

    if not result.succeeded:
        detail.recording_status = RecordingStatus.FAILED.value
        detail.recording_note = result.error
        await session.commit()
        await session.refresh(detail)
        return detail

    link = await recording_course_link(session, live=live)
    if link.course_id is None:
        # The file is real but nothing in the LMS can hold it, so it is
        # unreachable for students however long it sits in the bucket.
        logger.warning(
            "Recording for room=%s finished but resolves to no course; it will "
            "not appear in any student's course",
            live.room_name,
        )

    url = public_url_for(detail.recording_object_key) if detail.recording_object_key else None
    if url:
        live.recording_url = url
        session.add(live)
        detail.recording_status = RecordingStatus.READY.value
        detail.recording_note = None
    else:
        # The file is in storage but no public domain is configured, so there
        # is no honest link to hand out. PROCESSING, not READY: from the
        # student's side there is still nothing to watch.
        detail.recording_status = RecordingStatus.PROCESSING.value
        detail.recording_note = (
            "The recording was captured but no public media domain is configured, "
            "so it cannot be linked yet. Ask your administrator to set S3_PUBLIC_DOMAIN."
        )
    await session.commit()
    await session.refresh(detail)
    return detail


@dataclass(frozen=True)
class RecordingCourseLink:
    """Where a finished recording belongs in the LMS."""

    course_id: Optional[int] = None
    chapter_id: Optional[int] = None
    activity_id: Optional[int] = None


async def recording_course_link(
    session: AsyncSession, *, live: LiveClassSession
) -> RecordingCourseLink:
    """Resolve the course -- and chapter, when there is one -- a recording
    belongs to.

    `sms_live_class_coursework` carries only an `activity_id`: it has no
    chapter or course column of its own, and giving it one would need an
    Alembic migration. It does not need one. Learnhouse's own content model
    already supplies the link -- `activity` -> `chapter_activity` -> `chapter`
    -> `course` -- so walking it is the minimal change and invents no parallel
    content type.

    Falls back to the session's own `course_id` when no coursework is attached.
    An unresolvable recording reports no course rather than course 0: absence
    of a link is not the same as a link to something.
    """
    coursework = (
        await session.execute(
            select(LiveClassCoursework)
            .where(LiveClassCoursework.session_id == live.id)
            .order_by(LiveClassCoursework.created_at)
        )
    ).scalars().first()

    if coursework is not None:
        row = (
            await session.execute(
                select(Activity.course_id, ChapterActivity.chapter_id)
                .join(ChapterActivity, ChapterActivity.activity_id == Activity.id)
                .where(Activity.id == coursework.activity_id)
            )
        ).first()
        if row is not None:
            return RecordingCourseLink(
                course_id=row[0], chapter_id=row[1], activity_id=coursework.activity_id
            )
        # Attached to an activity that is not in any chapter (or is gone): the
        # course is still knowable from the activity row itself.
        course_id = (
            await session.execute(
                select(Activity.course_id).where(Activity.id == coursework.activity_id)
            )
        ).scalar_one_or_none()
        if course_id is not None:
            return RecordingCourseLink(
                course_id=course_id, chapter_id=None, activity_id=coursework.activity_id
            )

    return RecordingCourseLink(course_id=live.course_id, chapter_id=None, activity_id=None)


async def finish_recording(
    session: AsyncSession, *, live: LiveClassSession
) -> Optional[LiveClassSessionDetail]:
    """Stop egress when a class ends.

    Deliberately does NOT mark the recording READY, and does not write
    `live.recording_url`. Asking Egress to stop is not the same as the file
    landing in storage -- the upload happens after this, and it can still fail.
    Publishing a URL here hands a student a link to a file that may not exist
    yet, or at all. `complete_recording_from_egress` (driven by `egress_ended`)
    is the only thing that knows the upload finished, so it is the only thing
    that sets READY.
    """
    detail = await get_detail(session, live.id)
    if detail is None or detail.recording_status != RecordingStatus.RECORDING.value:
        return detail

    if detail.egress_id:
        await stop_recording(detail.egress_id)

    detail.recording_completed_at = _now()
    started = _aware(detail.recording_started_at)
    if started is not None:
        detail.recording_duration_seconds = round((_now() - started).total_seconds(), 2)

    detail.recording_status = RecordingStatus.PROCESSING.value
    detail.recording_note = "The recording is being uploaded and will be available shortly."
    await session.commit()
    await session.refresh(detail)
    return detail


async def student_may_view_recording(
    session: AsyncSession, *, live: LiveClassSession, student_user_id: int
) -> bool:
    """A student may watch only if the teacher shared it AND they were
    actually enrolled in that section.

    Enrolment, not merely holding the STUDENT role -- otherwise any student in
    the school could watch any other class.
    """
    detail = await get_detail(session, live.id)
    if detail is None or not detail.recording_shared_with_students:
        return False
    if live.section_id is None:
        # A course-only class has no roster to check against; without a
        # defensible membership test, refuse rather than guess.
        return False
    enrolment = (
        await session.execute(
            select(StudentEnrollment).where(
                and_(
                    StudentEnrollment.section_id == live.section_id,
                    StudentEnrollment.student_id == student_user_id,
                )
            )
        )
    ).scalars().first()
    return enrolment is not None


async def attach_coursework(
    session: AsyncSession,
    *,
    live: LiveClassSession,
    activity_id: int,
    attached_by_user_id: int,
    note: Optional[str] = None,
) -> LiveClassCoursework:
    existing = (
        await session.execute(
            select(LiveClassCoursework).where(
                and_(
                    LiveClassCoursework.session_id == live.id,
                    LiveClassCoursework.activity_id == activity_id,
                )
            )
        )
    ).scalars().first()
    if existing is not None:
        return existing

    row = LiveClassCoursework(
        session_id=live.id,
        activity_id=activity_id,
        attached_by_user_id=attached_by_user_id,
        note=note,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def list_coursework(
    session: AsyncSession, *, session_id: int
) -> Sequence[LiveClassCoursework]:
    return (
        await session.execute(
            select(LiveClassCoursework)
            .where(LiveClassCoursework.session_id == session_id)
            .order_by(LiveClassCoursework.created_at)
        )
    ).scalars().all()


async def detach_coursework(
    session: AsyncSession, *, session_id: int, activity_id: int
) -> bool:
    row = (
        await session.execute(
            select(LiveClassCoursework).where(
                and_(
                    LiveClassCoursework.session_id == session_id,
                    LiveClassCoursework.activity_id == activity_id,
                )
            )
        )
    ).scalars().first()
    if row is None:
        return False
    await session.delete(row)
    await session.commit()
    return True
