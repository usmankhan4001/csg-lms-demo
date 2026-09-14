import logging
import os
from typing import Optional

from livekit.api import (
    AccessToken,
    CreateRoomRequest,
    DeleteRoomRequest,
    LiveKitAPI,
    TokenVerifier,
    VideoGrants,
    WebhookReceiver,
)
from livekit.api.webhook import WebhookEvent

logger = logging.getLogger(__name__)


def get_livekit_config() -> dict:
    """Returns LiveKit server configuration from environment.

    `url` is the BROWSER-facing ws(s):// address (handed to the frontend so
    it can open a WebRTC signaling connection) -- this is deliberately
    separate from `internal_url` below, the same
    browser-facing/container-internal split already established for the API
    itself (`NEXT_PUBLIC_LEARNHOUSE_BACKEND_URL` vs `LEARNHOUSE_INTERNAL_API_URL`
    in docker-compose.local.yml): inside the `api` container, "localhost"
    means the api container itself, not the `livekit` service container.
    """
    return {
        "api_key": os.getenv("LIVEKIT_API_KEY", "devkey"),
        "api_secret": os.getenv("LIVEKIT_API_SECRET", "secret"),
        "url": os.getenv("LIVEKIT_URL", "ws://localhost:7880"),
        "internal_url": os.getenv("LIVEKIT_INTERNAL_URL", os.getenv("LIVEKIT_URL", "ws://localhost:7880")),
    }


def generate_livekit_token(
    room_name: str,
    participant_id: str,
    participant_name: str,
    is_teacher: bool = False,
    can_publish: Optional[bool] = None,
    can_subscribe: bool = True,
    ttl_seconds: int = 21600,
) -> str:
    """Generates a real LiveKit WebRTC access token via the official SDK's
    `AccessToken`/`VideoGrants` -- same signed-JWT format as the previous
    hand-rolled PyJWT implementation (confirmed identical claim shape), now
    using the canonical library instead of reimplementing LiveKit's token
    spec by hand."""
    import datetime

    config = get_livekit_config()
    publish_perm = is_teacher if can_publish is None else can_publish

    grants = VideoGrants(
        room=room_name,
        room_join=True,
        can_publish=publish_perm,
        can_subscribe=can_subscribe,
        can_publish_data=True,
        room_admin=True if is_teacher else None,
        room_record=True if is_teacher else None,
    )

    token = (
        AccessToken(config["api_key"], config["api_secret"])
        .with_identity(str(participant_id))
        .with_name(participant_name)
        .with_grants(grants)
        .with_ttl(datetime.timedelta(seconds=ttl_seconds))
        .to_jwt()
    )
    return token


def _as_http_url(livekit_url: str) -> str:
    """The LiveKit server's room/egress/etc. management API is plain HTTP(S)
    Twirp over the same port participants connect to over WebSocket --
    `LIVEKIT_URL` is conventionally ws(s):// (what browser clients need), so
    translate the scheme for the server-to-server `LiveKitAPI` client."""
    if livekit_url.startswith("wss://"):
        return "https://" + livekit_url[len("wss://") :]
    if livekit_url.startswith("ws://"):
        return "http://" + livekit_url[len("ws://") :]
    return livekit_url


def get_livekit_api_client() -> LiveKitAPI:
    config = get_livekit_config()
    return LiveKitAPI(_as_http_url(config["internal_url"]), config["api_key"], config["api_secret"])


async def create_room_on_server(room_name: str, *, empty_timeout_seconds: int = 300) -> None:
    """Best-effort: explicitly creates the room on the real LiveKit media
    server ahead of anyone joining (mainly so `empty_timeout` is configured
    from creation). Deliberately never raises -- local/test environments
    routinely run without a live LiveKit server reachable, and LiveKit rooms
    auto-create on first participant join by default anyway, so a failure
    here must not block the DB-level session record this backs."""
    client = get_livekit_api_client()
    try:
        await client.room.create_room(CreateRoomRequest(name=room_name, empty_timeout=empty_timeout_seconds))
    except Exception:
        logger.warning("LiveKit create_room failed for room=%s (server unreachable?)", room_name, exc_info=True)
    finally:
        await client.aclose()


async def end_room_on_server(room_name: str) -> None:
    """Best-effort: forcibly disconnects any remaining participants and
    closes the real LiveKit room when a teacher ends the session from the
    app, rather than waiting for LiveKit's own empty-room timeout. Never
    raises, matching `create_room_on_server`."""
    client = get_livekit_api_client()
    try:
        await client.room.delete_room(DeleteRoomRequest(room=room_name))
    except Exception:
        logger.warning("LiveKit delete_room failed for room=%s (server unreachable or already closed)", room_name, exc_info=True)
    finally:
        await client.aclose()


def verify_and_parse_webhook(body: str, auth_header: str) -> WebhookEvent:
    """Verifies a LiveKit webhook POST's signature and returns the decoded
    event. Raises `jwt`/`InvalidTokenError`-family exceptions on a bad or
    missing signature -- the caller (the webhook router) turns that into a
    401, never trusting an unverified event."""
    config = get_livekit_config()
    receiver = WebhookReceiver(TokenVerifier(config["api_key"], config["api_secret"]))
    return receiver.receive(body, auth_header)
