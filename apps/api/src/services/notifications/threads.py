"""
Conversation CRUD for the Communication Hub (M13).

Kept separate from `messaging.py`, which owns the *access rules*: that file
answers "may these two people talk at all", this one does the reading and
writing. The split matters because every write path here is forced through
`assert_may_message` / `assert_participant` in one place, rather than each
endpoint being trusted to remember.

Unread counts are derived from `ThreadParticipant.last_read_at` against
message timestamps rather than stored as a counter. A stored counter drifts
the moment a message is deleted, backfilled, or written by a background job,
and a wrong unread badge is the kind of bug nobody reports but everybody
stops trusting.
"""

import datetime
import logging
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.notifications import Message, MessageThread, ThreadParticipant
from src.db.users import User
from src.services.notifications.messaging import assert_may_message
from src.services.notifications.service import notify

logger = logging.getLogger(__name__)


def _utc_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


async def assert_participant(
    db_session: AsyncSession, thread_id: int, user_id: int
) -> ThreadParticipant:
    """Membership is the read gate.

    Returns 404 rather than 403 for a non-participant: a thread id is a small
    integer and therefore guessable, and "403" on someone else's conversation
    confirms that conversation exists. Absence is the honest answer.
    """
    res = await db_session.execute(
        select(ThreadParticipant).where(
            ThreadParticipant.thread_id == thread_id,
            ThreadParticipant.user_id == user_id,
        )
    )
    participant = res.scalars().first()
    if participant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return participant


async def list_threads_for_user(db_session: AsyncSession, user_id: int) -> List[Dict[str, Any]]:
    """Threads this user participates in, most recent activity first."""
    part_res = await db_session.execute(
        select(ThreadParticipant).where(ThreadParticipant.user_id == user_id)
    )
    parts = list(part_res.scalars().all())
    if not parts:
        return []

    by_thread = {p.thread_id: p for p in parts}
    thread_res = await db_session.execute(
        select(MessageThread).where(
            MessageThread.id.in_(list(by_thread.keys()))  # type: ignore[attr-defined]
        )
    )
    threads = list(thread_res.scalars().all())
    threads.sort(key=lambda t: t.last_message_at, reverse=True)

    out: List[Dict[str, Any]] = []
    for thread in threads:
        part = by_thread[thread.id]
        msg_res = await db_session.execute(select(Message).where(Message.thread_id == thread.id))
        messages = list(msg_res.scalars().all())
        unread = sum(
            1
            for m in messages
            if m.sender_user_id != user_id
            and (part.last_read_at is None or m.created_at > part.last_read_at)
        )
        out.append(
            {
                "id": thread.id,
                "subject": thread.subject,
                "about_student_id": thread.about_student_id,
                "last_message_at": thread.last_message_at,
                "message_count": len(messages),
                "unread_count": unread,
            }
        )
    return out


async def get_thread_messages(
    db_session: AsyncSession, thread_id: int, user_id: int
) -> List[Dict[str, Any]]:
    """Messages oldest-first, and marks the thread read for this reader.

    Opening a conversation IS reading it, so the read marker is a side effect
    here rather than a separate call the client has to remember to make.
    """
    participant = await assert_participant(db_session, thread_id, user_id)

    res = await db_session.execute(select(Message).where(Message.thread_id == thread_id))
    messages = list(res.scalars().all())
    messages.sort(key=lambda m: m.created_at)

    participant.last_read_at = _utc_now()
    db_session.add(participant)
    await db_session.commit()

    return [
        {
            "id": m.id,
            "sender_user_id": m.sender_user_id,
            "body": m.body,
            "created_at": m.created_at,
        }
        for m in messages
    ]


async def start_thread(
    db_session: AsyncSession,
    *,
    org_id: int,
    creator_user_id: int,
    recipient_user_id: int,
    subject: str,
    body: str,
    about_student_id: Optional[int] = None,
) -> MessageThread:
    """Create a conversation and its first message.

    Raises 403 unless a school relationship permits the pair -- see
    `messaging.py`'s docstring for which pairs those are and why.
    """
    await assert_may_message(db_session, org_id, creator_user_id, recipient_user_id)

    thread = MessageThread(
        org_id=org_id,
        subject=subject,
        created_by_user_id=creator_user_id,
        about_student_id=about_student_id,
    )
    db_session.add(thread)
    await db_session.commit()
    await db_session.refresh(thread)

    for uid in (creator_user_id, recipient_user_id):
        db_session.add(ThreadParticipant(thread_id=thread.id, user_id=uid))
    db_session.add(Message(thread_id=thread.id, sender_user_id=creator_user_id, body=body))
    await db_session.commit()
    await db_session.refresh(thread)

    await _notify_others(db_session, thread=thread, sender_user_id=creator_user_id, body=body)
    return thread


async def post_message(
    db_session: AsyncSession, *, thread_id: int, sender_user_id: int, body: str
) -> Message:
    """Reply to an existing thread.

    The access rule is re-checked on every reply, not only at creation. A
    teacher can stop teaching a child mid-year; a thread that was legitimate
    in September should not stay open on the strength of that forever.
    """
    await assert_participant(db_session, thread_id, sender_user_id)

    thread = await db_session.get(MessageThread, thread_id)
    if thread is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    others_res = await db_session.execute(
        select(ThreadParticipant).where(
            ThreadParticipant.thread_id == thread_id,
            ThreadParticipant.user_id != sender_user_id,
        )
    )
    for other in others_res.scalars().all():
        await assert_may_message(db_session, thread.org_id, sender_user_id, other.user_id)

    message = Message(thread_id=thread_id, sender_user_id=sender_user_id, body=body)
    db_session.add(message)
    thread.last_message_at = _utc_now()
    db_session.add(thread)
    await db_session.commit()
    await db_session.refresh(message)

    await _notify_others(db_session, thread=thread, sender_user_id=sender_user_id, body=body)
    return message


async def _notify_others(
    db_session: AsyncSession, *, thread: MessageThread, sender_user_id: int, body: str
) -> None:
    """Tell the other participants through the same M35 service everything
    else uses, so a message shows up in one inbox rather than a second one.

    Never raises: the message is already committed by this point, and losing
    it because a notification failed would be the worse outcome.
    """
    try:
        res = await db_session.execute(
            select(ThreadParticipant).where(
                ThreadParticipant.thread_id == thread.id,
                ThreadParticipant.user_id != sender_user_id,
            )
        )
        user_ids = [p.user_id for p in res.scalars().all()]
        if not user_ids:
            return

        users_res = await db_session.execute(
            select(User).where(User.id.in_(user_ids))  # type: ignore[attr-defined]
        )
        await notify(
            db_session,
            recipients=list(users_res.scalars().all()),
            kind="message",
            title=f"New message: {thread.subject}",
            # Truncated: an email preview, not the whole conversation. The
            # full text stays in the app behind the membership check.
            body_html=body[:1000],
            org_id=thread.org_id,
            related_kind="message_thread",
            related_id=thread.id,
        )
    except Exception:
        logger.exception("Failed to notify participants of thread %s", getattr(thread, "id", None))
