"""Shared fixtures for the school test suite.

Invite dispatch is switched OFF by default here. Provisioning now sends an
invitation as part of its normal work, which is correct -- an account nobody
can sign into was the defect that behaviour fixes -- but it means every test
that provisions somebody would otherwise reach for Redis and an email provider
that are not running, and wait out the connection timeout for each one. That
turned the provisioning suite from seconds into minutes while testing nothing
it is about.

Tests whose subject IS the invitation lifecycle (`test_people_invites.py`)
install their own in-memory token store and capture the mail, overriding this.
"""

import pytest


@pytest.fixture(autouse=True)
def _no_invite_dispatch_by_default(monkeypatch):
    """Make invite dispatch a no-op unless a test opts in.

    Patched at `_redis`, deliberately, rather than by stubbing `dispatch_invite`
    wholesale: this exercises the REAL failure path, so the suite keeps proving
    that an unreachable token store degrades to an honest DELIVERY_FAILED
    instead of taking provisioning down with it.
    """
    import src.services.sms.invites as invites_mod

    monkeypatch.setattr(invites_mod, "_redis", lambda: None)
