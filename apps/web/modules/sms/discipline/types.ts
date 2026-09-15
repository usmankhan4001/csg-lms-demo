/**
 * Mirrors `apps/api/src/schemas/sms_discipline.py`.
 *
 * Severity is not cosmetic here. `sms_discipline.py:111` raises a DIFFERENT
 * notification event per band: MAJOR and CRITICAL fire
 * `safeguarding.discipline_incident_serious`, which families cannot mute,
 * while MINOR and MODERATE fire `academic.discipline_incident_recorded`,
 * which they can. Choosing a severity therefore decides whether a parent is
 * interrupted, and the UI has to say so at the point of choosing.
 */

export type IncidentSeverity = 'minor' | 'moderate' | 'major' | 'critical'
export type IncidentStatus = 'open' | 'investigating' | 'resolved' | 'appealed'

/** The two bands that raise an unmutable safeguarding notification. */
export const UNMUTABLE_SEVERITIES: readonly IncidentSeverity[] = ['major', 'critical']

export const SEVERITY_ORDER: readonly IncidentSeverity[] = [
  'minor',
  'moderate',
  'major',
  'critical',
]

export const STATUS_ORDER: readonly IncidentStatus[] = [
  'open',
  'investigating',
  'resolved',
  'appealed',
]

export interface Incident {
  id: number
  org_id: number | null
  campus_id: number | null
  student_id: number
  reporter_id: number
  incident_date: string
  title: string
  description: string
  location: string | null
  severity: IncidentSeverity
  status: IncidentStatus
  action_taken: string | null
  parent_notified: boolean
  parent_notified_at: string | null
  parent_acknowledgement: boolean
  notes: string | null
  created_at: string
}

export interface IncidentCreate {
  student_id: number
  incident_date: string
  title: string
  description: string
  location?: string | null
  severity?: IncidentSeverity
  action_taken?: string | null
  notes?: string | null
}

export interface IncidentUpdate {
  title?: string
  description?: string
  location?: string | null
  severity?: IncidentSeverity
  status?: IncidentStatus
  action_taken?: string | null
  parent_notified?: boolean
  parent_acknowledgement?: boolean
  notes?: string | null
}

export interface IncidentFilters {
  student_id?: number
  severity?: IncidentSeverity
  status_filter?: IncidentStatus
}

export interface Suspension {
  id: number
  org_id: number | null
  incident_id: number
  student_id: number
  authorized_by_id: number
  start_date: string
  end_date: string
  is_in_school: boolean
  academic_work_provided: boolean
  reinstatement_date: string | null
  reinstatement_conditions: string | null
  created_at: string
}

export interface SuspensionCreate {
  incident_id: number
  student_id: number
  start_date: string
  end_date: string
  is_in_school?: boolean
  academic_work_provided?: boolean
  reinstatement_conditions?: string | null
}
