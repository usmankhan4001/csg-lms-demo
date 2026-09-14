'use client'

/**
 * Messages & notifications (M13 / M35), attached as a Learnhouse dash module.
 *
 * Conversations and alerts sit on one page on purpose: both answer "what does
 * the school need me to know", and splitting them would give a user two
 * unread counts to reconcile.
 *
 * Who a person may message is decided entirely server-side (see
 * `services/notifications/messaging.py`). This screen does not filter
 * recipients or hide controls to enforce that -- it shows the conversations
 * the API returns, and surfaces the refusal reason verbatim when a send is
 * denied, so the rule has exactly one implementation.
 */

import { useState } from 'react'
import { Bell, MessageSquare } from 'lucide-react'
import { DashPageShell, DataTable, EmptyState, SectionCard, StatGrid, StatusChip, LH_INPUT, LH_PRIMARY_BUTTON } from '@/components/widgets'
import { ApiError } from '@/lib/api/api-client'
import { useApiResource } from '@/lib/api/useApiResource'
import { useSchoolSession } from '@/lib/api/useSchoolSession'
import {
  listNotifications,
  listThreads,
  markAllNotificationsRead,
  postMessage,
  readThread,
} from '@/modules/sms/messages/api'
import type { MessageRead } from '@/modules/sms/messages/api'

interface MessagesDashClientProps {
  org_id: number
  orgslug: string
}

export default function MessagesDashClient({}: MessagesDashClientProps) {
  const { session, checked } = useSchoolSession()
  const [openThreadId, setOpenThreadId] = useState<number | undefined>(undefined)
  const [messages, setMessages] = useState<MessageRead[]>([])
  const [loadingThread, setLoadingThread] = useState(false)
  const [reply, setReply] = useState('')
  const [sendError, setSendError] = useState<string | null>(null)
  const [sending, setSending] = useState(false)

  const threads = useApiResource(() => listThreads(), [], {
    skip: !checked,
    isEmpty: (d) => d.length === 0,
  })
  const notifications = useApiResource(() => listNotifications(), [], {
    skip: !checked,
    isEmpty: (d) => d.length === 0,
  })

  const unreadNotifications = (notifications.data ?? []).filter((n) => !n.is_read).length
  const unreadMessages = (threads.data ?? []).reduce((sum, t) => sum + t.unread_count, 0)

  async function openThread(id: number) {
    setOpenThreadId(id)
    setLoadingThread(true)
    setSendError(null)
    try {
      setMessages(await readThread(id))
      // Opening marks it read server-side, so the badge has to be refetched.
      threads.refetch()
    } catch {
      setMessages([])
      setSendError('Could not open this conversation.')
    } finally {
      setLoadingThread(false)
    }
  }

  async function handleReply(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (!reply.trim() || openThreadId === undefined) return
    setSending(true)
    setSendError(null)
    try {
      await postMessage(openThreadId, reply.trim())
      setReply('')
      setMessages(await readThread(openThreadId))
      threads.refetch()
    } catch (err) {
      // The server's refusal reason is shown verbatim: it explains WHY
      // ("You can only message staff who teach your own child"), which a
      // generic failure message would throw away.
      setSendError(
        err instanceof ApiError
          ? err.message
          : 'Could not send. Try again.'
      )
    } finally {
      setSending(false)
    }
  }

  async function handleMarkAllRead() {
    await markAllNotificationsRead().catch(() => null)
    notifications.refetch()
  }

  return (
    <DashPageShell
      title="Messages"
      description="Conversations with families and staff, and everything the school has notified you about."
    >
      <StatGrid
        state={threads.status === 'loading' ? 'loading' : 'success'}
        columns={3}
        items={[
          { label: 'Conversations', value: threads.data?.length ?? 0, icon: MessageSquare, tone: 'neutral' },
          { label: 'Unread messages', value: unreadMessages, icon: MessageSquare, tone: unreadMessages > 0 ? 'caution' : 'positive' },
          { label: 'Unread alerts', value: unreadNotifications, icon: Bell, tone: unreadNotifications > 0 ? 'caution' : 'positive' },
        ]}
      />

      <SectionCard
        id="threads"
        title="Conversations"
        icon={<MessageSquare className="size-4 text-gray-500" />}
        state={threads.status}
        error={threads.error}
        onRetry={threads.refetch}
        emptyTitle="No conversations yet"
        emptyDescription="Threads you take part in appear here. Who you can message is decided by your school role and the children you are connected to."
      >
        <DataTable
          rows={threads.data ?? []}
          rowKey={(row) => row.id}
          state="success"
          columns={[
            { key: 'subject', header: 'Subject', render: (r) => r.subject },
            {
              key: 'unread',
              header: 'Unread',
              align: 'right',
              render: (r) =>
                r.unread_count > 0 ? (
                  <StatusChip label={String(r.unread_count)} tone="caution" />
                ) : (
                  <span className="text-gray-400">—</span>
                ),
            },
            { key: 'count', header: 'Messages', align: 'right', render: (r) => r.message_count },
            {
              key: 'last',
              header: 'Last activity',
              render: (r) => new Date(r.last_message_at).toLocaleString(),
            },
            {
              key: 'open',
              header: '',
              align: 'right',
              render: (r) => (
                <button
                  type="button"
                  onClick={() => openThread(r.id)}
                  className="text-xs font-bold text-gray-600 hover:text-black"
                >
                  Open
                </button>
              ),
            },
          ]}
        />
      </SectionCard>

      {openThreadId !== undefined && (
        <SectionCard
          id="thread"
          title="Conversation"
          icon={<MessageSquare className="size-4 text-gray-500" />}
          state={loadingThread ? 'loading' : 'success'}
        >
          <div className="flex flex-col gap-3">
            {messages.length === 0 ? (
              <EmptyState title="No messages" description="This conversation is empty." />
            ) : (
              messages.map((m) => {
                const mine = session?.staff_id === m.sender_user_id || session?.student_id === m.sender_user_id
                return (
                  <div
                    key={m.id}
                    className={`rounded-xl px-4 py-3 text-sm ${
                      mine ? 'bg-black text-white self-end' : 'bg-gray-50 text-gray-800'
                    }`}
                    style={{ maxWidth: '80%' }}
                  >
                    <p className="whitespace-pre-wrap">{m.body}</p>
                    <p className={`mt-1 text-[11px] ${mine ? 'text-white/60' : 'text-gray-400'}`}>
                      {new Date(m.created_at).toLocaleString()}
                    </p>
                  </div>
                )
              })
            )}

            <form onSubmit={handleReply} className="flex items-center gap-2 pt-2">
              <input
                id="message-reply"
                value={reply}
                onChange={(e) => setReply(e.target.value)}
                placeholder="Write a reply…"
                className={`${LH_INPUT} flex-1`}
              />
              <button type="submit" disabled={sending || !reply.trim()} className={LH_PRIMARY_BUTTON}>
                <span>{sending ? 'Sending…' : 'Send'}</span>
              </button>
            </form>
            {sendError && <p className="text-sm text-rose-600">{sendError}</p>}
          </div>
        </SectionCard>
      )}

      <SectionCard
        id="notifications"
        title="Notifications"
        icon={<Bell className="size-4 text-gray-500" />}
        state={notifications.status}
        error={notifications.error}
        onRetry={notifications.refetch}
        emptyTitle="Nothing to catch up on"
        emptyDescription="Absence alerts, wellbeing escalations and weekly digests appear here."
        action={
          unreadNotifications > 0 ? (
            <button
              type="button"
              onClick={handleMarkAllRead}
              className="text-xs font-bold text-gray-600 hover:text-black"
            >
              Mark all read
            </button>
          ) : undefined
        }
      >
        <DataTable
          rows={notifications.data ?? []}
          rowKey={(row) => row.id}
          state="success"
          columns={[
            {
              key: 'title',
              header: 'Notification',
              render: (r) => (
                <span className={r.is_read ? 'text-gray-500' : 'font-bold text-gray-900'}>
                  {r.title}
                </span>
              ),
            },
            { key: 'kind', header: 'Type', render: (r) => <StatusChip label={r.kind} tone="info" /> },
            {
              key: 'when',
              header: 'When',
              render: (r) => new Date(r.created_at).toLocaleString(),
            },
          ]}
        />
      </SectionCard>
    </DashPageShell>
  )
}
