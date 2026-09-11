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
