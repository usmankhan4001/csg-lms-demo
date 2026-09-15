'use client'

/**
 * Attendance report over a date range.
 *
 * Not a duplicate of the Overview tile: this one carries its OWN date window,
 * so "last week" can be asked here while the Grades tab sits on a different
 * term. The overview forces one window across all four domains.
 *
 * THE RENDERING RULE: `attendance_rate` is a `Metric` and may have no value.
 * "0% attendance" means nobody came to school. "Not recorded" means nobody
 * took a register. A head teacher acts on those in opposite directions, so
 * they must never render the same — every figure below goes through
 * `presentation.ts`, and the raw counts are shown beside the rate so the
 * reader can see the denominator it came from.
 */

import { useState } from 'react'
import { CalendarCheck, CircleSlash, Clock, FileCheck2 } from 'lucide-react'
import { DashPageShell, SectionCard, StatGrid } from '@/components/widgets'
import { useApiResource } from '@/lib/api/useApiResource'
import { useSchoolSession } from '@/lib/api/useSchoolSession'
import { listCampuses } from '@/modules/sms/campus/api'
import { getAttendanceReport } from '@/modules/sms/reports/api'
import { ReportFilters } from '@/modules/sms/reports/components/ReportFilters'
import { formatMetric, metricHint, metricTone } from '@/modules/sms/reports/presentation'

interface Props {
  org_id: number
  orgslug: string
}

export default function AttendanceReportClient({ org_id }: Props) {
  const { session } = useSchoolSession()
  const [campusId, setCampusId] = useState<number | undefined>(undefined)
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')

  const campuses = useApiResource(() => listCampuses({ orgId: org_id, isActive: true }), [org_id], {
    isEmpty: (d) => d.length === 0,
  })

  const effectiveCampusId = campusId ?? session?.campus_id ?? campuses.data?.[0]?.id

  const report = useApiResource(
    () =>
      getAttendanceReport({
        campusId: effectiveCampusId,
        dateFrom: dateFrom || undefined,
        dateTo: dateTo || undefined,
      }),
    [effectiveCampusId, dateFrom, dateTo],
    {
      skip: effectiveCampusId === undefined,
      // A report with nothing recorded is a REAL answer, not an empty list.
      // Letting the generic empty state swallow it would hide the very
      // "no register taken" message this page exists to show.
      isEmpty: () => false,
    }
  )

  const data = report.data
  const rate = data?.attendance_rate

  return (
    <DashPageShell
      module="reports"
      title="Attendance report"
      description="Attendance rate over a date range, from the registers actually taken."
    >
      <ReportFilters
        idPrefix="report-attendance"
        campuses={campuses.data ?? []}
        campusId={effectiveCampusId}
        onCampusChange={setCampusId}
        dateFrom={dateFrom}
        dateTo={dateTo}
        onDateFromChange={setDateFrom}
        onDateToChange={setDateTo}
      />

      <StatGrid
        state={report.status === 'error' ? 'error' : report.status === 'loading' ? 'loading' : 'success'}
        error={report.error}
        onRetry={report.refetch}
        columns={4}
        items={[
          {
            label: 'Attendance rate',
            value: rate ? formatMetric(rate) : '—',
            hint: rate ? metricHint(rate) : undefined,
            icon: CalendarCheck,
            tone: rate ? metricTone(rate) : 'neutral',
          },
          {
            // Counts are plain integers on purpose: "0 absences" and "no data"
            // differ, and the rate above already carries that distinction.
            label: 'Present',
            value: data ? String(data.present_count) : '—',
            icon: FileCheck2,
            tone: 'neutral',
          },
          {
            label: 'Absent',
            value: data ? String(data.absent_count) : '—',
            icon: CircleSlash,
            tone: 'neutral',
          },
          {
            label: 'Late',
            value: data ? String(data.late_count) : '—',
            icon: Clock,
            tone: 'neutral',
          },
        ]}
      />

      {/* The denominator, stated. A 100% built on two records and one built on
          two thousand are different claims about a school. */}
      {data && (
        <SectionCard
          title="What this is built on"
          description={
            data.records_counted > 0
              ? `${data.records_counted} attendance record${data.records_counted === 1 ? '' : 's'} from ${data.source_module}.`
              : `No attendance has been recorded for this range yet, so no rate can be calculated. Source: ${data.source_module}.`
          }
        >
          <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            {[
              ['Present', data.present_count],
              ['Absent', data.absent_count],
              ['Late', data.late_count],
              ['Excused', data.excused_count],
            ].map(([label, value]) => (
              <div key={String(label)} className="flex flex-col gap-1">
                <dt className="text-xs font-medium uppercase tracking-wide text-gray-500">
                  {label}
                </dt>
                <dd className="text-lg font-semibold tabular-nums text-gray-900">{value}</dd>
              </div>
            ))}
          </dl>
        </SectionCard>
      )}

    </DashPageShell>
  )
}
