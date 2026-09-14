/**
 * Real fetch calls against `apps/api/src/routers/sms_attendance.py`
 * (mounted at `/api/v1/sms/attendance` -- see `src/router.py`).
 */

import { apiGet, apiPatch, apiPost, toQueryString } from '@/lib/api/api-client'
import type {
  BatchRollCallRequest,
  BatchRollCallResponse,
  LeaveRequestCreate,
  LeaveRequestRead,
  LeaveRequestStatus,
  LeaveRequestUpdateStatus,
  MonthlyStudentAttendanceSheet,
  AbsenceExcuseCreate,
  AbsenceExcuseRead,
  AbsenceExcuseReview,
  AbsenceExcuseReviewResponse,
  AttendanceChangeEventRead,
  BulkMarkRangeRequest,
  BulkMarkRangeResponse,
  ExcuseStatus,
  PastoralConcernRead,
  PastoralConcernStatus,
  PastoralConcernUpdate,
  PastoralInterventionCreate,
  PastoralInterventionRead,
} from './types'

export function submitRollCall(payload: BatchRollCallRequest): Promise<BatchRollCallResponse> {
  return apiPost<BatchRollCallResponse>('/sms/attendance/roll-call', payload)
}

export function getMonthlyStudentAttendance(
  studentId: number,
  year: number,
  month: number,
  sectionId?: number
): Promise<MonthlyStudentAttendanceSheet> {
  const qs = toQueryString({ year, month, section_id: sectionId })
  return apiGet<MonthlyStudentAttendanceSheet>(`/sms/attendance/student/${studentId}/monthly${qs}`)
}

export function submitLeaveRequest(payload: LeaveRequestCreate): Promise<LeaveRequestRead> {
  return apiPost<LeaveRequestRead>('/sms/attendance/leave-requests', payload)
}

export function listLeaveRequests(params: { studentId?: number; status?: LeaveRequestStatus; limit?: number; offset?: number } = {}): Promise<LeaveRequestRead[]> {
  const qs = toQueryString({ student_id: params.studentId, status: params.status, limit: params.limit, offset: params.offset })
  return apiGet<LeaveRequestRead[]>(`/sms/attendance/leave-requests${qs}`)
}

export function updateLeaveRequestStatus(requestId: number, payload: LeaveRequestUpdateStatus): Promise<LeaveRequestRead> {
  return apiPatch<LeaveRequestRead>(`/sms/attendance/leave-requests/${requestId}/status`, payload)
}

// ── Attendance trail ──

export function getStudentAttendanceHistory(
  studentId: number,
  params: { sectionId?: number; dateFrom?: string; dateTo?: string } = {}
): Promise<AttendanceChangeEventRead[]> {
  const qs = toQueryString({
    section_id: params.sectionId,
    date_from: params.dateFrom,
    date_to: params.dateTo,
  })
  return apiGet<AttendanceChangeEventRead[]>(`/sms/attendance/history/student/${studentId}${qs}`)
}

// ── Absence excuses ──

export function submitAbsenceExcuse(payload: AbsenceExcuseCreate): Promise<AbsenceExcuseRead> {
  return apiPost<AbsenceExcuseRead>('/sms/attendance/excuses', payload)
}

export function listAbsenceExcuses(
  params: { sectionId?: number; studentId?: number; status?: ExcuseStatus; limit?: number; offset?: number } = {}
): Promise<AbsenceExcuseRead[]> {
  const qs = toQueryString({
    section_id: params.sectionId,
    student_id: params.studentId,
    status: params.status,
    limit: params.limit,
    offset: params.offset,
  })
  return apiGet<AbsenceExcuseRead[]>(`/sms/attendance/excuses${qs}`)
}

/**
 * PATCH, not POST -- verified against sms_attendance.py:653.
 * Returns `records_converted`, which the caller MUST surface: 0 is a
 * legitimate outcome (no ABSENT record that day), and a reviewer who sees
 * nothing happen will press the button again.
 */
export function reviewAbsenceExcuse(
  excuseId: number,
  payload: AbsenceExcuseReview
): Promise<AbsenceExcuseReviewResponse> {
  return apiPatch<AbsenceExcuseReviewResponse>(`/sms/attendance/excuses/${excuseId}/review`, payload)
}

// ── Pastoral queue ──

export function listPastoralConcerns(
  params: { status?: PastoralConcernStatus; limit?: number; offset?: number } = {}
): Promise<PastoralConcernRead[]> {
  const qs = toQueryString({ status: params.status, limit: params.limit, offset: params.offset })
  return apiGet<PastoralConcernRead[]>(`/sms/attendance/pastoral/concerns${qs}`)
}

export function updatePastoralConcern(
  concernId: number,
  payload: PastoralConcernUpdate
): Promise<PastoralConcernRead> {
  return apiPatch<PastoralConcernRead>(`/sms/attendance/pastoral/concerns/${concernId}`, payload)
}

export function listConcernInterventions(concernId: number): Promise<PastoralInterventionRead[]> {
  return apiGet<PastoralInterventionRead[]>(`/sms/attendance/pastoral/concerns/${concernId}/interventions`)
}

export function recordConcernIntervention(
  concernId: number,
  payload: PastoralInterventionCreate
): Promise<PastoralInterventionRead> {
  return apiPost<PastoralInterventionRead>(
    `/sms/attendance/pastoral/concerns/${concernId}/interventions`,
    payload
  )
}

// ── Bulk marking ──

export function bulkMarkRange(payload: BulkMarkRangeRequest): Promise<BulkMarkRangeResponse> {
  return apiPost<BulkMarkRangeResponse>('/sms/attendance/bulk-mark', payload)
}
