"""
CSG-LMS School Invite Records
=============================
Durable state for "who has been invited, and who is actually in yet".

WHY THIS EXISTS: `services/sms/people_provisioning.py` creates accounts with a
deliberately unusable password -- an Argon2 hash of a `secrets.token_urlsafe(64)`
that is discarded immediately -- so that no cohort of fifty students can ever
share a default password. That decision is right and stays. But nothing told
the person their account existed, so an administrator could import fifty
families and not one of them could sign in, or even know to try. The bulk
importer's careful per-row failure reporting was reporting on accounts nobody
could reach.

WHAT THIS TABLE IS FOR, AND WHAT IT DELIBERATELY IS NOT:

  * It records STATE -- invited, delivered, accepted, failed, expired -- so an
    administrator can see on the day who has not yet joined and chase them.
  * It holds NO SECRET. The invite token lives only in Redis, exactly like the
    password-reset code in `services/users/password_reset.py`. If this table
    leaked, no invite in it could be redeemed. `token_ref` is an opaque,
    non-secret handle used to invalidate a superseded token on resend; knowing
    it grants nothing.

Identifying columns are plain integers rather than foreign keys, and email and
role are SNAPSHOTTED, matching `SMSPersonProvisioningEvent` in
`db/sms_identity.py` and the four audit trails it copies. `SMSUserRole.user_id`
is `ondelete="CASCADE"`, so an FK-linked record would be destroyed by deleting
the user -- and "we invited this address and it bounced" is exactly the kind of
fact an investigation needs after an account is gone.

Purely additive (no ALTER on any existing table), like every other `sms_*`
model here: picked up by `SQLModel.metadata.create_all` at startup via the
router import chain, never through Alembic.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlalchemy import Column, DateTime, Index, Integer, String
from sqlmodel import Field, SQLModel


def get_utc_now() -> datetime:
    return datetime.now(timezone.utc)


class InviteStatus(str, Enum):
    """What genuinely happened to this invite.

    `PENDING` and `DELIVERY_FAILED` are deliberately different states. An
    account created whose invite bounced is NOT a success -- it looks identical
    to a success in every other system, and the family never arrives. The
    importer must be able to say which rows those were.

    `UNKNOWN` exists because the honest answer is sometimes "we do not know":
    the provider neither confirmed nor refused. Recording that as `SENT` would
    be a fabricated delivery status, and this repository has had nine
    fabrication defects torn out of it already.
    """

    PENDING = "PENDING"          # issued and handed to the provider, accepted
    DELIVERY_FAILED = "DELIVERY_FAILED"  # the provider refused it
    UNKNOWN = "UNKNOWN"          # dispatch outcome genuinely undetermined
    ACCEPTED = "ACCEPTED"        # the person set their password and is in
    REVOKED = "REVOKED"          # superseded by a resend, or withdrawn


# Statuses from which a resend makes sense. ACCEPTED is absent on purpose:
# re-inviting someone who is already in would hand out a fresh
# password-setting token for a live account.
RESENDABLE = frozenset(
    {InviteStatus.PENDING, InviteStatus.DELIVERY_FAILED, InviteStatus.UNKNOWN}
)


class SMSPersonInvite(SQLModel, table=True):
    """One invitation to one person for one organization."""

    __tablename__ = "sms_person_invite"
    __table_args__ = (
        # NOTE: the indexed columns below must NOT also carry `index=True`.
        # Declaring both makes `create_all` emit CREATE INDEX twice and the API
        # fails to boot -- this has happened in this codebase before.
        Index("ix_sms_invite_org_status", "org_id", "status"),
        Index("ix_sms_invite_subject", "subject_user_id"),
        {"extend_existing": True},
    )

    id: Optional[int] = Field(default=None, primary_key=True)

    # Plain Integer, not an FK -- see module docstring.
    subject_user_id: int = Field(sa_column=Column(Integer, nullable=False))
    # Snapshot, so the record stays legible after the user row is gone.
    subject_email: str = Field(sa_column=Column(String(255), nullable=False))
    subject_role: str = Field(sa_column=Column(String(32), nullable=False))

    org_id: int = Field(sa_column=Column(Integer, nullable=False))

    status: str = Field(
        default=InviteStatus.PENDING.value,
        sa_column=Column(String(32), nullable=False),
    )

    # Opaque, NON-SECRET handle for the Redis token currently outstanding.
    # Used only to revoke a superseded token on resend. Knowing it grants
    # nothing -- the secret never leaves Redis.
    token_ref: Optional[str] = Field(
        default=None, sa_column=Column(String(64), nullable=True)
    )

    # Why a dispatch failed, in the provider's own words where we have them.
    # An administrator chasing a family needs "mailbox full", not "failed".
    delivery_error: Optional[str] = Field(
        default=None, sa_column=Column(String(500), nullable=True)
    )

    sent_count: int = Field(default=1, sa_column=Column(Integer, nullable=False))

    created_at: datetime = Field(
        default_factory=get_utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    last_sent_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    expires_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    accepted_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )

    # Who sent it. Nullable because a system-initiated invite has no human
    # actor, and recording 0 or a guessed id would be a fabrication.
    invited_by_user_id: Optional[int] = Field(
        default=None, sa_column=Column(Integer, nullable=True)
    )
