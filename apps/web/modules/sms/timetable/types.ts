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
