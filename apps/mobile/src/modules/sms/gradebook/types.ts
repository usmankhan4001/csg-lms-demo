/**
 * Ported verbatim from `apps/web/modules/sms/gradebook/types.ts`, mirroring
 * `apps/api/src/schemas/sms_gradebook.py`.
 */

export interface GradeInterval {
  grade: string
  min_percentage: number
  max_percentage: number
  gpa_point: number
}

export interface GradingScaleRead {
  id: number
  name: string
  description?: string | null
  intervals: GradeInterval[]
  is_default: boolean
}

export interface GradingScaleCreate {
  name: string
  description?: string | null
  intervals: GradeInterval[]
  is_default?: boolean
}

export interface AssessmentPlanRead {
  id: number
  course_id: number
  section_id?: number | null
  academic_term_id?: number | null
  assessment_name: string
  weight_percentage: number
  max_score: number
}

export interface AssessmentPlanCreate {
  course_id: number
  section_id?: number | null
  academic_term_id?: number | null
  assessment_name: string
  weight_percentage: number
  max_score?: number
}

export interface GradebookEntryInput {
  student_id: number
  raw_score: number
  remarks?: string | null
}

export interface BatchGradebookEntryRequest {
  assessment_plan_id: number
  entries: GradebookEntryInput[]
  graded_by?: number | null
}

export interface GradebookEntryRead {
  id: number
  student_id: number
  assessment_plan_id: number
  raw_score: number
  max_score: number
  weighted_score?: number | null
  letter_grade?: string | null
  gpa_point?: number | null
  remarks?: string | null
  graded_by?: number | null
  graded_at: string
}

export interface CourseGradeSummary {
  course_id: number
  course_name?: string | null
  credits: number
  total_raw_percentage: number
  total_weighted_percentage: number
  letter_grade: string
  gpa_point: number
  assessment_breakdown: Record<string, unknown>[]
}

export interface StudentTermReportCardResponse {
  student_id: number
  section_id: number
  academic_term_id: number
  total_credits: number
  cumulative_gpa: number
  overall_letter_grade: string
  remarks?: string | null
  courses: CourseGradeSummary[]
  generated_at: string
}
