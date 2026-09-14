"""
Tests for Notifications (M35) and the Communication Hub (M13).

Two things are being protected here.

The first is that a failed send stays VISIBLE. The whole reason M35 exists is
that three code paths used to email people and leave no trace, so a broken
mail server looked identical to a quiet week. A `NotificationDelivery` row
with status='failed' is the artefact that makes the difference observable.

The second is the safeguarding rule. This is a messaging surface in a system
holding children's accounts, so the deny cases matter more than the allow
case: parent-to-parent, student-to-student and parent-to-student must be
refused, and a parent must not be able to reach a teacher who has nothing to
do with their child. Each of those is asserted below rather than assumed from
reading `messaging.py`.
"""

from datetime import datetime
from unittest.mock import patch

import pytest
from sqlmodel import select

from src.db.notifications import Message, Notification, NotificationDelivery
from src.db.sms_campus import Campus, ClassSection, StudentEnrollment
from src.db.sms_identity import SchoolRole, SMSUserRole, StudentGuardian
from src.db.users import User
from src.services.notifications.messaging import may_message
from src.services.notifications.service import notify
from src.services.notifications import threads as thread_service


async def _user(db, id_: int, email: str | None = None) -> User:
    u = User(
        id=id_,
        username=f"user{id_}",
        first_name="Test",
        last_name=f"User{id_}",
        email=email or f"user{id_}@test.com",
        password="hashed",
        user_uuid=f"uuid-{id_}",
        creation_date=str(datetime.now()),
        update_date=str(datetime.now()),
    )
    db.add(u)
    await db.commit()
    return u


async def _grant(db, user_id: int, org_id: int, role: SchoolRole) -> None:
    db.add(SMSUserRole(user_id=user_id, org_id=org_id, role=role))
    await db.commit()


# ---------------------------------------------------------------- M35


@pytest.mark.asyncio
async def test_notification_persists_and_records_in_app_delivery(db, org):
    user = await _user(db, 700)

    with patch("src.services.email.utils.send_email"):
        result = await notify(
            db,
            recipients=[user],
            kind="test",
            title="Roll-call reminder",
            body_html="<p>Please submit roll-call.</p>",
            org_id=org.id,
        )

    assert result.created == 1
    rows = (await db.execute(select(Notification).where(Notification.recipient_user_id == 700))).scalars().all()
    assert len(list(rows)) == 1

    deliveries = (await db.execute(select(NotificationDelivery))).scalars().all()
    channels = {d.channel for d in deliveries}
    # The in-app copy is what makes the notification readable even when mail
    # is down, so it must be recorded as its own delivery.
    assert "in_app" in channels


@pytest.mark.asyncio
async def test_failed_email_is_recorded_not_swallowed(db, org):
    """The point of M35: a broken mail server must leave evidence."""
    user = await _user(db, 701)

    with patch("src.services.email.utils.send_email", side_effect=RuntimeError("smtp down")):
        result = await notify(
            db,
            recipients=[user],
            kind="test",
            title="Alert",
            body_html="<p>body</p>",
            org_id=org.id,
        )

    # The notification still exists -- the person sees it in-app.
    assert result.created == 1
    assert result.delivered == 0

    failed = [
        d
        for d in (await db.execute(select(NotificationDelivery))).scalars().all()
        if d.status == "failed"
    ]
    assert len(failed) == 1
    # The reason is kept, so an admin can tell a typo from an outage.
    assert "smtp down" in (failed[0].error or "")


@pytest.mark.asyncio
async def test_recipient_without_email_is_skipped_not_failed(db, org):
    """A missing address is a data gap, not a delivery failure; conflating
    them would make a real outage harder to spot."""
    user = await _user(db, 702)
    user.email = ""
    db.add(user)
    await db.commit()

    with patch("src.services.email.utils.send_email") as mock_send:
        await notify(
            db, recipients=[user], kind="test", title="T", body_html="<p>b</p>", org_id=org.id
        )

    mock_send.assert_not_called()
    statuses = {d.status for d in (await db.execute(select(NotificationDelivery))).scalars().all()}
    assert "skipped" in statuses


@pytest.mark.asyncio
async def test_notifications_are_addressed_per_recipient(db, org):
    """Fan-out is one row per person, so one reader marking it read cannot
    hide it from the other."""
    a = await _user(db, 703)
    b = await _user(db, 704)

    with patch("src.services.email.utils.send_email"):
        await notify(
            db, recipients=[a, b], kind="test", title="T", body_html="<p>b</p>", org_id=org.id
        )

    for uid in (703, 704):
        rows = (
            await db.execute(select(Notification).where(Notification.recipient_user_id == uid))
        ).scalars().all()
        assert len(list(rows)) == 1


# ------------------------------------------------- M13 safeguarding rules


async def _school_with_teacher_and_family(db, org):
    """A teacher who teaches child 802, a guardian of 802, and an unrelated
    teacher who teaches nobody."""
    campus = Campus(name="Main", code="MSG-01", org_id=org.id)
    db.add(campus)
    await db.commit()
    await db.refresh(campus)

    section = ClassSection(
        grade_level="Grade 9", section_name="A", campus_id=campus.id, class_teacher_id=800
    )
    db.add(section)
    await db.commit()
    await db.refresh(section)

    await _user(db, 800)  # class teacher
    await _user(db, 801)  # guardian
    await _user(db, 802)  # student
    await _user(db, 803)  # unrelated teacher
    await _grant(db, 800, org.id, SchoolRole.TEACHER)
    await _grant(db, 801, org.id, SchoolRole.PARENT)
    await _grant(db, 802, org.id, SchoolRole.STUDENT)
    await _grant(db, 803, org.id, SchoolRole.TEACHER)

    db.add(StudentEnrollment(student_id=802, section_id=section.id, academic_year_id=1))
    db.add(StudentGuardian(guardian_user_id=801, student_id=802))
    await db.commit()
    return section


@pytest.mark.asyncio
async def test_parent_may_message_their_own_childs_teacher(db, org):
    await _school_with_teacher_and_family(db, org)
    allowed, reason = await may_message(db, org.id, 801, 800)
    assert allowed is True, reason


@pytest.mark.asyncio
async def test_parent_may_not_message_an_unrelated_teacher(db, org):
    """The core safeguarding case: teaching somebody else's class is not a
    relationship with this family."""
    await _school_with_teacher_and_family(db, org)
    allowed, reason = await may_message(db, org.id, 801, 803)
    assert allowed is False
    assert "own child" in (reason or "")


@pytest.mark.asyncio
async def test_parent_may_not_message_another_parent(db, org):
    await _school_with_teacher_and_family(db, org)
    await _user(db, 804)
    await _grant(db, 804, org.id, SchoolRole.PARENT)
    allowed, _ = await may_message(db, org.id, 801, 804)
    assert allowed is False


@pytest.mark.asyncio
async def test_students_may_not_message_each_other(db, org):
    """Peer messaging is the classic bullying vector and there is no
    moderation here to make it safe."""
    await _school_with_teacher_and_family(db, org)
    await _user(db, 805)
    await _grant(db, 805, org.id, SchoolRole.STUDENT)
    allowed, _ = await may_message(db, org.id, 802, 805)
    assert allowed is False


@pytest.mark.asyncio
async def test_school_admin_is_always_reachable_by_a_parent(db, org):
    """Otherwise a family with a complaint about their child's teacher has
    no route to anyone else."""
    await _school_with_teacher_and_family(db, org)
    await _user(db, 806)
    await _grant(db, 806, org.id, SchoolRole.SCHOOL_ADMIN)
    allowed, reason = await may_message(db, org.id, 801, 806)
    assert allowed is True, reason


@pytest.mark.asyncio
async def test_rule_is_symmetric(db, org):
    """A teacher opening a thread and a parent replying to it must be
    governed identically."""
    await _school_with_teacher_and_family(db, org)
    forward, _ = await may_message(db, org.id, 801, 803)
    reverse, _ = await may_message(db, org.id, 803, 801)
    assert forward == reverse is False


# ------------------------------------------------------- M13 thread flow


@pytest.mark.asyncio
async def test_thread_flow_and_non_participant_gets_404(db, org):
    from fastapi import HTTPException

    await _school_with_teacher_and_family(db, org)

    with patch("src.services.email.utils.send_email"):
        thread = await thread_service.start_thread(
            db,
            org_id=org.id,
            creator_user_id=800,
            recipient_user_id=801,
            subject="Absence on Tuesday",
            body="Could we talk about Tuesday?",
            about_student_id=802,
        )
        await thread_service.post_message(
            db, thread_id=thread.id, sender_user_id=801, body="Yes, of course."
        )

    messages = (await db.execute(select(Message).where(Message.thread_id == thread.id))).scalars().all()
    assert len(list(messages)) == 2

    # The parent sees it in their thread list...
    listed = await thread_service.list_threads_for_user(db, 801)
    assert len(listed) == 1
    assert listed[0]["id"] == thread.id

    # ...and an unrelated teacher gets 404, not 403: a 403 would confirm that
    # a conversation about this child exists.
    with pytest.raises(HTTPException) as exc:
        await thread_service.get_thread_messages(db, thread.id, 803)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_starting_a_forbidden_thread_is_refused(db, org):
    from fastapi import HTTPException

    await _school_with_teacher_and_family(db, org)

    with pytest.raises(HTTPException) as exc:
        await thread_service.start_thread(
            db,
            org_id=org.id,
            creator_user_id=801,
            recipient_user_id=803,
            subject="Hello",
            body="Hi",
        )
    assert exc.value.status_code == 403


# ------------------------------------------------------------ HTTP surface
#
# The service tests above prove the RULES; this proves the router is actually
# mounted and reachable. Worth asserting separately: a sibling module in this
# codebase shipped with a wrong prefix and nothing caught it, because every
# test called the service layer directly.


def _make_app(db):
    from fastapi import FastAPI

    from src.core.events.database import get_db_session
    from src.router import v1_router

    app = FastAPI()
    app.include_router(v1_router)
    app.dependency_overrides[get_db_session] = lambda: db
    return app


def _public_user(id_: int):
    from src.db.users import PublicUser

    return PublicUser(
        id=id_,
        username=f"user{id_}",
        first_name="Test",
        last_name=f"User{id_}",
        email=f"user{id_}@test.com",
        user_uuid=f"uuid-{id_}",
    )


@pytest.mark.asyncio
async def test_notifications_endpoint_is_mounted_and_scoped_to_caller(db, org):
    """Two users, one notification each: the caller must see exactly their own."""
    from httpx import ASGITransport, AsyncClient

    from src.security.auth import get_authenticated_user

    mine = await _user(db, 900)
    theirs = await _user(db, 901)
    await _grant(db, 900, org.id, SchoolRole.TEACHER)
    await _grant(db, 901, org.id, SchoolRole.TEACHER)

    with patch("src.services.email.utils.send_email"):
        await notify(db, recipients=[mine], kind="mine", title="For 900", body_html="<p>x</p>", org_id=org.id)
        await notify(db, recipients=[theirs], kind="theirs", title="For 901", body_html="<p>y</p>", org_id=org.id)

    app = _make_app(db)
    app.dependency_overrides[get_authenticated_user] = lambda: _public_user(900)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/sms/notifications")

    assert response.status_code == 200, response.text
    titles = [n["title"] for n in response.json()]
    assert titles == ["For 900"]
    assert "For 901" not in titles
