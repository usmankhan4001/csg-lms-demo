/**
 * Mirrors `apps/api/src/schemas/sms_pathways.py`.
 *
 * READ THE PROGRESS COMMENT BELOW BEFORE RENDERING ANYTHING FROM IT.
 */

export interface PathwayCourse {
  id: number
  pathway_id: number
  course_id: number
  credits: number
  is_mandatory: boolean
  semester_sequence: number
  prerequisite_course_id: number | null
}

export interface PathwayCourseCreate {
  course_id: number
  credits?: number
  is_mandatory?: boolean
  semester_sequence?: number
  prerequisite_course_id?: number | null
}

export interface CurricularPathway {
  id: number
  org_id: number | null
  name: string
  code: string
  description: string | null
  required_credits: number
  is_active: boolean
  created_at: string
  courses: PathwayCourse[]
}

export interface CurricularPathwayCreate {
  name: string
  code: string
  description?: string
  required_credits?: number
  courses?: PathwayCourseCreate[]
}

export interface EnrollPathwayPayload {
  student_id: number
  pathway_id: number
}

export interface StudentPathwayProgress {
  id: number
  org_id: number | null
  student_id: number
  pathway_id: number
  pathway_name: string
  status: string
  total_required_credits: number
  /**
   * BOTH NULLABLE, AND THEY WILL BE NULL. Credit progress is not tracked
   * anywhere in this system: `StudentPathwayEnrollment` records who enrolled
   * and when, and nothing links it to completed work.
   *
   * This previously read `earned_credits = min(required, courses * 3)` where
   * `courses` was the PATHWAY'S OWN CURRICULUM -- so every enrolled student
   * was credited with the entire syllabus, and the min() clamp reported most
   * of them at 100% of their graduation requirements on the day they enrolled.
   * A student could be told they had finished a track they had not started.
   *
   * The honest answer is null until a completed-credit record exists, and
   * `detail` carries the reason. Rendering these as a progress bar at 0%, or
   * as "0 of 30 credits", would be the same lie in a different font: it
   * asserts the student has earned nothing, when the truth is that nobody is
   * counting.
   */
  earned_credits: number | null
  progress_percentage: number | null
  detail: string | null
  enrolled_at: string
}
