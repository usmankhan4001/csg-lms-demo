/**
 * Ported verbatim from `apps/web/modules/sms/attendance/types.ts`, which
 * mirrors `apps/api/src/schemas/sms_attendance.py` field-for-field. Do not
 * re-shape these on the client — the whole point is both clients speak the
 * same contract against the same backend.
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
}

export interface StudentAttendanceRead {
  id: number
  student_id: number
  section_id: number
  date: string
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
  attendance_percentage: number
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
