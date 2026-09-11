/**
 * Real fetch calls against `apps/api/src/routers/sms_hr.py` (mounted at
 * `/api/v1/sms/hr`) and `apps/api/src/routers/sms_payroll.py` (mounted at
 * `/api/v1/sms/payroll`) -- combined here because they share one feature
 * toggle (`sms_hr_payroll`).
 */

import { apiGet, apiPatch, apiPost, toQueryString } from '@/lib/api/api-client'
import type {
  BatchSalarySlipGenerateRequest,
  ContractType,
  LeaveStatus,
  LeaveType,
  ProcessSalaryPaymentRequest,
  SalaryPaymentStatus,
  SalarySlipRead,
  SalaryStructureCreate,
  SalaryStructureRead,
  StaffLeaveActionRequest,
  StaffLeaveCreate,
  StaffLeaveRead,
  StaffProfileCreate,
  StaffProfileRead,
  StaffProfileUpdate,
} from './types'

// ── HR: Staff directory ──

export function listStaffProfiles(params: { campusId?: number; department?: string; contractType?: ContractType; isActive?: boolean } = {}): Promise<StaffProfileRead[]> {
  const qs = toQueryString({
    campus_id: params.campusId,
    department: params.department,
    contract_type: params.contractType,
    is_active: params.isActive,
  })
  return apiGet<StaffProfileRead[]>(`/sms/hr/staff${qs}`)
}

export function createStaffProfile(payload: StaffProfileCreate): Promise<StaffProfileRead> {
  return apiPost<StaffProfileRead>('/sms/hr/staff', payload)
}

export function getStaffProfile(staffId: number): Promise<StaffProfileRead> {
  return apiGet<StaffProfileRead>(`/sms/hr/staff/${staffId}`)
}

export function updateStaffProfile(staffId: number, payload: StaffProfileUpdate): Promise<StaffProfileRead> {
  return apiPatch<StaffProfileRead>(`/sms/hr/staff/${staffId}`, payload)
}

// ── HR: Staff leaves ──

export function applyStaffLeave(payload: StaffLeaveCreate): Promise<StaffLeaveRead> {
  return apiPost<StaffLeaveRead>('/sms/hr/leaves', payload)
}

export function listStaffLeaves(params: { staffId?: number; leaveType?: LeaveType; status?: LeaveStatus } = {}): Promise<StaffLeaveRead[]> {
  const qs = toQueryString({ staff_id: params.staffId, leave_type: params.leaveType, status: params.status })
  return apiGet<StaffLeaveRead[]>(`/sms/hr/leaves${qs}`)
}

export function updateStaffLeaveStatus(leaveId: number, payload: StaffLeaveActionRequest): Promise<StaffLeaveRead> {
  return apiPatch<StaffLeaveRead>(`/sms/hr/leaves/${leaveId}/status`, payload)
}

// ── Payroll: Salary structures ──

export function upsertSalaryStructure(payload: SalaryStructureCreate): Promise<SalaryStructureRead> {
  return apiPost<SalaryStructureRead>('/sms/payroll/structures', payload)
}

export function getStaffSalaryStructure(staffId: number): Promise<SalaryStructureRead> {
  return apiGet<SalaryStructureRead>(`/sms/payroll/structures/${staffId}`)
}

// ── Payroll: Salary slips ──

export function generateSalarySlipsBatch(payload: BatchSalarySlipGenerateRequest): Promise<SalarySlipRead[]> {
  return apiPost<SalarySlipRead[]>('/sms/payroll/slips/generate', payload)
}

export function listSalarySlips(params: { staffId?: number; month?: number; year?: number; paymentStatus?: SalaryPaymentStatus } = {}): Promise<SalarySlipRead[]> {
  const qs = toQueryString({ staff_id: params.staffId, month: params.month, year: params.year, payment_status: params.paymentStatus })
  return apiGet<SalarySlipRead[]>(`/sms/payroll/slips${qs}`)
}

export function getSalarySlip(slipId: number): Promise<SalarySlipRead> {
  return apiGet<SalarySlipRead>(`/sms/payroll/slips/${slipId}`)
}

export function recordSalaryPayment(slipId: number, payload: ProcessSalaryPaymentRequest): Promise<SalarySlipRead> {
  return apiPost<SalarySlipRead>(`/sms/payroll/slips/${slipId}/pay`, payload)
}
