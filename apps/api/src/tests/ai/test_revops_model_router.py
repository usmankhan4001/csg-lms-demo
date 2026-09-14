"""
Tests for RevOps per-org token budgets and the provider-routing seam.

The budget is a cost guardrail, not an auth boundary, so the behaviour that
matters most is what happens when Redis is DOWN: it must fail open rather
than take admissions AI offline for every school at once.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.services.ai.revops_model_router import (
    DEFAULT_MONTHLY_TOKEN_BUDGET,
    ProviderCandidate,
    TokenBudgetExceeded,
    build_token_budget_key,
    call_with_budget,
    check_token_budget,
    record_token_spend,
    resolve_provider_chain,
)

MODULE = "src.services.ai.revops_model_router"


def test_budget_key_is_org_and_month_scoped():
    key = build_token_budget_key(7, period="2026-09")
    assert key == "csg:7:2026-09:revops:monthly_token_spend"


def test_budget_key_handles_missing_org():
    assert build_token_budget_key(None, period="2026-09").startswith("csg:noorg:")


def test_budget_fails_open_when_redis_is_unavailable():
    with patch(f"{MODULE}.get_redis_client", return_value=None):
        result = check_token_budget(1)
    assert result.is_allowed is True
    assert result.degraded is True


def test_budget_fails_open_when_redis_raises():
    r = MagicMock()
    r.get.side_effect = RuntimeError("connection reset")
    with patch(f"{MODULE}.get_redis_client", return_value=r):
        result = check_token_budget(1)
    assert result.is_allowed is True
    assert result.degraded is True


def test_budget_blocks_once_limit_is_reached():
    r = MagicMock()
    r.get.return_value = str(DEFAULT_MONTHLY_TOKEN_BUDGET)
    with patch(f"{MODULE}.get_redis_client", return_value=r):
        result = check_token_budget(1)
    assert result.is_allowed is False
    assert result.remaining == 0


def test_budget_allows_under_limit_and_reports_remaining():
    r = MagicMock()
    r.get.return_value = "100"
    with patch(f"{MODULE}.get_redis_client", return_value=r):
        result = check_token_budget(1, limit=1000)
    assert result.is_allowed is True
    assert result.current_spend == 100
    assert result.remaining == 900


def test_expiry_is_set_only_on_first_write():
    """Re-setting the TTL on every call would slide the window forward and the
    monthly counter would never reset."""
    r = MagicMock()
    r.incrby.return_value = 500
    r.ttl.return_value = 120  # already has an expiry
    with patch(f"{MODULE}.get_redis_client", return_value=r):
        record_token_spend(1, 500)
    r.expire.assert_not_called()

    r2 = MagicMock()
    r2.incrby.return_value = 500
    r2.ttl.return_value = -1  # no expiry yet
    with patch(f"{MODULE}.get_redis_client", return_value=r2):
        record_token_spend(1, 500)
    r2.expire.assert_called_once()


def test_recording_spend_never_raises():
    r = MagicMock()
    r.incrby.side_effect = RuntimeError("redis gone")
    with patch(f"{MODULE}.get_redis_client", return_value=r):
        assert record_token_spend(1, 100) == 0


def test_provider_chain_is_never_empty():
    chain = resolve_provider_chain("some-model")
    assert len(chain) >= 1
    assert all(isinstance(c, ProviderCandidate) for c in chain)


def test_call_is_refused_before_spending_when_over_budget():
    r = MagicMock()
    r.get.return_value = str(DEFAULT_MONTHLY_TOKEN_BUDGET)
    invoked = []

    with patch(f"{MODULE}.get_redis_client", return_value=r):
        with pytest.raises(TokenBudgetExceeded):
            call_with_budget(1, "m", lambda c: invoked.append(c))

    # The point of checking first: the model is never called at all.
    assert invoked == []


def test_successful_call_records_spend():
    r = MagicMock()
    r.get.return_value = "0"
    r.incrby.return_value = 250
    r.ttl.return_value = 60

    with patch(f"{MODULE}.get_redis_client", return_value=r):
        out = call_with_budget(1, "m", lambda c: "ok", estimated_tokens=250)

    assert out == "ok"
    r.incrby.assert_called_once()


def test_failure_propagates_when_the_chain_is_exhausted():
    """With a single-provider chain there is nothing to fall back to, so the
    error must surface rather than being silently swallowed."""
    r = MagicMock()
    r.get.return_value = "0"

    def boom(_c):
        raise RuntimeError("provider down")

    with patch(f"{MODULE}.get_redis_client", return_value=r):
        with pytest.raises(RuntimeError, match="provider down"):
            call_with_budget(1, "m", boom)

    # Nothing was charged for a call that never produced a result.
    r.incrby.assert_not_called()
