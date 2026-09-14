/**
 * Student-facing AI Tutor client.
 *
 * Real calls against `apps/api/src/routers/ai_tutor.py`, mounted at
 * `/api/v1/ai/tutor` (router prefix `/tutor` + mount prefix `/ai`,
 * `src/router.py:359-361`).
 *
 * WHY THIS DOES NOT REUSE THE LEGACY LESSON PAGE'S FETCH
 * -----------------------------------------------------
 * `app/student/courses/[courseId]/lesson/[lessonId]/page.tsx` is the only
 * other consumer of this endpoint, and it is wrong in three ways that would
 * have been inherited by copying it:
 *
 *   1. It never parses SSE. It appends the raw response body straight into
 *      the message bubble, so a student sees literal
 *      `data: {"chunk":"..."}` JSON rather than prose.
 *   2. It sends `context` and `hintType`, which the server does not accept.
 *      `SocraticChatRequest` takes `course_id` and `hint_level` (an int 1-3).
 *      Both fields were silently ignored.
 *   3. Its catch block FABRICATES a physics answer about torque, complete
 *      with LaTeX, whenever the network fails. Inventing an academic answer
 *      and presenting it as the tutor's is the exact failure class this
 *      codebase has removed repeatedly.
 *
 * This client parses SSE properly and surfaces failure as failure.
 */

import { apiGet, toQueryString } from '@/lib/api/api-client'
import { authReadyPromise, getActiveAccessToken } from '@/lib/api/session-token-bridge'
import { getBackendUrl } from '@/services/config/config'
import type {
  SocraticChatRequest,
  SocraticHistoryResponse,
  TutorStreamEvent,
} from './types'

/** Raised when the daily tutor quota is exhausted (HTTP 429). */
export class TutorRateLimitError extends Error {
  readonly retryAfterSeconds: number

  constructor(message: string, retryAfterSeconds: number) {
    super(message)
    this.name = 'TutorRateLimitError'
    this.retryAfterSeconds = retryAfterSeconds
  }
}

/**
 * Split a raw SSE buffer into decoded events.
 *
 * Frames are separated by a blank line and each payload line is prefixed
 * `data: `. A chunk boundary can land mid-frame, so the caller keeps the
 * trailing partial frame and feeds it back in on the next read.
 */
function drainFrames(buffer: string): { events: TutorStreamEvent[]; rest: string } {
  const events: TutorStreamEvent[] = []
  const parts = buffer.split('\n\n')
  // The final part is whatever has not been terminated yet.
  const rest = parts.pop() ?? ''

  for (const frame of parts) {
    for (const line of frame.split('\n')) {
      const trimmed = line.trimStart()
      if (!trimmed.startsWith('data:')) continue
      const raw = trimmed.slice('data:'.length).trim()
      if (!raw) continue
      try {
        events.push(JSON.parse(raw) as TutorStreamEvent)
      } catch {
        // A frame we cannot parse is dropped rather than shown to a student
        // as garbled text. The stream continues; a genuine server failure
        // arrives as its own `{ error }` frame.
      }
    }
  }

  return { events, rest }
}

export interface AskTutorHandlers {
  /** Called for each content chunk as it arrives. */
  onChunk: (chunk: string) => void
  /** Called once when the stream terminates normally. */
  onDone: (full: string, sessionUuid: string | null, code?: string) => void
  /** Called when the server reports a failure inside the stream. */
  onError: (message: string) => void
}

/**
 * Stream a Socratic tutor reply.
 *
 * Note the consent refusal arrives as a normal 200 SSE stream carrying
 * `code: "AI_CONSENT_REQUIRED"` -- not a 403 -- so the caller must read the
 * code off the events rather than switching on an HTTP status.
 */
export async function askTutor(
  payload: SocraticChatRequest,
  handlers: AskTutorHandlers,
  signal?: AbortSignal
): Promise<void> {
  await authReadyPromise
  const token = getActiveAccessToken()

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Accept: 'text/event-stream',
  }
  if (token) headers.Authorization = `Bearer ${token}`

  const response = await fetch(`${getBackendUrl()}/api/v1/ai/tutor/chat`, {
    method: 'POST',
    headers,
    body: JSON.stringify(payload),
    signal,
  })

  if (response.status === 429) {
    // The server sends a structured quota message plus Retry-After.
    let message =
      "You've reached today's limit for the AI tutor. Please ask your teacher for help in the meantime."
    let retryAfter = Number(response.headers.get('Retry-After') ?? 0)
    try {
      const body = await response.json()
      const detail = body?.detail
      if (detail && typeof detail === 'object') {
        if (typeof detail.message === 'string') message = detail.message
        if (typeof detail.retry_after === 'number') retryAfter = detail.retry_after
      }
    } catch {
      // Keep the fallback wording; the status alone is the useful signal.
    }
    throw new TutorRateLimitError(message, retryAfter)
  }

  if (!response.ok) {
    throw new Error(`The tutor could not be reached (HTTP ${response.status}).`)
  }
  if (!response.body) {
    throw new Error('The tutor sent no response body.')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let accumulated = ''
  let settled = false

  try {
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const { events, rest } = drainFrames(buffer)
      buffer = rest

      for (const event of events) {
        if (event.error) {
          settled = true
          handlers.onError(event.error)
          return
        }
        if (event.done) {
          settled = true
          handlers.onDone(
            event.full_response ?? accumulated,
            event.session_uuid ?? null,
            event.code
          )
          return
        }
        if (typeof event.chunk === 'string') {
          accumulated += event.chunk
          handlers.onChunk(event.chunk)
        }
      }
    }
  } finally {
    reader.releaseLock()
  }

  // The stream closed without a terminator. Report what did arrive rather
  // than discarding it, but never invent the missing remainder.
  if (!settled) {
    handlers.onDone(accumulated, payload.session_uuid ?? null)
  }
}

/** Stored turns for a session. */
export function getTutorHistory(sessionUuid: string): Promise<SocraticHistoryResponse> {
  return apiGet<SocraticHistoryResponse>(
    `/ai/tutor/history${toQueryString({ session_uuid: sessionUuid })}`
  )
}
