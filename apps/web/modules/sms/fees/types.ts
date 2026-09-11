/**
 * Types mirroring `apps/api/src/schemas/sms_fees.py`.
 */

export type VoucherStatus = 'UNPAID' | 'PARTIALLY_PAID' | 'PAID' | 'OVERDUE' | 'CANCELLED'
export type PaymentMethod = 'CASH' | 'BANK_TRANSFER' | 'CARD' | 'ONLINE' | 'CHEQUE'

export interface FeeStructureRead {
  id: number
  name: string
  campus_id?: number | null
  section_id?: number | null
  academic_term_id?: number | null
  tuition_fee: number
  transport_fee: number
  lab_fee: number
  other_fee: number
  total_amount: number
}

export interface FeeStructureCreate {
  name: string
  campus_id?: number | null
  section_id?: number | null
  academic_term_id?: number | null
  tuition_fee?: number
  transport_fee?: number
  lab_fee?: number
  other_fee?: number
}

export interface GenerateVouchersRequest {
  fee_structure_id: number
  student_ids: number[]
  issue_date: string
  due_date: string
  discount_per_student?: number
  fine_per_student?: number
  remarks?: string | null
}

export interface StudentFeeVoucherRead {
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
  total_amount: number
  paid_amount: number
  balance_amount: number
  status: VoucherStatus
  remarks?: string | null
  created_at: string
}

export interface RecordPaymentRequest {
  voucher_id: number
  amount_paid: number
  payment_method?: PaymentMethod
  payment_date?: string | null
  transaction_ref?: string | null
  collected_by?: number | null
  remarks?: string | null
}

export interface FeePaymentReceiptRead {
  id: number
  voucher_id: number
  receipt_no: string
  payment_date: string
  amount_paid: number
  payment_method: PaymentMethod
  transaction_ref?: string | null
  collected_by?: number | null
  remarks?: string | null
  created_at: string
}

export interface StudentFeeLedgerResponse {
  student_id: number
  total_invoiced: number
  total_paid: number
  total_outstanding: number
  vouchers: StudentFeeVoucherRead[]
  receipts: FeePaymentReceiptRead[]
}
