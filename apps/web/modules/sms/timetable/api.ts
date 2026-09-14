/**
 * Real fetch calls against `apps/api/src/routers/sms_timetable.py`
 * (mounted at `/api/v1/sms/timetable`).
 */

import { apiGet, apiPost, toQueryString } from '@/lib/api/api-client'
import type {
  ClashCheckRequest,
  ClashCheckResponse,
  ClassPeriodCreate,
  ClassPeriodRead,
  DayOfWeek,
  StudentTimetableResponse,
  TeacherTimetableResponse,
  TimetableScheduleCreate,
  TimetableScheduleRead,
  TimetableSlotDetail,
  TimetableSubstitutionCreate,
  TimetableSubstitutionRead,
  GenerationRequest,
  GenerationResponse,
  LessonLogCreate,
  LessonLogRead,
  TimetableConflictScanResponse,
} from './types'

export function listClassPeriods(campusId?: number): Promise<ClassPeriodRead[]> {
  return apiGet<ClassPeriodRead[]>(`/sms/timetable/periods${toQueryString({ campus_id: campusId })}`)
}

export function createClassPeriod(payload: ClassPeriodCreate): Promise<ClassPeriodRead> {
  return apiPost<ClassPeriodRead>('/sms/timetable/periods', payload)
}

export function checkTimetableClashes(payload: ClashCheckRequest): Promise<ClashCheckResponse> {
  return apiPost<ClashCheckResponse>('/sms/timetable/check-clashes', payload)
}

export function createTimetableSchedule(payload: TimetableScheduleCreate, enforceNoClash = true): Promise<TimetableScheduleRead> {
  return apiPost<TimetableScheduleRead>(`/sms/timetable/schedules${toQueryString({ enforce_no_clash: enforceNoClash })}`, payload)
}

export function listTimetableSchedules(params: {
  sectionId?: number
  teacherId?: number
  academicTermId?: number
  dayOfWeek?: DayOfWeek
} = {}): Promise<TimetableSlotDetail[]> {
  const qs = toQueryString({
    section_id: params.sectionId,
    teacher_id: params.teacherId,
    academic_term_id: params.academicTermId,
    day_of_week: params.dayOfWeek,
  })
  return apiGet<TimetableSlotDetail[]>(`/sms/timetable/schedules${qs}`)
}

export function getStudentTimetable(studentId: number, sectionId: number, academicTermId?: number): Promise<StudentTimetableResponse> {
  const qs = toQueryString({ section_id: sectionId, academic_term_id: academicTermId })
  return apiGet<StudentTimetableResponse>(`/sms/timetable/student/${studentId}${qs}`)
}

export function getTeacherTimetable(teacherId: number, academicTermId?: number): Promise<TeacherTimetableResponse> {
  const qs = toQueryString({ academic_term_id: academicTermId })
  return apiGet<TeacherTimetableResponse>(`/sms/timetable/teacher/${teacherId}${qs}`)
}

/**
 * Teacher substitutions. A substitution is DATE-SCOPED against one recurring
 * slot: it never mutates the schedule's own `teacher_id`, so the original
 * teacher is always restorable and future weeks are untouched.
 */
export function listSubstitutions(params: {
  scheduleId?: number
  substituteTeacherId?: number
  substitutionDate?: string
  includeCancelled?: boolean
} = {}): Promise<TimetableSubstitutionRead[]> {
  const qs = toQueryString({
    schedule_id: params.scheduleId,
    substitute_teacher_id: params.substituteTeacherId,
    substitution_date: params.substitutionDate,
    include_cancelled: params.includeCancelled,
  })
  return apiGet<TimetableSubstitutionRead[]>(`/sms/timetable/substitutions${qs}`)
}

export function createSubstitution(payload: TimetableSubstitutionCreate): Promise<TimetableSubstitutionRead> {
  return apiPost<TimetableSubstitutionRead>('/sms/timetable/substitutions', payload)
}

/** Soft-cancels: the row stays for audit ("who was asked to cover"). */
export function cancelSubstitution(substitutionId: number): Promise<TimetableSubstitutionRead> {
  return apiPost<TimetableSubstitutionRead>(`/sms/timetable/substitutions/${substitutionId}/cancel`)
}

export const DAY_ORDER: DayOfWeek[] = ['MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY', 'SATURDAY', 'SUNDAY']

/** Convenience: today's slots from a full weekly slot list, in period order. */
export function slotsForToday(slots: TimetableSlotDetail[]): TimetableSlotDetail[] {
  const todayName = DAY_ORDER[(new Date().getDay() + 6) % 7] // JS getDay(): 0=Sunday -> map to MONDAY-first
  return slots
    .filter((s) => s.day_of_week?.toUpperCase() === todayName)
    .sort((a, b) => (a.period_number ?? a.period_id) - (b.period_number ?? b.period_id))
}

/**
 * Assisted generation. `dry_run` defaults to true server-side; this client
 * passes it explicitly so a caller can never write a week by omission.
 */
export function generateTimetable(payload: GenerationRequest): Promise<GenerationResponse> {
  return apiPost<GenerationResponse>('/sms/timetable/schedules/generate', {
    dry_run: true,
    ...payload,
  })
}

/** Conflicts that already exist, as opposed to checkTimetableClashes' "would this one?". */
export function scanTimetableConflicts(params: {
  sectionId?: number
  teacherId?: number
  academicTermId?: number
} = {}): Promise<TimetableConflictScanResponse> {
  const qs = toQueryString({
    section_id: params.sectionId,
    teacher_id: params.teacherId,
    academic_term_id: params.academicTermId,
  })
  return apiGet<TimetableConflictScanResponse>(`/sms/timetable/conflicts${qs}`)
}

/** Lesson logs: what was actually taught. */
export function listLessonLogs(params: {
  sectionId?: number
  scheduleId?: number
  dateFrom?: string
  dateTo?: string
  limit?: number
} = {}): Promise<LessonLogRead[]> {
  const qs = toQueryString({
    section_id: params.sectionId,
    schedule_id: params.scheduleId,
    date_from: params.dateFrom,
    date_to: params.dateTo,
    limit: params.limit,
  })
  return apiGet<LessonLogRead[]>(`/sms/timetable/lessons${qs}`)
}

export function recordLessonLog(payload: LessonLogCreate): Promise<LessonLogRead> {
  return apiPost<LessonLogRead>('/sms/timetable/lessons', payload)
}

/**
 * The substitute's question: what did this section last do?
 * Resolves to null when no log exists -- meaning nobody wrote one down, NOT
 * that nothing was taught. Callers must render that distinction.
 */
export function getPreviousLesson(params: {
  sectionId: number
  beforeDate: string
  courseId?: number
}): Promise<LessonLogRead | null> {
  const qs = toQueryString({
    section_id: params.sectionId,
    before_date: params.beforeDate,
    course_id: params.courseId,
  })
  return apiGet<LessonLogRead | null>(`/sms/timetable/lessons/previous${qs}`)
}
