/**
 * Types mirroring `apps/api/src/schemas/sms_hr.py` and
 * `apps/api/src/schemas/sms_payroll.py` -- combined here because both
 * routers share one feature toggle (`sms_hr_payroll`, see
 * `require_sms_hr_payroll_feature`) and one module folder.
 */

export type ContractType = 'PERMANENT' | 'CONTRACT' | 'VISITING' | 'PROBATION'
export type LeaveType = 'CASUAL' | 'SICK' | 'ANNUAL' | 'MATERNITY' | 'PATERNITY' | 'UNPAID'
export type LeaveStatus = 'PENDING' | 'APPROVED' | 'REJECTED'
export type SalaryPaymentStatus = 'PENDING' | 'PAID' | 'FAILED'

export interface StaffProfileRead {
  id: number
  employee_code: string
  full_name: string
  designation: string
  department: string
  joining_date: string
  contract_type: ContractType
  basic_salary: number
  user_id?: number | null
  campus_id?: number | null
  email?: string | null
  phone?: string | null
  is_active: boolean
  created_at: string
}

export interface StaffProfileCreate {
  employee_code: string
  full_name: string
  designation: string
  department: string
  joining_date: string
  contract_type?: ContractType
  basic_salary?: number
  user_id?: number | null
  campus_id?: number | null
  email?: string | null
  phone?: string | null
  is_active?: boolean
}

export interface StaffProfileUpdate {
  full_name?: string
  designation?: string
  department?: string
  joining_date?: string
  contract_type?: ContractType
  basic_salary?: number
  user_id?: number | null
  campus_id?: number | null
  email?: string | null
  phone?: string | null
  is_active?: boolean
}

export interface StaffLeaveCreate {
  staff_id: number
  leave_type: LeaveType
  start_date: string
  end_date: string
  reason?: string | null
}

export interface StaffLeaveActionRequest {
  status: LeaveStatus
  approved_by?: number | null
}

export interface StaffLeaveRead {
  id: number
  staff_id: number
  leave_type: LeaveType
  start_date: string
  end_date: string
  reason?: string | null
  status: LeaveStatus
  approved_by?: number | null
  created_at: string
}

export interface SalaryStructureCreate {
  staff_id: number
  basic?: number
  housing_allowance?: number
  medical_allowance?: number
  other_allowances?: number
  tax_deduction?: number
  provident_fund?: number
  other_deductions?: number
}

export interface SalaryStructureRead extends SalaryStructureCreate {
  id: number
  gross_salary: number
  total_deductions: number
  net_salary: number
  created_at: string
  updated_at: string
}

export interface BatchSalarySlipGenerateRequest {
  month: number
  year: number
  campus_id?: number | null
  staff_ids?: number[] | null
  remarks?: string | null
}

export interface SalarySlipRead {
  id: number
  slip_no: string
  staff_id: number
  month: number
  year: number
  basic: number
  housing_allowance: number
  medical_allowance: number
  other_allowances: number
  tax_deduction: number
  provident_fund: number
  other_deductions: number
  /**
   * Surfaced separately from `other_deductions` so a payslip can show WHY pay
   * was docked, not just that it was -- "pay is short and the slip doesn't
   * say why" is the classic payroll dispute. Mirrors `SalarySlipRead` in
   * apps/api/src/schemas/sms_payroll.py, which has returned these since
   * unpaid-leave deduction landed.
   */
  unpaid_leave_days: number
  unpaid_leave_deduction: number
  gross_salary: number
  total_deductions: number
  net_salary: number
  payment_status: SalaryPaymentStatus
  payment_date?: string | null
  payment_method?: string | null
  remarks?: string | null
  created_at: string
}

export interface ProcessSalaryPaymentRequest {
  payment_date: string
  payment_method?: string
  remarks?: string | null
}


// ── Offboarding ──
//
// `is_active = false` used to be the whole of "this person has left". These
// types back the cascade that actually revokes access.

export type OffboardingReason =
  | 'RESIGNATION'
  | 'END_OF_CONTRACT'
  | 'RETIREMENT'
  | 'DISMISSAL'
  | 'OTHER'

export interface StaffOffboardingRequest {
  effective_date: string
  reason: OffboardingReason
  notes?: string | null
  /** Omit to release sections to unassigned. Never inferred — who inherits a
   *  class is a staffing decision a school makes deliberately. */
  successor_user_id?: number | null
  revoke_roles?: boolean
}

export interface StaffOffboardingRead {
  id: number
  staff_id: number
  staff_user_id: number | null
  campus_id: number | null
  effective_date: string
  reason: OffboardingReason
  notes: string | null
  roles_revoked: number
  sections_released: number
  sections_reassigned: number
  timetable_slots_reassigned: number
  timetable_slots_outstanding: number
  initiated_by_user_id: number | null
  created_at: string
}

export interface OffboardingOutcome {
  offboarding: StaffOffboardingRead
  /** WORK REMAINING, not a result. Timetable slots cannot be left unassigned
   *  (teacher_id is NOT NULL), so a departed teacher still attached to live
   *  rows must be visible rather than buried in a success message. */
  outstanding_timetable_slot_ids: number[]
  warnings: string[]
}

// ── Appraisals ──

export type AppraisalOutcome =
  | 'EXCEEDS'
  | 'MEETS'
  | 'DEVELOPING'
  | 'BELOW'
export type AppraisalStatus = 'DRAFT' | 'SHARED' | 'ACKNOWLEDGED'

export interface StaffAppraisalCreate {
  staff_id: number
  period_start: string
  period_end: string
  outcome?: AppraisalOutcome | null
  strengths?: string | null
  development_areas?: string | null
  objectives?: string | null
}

export interface StaffAppraisalUpdate {
  outcome?: AppraisalOutcome | null
  strengths?: string | null
  development_areas?: string | null
  objectives?: string | null
}

export interface StaffAppraisalRead {
  id: number
  staff_id: number
  campus_id: number | null
  period_start: string
  period_end: string
  outcome: AppraisalOutcome | null
  strengths: string | null
  development_areas: string | null
  objectives: string | null
  status: AppraisalStatus
  /** Always the authenticated reviewer, never a payload value. */
  reviewer_user_id: number
  shared_at: string | null
  acknowledged_at: string | null
  created_at: string
}

// ── Payroll approval ──

export type PayrollActionType = 'PREPARED' | 'APPROVED' | 'REJECTED' | 'PAID'

export interface PayrollActionRead {
  id: number
  slip_id: number
  staff_id: number
  campus_id: number | null
  action: PayrollActionType
  net_salary_at_action: number | null
  note: string | null
  actor_user_id: number | null
  actor_label: string | null
  created_at: string
}

export interface PayrollApprovalRequest {
  slip_ids: number[]
  note?: string | null
}

/** `self_approval_refused` is the separation-of-duties control surfacing: the
 *  person who prepared a slip cannot approve it. It is an outcome rather than
 *  an error so one refused slip does not abort a whole payroll run. */
export type PayrollApprovalOutcomeKind =
  | 'approved'
  | 'rejected'
  | 'self_approval_refused'
  | 'already_paid'
  | 'not_found'

export interface PayrollApprovalOutcome {
  slip_id: number
  outcome: PayrollApprovalOutcomeKind
  detail: string | null
}

export interface PayrollApprovalResponse {
  results: PayrollApprovalOutcome[]
}
