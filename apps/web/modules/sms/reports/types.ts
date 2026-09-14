/**
 * Mirrors `apps/api/src/schemas/sms_reports.py`.
 *
 * `Metric.value` is deliberately `number | null`. A null is NOT a zero: it
 * means the figure could not be computed because nothing was recorded, and
 * `noDataReason` says what is missing. Rendering a null as 0 would recreate
 * exactly the fabricated reporting this codebase has already had to tear out
 * three times.
 */

export interface Metric {
  value: number | null
  unit: 'percent' | 'currency' | 'count' | 'gpa'
  has_data: boolean
  no_data_reason: string | null
  sample_size: number
}

export interface AttendanceReport {
  attendance_rate: Metric
  present_count: number
  absent_count: number
  late_count: number
  excused_count: number
  records_counted: number
  source_module: string
}

export interface GradeDistributionReport {
  average_percentage: Metric
  average_gpa: Metric
  letter_distribution: Record<string, number>
  entries_counted: number
  source_module: string
}

export interface FeeCollectionReport {
  collection_rate: Metric
  total_invoiced: number
  total_collected: number
  total_outstanding: number
  voucher_count: number
  status_breakdown: Record<string, number>
  source_module: string
}

export interface AdmissionsFunnelReport {
  conversion_rate: Metric
  stage_counts: Record<string, number>
  total_leads: number
  enrolled_count: number
  lost_count: number
  stalled_count: number
  source_module: string
}

export interface SchoolOverviewReport {
  campus_id: number | null
  campus_name: string | null
  date_from: string | null
  date_to: string | null
  attendance: AttendanceReport
  grades: GradeDistributionReport
  fees: FeeCollectionReport
  admissions: AdmissionsFunnelReport
  sections_covered: number
  students_covered: number
  warnings: string[]
}

export interface ReportQuery {
  campusId?: number
  dateFrom?: string
  dateTo?: string
  academicTermId?: number
}
