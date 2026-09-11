/**
 * Real fetch calls against `apps/api/src/routers/sms_gradebook.py`
 * (mounted at `/api/v1/sms/gradebook`). Ported from
 * `apps/web/modules/sms/gradebook/api.ts`.
 */

import { apiGet, apiPost, toQueryString } from '@/api/client'
import type {
  AssessmentPlanCreate,
  AssessmentPlanRead,
  BatchGradebookEntryRequest,
  GradebookEntryRead,
  GradingScaleCreate,
  GradingScaleRead,
  StudentTermReportCardResponse,
} from './types'

export function listGradingScales(): Promise<GradingScaleRead[]> {
  return apiGet<GradingScaleRead[]>('/sms/gradebook/scales')
}

export function createGradingScale(payload: GradingScaleCreate): Promise<GradingScaleRead> {
  return apiPost<GradingScaleRead>('/sms/gradebook/scales', payload)
}

export function listAssessmentPlans(params: { courseId?: number; academicTermId?: number } = {}): Promise<AssessmentPlanRead[]> {
  const qs = toQueryString({ course_id: params.courseId, academic_term_id: params.academicTermId })
  return apiGet<AssessmentPlanRead[]>(`/sms/gradebook/plans${qs}`)
}

export function createAssessmentPlan(payload: AssessmentPlanCreate): Promise<AssessmentPlanRead> {
  return apiPost<AssessmentPlanRead>('/sms/gradebook/plans', payload)
}

export function batchEnterGrades(payload: BatchGradebookEntryRequest): Promise<GradebookEntryRead[]> {
  return apiPost<GradebookEntryRead[]>('/sms/gradebook/entries/batch', payload)
}

export function getStudentReportCard(studentId: number, sectionId: number, academicTermId: number): Promise<StudentTermReportCardResponse> {
  const qs = toQueryString({ section_id: sectionId, academic_term_id: academicTermId })
  return apiGet<StudentTermReportCardResponse>(`/sms/gradebook/report-card/student/${studentId}${qs}`)
}
