'use client'

/**
 * The student-facing AI Tutor.
 *
 * WHY IT LIVES HERE. Learnhouse ships two shells deliberately: `dash/` for
 * people administering the org and `(withmenu)/` for people learning in it.
 * A student already lives in this shell -- courses, player, certificates,
 * my-school -- so the tutor belongs beside those. `/dash/ai-tutor` is the
 * staff OVERSIGHT surface (transcripts, safety incidents, access blocks) and
 * is a different product for a different person.
 *
 * Until now the only tutor chat on web was at
 * `app/student/courses/[courseId]/lesson/[lessonId]`, which nothing links to,
 * so no student could reach it without being handed a URL.
 *
 * TWO THINGS THIS SCREEN IS CAREFUL ABOUT
 * ---------------------------------------
 * 1. A CRISIS REPLY IS INDISTINGUISHABLE FROM A NORMAL ONE. When the safety
 *    classifier fires, `socratic_tutor.py:411` yields the canned crisis
 *    message as an ordinary string chunk -- no flag, no code, no marker. So
 *    the UI cannot detect it, and must not pretend to: keyword-sniffing for
 *    "988" would both miss real escalations and misfire on a maths question
 *    about the number. The design answer is that EVERY tutor reply renders
 *    calmly, legibly and as markdown, so the crisis message is presented
 *    correctly by default rather than by detection. Nothing here styles a
 *    tutor reply as an error.
 *
 * 2. A CONSENT REFUSAL ARRIVES AS HTTP 200. `ai_tutor.py` returns the refusal
 *    inside the SSE stream with `code: "AI_CONSENT_REQUIRED"`, not as a 403,
 *    so it is read off the event rather than a status code, and is rendered
 *    as guidance. The student has done nothing wrong; they need to know what
 *    to ask their school for.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { GraduationCap, Send, ShieldCheck, Sparkles } from 'lucide-react'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { EmptyState, SectionCard } from '@/components/widgets'
import { useSchoolSession } from '@/lib/api/useSchoolSession'
import { askTutor, TutorRateLimitError } from '@/modules/ai/tutor/api'
import type { TutorBlockReason, TutorMessage, TutorTurn } from '@/modules/ai/tutor/types'

interface AiTutorClientProps {
  org_id: number
  orgslug: string
}

/** How many prior turns to send back as context. */
const HISTORY_TURNS = 8

function newId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`
}

export default function AiTutorClient({ orgslug }: AiTutorClientProps) {
  const { session, checked } = useSchoolSession()
  const [messages, setMessages] = useState<TutorMessage[]>([])
  const [draft, setDraft] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [blocked, setBlocked] = useState<TutorBlockReason | null>(null)
  const [sessionUuid, setSessionUuid] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const endRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages])

  useEffect(() => {
    // Cancel an in-flight stream if the student navigates away mid-answer.
    return () => abortRef.current?.abort()
  }, [])

  const send = useCallback(async () => {
    const question = draft.trim()
    if (!question || isStreaming) return

    const studentMessage: TutorMessage = { id: newId(), role: 'student', text: question }
    const replyId = newId()

    // Context is taken from what is already on screen, before this turn.
    const history: TutorTurn[] = messages.slice(-HISTORY_TURNS).map((m) => ({
      role: m.role === 'student' ? 'user' : 'assistant',
      content: m.text,
    }))

    setMessages((prev) => [
      ...prev,
      studentMessage,
      { id: replyId, role: 'tutor', text: '' },
    ])
    setDraft('')
    setIsStreaming(true)
    setBlocked(null)

    const controller = new AbortController()
    abortRef.current = controller

    try {
      await askTutor(
        { query: question, history, session_uuid: sessionUuid },
        {
          onChunk: (chunk) =>
            setMessages((prev) =>
              prev.map((m) => (m.id === replyId ? { ...m, text: m.text + chunk } : m))
            ),
          onDone: (full, uuid, code) => {
            if (uuid) setSessionUuid(uuid)
            const isConsent = code === 'AI_CONSENT_REQUIRED'
            setMessages((prev) =>
              prev.map((m) =>
                m.id === replyId
                  ? { ...m, text: full || m.text, isConsentNotice: isConsent }
                  : m
              )
            )
            if (isConsent) {
              setBlocked({ kind: 'consent', message: full })
            }
          },
          onError: (message) =>
            setMessages((prev) =>
              prev.map((m) =>
                m.id === replyId
                  ? {
                      ...m,
                      // Report the failure; never substitute an invented answer.
                      text: `The tutor could not answer that just now. ${message}`,
                      isError: true,
                    }
                  : m
              )
            ),
        },
        controller.signal
      )
    } catch (err) {
      if (controller.signal.aborted) return
      if (err instanceof TutorRateLimitError) {
        setBlocked({
          kind: 'rate_limit',
          message: err.message,
          retryAfterSeconds: err.retryAfterSeconds,
        })
        // Drop the empty bubble -- nothing was answered.
        setMessages((prev) => prev.filter((m) => m.id !== replyId))
      } else {
        const text =
          err instanceof Error
            ? err.message
            : 'The tutor could not be reached.'
        setMessages((prev) =>
          prev.map((m) => (m.id === replyId ? { ...m, text, isError: true } : m))
        )
      }
    } finally {
      setIsStreaming(false)
      abortRef.current = null
    }
  }, [draft, isStreaming, messages, sessionUuid])

  if (!checked) {
    return (
      <div className="mx-auto w-full max-w-3xl px-4 py-8">
        <SectionCard title="AI Tutor" state="loading" />
      </div>
    )
  }

  const roles = session?.roles ?? []
  const isStudent = roles.includes('STUDENT')

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-4 py-8">
      <div>
        <h1 className="text-xl font-bold text-foreground">AI Tutor</h1>
        <p className="text-sm text-muted-foreground">
          A study coach that helps you work an answer out, rather than handing
          it to you.
        </p>
      </div>

      {!isStudent && (
        <EmptyState
          tone="caution"
          title="This is the student study coach"
          description="Your account has no student record at this school, so there are no enrolled subjects to scope the tutor to. Staff can review tutor activity from the school dashboard instead."
        />
      )}

      {isStudent && (
        <>
          <SectionCard
            id="tutor-conversation"
            title="Ask a question"
            icon={<Sparkles className="size-4 text-gray-500" />}
          >
            <div className="flex flex-col gap-4">
              {messages.length === 0 ? (
                <EmptyState
                  title="Nothing asked yet"
                  description="Ask about something you are studying. The tutor is limited to the subjects you are enrolled in, and will steer you back if a question drifts off your coursework."
                />
              ) : (
                <div
                  className="flex flex-col gap-3"
                  role="log"
                  aria-live="polite"
                  aria-label="Conversation with the AI tutor"
                >
                  {messages.map((m) => (
                    <MessageBubble key={m.id} message={m} isStreaming={isStreaming} />
                  ))}
                  <div ref={endRef} />
                </div>
              )}

              {blocked?.kind === 'rate_limit' && (
                <div className="rounded-lg bg-amber-50 px-4 py-3 text-sm text-amber-900">
                  {blocked.message}
                </div>
              )}

              <form
                className="flex items-end gap-2"
                onSubmit={(e) => {
                  e.preventDefault()
                  void send()
                }}
              >
                <label htmlFor="tutor-question" className="sr-only">
                  Your question
                </label>
                <textarea
                  id="tutor-question"
                  name="question"
                  rows={2}
                  value={draft}
                  disabled={isStreaming || blocked?.kind === 'rate_limit'}
                  onChange={(e) => setDraft(e.target.value)}
                  onKeyDown={(e) => {
                    // Enter sends; Shift+Enter makes a new line.
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault()
                      void send()
                    }
                  }}
                  placeholder="What are you stuck on?"
                  className="min-h-[3rem] flex-1 resize-y rounded-lg border-0 bg-white px-3 py-2 text-sm nice-shadow focus:outline-none focus:ring-2 focus:ring-black focus:ring-offset-2 disabled:opacity-60"
                />
                <button
                  id="tutor-send"
                  type="submit"
                  disabled={!draft.trim() || isStreaming || blocked?.kind === 'rate_limit'}
                  className="inline-flex items-center gap-2 rounded-lg bg-black px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-80 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  <Send className="size-4" />
                  <span>{isStreaming ? 'Thinking…' : 'Ask'}</span>
                </button>
              </form>
            </div>
          </SectionCard>

          <SectionCard
            id="tutor-how-it-works"
            title="How this works"
            icon={<ShieldCheck className="size-4 text-gray-500" />}
          >
            <ul className="flex list-disc flex-col gap-2 pl-5 text-sm text-muted-foreground">
              <li>
                The tutor is scoped to the subjects you are enrolled in. Ask
                about something else and it will bring you back to your
                coursework.
              </li>
              <li>
                It is built to guide rather than answer outright — expect
                questions back, and hints before solutions.
              </li>
              <li>
                Your school can review these conversations. If you write
                something that suggests you are struggling or unsafe, your
                school&rsquo;s wellbeing team is told so they can help.
              </li>
              <li>There is a daily limit on how many questions you can ask.</li>
            </ul>
          </SectionCard>
        </>
      )}
    </div>
  )
}

function MessageBubble({
  message,
  isStreaming,
}: {
  message: TutorMessage
  isStreaming: boolean
}) {
  if (message.role === 'student') {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] whitespace-pre-wrap rounded-2xl bg-black px-4 py-2 text-sm text-white">
          {message.text}
        </div>
      </div>
    )
  }

  // A tutor reply is never styled as an error, because a crisis response
  // arrives through this same path and must read as support, not failure.
  // The only exception is an explicit transport/server failure.
  const tone = message.isError
    ? 'bg-rose-50 text-rose-900'
    : message.isConsentNotice
      ? 'bg-sky-50 text-sky-950'
      : 'bg-white text-foreground nice-shadow'

  const isEmpty = message.text.length === 0

  return (
    <div className="flex items-start gap-2">
      <div className="mt-1 shrink-0 rounded-full bg-gray-100 p-1.5">
        <GraduationCap className="size-4 text-gray-600" />
      </div>
      <div className={`max-w-[85%] rounded-2xl px-4 py-2 text-sm ${tone}`}>
        {isEmpty && isStreaming ? (
          <span className="text-muted-foreground">Thinking…</span>
        ) : (
          // Rendered as markdown deliberately: the crisis message is written
          // with bold text, a bulleted list of helplines and a link. Rendered
          // as plain text a child in distress would see literal `**988**`
          // and an unclickable URL.
          <div className="prose prose-sm max-w-none prose-p:my-1 prose-ul:my-1 prose-a:underline">
            <Markdown remarkPlugins={[remarkGfm]}>{message.text}</Markdown>
          </div>
        )}
      </div>
    </div>
  )
}
