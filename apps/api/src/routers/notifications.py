"""
Notifications (M35) and Communication Hub (M13) HTTP surface.

Thin by design: every rule that matters lives in
`services/notifications/` -- who may message whom (`messaging.py`), and what
a delivery attempt actually did (`service.py`). This file resolves the caller
and calls them.

Two access invariants, both enforced here rather than assumed:

* A caller only ever sees their OWN notifications. Every query filters on the
  caller's `lh_user_id`; there is no endpoint that takes a recipient id.
* A conversation is only readable by a participant, and reads 404 -- not 403
  -- for everyone else. Thread ids are small integers, so a 403 would confirm
  the existence of someone else's conversation about someone else's child.
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.events.database import get_db_session
from src.core.keycloak_auth import KeycloakUserPrincipal, get_current_user_principal
from src.db.notifications import Notification
from src.services.notifications import threads as thread_service

router = APIRouter(tags=["notifications"])


def _caller_id(principal: KeycloakUserPrincipal) -> int:
    """The caller's Learnhouse user id.

    Every route here is per-person, so a principal without one cannot be
    served at all -- better a clear 403 than silently returning an empty
    inbox that looks like "you have no messages".
    """
    user_id = principal.raw_claims.get("lh_user_id")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is not linked to a school user record.",
        )
    return int(user_id)


# ---------------------------------------------------------------- M35


class NotificationRead(SQLModel):
    id: int
    kind: str
    title: str
    body: str
    related_kind: Optional[str] = None
    related_id: Optional[int] = None
    is_read: bool
    created_at: datetime


class UnreadCountResponse(SQLModel):
    unread: int


@router.get(
    "/notifications",
    response_model=List[NotificationRead],
    summary="List My Notifications",
    description="The caller's own notifications, newest first. There is deliberately no recipient parameter.",
)
async def list_my_notifications(
    unread_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    db_session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> List[Notification]:
    user_id = _caller_id(principal)
    query = select(Notification).where(Notification.recipient_user_id == user_id)
    if unread_only:
        query = query.where(Notification.is_read == False)  # noqa: E712
    result = await db_session.execute(query)
    rows = list(result.scalars().all())
    rows.sort(key=lambda n: n.created_at, reverse=True)
    return rows[:limit]


@router.get(
    "/notifications/unread-count",
    response_model=UnreadCountResponse,
    summary="Count My Unread Notifications",
)
async def unread_count(
    db_session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> UnreadCountResponse:
    user_id = _caller_id(principal)
    result = await db_session.execute(
        select(Notification).where(
            Notification.recipient_user_id == user_id,
            Notification.is_read == False,  # noqa: E712
        )
    )
    return UnreadCountResponse(unread=len(list(result.scalars().all())))


@router.post(
    "/notifications/{notification_id}/read",
    response_model=NotificationRead,
    summary="Mark a Notification Read",
    responses={404: {"description": "Not found, or not addressed to you"}},
)
async def mark_read(
    notification_id: int,
    db_session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> Notification:
    user_id = _caller_id(principal)
    notification = await db_session.get(Notification, notification_id)
    # 404 rather than 403 on someone else's notification: the caller has no
    # business learning that it exists.
    if notification is None or notification.recipient_user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")

    notification.is_read = True
    notification.read_at = datetime.now(notification.created_at.tzinfo)
    db_session.add(notification)
    await db_session.commit()
    await db_session.refresh(notification)
    return notification


@router.post(
    "/notifications/read-all",
    response_model=UnreadCountResponse,
    summary="Mark All My Notifications Read",
)
async def mark_all_read(
    db_session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> UnreadCountResponse:
    user_id = _caller_id(principal)
    result = await db_session.execute(
        select(Notification).where(
            Notification.recipient_user_id == user_id,
            Notification.is_read == False,  # noqa: E712
        )
    )
    rows = list(result.scalars().all())
    now = datetime.now()
    for row in rows:
        row.is_read = True
        row.read_at = datetime.now(row.created_at.tzinfo) if row.created_at.tzinfo else now
        db_session.add(row)
    await db_session.commit()
    return UnreadCountResponse(unread=0)


# ---------------------------------------------------------------- M13


class ThreadSummary(SQLModel):
    id: int
    subject: str
    about_student_id: Optional[int] = None
    last_message_at: datetime
    message_count: int
    unread_count: int


class MessageRead(SQLModel):
    id: int
    sender_user_id: int
    body: str
    created_at: datetime


class StartThreadRequest(SQLModel):
    recipient_user_id: int
    subject: str
    body: str
    about_student_id: Optional[int] = None


class PostMessageRequest(SQLModel):
    body: str


@router.get(
    "/messages/threads",
    response_model=List[ThreadSummary],
    summary="List My Conversations",
)
async def list_threads(
    db_session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
):
    user_id = _caller_id(principal)
    return await thread_service.list_threads_for_user(db_session, user_id)


@router.get(
    "/messages/threads/{thread_id}",
    response_model=List[MessageRead],
    summary="Read a Conversation",
    description="Messages oldest-first. Marks the conversation read for the caller.",
    responses={404: {"description": "Not found, or you are not a participant"}},
)
async def read_thread(
    thread_id: int,
    db_session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
):
    user_id = _caller_id(principal)
    return await thread_service.get_thread_messages(db_session, thread_id, user_id)


@router.post(
    "/messages/threads",
    response_model=ThreadSummary,
    status_code=status.HTTP_201_CREATED,
    summary="Start a Conversation",
    description=(
        "Refused with 403 unless a school relationship permits the pair -- staff "
        "to staff, or a family to staff connected to their own child. Parent-to-"
        "parent, student-to-student and parent-to-student are never permitted."
    ),
    responses={403: {"description": "No school relationship permits this conversation"}},
)
async def start_thread(
    payload: StartThreadRequest,
    db_session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
):
    user_id = _caller_id(principal)
    if principal.org_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No organisation context for this account.",
        )
    thread = await thread_service.start_thread(
        db_session,
        org_id=principal.org_id,
        creator_user_id=user_id,
        recipient_user_id=payload.recipient_user_id,
        subject=payload.subject,
        body=payload.body,
        about_student_id=payload.about_student_id,
    )
    return ThreadSummary(
        id=thread.id,
        subject=thread.subject,
        about_student_id=thread.about_student_id,
        last_message_at=thread.last_message_at,
        message_count=1,
        unread_count=0,
    )


@router.post(
    "/messages/threads/{thread_id}/messages",
    response_model=MessageRead,
    status_code=status.HTTP_201_CREATED,
    summary="Reply to a Conversation",
    description="The access rule is re-checked on every reply, not only at creation.",
    responses={
        403: {"description": "The school relationship no longer permits this conversation"},
        404: {"description": "Not found, or you are not a participant"},
    },
)
async def post_message(
    thread_id: int,
    payload: PostMessageRequest,
    db_session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
):
    user_id = _caller_id(principal)
    return await thread_service.post_message(
        db_session, thread_id=thread_id, sender_user_id=user_id, body=payload.body
    )
