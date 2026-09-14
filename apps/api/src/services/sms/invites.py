"""
School invites: making a provisioned account reachable by its owner.
====================================================================

THE GAP THIS CLOSES. `people_provisioning.py` creates an account whose password
is an Argon2 hash of a `secrets.token_urlsafe(64)` that is thrown away -- so
nobody can sign in, by construction, which is exactly right: a shared default
password across a cohort of fifty students is a school-wide compromise. What
was missing is the other half. Nothing told the person the account existed. An
administrator could import fifty families and every one of them was stranded.

DESIGN: AN INVITE IS A LONG-LIVED, SINGLE-USE PASSWORD-SETTING TOKEN.

This deliberately does NOT invent a second way to set a password. A second path
is a second thing to get wrong, and the one already here --
`services/users/password_reset.py` -- is mature: cryptographically secure codes,
Redis-backed with a TTL, strict alphanumeric validation against Redis key
injection, one-time use enforced by deleting the key, generic errors that refuse
to confirm whether an account exists, and rate limiting by both email and IP.
So this module reuses that shape exactly, changing only what must change:

  * a much longer TTL -- a reset is something you asked for a minute ago, an
    invite has to survive a weekend and a school holiday;
  * a distinct Redis key prefix, so an invite token can never be redeemed
    through the reset endpoint or vice versa;
  * a durable record in Postgres (`db/sms_invite.py`) of who was invited and
    whether they are in yet, which a reset code has no need of.

THE SECRET NEVER TOUCHES POSTGRES. The token exists only in Redis. The invite
row holds `token_ref`, an opaque non-secret handle used solely to revoke a
superseded token when an administrator resends. A dump of the invite table
grants an attacker nothing.

WHY A POINTER KEY. Resending must invalidate the previous token -- otherwise an
old email forwarded to the wrong person still works. Finding the previous key
would need a Redis scan over a wildcard, which `password_reset.py` deliberately
avoided for performance. Instead a second, deterministic pointer key holds the
outstanding token for a user+org, so revocation is two O(1) operations.

DISPATCH IS POST-COMMIT, ALWAYS. `provision_person()` stages without committing
so the caller can commit once and a failure rolls the whole person back. Email
must therefore be sent only after that commit lands -- you do not tell somebody
their account exists until it durably does. `notify()` in
`services/notifications/service.py` commits internally, so it is unusable inside
that transaction; transactional mail the recipient is actively waiting on also
goes direct in this codebase by convention (see the docstring on
`_send_notification_email` in `services/users/emails.py`).
"""

from __future__ import annotations

import json
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

import redis
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from config.config import get_learnhouse_config
from src.db.organizations import Organization
from src.db.sms_invite import RESENDABLE, InviteStatus, SMSPersonInvite
from src.db.users import User
from src.services.users.password_reset import generate_secure_reset_code

logger = logging.getLogger(__name__)


# Seven days. An invite has to survive a weekend, a half-term, or an
# administrator who imports the cohort on Friday afternoon. The reset code's
# one hour would strand most of a real intake.
INVITE_TTL_SECONDS = 7 * 24 * 60 * 60

# Longer than a reset code's 8 characters: this one sits in an inbox for a week
# rather than a minute, so it is worth the extra entropy against an attacker
# who has that long to guess.
INVITE_CODE_LENGTH = 24


def _redis():
    """Redis connection, or None when unavailable.

    Returns None rather than raising: an invite that cannot be issued must
    degrade to a reported failure on that row, not a 500 that discards the
    other forty-nine accounts the importer just created.
    """
    try:
        conn_string = get_learnhouse_config().redis_config.redis_connection_string
        if not conn_string:
            logger.error("No Redis connection string -- invites cannot be issued")
            return None
        # Short, explicit timeouts. Without them a degraded Redis does not fail
        # -- it HANGS, and an administrator importing fifty students waits on
        # fifty successive connection timeouts with no indication why. Failing
        # in two seconds and recording an honest DELIVERY_FAILED is far better
        # than an import that appears to have frozen.
        return redis.Redis.from_url(
            conn_string, socket_connect_timeout=2, socket_timeout=2
        )
    except Exception:
        logger.exception("Could not connect to Redis -- invites cannot be issued")
        return None


def _token_key(user_uuid: str, org_uuid: str, code: str) -> str:
    return f"sms_invite:user:{user_uuid}:org:{org_uuid}:code:{code}"


def _pointer_key(user_uuid: str, org_uuid: str) -> str:
    """Holds the code currently outstanding, so a resend can revoke it in O(1)."""
    return f"sms_invite_current:user:{user_uuid}:org:{org_uuid}"


def _revoke_outstanding(r, user_uuid: str, org_uuid: str) -> None:
    """Invalidate any token still outstanding for this user and org.

    Without this, an invite forwarded to the wrong address stays redeemable
    after the administrator has resent a fresh one.
    """
    try:
        pointer = _pointer_key(user_uuid, org_uuid)
        previous = r.get(pointer)
        if previous:
            code = previous.decode() if isinstance(previous, bytes) else str(previous)
            r.delete(_token_key(user_uuid, org_uuid, code))
        r.delete(pointer)
    except Exception:
        # A failure to revoke must not stop a fresh invite going out; the old
        # token still expires on its own TTL.
        logger.exception("Could not revoke outstanding invite for user %s", user_uuid)


def issue_invite_token(user: User, org: Organization) -> Optional[Tuple[str, str, datetime]]:
    """Mint a single-use password-setting token. Returns (code, token_ref, expires_at).

    Returns None when Redis is unavailable, so the caller records an honest
    failure instead of reporting an invite that was never issued.
    """
    r = _redis()
    if r is None:
        return None

    _revoke_outstanding(r, user.user_uuid, org.org_uuid)

    code = generate_secure_reset_code(length=INVITE_CODE_LENGTH)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=INVITE_TTL_SECONDS)

    payload = {
        "kind": "sms_invite",
        "user_uuid": user.user_uuid,
        "org_uuid": org.org_uuid,
        "expires": int(expires_at.timestamp()),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        r.set(
            _token_key(user.user_uuid, org.org_uuid, code),
            json.dumps(payload),
            ex=INVITE_TTL_SECONDS,
        )
        r.set(_pointer_key(user.user_uuid, org.org_uuid), code, ex=INVITE_TTL_SECONDS)
    except Exception:
        logger.exception("Could not store invite token for user %s", user.user_uuid)
        return None

    # A non-secret handle. Deriving the code from this is not possible; it
    # exists only so a later resend knows there was something to revoke.
    token_ref = secrets.token_hex(8)
    return code, token_ref, expires_at


def verify_invite_token(user: User, org: Organization, code: str) -> bool:
    """True only for a token that is outstanding and unexpired.

    Fails closed on every uncertainty, including Redis being unreachable: an
    invite acceptance that cannot be verified must not proceed.
    """
    # Same defence as `change_password_with_reset_code`: a code that is not
    # strictly alphanumeric could otherwise shape the Redis key it is
    # interpolated into.
    if not code or not code.isalnum():
        return False

    r = _redis()
    if r is None:
        return False

    try:
        raw = r.get(_token_key(user.user_uuid, org.org_uuid, code))
    except Exception:
        logger.exception("Could not read invite token for user %s", user.user_uuid)
        return False

    if raw is None:
        return False

    try:
        payload = json.loads(raw)
    except Exception:
        logger.exception("Malformed invite token payload for user %s", user.user_uuid)
        return False

    if payload.get("kind") != "sms_invite":
        # A reset code must never be redeemable as an invite.
        return False

    expires = payload.get("expires")
    if not isinstance(expires, int) or expires < int(datetime.now(timezone.utc).timestamp()):
        consume_invite_token(user, org, code)
        return False

    return True


def consume_invite_token(user: User, org: Organization, code: str) -> None:
    """Burn the token. Single-use is enforced here, as it is for reset codes."""
    r = _redis()
    if r is None:
        return
    try:
        r.delete(_token_key(user.user_uuid, org.org_uuid, code))
        pointer = r.get(_pointer_key(user.user_uuid, org.org_uuid))
        current = pointer.decode() if isinstance(pointer, bytes) else pointer
        if current == code:
            r.delete(_pointer_key(user.user_uuid, org.org_uuid))
    except Exception:
        logger.exception("Could not consume invite token for user %s", user.user_uuid)


async def get_open_invite(
    session: AsyncSession, user_id: int, org_id: int
) -> Optional[SMSPersonInvite]:
    """The most recent invite for this person that has not been accepted."""
    rows = await session.execute(
        select(SMSPersonInvite)
        .where(
            SMSPersonInvite.subject_user_id == user_id,
            SMSPersonInvite.org_id == org_id,
        )
        .order_by(SMSPersonInvite.id.desc())
    )
    for invite in rows.scalars().all():
        if invite.status != InviteStatus.ACCEPTED.value:
            return invite
        # Already in: nothing is open.
        return None
    return None


async def list_invites(
    session: AsyncSession,
    org_id: int,
    *,
    status: Optional[str] = None,
    limit: int = 200,
) -> List[SMSPersonInvite]:
    statement = select(SMSPersonInvite).where(SMSPersonInvite.org_id == org_id)
    if status:
        statement = statement.where(SMSPersonInvite.status == status)
    statement = statement.order_by(SMSPersonInvite.id.desc()).limit(limit)
    rows = await session.execute(statement)
    return list(rows.scalars().all())


async def accept_invite(
    session: AsyncSession,
    *,
    org_id: int,
    email: str,
    code: str,
    new_password: str,
) -> None:
    """Redeem an invite: set the chosen password and burn the token.

    Mirrors `change_password_with_reset_code` deliberately, down to the generic
    error text. Differences from that function would be differences in security
    posture, and there is no reason for this path to be weaker:

      * password complexity is validated BEFORE any lookup, so a weak password
        is refused without revealing whether the account or code exists;
      * every failure returns the same message, so this cannot be used to
        enumerate which addresses have accounts or which codes are live;
      * the token is deleted on success, making it single-use;
      * the password is hashed with the same `security_hash_password` the rest
        of the platform uses -- there is no second hashing path here.
    """
    from fastapi import HTTPException, status as http_status

    from src.security.security import security_hash_password
    from src.services.security.password_validation import validate_password_complexity

    generic = HTTPException(
        status_code=http_status.HTTP_400_BAD_REQUEST,
        detail="Invalid or expired invitation.",
    )

    validation = validate_password_complexity(new_password)
    if not validation.is_valid:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "WEAK_PASSWORD",
                "message": "Password does not meet security requirements",
                "errors": validation.errors,
                "requirements": validation.requirements,
            },
        )

    org = (
        await session.execute(select(Organization).where(Organization.id == org_id))
    ).scalars().first()
    if not org:
        raise generic

    normalized = (email or "").strip().lower()
    user = (
        await session.execute(select(User).where(User.email == normalized))
    ).scalars().first()
    if not user:
        logger.warning("Invite acceptance for unknown email %s***", normalized[:3])
        raise generic

    if not verify_invite_token(user, org, code):
        logger.warning("Invalid or expired invite token for user %s", user.user_uuid)
        raise generic

    invite = await get_open_invite(session, user.id, org.id)
    if invite is None or invite.status == InviteStatus.ACCEPTED.value:
        # The token verified but there is no open record, or it is already
        # redeemed. Fail closed rather than setting a password off the back of
        # a state we cannot explain.
        logger.warning("No open invite record for user %s", user.user_uuid)
        consume_invite_token(user, org, code)
        raise generic

    user.password = security_hash_password(new_password)
    user.password_changed_at = datetime.now(timezone.utc).replace(tzinfo=None)
    # The address is now proven: only its owner could have followed the link.
    if hasattr(user, "email_verified"):
        user.email_verified = True
    session.add(user)

    invite.status = InviteStatus.ACCEPTED.value
    invite.accepted_at = datetime.now(timezone.utc)
    invite.delivery_error = None
    session.add(invite)

    await session.commit()

    # Burn the token only after the password is durably committed. Burning
    # first would strand the person if the commit then failed.
    consume_invite_token(user, org, code)
    logger.info("Invite accepted for user %s", user.user_uuid)


async def dispatch_invite(
    session: AsyncSession,
    *,
    user: User,
    org: Organization,
    role: str,
    request,
    actor_user_id: Optional[int] = None,
    existing: Optional[SMSPersonInvite] = None,
) -> SMSPersonInvite:
    """Issue a token, send the email, and record honestly what happened.

    NEVER RAISES. Called after the provisioning transaction has committed, so
    the account already exists; a mail failure at this point must be recorded
    against that account, not turned into an error that makes an administrator
    think the import failed when forty-nine of fifty rows are fine.

    Commits its own row. Safe because the caller has already committed the
    person -- see the module docstring on post-commit dispatch.
    """
    invite = existing or SMSPersonInvite(
        subject_user_id=user.id,
        subject_email=user.email,
        subject_role=getattr(role, "value", str(role)),
        org_id=org.id,
        invited_by_user_id=actor_user_id,
        sent_count=0,
    )

    issued = issue_invite_token(user, org)
    if issued is None:
        invite.status = InviteStatus.DELIVERY_FAILED.value
        invite.delivery_error = (
            "Could not issue an invite token (the token store was unreachable)."
        )
        invite.sent_count = (invite.sent_count or 0) + 1
        invite.last_sent_at = datetime.now(timezone.utc)
        session.add(invite)
        await session.commit()
        await session.refresh(invite)
        return invite

    code, token_ref, expires_at = issued

    try:
        from src.db.organization_config import OrganizationConfig
        from src.services.email.branding import resolve_org_email_branding
        from src.services.email.utils import get_org_signup_base_url
        from src.services.sms.invite_emails import (
            build_invite_url,
            send_school_invite_email,
        )

        org_config = (
            await session.execute(
                select(OrganizationConfig).where(OrganizationConfig.org_id == org.id)
            )
        ).scalars().first()

        base_url = await get_org_signup_base_url(
            org.slug, request, db_session=session, org_id=org.id
        )

        sent = send_school_invite_email(
            email=user.email,
            first_name=getattr(user, "first_name", "") or "",
            org_name=org.name,
            role_label=getattr(role, "value", str(role)).replace("_", " ").title(),
            invite_url=build_invite_url(base_url, org.id, user.email, code),
            expires_in_days=INVITE_TTL_SECONDS // 86400,
            **resolve_org_email_branding(org, org_config, request).as_kwargs(),
        )
        status_enum, error = classify_dispatch(sent)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Invite email to %s failed", user.email)
        status_enum, error = InviteStatus.DELIVERY_FAILED, f"{type(exc).__name__}: {exc}"

    invite.status = status_enum.value
    invite.delivery_error = (error or "")[:500] or None
    invite.token_ref = token_ref
    invite.expires_at = expires_at
    invite.last_sent_at = datetime.now(timezone.utc)
    invite.sent_count = (invite.sent_count or 0) + 1

    session.add(invite)
    await session.commit()
    await session.refresh(invite)
    return invite


def classify_dispatch(sent) -> Tuple[InviteStatus, Optional[str]]:
    """Turn what the mail layer returned into an honest status.

    `send_email` returns a truthy provider response on success, returns None
    when it deliberately drops the address (a reserved `.invalid` demo domain),
    and raises when the provider refuses. None is NOT success and must never be
    recorded as sent -- the family in question would be chased by nobody.
    """
    if sent is None:
        return (
            InviteStatus.UNKNOWN,
            "Address was not deliverable and the message was dropped before sending.",
        )
    if not sent:
        return InviteStatus.DELIVERY_FAILED, "The email provider did not accept the message."
    return InviteStatus.PENDING, None
