/**
 * Mirrors `SocraticChatRequest` / the SSE event payloads emitted by
 * `apps/api/src/routers/ai_tutor.py` (`POST /api/v1/ai/tutor/chat`).
 */

export interface SocraticChatRequest {
  query?: string
  message?: string
  course_id?: string | null
  history?: ChatTurn[] | null
  session_uuid?: string | null
  /** Progressive hint scaffolding: 1=Clue, 2=Formula, 3=Analogous Example. */
  hint_level?: 1 | 2 | 3 | null
  model_name?: string | null
}

export interface ChatTurn {
  role: 'user' | 'assistant'
  content: string
}

/** One `data: {...}` SSE frame from the chat stream. */
export type TutorChatEvent =
  | { chunk: string; session_uuid?: string | null }
  | { done: true; full_response: string; session_uuid?: string | null }
  | { error: string }

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  /** true while an assistant message is still streaming in. */
  streaming?: boolean
}
