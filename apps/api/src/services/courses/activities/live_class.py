"""Live class as a first-class course activity.

Before this, a live class lived only on a detached `/live/{roomId}` page: a
teacher started one from their dashboard and handed out the URL. It was not
part of any course, so it never appeared in the chapter structure, never
showed in the activity strip, and a student browsing the course had no way
to reach it.

This mirrors `video.create_external_video_activity` exactly -- same RBAC
gate, same Activity + ChapterActivity pair, same `content` dict for the
type's payload -- so a live class flows through the course builder like any
other activity type.

The LiveKit half is reused wholesale from `services/sms/live_class.py`
(token minting, room provisioning); nothing here re-implements it. The one
thing deliberately NOT reused is the `is_teacher` flag: the existing
`/live/rooms/{room}/token` endpoint takes it from the request body, which is
workable for the dashboard flow but would let any student mint a host token
by flipping a boolean. Here it is derived server-side from whether the
caller can actually edit the course -- see `resolve_join_grant`.
"""

import logging
import uuid as uuid_module
from datetime import datetime
from typing import Optional
from uuid import uuid4

from fastapi import HTTPException, Request
from pydantic import BaseModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.courses.activities import (
    Activity,
    ActivityRead,
    ActivitySubTypeEnum,
    ActivityTypeEnum,
)
from src.db.courses.chapter_activities import ChapterActivity
from src.db.courses.chapters import Chapter
from src.db.courses.course_chapters import CourseChapter
from src.db.courses.courses import Course
from src.db.sms_live_class import LiveClassSession
from src.db.users import AnonymousUser, PublicUser
from src.security.rbac import AccessAction, check_resource_access
from src.services.sms.live_class import (
    create_room_on_server,
    generate_livekit_token,
    get_livekit_config,
)

logger = logging.getLogger(__name__)


class LiveClassActivityCreate(BaseModel):
    name: str
    chapter_id: int
    description: Optional[str] = None
    extra_metadata: Optional[dict] = None


class LiveClassJoinResponse(BaseModel):
    room_name: str
    token: str
    livekit_url: str
    is_host: bool
    participant_name: str


async def _load_course_for_chapter(chapter_id: int, db_session: AsyncSession):
    """Resolve chapter -> coursechapter -> course, 404ing at whichever link
    is missing. Same three-step walk the video and document services do."""
    chapter = (
        await db_session.execute(select(Chapter).where(Chapter.id == chapter_id))
    ).scalars().first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")

    coursechapter = (
        await db_session.execute(
            select(CourseChapter).where(CourseChapter.chapter_id == chapter_id)
        )
    ).scalars().first()
    if not coursechapter:
        raise HTTPException(status_code=404, detail="CourseChapter not found")

    course = (
        await db_session.execute(
            select(Course).where(Course.id == coursechapter.course_id)
        )
    ).scalars().first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    return chapter, coursechapter, course


async def create_liveclass_activity(
    request: Request,
    current_user: PublicUser | AnonymousUser,
    data: LiveClassActivityCreate,
    db_session: AsyncSession,
) -> ActivityRead:
    """Create a live-class activity and provision its LiveKit room."""
    _, coursechapter, course = await _load_course_for_chapter(
        data.chapter_id, db_session
    )

    await check_resource_access(
        request, db_session, current_user, course.course_uuid, AccessAction.CREATE
    )

    activity_uuid = str(f"activity_{uuid4()}")
    room_name = f"course-{uuid_module.uuid4().hex[:10]}"

    # The LiveClassSession row stays the room's source of truth (it already
    # carries course_id), so attendance webhooks, the active-rooms list and
    # the end-session path all keep working unchanged for a room created
    # from a course. The Activity only stores the room_name pointing at it.
    teacher_id = getattr(current_user, "id", 0) or 0
    live_session = LiveClassSession(
        title=data.name,
        teacher_id=teacher_id,
        section_id=None,
        course_id=coursechapter.course_id,
        room_name=room_name,
        is_active=True,
    )
    db_session.add(live_session)
    await db_session.commit()
    await db_session.refresh(live_session)

    # Best-effort, never raises (see create_room_on_server's docstring): a
    # LiveKit server that is down must not stop the teacher adding the
    # activity, since the room auto-creates on first join anyway.
    await create_room_on_server(room_name)

    activity_object = Activity(
        name=data.name,
        activity_type=ActivityTypeEnum.TYPE_LIVECLASS,
        activity_sub_type=ActivitySubTypeEnum.SUBTYPE_LIVECLASS_LIVEKIT,
        activity_uuid=activity_uuid,
        course_id=coursechapter.course_id,
        org_id=coursechapter.org_id,
        content={
            "room_name": room_name,
            "live_session_id": live_session.id,
            "activity_uuid": activity_uuid,
        },
        details={"description": data.description or ""},
        creation_date=str(datetime.now()),
        update_date=str(datetime.now()),
        extra_metadata=data.extra_metadata,
    )

    activity = Activity.model_validate(activity_object)
    db_session.add(activity)
    await db_session.commit()
    await db_session.refresh(activity)

    # Append to the end of the chapter, same ordering rule as every other type.
    chapter_activities = (
        await db_session.execute(
            select(ChapterActivity)
            .where(ChapterActivity.chapter_id == coursechapter.chapter_id)
            .order_by(ChapterActivity.order)  # type: ignore
        )
    ).scalars().all()
    last_order = chapter_activities[-1].order if chapter_activities else 0

    db_session.add(
        ChapterActivity(
            chapter_id=coursechapter.chapter_id,  # type: ignore
            activity_id=activity.id,  # type: ignore
            course_id=coursechapter.course_id,
            org_id=coursechapter.org_id,
            creation_date=str(datetime.now()),
            update_date=str(datetime.now()),
            order=last_order + 1,
        )
    )
    await db_session.commit()

    return ActivityRead.model_validate(activity)


async def resolve_join_grant(
    request: Request,
    activity_uuid: str,
    current_user: PublicUser | AnonymousUser,
    db_session: AsyncSession,
) -> LiveClassJoinResponse:
    """Mint a join token for a live-class activity.

    Two checks, in order:

    1. READ on the course -- you must be able to see the activity to join
       its room at all. This is what stops someone with a guessed
       activity_uuid getting a token.
    2. UPDATE on the course, evaluated with `raise_on_deny=False`, decides
       HOST vs PARTICIPANT. Someone who can edit the course is running it
       and gets room_admin/record rights; everyone else joins as a normal
       participant.

    Deriving the role from a permission the user provably already has --
    rather than from a request field -- is the whole difference between this
    and the dashboard token endpoint. A student cannot ask for host rights.
    """
    activity = (
        await db_session.execute(
            select(Activity).where(Activity.activity_uuid == activity_uuid)
        )
    ).scalars().first()
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")

    if activity.activity_type != ActivityTypeEnum.TYPE_LIVECLASS:
        raise HTTPException(
            status_code=400, detail="This activity is not a live class"
        )

    course = (
        await db_session.execute(
            select(Course).where(Course.id == activity.course_id)
        )
    ).scalars().first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    await check_resource_access(
        request, db_session, current_user, course.course_uuid, AccessAction.READ
    )

    host_decision = await check_resource_access(
        request,
        db_session,
        current_user,
        course.course_uuid,
        AccessAction.UPDATE,
        raise_on_deny=False,
    )
    is_host = bool(host_decision.allowed)

    room_name = (activity.content or {}).get("room_name")
    if not room_name:
        raise HTTPException(
            status_code=409,
            detail="This live class has no room attached. Recreate the activity.",
        )

    participant_id = str(getattr(current_user, "id", "") or "")
    if not participant_id:
        raise HTTPException(
            status_code=401, detail="You must be signed in to join a live class"
        )

    participant_name = (
        getattr(current_user, "username", None)
        or getattr(current_user, "email", None)
        or f"Participant {participant_id}"
    )

    token = generate_livekit_token(
        room_name=room_name,
        participant_id=participant_id,
        participant_name=participant_name,
        is_teacher=is_host,
        can_publish=True,
        can_subscribe=True,
    )

    return LiveClassJoinResponse(
        room_name=room_name,
        token=token,
        livekit_url=get_livekit_config()["url"],
        is_host=is_host,
        participant_name=participant_name,
    )
