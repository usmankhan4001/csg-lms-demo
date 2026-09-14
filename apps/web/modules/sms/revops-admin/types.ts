/**
 * Types for `apps/api/src/routers/sms_revops_config.py`, mounted at
 * `/api/v1/sms/revops-admin` (router.py:598-602).
 *
 * M30 is the configuration behind the admissions agents -- scoring weights,
 * nurture cadence, consent policy -- and M34 is the knowledge base they draw
 * on. Both existed only as endpoints until now, which meant the thing they
 * were built for (a school tuning its own funnel without a developer) still
 * required a developer.
 */

/** schemas/sms_revops_config.py:34 */
export type RevOpsConfigGroupKey = 'lead_scoring' | 'nurture' | 'consent_policy'

/**
 * Where a group's values came from. The backend resolves campus -> org ->
 * code default and reports which layer won, because an admin editing what
 * they believe is their campus's setting -- while actually looking at an
 * inherited org default -- is the most confusing thing this screen can do.
 */
export type RevOpsConfigSource = 'CAMPUS' | 'ORG' | 'DEFAULT'

export interface ResolvedRevOpsGroup {
  group: RevOpsConfigGroupKey
  source: RevOpsConfigSource
  /** Shape depends on `group`; narrowed by the helpers below. */
  values: Record<string, unknown>
  updated_at: string | null
}

export interface RevOpsConfigRead {
  org_id: number
  campus_id: number | null
  groups: ResolvedRevOpsGroup[]
}

/** schemas/sms_revops_config.py:64 */
export interface LeadScoringSettings {
  weight_completeness: number
  weight_responsiveness: number
  weight_grade_demand: number
  weight_budget_fit: number
  weight_timeline: number
  hot_threshold: number
  warm_threshold: number
  high_demand_grades: string[]
  moderate_demand_grades: string[]
  /**
   * Below this score an agent's decision awaits human review instead of
   * auto-advancing. 0.0 means NO GATE -- today's behaviour -- so the UI must
   * not imply a review queue is already running.
   */
  human_review_below_score: number
}

/** schemas/sms_revops_config.py:119 */
export interface NurtureStageSettings {
  stage: number
  day: number
  channel: string
  enabled: boolean
}

/** schemas/sms_revops_config.py:134 */
export interface NurtureSettings {
  stages: NurtureStageSettings[]
}

/** schemas/sms_revops_config.py:164 */
export interface ConsentPolicySettings {
  require_explicit_opt_in: boolean
  consent_tracked_channels: string[]
}

export interface RevOpsConfigUpdate {
  values: Record<string, unknown>
}

// ---------------------------------------------------------------------------
// M34 -- knowledge base
// ---------------------------------------------------------------------------

/** db/sms_revops_config.py:70 */
export type KnowledgeEntryStatus = 'DRAFT' | 'PUBLISHED' | 'ARCHIVED'

export interface KnowledgeEntryRead {
  id: number
  org_id: number
  campus_id: number | null
  title: string
  body: string
  category: string | null
  source_label: string | null
  source_url: string | null
  /**
   * Reported by the server rather than derived here, so a reviewer can filter
   * for unbacked claims instead of having to notice two empty fields. A
   * source is NEVER synthesised -- an entry saved without one stays sourceless.
   */
  is_sourceless: boolean
  status: KnowledgeEntryStatus
  owner_user_id: number | null
  created_at: string
  updated_at: string
}

export interface KnowledgeEntryWrite {
  title: string
  body: string
  campus_id?: number | null
  category?: string | null
  source_label?: string | null
  source_url?: string | null
  status?: KnowledgeEntryStatus
}

export interface KnowledgeListFilters {
  campus_id?: number
  status?: KnowledgeEntryStatus
  category?: string
  limit?: number
  offset?: number
}

export interface KnowledgeSearchFilters {
  q: string
  campus_id?: number
  include_drafts?: boolean
  limit?: number
}
