/**
 * Mirrors `apps/api/src/schemas/sms_counseling.py`.
 *
 * CONFIDENTIALITY: `CounselingSessionRead` is the PSYCHOLOGIST-only full
 * record and carries clinical `notes` plus `follow_up_plan`.
 * `ParentVisibleSessionSummary` is a DIFFERENT shape with neither of those
 * fields -- it exists so a guardian can be shown what was agreed without
 * being shown the clinical record. They are deliberately not one type with
 * optional fields: a single type invites a component to render `notes` on a
 * parent screen because the field merely happened to be populated.
 */

export interface ActivityLogRead {
  id: number
  student_id: number
  /** Keycloak `sub` STRING, not an integer user id -- see api.ts. */
  psychologist_id: string
  signal_type: string
  description: string
  severity: string
  recorded_at: string
}

export interface ActivityLogCreate {
  student_id: number
  signal_type: string
  description: string
  severity?: string
}

/** PSYCHOLOGIST-only full clinical record. Never render on a parent surface. */
export interface CounselingSessionRead {
  id: number
  student_id: number
  psychologist_id: string
  session_date: string
  duration_minutes: number
  notes: string
  follow_up_plan: string | null
  share_summary_with_parent: boolean
  parent_visible_summary: string | null
  created_at: string
  updated_at: string
}

export interface CounselingSessionCreate {
  student_id: number
  session_date: string
  duration_minutes: number
  notes: string
  follow_up_plan?: string | null
  share_summary_with_parent?: boolean
  parent_visible_summary?: string | null
}

export interface CounselingSessionUpdate {
  notes?: string | null
  follow_up_plan?: string | null
  share_summary_with_parent?: boolean | null
  parent_visible_summary?: string | null
}

/** PARENT/STUDENT view. No clinical notes, no follow-up plan, by design. */
export interface ParentVisibleSessionSummary {
  id: number
  student_id: number
  session_date: string
  parent_visible_summary: string
  created_at: string
}

export interface CareerGuidancePathway {
  pathway: string
  reasoning: string
}

export interface CareerGuidancePlanRead {
  id: number
  student_id: number
  generated_by: string | null
  suggested_pathways: CareerGuidancePathway[]
  reasoning: string
  next_steps: string[]
  generated_at: string
}

export interface CareerGuidanceGenerateRequest {
  student_id: number
  interests?: string[] | null
  extra_context?: string | null
}
