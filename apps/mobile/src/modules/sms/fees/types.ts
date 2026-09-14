/**
 * Mirrors `apps/api/src/schemas/sms_fees.py` field-for-field.
 */

/**
 * `VoucherStatus` in `apps/api/src/db/sms_fees.py:20`. Exactly these four --
 * there is no PARTIALLY_PAID and no OVERDUE. Inventing either produces a
 * branch that can never match, which this codebase has already shipped once.
 * "Overdue" is derived from `due_date` against today, not a status value.
 */
export type VoucherStatus = 'UNPAID' | 'PARTIAL' | 'PAID' | 'CANCELLED'

export interface StudentFeeVoucher {
  id: number
  student_id: number
  fee_structure_id?: number | null
  voucher_no: string
  issue_date: string
  due_date: string
  tuition_fee: number
  transport_fee: number
  lab_fee: number
  other_fee: number
  discount: number
  fine: number
  late_fee_applied: number
  late_fee_last_accrued_on?: string | null
  total_amount: number
  paid_amount: number
  balance_amount: number
  status: VoucherStatus
  remarks?: string | null
}

export interface FeePaymentReceipt {
  id: number
  voucher_id: number
  amount: number
  [key: string]: unknown
}

export interface StudentFeeLedger {
  student_id: number
  total_invoiced: number
  total_paid: number
  total_outstanding: number
  vouchers: StudentFeeVoucher[]
  receipts: FeePaymentReceipt[]
}
