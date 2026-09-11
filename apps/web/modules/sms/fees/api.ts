/**
 * Real fetch calls against `apps/api/src/routers/sms_fees.py`
 * (mounted at `/api/v1/sms/fees`).
 */

import { apiGet, apiPost, toQueryString } from '@/lib/api/api-client'
import type {
  FeePaymentReceiptRead,
  FeeStructureCreate,
  FeeStructureRead,
  GenerateVouchersRequest,
  RecordPaymentRequest,
  StudentFeeLedgerResponse,
  StudentFeeVoucherRead,
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
