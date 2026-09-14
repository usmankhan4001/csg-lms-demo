/**
 * Real fetch calls against `apps/api/src/routers/sms_fees.py`, mounted at
 * `/api/v1/sms/fees` (router.py:546-547).
 */

import { apiGet } from '@/api/client'
import type { StudentFeeLedger } from './types'

/**
 * GET /sms/fees/ledger/student/{student_id} — sms_fees.py:153.
 * Gated by `require_own_student_or_privileged()`: a guardian may read their
 * own child's ledger and nobody else's. Ownership is the server's call.
 */
export function getStudentFeeLedger(studentId: number): Promise<StudentFeeLedger> {
  return apiGet<StudentFeeLedger>(`/sms/fees/ledger/student/${studentId}`)
}
