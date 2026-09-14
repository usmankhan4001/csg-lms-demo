"""
Resolution and persistence for RevOps Admin Config (M30).

THE CONTRACT THAT MATTERS, identical to school settings: a school with no
config rows behaves exactly as it did before this module existed. `resolve_group`
falls back campus -> org -> the code default in schemas/sms_revops_config.py,
and those defaults mirror the engines' hardcoded constants exactly. A missing
row is never an error and never a zeroed value -- a scoring weight of 0 and
"no scoring policy configured" are different things, and a zeroed weight would
silently disqualify every lead a school receives.

`get_lead_scoring` / `get_nurture` / `get_consent_policy` are the typed entry
points revops_lead_scoring.py and revops_drip_engine.py call when they are
migrated off their module constants. They live here rather than in those files
so the import direction stays services -> schemas, never services -> services.
"""

import datetime
import logging
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_revops_config import RevOpsConfig
from src.schemas.sms_revops_config import (
    BASELINE_FACTOR_MAX,
    REVOPS_GROUP_MODELS,
    ConsentPolicySettings,
    LeadScoringSettings,
    NurtureSettings,
    RevOpsConfigGroup,
    RevOpsConfigSource,
)

logger = logging.getLogger(__name__)


class InvalidRevOpsConfigPayload(ValueError):
    """Raised when a write does not match its group's schema.

    Surfaced as a 422 rather than swallowed: silently discarding a weight an
    admin believes they just set is worse than refusing the write.
    """


async def _load_rows(
    session: AsyncSession,
    org_id: int,
    campus_id: Optional[int],
    group: RevOpsConfigGroup,
) -> Tuple[Optional[RevOpsConfig], Optional[RevOpsConfig]]:
    """Return (campus_row, org_row) for one group.

    Ordered by id so that even if a duplicate row somehow existed -- see the
    note on uniqueness in db/sms_revops_config.py -- reads stay deterministic
    and the most recently created row wins, matching what an admin last saved.
    """
    stmt = select(RevOpsConfig).where(
        RevOpsConfig.org_id == org_id,
        RevOpsConfig.group_key == group.value,
    )
    rows = list((await session.execute(stmt)).scalars().all())
    rows.sort(key=lambda r: r.id or 0)

    campus_row = None
    org_row = None
    for row in rows:
        if row.campus_id is None:
            org_row = row
        elif campus_id is not None and row.campus_id == campus_id:
            campus_row = row
    return campus_row, org_row


def _coerce(group: RevOpsConfigGroup, payload: Dict[str, Any]) -> BaseModel:
    """Parse a stored payload, falling back to the default if it no longer fits.

    Loud, because silently reverting a school's scoring policy to the default
    is exactly the kind of thing nobody notices until the wrong families are
    being chased.
    """
    model = REVOPS_GROUP_MODELS[group]
    try:
        return model(**payload)
    except ValidationError:
        logger.exception(
            "Stored RevOps config for group %s no longer validates; falling back "
            "to the code default. The saved values are being IGNORED.",
            group.value,
        )
        return model()


async def resolve_group(
    session: AsyncSession,
    org_id: int,
    campus_id: Optional[int],
    group: RevOpsConfigGroup,
) -> Tuple[BaseModel, RevOpsConfigSource, Optional[datetime.datetime]]:
    """The effective config for one group, and where it came from."""
    campus_row, org_row = await _load_rows(session, org_id, campus_id, group)

    if campus_row is not None:
        return _coerce(group, campus_row.payload or {}), RevOpsConfigSource.CAMPUS, campus_row.updated_at
    if org_row is not None:
        return _coerce(group, org_row.payload or {}), RevOpsConfigSource.ORG, org_row.updated_at
    return REVOPS_GROUP_MODELS[group](), RevOpsConfigSource.DEFAULT, None


async def resolve_all_groups(
    session: AsyncSession,
    org_id: int,
    campus_id: Optional[int],
) -> List[Tuple[RevOpsConfigGroup, BaseModel, RevOpsConfigSource, Optional[datetime.datetime]]]:
    """Every group resolved for this scope, in declaration order."""
    out = []
    for group in RevOpsConfigGroup:
        values, source, updated = await resolve_group(session, org_id, campus_id, group)
        out.append((group, values, source, updated))
    return out


async def write_group(
    session: AsyncSession,
    org_id: int,
    campus_id: Optional[int],
    group: RevOpsConfigGroup,
    values: Dict[str, Any],
    updated_by_user_id: Optional[int] = None,
) -> RevOpsConfig:
    """Create or update one group's row for this exact scope.

    Read-then-write rather than a DB upsert, because the scope key includes a
    nullable campus_id and NULL != NULL makes a unique constraint unreliable
    for the org-level row. Writes here are admin-only and infrequent.

    Note this writes the row for the scope it is GIVEN. Passing campus_id=None
    writes the org-wide default, which is a more privileged act than editing
    one campus -- the router decides whether the caller may do it.
    """
    model = REVOPS_GROUP_MODELS[group]
    try:
        parsed = model(**values)
    except ValidationError as exc:
        raise InvalidRevOpsConfigPayload(str(exc)) from exc

    payload = parsed.model_dump(mode="json")

    stmt = select(RevOpsConfig).where(
        RevOpsConfig.org_id == org_id,
        RevOpsConfig.group_key == group.value,
    )
    rows = list((await session.execute(stmt)).scalars().all())
    existing = next((r for r in rows if r.campus_id == campus_id), None)

    now = datetime.datetime.now(datetime.timezone.utc)
    if existing is None:
        existing = RevOpsConfig(
            org_id=org_id,
            campus_id=campus_id,
            group_key=group.value,
            payload=payload,
            updated_at=now,
            updated_by_user_id=updated_by_user_id,
        )
    else:
        existing.payload = payload
        existing.updated_at = now
        existing.updated_by_user_id = updated_by_user_id

    session.add(existing)
    await session.commit()
    await session.refresh(existing)
    return existing


# ---------------------------------------------------------------------------
# Typed entry points for the engines that will consume these.
# ---------------------------------------------------------------------------


async def get_lead_scoring(
    session: AsyncSession, org_id: int, campus_id: Optional[int] = None
) -> LeadScoringSettings:
    values, _, _ = await resolve_group(session, org_id, campus_id, RevOpsConfigGroup.LEAD_SCORING)
    return values  # type: ignore[return-value]


async def get_nurture(
    session: AsyncSession, org_id: int, campus_id: Optional[int] = None
) -> NurtureSettings:
    values, _, _ = await resolve_group(session, org_id, campus_id, RevOpsConfigGroup.NURTURE)
    return values  # type: ignore[return-value]


async def get_consent_policy(
    session: AsyncSession, org_id: int, campus_id: Optional[int] = None
) -> ConsentPolicySettings:
    values, _, _ = await resolve_group(session, org_id, campus_id, RevOpsConfigGroup.CONSENT_POLICY)
    return values  # type: ignore[return-value]


def apply_scoring_weights(
    breakdown: Dict[str, Any], settings: LeadScoringSettings
) -> Dict[str, Any]:
    """Re-weight a raw scoring breakdown and re-band the intent.

    `calculate_lead_score` produces each factor against its BASELINE cap
    (completeness out of 25, responsiveness out of 20, and so on). This scales
    each to the school's configured weight by ratio, so a lead scoring 20/25 on
    completeness still means "80% of completeness" whatever weight is set.

    `total_possible` is returned alongside the total precisely so a score is
    never presented as "out of 100" when the weights do not sum to 100.

    Returns a NEW dict; the caller's breakdown is not mutated.
    """
    weights = {
        "completeness": settings.weight_completeness,
        "responsiveness": settings.weight_responsiveness,
        "grade_demand": settings.weight_grade_demand,
        "budget_fit": settings.weight_budget_fit,
        "timeline": settings.weight_timeline,
    }

    scaled: Dict[str, float] = {}
    total = 0.0
    for factor, weight in weights.items():
        baseline = BASELINE_FACTOR_MAX[factor]
        raw = float(breakdown.get(f"{factor}_score", 0.0) or 0.0)
        # baseline is a module constant and never 0, but guard anyway: a
        # divide-by-zero here would take down scoring for every lead.
        ratio = (raw / baseline) if baseline else 0.0
        value = round(ratio * weight, 1)
        scaled[f"{factor}_score"] = value
        total += value

    total = round(total, 1)
    total_possible = round(sum(weights.values()), 1)

    if total >= settings.hot_threshold:
        intent = "HOT"
    elif total >= settings.warm_threshold:
        intent = "WARM"
    else:
        intent = "COLD"

    return {
        "score": total,
        "total_possible": total_possible,
        "intent": intent,
        "breakdown": scaled,
        # Whether this lead's score is low enough that a human should look
        # before the funnel advances it. 0.0 (the default) disables the gate.
        "awaiting_human_review": (
            settings.human_review_below_score > 0.0
            and total < settings.human_review_below_score
        ),
    }


def consent_blocks_channel(
    lead: Dict[str, Any], channel_token: str, settings: ConsentPolicySettings
) -> bool:
    """Whether one channel token is blocked for this lead under `settings`.

    Default policy (`require_explicit_opt_in=False`) reproduces
    `_stage_consent_blocked` exactly: only an explicit False blocks. With
    opt-in required, unknown consent blocks too. This can only ever NARROW who
    is contactable, never widen it.
    """
    token = channel_token.lower()
    if token not in {c.lower() for c in settings.consent_tracked_channels}:
        # No consent field exists for this channel, so it never gates a stage
        # on its own.
        return False

    consent_key = f"{token}_consent"
    if consent_key in lead and lead.get(consent_key) is False:
        return True
    if settings.require_explicit_opt_in:
        return lead.get(consent_key) is not True
    return False
