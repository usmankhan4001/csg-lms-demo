"""
RAG query service.

Handles vector similarity search and streaming LLM responses
grounded in course content.

Grade segregation note: CourseEmbedding chunk rows do not carry a
per-chunk grade-level column (that would need a schema migration to
src/db/course_embeddings.py, out of scope for this change). Instead,
per-grade segregation is achieved relationally: a course's grade-level
audience is derived from which class sections actually take it, via the
existing SMS timetable (src.db.sms_timetable.TimetableSchedule ->
src.db.sms_campus.ClassSection.grade_level). See resolve_course_ids_for_grade.
"""

import logging
from typing import AsyncGenerator, List, Optional, Sequence, Set

from sqlalchemy import text
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.services.ai.rag.embedding_service import embed_single_text
from src.services.ai.base import ask_ai_stream
from src.services.ai.llm import model_for_tier
from src.db.sms_campus import Campus, ClassSection
from src.db.sms_timetable import TimetableSchedule

logger = logging.getLogger(__name__)

TOP_K = 5

# Client spec target: only surface chunks whose semantic similarity to the
# query is at least this high. pgvector's `<=>` operator returns COSINE
# DISTANCE (0 = identical), so this is applied as `distance <= 1 - MIN_SIMILARITY`.
# Previously there was no relevance floor at all — the top_k nearest
# neighbours were always returned regardless of how distant they actually were.
MIN_SIMILARITY_THRESHOLD = 0.82

# Grade/enrollment/similarity filtering happens in Python after the SQL
# fetch (it can combine data the single SQL join doesn't have, e.g. the
# course -> section -> grade path). Over-fetch so filtering still leaves
# enough candidates to fill top_k.
_OVER_FETCH_FACTOR = 4


async def resolve_course_ids_for_grade(
    org_id: int,
    grade_level: str,
    db_session: AsyncSession,
) -> List[int]:
    """
    Resolve which course IDs are taught to a given grade level within an
    org, via the SMS class-section timetable. Used to segregate the
    knowledge base per grade at query time (see module docstring for why
    this is relational rather than a per-chunk column).
    """
    if not grade_level or db_session is None:
        return []
    try:
        stmt = (
            select(TimetableSchedule.course_id)
            .join(ClassSection, ClassSection.id == TimetableSchedule.section_id)
            .join(Campus, Campus.id == ClassSection.campus_id)
            .where(ClassSection.grade_level == grade_level, Campus.org_id == org_id)
            .distinct()
        )
        res = await db_session.execute(stmt)
        return [c for c in res.scalars().all() if c is not None]
    except Exception as e:
        logger.warning("Grade-level course resolution failed for grade '%s': %s", grade_level, e)
        return []


async def query_course_rag(
    question: str,
    org_id: int,
    db_session: AsyncSession,
    course_id: Optional[int] = None,
    top_k: int = TOP_K,
    course_ids: Optional[Sequence[int]] = None,
    grade_level: Optional[str] = None,
    min_similarity: Optional[float] = MIN_SIMILARITY_THRESHOLD,
) -> dict:
    """
    Retrieve relevant course content via vector similarity search.

    Args:
        question: The user's question
        org_id: Organization ID to scope the search
        course_id: Optional course ID to scope to a single course (None = all courses)
        db_session: Database session
        top_k: Number of results to return
        course_ids: Optional allow-list of course IDs (e.g. a student's
            actively enrolled courses). When given, only chunks from these
            courses are returned, regardless of `course_id`.
        grade_level: Optional grade level (e.g. "Grade 9") used to segregate
            the knowledge base per grade when `course_ids` is not already
            known. Resolved to an allow-list via resolve_course_ids_for_grade.
        min_similarity: Minimum cosine similarity in [0, 1] a chunk must
            have to be included (default 0.82 per spec). Pass None to
            disable the floor entirely.

    Returns:
        {context: str, sources: list[dict]}
    """
    # Embed the question
    query_embedding = await embed_single_text(question)

    # Build the similarity search query
    embedding_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

    allowed_course_ids: Optional[Set[int]] = None
    if course_ids:
        allowed_course_ids = {int(c) for c in course_ids}
    elif grade_level:
        resolved = await resolve_course_ids_for_grade(org_id, grade_level, db_session)
        allowed_course_ids = set(resolved)

    needs_post_filter = allowed_course_ids is not None or min_similarity is not None
    fetch_limit = top_k * _OVER_FETCH_FACTOR if needs_post_filter else top_k

    if course_id is not None:
        sql = text("""
            SELECT ce.id, ce.chunk_text, ce.activity_uuid, ce.activity_name,
                   ce.chapter_name, ce.course_name, ce.source_type, ce.block_uuid,
                   ce.course_id, c.course_uuid,
                   ce.embedding <=> :query_embedding AS distance
            FROM course_embedding ce
            JOIN course c ON c.id = ce.course_id
            WHERE ce.org_id = :org_id AND ce.course_id = :course_id
            ORDER BY ce.embedding <=> :query_embedding
            LIMIT :top_k
        """)
        params = {
            "query_embedding": embedding_str,
            "org_id": org_id,
            "course_id": course_id,
            "top_k": fetch_limit,
        }
    else:
        sql = text("""
            SELECT ce.id, ce.chunk_text, ce.activity_uuid, ce.activity_name,
                   ce.chapter_name, ce.course_name, ce.source_type, ce.block_uuid,
                   ce.course_id, c.course_uuid,
                   ce.embedding <=> :query_embedding AS distance
            FROM course_embedding ce
            JOIN course c ON c.id = ce.course_id
            WHERE ce.org_id = :org_id
            ORDER BY ce.embedding <=> :query_embedding
            LIMIT :top_k
        """)
        params = {
            "query_embedding": embedding_str,
            "org_id": org_id,
            "top_k": fetch_limit,
        }

    results = (await db_session.execute(sql, params)).fetchall()

    if not results:
        return {"context": "", "sources": []}

    # Post-filter by grade/enrollment allow-list and similarity floor. Done
    # in Python (rather than more SQL WHERE clauses) because the allow-list
    # is resolved from a separate relational join and callers may pass it
    # in directly (course_ids) without a grade_level at all.
    max_distance = (1.0 - min_similarity) if min_similarity is not None else None
    filtered_results = []
    for row in results:
        if allowed_course_ids is not None:
            row_course_id = getattr(row, "course_id", None)
            if row_course_id is None or int(row_course_id) not in allowed_course_ids:
                continue
        if max_distance is not None:
            distance = getattr(row, "distance", None)
            if distance is not None and distance > max_distance:
                continue
        filtered_results.append(row)
        if len(filtered_results) >= top_k:
            break
    results = filtered_results

    if not results:
        return {"context": "", "sources": []}

    # Build numbered context and deduplicated source list
    context_parts = []
    sources = []
    seen_sources = {}  # source_key -> source index (1-based)
    source_index = 0

    for row in results:
        chunk_text = row.chunk_text
        activity_name = row.activity_name
        chapter_name = row.chapter_name
        course_name = row.course_name
        source_type = row.source_type

        # Deduplicate sources and assign a stable number
        source_key = (row.activity_uuid, row.source_type, row.block_uuid)
        if source_key not in seen_sources:
            source_index += 1
            seen_sources[source_key] = source_index
            sources.append({
                "activity_uuid": row.activity_uuid,
                "activity_name": activity_name,
                "chapter_name": chapter_name,
                "course_name": course_name,
                "course_uuid": row.course_uuid,
                "source_type": source_type,
            })

        ref_num = seen_sources[source_key]
        context_parts.append(f"[Source {ref_num}]\n{chunk_text}")

    context = "\n\n---\n\n".join(context_parts)
    return {"context": context, "sources": sources}


async def query_course_rag_stream(
    question: str,
    org_id: int,
    db_session: AsyncSession,
    message_history: list,
    course_id: Optional[int] = None,
    mode: str = "course_only",
) -> tuple[AsyncGenerator[str, None], list[dict]]:
    """
    Perform RAG retrieval and return a streaming LLM response.

    Returns:
        Tuple of (stream_generator, sources)
    """
    # Retrieve relevant context
    rag_result = await query_course_rag(
        question=question,
        org_id=org_id,
        db_session=db_session,
        course_id=course_id,
    )

    context = rag_result["context"]
    sources = rag_result["sources"]

    # Build the grounding prompt based on mode
    citation_instructions = (
        "IMPORTANT: When referencing information from the provided sources, use numbered citations "
        "like [1], [2], etc. matching the source numbers. Do NOT write out full source names, "
        "paths, locations, or verbose references like '(From: Course > Chapter > Activity)'. "
        "Just use the short [1] notation inline. Example: 'The building has 5 floors [2].'"
    )

    # The copilot renders answers with remark-math + KaTeX, which reads $...$ and
    # $$...$$ only. A bare $ in front of a number would start a math run and swallow
    # the rest of the sentence, so ask for it escaped.
    math_instructions = (
        "MATH: Write any mathematical expression as LaTeX between dollar signs — $x^2$ inline, "
        "$$...$$ on its own lines for display equations. Escape a literal dollar sign as \\$ "
        "(for example \\$5)."
    )

    if context and mode == "general":
        system_prompt = (
            "You are a helpful, knowledgeable educational assistant. Answer the student's question "
            "thoroughly using both the course content provided below AND your own general knowledge. "
            "Treat the course content as your primary reference, but freely expand with additional "
            "context, explanations, examples, and insights from your training data. "
            "When you add information beyond the course material, wrap that part in a blockquote "
            "using the > prefix.\n\n"
            f"{citation_instructions}\n\n"
            f"{math_instructions}\n\n"
            f"Course Content:\n{context}"
        )
    elif context:
        # course_only mode (default)
        system_prompt = (
            "You are a helpful educational assistant. Answer the student's question "
            "based on the course content provided below.\n\n"
            f"{citation_instructions}\n\n"
            "SUPPLEMENTARY KNOWLEDGE: When you add any information that is NOT directly from the "
            "provided course content — even small additions, clarifications, or general context — "
            "you MUST wrap that part in a blockquote using the > prefix. Always do this, even for "
            "brief supplementary notes. Example:\n"
            "> This is additional context from general knowledge.\n\n"
            f"{math_instructions}\n\n"
            f"Course Content:\n{context}"
        )
    elif mode == "general":
        system_prompt = (
            "You are a helpful, knowledgeable educational assistant. No specific course content "
            "was found for this question, but that's fine — answer the student's question using "
            "your general knowledge. Be thorough and helpful.\n\n"
            f"{math_instructions}"
        )
    else:
        system_prompt = (
            "You are a helpful educational assistant. The student asked a question but "
            "no relevant course content was found. Let them know you couldn't find "
            "specific course material related to their question, but offer to help "
            "with what you know.\n\n"
            f"{math_instructions}"
        )

    # Create the streaming generator
    stream = ask_ai_stream(
        question=question,
        message_history=message_history,
        text_reference=context,
        message_for_the_prompt=system_prompt,
        model_name=model_for_tier("standard"),
    )

    return stream, sources
