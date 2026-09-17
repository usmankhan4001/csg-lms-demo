"""One configured S3 client for every S3-compatible backend.

Before this module there were four hand-rolled `boto3.client("s3", ...)` calls
and they had already drifted: `courses/transfer/storage_utils.py` set
`region_name` and `signature_version="s3v4"` (needed, or Cloudflare R2 rejects
presigned URLs with 401), while `utils/upload_content.py` and
`routers/code_execution.py` set neither. Uploads and downloads of the same
object were therefore configured differently.

None of them passed credentials, so boto3 fell back to its ambient chain --
which reads only `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`. Every compose
file in this repo sets `S3_ACCESS_KEY_ID`/`S3_SECRET_ACCESS_KEY` instead, so a
deployment following its own documentation supplied no credentials at all.

Supported backends:

* **AWS S3** -- virtual-hosted addressing, a real region.
* **Cloudflare R2** -- virtual-hosted addressing, region ``auto``, and SigV4 is
  mandatory.
* **MinIO** (self-hosted) -- generally requires **path-style** addressing.
  botocore's ``auto`` resolves to virtual-hosted for a custom endpoint, which
  points at ``bucket.my-host`` -- a name that does not resolve for a MinIO
  container on a bare hostname or an IP. The failure surfaces as a connection
  error rather than anything mentioning addressing, so set
  ``S3_ADDRESSING_STYLE=path`` for MinIO. The bundled MinIO compose override
  sets it for you.
"""

from __future__ import annotations

from typing import Any, Optional

import boto3
import botocore.config

from config.config import get_learnhouse_config


def get_s3_settings():
    """The resolved s3api config block (bucket, endpoint, credentials, region)."""
    return get_learnhouse_config().hosting_config.content_delivery.s3api


def get_s3_bucket_name(default: str = "learnhouse-media") -> str:
    """Bucket name, falling back to the historic default used across callers."""
    s3 = get_s3_settings()
    return (getattr(s3, "bucket_name", None) or default) if s3 else default


def build_s3_client(
    *,
    connect_timeout: int = 10,
    read_timeout: int = 60,
    max_attempts: int = 2,
) -> Any:
    """A boto3 S3 client configured for whichever backend is in use.

    Credentials are passed explicitly when configured. When they are absent the
    arguments are omitted entirely rather than passed as ``None``, so boto3's
    normal chain (instance role, shared credentials file, AWS_* environment)
    still works for deployments that rely on it.
    """
    s3 = get_s3_settings()
    if not s3:
        return None

    endpoint_url = (getattr(s3, "endpoint_url", None) or "").strip() or None
    access_key_id = (getattr(s3, "access_key_id", None) or "").strip() or None
    secret_access_key = (getattr(s3, "secret_access_key", None) or "").strip() or None
    # R2 requires the "auto" region; without a region botocore falls back to
    # SigV2 for presigned URLs, which R2 rejects with 401. AWS and MinIO
    # validate the region against the endpoint, so it stays overridable.
    region = (getattr(s3, "region", None) or "").strip() or "auto"
    addressing_style = (getattr(s3, "addressing_style", None) or "").strip() or "auto"

    if endpoint_url and ("<" in endpoint_url or ">" in endpoint_url or "account-id" in endpoint_url):
        logger.warning("Ignoring placeholder S3 endpoint URL: %s", endpoint_url)
        endpoint_url = None

    if not endpoint_url and not access_key_id:
        return None

    client_config = botocore.config.Config(
        signature_version="s3v4",
        s3={"addressing_style": addressing_style},
        connect_timeout=connect_timeout,
        read_timeout=read_timeout,
        retries={"max_attempts": max_attempts},
    )

    kwargs: dict[str, Any] = {"config": client_config, "region_name": region}
    if endpoint_url:
        kwargs["endpoint_url"] = endpoint_url
    if access_key_id and secret_access_key:
        kwargs["aws_access_key_id"] = access_key_id
        kwargs["aws_secret_access_key"] = secret_access_key

    try:
        return boto3.client("s3", **kwargs)
    except Exception as e:
        logger.warning("Failed to initialize boto3 S3 client: %s", e)
        return None


def get_public_object_url(key: str) -> Optional[str]:
    """Public URL for an object, or None when no public domain is configured.

    Returns None rather than guessing a URL: a link that 404s is worse than an
    absent one, because the caller cannot tell the difference.
    """
    s3 = get_s3_settings()
    domain = (getattr(s3, "public_domain", None) or "").strip() if s3 else ""
    if not domain:
        return None
    return f"{domain.rstrip('/')}/{key.lstrip('/')}"
