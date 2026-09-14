"""
CSG School Settings API.

DELIBERATELY NOT BEHIND A FEATURE TOGGLE. Every other school module has one,
but the settings surface is where toggles are administered: putting it behind
its own flag creates a state a school cannot get out of without a developer
and a database client, which is the exact problem this module exists to solve.
It is gated on role instead, matching how `sms_campus` (the tenancy root)
stays always-on.

CAMPUS SCOPING HAS A SUBTLE CASE HERE, and it is the one worth reading twice.
`assert_campus_allowed` returns early when the requested campus is None,
because for most endpoints "no campus named" means "no cross-campus claim
made". For THIS module that is inverted: campus_id=None is the ORG-WIDE row,
which every campus inherits. So a campus-bound admin writing it would change
settings for every other campus -- a privilege escalation dressed as an
omitted field. `_assert_may_write_scope` handles that explicitly.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.events.database import get_db_session
from src.core.keycloak_auth import (
    KeycloakUserPrincipal,
    SCHOOL_ADMIN,
    SUPER_ADMIN,
    require_roles,
)
from src.schemas.sms_settings import (
    UI_EDITABLE_GROUPS,
    ResolvedSettingsGroup,
    SchoolSettingsRead,
    SettingsGroup,
    SettingsGroupUpdate,
)
from src.security.school_ownership import (
    assert_campus_allowed,
    require_org_id,
    resolve_scoped_campus_id,
)
from src.services.sms.settings import (
    InvalidSettingsPayload,
    resolve_all_groups,
    resolve_group,
    write_group,
)

router = APIRouter()

# School-admin and above. Settings drive money (fee policy) and grades
# (grading scale), so this is office-level, not teacher-wide.
_SETTINGS_ROLES = [SUPER_ADMIN, SCHOOL_ADMIN]


def _assert_may_write_scope(
    principal: KeycloakUserPrincipal, target_campus_id: Optional[int]
) -> None:
    """Decide whether this caller may write settings at this scope.

    A SUPER_ADMIN, and an org-level admin (one with no campus of their own),
    may write the org-wide row and any campus row. A CAMPUS-BOUND admin may
    write ONLY their own campus: not another campus, and not the org-wide row
    that every campus inherits.
    """
    if principal.is_superadmin:
        return

    caller_campus = principal.campus_id
    if caller_campus is None:
        # No campus binding -> org-level administrator.
        return

    if target_campus_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "You are scoped to a single campus and cannot edit the "
                "organisation-wide defaults, which apply to every campus. "
                "Edit your own campus's settings instead."
            ),
        )

    # Explicit cross-campus write: fail loudly rather than silently redirect.
    assert_campus_allowed(principal, target_campus_id)


@router.get(
    "",
    response_model=SchoolSettingsRead,
    summary="Read Resolved School Settings",
    description=(
        "Every settings group resolved for this scope, each tagged with where "
        "its values came from: CAMPUS (this campus overrides), ORG (inherited "
        "from the organisation default) or DEFAULT (nothing configured, using "
        "the built-in value). An admin needs that distinction to know whether "
        "editing creates an override or changes an existing one."
    ),
)
async def get_school_settings(
    campus_id: Optional[int] = Query(
        None, description="Campus to resolve for. Omitted = the organisation-wide view."
    ),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_SETTINGS_ROLES)),
) -> SchoolSettingsRead:
    # Reads narrow: a campus-bound admin asking for nothing in particular gets
    # their own campus, not an org-wide view they are not entitled to.
    scoped_campus = resolve_scoped_campus_id(principal, campus_id)

    resolved = await resolve_all_groups(session, require_org_id(principal), scoped_campus)
    return SchoolSettingsRead(
        org_id=require_org_id(principal),
        campus_id=scoped_campus,
        groups=[
            ResolvedSettingsGroup(
                group=group,
                source=source,
                values=values.model_dump(mode="json"),
                editable_in_ui=group in UI_EDITABLE_GROUPS,
                updated_at=updated.isoformat() if updated else None,
            )
            for (group, values, source, updated) in resolved
        ],
    )


@router.put(
    "/{group}",
    response_model=ResolvedSettingsGroup,
    summary="Update One Settings Group",
    description=(
        "Writes one group at the given scope. Omitting campus_id writes the "
        "organisation-wide default, which every campus without its own row "
        "inherits -- that is a broader act than editing one campus and is "
        "refused for campus-bound administrators."
    ),
    responses={
        403: {"description": "Not permitted to write settings at this scope"},
        422: {"description": "Values do not match this group's schema"},
    },
)
async def update_settings_group(
    group: SettingsGroup,
    payload: SettingsGroupUpdate,
    campus_id: Optional[int] = Query(
        None, description="Campus to write. Omitted = the organisation-wide default."
    ),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_SETTINGS_ROLES)),
) -> ResolvedSettingsGroup:
    _assert_may_write_scope(principal, campus_id)

    try:
        await write_group(
            session=session,
            org_id=require_org_id(principal),
            campus_id=campus_id,
            group=group,
            values=payload.values,
            updated_by_user_id=(principal.raw_claims or {}).get("lh_user_id"),
        )
    except InvalidSettingsPayload as exc:
        # 422 with the validation detail: an admin who mistypes a field needs
        # to know which one, not a generic rejection.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    values, source, updated = await resolve_group(
        session, require_org_id(principal), campus_id, group
    )
    return ResolvedSettingsGroup(
        group=group,
        source=source,
        values=values.model_dump(mode="json"),
        editable_in_ui=group in UI_EDITABLE_GROUPS,
        updated_at=updated.isoformat() if updated else None,
    )
