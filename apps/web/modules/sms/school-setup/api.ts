/**
 * Real fetch calls against `apps/api/src/routers/sms_school_setup.py`
 * (mounted at `/api/v1/sms` -- see `src/router.py`).
 */

import { apiGet, apiPost, toQueryString } from '@/lib/api/api-client'
import type {
  SchoolSetupRequest,
  SchoolSetupResponse,
  SchoolSetupStatus,
} from './types'

export function getSchoolSetupStatus(orgId: number): Promise<SchoolSetupStatus> {
  return apiGet<SchoolSetupStatus>(
    `/sms/school-setup/status${toQueryString({ org_id: orgId })}`
  )
}

export function runSchoolSetup(
  payload: SchoolSetupRequest
): Promise<SchoolSetupResponse> {
  return apiPost<SchoolSetupResponse>('/sms/school-setup', payload)
}
