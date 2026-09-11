/**
 * Streaming client for `POST /api/v1/ai/tutor/chat` (`apps/api/src/routers/ai_tutor.py`).
 * ============================================================================================
 *
 * That endpoint is Server-Sent Events (`text/event-stream`) ONLY — there is
 * no plain-JSON alternative, so a mobile client has to consume the stream to
 * get any answer at all (the final `done` frame carries `full_response`).
 *
 * React Native's `fetch` does not reliably expose a readable `response.body`
 * stream across Hermes/iOS/Android the way a browser does, so this uses the
 * well-established RN workaround: `XMLHttpRequest` with `onprogress`, which
 * DOES expose `xhr.responseText` growing incrementally as bytes arrive. Each
 * tick we diff against what we've already parsed and split the new text on
 * blank-line (`\n\n`) SSE frame boundaries. This is the same technique used
 * by e.g. `@microsoft/fetch-event-source`'s RN fallback and `react-native-sse`
 * internally — implemented by hand here to avoid pulling in an extra
 * dependency for one endpoint.
 *
 * Caveat (documented, not silently glossed over): `onprogress` granularity on
 * Android's OkHttp-backed XHR can coalesce multiple small writes together
 * more aggressively than iOS. The parser below tolerates that (it just means
 * fewer, larger chunks arrive per callback, not broken data) but genuinely
 * fine-grained token-by-token animation may look chunkier on Android than on
 * iOS/web. That's a real platform limitation of this approach, not a bug to
 * "fix" without adding a native streaming dependency.
 */

import { API_BASE_URL } from '@/config/env'
import { loadStoredSession } from '@/auth/token'
import type { SocraticChatRequest, TutorChatEvent } from './types'

export interface StreamTutorChatHandlers {
  onChunk?: (text: string) => void
  onDone?: (fullResponse: string, sessionUuid?: string | null) => void
  /** Fired for both a server-sent `{error}` frame and a network/HTTP failure. */
  onError?: (message: string) => void
}

export interface StreamHandle {
  abort: () => void
}

function parseFrame(rawFrame: string): TutorChatEvent | null {
  // Each SSE frame looks like `data: {...json...}` (possibly with a
  // trailing newline) — see socratic_chat_event_generator in ai_tutor.py.
  const line = rawFrame.split('\n').find((l) => l.startsWith('data:'))
  if (!line) return null
  const jsonText = line.slice('data:'.length).trim()
  if (!jsonText) return null
  try {
    return JSON.parse(jsonText) as TutorChatEvent
  } catch {
    return null
  }
}

/**
 * Starts streaming a Socratic tutor response. Returns a handle whose
 * `abort()` cancels the in-flight request (e.g. the chat screen unmounting,
 * or the user navigating away mid-answer).
 */
export function streamTutorChat(payload: SocraticChatRequest, handlers: StreamTutorChatHandlers): StreamHandle {
  const state: { xhr: XMLHttpRequest | null; aborted: boolean; processedLength: number; buffer: string } = {
    xhr: null,
    aborted: false,
    processedLength: 0,
    buffer: '',
  }

  const consumeNewText = (newText: string) => {
    state.buffer += newText
    // SSE frames are separated by a blank line. Keep any trailing partial
    // frame in the buffer until the rest of it arrives.
    const frames = state.buffer.split('\n\n')
    state.buffer = frames.pop() ?? ''
    for (const frame of frames) {
      const event = parseFrame(frame)
      if (!event) continue
      if ('error' in event) {
        handlers.onError?.(event.error)
      } else if ('chunk' in event) {
        handlers.onChunk?.(event.chunk)
      } else if ('done' in event && event.done) {
        handlers.onDone?.(event.full_response, event.session_uuid)
      }
    }
  }

  void (async () => {
    const session = await loadStoredSession()
    if (state.aborted) return

    const xhr = new XMLHttpRequest()
    state.xhr = xhr
    xhr.open('POST', `${API_BASE_URL}/api/v1/ai/tutor/chat`)
    xhr.setRequestHeader('Content-Type', 'application/json')
    xhr.setRequestHeader('Accept', 'text/event-stream')
    if (session?.token) {
      xhr.setRequestHeader('Authorization', `Bearer ${session.token}`)
    }

    xhr.onprogress = () => {
      const newText = xhr.responseText.slice(state.processedLength)
      state.processedLength = xhr.responseText.length
      if (newText) consumeNewText(newText)
    }

    xhr.onerror = () => {
      handlers.onError?.('Could not reach the AI tutor. Check your connection and try again.')
    }

    xhr.onload = () => {
      if (xhr.status < 200 || xhr.status >= 300) {
        handlers.onError?.(`AI tutor request failed (HTTP ${xhr.status}).`)
        return
      }
      // Flush anything left in the buffer in case the server closed the
      // stream without a trailing blank line after the last frame.
      if (state.buffer.trim()) {
        const event = parseFrame(state.buffer)
        state.buffer = ''
        if (event && 'done' in event && event.done) {
          handlers.onDone?.(event.full_response, event.session_uuid)
        }
      }
    }

    xhr.send(JSON.stringify(payload))
  })()

  return {
    abort: () => {
      state.aborted = true
      state.xhr?.abort()
    },
  }
}
