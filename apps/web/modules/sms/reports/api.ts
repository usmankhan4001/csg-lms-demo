/**
 * Real fetch calls against `apps/api/src/routers/sms_reports.py`
 * (mounted at `/api/v1/sms/reports` -- see `src/router.py`).
 */

import { apiGet, toQueryString } from '@/lib/api/api-client'
import type { SchoolOverviewReport, ReportQuery } from './types'

export function getSchoolOverview(query: ReportQuery = {}): Promise<SchoolOverviewReport> {
  const qs = toQueryString({
    campus_id: query.campusId,
    date_from: query.dateFrom,
    date_to: query.dateTo,
    academic_term_id: query.academicTermId,
  })
  return apiGet<SchoolOverviewReport>(`/sms/reports/overview${qs}`)
}
