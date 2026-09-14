/**
 * Real fetch calls against `apps/api/src/routers/sms_fees.py`
 * (mounted at `/api/v1/sms/fees`).
 */

import { apiGet, apiPost, toQueryString } from '@/lib/api/api-client'
import type {
  BankTransferRead,
  ConcessionRead,
  CreateConcessionRequest,
  CreateInstallmentPlanRequest,
  FeeChangeEventRead,
  FeePaymentReceiptRead,
  FeeReminderLogRead,
  FeeStructureCreate,
  FeeStructureRead,
  GenerateVouchersRequest,
  ImportBankTransfersRequest,
  InstallmentPlanSummary,
  IssueRefundRequest,
  MatchTransferRequest,
  RecordPaymentRequest,
  RefundRead,
  StudentFeeLedgerResponse,
  StudentFeeVoucherRead,
  TransferMatchSuggestion,
  VoucherStatus,
} from './types'

export function listFeeStructures(params: { campusId?: number; academicTermId?: number } = {}): Promise<FeeStructureRead[]> {
  const qs = toQueryString({ campus_id: params.campusId, academic_term_id: params.academicTermId })
  return apiGet<FeeStructureRead[]>(`/sms/fees/structures${qs}`)
}

export function createFeeStructure(payload: FeeStructureCreate): Promise<FeeStructureRead> {
  return apiPost<FeeStructureRead>('/sms/fees/structures', payload)
}

export function generateVouchers(payload: GenerateVouchersRequest): Promise<StudentFeeVoucherRead[]> {
  return apiPost<StudentFeeVoucherRead[]>('/sms/fees/vouchers/generate', payload)
}

export function listVouchers(params: { studentId?: number; status?: VoucherStatus } = {}): Promise<StudentFeeVoucherRead[]> {
  const qs = toQueryString({ student_id: params.studentId, status: params.status })
  return apiGet<StudentFeeVoucherRead[]>(`/sms/fees/vouchers${qs}`)
}

export function recordPayment(payload: RecordPaymentRequest): Promise<FeePaymentReceiptRead> {
  return apiPost<FeePaymentReceiptRead>('/sms/fees/payments', payload)
}

export function getStudentFeeLedger(studentId: number): Promise<StudentFeeLedgerResponse> {
  return apiGet<StudentFeeLedgerResponse>(`/sms/fees/ledger/student/${studentId}`)
}

/**
 * Charges late fees on every overdue UNPAID/PARTIAL voucher, returning only
 * the vouchers that actually changed.
 *
 * Idempotent by design on the backend (it recomputes the target fee and
 * charges only the difference), so re-running it is safe and will not
 * compound. Narrow it with `studentId`/`voucherId`; omit both to sweep the
 * whole school. Rate/grace/cap fall back to the server's defaults.
 */
export function accrueLateFees(
  params: {
    studentId?: number
    voucherId?: number
    ratePercent?: number
    graceDays?: number
    maxPercent?: number
  } = {}
): Promise<StudentFeeVoucherRead[]> {
  const qs = toQueryString({
    student_id: params.studentId,
    voucher_id: params.voucherId,
    rate_percent: params.ratePercent,
    grace_days: params.graceDays,
    max_percent: params.maxPercent,
  })
  return apiPost<StudentFeeVoucherRead[]>(`/sms/fees/vouchers/accrue-late-fees${qs}`)
}


/* ──────────────────────────────────────────────────────────────────────────
 * Instalment plans
 * ────────────────────────────────────────────────────────────────────────── */

/**
 * Splits a term or year fee into scheduled instalments.
 *
 * Each instalment is a REAL voucher, so payments, receipts, the ledger and
 * late-fee accrual all work on it unchanged -- and a family that misses
 * instalment 2 is charged a late fee on instalment 2 rather than on the whole
 * year. Requires at least two due dates; the backend rejects one.
 */
export function createInstallmentPlan(
  payload: CreateInstallmentPlanRequest
): Promise<InstallmentPlanSummary> {
  return apiPost<InstallmentPlanSummary>('/sms/fees/installment-plans', payload)
}

export function listStudentInstallmentPlans(studentId: number): Promise<InstallmentPlanSummary[]> {
  return apiGet<InstallmentPlanSummary[]>(`/sms/fees/installment-plans/student/${studentId}`)
}

/* ──────────────────────────────────────────────────────────────────────────
 * Concessions
 * ────────────────────────────────────────────────────────────────────────── */

/**
 * Records a sibling discount, scholarship or hardship reduction for one named
 * student, with the reason and the authorising officer.
 *
 * Attached to a named student rather than inferred: which child counts as the
 * "second child" is a school policy question, and guessing it would quietly
 * award or withhold money from a real family.
 */
export function createConcession(payload: CreateConcessionRequest): Promise<ConcessionRead> {
  return apiPost<ConcessionRead>('/sms/fees/concessions', payload)
}

export function listStudentConcessions(studentId: number): Promise<ConcessionRead[]> {
  return apiGet<ConcessionRead[]>(`/sms/fees/concessions/student/${studentId}`)
}

/* ──────────────────────────────────────────────────────────────────────────
 * Refunds
 * ────────────────────────────────────────────────────────────────────────── */

/**
 * Returns money to a family. The backend refuses an amount exceeding what was
 * actually paid on the voucher, and recomputes the balance with the same
 * expression the payment path uses -- so a refunded voucher reads exactly like
 * one that was never paid that much.
 */
export function issueRefund(payload: IssueRefundRequest): Promise<RefundRead> {
  return apiPost<RefundRead>('/sms/fees/refunds', payload)
}

/* ──────────────────────────────────────────────────────────────────────────
 * Bank reconciliation
 * ────────────────────────────────────────────────────────────────────────── */

/**
 * Takes already-parsed bank statement rows into the unmatched queue.
 *
 * Parsing a bank's own export format is deliberately not done anywhere in this
 * system: formats are per-bank and per-country, and a parser guessing at a
 * column would silently attribute money to the wrong family.
 */
export function importBankTransfers(
  payload: ImportBankTransfersRequest
): Promise<BankTransferRead[]> {
  return apiPost<BankTransferRead[]>('/sms/fees/bank-transfers/import', payload)
}

/** The reconciliation queue: money received that nobody has attributed to a
 * family yet. */
export function listUnmatchedTransfers(
  params: { campusId?: number } = {}
): Promise<BankTransferRead[]> {
  const qs = toQueryString({ campus_id: params.campusId })
  return apiGet<BankTransferRead[]>(`/sms/fees/bank-transfers/unmatched${qs}`)
}

/**
 * Candidate vouchers for a transfer. Nothing here marks anything paid -- a
 * wrong automatic match moves real money against the wrong family, so a human
 * always confirms. Each suggestion states the evidence it was found on.
 */
export function suggestTransferMatches(transferId: number): Promise<TransferMatchSuggestion[]> {
  return apiGet<TransferMatchSuggestion[]>(
    `/sms/fees/bank-transfers/${transferId}/suggestions`
  )
}

/**
 * Attributes a transfer by recording a real payment through the ordinary
 * payment path, so a reconciled payment is indistinguishable from one taken at
 * the counter and cannot drift from it.
 */
export function matchTransfer(payload: MatchTransferRequest): Promise<BankTransferRead> {
  return apiPost<BankTransferRead>('/sms/fees/bank-transfers/match', payload)
}

/* ──────────────────────────────────────────────────────────────────────────
 * Audit and reminders
 * ────────────────────────────────────────────────────────────────────────── */

/** Append-only record of every money mutation on this voucher. No endpoint
 * updates or deletes a row here -- a trail that can be rewritten is not a
 * trail. */
export function getVoucherHistory(voucherId: number): Promise<FeeChangeEventRead[]> {
  return apiGet<FeeChangeEventRead[]>(`/sms/fees/vouchers/${voucherId}/history`)
}

/** What the school actually told families, and what was actually delivered.
 * `recipients` and `delivered` differ whenever mail is unconfigured -- which is
 * exactly the gap a school needs to see rather than assume. */
export function listFeeReminders(
  params: { studentId?: number; voucherId?: number } = {}
): Promise<FeeReminderLogRead[]> {
  const qs = toQueryString({ student_id: params.studentId, voucher_id: params.voucherId })
  return apiGet<FeeReminderLogRead[]>(`/sms/fees/reminders${qs}`)
}
