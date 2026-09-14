/** Mirrors `apps/api/src/schemas/sms_exam.py`. */

export type ExamStatus =
  | 'SCHEDULED'
  | 'IN_PROGRESS'
  | 'COMPLETED'
  | 'RESULTS_POSTED'
  | 'CANCELLED'

export type ExamAttendanceStatus = 'PRESENT' | 'ABSENT' | 'EXEMPT' | 'MALPRACTICE'

export interface ExamRead {
  id: number
  campus_id: number
  academic_term_id: number
  course_id: number
  title: string
  exam_type: string | null
  exam_date: string
  start_time: string | null
  duration_minutes: number
  total_marks: number
  pass_marks: number
  assessment_plan_id: number | null
  status: ExamStatus
  instructions: string | null
  created_by: number | null
  created_at: string
}

export interface ExamCreatePayload {
  campus_id: number
  academic_term_id: number
  course_id: number
  title: string
  exam_type?: string | null
  exam_date: string
  start_time?: string | null
  duration_minutes?: number
  total_marks?: number
  pass_marks?: number
  assessment_plan_id?: number | null
  instructions?: string | null
}

export interface ExamResultRead {
  id: number
  exam_id: number
  student_id: number
  /** null means NOT MARKED — never render this as 0. */
  marks_obtained: number | null
  attendance_status: ExamAttendanceStatus
  percentage: number | null
  passed: boolean | null
  remarks: string | null
  marked_by: number | null
  marked_at: string | null
  posted_to_gradebook_at: string | null
}

export interface ExamResultEntryInput {
  student_id: number
  marks_obtained?: number | null
  attendance_status?: ExamAttendanceStatus
  remarks?: string | null
}

/**
 * Cohort statistics. `average_marks`/`highest_marks`/`lowest_marks` are null
 * when nobody has been marked — there is no average of nothing, and this
 * codebase has twice had to remove endpoints that defaulted missing academic
 * figures to a plausible number.
 */
export interface ExamResultSummary {
  exam_id: number
  total_students: number
  marked: number
  not_yet_marked: number
  absent: number
  average_marks: number | null
  highest_marks: number | null
  lowest_marks: number | null
  pass_count: number
  fail_count: number
}

export interface PostResultsResponse {
  exam_id: number
  entries_written: number
  entries_skipped: number
  already_posted: boolean
  assessment_plan_id: number
  message: string
}

// ── Seating and resits ─────────────────────────────────────────────────────

export interface SeatAllocationInput {
  student_id: number
  seat_label: string
  notes?: string | null
}

export interface SeatAllocationRead {
  id: number
  schedule_id: number
  student_id: number
  seat_label: string
  notes: string | null
  allocated_by_user_id: number | null
  allocated_at: string
}

export interface AllocateSeatsResponse {
  schedule_id: number
  allocated: SeatAllocationRead[]
  /**
   * Rows that were NOT allocated, each with its reason. Never empty silently:
   * a clash is reported so a human can resolve it, because an auto-reseated
   * candidate finds someone in their chair on exam day.
   */
  skipped: string[]
}

export type ResitReason =
  | 'ABSENT'
  | 'ILLNESS'
  | 'TIMETABLE_CLASH'
  | 'FAILED'
  | 'MALPRACTICE'
  | 'OTHER'

export type ResitStatus = 'APPROVED' | 'SCHEDULED' | 'COMPLETED' | 'CANCELLED'

export interface ResitRead {
  id: number
  original_exam_id: number
  /** Null until the resit is actually scheduled — approval comes first. */
  resit_exam_id: number | null
  student_id: number
  reason: ResitReason
  reason_detail: string | null
  status: ResitStatus
  approved_by_user_id: number | null
  approved_at: string
}

export interface ResitCandidate {
  student_id: number
  /**
   * Null means the record shows a gap to CHASE rather than grounds for a
   * resit — e.g. sat the exam but has no mark recorded yet. An unmarked paper
   * is not a failure, and must never be rendered as one.
   */
  suggested_reason: ResitReason | null
  /** What the record actually shows. Never an inference. */
  evidence: string
}
