/**
 * Real fetch calls against `apps/api/src/routers/notifications.py`, mounted at
 * `/api/v1/sms` (router.py:524-526).
 *
 * Note what is deliberately absent: `startThread`. POST /sms/messages/threads
 * exists (notifications.py:218) but is refused with 403 unless a school
 * relationship permits the pair, and the recipient picker it would need
 * (/sms/identity/people) rejects PARENT callers outright. Offering a parent a
 * "new conversation" button here would be offering a button that 403s, so the
 * mobile app replies within threads staff have opened and does not compose.
 */

import { apiGet, apiPost } from '@/api/client'
import type { MessageItem, NotificationItem, ThreadSummary, UnreadCount } from './types'

/** GET /sms/notifications — notifications.py:67. */
export function listNotifications(unreadOnly?: boolean): Promise<NotificationItem[]> {
  const qs = unreadOnly ? '?unread_only=true' : ''
  return apiGet<NotificationItem[]>(`/sms/notifications${qs}`)
}

/** GET /sms/notifications/unread-count — notifications.py:89. */
export function getUnreadNotificationCount(): Promise<UnreadCount> {
  return apiGet<UnreadCount>('/sms/notifications/unread-count')
}

/** POST /sms/notifications/{id}/read — notifications.py:108. */
export function markNotificationRead(notificationId: number): Promise<void> {
  return apiPost<void>(`/sms/notifications/${notificationId}/read`)
}

/** GET /sms/messages/threads — notifications.py:189. */
export function listMessageThreads(): Promise<ThreadSummary[]> {
  return apiGet<ThreadSummary[]>('/sms/messages/threads')
}

/**
 * GET /sms/messages/threads/{id} — notifications.py:202. Oldest-first, and
 * reading marks the thread read for the caller. A non-participant gets 404,
 * not 403: thread ids are small integers and 403 would confirm that a
 * conversation about someone's child exists.
 */
export function getThreadMessages(threadId: number): Promise<MessageItem[]> {
  return apiGet<MessageItem[]>(`/sms/messages/threads/${threadId}`)
}

/**
 * POST /sms/messages/threads/{id}/messages — notifications.py:260.
 * The access rule is re-checked on every reply, not only at creation, so this
 * can legitimately start returning 403 mid-year (e.g. a teacher stops
 * teaching the child). Callers must surface that, not swallow it.
 */
export function postThreadMessage(threadId: number, body: string): Promise<MessageItem> {
  return apiPost<MessageItem>(`/sms/messages/threads/${threadId}/messages`, { body })
}
