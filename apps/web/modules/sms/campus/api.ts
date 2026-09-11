/**
 * Real fetch calls against `apps/api/src/routers/sms_campus.py` (mounted at
 * `/api/v1/sms/campuses` -- prefix `/sms` + router's own `/campuses`
 * prefix, see `src/router.py` / `src/routers/sms_campus.py`).
 */

import { apiGet, toQueryString } from '@/lib/api/api-client'
import type { AcademicYearRead, CampusRead, ClassSectionRead, StudentEnrollmentRead } from './types'

export function listCampuses(params: { orgId?: number; isActive?: boolean } = {}): Promise<CampusRead[]> {
  const qs = toQueryString({ org_id: params.orgId, is_active: params.isActive })
  return apiGet<CampusRead[]>(`/sms/campuses/${qs}`)
}

export function getCampus(campusId: number): Promise<CampusRead> {
  return apiGet<CampusRead>(`/sms/campuses/${campusId}`)
}

export function listAcademicYears(campusId: number, isActive?: boolean): Promise<AcademicYearRead[]> {
  return apiGet<AcademicYearRead[]>(`/sms/campuses/${campusId}/academic-years${toQueryString({ is_active: isActive })}`)
}

export function listClassSections(campusId: number, params: { gradeLevel?: string; isActive?: boolean } = {}): Promise<ClassSectionRead[]> {
  const qs = toQueryString({ grade_level: params.gradeLevel, is_active: params.isActive })
  return apiGet<ClassSectionRead[]>(`/sms/campuses/${campusId}/sections${qs}`)
}

export function listSectionEnrollments(sectionId: number, status?: string): Promise<StudentEnrollmentRead[]> {
  return apiGet<StudentEnrollmentRead[]>(`/sms/campuses/sections/${sectionId}/enrollments${toQueryString({ status })}`)
}
