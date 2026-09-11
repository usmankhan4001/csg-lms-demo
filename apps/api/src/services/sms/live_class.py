import os
import time
from typing import Optional
import jwt


def get_livekit_config() -> dict:
    """Returns LiveKit server configuration from environment."""
    return {
        "api_key": os.getenv("LIVEKIT_API_KEY", "devkey"),
        "api_secret": os.getenv("LIVEKIT_API_SECRET", "secret"),
        "url": os.getenv("LIVEKIT_URL", "ws://localhost:7880"),
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
    """
    Generates a LiveKit-compatible WebRTC access JWT token.
    """
    config = get_livekit_config()
    api_key = config["api_key"]
    api_secret = config["api_secret"]

    now = int(time.time())

    publish_perm = is_teacher if can_publish is None else can_publish

    video_grants = {
        "room": room_name,
        "roomJoin": True,
        "canPublish": publish_perm,
        "canSubscribe": can_subscribe,
        "canPublishData": True,
    }

    if is_teacher:
        video_grants["roomAdmin"] = True
        video_grants["roomRecord"] = True

    claims = {
        "iss": api_key,
        "sub": str(participant_id),
        "name": participant_name,
        "iat": now,
        "nbf": now,
        "exp": now + ttl_seconds,
        "video": video_grants,
        "metadata": "",
    }

    token = jwt.encode(claims, api_secret, algorithm="HS256")
    if isinstance(token, bytes):
        token = token.decode("utf-8")
    return token
