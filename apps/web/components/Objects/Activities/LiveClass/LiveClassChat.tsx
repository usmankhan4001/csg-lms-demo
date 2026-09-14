'use client'

/**
 * In-class chat.
 *
 * Built on `useChat()` from `@livekit/components-react` (v2.9.24), which rides
 * LiveKit's own data channel rather than a separate socket. Two consequences
 * worth stating, because both are documented behaviour of that hook and not
 * something a nicer UI can paper over:
 *
 *   1. Messages reach only participants who are IN the room when they are
 *      sent. Someone joining late sees nothing that came before.
 *   2. Nothing is persisted. Refresh the page and the transcript is gone.
 *
 * So the panel says so, plainly, instead of implying a history that does not
 * exist. Persisting chat needs a backend channel that does not exist yet.
 *
 * Authorship is NOT client-supplied: `msg.from.identity` comes from the
 * LiveKit token, which the server mints after deriving who the caller is.
 * A participant cannot post as someone else by editing a payload — that
 * exact hole was closed server-side and must not be reintroduced here.
 */

import { useEffect, useRef, useState } from 'react'
import { useChat, useLocalParticipant } from '@livekit/components-react'
import { PaperPlaneRight } from '@phosphor-icons/react'
import { LH_INPUT } from '@/components/widgets'

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  if (parts.length === 0) return '?'
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
}

function timeOf(timestamp: number): string {
  try {
    return new Date(timestamp).toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return ''
  }
}

export function LiveClassChat() {
  const { chatMessages, send, isSending } = useChat()
  const { localParticipant } = useLocalParticipant()
  const [draft, setDraft] = useState('')
  const endRef = useRef<HTMLDivElement | null>(null)

  // Keep the newest message in view as the conversation grows.
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'end' })
  }, [chatMessages.length])

  const handleSend = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    const text = draft.trim()
    if (!text || isSending) return
    // Clear optimistically: the hook echoes the sent message back through
    // chatMessages, so leaving it would read as a duplicate draft.
    setDraft('')
    try {
      await send(text)
    } catch {
      // Put the text back rather than losing what someone typed.
      setDraft(text)
    }
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex-1 min-h-0 overflow-y-auto px-3 py-3">
        {chatMessages.length === 0 ? (
          <p className="px-1 pt-2 text-sm text-gray-400">
            No messages yet. Anything sent here reaches everyone currently in
            the class.
          </p>
        ) : (
          <ul className="flex flex-col gap-3">
            {chatMessages.map((msg, i) => {
              const who =
                msg.from?.name || msg.from?.identity || 'Unknown participant'
              const isMe =
                !!localParticipant &&
                msg.from?.identity === localParticipant.identity
              return (
                <li
                  key={`${msg.timestamp}-${i}`}
                  className="flex items-start gap-2"
                >
                  <div
                    className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-full bg-gray-100 text-[10px] font-semibold text-gray-600"
                    aria-hidden="true"
                  >
                    {initials(who)}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-baseline gap-2">
                      <span className="truncate text-xs font-semibold text-gray-900">
                        {isMe ? 'You' : who}
                      </span>
                      <span className="shrink-0 text-[10px] text-gray-400">
                        {timeOf(msg.timestamp)}
                      </span>
                    </div>
                    <p className="whitespace-pre-wrap break-words text-sm text-gray-700">
                      {msg.message}
                    </p>
                  </div>
                </li>
              )
            })}
          </ul>
        )}
        <div ref={endRef} />
      </div>

      <form
        onSubmit={handleSend}
        className="flex items-center gap-2 border-t border-gray-100 px-3 py-2"
      >
        <input
          id="live-class-chat-input"
          name="message"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Message the class…"
          autoComplete="off"
          className={LH_INPUT}
        />
        <button
          id="live-class-chat-send"
          type="submit"
          disabled={isSending || !draft.trim()}
          aria-label="Send message"
          className="inline-flex size-9 shrink-0 items-center justify-center rounded-lg bg-black text-white transition-colors hover:bg-gray-800 disabled:opacity-40"
        >
          <PaperPlaneRight size={16} weight="fill" />
        </button>
      </form>

      <p className="border-t border-gray-100 px-3 py-1.5 text-[11px] leading-snug text-gray-400">
        Chat is live only — messages are not saved, and anyone joining later
        will not see them.
      </p>
    </div>
  )
}

export default LiveClassChat
