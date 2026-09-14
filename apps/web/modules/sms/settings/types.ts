/**
 * Mirrors `apps/api/src/schemas/sms_settings.py`.
 *
 * `source` is the field that matters in the UI: an admin editing a campus
 * needs to know whether they are changing an existing override or creating
 * one, and whether what they see is inherited from the organisation.
 */

export type SettingsGroupKey =
  | 'school_profile'
  | 'academic_calendar'
  | 'grading_policy'
  | 'attendance_policy'
  | 'fee_policy'
  | 'report_cards'
  | 'notifications'
  | 'ai_tutor_policy'

/** CAMPUS = this campus overrides; ORG = inherited; DEFAULT = nothing saved. */
export type SettingsSource = 'CAMPUS' | 'ORG' | 'DEFAULT'

export interface ResolvedSettingsGroup {
  group: SettingsGroupKey
  source: SettingsSource
  values: Record<string, any>
  editable_in_ui: boolean
  updated_at: string | null
}

export interface SchoolSettingsRead {
  org_id: number
  campus_id: number | null
  groups: ResolvedSettingsGroup[]
}

export interface SchoolProfileValues {
  legal_name: string | null
  logo_url: string | null
  principal_name: string | null
  contact_email: string | null
  contact_phone: string | null
  address: string | null
}

export interface GradeInterval {
  grade: string
  min_percentage: number
  max_percentage: number
  gpa_point: number
}

export interface GradingPolicyValues {
  intervals: GradeInterval[]
  pass_mark: number
}

export interface FeePolicyValues {
  late_fee_percent_per_period: number
  late_fee_grace_days: number
  late_fee_period_days: number
  late_fee_max_percent: number
}

/** Human labels. Kept beside the types so a new group can't ship unlabelled. */
export const GROUP_LABELS: Record<SettingsGroupKey, string> = {
  school_profile: 'School profile',
  academic_calendar: 'Academic calendar',
  grading_policy: 'Grading policy',
  attendance_policy: 'Attendance policy',
  fee_policy: 'Fee policy',
  report_cards: 'Report cards',
  notifications: 'Notifications',
  ai_tutor_policy: 'AI Tutor policy',
}

export const GROUP_DESCRIPTIONS: Record<SettingsGroupKey, string> = {
  school_profile: 'Name, principal and contact details used on documents the school issues.',
  academic_calendar: 'Working week, period structure and term rollover.',
  grading_policy: 'The scale every percentage becomes a letter grade and GPA point by.',
  attendance_policy: 'When a student counts as late, and when a guardian is alerted.',
  fee_policy: 'Late-fee rate, grace period and ceiling.',
  report_cards: 'Signatories and whether report cards send automatically.',
  notifications: 'Which channels carry which alerts.',
  ai_tutor_policy: 'Subjects the tutor covers, hint limits and message caps.',
}
