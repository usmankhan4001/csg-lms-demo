/**
 * Types mirroring `apps/api/src/schemas/sms_attendance.py` response/request
 * shapes exactly (field names, optionality) so `api.ts` responses can be used
 * without any client-side re-shaping.
 */

export type AttendanceStatus = 'PRESENT' | 'ABSENT' | 'LATE' | 'EXCUSED'
export type LeaveRequestStatus = 'PENDING' | 'APPROVED' | 'REJECTED'

export interface RollCallStudentEntry {
  student_id: number
  status: AttendanceStatus
  remarks?: string | null
}

export interface BatchRollCallRequest {
  section_id: number
  date: string // ISO date (YYYY-MM-DD)
  entries: RollCallStudentEntry[]
  marked_by?: number | null
  /**
   * Omitted/null records a WHOLE-DAY register (how a primary school works).
   * Supplying it records that one period only, so a secondary school can take
   * six registers a day without each overwriting the last.
   */
  period_id?: number | null
  /** Why this register was changed. Optional by design -- see the backend schema. */
  reason?: string | null
}

export interface StudentAttendanceRead {
  id: number
  student_id: number
  section_id: number
  date: string
  /** Null for a whole-day register. */
  period_id?: number | null
  status: AttendanceStatus
  marked_by?: number | null
  remarks?: string | null
  timestamp: string
}

export interface BatchRollCallResponse {
  success: boolean
  section_id: number
  date: string
  total_submitted: number
  total_recorded: number
  records: StudentAttendanceRead[]
}

export interface MonthlyAttendanceStats {
  total_days: number
  present_days: number
  absent_days: number
  late_days: number
  excused_days: number
  /**
   * NULL when no register has been taken in the period -- NOT 0.
   * `sms_attendance.py` returns `Optional[float]` precisely so "nobody marked
   * a register" stays distinguishable from "attended nothing". Render
   * "Not recorded", never "0%".
   */
  attendance_percentage: number | null
}

export interface MonthlyStudentAttendanceSheet {
  student_id: number
  section_id?: number | null
  year: number
  month: number
  stats: MonthlyAttendanceStats
  daily_records: StudentAttendanceRead[]
}

export interface LeaveRequestCreate {
  student_id: number
  start_date: string
  end_date: string
  reason?: string | null
}

export interface LeaveRequestUpdateStatus {
  status: LeaveRequestStatus
  approved_by?: number | null
}

export interface LeaveRequestRead {
  id: number
  student_id: number
  start_date: string
  end_date: string
  reason?: string | null
  status: LeaveRequestStatus
  approved_by?: number | null
  created_at: string
}

// ── Attendance trail (append-only) ──

export type AttendanceChangeAction = 'marked' | 'corrected'

export interface AttendanceChangeEventRead {
  id: number
  attendance_id: number
  student_id: number
  section_id: number
  date: string
  period_id?: number | null
  action: AttendanceChangeAction
  /** None on MARKED: there was no previous status. Distinct from PRESENT. */
  previous_status?: AttendanceStatus | null
  new_status: AttendanceStatus
  changed_by_user_id?: number | null
  reason?: string | null
  created_at: string
}

// ── Absence excuses ──

export type ExcuseStatus = 'PENDING' | 'APPROVED' | 'REJECTED'

export interface AbsenceExcuseCreate {
  student_id: number
  section_id: number
  date: string
  reason: string
}

export interface AbsenceExcuseRead {
  id: number
  student_id: number
  section_id: number
  date: string
  reason: string
  submitted_by_user_id?: number | null
  status: ExcuseStatus
  reviewed_by_user_id?: number | null
  review_note?: string | null
  reviewed_at?: string | null
  created_at: string
}

export interface AbsenceExcuseReview {
  status: ExcuseStatus
  review_note?: string | null
}

export interface AbsenceExcuseReviewResponse {
  excuse: AbsenceExcuseRead
  /** How many registers actually changed. 0 is a legitimate outcome. */
  records_converted: number
}

// ── Pastoral concerns ──

export type PastoralConcernStatus = 'OPEN' | 'IN_PROGRESS' | 'RESOLVED'

export interface PastoralConcernRead {
  id: number
  student_id: number
  section_id: number
  trigger: string
  detail?: string | null
  /** None where the trigger has no natural magnitude -- never 0. */
  magnitude?: number | null
  status: PastoralConcernStatus
  resolved_by_user_id?: number | null
  resolution_note?: string | null
  resolved_at?: string | null
  created_at: string
}

export interface PastoralConcernUpdate {
  status: PastoralConcernStatus
  resolution_note?: string | null
}

export interface PastoralInterventionCreate {
  action: string
  note?: string | null
  outcome?: string | null
}

export interface PastoralInterventionRead {
  id: number
  concern_id: number
  action: string
  note?: string | null
  outcome?: string | null
  acted_by_user_id?: number | null
  created_at: string
}

// ── Bulk marking ──

export interface BulkMarkRangeRequest {
  section_id: number
  start_date: string
  end_date: string
  status: AttendanceStatus
  student_ids?: number[] | null
  reason?: string | null
  /** False by default: an existing differing record is reported, never rewritten. */
  overwrite_existing?: boolean
}

export interface BulkMarkSkipped {
  student_id: number
  date: string
  existing_status: AttendanceStatus
}

export interface BulkMarkRangeResponse {
  section_id: number
  start_date: string
  end_date: string
  dates_covered: number
  records_created: number
  records_updated: number
  skipped: BulkMarkSkipped[]
}
