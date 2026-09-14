"""
RevOps model routing and per-tenant token budgets (M38).

WHAT THIS DOES AND DELIBERATELY DOES NOT DO
-------------------------------------------
The spec asks for an automatic failover chain (DeepSeek -> Qwen-2.5 ->
Claude/OpenAI) plus per-tenant monthly token budgets. Only the second half is
built here, and that is a deliberate call rather than an omission.

`services/ai/llm/provider.py`'s `build_model()` resolves ONE provider id and
ONE `api_key` from the single global `lh_config.ai_config`. There is no
per-provider credential storage anywhere in this codebase. A failover chain
built on top of it would hand the same key to three different providers'
endpoints, so every fallback hop would fail authentication -- producing
something that looks like resilient failover in code review and is
guaranteed to fail in production, at exactly the moment the primary provider
is already down. A chain that cannot possibly work is worse than no chain,
because it invites reliance on it.

So what exists here is:

  * **Real, working**: per-org monthly token budget accounting, so a tenant
    cannot silently burn unlimited spend.
  * **A real seam, not a stub**: `resolve_provider_chain()` returns the
    ordered chain that *would* be attempted, and `call_with_budget()` routes
    through it. Today that chain is length 1 (the single configured
    provider). The day multi-credential config lands, only
    `resolve_provider_chain()` changes and failover starts working -- no
    caller changes.

The budget counter deliberately mirrors the Socratic Tutor's Redis limiter
(`socratic_tutor.py`): same `csg:{org}:...` key convention, same fail-OPEN
posture. Fail-open matters here: a budget is a cost guardrail, not an
authorization boundary, and a Redis outage must not take admissions AI down
for every school at once.
"""

import calendar
import datetime
import logging
from dataclasses import dataclass
from typing import Any, Callable, List, Optional

from src.core.redis import get_redis_client

logger = logging.getLogger(__name__)

# Default ceiling per org per calendar month. Generous by design: this is a
# runaway-spend backstop, not a rationing mechanism.
DEFAULT_MONTHLY_TOKEN_BUDGET = 2_000_000

_BUDGET_MODULE = "revops"
_BUDGET_KEY_NAME = "monthly_token_spend"


def build_token_budget_key(org_id: Optional[int], period: Optional[str] = None) -> str:
    """csg:{org_id}:{YYYY-MM}:revops:monthly_token_spend

    Scoped by calendar month rather than a rolling window so a finance person
    can reconcile it against a monthly provider invoice.
    """
    org_part = str(org_id) if org_id is not None else "noorg"
    period_part = period or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m")
    return f"csg:{org_part}:{period_part}:{_BUDGET_MODULE}:{_BUDGET_KEY_NAME}"


def _seconds_until_month_end() -> int:
    """TTL to the end of the current UTC month, so the counter self-expires in
    step with the billing period it represents."""
    now = datetime.datetime.now(datetime.timezone.utc)
    last_day = calendar.monthrange(now.year, now.month)[1]
    month_end = now.replace(
        day=last_day, hour=23, minute=59, second=59, microsecond=0
    )
    return max(1, int((month_end - now).total_seconds()))


@dataclass
class TokenBudgetResult:
    is_allowed: bool
    current_spend: int
    limit: int
    remaining: int
    degraded: bool = False  # True when Redis was unavailable and we failed open


def check_token_budget(
    org_id: Optional[int],
    limit: int = DEFAULT_MONTHLY_TOKEN_BUDGET,
) -> TokenBudgetResult:
    """Read-only budget check. Fails OPEN when Redis is unreachable."""
    r = get_redis_client()
    if r is None:
        return TokenBudgetResult(True, 0, limit, limit, degraded=True)

    key = build_token_budget_key(org_id)
    try:
        raw = r.get(key)
        spend = int(raw) if raw is not None else 0
    except Exception:
        logger.warning("RevOps token-budget read failed for org=%s; failing open", org_id, exc_info=True)
        return TokenBudgetResult(True, 0, limit, limit, degraded=True)

    return TokenBudgetResult(
        is_allowed=spend < limit,
        current_spend=spend,
        limit=limit,
        remaining=max(0, limit - spend),
    )


def record_token_spend(org_id: Optional[int], tokens: int) -> int:
    """Add `tokens` to this org's monthly spend. Returns the new total.

    Never raises: losing an accounting increment must not fail the user-facing
    AI call that already succeeded.
    """
    if tokens <= 0:
        return 0
    r = get_redis_client()
    if r is None:
        return 0

    key = build_token_budget_key(org_id)
    try:
        new_total = r.incrby(key, tokens)
        ttl = r.ttl(key)
        # Only set the expiry on first write (or if it was somehow lost), so
        # the window isn't extended on every single call.
        if ttl is None or ttl < 0:
            r.expire(key, _seconds_until_month_end())
        return int(new_total)
    except Exception:
        logger.warning("RevOps token-spend record failed for org=%s", org_id, exc_info=True)
        return 0


class TokenBudgetExceeded(Exception):
    """Raised when an org has exhausted its monthly AI token budget."""

    def __init__(self, org_id: Optional[int], result: TokenBudgetResult) -> None:
        self.org_id = org_id
        self.result = result
        super().__init__(
            f"Organization {org_id} has used {result.current_spend} of its "
            f"{result.limit} monthly AI token budget."
        )


@dataclass
class ProviderCandidate:
    """One hop in the routing chain."""
    provider_id: str
    model_name: str


def resolve_provider_chain(model_name: str) -> List[ProviderCandidate]:
    """The ordered providers a RevOps AI call should try.

    THE SEAM. Today this is always length 1: the single provider configured in
    `lh_config.ai_config`, because that is the only one this deployment holds
    a credential for (see module docstring). It is a list rather than a scalar
    so that when per-provider credentials exist, this function alone changes
    and `call_with_budget` starts doing real failover with no caller edits.

    It deliberately does NOT invent a DeepSeek -> Qwen -> Claude chain against
    one shared key.
    """
    from config.config import get_learnhouse_config

    cfg = get_learnhouse_config().ai_config
    provider_id = (getattr(cfg, "provider", None) or "").strip().lower() or "openai"
    return [ProviderCandidate(provider_id=provider_id, model_name=model_name)]


def call_with_budget(
    org_id: Optional[int],
    model_name: str,
    invoke: Callable[[ProviderCandidate], Any],
    *,
    limit: int = DEFAULT_MONTHLY_TOKEN_BUDGET,
    estimated_tokens: int = 0,
) -> Any:
    """Run a RevOps AI call under this org's monthly budget, via the chain.

    `invoke` receives the chosen `ProviderCandidate` and does the actual model
    call, so this stays agnostic about pydantic-ai specifics and is trivially
    testable.

    Raises `TokenBudgetExceeded` BEFORE spending anything when the org is
    already over. Records spend after a successful call.
    """
    budget = check_token_budget(org_id, limit=limit)
    if not budget.is_allowed:
        raise TokenBudgetExceeded(org_id, budget)

    chain = resolve_provider_chain(model_name)
    last_error: Optional[Exception] = None

    for candidate in chain:
        try:
            result = invoke(candidate)
        except Exception as exc:  # noqa: BLE001 - re-raised below if chain exhausts
            last_error = exc
            logger.warning(
                "RevOps model call failed on provider=%s model=%s",
                candidate.provider_id,
                candidate.model_name,
                exc_info=True,
            )
            continue

        if estimated_tokens:
            record_token_spend(org_id, estimated_tokens)
        return result

    assert last_error is not None  # chain is never empty
    raise last_error
