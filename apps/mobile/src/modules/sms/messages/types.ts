/**
 * Mirrors `NotificationRead` / `ThreadSummary` / `MessageRead` in
 * `apps/api/src/routers/notifications.py` field-for-field.
 */

export interface NotificationItem {
  id: number
  kind: string
  title: string
  body: string
  related_kind?: string | null
  related_id?: number | null
  is_read: boolean
  created_at: string
}

export interface UnreadCount {
  unread: number
}

export interface ThreadSummary {
  id: number
  subject: string
  about_student_id?: number | null
  last_message_at: string
  message_count: number
  unread_count: number
}

export interface MessageItem {
  id: number
  sender_user_id: number
  body: string
  created_at: string
}
