"""
Managed knowledge base for the RevOps agents (M34).

The agents' content was code-resident and unauditable: nobody could say where
a claim made to a family came from, or change it without a developer. This is
a CRUD surface with citations, so an answer is traceable to something a human
approved.

SCOPE, stated plainly: this is keyword retrieval over approved entries, NOT a
RAG pipeline. `search_entries` matches on title, body and category. Semantic
retrieval would need embeddings, a vector column and a re-embedding path on
every edit -- pgvector is already a dependency and `services/ai/rag/` exists,
so the seam is there, but half-building it would give the agents a retrieval
surface whose recall nobody had measured. Keyword search over a curated,
human-approved set is honest about what it does.

THE ONE RULE THAT MATTERS: a source is never synthesised. An entry saved
without a citation is stored sourceless and reported as such, so a reviewer
can see exactly which claims are unbacked. A plausible-looking invented
citation would be worse than none -- fabricated content has been torn out of
this codebase three times, including outbound copy naming a school that does
not exist.
"""

import datetime
from typing import List, Optional

from sqlalchemy import or_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_revops_config import KnowledgeEntryStatus, RevOpsKnowledgeEntry


async def list_entries(
    session: AsyncSession,
    org_id: int,
    campus_id: Optional[int] = None,
    status: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[RevOpsKnowledgeEntry]:
    """Entries for this scope.

    A campus-scoped read includes org-wide entries (campus_id IS NULL) as well
    as that campus's own: an org-wide fee policy applies at every campus, and
    hiding it from a campus view would make the KB look emptier than it is.
    """
    stmt = select(RevOpsKnowledgeEntry).where(RevOpsKnowledgeEntry.org_id == org_id)

    if campus_id is not None:
        stmt = stmt.where(
            or_(
                RevOpsKnowledgeEntry.campus_id == campus_id,
                RevOpsKnowledgeEntry.campus_id.is_(None),  # type: ignore[union-attr]
            )
        )
    if status:
        stmt = stmt.where(RevOpsKnowledgeEntry.status == status)
    if category:
        stmt = stmt.where(RevOpsKnowledgeEntry.category == category)

    stmt = stmt.order_by(RevOpsKnowledgeEntry.id.desc()).limit(limit).offset(offset)  # type: ignore[union-attr]
    return list((await session.execute(stmt)).scalars().all())


async def get_entry(
    session: AsyncSession, org_id: int, entry_id: int
) -> Optional[RevOpsKnowledgeEntry]:
    """One entry, scoped to the caller's org.

    Org-scoped rather than by id alone: an id from another organisation must
    read as "not found", not as someone else's content.
    """
    stmt = select(RevOpsKnowledgeEntry).where(
        RevOpsKnowledgeEntry.id == entry_id,
        RevOpsKnowledgeEntry.org_id == org_id,
    )
    return (await session.execute(stmt)).scalars().first()


async def search_entries(
    session: AsyncSession,
    org_id: int,
    query: str,
    campus_id: Optional[int] = None,
    published_only: bool = True,
    limit: int = 20,
) -> List[RevOpsKnowledgeEntry]:
    """Keyword search over approved entries.

    `published_only` defaults to True because this is what an agent calls: a
    DRAFT is a human's working note and must not be quoted at a parent.
    """
    if not query or not query.strip():
        return []

    pattern = f"%{query.strip().lower()}%"
    stmt = select(RevOpsKnowledgeEntry).where(RevOpsKnowledgeEntry.org_id == org_id)

    if published_only:
        stmt = stmt.where(RevOpsKnowledgeEntry.status == KnowledgeEntryStatus.PUBLISHED.value)
    if campus_id is not None:
        stmt = stmt.where(
            or_(
                RevOpsKnowledgeEntry.campus_id == campus_id,
                RevOpsKnowledgeEntry.campus_id.is_(None),  # type: ignore[union-attr]
            )
        )

    stmt = stmt.where(
        or_(
            RevOpsKnowledgeEntry.title.ilike(pattern),  # type: ignore[union-attr]
            RevOpsKnowledgeEntry.body.ilike(pattern),  # type: ignore[union-attr]
            RevOpsKnowledgeEntry.category.ilike(pattern),  # type: ignore[union-attr]
        )
    )
    return list((await session.execute(stmt.limit(limit))).scalars().all())


async def create_entry(
    session: AsyncSession,
    org_id: int,
    title: str,
    body: str,
    campus_id: Optional[int] = None,
    category: Optional[str] = None,
    source_label: Optional[str] = None,
    source_url: Optional[str] = None,
    status: str = KnowledgeEntryStatus.DRAFT.value,
    owner_user_id: Optional[int] = None,
) -> RevOpsKnowledgeEntry:
    """Create an entry.

    Note what is NOT done here: no default source is invented when
    `source_label` and `source_url` are both absent. Sourceless is a real,
    reportable state.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    entry = RevOpsKnowledgeEntry(
        org_id=org_id,
        campus_id=campus_id,
        title=title,
        body=body,
        category=category,
        source_label=source_label,
        source_url=source_url,
        status=status,
        owner_user_id=owner_user_id,
        created_at=now,
        updated_at=now,
        updated_by_user_id=owner_user_id,
    )
    session.add(entry)
    await session.commit()
    await session.refresh(entry)
    return entry


async def update_entry(
    session: AsyncSession,
    entry: RevOpsKnowledgeEntry,
    updated_by_user_id: Optional[int] = None,
    **fields,
) -> RevOpsKnowledgeEntry:
    """Update the given fields on an entry.

    Only keys explicitly passed are touched, so clearing a source is an
    explicit act (`source_label=None`) rather than a side effect of omitting it.
    """
    for key, value in fields.items():
        if hasattr(entry, key):
            setattr(entry, key, value)

    entry.updated_at = datetime.datetime.now(datetime.timezone.utc)
    entry.updated_by_user_id = updated_by_user_id

    session.add(entry)
    await session.commit()
    await session.refresh(entry)
    return entry


async def delete_entry(session: AsyncSession, entry: RevOpsKnowledgeEntry) -> None:
    """Remove an entry outright.

    Archiving (status=ARCHIVED) is the softer option and is what the UI should
    prefer; this exists for genuine mistakes.
    """
    await session.delete(entry)
    await session.commit()


def is_sourceless(entry: RevOpsKnowledgeEntry) -> bool:
    """True when nothing backs this entry.

    Surfaced on the read model so a reviewer can filter for unbacked claims
    rather than having to notice two empty fields.
    """
    return not (entry.source_label or entry.source_url)
