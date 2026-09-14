/**
 * Real fetch calls against `apps/api/src/routers/sms_payroll.py`
 * (mounted at `/api/v1/sms/payroll`).
 *
 * Only the staff member's OWN slips are ever requested here. That is not
 * merely a client-side convention: `_assert_may_read_salary`
 * (sms_payroll.py:57) enforces it server-side -- a non-admin caller may read
 * only their own `staff_id`, and a bare listing with no staff_id is
 * admin-only. Passing someone else's id from this app would 403, which is
 * the correct outcome.
 */

import { apiGet, toQueryString } from '@/api/client'
import type { SalarySlipRead } from './types'

export function listMySalarySlips(staffId: number, params: { year?: number } = {}): Promise<SalarySlipRead[]> {
  return apiGet<SalarySlipRead[]>(
    `/sms/payroll/slips${toQueryString({ staff_id: staffId, year: params.year })}`
  )
}
