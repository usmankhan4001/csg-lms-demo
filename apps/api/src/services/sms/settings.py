"""
Resolution and persistence for CSG School Settings.

THE CONTRACT THAT MATTERS: a school with no settings rows behaves exactly as
it did before this module existed. `resolve_group` falls back
campus -> org -> the code default in schemas/sms_settings.py, and those
defaults mirror the previously-hardcoded constants exactly. A missing row is
never an error and never a zeroed value -- "no fee policy configured" and "a
late fee of 0%" are different things, and this codebase has had fabricated
zero-for-absent data torn out repeatedly.

`get_fee_policy` / `get_grading_policy` are the typed entry points
services/sms/fees.py and services/sms/gradebook.py will call when they are
migrated off their module constants. They are deliberately here rather than in
those files so the import direction stays services -> schemas, never
services -> services.
"""

import datetime
import logging
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_settings import SchoolSettings
from src.schemas.sms_settings import (
    CrisisResourcesSettings,
    AdmissionsPolicySettings,
    GROUP_MODELS,
    FeePolicySettings,
    GradingPolicySettings,
    SettingsGroup,
    SettingsSource,
)

logger = logging.getLogger(__name__)


class InvalidSettingsPayload(ValueError):
    """Raised when a write does not match its group's schema.

    Surfaced as a 422 rather than swallowed: silently discarding a field an
    admin believes they just set is worse than refusing the write.
    """


async def _load_rows(
    session: AsyncSession,
    org_id: int,
    campus_id: Optional[int],
    group: SettingsGroup,
) -> Tuple[Optional[SchoolSettings], Optional[SchoolSettings]]:
    """Return (campus_row, org_row) for one group.

    Ordered by id so that even if a duplicate row somehow existed -- see the
    note on uniqueness in db/sms_settings.py -- reads stay deterministic and
    the most recently created row wins, matching what an admin last saved.
    """
    stmt = select(SchoolSettings).where(
        SchoolSettings.org_id == org_id,
        SchoolSettings.group_key == group.value,
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


def _coerce(group: SettingsGroup, payload: Dict[str, Any]) -> BaseModel:
    """Parse a stored payload, falling back to the default if it no longer fits.

    A stored row can go stale -- a field gets renamed, a group gains a required
    field. Refusing to serve settings at all in that case would take the whole
    school down for a schema drift, so this logs loudly and returns the code
    default instead. Loud because silently reverting a school's fee policy to
    the default is exactly the kind of thing nobody notices until a parent is
    charged the wrong amount.
    """
    model = GROUP_MODELS[group]
    try:
        return model(**payload)
    except ValidationError:
        logger.exception(
            "Stored settings for group %s no longer validate; falling back to "
            "the code default. The saved values are being IGNORED.",
            group.value,
        )
        return model()


async def resolve_group(
    session: AsyncSession,
    org_id: int,
    campus_id: Optional[int],
    group: SettingsGroup,
) -> Tuple[BaseModel, SettingsSource, Optional[datetime.datetime]]:
    """The effective settings for one group, and where they came from."""
    campus_row, org_row = await _load_rows(session, org_id, campus_id, group)

    if campus_row is not None:
        return _coerce(group, campus_row.payload or {}), SettingsSource.CAMPUS, campus_row.updated_at
    if org_row is not None:
        return _coerce(group, org_row.payload or {}), SettingsSource.ORG, org_row.updated_at
    return GROUP_MODELS[group](), SettingsSource.DEFAULT, None


async def resolve_all_groups(
    session: AsyncSession,
    org_id: int,
    campus_id: Optional[int],
) -> List[Tuple[SettingsGroup, BaseModel, SettingsSource, Optional[datetime.datetime]]]:
    """Every group resolved for this scope, in declaration order."""
    out = []
    for group in SettingsGroup:
        values, source, updated = await resolve_group(session, org_id, campus_id, group)
        out.append((group, values, source, updated))
    return out


async def write_group(
    session: AsyncSession,
    org_id: int,
    campus_id: Optional[int],
    group: SettingsGroup,
    values: Dict[str, Any],
    updated_by_user_id: Optional[int] = None,
) -> SchoolSettings:
    """Create or update one group's row for this exact scope.

    Read-then-write rather than a DB upsert, because the scope key includes a
    nullable campus_id and NULL != NULL makes a unique constraint unreliable
    for the org-level row (see db/sms_settings.py). Writes here are
    admin-only and infrequent, so the race window is not worth a
    dialect-specific partial index.

    Note this writes the row for the scope it is GIVEN. Passing campus_id=None
    writes the org-wide default, which is a more privileged act than editing
    one campus -- the router is responsible for deciding the caller may do it.
    """
    model = GROUP_MODELS[group]
    try:
        parsed = model(**values)
    except ValidationError as exc:
        raise InvalidSettingsPayload(str(exc)) from exc

    payload = parsed.model_dump(mode="json")

    stmt = select(SchoolSettings).where(
        SchoolSettings.org_id == org_id,
        SchoolSettings.group_key == group.value,
    )
    rows = list((await session.execute(stmt)).scalars().all())
    existing = next((r for r in rows if r.campus_id == campus_id), None)

    now = datetime.datetime.now(datetime.timezone.utc)
    if existing is None:
        existing = SchoolSettings(
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
# Typed entry points for the modules that will consume these.
#
# fees.py and gradebook.py keep their module constants as the ultimate
# fallback; these simply resolve a school's override when one exists.
# ---------------------------------------------------------------------------


async def get_fee_policy(
    session: AsyncSession, org_id: int, campus_id: Optional[int] = None
) -> FeePolicySettings:
    values, _, _ = await resolve_group(session, org_id, campus_id, SettingsGroup.FEE_POLICY)
    return values  # type: ignore[return-value]


async def get_grading_policy(
    session: AsyncSession, org_id: int, campus_id: Optional[int] = None
) -> GradingPolicySettings:
    values, _, _ = await resolve_group(session, org_id, campus_id, SettingsGroup.GRADING_POLICY)
    return values  # type: ignore[return-value]


async def get_grading_intervals(
    session: AsyncSession, org_id: int, campus_id: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Grade bands in the exact shape `resolve_letter_and_gpa` already accepts.

    That function takes `intervals` as a list of plain dicts, so this returns
    that shape rather than the typed model -- the migration in gradebook.py
    then becomes a one-line default swap, not a rewrite.
    """
    policy = await get_grading_policy(session, org_id, campus_id)
    return [i.model_dump(mode="json") for i in policy.intervals]


async def get_crisis_resources(
    session: AsyncSession, org_id: int, campus_id: Optional[int] = None
) -> CrisisResourcesSettings:
    """The school's own crisis helplines, for the AI tutor's escalation message.

    Defaults to empty, and that is deliberate: the message it feeds previously
    hardcoded US helplines in a deployment serving a school in Pakistan. The
    software must not guess a country's crisis lines -- a wrong number is worse
    than none -- so an unconfigured school gets an honest message saying so.
    """
    values, _, _ = await resolve_group(session, org_id, campus_id, SettingsGroup.CRISIS_RESOURCES)
    return values  # type: ignore[return-value]


async def get_admissions_policy(
    session: AsyncSession, org_id: int, campus_id: Optional[int] = None
) -> AdmissionsPolicySettings:
    """How much the admissions funnel may do without a human.

    Read by the inbound webhook before letting an AI agent reply to a real
    family, so a school can dial automation down without a code change.
    """
    values, _, _ = await resolve_group(session, org_id, campus_id, SettingsGroup.ADMISSIONS_POLICY)
    return values  # type: ignore[return-value]
