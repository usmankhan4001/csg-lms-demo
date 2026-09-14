"""
LiveKit server-to-server webhook receiver.

Unlike every other endpoint under /live, this one is called by the LiveKit
media server itself, not by a logged-in Learnhouse user or an API token --
mounting it under the same `require_authenticated_user_or_api_token`
dependency as `live_classes.router` would make it uncallable (LiveKit has no
Learnhouse session or API token). Authenticity is verified LiveKit's own way
instead: every webhook POST carries a JWT (in `Authorization`) signed with
the same `LIVEKIT_API_SECRET`, over a body whose sha256 is one of the JWT's
own claims (`verify_and_parse_webhook` checks both) -- an unverified or
mismatched signature is rejected with 401, so this is not an open write
endpoint despite needing no Learnhouse auth. See router.py for the mount
(same "/live" prefix as live_classes.router, no auth dependency, distinct
route path -- no collision).

Turns real, server-verified `participant_joined`/`participant_left`/
`room_finished` events into `LiveClassAttendanceLog` rows: the authoritative
replacement for the client-driven `POST /rooms/{room}/attendance` calls in
live_classes.py (kept there for backward compatibility / manual testing,
but a client can simply not call them, or lie about timing; this cannot,
since the event only exists if LiveKit's own server actually saw the
participant connect/disconnect).
"""

import datetime
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import and_, desc, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.events.database import get_db_session
from src.db.sms_live_class import LiveClassAttendanceLog, LiveClassSession
from src.services.sms.live_class import verify_and_parse_webhook

logger = logging.getLogger(__name__)
router = APIRouter()


def _parse_student_identity(identity: str, live_session: LiveClassSession) -> Optional[int]:
    """Participant identity is always the Learnhouse user_id as a string
    (see `generate_livekit_token`'s `with_identity`). The teacher joins the
    same room under their own identity -- their own presence isn't "student
    attendance", so it's excluded here rather than logged alongside real
    students."""
    try:
        user_id = int(identity)
    except (TypeError, ValueError):
        return None
    if user_id == live_session.teacher_id:
        return None
    return user_id


def _close_log(log: LiveClassAttendanceLog, at: datetime.datetime) -> None:
    log.left_at = at
    joined_aware = log.joined_at if log.joined_at.tzinfo else log.joined_at.replace(tzinfo=datetime.timezone.utc)
    diff = (at - joined_aware).total_seconds() / 60.0
    log.duration_minutes = max(round(diff, 2), 0.0)


@router.post(
    "/webhooks",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="LiveKit Server Webhook Receiver",
    description=(
        "Called by the LiveKit media server (not a Learnhouse client) on room/"
        "participant lifecycle events. Verifies the LiveKit-signed request "
        "before trusting anything in it. Records server-verified attendance."
    ),
)
async def receive_livekit_webhook(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    body = await request.body()
    # LiveKit's real webhook POST sets Authorization to the bare signed JWT
    # (no "Bearer " prefix, unlike OAuth-style headers) -- strip one anyway
    # if present, defensively, in case a proxy/relay adds it.
    auth_header = request.headers.get("Authorization", "")
    if auth_header.lower().startswith("bearer "):
        auth_header = auth_header[len("bearer ") :]
    try:
        event = verify_and_parse_webhook(body.decode("utf-8"), auth_header)
    except Exception:
        # Broad on purpose: an invalid/expired JWT signature raises a
        # jwt.PyJWTError, but a well-signed token whose sha256 claim doesn't
        # match a tampered body raises a plain `Exception("hash mismatch")`
        # from livekit.api.webhook.WebhookReceiver.receive -- both are
        # "reject this webhook" cases, never a 500.
        logger.warning("Rejected LiveKit webhook: signature/hash verification failed", exc_info=True)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook signature")

    room_name = event.room.name if event.room else None
    if not room_name:
        return None

    stmt = select(LiveClassSession).where(LiveClassSession.room_name == room_name)
    live_session = (await session.execute(stmt)).scalars().first()
    if not live_session:
        # A room LiveKit knows about but this app never created a session
        # row for (shouldn't happen in practice) -- nothing to attribute the
        # event to, so no-op rather than error, matching the client-driven
        # endpoints' own not-a-Learnhouse-concern-yet tolerance.
        return None

    now = datetime.datetime.now(datetime.timezone.utc)

    if event.event == "participant_joined" and event.participant:
        student_id = _parse_student_identity(event.participant.identity, live_session)
        if student_id is not None:
            session.add(LiveClassAttendanceLog(session_id=live_session.id, student_id=student_id, joined_at=now))
            await session.commit()

    elif event.event == "participant_left" and event.participant:
        student_id = _parse_student_identity(event.participant.identity, live_session)
        if student_id is not None:
            log_stmt = (
                select(LiveClassAttendanceLog)
                .where(
                    and_(
                        LiveClassAttendanceLog.session_id == live_session.id,
                        LiveClassAttendanceLog.student_id == student_id,
                        LiveClassAttendanceLog.left_at.is_(None),
                    )
                )
                .order_by(desc(LiveClassAttendanceLog.joined_at))
            )
            log = (await session.execute(log_stmt)).scalars().first()
            if log:
                _close_log(log, now)
                await session.commit()

    elif event.event == "room_finished":
        live_session.is_active = False
        live_session.end_time = now
        open_logs_stmt = select(LiveClassAttendanceLog).where(
            and_(
                LiveClassAttendanceLog.session_id == live_session.id,
                LiveClassAttendanceLog.left_at.is_(None),
            )
        )
        open_logs = (await session.execute(open_logs_stmt)).scalars().all()
        for log in open_logs:
            _close_log(log, now)
        await session.commit()

    return None
