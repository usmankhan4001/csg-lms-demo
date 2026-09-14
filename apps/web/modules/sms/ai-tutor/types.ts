/** Mirrors `apps/api/src/routers/ai_oversight.py`. */

export type TranscriptOutcome =
  | 'answered'
  | 'blocked_safety'
  | 'blocked_offtopic'
  | 'blocked_disabled'
  | 'blocked_rate_limit'
  | 'blocked_session_limit'

export interface TranscriptRead {
  id: number
  student_id: number
  section_id: number | null
  course_id: string | null
  prompt: string
  outcome: TranscriptOutcome
  detail: string | null
  created_at: string
}

export interface AccessBlockRead {
  id: number
  student_id: number | null
  section_id: number | null
  blocked_by_user_id: number
  reason: string | null
  is_active: boolean
  created_at: string
  lifted_by_user_id: number | null
  lifted_at: string | null
}

export interface SafetyIncidentRead {
  id: number
  student_id: string
  severity: string
  trigger_category: string
  counselor_notified: boolean
  created_at: string
}

export interface CreateBlockPayload {
  student_id?: number
  section_id?: number
  reason?: string
}
