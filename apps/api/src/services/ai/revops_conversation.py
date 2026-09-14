"""
Conversation memory for the admissions SDR agent (M29).

`revops_sdr_agent.handle_admissions_inquiry` accepts a `history` argument and
has always done so -- nothing ever passed one, so every reply was generated
cold. A parent who asked about fees on Monday and transport on Tuesday got two
replies that each opened as if it were first contact.

This module is the missing half: it persists both sides of the conversation
against the lead and hands the recent window back on the next turn.

Deliberately NOT summarised by an LLM. The turns are short and the value here
is fidelity -- what the parent actually said, and what we actually told them.
Compressing that through a model would introduce a place for the record to
drift from the truth, which is the failure mode this codebase has already had
to tear out twice (a GPA endpoint and a parent digest, both returning
confident invented figures).
"""

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.revops_conversation import LeadConversationTurn, TurnDirection

logger = logging.getLogger(__name__)

# How many prior turns to feed back. Enough for a thread to stay coherent,
# short enough that a long history cannot crowd out the current message.
DEFAULT_HISTORY_LIMIT = 10


async def record_turn(
    db_session: AsyncSession,
    *,
    lead_id: int,
    direction: TurnDirection,
    message: str,
    channel: Optional[str] = None,
    detected_intent: Optional[str] = None,
) -> Optional[LeadConversationTurn]:
    """Persist one turn. Never raises: losing a memory write must not fail the
    reply the parent is waiting on."""
    try:
        turn = LeadConversationTurn(
            lead_id=lead_id,
            direction=direction,
            message=(message or "")[:8000],
            channel=channel,
            detected_intent=detected_intent,
        )
        db_session.add(turn)
        await db_session.commit()
        await db_session.refresh(turn)
        return turn
    except Exception:
        logger.exception("Failed to record conversation turn for lead_id=%s", lead_id)
        try:
            await db_session.rollback()
        except Exception:
            logger.exception("Rollback failed after conversation-turn write error")
        return None


async def load_history(
    db_session: AsyncSession,
    lead_id: int,
    limit: int = DEFAULT_HISTORY_LIMIT,
) -> List[Dict[str, Any]]:
    """Recent turns oldest-first, shaped for `handle_admissions_inquiry`'s
    `history` argument.

    Returns [] on any failure -- a memory lookup problem should degrade the
    reply to a cold one, not break it.
    """
    try:
        result = await db_session.execute(
            select(LeadConversationTurn)
            .where(LeadConversationTurn.lead_id == lead_id)
            .order_by(LeadConversationTurn.created_at.desc())
            .limit(limit)
        )
        turns = list(result.scalars().all())
    except Exception:
        logger.exception("Failed to load conversation history for lead_id=%s", lead_id)
        return []

    turns.reverse()  # chronological for the agent
    return [
        {
            "role": "parent" if t.direction == TurnDirection.INBOUND else "admissions",
            "message": t.message,
            "channel": t.channel,
            "intent": t.detected_intent,
            "at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in turns
    ]


def lead_to_context(lead: Any) -> Dict[str, Any]:
    """Map an `AdmissionsLead` row onto the dict shape the SDR agent and drip
    engine expect.

    The consent keys matter most: `has_channel_consent` and
    `_stage_consent_blocked` both treat an ABSENT key as "unknown, allow" and
    only an explicit False as opt-out. AdmissionsLead stores real booleans, so
    passing them through preserves a genuine opt-out rather than letting it
    read as unknown.
    """
    return {
        "id": getattr(lead, "id", None),
        "lead_id": getattr(lead, "id", None),
        "parent_name": getattr(lead, "parent_name", None),
        "student_name": getattr(lead, "student_name", None),
        "email": getattr(lead, "email", None),
        "phone": getattr(lead, "phone", None),
        "grade": getattr(lead, "grade_applying_for", None),
        "target_grade": getattr(lead, "grade_applying_for", None),
        "whatsapp_consent": getattr(lead, "whatsapp_consent", None),
        "email_consent": getattr(lead, "email_consent", None),
    }
