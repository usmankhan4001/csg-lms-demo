/**
 * Mirrors `SalarySlipRead` in `apps/api/src/schemas/sms_payroll.py:41`.
 */

export type SalaryPaymentStatus = 'PENDING' | 'APPROVED' | 'PAID' | 'REJECTED'

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
  /** Surfaced so a payslip shows WHY pay was docked, not just that it was. */
  unpaid_leave_days: number
  unpaid_leave_deduction: number
  gross_salary: number
  total_deductions: number
  net_salary: number
  payment_status: SalaryPaymentStatus
  payment_date?: string | null
  payment_method?: string | null
  remarks?: string | null
}
