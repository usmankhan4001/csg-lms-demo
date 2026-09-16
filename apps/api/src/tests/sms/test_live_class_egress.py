"""
LiveKit Egress end-to-end: `room_started` dispatches a composite recording and
`egress_ended` persists it. Both arrive on the same server-verified webhook as
attendance (src/routers/live_class_webhooks.py) -- there is no separate,
unauthenticated path for them.

The three behaviours this file exists to pin down:

1. A finished egress is persisted (duration, object key, status).
2. A failed dispatch does not break the webhook -- the class still runs.
3. A recording is never READY without a successful egress event. (3) is the
   one that matters most: a "Recording" link that 404s is worse for a student
   than an honest "not available yet".
"""

import base64
import hashlib
import json

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from livekit.api.access_token import AccessToken
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.events.database import get_db_session
from src.db.sms_live_class import (
    LiveClassCoursework,
    LiveClassSession,
    LiveClassSessionDetail,
    RecordingStatus,
)
from src.router import v1_router
from src.services.sms import live_class_recording, live_class_schedule as lc_schedule
from src.services.sms.live_class import get_livekit_config
from src.services.sms.live_class_recording import RecordingStorageUnavailable

# LiveKit reports egress durations in nanoseconds.
_ONE_MINUTE_NS = 60_000_000_000


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_app(db):
    app = FastAPI()
    app.include_router(v1_router)
    app.dependency_overrides[get_db_session] = lambda: db
    return app


def _signed_webhook(event: dict) -> tuple[str, str]:
    """Signed exactly the way a real LiveKit server signs its webhook POSTs."""
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


async def _create_session(
    db: AsyncSession, *, teacher_id: int, room_name: str, course_id: int | None = None
) -> LiveClassSession:
    live = LiveClassSession(
        title="Live",
        teacher_id=teacher_id,
        room_name=room_name,
        course_id=course_id,
        is_active=True,
    )
    db.add(live)
    await db.commit()
    await db.refresh(live)
    return live


async def _create_detail(
    db: AsyncSession,
    *,
    session_id: int,
    recording_enabled: bool = True,
    recording_status: str = RecordingStatus.PENDING.value,
) -> LiveClassSessionDetail:
    detail = LiveClassSessionDetail(
        session_id=session_id,
        recording_enabled=recording_enabled,
        recording_status=recording_status,
    )
    db.add(detail)
    await db.commit()
    await db.refresh(detail)
    return detail


async def _detail_for(db: AsyncSession, session_id: int) -> LiveClassSessionDetail | None:
    return (
        await db.execute(
            select(LiveClassSessionDetail).where(LiveClassSessionDetail.session_id == session_id)
        )
    ).scalar_one_or_none()


def _egress_event(
    room_name: str,
    *,
    status: str = "EGRESS_COMPLETE",
    egress_id: str = "EG_test_1",
    filename: str | None = "live-classes/2026/09/16/session-1-egress-room.mp4",
    duration_ns: int | None = _ONE_MINUTE_NS,
    size: int | None = 12_345_678,
    error: str | None = None,
    with_room: bool = True,
) -> dict:
    info: dict = {
        "egress_id": egress_id,
        "room_name": room_name,
        "status": status,
        "started_at": "1692057600000000000",
        "ended_at": "1692057660000000000",
    }
    if error:
        info["error"] = error
    if filename is not None:
        info["file_results"] = [
            {
                "filename": filename,
                "duration": str(duration_ns),
                "size": str(size),
                "location": f"https://cdn.test/{filename}",
            }
        ]
    event: dict = {"event": "egress_ended", "egress_info": info}
    if with_room:
        event["room"] = {"name": room_name}
    return event


@pytest.fixture
def storage(monkeypatch):
    """Object storage configured, with a public domain to link recordings from.

    Patched at `get_recording_storage` -- the single source both
    `recording_is_available()` and `public_url_for()` read -- so the real
    resolution and URL-building code runs rather than a stubbed URL.
    """
    cfg = {
        "bucket": "test-bucket",
        "endpoint": None,
        "access_key": "ak",
        "secret_key": "sk",
        "region": "auto",
        "public_domain": "https://cdn.test",
    }
    monkeypatch.setattr(live_class_recording, "get_recording_storage", lambda: (cfg, None))
    return cfg


# ---------------------------------------------------------------------------
# room_started -> dispatch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_room_started_dispatches_composite_egress(db, monkeypatch, storage):
    live = await _create_session(db, teacher_id=1001, room_name="egress-room-1")
    await _create_detail(db, session_id=live.id)

    called = {}

    async def fake_start(room_name, session_id):
        called["args"] = (room_name, session_id)
        return "EG_dispatched", "live-classes/2026/09/16/session-1.mp4"

    monkeypatch.setattr(lc_schedule, "start_recording", fake_start)

    resp = await _post_webhook(db, {"event": "room_started", "room": {"name": "egress-room-1"}})
    assert resp.status_code == 204
    assert called["args"] == ("egress-room-1", live.id)

    detail = await _detail_for(db, live.id)
    assert detail.recording_status == RecordingStatus.RECORDING.value
    assert detail.egress_id == "EG_dispatched"
    assert detail.recording_object_key == "live-classes/2026/09/16/session-1.mp4"
    assert detail.recording_started_at is not None


@pytest.mark.asyncio
async def test_room_started_dispatch_failure_does_not_break_webhook(db, monkeypatch, storage):
    """The class must still run when the recorder is unreachable.

    LiveKit's own client caps a dispatch at 10s, so this cannot hang the
    webhook either -- but whatever the failure, it is recorded on the class
    and the response stays 204 (a non-2xx makes LiveKit retry forever).
    """
    live = await _create_session(db, teacher_id=1002, room_name="egress-room-2")
    await _create_detail(db, session_id=live.id)

    async def boom(room_name, session_id):
        raise RuntimeError("no response from egress service")

    monkeypatch.setattr(lc_schedule, "start_recording", boom)

    resp = await _post_webhook(db, {"event": "room_started", "room": {"name": "egress-room-2"}})
    assert resp.status_code == 204

    detail = await _detail_for(db, live.id)
    assert detail.recording_status == RecordingStatus.FAILED.value
    assert "no response from egress service" in (detail.recording_note or "")
    # Never a fabricated success.
    assert detail.egress_id is None


@pytest.mark.asyncio
async def test_room_started_without_storage_records_unavailable(db, monkeypatch, storage):
    """No object storage is UNAVAILABLE, not FAILED -- nobody broke anything,
    the deployment simply cannot record."""
    live = await _create_session(db, teacher_id=1003, room_name="egress-room-3")
    await _create_detail(db, session_id=live.id)

    async def boom(room_name, session_id):
        raise RecordingStorageUnavailable("Class recording is not available on this deployment.")

    monkeypatch.setattr(lc_schedule, "start_recording", boom)

    resp = await _post_webhook(db, {"event": "room_started", "room": {"name": "egress-room-3"}})
    assert resp.status_code == 204

    detail = await _detail_for(db, live.id)
    assert detail.recording_status == RecordingStatus.UNAVAILABLE.value
    assert "not available on this deployment" in (detail.recording_note or "")


@pytest.mark.asyncio
async def test_room_started_does_not_dispatch_twice(db, monkeypatch, storage):
    """`start_live_class` may already have dispatched one; `room_started`
    fires on the first join. A second egress would record the class twice and
    orphan the first file."""
    live = await _create_session(db, teacher_id=1004, room_name="egress-room-4")
    await _create_detail(
        db,
        session_id=live.id,
        recording_status=RecordingStatus.RECORDING.value,
    )

    async def boom(room_name, session_id):
        raise AssertionError("must not dispatch a second egress")

    monkeypatch.setattr(lc_schedule, "start_recording", boom)

    resp = await _post_webhook(db, {"event": "room_started", "room": {"name": "egress-room-4"}})
    assert resp.status_code == 204
    assert (await _detail_for(db, live.id)).recording_status == RecordingStatus.RECORDING.value


@pytest.mark.asyncio
async def test_room_started_without_teacher_opt_in_does_not_record(db, monkeypatch, storage):
    live = await _create_session(db, teacher_id=1005, room_name="egress-room-5")
    await _create_detail(db, session_id=live.id, recording_enabled=False)

    async def boom(room_name, session_id):
        raise AssertionError("recording is opt-in; must not dispatch")

    monkeypatch.setattr(lc_schedule, "start_recording", boom)

    resp = await _post_webhook(db, {"event": "room_started", "room": {"name": "egress-room-5"}})
    assert resp.status_code == 204
    assert (await _detail_for(db, live.id)).egress_id is None


# ---------------------------------------------------------------------------
# egress_ended -> persist
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_egress_ended_persists_recording(db, storage):
    live = await _create_session(db, teacher_id=1010, room_name="egress-room-10")
    await _create_detail(
        db,
        session_id=live.id,
        recording_status=RecordingStatus.RECORDING.value,
    )

    resp = await _post_webhook(db, _egress_event("egress-room-10"))
    assert resp.status_code == 204

    detail = await _detail_for(db, live.id)
    assert detail.recording_status == RecordingStatus.READY.value
    assert detail.egress_id == "EG_test_1"
    assert detail.recording_object_key == "live-classes/2026/09/16/session-1-egress-room.mp4"
    # 60s, converted from LiveKit's nanoseconds.
    assert detail.recording_duration_seconds == 60.0
    assert detail.recording_completed_at is not None
    assert detail.recording_note is None

    await db.refresh(live)
    assert live.recording_url == (
        "https://cdn.test/live-classes/2026/09/16/session-1-egress-room.mp4"
    )


@pytest.mark.asyncio
async def test_egress_ended_resolves_room_from_egress_payload(db, storage):
    """`room` is not always populated on egress events; the room name on the
    egress payload must still attribute the recording to the right class."""
    live = await _create_session(db, teacher_id=1011, room_name="egress-room-11")
    await _create_detail(
        db,
        session_id=live.id,
        recording_status=RecordingStatus.RECORDING.value,
    )

    resp = await _post_webhook(db, _egress_event("egress-room-11", with_room=False))
    assert resp.status_code == 204
    assert (await _detail_for(db, live.id)).recording_status == RecordingStatus.READY.value


@pytest.mark.asyncio
async def test_egress_ended_failure_is_recorded_not_ready(db, storage):
    live = await _create_session(db, teacher_id=1012, room_name="egress-room-12")
    await _create_detail(
        db,
        session_id=live.id,
        recording_status=RecordingStatus.RECORDING.value,
    )

    resp = await _post_webhook(
        db,
        _egress_event(
            "egress-room-12",
            status="EGRESS_FAILED",
            filename=None,
            error="failed to upload to S3",
        ),
    )
    assert resp.status_code == 204

    detail = await _detail_for(db, live.id)
    assert detail.recording_status == RecordingStatus.FAILED.value
    assert "failed to upload to S3" in (detail.recording_note or "")

    await db.refresh(live)
    assert live.recording_url is None


@pytest.mark.asyncio
async def test_egress_ended_complete_without_file_is_not_ready(db, storage):
    """EGRESS_COMPLETE alone is not enough -- with no file result nothing was
    written, so there is nothing to watch."""
    live = await _create_session(db, teacher_id=1013, room_name="egress-room-13")
    await _create_detail(
        db,
        session_id=live.id,
        recording_status=RecordingStatus.RECORDING.value,
    )

    resp = await _post_webhook(db, _egress_event("egress-room-13", filename=None))
    assert resp.status_code == 204

    detail = await _detail_for(db, live.id)
    assert detail.recording_status == RecordingStatus.FAILED.value
    await db.refresh(live)
    assert live.recording_url is None


@pytest.mark.asyncio
async def test_egress_ended_without_public_domain_is_processing_not_ready(db, monkeypatch):
    """The file exists but there is no honest link to hand out. PROCESSING,
    not READY -- from the student's side there is still nothing to watch."""
    monkeypatch.setattr(
        live_class_recording,
        "get_recording_storage",
        lambda: (
            {
                "bucket": "test-bucket",
                "endpoint": None,
                "access_key": "ak",
                "secret_key": "sk",
                "region": "auto",
                "public_domain": None,
            },
            None,
        ),
    )
    live = await _create_session(db, teacher_id=1014, room_name="egress-room-14")
    await _create_detail(
        db,
        session_id=live.id,
        recording_status=RecordingStatus.RECORDING.value,
    )

    resp = await _post_webhook(db, _egress_event("egress-room-14"))
    assert resp.status_code == 204

    detail = await _detail_for(db, live.id)
    assert detail.recording_status == RecordingStatus.PROCESSING.value
    assert "S3_PUBLIC_DOMAIN" in (detail.recording_note or "")
    await db.refresh(live)
    assert live.recording_url is None


@pytest.mark.asyncio
async def test_ending_the_class_does_not_mark_recording_ready(db, monkeypatch, storage):
    """Stopping egress is not the same as the file landing in storage: the
    upload happens afterwards and can still fail. Only `egress_ended` knows."""
    live = await _create_session(db, teacher_id=1018, room_name="egress-room-18")
    await _create_detail(
        db, session_id=live.id, recording_status=RecordingStatus.RECORDING.value
    )

    async def fake_stop(egress_id):
        return None

    monkeypatch.setattr(lc_schedule, "stop_recording", fake_stop)

    detail = await lc_schedule.finish_recording(db, live=live)
    assert detail.recording_status == RecordingStatus.PROCESSING.value

    await db.refresh(live)
    assert live.recording_url is None


@pytest.mark.asyncio
async def test_egress_ended_for_class_that_never_opted_in_is_ignored(db, storage):
    """A stray egress must not be reported as a failed recording: that would
    tell a teacher their recording broke when they never turned it on."""
    live = await _create_session(db, teacher_id=1017, room_name="egress-room-17")
    await _create_detail(db, session_id=live.id, recording_enabled=False)

    resp = await _post_webhook(
        db,
        _egress_event("egress-room-17", status="EGRESS_FAILED", filename=None, error="boom"),
    )
    assert resp.status_code == 204

    detail = await _detail_for(db, live.id)
    assert detail.recording_status == RecordingStatus.PENDING.value
    assert detail.recording_note is None
    assert detail.egress_id is None


@pytest.mark.asyncio
async def test_recording_not_ready_without_successful_egress(db, monkeypatch, storage):
    """A class that was recorded and then ended, with no egress_ended ever
    arriving, must not read as ready."""
    live = await _create_session(db, teacher_id=1015, room_name="egress-room-15")
    await _create_detail(db, session_id=live.id)

    async def fake_start(room_name, session_id):
        return "EG_dispatched", "live-classes/2026/09/16/session-15.mp4"

    monkeypatch.setattr(lc_schedule, "start_recording", fake_start)

    await _post_webhook(db, {"event": "room_started", "room": {"name": "egress-room-15"}})
    await _post_webhook(db, {"event": "room_finished", "room": {"name": "egress-room-15"}})

    detail = await _detail_for(db, live.id)
    assert detail.recording_status != RecordingStatus.READY.value
    await db.refresh(live)
    assert live.recording_url is None


@pytest.mark.asyncio
async def test_egress_ended_for_session_without_detail_row_is_noop(db, storage):
    """An ad-hoc room that never opted in. Nothing to attach the recording to,
    and inventing a detail row would claim a recording nobody asked for."""
    await _create_session(db, teacher_id=1016, room_name="egress-room-16")

    resp = await _post_webhook(db, _egress_event("egress-room-16"))
    assert resp.status_code == 204
    rows = (await db.execute(select(LiveClassSessionDetail))).scalars().all()
    assert rows == []


# ---------------------------------------------------------------------------
# Recording -> LMS linkage
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recording_course_link_resolves_chapter_via_coursework(db, course, chapter, activity):
    """`sms_live_class_coursework` carries only an `activity_id` -- no chapter
    or course column. It does not need one: Learnhouse's own content model
    supplies the link (activity -> chapter_activity -> chapter -> course)."""
    live = await _create_session(db, teacher_id=1020, room_name="egress-room-20")
    db.add(
        LiveClassCoursework(
            session_id=live.id,
            activity_id=activity.id,
            attached_by_user_id=1020,
        )
    )
    await db.commit()

    link = await lc_schedule.recording_course_link(db, live=live)
    assert link.course_id == course.id
    assert link.chapter_id == chapter.id
    assert link.activity_id == activity.id


@pytest.mark.asyncio
async def test_recording_course_link_falls_back_to_session_course(db, course):
    live = await _create_session(
        db, teacher_id=1021, room_name="egress-room-21", course_id=course.id
    )

    link = await lc_schedule.recording_course_link(db, live=live)
    assert link.course_id == course.id
    assert link.chapter_id is None
    assert link.activity_id is None


@pytest.mark.asyncio
async def test_recording_course_link_is_empty_when_unresolvable(db):
    """Absence of a link is reported as no link, never as course 0."""
    live = await _create_session(db, teacher_id=1022, room_name="egress-room-22")

    link = await lc_schedule.recording_course_link(db, live=live)
    assert link.course_id is None
    assert link.chapter_id is None
    assert link.activity_id is None


# ---------------------------------------------------------------------------
# Payload parsing
# ---------------------------------------------------------------------------


def test_parse_egress_ended_converts_nanoseconds_and_size():
    from google.protobuf.json_format import Parse

    from livekit.protocol.egress import EgressInfo

    # Parsed from JSON exactly as WebhookReceiver does, so int64-as-string
    # (how LiveKit actually sends durations and sizes) is exercised too.
    info = Parse(
        json.dumps(
            {
                "egress_id": "EG_x",
                "status": "EGRESS_COMPLETE",
                "file_results": [
                    {"filename": "live-classes/a.mp4", "duration": "90000000000", "size": "2048"}
                ],
            }
        ),
        EgressInfo(),
    )
    result = live_class_recording.parse_egress_ended(info)
    assert result.succeeded is True
    assert result.duration_seconds == 90.0
    assert result.file_size_bytes == 2048
    assert result.object_key == "live-classes/a.mp4"


def test_parse_egress_ended_on_missing_info_is_a_stated_failure():
    result = live_class_recording.parse_egress_ended(None)
    assert result.succeeded is False
    assert result.error
