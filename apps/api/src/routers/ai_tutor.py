"""
AI Socratic Tutor & Wellbeing Safety Router (M39, M42, M47)
===========================================================
Provides streaming Socratic tutoring, progressive hint scaffolding,
chat session history, and role-protected crisis/safety incident reporting.
"""

import json
import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlmodel import select, col
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.events.database import get_db_session
from src.core.keycloak_auth import (
    KeycloakUserPrincipal,
    TEACHER,
    CAMPUS_PRINCIPAL,
    SUPER_ADMIN,
    get_optional_user_principal,
    require_roles,
)
from src.db.ai_models import (
    AISafetyIncident,
    AISafetyIncidentRead,
)
from src.services.ai.socratic_tutor import stream_socratic_guidance
from src.services.ai.base import get_chat_session_history, save_message_to_history

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tutor", tags=["ai-tutor"])


class SocraticChatRequest(BaseModel):
    query: Optional[str] = Field(default=None, description="The student's question or problem prompt")
    message: Optional[str] = Field(default=None, description="Alias for query")
    course_id: Optional[str] = Field(default=None, description="Optional course UUID or numeric ID for textbook RAG")
    history: Optional[List[Dict[str, Any]]] = Field(default=None, description="Prior conversation message turns")
    session_uuid: Optional[str] = Field(default=None, description="Session UUID for persisting conversation")
    hint_level: Optional[int] = Field(default=None, ge=1, le=3, description="Progressive hint level (1=Clue, 2=Formula, 3=Analogous Example)")
    model_name: Optional[str] = Field(default=None, description="Optional LLM model override")


class SocraticHistoryResponse(BaseModel):
    session_uuid: str
    message_history: List[Dict[str, Any]]


async def socratic_chat_event_generator(
    query_text: str,
    course_id: Optional[str],
    history: Optional[List[Dict[str, Any]]],
    user_id: str,
    org_id: Optional[int],
    db_session: AsyncSession,
    session_uuid: Optional[str],
    hint_level: Optional[int],
    model_name: Optional[str],
):
    """
    Generate Server-Sent Events (SSE) stream for Socratic Tutor responses.
    """
    accumulated_response = []
    try:
        async for chunk in stream_socratic_guidance(
            query=query_text,
            course_id=course_id,
            history=history,
            user_id=user_id,
            org_id=org_id,
            db_session=db_session,
            hint_level=hint_level,
            model_name=model_name,
        ):
            accumulated_response.append(chunk)
            payload = json.dumps({"chunk": chunk, "session_uuid": session_uuid})
            yield f"data: {payload}\n\n"

        # End of stream event
        full_text = "".join(accumulated_response)
        if session_uuid:
            try:
                save_message_to_history(
                    aichat_uuid=session_uuid,
                    user_message=query_text,
                    ai_response=full_text,
                    user_id=int(user_id) if user_id and str(user_id).isdigit() else None,
                    course_uuid=course_id,
                    org_id=org_id,
                )
            except Exception as hist_err:
                logger.warning("Failed to save Socratic chat to history: %s", hist_err)

        done_payload = json.dumps({"done": True, "full_response": full_text, "session_uuid": session_uuid})
        yield f"data: {done_payload}\n\n"

    except Exception as e:
        logger.error("Error in Socratic chat event generator: %s", e, exc_info=True)
        error_payload = json.dumps({"error": str(e)})
        yield f"data: {error_payload}\n\n"


@router.post(
    "/chat",
    summary="Socratic AI Academic Tutor Chat Stream",
    description="Stream Socratic guidance with progressive hints, textbook RAG, and crisis guardrail protection.",
    responses={
        200: {"description": "Server-Sent Events text/event-stream"},
        400: {"description": "Missing query or message parameter"},
    },
)
async def api_socratic_tutor_chat(
    payload: SocraticChatRequest,
    principal: Optional[KeycloakUserPrincipal] = Depends(get_optional_user_principal),
    db_session: AsyncSession = Depends(get_db_session),
):
    """
    POST /api/v1/ai/tutor/chat - Stream Socratic Tutor responses via SSE
    """
    query_text = payload.query or payload.message
    if not query_text or not query_text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either 'query' or 'message' field is required in the request payload.",
        )

    user_id = principal.sub if principal else "anonymous_student"
    org_id = principal.org_id if principal else None

    # If history is not explicitly passed in payload, attempt retrieval from session_uuid
    effective_history = payload.history
    if effective_history is None and payload.session_uuid:
        session_data = get_chat_session_history(payload.session_uuid)
        effective_history = session_data.get("message_history", [])

    return StreamingResponse(
        socratic_chat_event_generator(
            query_text=query_text,
            course_id=payload.course_id,
            history=effective_history,
            user_id=user_id,
            org_id=org_id,
            db_session=db_session,
            session_uuid=payload.session_uuid,
            hint_level=payload.hint_level,
            model_name=payload.model_name,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/history",
    response_model=SocraticHistoryResponse,
    summary="Get Socratic Chat Session History",
    description="Retrieve stored conversation turns for a Socratic tutor session.",
)
async def api_get_socratic_history(
    session_uuid: str = Query(..., description="UUID of the chat session"),
):
    """
    GET /api/v1/ai/tutor/history - Retrieve conversation history for a tutor session
    """
    session_data = get_chat_session_history(session_uuid)
    return SocraticHistoryResponse(
        session_uuid=session_data.get("aichat_uuid", session_uuid),
        message_history=session_data.get("message_history", []),
    )


@router.get(
    "/safety-flags",
    response_model=List[AISafetyIncidentRead],
    summary="List Student Wellbeing & Crisis Safety Incidents",
    description="Protected endpoint for teachers and campus principals to review AI safety flags and counselor notifications.",
    dependencies=[Depends(require_roles([TEACHER, CAMPUS_PRINCIPAL, SUPER_ADMIN]))],
)
async def api_list_safety_flags(
    student_id: Optional[str] = Query(None, description="Filter incidents by student ID"),
    severity: Optional[str] = Query(None, description="Filter incidents by severity (LOW, MEDIUM, HIGH, CRITICAL)"),
    trigger_category: Optional[str] = Query(None, description="Filter by trigger category (SELF_HARM, CRISIS, etc.)"),
    limit: int = Query(50, ge=1, le=200, description="Max number of incidents to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db_session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles([TEACHER, CAMPUS_PRINCIPAL, SUPER_ADMIN])),
):
    """
    GET /api/v1/ai/tutor/safety-flags - Role-protected safety incident review
    """
    stmt = select(AISafetyIncident)

    if student_id and isinstance(student_id, str):
        stmt = stmt.where(col(AISafetyIncident.student_id) == student_id)
    if severity and isinstance(severity, str):
        stmt = stmt.where(col(AISafetyIncident.severity) == severity.upper())
    if trigger_category and isinstance(trigger_category, str):
        stmt = stmt.where(col(AISafetyIncident.trigger_category) == trigger_category.upper())
    if principal and principal.org_id and not principal.is_superadmin:
        stmt = stmt.where(col(AISafetyIncident.org_id) == principal.org_id)

    off = offset if isinstance(offset, int) else 0
    lim = limit if isinstance(limit, int) else 50
    stmt = stmt.order_by(col(AISafetyIncident.id).desc()).offset(off).limit(lim)
    result = await db_session.execute(stmt)
    incidents = result.scalars().all()
    return incidents
