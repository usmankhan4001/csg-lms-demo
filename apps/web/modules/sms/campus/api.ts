/**
 * Real fetch calls against `apps/api/src/routers/sms_campus.py` (mounted at
 * `/api/v1/sms/campuses` -- prefix `/sms` + router's own `/campuses`
 * prefix, see `src/router.py` / `src/routers/sms_campus.py`).
 */

import { apiGet, apiPost, toQueryString } from '@/lib/api/api-client'
import type { AcademicTermRead, AcademicYearRead, CampusRead, ClassSectionRead, StudentEnrollmentRead } from './types'

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

// Note: mounted at bare `/sms/academic-terms` (src/routers/sms_identity.py),
// NOT under `/sms/campuses` like the rest of this file -- it joins across
// Campus -> AcademicYear -> AcademicTerm itself rather than nesting under a
// specific campus/year path.
export function listAcademicTerms(params: { campusId?: number; academicYearId?: number } = {}): Promise<AcademicTermRead[]> {
  const qs = toQueryString({ campus_id: params.campusId, academic_year_id: params.academicYearId })
  return apiGet<AcademicTermRead[]>(`/sms/academic-terms${qs}`)
}

export function listClassSections(campusId: number, params: { gradeLevel?: string; isActive?: boolean } = {}): Promise<ClassSectionRead[]> {
  const qs = toQueryString({ grade_level: params.gradeLevel, is_active: params.isActive })
  return apiGet<ClassSectionRead[]>(`/sms/campuses/${campusId}/sections${qs}`)
}

export function listSectionEnrollments(sectionId: number, status?: string): Promise<StudentEnrollmentRead[]> {
  return apiGet<StudentEnrollmentRead[]>(`/sms/campuses/sections/${sectionId}/enrollments${toQueryString({ status })}`)
}

/* ------------------------------------------------------------------ writes
 * Until these existed the school could only be READ, never set up: the
 * backend has had create endpoints all along, but this module exposed none
 * of them, so a campus could only be made by calling the API by hand. No
 * campus means no sections, no enrolments, and nothing for attendance,
 * gradebook or fees to point at -- the whole system was unusable from the
 * UI for want of these few calls.
 */

export interface CampusCreatePayload {
  name: string
  code: string
  org_id: number
  address?: string | null
  timezone?: string
  is_active?: boolean
}

export function createCampus(payload: CampusCreatePayload): Promise<CampusRead> {
  return apiPost<CampusRead>('/sms/campuses/', payload)
}

export interface AcademicYearCreatePayload {
  name: string
  start_date?: string | null
  end_date?: string | null
  is_active?: boolean
}

export function createAcademicYear(campusId: number, payload: AcademicYearCreatePayload): Promise<AcademicYearRead> {
  return apiPost<AcademicYearRead>(`/sms/campuses/${campusId}/academic-years`, payload)
}

export interface AcademicTermCreatePayload {
  name: string
  term_code?: string | null
  weight_percentage?: number
  start_date?: string | null
  end_date?: string | null
}

export function createAcademicTerm(academicYearId: number, payload: AcademicTermCreatePayload): Promise<AcademicTermRead> {
  return apiPost<AcademicTermRead>(`/sms/campuses/academic-years/${academicYearId}/terms`, payload)
}

export interface ClassSectionCreatePayload {
  grade_level: string
  section_name: string
  room_number?: string | null
  max_capacity?: number
  class_teacher_id?: number | null
  is_active?: boolean
}

export function createClassSection(campusId: number, payload: ClassSectionCreatePayload): Promise<ClassSectionRead> {
  return apiPost<ClassSectionRead>(`/sms/campuses/${campusId}/sections`, payload)
}

export interface EnrollStudentPayload {
  student_id: number
  section_id: number
  academic_year_id: number
  roll_number?: string | null
  status?: string
}

export function enrollStudent(payload: EnrollStudentPayload): Promise<StudentEnrollmentRead> {
  return apiPost<StudentEnrollmentRead>('/sms/campuses/enrollments', payload)
}

/** A person holding a school role, with their name attached — the picker
 * source for enrolment. `GET /sms/identity/roles` returns bare user_ids,
 * which is why screens built on it render "User #42". */
export interface SchoolPerson {
  user_id: number
  name: string | null
  email: string | null
  role: string
  campus_id: number | null
}

export function listSchoolPeople(role: string, campusId?: number): Promise<SchoolPerson[]> {
  return apiGet<SchoolPerson[]>(`/sms/identity/people${toQueryString({ role, campus_id: campusId })}`)
}
