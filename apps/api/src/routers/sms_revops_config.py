"""
RevOps Admin Config (M30) and Knowledge Base (M34) API.

CAMPUS SCOPING HAS THE SAME SUBTLE CASE AS SCHOOL SETTINGS, and it is worth
reading twice. `assert_campus_allowed` returns early when the requested campus
is None, because for most endpoints "no campus named" means "no cross-campus
claim made". For config that is INVERTED: campus_id=None is the ORG-WIDE row
which every campus inherits, so a campus-bound admin writing it would change
scoring and nurture policy for every other campus -- a privilege escalation
dressed as an omitted query parameter. `_assert_may_write_scope` handles it.

DELIBERATELY NOT BEHIND A FEATURE TOGGLE, matching sms_settings: this is an
administrative surface, and gating the controls behind the thing they control
creates a state a school cannot escape without a database client.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.events.database import get_db_session
from src.core.keycloak_auth import (
    KeycloakUserPrincipal,
    SCHOOL_ADMIN,
    STAFF,
    SUPER_ADMIN,
    require_roles,
)
from src.db.sms_revops_config import KnowledgeEntryStatus, RevOpsKnowledgeEntry
from src.schemas.sms_revops_config import (
    ResolvedRevOpsGroup,
    RevOpsConfigGroup,
    RevOpsConfigRead,
    RevOpsConfigUpdate,
)
from src.security.school_ownership import (
    assert_campus_allowed,
    require_org_id,
    resolve_scoped_campus_id,
)
from src.services.sms import revops_kb
from src.services.sms.revops_config import (
    InvalidRevOpsConfigPayload,
    resolve_all_groups,
    resolve_group,
    write_group,
)

router = APIRouter()

# Changing scoring weights or nurture cadence decides which families get
# chased and how often. Office-level, not officer-level.
_CONFIG_ROLES = [SUPER_ADMIN, SCHOOL_ADMIN]

# The knowledge base is admissions-officer working material: STAFF may curate
# it. Publishing is what makes an entry quotable, so it is gated separately
# below rather than folded in here.
_KB_ROLES = [SUPER_ADMIN, SCHOOL_ADMIN, STAFF]


def _assert_may_write_scope(
    principal: KeycloakUserPrincipal, target_campus_id: Optional[int]
) -> None:
    """Decide whether this caller may write config at this scope.

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
                "organisation-wide RevOps defaults, which apply to every "
                "campus. Edit your own campus's configuration instead."
            ),
        )

    # Explicit cross-campus write: fail loudly rather than silently redirect.
    assert_campus_allowed(principal, target_campus_id)


# ---------------------------------------------------------------------------
# M30 -- Admin config
# ---------------------------------------------------------------------------


@router.get(
    "/config",
    response_model=RevOpsConfigRead,
    summary="Read Resolved RevOps Configuration",
    description=(
        "Lead scoring, nurture cadence and consent policy resolved for this "
        "scope, each tagged with where its values came from: CAMPUS, ORG "
        "(inherited) or DEFAULT (nothing configured, using the built-in "
        "behaviour). An admin needs that distinction to know whether editing "
        "creates an override or changes an existing one."
    ),
)
async def get_revops_config(
    campus_id: Optional[int] = Query(
        None, description="Campus to resolve for. Omitted = the organisation-wide view."
    ),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_CONFIG_ROLES)),
) -> RevOpsConfigRead:
    # Reads narrow: a campus-bound admin asking for nothing in particular gets
    # their own campus, not an org-wide view they are not entitled to.
    scoped_campus = resolve_scoped_campus_id(principal, campus_id)

    resolved = await resolve_all_groups(session, require_org_id(principal), scoped_campus)
    return RevOpsConfigRead(
        org_id=require_org_id(principal),
        campus_id=scoped_campus,
        groups=[
            ResolvedRevOpsGroup(
                group=group,
                source=source,
                values=values.model_dump(mode="json"),
                updated_at=updated.isoformat() if updated else None,
            )
            for (group, values, source, updated) in resolved
        ],
    )


@router.put(
    "/config/{group}",
    response_model=ResolvedRevOpsGroup,
    summary="Update One RevOps Config Group",
    description=(
        "Writes one group at the given scope. Omitting campus_id writes the "
        "organisation-wide default, which every campus without its own row "
        "inherits -- a broader act than editing one campus, and refused for "
        "campus-bound administrators."
    ),
    responses={
        403: {"description": "Not permitted to write configuration at this scope"},
        422: {"description": "Values do not match this group's schema"},
    },
)
async def update_revops_config_group(
    group: RevOpsConfigGroup,
    payload: RevOpsConfigUpdate,
    campus_id: Optional[int] = Query(
        None, description="Campus to write. Omitted = the organisation-wide default."
    ),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_CONFIG_ROLES)),
) -> ResolvedRevOpsGroup:
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
    except InvalidRevOpsConfigPayload as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    values, source, updated = await resolve_group(
        session, require_org_id(principal), campus_id, group
    )
    return ResolvedRevOpsGroup(
        group=group,
        source=source,
        values=values.model_dump(mode="json"),
        updated_at=updated.isoformat() if updated else None,
    )


# ---------------------------------------------------------------------------
# M34 -- Knowledge base
# ---------------------------------------------------------------------------


class KnowledgeEntryRead(BaseModel):
    id: int
    org_id: int
    campus_id: Optional[int] = None
    title: str
    body: str
    category: Optional[str] = None
    source_label: Optional[str] = None
    source_url: Optional[str] = None
    # Surfaced explicitly so a reviewer can filter for unbacked claims rather
    # than having to notice two empty fields.
    is_sourceless: bool
    status: str
    owner_user_id: Optional[int] = None
    created_at: str
    updated_at: str


class KnowledgeEntryWrite(BaseModel):
    title: str
    body: str
    campus_id: Optional[int] = None
    category: Optional[str] = None
    # Both optional and never filled in automatically. An entry with no source
    # is stored sourceless.
    source_label: Optional[str] = None
    source_url: Optional[str] = None
    status: str = KnowledgeEntryStatus.DRAFT.value


def _to_read(entry: RevOpsKnowledgeEntry) -> KnowledgeEntryRead:
    return KnowledgeEntryRead(
        id=entry.id or 0,
        org_id=entry.org_id,
        campus_id=entry.campus_id,
        title=entry.title,
        body=entry.body,
        category=entry.category,
        source_label=entry.source_label,
        source_url=entry.source_url,
        is_sourceless=revops_kb.is_sourceless(entry),
        status=entry.status,
        owner_user_id=entry.owner_user_id,
        created_at=entry.created_at.isoformat(),
        updated_at=entry.updated_at.isoformat(),
    )


@router.get(
    "/knowledge",
    response_model=List[KnowledgeEntryRead],
    summary="List Knowledge Base Entries",
    description=(
        "Approved content the admissions agents may draw on. A campus-scoped "
        "read also includes organisation-wide entries, since those apply at "
        "every campus."
    ),
)
async def list_knowledge_entries(
    campus_id: Optional[int] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    category: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_KB_ROLES)),
) -> List[KnowledgeEntryRead]:
    scoped_campus = resolve_scoped_campus_id(principal, campus_id)
    entries = await revops_kb.list_entries(
        session,
        org_id=require_org_id(principal),
        campus_id=scoped_campus,
        status=status_filter,
        category=category,
        limit=limit,
        offset=offset,
    )
    return [_to_read(e) for e in entries]


@router.get(
    "/knowledge/search",
    response_model=List[KnowledgeEntryRead],
    summary="Search Knowledge Base",
    description=(
        "Keyword search over title, body and category. Returns PUBLISHED "
        "entries only by default: a DRAFT is a human's working note and must "
        "not be quoted at a family. This is keyword retrieval, not semantic "
        "search -- see services/sms/revops_kb.py on that decision."
    ),
)
async def search_knowledge_entries(
    q: str = Query(..., min_length=1, description="Search text"),
    campus_id: Optional[int] = Query(None),
    include_drafts: bool = Query(False),
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_KB_ROLES)),
) -> List[KnowledgeEntryRead]:
    scoped_campus = resolve_scoped_campus_id(principal, campus_id)
    entries = await revops_kb.search_entries(
        session,
        org_id=require_org_id(principal),
        query=q,
        campus_id=scoped_campus,
        published_only=not include_drafts,
        limit=limit,
    )
    return [_to_read(e) for e in entries]


@router.post(
    "/knowledge",
    response_model=KnowledgeEntryRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a Knowledge Base Entry",
    description=(
        "Creates an entry. A source is NEVER synthesised: an entry saved "
        "without a citation is stored sourceless and reported as such, so "
        "unbacked claims stay visible to a reviewer."
    ),
)
async def create_knowledge_entry(
    payload: KnowledgeEntryWrite,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_KB_ROLES)),
) -> KnowledgeEntryRead:
    # A write naming a campus fails loudly rather than landing on another one.
    assert_campus_allowed(principal, payload.campus_id)

    entry = await revops_kb.create_entry(
        session,
        org_id=require_org_id(principal),
        title=payload.title,
        body=payload.body,
        campus_id=payload.campus_id,
        category=payload.category,
        source_label=payload.source_label,
        source_url=payload.source_url,
        status=payload.status,
        owner_user_id=(principal.raw_claims or {}).get("lh_user_id"),
    )
    return _to_read(entry)


@router.put(
    "/knowledge/{entry_id}",
    response_model=KnowledgeEntryRead,
    summary="Update a Knowledge Base Entry",
    responses={404: {"description": "No such entry in this organisation"}},
)
async def update_knowledge_entry(
    entry_id: int,
    payload: KnowledgeEntryWrite,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_KB_ROLES)),
) -> KnowledgeEntryRead:
    entry = await revops_kb.get_entry(session, require_org_id(principal), entry_id)
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")

    # Guard both the entry's current campus and the destination: without the
    # second check a campus-bound admin could pull another campus's entry
    # across, or push their own out of sight.
    assert_campus_allowed(principal, entry.campus_id)
    assert_campus_allowed(principal, payload.campus_id)

    updated = await revops_kb.update_entry(
        session,
        entry,
        updated_by_user_id=(principal.raw_claims or {}).get("lh_user_id"),
        title=payload.title,
        body=payload.body,
        campus_id=payload.campus_id,
        category=payload.category,
        source_label=payload.source_label,
        source_url=payload.source_url,
        status=payload.status,
    )
    return _to_read(updated)


@router.delete(
    "/knowledge/{entry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a Knowledge Base Entry",
    description=(
        "Removes an entry outright. Setting status to ARCHIVED is the softer "
        "option and is what the UI should prefer; this is for genuine "
        "mistakes. School-admin only."
    ),
    responses={404: {"description": "No such entry in this organisation"}},
)
async def delete_knowledge_entry(
    entry_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_CONFIG_ROLES)),
) -> None:
    entry = await revops_kb.get_entry(session, require_org_id(principal), entry_id)
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")

    assert_campus_allowed(principal, entry.campus_id)
    await revops_kb.delete_entry(session, entry)
