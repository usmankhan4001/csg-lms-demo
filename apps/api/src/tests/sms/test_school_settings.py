"""
CSG School Settings: resolution, fallback, and write scoping.

The load-bearing guarantee is that a school with NO settings rows behaves
exactly as it did before this module existed. Fee policy and grading scales
were hardcoded constants; if resolution ever returned a zero or an empty scale
for an unconfigured school, every fee accrual and every letter grade in the
system would silently change. `test_missing_row_yields_the_hardcoded_default`
and `test_defaults_still_match_the_module_constants` pin that.

The scoping tests cover the case that is easy to get wrong: campus_id=None is
not "no campus claimed", it is the ORG-WIDE row every campus inherits, so a
campus-bound admin writing it would change every other campus.
"""

import pytest
from fastapi import HTTPException

from src.routers.sms_settings import _assert_may_write_scope, update_settings_group
from src.schemas.sms_settings import SettingsGroup, SettingsSource
from src.services.sms.settings import (
    InvalidSettingsPayload,
    get_fee_policy,
    get_grading_intervals,
    resolve_group,
    write_group,
)
from src.tests.sms._principals import principal

# Mirrors the constants these settings fall back to.
from src.services.sms.fees import (
    DEFAULT_LATE_FEE_GRACE_DAYS,
    DEFAULT_LATE_FEE_MAX_PERCENT,
    DEFAULT_LATE_FEE_PERCENT_PER_PERIOD,
    DEFAULT_LATE_FEE_PERIOD_DAYS,
)
from src.services.sms.gradebook import DEFAULT_INTERVALS


# ---------------------------------------------------------------------------
# Fallback: campus -> org -> code default
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_row_yields_the_hardcoded_default_not_a_zero(db):
    """No row must mean "use the built-in policy", never 0.

    A late-fee percent of 0.0 and "no fee policy configured" are different
    things: the first silently stops charging every school on the system.
    """
    policy, source, updated = await resolve_group(
        db, org_id=1, campus_id=None, group=SettingsGroup.FEE_POLICY
    )
    assert source is SettingsSource.DEFAULT
    assert updated is None
    assert policy.late_fee_percent_per_period == DEFAULT_LATE_FEE_PERCENT_PER_PERIOD
    assert policy.late_fee_percent_per_period != 0.0


@pytest.mark.asyncio
async def test_defaults_still_match_the_module_constants(db):
    """Turning this feature on must change nothing for an existing school."""
    policy = await get_fee_policy(db, org_id=1)
    assert policy.late_fee_percent_per_period == DEFAULT_LATE_FEE_PERCENT_PER_PERIOD
    assert policy.late_fee_grace_days == DEFAULT_LATE_FEE_GRACE_DAYS
    assert policy.late_fee_period_days == DEFAULT_LATE_FEE_PERIOD_DAYS
    assert policy.late_fee_max_percent == DEFAULT_LATE_FEE_MAX_PERCENT

    intervals = await get_grading_intervals(db, org_id=1)
    assert len(intervals) == len(DEFAULT_INTERVALS)
    for got, expected in zip(intervals, DEFAULT_INTERVALS):
        assert got["grade"] == expected["grade"]
        assert got["min_percentage"] == expected["min_percentage"]
        assert got["gpa_point"] == expected["gpa_point"]


@pytest.mark.asyncio
async def test_org_row_is_inherited_by_a_campus_with_no_row(db):
    await write_group(
        db, org_id=1, campus_id=None, group=SettingsGroup.FEE_POLICY,
        values={"late_fee_percent_per_period": 5.0},
    )
    policy, source, _ = await resolve_group(
        db, org_id=1, campus_id=7, group=SettingsGroup.FEE_POLICY
    )
    assert source is SettingsSource.ORG
    assert policy.late_fee_percent_per_period == 5.0


@pytest.mark.asyncio
async def test_campus_row_overrides_the_org_row(db):
    await write_group(
        db, org_id=1, campus_id=None, group=SettingsGroup.FEE_POLICY,
        values={"late_fee_percent_per_period": 5.0},
    )
    await write_group(
        db, org_id=1, campus_id=7, group=SettingsGroup.FEE_POLICY,
        values={"late_fee_percent_per_period": 9.0},
    )

    scoped, source, _ = await resolve_group(db, org_id=1, campus_id=7, group=SettingsGroup.FEE_POLICY)
    assert source is SettingsSource.CAMPUS
    assert scoped.late_fee_percent_per_period == 9.0

    # A different campus still inherits the org row, not campus 7's override.
    other, other_source, _ = await resolve_group(
        db, org_id=1, campus_id=8, group=SettingsGroup.FEE_POLICY
    )
    assert other_source is SettingsSource.ORG
    assert other.late_fee_percent_per_period == 5.0


@pytest.mark.asyncio
async def test_another_org_is_not_affected(db):
    """Settings are per-org: org 1's policy must not leak into org 2."""
    await write_group(
        db, org_id=1, campus_id=None, group=SettingsGroup.FEE_POLICY,
        values={"late_fee_percent_per_period": 5.0},
    )
    policy, source, _ = await resolve_group(
        db, org_id=2, campus_id=None, group=SettingsGroup.FEE_POLICY
    )
    assert source is SettingsSource.DEFAULT
    assert policy.late_fee_percent_per_period == DEFAULT_LATE_FEE_PERCENT_PER_PERIOD


@pytest.mark.asyncio
async def test_writing_twice_updates_rather_than_duplicating(db):
    first = await write_group(
        db, org_id=1, campus_id=None, group=SettingsGroup.FEE_POLICY,
        values={"late_fee_percent_per_period": 5.0},
    )
    second = await write_group(
        db, org_id=1, campus_id=None, group=SettingsGroup.FEE_POLICY,
        values={"late_fee_percent_per_period": 6.0},
    )
    assert first.id == second.id
    policy, _, _ = await resolve_group(db, org_id=1, campus_id=None, group=SettingsGroup.FEE_POLICY)
    assert policy.late_fee_percent_per_period == 6.0


@pytest.mark.asyncio
async def test_invalid_values_are_refused_not_silently_dropped(db):
    with pytest.raises(InvalidSettingsPayload):
        await write_group(
            db, org_id=1, campus_id=None, group=SettingsGroup.FEE_POLICY,
            values={"late_fee_grace_days": "not-a-number"},
        )


# ---------------------------------------------------------------------------
# Write scoping
# ---------------------------------------------------------------------------


def test_campus_bound_admin_cannot_write_another_campus():
    bound = principal("SCHOOL_ADMIN", campus_id=2)
    with pytest.raises(HTTPException) as exc:
        _assert_may_write_scope(bound, 9)
    assert exc.value.status_code == 403


def test_campus_bound_admin_cannot_write_the_org_level_row():
    """The subtle one.

    campus_id=None is not "no campus claimed" here -- it is the row every
    campus inherits. `assert_campus_allowed` alone returns early on None, so
    without the explicit check a campus-bound admin could change settings for
    the entire organisation by omitting a query parameter.
    """
    bound = principal("SCHOOL_ADMIN", campus_id=2)
    with pytest.raises(HTTPException) as exc:
        _assert_may_write_scope(bound, None)
    assert exc.value.status_code == 403
    assert "every campus" in exc.value.detail


def test_campus_bound_admin_may_write_their_own_campus():
    _assert_may_write_scope(principal("SCHOOL_ADMIN", campus_id=2), 2)


def test_org_level_admin_may_write_org_and_any_campus():
    org_admin = principal("SCHOOL_ADMIN", campus_id=None)
    _assert_may_write_scope(org_admin, None)
    _assert_may_write_scope(org_admin, 9)


def test_superadmin_may_write_any_scope():
    su = principal("SUPER_ADMIN", campus_id=2)
    _assert_may_write_scope(su, None)
    _assert_may_write_scope(su, 9)


@pytest.mark.asyncio
async def test_endpoint_refuses_a_campus_bound_admin_writing_org_defaults(db):
    """End-to-end through the handler, not just the helper."""
    from src.schemas.sms_settings import SettingsGroupUpdate

    with pytest.raises(HTTPException) as exc:
        await update_settings_group(
            group=SettingsGroup.FEE_POLICY,
            payload=SettingsGroupUpdate(values={"late_fee_percent_per_period": 99.0}),
            campus_id=None,
            session=db,
            principal=principal("SCHOOL_ADMIN", campus_id=2),
        )
    assert exc.value.status_code == 403

    # And nothing was written.
    policy, source, _ = await resolve_group(
        db, org_id=1, campus_id=None, group=SettingsGroup.FEE_POLICY
    )
    assert source is SettingsSource.DEFAULT
    assert policy.late_fee_percent_per_period == DEFAULT_LATE_FEE_PERCENT_PER_PERIOD


def test_the_scope_assertion_discriminates():
    """Guard against the scoping tests going vacuous.

    An org-level admin writing the org row is exactly what SHOULD be allowed,
    so if `_assert_may_write_scope` ever started refusing everything, this
    would fail and the tests above would no longer prove anything.
    """
    _assert_may_write_scope(principal("SCHOOL_ADMIN", campus_id=None), None)

    with pytest.raises(HTTPException):
        _assert_may_write_scope(principal("SCHOOL_ADMIN", campus_id=2), None)
