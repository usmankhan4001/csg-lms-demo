/**
 * Types for the student-facing Socratic AI Tutor.
 *
 * Mirrors `apps/api/src/routers/ai_tutor.py` (mounted at `/api/v1/ai/tutor`
 * -- router prefix `/tutor`, mount prefix `/ai`, see `src/router.py:359`).
 */

/** Request body for `POST /ai/tutor/chat` (`SocraticChatRequest`). */
export interface SocraticChatRequest {
  /** The student's question. The server accepts `query` or `message`. */
  query: string
  /** Optional course UUID or numeric id, used for textbook RAG. */
  course_id?: string | null
  /** Prior conversation turns, sent back so the tutor has context. */
  history?: TutorTurn[]
  /** Session UUID, so the server persists the exchange to history. */
  session_uuid?: string | null
  /** Progressive hint scaffolding: 1 = clue, 2 = formula, 3 = worked example. */
  hint_level?: 1 | 2 | 3 | null
}

/** One stored turn, matching what `/ai/tutor/history` returns. */
export interface TutorTurn {
  role: 'user' | 'assistant'
  content: string
}

/** `GET /ai/tutor/history?session_uuid=` (`SocraticHistoryResponse`). */
export interface SocraticHistoryResponse {
  session_uuid: string
  message_history: Array<Record<string, unknown>>
}

/**
 * A single decoded SSE frame from `/ai/tutor/chat`.
 *
 * The endpoint emits `data: <json>\n\n` frames, NOT raw text. Every frame is
 * one of:
 *   - a content chunk        `{ chunk, session_uuid, code? }`
 *   - the terminator         `{ done: true, full_response, session_uuid, code? }`
 *   - a server-side failure  `{ error }`
 */
export interface TutorStreamEvent {
  chunk?: string
  done?: boolean
  full_response?: string
  session_uuid?: string | null
  /**
   * Set to `AI_CONSENT_REQUIRED` when a guardian has not consented to AI
   * tutoring. The HTTP status is still 200 -- the refusal arrives *inside*
   * the stream, so it must be detected here rather than from a status code.
   */
  code?: string
  error?: string
}

/** Why the tutor is unavailable, when it is. */
export type TutorBlockReason =
  | { kind: 'consent'; message: string }
  | { kind: 'rate_limit'; message: string; retryAfterSeconds: number }

/** A message as rendered in the conversation. */
export interface TutorMessage {
  id: string
  role: 'student' | 'tutor'
  text: string
  /**
   * True when this reply arrived carrying `code: AI_CONSENT_REQUIRED`.
   * Rendered as guidance, never as an error -- the student has done nothing
   * wrong and needs to know what to ask their school for.
   */
  isConsentNotice?: boolean
  /** True when the server reported a genuine failure (`{ error }`). */
  isError?: boolean
}
