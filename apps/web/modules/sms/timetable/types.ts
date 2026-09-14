/**
 * Types mirroring `apps/api/src/schemas/sms_timetable.py`.
 */

export type DayOfWeek = 'MONDAY' | 'TUESDAY' | 'WEDNESDAY' | 'THURSDAY' | 'FRIDAY' | 'SATURDAY' | 'SUNDAY'
export type ClashType = 'TEACHER_DOUBLE_BOOKED' | 'ROOM_DOUBLE_BOOKED' | 'SECTION_DOUBLE_BOOKED'

export interface ClassPeriodRead {
  id: number
  campus_id?: number | null
  period_number: number
  start_time: string
  end_time: string
  name?: string | null
}

export interface ClassPeriodCreate {
  campus_id?: number | null
  period_number: number
  start_time: string
  end_time: string
  name?: string | null
}

export interface TimetableScheduleCreate {
  section_id: number
  course_id: number
  teacher_id: number
  day_of_week: DayOfWeek | string
  period_id: number
  room_number?: string | null
  academic_term_id?: number | null
}

export interface TimetableScheduleRead extends TimetableScheduleCreate {
  id: number
}

export interface TimetableSlotDetail {
  id: number
  section_id: number
  course_id: number
  teacher_id: number
  day_of_week: string
  period_id: number
  period_number?: number | null
  start_time?: string | null
  end_time?: string | null
  room_number?: string | null
  academic_term_id?: number | null
}

export interface ClashDetail {
  clash_type: ClashType
  description: string
  conflicting_schedule_id: number
  day_of_week: string
  period_id: number
  academic_term_id?: number | null
  teacher_id?: number | null
  room_number?: string | null
  section_id?: number | null
}

export interface ClashCheckRequest {
  section_id: number
  course_id: number
  teacher_id: number
  day_of_week: DayOfWeek | string
  period_id: number
  room_number?: string | null
  academic_term_id?: number | null
  exclude_schedule_id?: number | null
}

export interface ClashCheckResponse {
  has_clash: boolean
  clashes: ClashDetail[]
  message: string
}

export interface StudentTimetableResponse {
  student_id?: number | null
  section_id?: number | null
  academic_term_id?: number | null
  slots: TimetableSlotDetail[]
}

export interface TeacherTimetableResponse {
  teacher_id: number
  academic_term_id?: number | null
  slots: TimetableSlotDetail[]
}

/** Mirrors `TimetableSubstitutionCreate` in apps/api/src/schemas/sms_timetable.py. */
export interface TimetableSubstitutionCreate {
  schedule_id: number
  /** ISO date 'YYYY-MM-DD' the substitute covers. */
  substitution_date: string
  /** Learnhouse user id of the covering teacher (not StaffProfile.id). */
  substitute_teacher_id: number
  reason?: string | null
}

export interface TimetableSubstitutionRead {
  id: number
  schedule_id: number
  substitution_date: string
  original_teacher_id: number
  substitute_teacher_id: number
  reason?: string | null
  created_by?: number | null
  is_active: boolean
}

/**
 * Lesson logs -- what was ACTUALLY taught, as opposed to an AI lesson PLAN
 * (`sms_lesson_plan`), which is written beforehand and may never have been
 * followed. Mirrors `LessonLogCreate`/`LessonLogRead` in
 * apps/api/src/schemas/sms_timetable.py.
 */
export interface LessonLogCreate {
  schedule_id: number
  /** ISO date 'YYYY-MM-DD'. */
  lesson_date: string
  topic_covered: string
  homework_set?: string | null
  notes_for_next_teacher?: string | null
  lesson_plan_id?: number | null
}

export interface LessonLogRead {
  id: number
  schedule_id: number
  section_id: number
  lesson_date: string
  /**
   * Set server-side from the authenticated caller. There is deliberately NO
   * corresponding field on LessonLogCreate: a lesson must not be attributable
   * to a colleague who was not there.
   */
  taught_by_user_id?: number | null
  topic_covered: string
  homework_set?: string | null
  notes_for_next_teacher?: string | null
  lesson_plan_id?: number | null
  recorded_by_user_id?: number | null
}

/**
 * Conflicts that ALREADY EXIST, as opposed to ClashCheckResponse which answers
 * "would this one PROPOSED slot conflict?".
 */
export interface TimetableConflictScanResponse {
  /** 0 scanned means nothing was checked -- a different answer from 0 conflicts. */
  scanned_slots: number
  conflicts: ClashDetail[]
  message: string
}

/** Assisted generation. Mirrors the schemas of the same names. */
export interface GenerationRequirement {
  course_id: number
  teacher_id: number
  periods_per_week: number
  room_number?: string | null
  preferred_days?: DayOfWeek[] | null
}

export interface GenerationRequest {
  section_id: number
  academic_term_id?: number | null
  requirements: GenerationRequirement[]
  days?: DayOfWeek[] | null
  period_ids?: number[] | null
  /** Defaults to true server-side. Nothing is written unless explicitly false. */
  dry_run?: boolean
}

export interface PlacedSlot {
  course_id: number
  teacher_id: number
  day_of_week: string
  period_id: number
  room_number?: string | null
  /** Null on a dry run -- nothing was written. */
  schedule_id?: number | null
}

/** A period the generator could NOT place, and why. Never silently dropped. */
export interface UnplacedSlot {
  course_id: number
  teacher_id: number
  occurrence: number
  reason: string
}

export interface GenerationResponse {
  section_id: number
  academic_term_id?: number | null
  dry_run: boolean
  requested_periods: number
  placed: PlacedSlot[]
  unplaced: UnplacedSlot[]
  message: string
}
