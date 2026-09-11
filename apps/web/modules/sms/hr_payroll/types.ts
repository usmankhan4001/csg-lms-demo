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
