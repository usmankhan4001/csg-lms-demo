"""Real class recording via LiveKit Egress.

Before this module, `LiveClassSession.recording_url` was only ever set if a
caller PASSED one to the end-session endpoint. There was no egress pipeline at
all, so the field advertised a capability the system did not have: a UI built
against it would render a "Recording" column that stayed empty forever.

Two rules this module exists to enforce:

1. **No object storage means recording is UNAVAILABLE, stated plainly.** It is
   never silently "on" while producing nothing, and it never invents a URL.
   `UNAVAILABLE` is deliberately a different state from `FAILED` -- telling a
   teacher their recording broke, when in truth nobody ever configured
   storage, sends them chasing the wrong problem.

2. **Recording is opt-in per class, and sharing is a second, separate opt-in.**
   These are rooms full of children. A default-on recording, or a recording
   that reaches students the moment it finishes, are both the wrong default to
   fail towards.
"""

import datetime
import logging
import os
from typing import Optional, Tuple

from livekit.api import (
    EncodedFileOutput,
    EncodedFileType,
    RoomCompositeEgressRequest,
    S3Upload,
    StopEgressRequest,
)

from config.config import get_learnhouse_config
from src.services.sms.live_class import get_livekit_api_client

logger = logging.getLogger(__name__)


class RecordingStorageUnavailable(RuntimeError):
    """Raised when recording is requested but no object storage is configured.

    Carries the human-readable reason so the API can hand it to the teacher
    rather than failing opaquely.
    """


def get_recording_storage() -> Tuple[Optional[dict], Optional[str]]:
    """Resolve S3 settings for egress.

    Returns `(config, None)` when usable, or `(None, reason)` when not. The
    reason is shown to the teacher, so it names the missing piece rather than
    saying "misconfigured".

    Credentials come from the environment rather than the YAML config because
    that is where this deployment already puts them -- `dokploy-compose.yml`
    defines S3_ACCESS_KEY_ID / S3_SECRET_ACCESS_KEY (both unset by default),
    and boto3 elsewhere in this codebase reads the standard AWS_* names.
    Either spelling works here.
    """
    cfg = get_learnhouse_config()
    s3 = cfg.hosting_config.content_delivery.s3api

    bucket = (s3.bucket_name or "").strip() if s3 else ""
    endpoint = (s3.endpoint_url or "").strip() if s3 else ""
    access_key = (
        os.environ.get("S3_ACCESS_KEY_ID") or os.environ.get("AWS_ACCESS_KEY_ID") or ""
    ).strip()
    secret_key = (
        os.environ.get("S3_SECRET_ACCESS_KEY") or os.environ.get("AWS_SECRET_ACCESS_KEY") or ""
    ).strip()

    missing = []
    if not bucket:
        missing.append("a storage bucket")
    if not access_key or not secret_key:
        missing.append("storage credentials")

    if missing:
        return None, (
            "Class recording is not available on this deployment: "
            + " and ".join(missing)
            + " have not been configured. Ask your administrator to set up "
            "object storage before enabling recording."
        )

    return (
        {
            "bucket": bucket,
            "endpoint": endpoint or None,
            "access_key": access_key,
            "secret_key": secret_key,
            "region": os.environ.get("LEARNHOUSE_S3_API_REGION") or "auto",
            "public_domain": (os.environ.get("S3_PUBLIC_DOMAIN") or "").strip() or None,
        },
        None,
    )


def recording_is_available() -> bool:
    storage, _ = get_recording_storage()
    return storage is not None


def build_object_key(room_name: str, session_id: int) -> str:
    """Storage path for a recording. Namespaced so one school's recordings are
    not interleaved with another's in a shared bucket."""
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y/%m/%d")
    return f"live-classes/{stamp}/session-{session_id}-{room_name}.mp4"


async def start_recording(room_name: str, session_id: int) -> Tuple[Optional[str], str]:
    """Begin a room-composite egress to object storage.

    Returns `(egress_id, object_key)`. Raises `RecordingStorageUnavailable`
    when storage is not configured -- the caller turns that into a stated
    reason on the class, never a silent no-op that looks like success.
    """
    storage, reason = get_recording_storage()
    if storage is None:
        raise RecordingStorageUnavailable(reason)

    object_key = build_object_key(room_name, session_id)
    client = get_livekit_api_client()
    try:
        request = RoomCompositeEgressRequest(
            room_name=room_name,
            layout="grid",
            file_outputs=[
                EncodedFileOutput(
                    file_type=EncodedFileType.MP4,
                    filepath=object_key,
                    s3=S3Upload(
                        access_key=storage["access_key"],
                        secret=storage["secret_key"],
                        bucket=storage["bucket"],
                        region=storage["region"],
                        endpoint=storage["endpoint"] or "",
                        force_path_style=True,
                    ),
                )
            ],
        )
        info = await client.egress.start_room_composite_egress(request)
        return (getattr(info, "egress_id", None), object_key)
    finally:
        await client.aclose()


async def stop_recording(egress_id: str) -> None:
    """Stop an in-progress egress.

    Best-effort and never raises: a class must be able to end even if the
    media server is unreachable. LiveKit also stops egress on its own when the
    room closes, so the recording is not lost by a failure here.
    """
    client = get_livekit_api_client()
    try:
        await client.egress.stop_egress(StopEgressRequest(egress_id=egress_id))
    except Exception:
        logger.warning(
            "LiveKit stop_egress failed for egress_id=%s; the room closing should "
            "end it server-side",
            egress_id,
            exc_info=True,
        )
    finally:
        await client.aclose()


def public_url_for(object_key: str) -> Optional[str]:
    """Resolve a viewable URL for a finished recording.

    Returns None when no public domain is configured rather than guessing a
    URL shape -- a link that 404s is worse than an honest "not yet available",
    and this codebase has had to remove fabricated URLs before.
    """
    storage, _ = get_recording_storage()
    if storage is None or not storage.get("public_domain"):
        return None
    domain = storage["public_domain"].rstrip("/")
    if not domain.startswith("http"):
        domain = f"https://{domain}"
    return f"{domain}/{object_key.lstrip('/')}"
