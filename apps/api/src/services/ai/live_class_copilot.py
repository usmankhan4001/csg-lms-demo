"""
Live Class AI Q&A & Transcription Copilot (M50)
================================================
Real-time pedagogical assistant for live classes that listens to teacher
audio transcripts, maintains rolling session context, and provides concise,
in-stream Q&A support for student chat without disrupting the live lesson.
"""

from datetime import datetime, timezone
import json
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional
from pydantic import BaseModel, Field

from sqlmodel.ext.asyncio.session import AsyncSession
from src.services.ai.llm import generate, generate_stream, model_for_tier
from src.services.ai.crisis_classifier import (
    classify_prompt_safety,
    compose_crisis_message,
    log_safety_incident,
)
from src.db.ai_models import AISafetySeverity, AISafetyCategory

logger = logging.getLogger(__name__)


async def _safety_reply(
    safety_result,
    db_session: Optional[AsyncSession],
    org_id: Optional[int],
    fallback: str,
) -> str:
    """The message a flagged student actually sees, school-aware where possible.

    `classify_prompt_safety` is sync regex with no database, so the message it
    carries is always the UNCONFIGURED fallback -- the one that says the school
    has not added its helplines yet. The Socratic tutor already upgrades that to
    the school's own numbers; the live-class copilot never did, so a child in
    distress in a live lesson got the "not configured" text even at a school
    that had configured its helplines. This closes that gap using the same
    lookup, so both surfaces stay in step.

    NEVER RAISES: a settings lookup failing must not stop a student in distress
    receiving support.
    """
    message = safety_result.canned_response or fallback
    if (
        db_session is None
        or org_id is None
        or safety_result.category != AISafetyCategory.SELF_HARM
    ):
        return message

    try:
        from src.services.sms.settings import get_crisis_resources

        resources = await get_crisis_resources(db_session, org_id)
        return compose_crisis_message(resources)
    except Exception:
        logger.exception(
            "Could not load school crisis resources for org %s; "
            "using the unconfigured message.",
            org_id,
        )
        return message

LIVE_COPILOT_SYSTEM_PROMPT = """You are the AI Teaching Assistant for a live interactive classroom.
Your role is to answer student questions in real-time during an ongoing lecture without disrupting the class.

PEDAGOGICAL & OPERATIONAL RULES:
1. GROUNDED IN RECENT LECTURE: Prioritize what the teacher just said or explained in the recent transcript.
2. CONCISE & CLEAR: Keep explanations direct and brief (2-4 sentences max), because the student is actively watching the live stream.
3. SOCRATIC & SUPPORTIVE: If the question is conceptual, explain the intuitive step or formula simply.
4. RAISE-HAND ESCALATION: If the question requires teacher discretion, conflicts with the teacher's explicit remarks, or is outside the lecture scope, give a short summary and suggest: "Consider raising your hand or asking in the live Q&A break."
5. SAFETY & INTEGRITY: Never provide direct answers to active live polls/quizzes if marked as an assessment.
"""


class TranscriptChunk(BaseModel):
    chunk_id: int
    speaker: str  # "teacher", "student", "system"
    text: str
    timestamp: float
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class LiveClassSessionState(BaseModel):
    session_id: str
    course_id: Optional[str] = None
    title: Optional[str] = None
    chunks: List[TranscriptChunk] = []
    question_history: List[Dict[str, Any]] = []
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class LiveClassQAResponse(BaseModel):
    session_id: str
    student_id: str
    student_name: str
    question: str
    answer: str
    referenced_timestamp: Optional[float] = None
    suggest_raise_hand: bool = False
    safety_flagged: bool = False


class LiveClassQAAssistant:
    """
    Manages live lecture transcript buffers and responds to in-stream student Q&A.
    """

    def __init__(self):
        # In-memory buffer indexed by session_id
        self._sessions: Dict[str, LiveClassSessionState] = {}

    def get_or_create_session(self, session_id: str, course_id: Optional[str] = None, title: Optional[str] = None) -> LiveClassSessionState:
        if session_id not in self._sessions:
            self._sessions[session_id] = LiveClassSessionState(
                session_id=session_id,
                course_id=course_id,
                title=title,
            )
        return self._sessions[session_id]

    def ingest_transcript_chunk(
        self,
        session_id: str,
        speaker: str,
        text: str,
        timestamp: Optional[float] = None,
        course_id: Optional[str] = None,
    ) -> TranscriptChunk:
        """
        Appends a newly transcribed speech segment from Whisper or LiveKit Agent into the session buffer.
        """
        session = self.get_or_create_session(session_id, course_id=course_id)
        ts = timestamp if timestamp is not None else float(len(session.chunks) * 5.0)
        chunk = TranscriptChunk(
            chunk_id=len(session.chunks) + 1,
            speaker=speaker.lower(),
            text=text.strip(),
            timestamp=round(ts, 2),
        )
        session.chunks.append(chunk)

        # Keep buffer bounded to last 200 chunks for memory efficiency
        if len(session.chunks) > 200:
            session.chunks = session.chunks[-200:]

        return chunk

    def get_transcript_window(self, session_id: str, last_n_chunks: int = 20) -> List[TranscriptChunk]:
        """
        Returns recent transcript chunks for context.
        """
        session = self._sessions.get(session_id)
        if not session or not session.chunks:
            return []
        return session.chunks[-last_n_chunks:]

    def format_transcript_context(self, session_id: str, last_n_chunks: int = 15) -> str:
        """
        Formats recent transcript chunks into a readable string prompt context.
        """
        chunks = self.get_transcript_window(session_id, last_n_chunks)
        if not chunks:
            return "No live lecture transcript recorded yet."

        lines = []
        for c in chunks:
            mins = int(c.timestamp // 60)
            secs = int(c.timestamp % 60)
            time_str = f"[{mins:02d}:{secs:02d}]"
            lines.append(f"{time_str} {c.speaker.capitalize()}: {c.text}")
        return "\n".join(lines)

    async def answer_student_question(
        self,
        session_id: str,
        student_id: str,
        student_name: str,
        question: str,
        course_id: Optional[str] = None,
        db_session: Optional[AsyncSession] = None,
        model_name: Optional[str] = None,
        org_id: Optional[int] = None,
    ) -> LiveClassQAResponse:
        """
        Generates a contextual response to a student's live chat question based on what the teacher explained.
        """
        # 1. Safety Guardrail & Crisis Sentiment Check
        safety_result = classify_prompt_safety(question)
        if safety_result.is_flagged:
            if db_session is not None and safety_result.counselor_escalation_required:
                try:
                    await log_safety_incident(
                        student_id=student_id,
                        severity=safety_result.severity.value,
                        trigger_category=safety_result.category.value,
                        prompt_snippet=question[:500],
                        counselor_notified=True,
                        db_session=db_session,
                        course_id=course_id,
                        details="Live class chat safety interception",
                    )
                except Exception as e:
                    logger.error("Failed to log live safety incident: %s", e)

            return LiveClassQAResponse(
                session_id=session_id,
                student_id=student_id,
                student_name=student_name,
                question=question,
                answer=await _safety_reply(
                    safety_result,
                    db_session,
                    org_id,
                    "Your message was flagged by safety filters.",
                ),
                safety_flagged=True,
            )

        # 2. Build live context
        transcript_context = self.format_transcript_context(session_id)
        session = self.get_or_create_session(session_id, course_id=course_id)

        user_prompt = f"""[LIVE CLASSROOM CONTEXT]
Recent Lecture Transcript:
{transcript_context}

[STUDENT QUESTION]
Student: {student_name} ({student_id})
Question: {question}

Provide a helpful, concise answer grounded in the teacher's recent explanation."""

        selected_model = model_name or model_for_tier("fast")

        try:
            ai_text = await generate(
                model_name=selected_model,
                user_prompt=user_prompt,
                system_prompt=LIVE_COPILOT_SYSTEM_PROMPT,
                max_tokens=250,
                temperature=0.3,
            )
        except Exception as e:
            logger.error("Live Class Copilot generation failed: %s", e)
            ai_text = (
                f"The teacher discussed this recently. In summary: please review the key formula or concept "
                f"or raise your hand during the Q&A pause."
            )

        # Determine if raise-hand advice is present
        suggest_raise = "raise your hand" in ai_text.lower() or "ask the teacher" in ai_text.lower()

        # Find closest referenced timestamp from recent teacher chunk
        ref_ts = None
        recent_teacher_chunks = [c for c in session.chunks if c.speaker == "teacher"]
        if recent_teacher_chunks:
            ref_ts = recent_teacher_chunks[-1].timestamp

        # Store in question history
        session.question_history.append({
            "student_id": student_id,
            "student_name": student_name,
            "question": question,
            "answer": ai_text,
            "timestamp": ref_ts,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

        return LiveClassQAResponse(
            session_id=session_id,
            student_id=student_id,
            student_name=student_name,
            question=question,
            answer=ai_text,
            referenced_timestamp=ref_ts,
            suggest_raise_hand=suggest_raise,
            safety_flagged=False,
        )

    async def stream_student_question_answer(
        self,
        session_id: str,
        student_id: str,
        student_name: str,
        question: str,
        course_id: Optional[str] = None,
        db_session: Optional[AsyncSession] = None,
        model_name: Optional[str] = None,
        org_id: Optional[int] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Streams SSE tokens for live in-stream Q&A response.
        """
        # Safety Check
        safety_result = classify_prompt_safety(question)
        if safety_result.is_flagged:
            if db_session is not None and safety_result.counselor_escalation_required:
                try:
                    await log_safety_incident(
                        student_id=student_id,
                        severity=safety_result.severity.value,
                        trigger_category=safety_result.category.value,
                        prompt_snippet=question[:500],
                        counselor_notified=True,
                        db_session=db_session,
                        course_id=course_id,
                        details="Live class stream chat safety interception",
                    )
                except Exception as e:
                    logger.error("Failed to log live safety incident: %s", e)

            yield await _safety_reply(
                safety_result,
                db_session,
                org_id,
                "Your message was flagged by safety filters.",
            )
            return

        transcript_context = self.format_transcript_context(session_id)
        user_prompt = f"""[LIVE CLASSROOM CONTEXT]
Recent Lecture Transcript:
{transcript_context}

[STUDENT QUESTION]
Student: {student_name} ({student_id})
Question: {question}

Provide a helpful, concise answer grounded in the teacher's recent explanation."""

        selected_model = model_name or model_for_tier("fast")

        try:
            async for chunk in generate_stream(
                model_name=selected_model,
                user_prompt=user_prompt,
                system_prompt=LIVE_COPILOT_SYSTEM_PROMPT,
            ):
                yield chunk
        except Exception as e:
            logger.error("Error streaming live copilot response: %s", e)
            yield f"The teacher touched upon this in the lesson. Please ask during the Q&A break."

    async def generate_live_summary(self, session_id: str, model_name: Optional[str] = None) -> str:
        """
        Generates a concise bulleted live recap of the lecture so far.
        """
        transcript = self.format_transcript_context(session_id, last_n_chunks=50)
        prompt = f"""Summarize the key learning points covered by the teacher so far in this live lecture into 3-5 concise bullet points:

Transcript:
{transcript}

Live Summary:"""

        selected_model = model_name or model_for_tier("fast")
        try:
            summary = await generate(
                model_name=selected_model,
                user_prompt=prompt,
                system_prompt="You are an expert educational summarizer for live classrooms.",
                max_tokens=250,
                temperature=0.3,
            )
            return summary
        except Exception as e:
            logger.error("Failed to generate live summary: %s", e)
            return "Live summary currently unavailable."

    def clear_session(self, session_id: str) -> bool:
        """Removes the live class session from the in-memory buffer."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False


# Singleton assistant instance
live_class_copilot = LiveClassQAAssistant()
