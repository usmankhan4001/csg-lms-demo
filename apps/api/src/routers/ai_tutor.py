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
    SCHOOL_ADMIN,
    SUPER_ADMIN,
    PSYCHOLOGIST,
    get_current_user_principal,
    get_optional_user_principal,
    require_roles,
)
from src.db.ai_models import (
    AISafetyIncident,
    AISafetyIncidentRead,
)
from src.services.ai.socratic_tutor import (
    stream_socratic_guidance,
    check_tutor_daily_rate_limit,
)
from src.services.ai.base import (
    get_chat_session_history,
    save_message_to_history,
    chat_session_owner_id,
    TUTOR_SESSION_MODE,
)
from src.services.ai.crisis_classifier import classify_prompt_safety, log_safety_incident
from src.db.sms_ai_consent import AIConsentType
from src.services.sms.ai_consent import may_screen_for_crisis, resolve_consent
from src.security.school_ownership import get_user_id

logger = logging.getLogger(__name__)

# Knowing THAT a named child disclosed self-harm is itself the disclosure, so
# this matches ai_oversight._SAFEGUARDING rather than general staff oversight.
_SAFEGUARDING = [SUPER_ADMIN, SCHOOL_ADMIN, PSYCHOLOGIST]

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


async def consent_denied_event_generator(
    query_text: str,
    student_db_id: Optional[int],
    user_id: str,
    org_id: Optional[int],
    course_id: Optional[str],
    db_session: AsyncSession,
    consent_reason: str,
):
    """What a student gets when their guardian has not consented to AI tutoring.

    This does NOT simply refuse. The prompt is still run through the local
    safety screen first, because `classify_prompt_safety` is pure regex -- no
    model call, no network, nothing leaves the server (see
    services/sms/ai_consent.CONSENT_CRISIS_OVERRIDE_RATIONALE). A child who is
    blocked from tutoring and then discloses self-harm must still be shown
    crisis resources and still reach a counsellor; refusing them on a consent
    technicality would be the worst possible reading of a parent's wishes.

    The tutoring itself -- the part that ships their words to a third-party
    LLM -- is what is withheld.
    """
    screened = False
    if await may_screen_for_crisis(db_session, student_db_id, org_id):
        screened = True
        safety_result = classify_prompt_safety(query_text)
        if safety_result.is_flagged and safety_result.counselor_escalation_required:
            logger.warning(
                "Crisis detected for student '%s' who has NO AI tutoring consent. "
                "Tutoring withheld; safety escalation proceeding (category=%s).",
                user_id,
                safety_result.category.value,
            )
            try:
                await log_safety_incident(
                    student_id=user_id,
                    severity=safety_result.severity.value,
                    trigger_category=safety_result.category.value,
                    prompt_snippet=query_text,
                    counselor_notified=True,
                    db_session=db_session,
                    org_id=org_id,
                    course_id=str(course_id) if course_id else None,
                    details=safety_result.reason,
                )
            except Exception:
                logger.exception(
                    "Failed to log safety incident for consent-blocked student '%s'", user_id
                )
            message = safety_result.canned_response or (
                "Your message triggered safety protocols. A counselor has been notified."
            )
            payload = json.dumps({"chunk": message, "session_uuid": None})
            yield f"data: {payload}\n\n"
            yield f"data: {json.dumps({'done': True, 'full_response': message, 'session_uuid': None})}\n\n"
            return

    if not screened:
        logger.info(
            "Crisis screening skipped for student '%s': org disabled the crisis override "
            "and wellbeing monitoring consent is refused.",
            user_id,
        )

    message = (
        f"{consent_reason} The AI tutor is unavailable until that is in place. "
        "Your teacher can still help, and your course materials are unaffected."
    )
    payload = json.dumps(
        {"chunk": message, "session_uuid": None, "code": "AI_CONSENT_REQUIRED"}
    )
    yield f"data: {payload}\n\n"
    yield f"data: {json.dumps({'done': True, 'full_response': message, 'code': 'AI_CONSENT_REQUIRED'})}\n\n"


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
    owner_user_id: Optional[int] = None,
):
    """
    Generate Server-Sent Events (SSE) stream for Socratic Tutor responses.

    `owner_user_id` is the integer Learnhouse user id, which is what gets
    written to `chat_meta:` so the transcript can be attributed later. It is
    NOT `user_id` -- that is `principal.sub`, a UUID string.
    """
    accumulated_response = []

    # Tag a crisis turn so the client can give it deliberate prominence rather
    # than rendering it as an ordinary tutor reply. The consent refusal already
    # carries AI_CONSENT_REQUIRED; this is its safety equivalent.
    #
    # Classified HERE rather than threaded out of the generator on purpose:
    # classify_prompt_safety is pure, synchronous, local regex with no database
    # and no network, so re-running it on the same input cannot diverge, and
    # the crisis path inside the generator is left completely untouched. A
    # failure here must never block the stream.
    safety_code = None
    try:
        _pre = classify_prompt_safety(query_text)
        if _pre.is_flagged and _pre.counselor_escalation_required:
            safety_code = "SAFETY_ESCALATION"
    except Exception:
        logger.exception("Pre-stream safety tagging failed; streaming untagged.")

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
            frame = {"chunk": chunk, "session_uuid": session_uuid}
            if safety_code:
                frame["code"] = safety_code
            payload = json.dumps(frame)
            yield f"data: {payload}\n\n"

        # End of stream event
        full_text = "".join(accumulated_response)
        if session_uuid:
            try:
                save_message_to_history(
                    aichat_uuid=session_uuid,
                    user_message=query_text,
                    ai_response=full_text,
                    # The integer id, never principal.sub: save_message_to_history
                    # only writes `chat_meta:` when it receives an int, and
                    # without that record the ownership check below has nothing
                    # to compare against. `mode` keeps the transcript out of the
                    # copilot chat list (see TUTOR_SESSION_MODE).
                    user_id=owner_user_id,
                    course_uuid=course_id,
                    org_id=org_id,
                    mode=TUTOR_SESSION_MODE,
                )
            except Exception as hist_err:
                logger.warning("Failed to save Socratic chat to history: %s", hist_err)

        done_frame = {"done": True, "full_response": full_text, "session_uuid": session_uuid}
        if safety_code:
            done_frame["code"] = safety_code
        done_payload = json.dumps(done_frame)
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

    # Rate limit BEFORE any LLM call is made: ~1000 requests/day per student,
    # Redis-backed (see check_tutor_daily_rate_limit for the key convention
    # and UTC-midnight reset window).
    rate_result = check_tutor_daily_rate_limit(student_id=user_id, org_id=org_id)
    if not rate_result.is_allowed:
        retry_after = rate_result.retry_after_seconds
        hours = max(1, round(retry_after / 3600))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "TUTOR_DAILY_LIMIT_REACHED",
                "message": (
                    f"You've reached today's limit of {rate_result.limit} questions with the AI "
                    f"tutor. Your quota resets in about {hours} hour(s) (midnight UTC) — in the "
                    "meantime, please ask your teacher or check your course materials for help."
                ),
                "retry_after": retry_after,
            },
            headers={"Retry-After": str(retry_after)},
        )

    # Parental consent gate (M47). A minor's words are about to be sent to a
    # third-party LLM; without a recorded guardian decision that must not
    # happen silently. Checked AFTER the rate limit so a consent-blocked
    # student cannot be used to bypass quota accounting.
    #
    # `student_db_id` is the real integer user id from the session, never
    # anything the client supplied -- consent is resolved against the
    # StudentGuardian link, so a forged id would defeat the whole control.
    student_db_id: Optional[int] = None
    if principal is not None:
        raw = (principal.raw_claims or {}).get("lh_user_id")
        if isinstance(raw, int):
            student_db_id = raw

    if student_db_id is not None:
        consent = await resolve_consent(
            db_session, student_db_id, AIConsentType.AI_TUTOR, org_id
        )
        if not consent.allowed:
            return StreamingResponse(
                consent_denied_event_generator(
                    query_text=query_text,
                    student_db_id=student_db_id,
                    user_id=user_id,
                    org_id=org_id,
                    course_id=payload.course_id,
                    db_session=db_session,
                    consent_reason=consent.reason or "Parental consent has not been recorded.",
                ),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )

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
            # Anonymous callers get no attribution, so their session stays
            # unowned and readable only by the safeguarding roles.
            owner_user_id=get_user_id(principal) if principal is not None else None,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _may_read_tutor_session(principal: KeycloakUserPrincipal, session_uuid: str) -> bool:
    """Entitlement to read one tutor transcript: own it, or safeguarding.

    A tutor transcript is where a child's crisis disclosure actually lives, in
    their own words, so the privileged side is `_SAFEGUARDING` -- the same
    reasoning as that constant, not general staff oversight.
    """
    # has_any_role() already satisfies SUPER_ADMIN.
    if principal.has_any_role(_SAFEGUARDING):
        return True

    user_id = get_user_id(principal)
    if user_id is None:
        return False

    # Positive proof of ownership only. A session with no `chat_meta:` record
    # is one written before tutor sessions were attributed; "unattributed"
    # cannot be told apart from "owned by somebody else", so it is refused here
    # and left reachable by the safeguarding roles above. That locks the owner
    # out of that one legacy transcript, not out of the tutor -- every session
    # started from this change onwards is attributed on its first message.
    #
    # Deliberately NOT backfilled on later turns: whoever sent the next message
    # would become the recorded owner, so an unattributed session is safer left
    # unowned than claimed by whoever guesses its uuid first.
    owner_id = chat_session_owner_id(session_uuid)
    return owner_id is not None and owner_id == user_id


@router.get(
    "/history",
    response_model=SocraticHistoryResponse,
    summary="Get Socratic Chat Session History",
    description="Retrieve stored conversation turns for a Socratic tutor session.",
    responses={404: {"description": "Session not found"}},
)
async def api_get_socratic_history(
    session_uuid: str = Query(..., description="UUID of the chat session"),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
):
    """
    GET /api/v1/ai/tutor/history - Retrieve conversation history for a tutor session
    """
    # 404, never 403: a tutor transcript is where a child's crisis disclosure
    # lives, so an unentitled caller must not be able to tell a real session
    # uuid from a wrong one.
    if not _may_read_tutor_session(principal, session_uuid):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found",
        )

    session_data = get_chat_session_history(session_uuid)
    return SocraticHistoryResponse(
        session_uuid=session_data.get("aichat_uuid", session_uuid),
        message_history=session_data.get("message_history", []),
    )


@router.get(
    "/safety-flags",
    response_model=List[AISafetyIncidentRead],
    summary="List Student Wellbeing & Crisis Safety Incidents",
    description=(
        "Safeguarding surface: lists AI safety incidents for the counsellor and "
        "school leadership. TEACHER is deliberately excluded -- this returns the "
        "same AISafetyIncident rows as /ai/oversight/incidents, filterable by "
        "SELF_HARM, so leaving it teacher-visible would have been a second door "
        "to the disclosure that endpoint was just narrowed to protect."
    ),
    dependencies=[Depends(require_roles(_SAFEGUARDING))],
)
async def api_list_safety_flags(
    student_id: Optional[str] = Query(None, description="Filter incidents by student ID"),
    severity: Optional[str] = Query(None, description="Filter incidents by severity (LOW, MEDIUM, HIGH, CRITICAL)"),
    trigger_category: Optional[str] = Query(None, description="Filter by trigger category (SELF_HARM, CRISIS, etc.)"),
    limit: int = Query(50, ge=1, le=200, description="Max number of incidents to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db_session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_SAFEGUARDING)),
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
