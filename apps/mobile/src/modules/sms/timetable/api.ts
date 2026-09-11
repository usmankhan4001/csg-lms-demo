/**
 * Real fetch calls against `apps/api/src/routers/sms_timetable.py`
 * (mounted at `/api/v1/sms/timetable`). Ported from
 * `apps/web/modules/sms/timetable/api.ts`.
 */

import { apiGet, apiPost, toQueryString } from '@/api/client'
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

export const DAY_ORDER: DayOfWeek[] = ['MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY', 'SATURDAY', 'SUNDAY']

/** Convenience: today's slots from a full weekly slot list, in period order. */
export function slotsForToday(slots: TimetableSlotDetail[]): TimetableSlotDetail[] {
  const todayName = DAY_ORDER[(new Date().getDay() + 6) % 7] // JS getDay(): 0=Sunday -> map to MONDAY-first
  return slots
    .filter((s) => s.day_of_week?.toUpperCase() === todayName)
    .sort((a, b) => (a.period_number ?? a.period_id) - (b.period_number ?? b.period_id))
}

/** Convenience: group a full weekly slot list by day, in DAY_ORDER, for a "Classes" list view. */
export function slotsByDay(slots: TimetableSlotDetail[]): { day: DayOfWeek; slots: TimetableSlotDetail[] }[] {
  return DAY_ORDER.map((day) => ({
    day,
    slots: slots
      .filter((s) => s.day_of_week?.toUpperCase() === day)
      .sort((a, b) => (a.period_number ?? a.period_id) - (b.period_number ?? b.period_id)),
  })).filter((group) => group.slots.length > 0)
}
