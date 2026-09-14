/**
 * Real fetch calls against `apps/api/src/routers/notifications.py`
 * (mounted at `/api/v1/sms` -- see `src/router.py`'s include_router).
 *
 * There is deliberately no recipient parameter on any notification call:
 * the backend resolves the caller and only ever serves their own.
 */

import { apiGet, apiPost } from '@/lib/api/api-client'

export interface NotificationRead {
  id: number
  kind: string
  title: string
  body: string
  related_kind: string | null
  related_id: number | null
  is_read: boolean
  created_at: string
}

export interface ThreadSummary {
  id: number
  subject: string
  about_student_id: number | null
  last_message_at: string
  message_count: number
  unread_count: number
}

export interface MessageRead {
  id: number
  sender_user_id: number
  body: string
  created_at: string
}

export function listNotifications(unreadOnly = false): Promise<NotificationRead[]> {
  return apiGet<NotificationRead[]>(`/sms/notifications${unreadOnly ? '?unread_only=true' : ''}`)
}

export function markNotificationRead(id: number): Promise<NotificationRead> {
  return apiPost<NotificationRead>(`/sms/notifications/${id}/read`)
}

export function markAllNotificationsRead(): Promise<{ unread: number }> {
  return apiPost<{ unread: number }>('/sms/notifications/read-all')
}

export function listThreads(): Promise<ThreadSummary[]> {
  return apiGet<ThreadSummary[]>('/sms/messages/threads')
}

export function readThread(threadId: number): Promise<MessageRead[]> {
  return apiGet<MessageRead[]>(`/sms/messages/threads/${threadId}`)
}

export function postMessage(threadId: number, body: string): Promise<MessageRead> {
  return apiPost<MessageRead>(`/sms/messages/threads/${threadId}/messages`, { body })
}

export interface StartThreadPayload {
  recipient_user_id: number
  subject: string
  body: string
  about_student_id?: number | null
}

export function startThread(payload: StartThreadPayload): Promise<ThreadSummary> {
  return apiPost<ThreadSummary>('/sms/messages/threads', payload)
}
