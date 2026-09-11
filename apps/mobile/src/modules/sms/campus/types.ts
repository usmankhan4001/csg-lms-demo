/**
 * Ported verbatim from `apps/web/modules/sms/campus/types.ts`, mirroring
 * `apps/api/src/db/sms_campus.py` Read schemas. Used here to resolve a
 * teacher's section roster for the Attendance Check-in and Gradebook
 * screens (`GET /sms/campuses/sections/{id}/enrollments`).
 */

export interface CampusRead {
  id: number
  org_id: number
  name: string
  code: string
  address?: string | null
  timezone: string
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface AcademicYearRead {
  id: number
  campus_id: number
  name: string
  start_date?: string | null
  end_date?: string | null
  is_active: boolean
  created_at: string
}

export interface ClassSectionRead {
  id: number
  campus_id: number
  grade_level: string
  section_name: string
  room_number?: string | null
  class_teacher_id?: number | null
  max_capacity: number
  is_active: boolean
}

export interface StudentEnrollmentRead {
  id: number
  student_id: number
  section_id: number
  academic_year_id: number
  roll_number?: string | null
  status: string
  enrolled_at: string
}
