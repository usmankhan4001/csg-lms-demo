"""
Integration tests for POST /api/v1/live/webhooks -- the real, server-verified
replacement path for client-driven live-class attendance. See
src/routers/live_class_webhooks.py.
"""

import base64
import datetime
import hashlib
import json

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from livekit.api.access_token import AccessToken
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.events.database import get_db_session
from src.db.sms_live_class import LiveClassAttendanceLog, LiveClassSession
from src.router import v1_router
from src.services.sms.live_class import get_livekit_config


def _make_app(db):
    app = FastAPI()
    app.include_router(v1_router)
    app.dependency_overrides[get_db_session] = lambda: db
    return app


def _signed_webhook(event: dict) -> tuple[str, str]:
    """Builds a (body, Authorization header) pair signed exactly the way a
    real LiveKit server signs its webhook POSTs: the BARE JWT, no "Bearer "
    prefix (unlike OAuth-style headers) -- see
    livekit.api.webhook.WebhookReceiver.receive, which verifies the raw
    token directly."""
    config = get_livekit_config()
    body = json.dumps(event)
    digest = base64.b64encode(hashlib.sha256(body.encode()).digest()).decode()
    token = AccessToken(config["api_key"], config["api_secret"]).with_sha256(digest).to_jwt()
    return body, token


async def _post_webhook(db, event: dict):
    app = _make_app(db)
    body, auth_header = _signed_webhook(event)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.post(
            "/api/v1/live/webhooks",
            content=body,
            headers={"Authorization": auth_header, "Content-Type": "application/json"},
        )


async def _create_session(db: AsyncSession, *, teacher_id: int, room_name: str) -> LiveClassSession:
    live_session = LiveClassSession(title="Live", teacher_id=teacher_id, room_name=room_name, is_active=True)
    db.add(live_session)
    await db.commit()
    await db.refresh(live_session)
    return live_session


@pytest.mark.asyncio
async def test_rejects_invalid_signature(db):
    # Tamper with the body after signing -- hash mismatch, not just bad JWT.
    config = get_livekit_config()
    body = json.dumps({"event": "room_finished", "room": {"name": "r1"}})
    digest = base64.b64encode(hashlib.sha256(body.encode()).digest()).decode()
    token = AccessToken(config["api_key"], config["api_secret"]).with_sha256(digest).to_jwt()
    tampered_body = json.dumps({"event": "room_finished", "room": {"name": "r1-tampered"}})

    app = _make_app(db)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/live/webhooks",
            content=tampered_body,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_rejects_wrong_secret(db):
    body = json.dumps({"event": "room_finished", "room": {"name": "r1"}})
    digest = base64.b64encode(hashlib.sha256(body.encode()).digest()).decode()
    token = AccessToken("devkey", "not-the-real-secret").with_sha256(digest).to_jwt()

    app = _make_app(db)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/live/webhooks",
            content=body,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_participant_joined_then_left_records_attendance(db):
    await _create_session(db, teacher_id=901, room_name="webhook-room-1")

    resp = await _post_webhook(
        db, {"event": "participant_joined", "room": {"name": "webhook-room-1"}, "participant": {"identity": "701"}}
    )
    assert resp.status_code == 204

    from sqlmodel import select

    result = await db.exec(select(LiveClassAttendanceLog).where(LiveClassAttendanceLog.student_id == 701))
    log = result.first()
    assert log is not None
    assert log.left_at is None

    resp = await _post_webhook(
        db, {"event": "participant_left", "room": {"name": "webhook-room-1"}, "participant": {"identity": "701"}}
    )
    assert resp.status_code == 204

    await db.refresh(log)
    assert log.left_at is not None


@pytest.mark.asyncio
async def test_teacher_own_presence_is_not_logged_as_student_attendance(db):
    await _create_session(db, teacher_id=902, room_name="webhook-room-2")

    resp = await _post_webhook(
        db, {"event": "participant_joined", "room": {"name": "webhook-room-2"}, "participant": {"identity": "902"}}
    )
    assert resp.status_code == 204

    from sqlmodel import select

    result = await db.exec(select(LiveClassAttendanceLog))
    assert result.first() is None


@pytest.mark.asyncio
async def test_room_finished_closes_active_session_and_open_logs(db):
    live_session = await _create_session(db, teacher_id=903, room_name="webhook-room-3")
    db.add(LiveClassAttendanceLog(session_id=live_session.id, student_id=801, joined_at=datetime.datetime.now(datetime.timezone.utc)))
    await db.commit()

    resp = await _post_webhook(db, {"event": "room_finished", "room": {"name": "webhook-room-3"}})
    assert resp.status_code == 204

    await db.refresh(live_session)
    assert live_session.is_active is False
    assert live_session.end_time is not None

    from sqlmodel import select

    result = await db.exec(select(LiveClassAttendanceLog).where(LiveClassAttendanceLog.session_id == live_session.id))
    log = result.first()
    assert log.left_at is not None


@pytest.mark.asyncio
async def test_accepts_defensive_bearer_prefix(db):
    """A valid token still verifies even if something upstream prepends
    'Bearer ' -- the router strips it defensively (see
    live_class_webhooks.py) even though real LiveKit never sends it."""
    await _create_session(db, teacher_id=904, room_name="webhook-room-4")
    body, token = _signed_webhook(
        {"event": "participant_joined", "room": {"name": "webhook-room-4"}, "participant": {"identity": "701"}}
    )
    app = _make_app(db)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/live/webhooks",
            content=body,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_unknown_room_is_a_silent_noop(db):
    resp = await _post_webhook(
        db, {"event": "participant_joined", "room": {"name": "no-such-room"}, "participant": {"identity": "701"}}
    )
    assert resp.status_code == 204
