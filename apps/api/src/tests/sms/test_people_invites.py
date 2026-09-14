"""
Tests for school invitations.

Provisioning deliberately creates accounts with no usable password, so an
invitation is the ONLY way the owner of a provisioned account can ever sign in.
That makes these paths load-bearing, and each risk below has a test here:

* a password leaking into a response, a log, or the email body,
* a token that survives being used, so a forwarded email keeps working,
* an expired or revoked token still being accepted,
* a bulk import reporting "created" for a row whose invite bounced, leaving a
  family stranded and nobody knowing which one,
* invite acceptance becoming an oracle for which addresses have accounts,
* a resend handing out a fresh password-setting token for a LIVE account.
"""

import pytest
from fastapi import HTTPException
from sqlmodel import select

from src.db.sms_identity import SchoolRole
from src.db.sms_invite import RESENDABLE, InviteStatus, SMSPersonInvite
from src.db.users import User
from src.routers.sms_identity import (
    AcceptInviteRequest,
    BulkProvisionRequest,
    ProvisionPersonRequest,
    accept_school_invite,
    bulk_provision_school_people,
    list_school_invites,
    provision_school_person,
    resend_school_invite,
)
from src.security.security import security_verify_password
from src.tests.sms._principals import SUPERADMIN, TEACHER, principal


def _admin(org_id: int, user_id: int = 910):
    # campus_id=None deliberately: these tests are about the invitation
    # lifecycle, not campus placement, and the helper otherwise defaults to a
    # campus id that does not exist in this fixture.
    return principal("SCHOOL_ADMIN", user_id=user_id, org_id=org_id, campus_id=None)


class _FakeRedis:
    """An in-memory stand-in with the handful of operations invites use.

    Real Redis is not assumed present in the test environment, and the point of
    these tests is the token LIFECYCLE -- issued once, redeemable once, gone
    afterwards -- which is identical either way.
    """

    def __init__(self):
        self.store: dict = {}

    def get(self, key):
        value = self.store.get(key)
        return value.encode() if isinstance(value, str) else value

    def set(self, key, value, ex=None):
        self.store[key] = value

    def delete(self, *keys):
        for key in keys:
            self.store.pop(key, None)


@pytest.fixture
def fake_redis(monkeypatch):
    import src.routers.sms_identity as router_mod
    import src.services.security.rate_limiting as rl
    import src.services.sms.invites as invites_mod

    r = _FakeRedis()
    monkeypatch.setattr(invites_mod, "_redis", lambda: r)
    # The acceptance endpoint's rate limiter talks to REAL Redis, which is not
    # running here. Its behaviour has its own coverage in the password-reset
    # tests; these tests are about the invitation lifecycle.
    monkeypatch.setattr(rl, "check_password_reset_rate_limit", lambda email: (True, 0))
    return r


@pytest.fixture
def sent_emails(monkeypatch):
    """Capture invite mail instead of sending it, and report success."""
    import src.services.sms.invites as invites_mod

    captured: list = []

    def _fake_send(**kwargs):
        captured.append(kwargs)
        return {"id": "msg_test"}

    # Patched at the point of use, because `dispatch_invite` imports it inside
    # the function body.
    import src.services.sms.invite_emails as emails_mod

    monkeypatch.setattr(emails_mod, "send_school_invite_email", _fake_send)
    monkeypatch.setattr(invites_mod, "INVITE_TTL_SECONDS", 7 * 24 * 3600)
    return captured


async def _provision(db, org, email="hira.malik@example.com", send_invite=True):
    return await provision_school_person(
        payload=ProvisionPersonRequest(
            role=SchoolRole.TEACHER,
            email=email,
            first_name="Hira",
            last_name="Malik",
            send_invite=send_invite,
        ),
        db_session=db,
        principal=_admin(org.id),
    )


# ---------------------------------------------------------------------------
# No password, ever
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_invite_email_never_contains_a_password(db, org, fake_redis, sent_emails):
    resp = await _provision(db, org)

    assert resp.invite_status == InviteStatus.PENDING.value
    assert len(sent_emails) == 1

    rendered = " ".join(str(v) for v in sent_emails[0].values()).lower()
    for forbidden in ("password is", "temporary password", "changeme", "your password:"):
        assert forbidden not in rendered

    # And the account still has no usable password until acceptance.
    user = await db.get(User, resp.user_id)
    for guess in ("", "changeme", "Password123!", "hira.malik@example.com", "Hira"):
        assert not security_verify_password(guess, user.password)


@pytest.mark.asyncio
async def test_response_carries_no_password_field(db, org, fake_redis, sent_emails):
    resp = await _provision(db, org)
    blob = resp.model_dump()
    assert not any("password" in key.lower() for key in blob)


# ---------------------------------------------------------------------------
# Single use, and expiry
# ---------------------------------------------------------------------------

def _issued_code(fake_redis, user_uuid: str | None = None):
    """The outstanding code, read out of the fake token store.

    Scoped by user when given: more than one invite can be outstanding at once,
    and picking whichever happened to be first would test the wrong token.
    """
    for key in fake_redis.store:
        if not key.startswith("sms_invite:") or ":code:" not in key:
            continue
        if user_uuid and f"user:{user_uuid}:" not in key:
            continue
        return key.rsplit(":code:", 1)[1]
    raise AssertionError("no invite token was issued")


@pytest.mark.asyncio
async def test_invite_token_works_exactly_once(db, org, fake_redis, sent_emails):
    resp = await _provision(db, org)
    code = _issued_code(fake_redis)

    await accept_school_invite(
        payload=AcceptInviteRequest(
            org_id=org.id,
            email=resp.email,
            code=code,
            new_password="Correct-Horse-9!",
        ),
        db_session=db,
    )

    user = await db.get(User, resp.user_id)
    await db.refresh(user)
    assert security_verify_password("Correct-Horse-9!", user.password)

    # The same link, used again -- as it would be if the email were forwarded.
    with pytest.raises(HTTPException) as exc:
        await accept_school_invite(
            payload=AcceptInviteRequest(
                org_id=org.id,
                email=resp.email,
                code=code,
                new_password="Different-Pass-9!",
            ),
            db_session=db,
        )
    assert exc.value.status_code == 400

    # And the first password still stands: the replay changed nothing.
    await db.refresh(user)
    assert security_verify_password("Correct-Horse-9!", user.password)


@pytest.mark.asyncio
async def test_expired_token_fails_closed(db, org, fake_redis, sent_emails):
    import json

    resp = await _provision(db, org)
    code = _issued_code(fake_redis)

    # Age the token past its expiry, exactly as a week's delay would.
    for key, raw in list(fake_redis.store.items()):
        if key.startswith("sms_invite:") and ":code:" in key:
            payload = json.loads(raw)
            payload["expires"] = 1
            fake_redis.store[key] = json.dumps(payload)

    with pytest.raises(HTTPException) as exc:
        await accept_school_invite(
            payload=AcceptInviteRequest(
                org_id=org.id, email=resp.email, code=code, new_password="Correct-Horse-9!"
            ),
            db_session=db,
        )
    assert exc.value.status_code == 400

    user = await db.get(User, resp.user_id)
    assert not security_verify_password("Correct-Horse-9!", user.password)


@pytest.mark.asyncio
async def test_resend_revokes_the_previous_link(db, org, fake_redis, sent_emails):
    resp = await _provision(db, org)
    first_code = _issued_code(fake_redis)

    await resend_school_invite(
        user_id=resp.user_id,
        request=None,
        db_session=db,
        principal=_admin(org.id),
    )
    second_code = _issued_code(fake_redis)
    assert second_code != first_code

    # The superseded link -- possibly sitting in the wrong person's inbox --
    # must no longer work.
    with pytest.raises(HTTPException):
        await accept_school_invite(
            payload=AcceptInviteRequest(
                org_id=org.id, email=resp.email, code=first_code, new_password="Correct-Horse-9!"
            ),
            db_session=db,
        )


@pytest.mark.asyncio
async def test_cannot_resend_to_someone_already_in(db, org, fake_redis, sent_emails):
    resp = await _provision(db, org)
    code = _issued_code(fake_redis)
    await accept_school_invite(
        payload=AcceptInviteRequest(
            org_id=org.id, email=resp.email, code=code, new_password="Correct-Horse-9!"
        ),
        db_session=db,
    )

    # Resending now would mint a fresh password-setting token for a live
    # account -- an account-takeover primitive handed to anyone who can read
    # that mailbox.
    with pytest.raises(HTTPException) as exc:
        await resend_school_invite(
            user_id=resp.user_id,
            request=None,
            db_session=db,
            principal=_admin(org.id),
        )
    assert exc.value.status_code in (404, 409)


# ---------------------------------------------------------------------------
# Honest delivery reporting
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bulk_reports_the_bounced_row_distinctly(db, org, fake_redis, monkeypatch):
    """"50 created" while three bounced is not fifty successes."""
    import src.services.sms.invite_emails as emails_mod

    def _selective(**kwargs):
        if kwargs.get("email") == "bounces@example.com":
            raise RuntimeError("Mailbox does not exist")
        return {"id": "msg_test"}

    monkeypatch.setattr(emails_mod, "send_school_invite_email", _selective)

    resp = await bulk_provision_school_people(
        payload=BulkProvisionRequest(
            people=[
                ProvisionPersonRequest(
                    role=SchoolRole.STUDENT, email="ok1@example.com", first_name="Ayesha"
                ),
                ProvisionPersonRequest(
                    role=SchoolRole.STUDENT, email="bounces@example.com", first_name="Bilal"
                ),
                ProvisionPersonRequest(
                    role=SchoolRole.STUDENT, email="ok2@example.com", first_name="Zara"
                ),
            ]
        ),
        db_session=db,
        principal=_admin(org.id),
    )

    assert resp.created == 3
    assert resp.invites_sent == 2
    assert resp.invites_failed == 1

    by_email = {r.email: r for r in resp.results}
    bounced = by_email["bounces@example.com"]

    # The account was created -- that part genuinely succeeded.
    assert bounced.status == "created"
    # But the invite did NOT, and it reads differently from the other two.
    assert bounced.invite_status == InviteStatus.DELIVERY_FAILED.value
    assert "Mailbox does not exist" in (bounced.invite_error or "")
    assert by_email["ok1@example.com"].invite_status == InviteStatus.PENDING.value

    # The row index survives, so the administrator can find the spreadsheet line.
    assert bounced.row == 1


@pytest.mark.asyncio
async def test_undeliverable_address_is_unknown_not_sent(db, org, fake_redis, monkeypatch):
    """A dropped message is not a delivered one."""
    import src.services.sms.invite_emails as emails_mod

    # `send_email` returns None when it deliberately drops an address.
    monkeypatch.setattr(emails_mod, "send_school_invite_email", lambda **kw: None)

    resp = await _provision(db, org, email="dropped@example.com")
    assert resp.invite_status == InviteStatus.UNKNOWN.value
    assert resp.invite_status != InviteStatus.PENDING.value


@pytest.mark.asyncio
async def test_token_store_failure_is_reported_not_swallowed(db, org, monkeypatch, sent_emails):
    import src.services.sms.invites as invites_mod

    monkeypatch.setattr(invites_mod, "_redis", lambda: None)

    resp = await _provision(db, org, email="noredis@example.com")

    # The account is still created -- that transaction already committed.
    assert resp.created_user is True
    # But nobody is claiming an invite went out.
    assert resp.invite_status == InviteStatus.DELIVERY_FAILED.value
    assert resp.invite_error


@pytest.mark.asyncio
async def test_withheld_invite_is_not_reported_as_failed(db, org, fake_redis, sent_emails):
    resp = await _provision(db, org, email="later@example.com", send_invite=False)
    assert resp.created_user is True
    assert resp.invite_status == "NOT_SENT"
    assert sent_emails == []


# ---------------------------------------------------------------------------
# Acceptance must not become an enumeration oracle
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unknown_address_and_bad_code_are_indistinguishable(db, org, fake_redis, sent_emails):
    resp = await _provision(db, org)

    with pytest.raises(HTTPException) as unknown_address:
        await accept_school_invite(
            payload=AcceptInviteRequest(
                org_id=org.id,
                email="nobody-here@example.com",
                code="aaaaaaaaaaaaaaaaaaaaaaaa",
                new_password="Correct-Horse-9!",
            ),
            db_session=db,
        )

    with pytest.raises(HTTPException) as bad_code:
        await accept_school_invite(
            payload=AcceptInviteRequest(
                org_id=org.id,
                email=resp.email,
                code="bbbbbbbbbbbbbbbbbbbbbbbb",
                new_password="Correct-Horse-9!",
            ),
            db_session=db,
        )

    # Same status AND same text: anything else tells an attacker which
    # addresses are real.
    assert unknown_address.value.status_code == bad_code.value.status_code == 400
    assert unknown_address.value.detail == bad_code.value.detail


@pytest.mark.asyncio
async def test_weak_password_is_refused(db, org, fake_redis, sent_emails):
    resp = await _provision(db, org)
    code = _issued_code(fake_redis)

    with pytest.raises(HTTPException) as exc:
        await accept_school_invite(
            payload=AcceptInviteRequest(
                org_id=org.id, email=resp.email, code=code, new_password="123"
            ),
            db_session=db,
        )
    assert exc.value.status_code == 400

    # The token was NOT burned by a rejected attempt -- the person gets to try
    # again with a stronger password rather than being locked out.
    await accept_school_invite(
        payload=AcceptInviteRequest(
            org_id=org.id, email=resp.email, code=code, new_password="Correct-Horse-9!"
        ),
        db_session=db,
    )


# ---------------------------------------------------------------------------
# Visibility for the administrator
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_admin_can_see_who_is_not_in_yet(db, org, fake_redis, sent_emails):
    await _provision(db, org, email="pending1@example.com")
    accepted = await _provision(db, org, email="joined@example.com")
    joined = await db.get(User, accepted.user_id)
    code = _issued_code(fake_redis, joined.user_uuid)
    await accept_school_invite(
        payload=AcceptInviteRequest(
            org_id=org.id, email=accepted.email, code=code, new_password="Correct-Horse-9!"
        ),
        db_session=db,
    )

    rows = await list_school_invites(
        status_filter=None, db_session=db, principal=_admin(org.id)
    )
    by_email = {r.subject_email: r.status for r in rows}
    assert by_email["pending1@example.com"] == InviteStatus.PENDING.value
    assert by_email["joined@example.com"] == InviteStatus.ACCEPTED.value


@pytest.mark.asyncio
async def test_a_teacher_cannot_list_or_resend_invites(db, org):
    """`require_roles` is a FastAPI dependency, so calling a handler directly
    bypasses it entirely. Pull the REAL gate off each route and run it with a
    teacher principal, which is what production actually does."""
    from fastapi.routing import APIRoute

    from src.routers.sms_identity import router

    gated = {
        "/identity/invites",
        "/identity/invites/{user_id}/resend",
        "/identity/invites/resend-pending",
    }
    checked = set()
    for route in router.routes:
        if not isinstance(route, APIRoute) or route.path not in gated:
            continue
        checkers = [
            dep.call
            for dep in route.dependant.dependencies
            if getattr(dep.call, "__name__", "") == "_role_checker"
        ]
        assert checkers, f"{route.path} declares no require_roles gate"
        for checker in checkers:
            with pytest.raises(HTTPException) as exc:
                await checker(principal=TEACHER)
            assert exc.value.status_code == 403
            assert await checker(principal=_admin(org.id)) is not None
        checked.add(route.path)

    assert checked == gated


@pytest.mark.asyncio
async def test_acceptance_is_deliberately_public(db, org):
    """The recipient cannot sign in yet, so this one route must NOT be gated.

    Asserted explicitly so that a later sweep adding auth everywhere cannot
    quietly lock every invited person out of the system.
    """
    from fastapi.routing import APIRoute

    from src.routers.sms_identity import router

    for route in router.routes:
        if isinstance(route, APIRoute) and route.path == "/identity/invites/accept":
            gates = [
                dep.call
                for dep in route.dependant.dependencies
                if getattr(dep.call, "__name__", "") == "_role_checker"
            ]
            assert gates == []
            return
    raise AssertionError("the acceptance route is missing")
