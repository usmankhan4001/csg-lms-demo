/**
 * Types mirroring `apps/api/src/schemas/sms_fees.py`.
 */

/**
 * Mirrors `VoucherStatus` in `apps/api/src/db/sms_fees.py` exactly.
 *
 * This previously declared `PARTIALLY_PAID` and `OVERDUE` -- neither exists
 * in the backend enum, so nothing could ever match them -- while omitting the
 * real `PARTIAL`. Any UI branching on the phantom values was dead code, and a
 * `PARTIAL` filter could not even be typed. "Overdue" is not a status here;
 * it is derived from `due_date` against today.
 */
export type VoucherStatus = 'UNPAID' | 'PARTIAL' | 'PAID' | 'CANCELLED'

/** Mirrors `PaymentMethod` in `apps/api/src/db/sms_fees.py`. `CARD` was listed
 * here but is not a value the backend accepts. */
export type PaymentMethod = 'CASH' | 'BANK_TRANSFER' | 'ONLINE' | 'CHEQUE'

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
  /** How much of `fine` was charged automatically by late-fee accrual, as
   * opposed to a fine the school set by hand. Real field on
   * `StudentFeeVoucherRead` in `apps/api/src/schemas/sms_fees.py`. */
  late_fee_applied: number
  late_fee_last_accrued_on?: string | null
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

/* ──────────────────────────────────────────────────────────────────────────
 * Extended fee types, mirroring `apps/api/src/schemas/sms_fees_extended.py`.
 *
 * Every money figure below is a `float` on the wire because that is what the
 * backend schema declares. The client therefore FORMATS but never
 * ACCUMULATES: totals shown to a bursar come from the server's own summary
 * fields (`total_amount`, `paid_amount`, `balance_amount`) rather than from
 * summing rows here, so a rounding drift in the browser can never make a
 * balance look settled when the ledger says it is not.
 * ────────────────────────────────────────────────────────────────────────── */

/** Mirrors `InstallmentPlanStatus` in `apps/api/src/db/sms_fees_extended.py`. */
export type InstallmentPlanStatus = 'ACTIVE' | 'COMPLETED' | 'CANCELLED'

/** Mirrors `ConcessionKind`. The reason a family pays less — a flat discount
 * number could express the amount but never the justification. */
export type ConcessionKind = 'SIBLING' | 'SCHOLARSHIP' | 'HARDSHIP' | 'STAFF_CHILD' | 'OTHER'

/** Mirrors `BankTransferStatus`. */
export type BankTransferStatus = 'UNMATCHED' | 'MATCHED' | 'IGNORED'

/** Mirrors `FeeReminderKind`. */
export type FeeReminderKind = 'UPCOMING' | 'DUE_TODAY' | 'OVERDUE'

/** Mirrors `FeeChangeAction`. */
export type FeeChangeAction =
  | 'VOUCHER_CREATED'
  | 'PAYMENT_RECORDED'
  | 'REFUND_ISSUED'
  | 'CONCESSION_APPLIED'
  | 'TRANSFER_MATCHED'

export interface CreateInstallmentPlanRequest {
  student_id: number
  fee_structure_id: number
  name: string
  issue_date: string
  /** One due date per instalment. The backend enforces 2–24; a single
   * "instalment" is just an ordinary voucher. */
  due_dates: string[]
  campus_id?: number | null
  academic_term_id?: number | null
  apply_concessions?: boolean
}

export interface InstallmentPlanSummary {
  plan_id: number
  student_id: number
  name: string
  status: InstallmentPlanStatus
  installment_count: number
  paid_count: number
  total_amount: number
  paid_amount: number
  balance_amount: number
  vouchers: StudentFeeVoucherRead[]
}

export interface CreateConcessionRequest {
  student_id: number
  kind: ConcessionKind
  /** Exactly one of `percentage` or `fixed_amount`. The backend returns a 400
   * explaining why rather than silently preferring one. */
  percentage?: number | null
  fixed_amount?: number | null
  /** Required: a concession with no stated reason is what the model exists to
   * prevent. */
  reason: string
  campus_id?: number | null
  valid_from?: string | null
  valid_until?: string | null
}

export interface ConcessionRead {
  id: number
  student_id: number
  campus_id?: number | null
  kind: ConcessionKind
  percentage?: number | null
  fixed_amount?: number | null
  reason: string
  authorised_by_user_id?: number | null
  valid_from?: string | null
  valid_until?: string | null
  is_active: boolean
  created_at: string
}

export interface IssueRefundRequest {
  voucher_id: number
  amount: number
  reason: string
  method?: string
  refund_date?: string | null
}

export interface RefundRead {
  id: number
  voucher_id: number
  refund_no: string
  refund_date: string
  amount: number
  method: string
  reason: string
  authorised_by_user_id?: number | null
  created_at: string
}

/** One parsed line off a bank statement. Parsing a particular bank's export
 * format is deliberately NOT done in this system — formats are per-bank and
 * per-country, and a parser guessing a column would silently attribute money
 * to the wrong family. */
export interface BankTransferLine {
  transfer_date: string
  amount: number
  bank_reference?: string | null
  payer_name?: string | null
  payer_note?: string | null
}

export interface ImportBankTransfersRequest {
  rows: BankTransferLine[]
  campus_id?: number | null
}

export interface BankTransferRead {
  id: number
  campus_id?: number | null
  transfer_date: string
  amount: number
  bank_reference?: string | null
  payer_name?: string | null
  payer_note?: string | null
  status: BankTransferStatus
  matched_receipt_id?: number | null
  matched_voucher_id?: number | null
  matched_by_user_id?: number | null
  matched_at?: string | null
  ignored_reason?: string | null
  created_at: string
}

/**
 * A candidate voucher for an unmatched transfer, with the evidence spelled
 * out. There is deliberately no confidence percentage: a fabricated "87%
 * match" on somebody's fee payment would invite a clerk to trust a number the
 * system cannot justify. `matched_on` lists what actually lined up.
 */
export interface TransferMatchSuggestion {
  voucher: StudentFeeVoucherRead
  matched_on: string[]
}

export interface MatchTransferRequest {
  transfer_id: number
  voucher_id: number
}

/** One entry in a voucher's append-only money trail. Nothing updates or
 * deletes these rows. */
export interface FeeChangeEventRead {
  id: number
  voucher_id: number
  student_id: number
  action: FeeChangeAction
  previous_paid_amount?: number | null
  new_paid_amount?: number | null
  previous_balance?: number | null
  new_balance?: number | null
  amount?: number | null
  changed_by_user_id?: number | null
  reason?: string | null
  created_at: string
}

export interface FeeReminderLogRead {
  id: number
  voucher_id: number
  student_id: number
  kind: FeeReminderKind
  sent_on: string
  /** How many recipients the school intended to reach. */
  recipients: number
  /** What the mail provider actually accepted. This differs from `recipients`
   * whenever mail is unconfigured, and that difference is the point — a school
   * must be able to see that reminders did NOT go out rather than assume they
   * did. */
  delivered: number
  balance_at_send: number
  created_at: string
}
