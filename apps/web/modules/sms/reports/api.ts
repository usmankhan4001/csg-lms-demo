/**
 * Real fetch calls against `apps/api/src/routers/sms_reports.py`
 * (mounted at `/api/v1/sms/reports` -- see `src/router.py`).
 */

import { apiGet, toQueryString } from '@/lib/api/api-client'
import type {
  AdmissionsFunnelReport,
  AttendanceReport,
  FeeCollectionReport,
  GradeDistributionReport,
  ReportQuery,
  SchoolOverviewReport,
} from './types'

export function getSchoolOverview(query: ReportQuery = {}): Promise<SchoolOverviewReport> {
  const qs = toQueryString({
    campus_id: query.campusId,
    date_from: query.dateFrom,
    date_to: query.dateTo,
    academic_term_id: query.academicTermId,
  })
  return apiGet<SchoolOverviewReport>(`/sms/reports/overview${qs}`)
}

/**
 * The four per-domain reports.
 *
 * These are NOT redundant with `/overview`. The overview applies ONE date
 * window and one term across all four domains, which is the right answer for
 * "how is the school doing today" and the wrong one for almost every real
 * question after that: a head of department asks for grades in term 2 while
 * the bursar asks for fee collection this month, and the overview cannot
 * express both at once. Each endpoint below carries only the filters that
 * mean something for its own domain — `/grades` has no date range because
 * grades are scoped by term, and `/admissions` has neither, because a funnel
 * is a current-state snapshot.
 *
 * Every rate returned here is a `Metric` and may legitimately have no value.
 * Render it through `presentation.ts`, never by coercing null to 0.
 */

export function getAttendanceReport(
  query: Pick<ReportQuery, 'campusId' | 'dateFrom' | 'dateTo'> = {}
): Promise<AttendanceReport> {
  const qs = toQueryString({
    campus_id: query.campusId,
    date_from: query.dateFrom,
    date_to: query.dateTo,
  })
  return apiGet<AttendanceReport>(`/sms/reports/attendance${qs}`)
}

export function getGradeDistribution(
  query: Pick<ReportQuery, 'campusId' | 'academicTermId'> = {}
): Promise<GradeDistributionReport> {
  const qs = toQueryString({
    campus_id: query.campusId,
    academic_term_id: query.academicTermId,
  })
  return apiGet<GradeDistributionReport>(`/sms/reports/grades${qs}`)
}

export function getFeeCollection(
  query: Pick<ReportQuery, 'campusId' | 'dateFrom' | 'dateTo'> = {}
): Promise<FeeCollectionReport> {
  const qs = toQueryString({
    campus_id: query.campusId,
    date_from: query.dateFrom,
    date_to: query.dateTo,
  })
  return apiGet<FeeCollectionReport>(`/sms/reports/fees${qs}`)
}

export function getAdmissionsFunnel(
  query: Pick<ReportQuery, 'campusId'> = {}
): Promise<AdmissionsFunnelReport> {
  const qs = toQueryString({ campus_id: query.campusId })
  return apiGet<AdmissionsFunnelReport>(`/sms/reports/admissions${qs}`)
}
