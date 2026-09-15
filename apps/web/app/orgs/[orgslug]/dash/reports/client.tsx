'use client'

/**
 * M19 Reports — the principal's single view across attendance, grades, fees
 * and admissions.
 *
 * THE RENDERING RULE THAT MATTERS: a `Metric` with `has_data: false` renders
 * as "Not recorded" plus the reason, never as 0, "0%", or a bare dash that
 * reads like a zero. A principal deciding on "12% attendance" and one
 * deciding on "no roll-call has been taken" need to act differently, and this
 * codebase has already had fabricated reporting torn out three times.
 *
 * Nothing here is computed client-side: every figure comes from
 * /sms/reports/overview, which in turn reuses each source module's own
 * calculations (grades via the gradebook's `resolve_letter_and_gpa`).
 */

import { useState } from 'react'
import {
  BadgeDollarSign,
  CalendarCheck,
  GraduationCap,
  Info,
  UserPlus,
} from 'lucide-react'
import {
  DashPageShell,
  DataTable,
  EmptyState,
  SectionCard,
  StatGrid,
} from '@/components/widgets'
import { useApiResource } from '@/lib/api/useApiResource'
import { useSchoolSession } from '@/lib/api/useSchoolSession'
import { listCampuses } from '@/modules/sms/campus/api'
import { getSchoolOverview } from '@/modules/sms/reports/api'
import type { Metric } from '@/modules/sms/reports/types'
// Shared with the school dashboard: one implementation of "how is a missing
// figure rendered". Two copies would eventually disagree about the same school.
import { formatMetric, metricHint, currency } from '@/modules/sms/reports/presentation'

interface ReportsDashClientProps {
  org_id: number
  orgslug: string
}

export default function ReportsDashClient({ org_id }: ReportsDashClientProps) {
  const { session } = useSchoolSession()
  const [campusId, setCampusId] = useState<number | undefined>(undefined)

  const campuses = useApiResource(() => listCampuses({ orgId: org_id, isActive: true }), [org_id], {
    isEmpty: (d) => d.length === 0,
  })

  const effectiveCampusId = campusId ?? session?.campus_id ?? campuses.data?.[0]?.id

  const overview = useApiResource(
    () => getSchoolOverview({ campusId: effectiveCampusId }),
    [effectiveCampusId],
    { skip: effectiveCampusId === undefined }
  )

  const data = overview.data

  return (
    <DashPageShell
      module="reports"
      title="Reports"
      description="Attendance, grades, fees and admissions for the whole school, in one place."
    >
      {(campuses.data ?? []).length > 1 && (
        <label className="flex w-fit flex-col gap-1.5">
          <span className="text-xs font-medium text-gray-500">Reporting on</span>
          <select
            id="reports-campus"
            className="px-3 py-2 bg-white nice-shadow rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-black focus:ring-offset-2 border-0"
            value={effectiveCampusId ?? ''}
            onChange={(e) => setCampusId(Number(e.target.value))}
          >
            {(campuses.data ?? []).map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </label>
      )}

      <StatGrid
        state={overview.status === 'loading' ? 'loading' : 'success'}
        columns={4}
        items={[
          {
            label: 'Attendance',
            value: data ? formatMetric(data.attendance.attendance_rate) : '—',
            hint: data ? metricHint(data.attendance.attendance_rate) : undefined,
            icon: CalendarCheck,
            tone: data?.attendance.attendance_rate.has_data ? 'positive' : 'neutral',
          },
          {
            label: 'Average grade',
            value: data ? formatMetric(data.grades.average_percentage) : '—',
            hint: data ? metricHint(data.grades.average_percentage) : undefined,
            icon: GraduationCap,
            tone: data?.grades.average_percentage.has_data ? 'positive' : 'neutral',
          },
          {
            label: 'Fees collected',
            value: data ? formatMetric(data.fees.collection_rate) : '—',
            hint: data ? metricHint(data.fees.collection_rate) : undefined,
            icon: BadgeDollarSign,
            tone: data?.fees.collection_rate.has_data ? 'positive' : 'neutral',
          },
          {
            label: 'Admissions conversion',
            value: data ? formatMetric(data.admissions.conversion_rate) : '—',
            hint: data ? metricHint(data.admissions.conversion_rate) : undefined,
            icon: UserPlus,
            tone: data?.admissions.conversion_rate.has_data ? 'positive' : 'neutral',
          },
        ]}
      />

      {/* What could not be answered, stated plainly. Without this an empty
          panel silently reads as a bad result rather than as missing data. */}
      {data && data.warnings.length > 0 && (
        <SectionCard
          title="Not enough data to report"
          icon={<Info className="size-4 text-gray-500" />}
        >
          <ul className="flex flex-col gap-2">
            {data.warnings.map((w) => (
              <li key={w} className="flex gap-2 text-sm text-gray-600">
                <span className="text-gray-300">•</span>
                <span>{w}</span>
              </li>
            ))}
          </ul>
        </SectionCard>
      )}

      <SectionCard
        id="attendance"
        title="Attendance"
        icon={<CalendarCheck className="size-4 text-gray-500" />}
        state={overview.status}
        error={overview.error}
        onRetry={overview.refetch}
        emptyTitle="No attendance recorded"
        emptyDescription="Take roll-call for a section and it will be reported here."
      >
        <DataTable
          rows={
            data
              ? [
                  { key: 'Present', count: data.attendance.present_count },
                  { key: 'Absent', count: data.attendance.absent_count },
                  { key: 'Late', count: data.attendance.late_count },
                  { key: 'Excused', count: data.attendance.excused_count },
                ]
              : []
          }
          rowKey={(row) => row.key}
          state="success"
          totalLabel={`${data?.attendance.records_counted ?? 0} record${(data?.attendance.records_counted ?? 0) === 1 ? '' : 's'} · ${data?.attendance.source_module ?? ''}`}
          columns={[
            { key: 'status', header: 'Status', render: (r) => r.key },
            { key: 'count', header: 'Records', align: 'right', render: (r) => r.count },
          ]}
        />
      </SectionCard>

      <SectionCard
        id="grades"
        title="Grade distribution"
        icon={<GraduationCap className="size-4 text-gray-500" />}
        state={overview.status}
        error={overview.error}
        onRetry={overview.refetch}
      >
        {data && Object.keys(data.grades.letter_distribution).length > 0 ? (
          <DataTable
            rows={Object.entries(data.grades.letter_distribution).map(([letter, count]) => ({
              letter,
              count,
            }))}
            rowKey={(row) => row.letter}
            state="success"
            totalLabel={`Average GPA ${formatMetric(data.grades.average_gpa)} · ${data.grades.source_module}`}
            columns={[
              { key: 'letter', header: 'Grade', render: (r) => r.letter },
              { key: 'count', header: 'Marks', align: 'right', render: (r) => r.count },
            ]}
          />
        ) : (
          <EmptyState
            title="No marks recorded"
            description={
              data?.grades.average_percentage.no_data_reason ??
              'Grades appear here once teachers enter marks against an assessment.'
            }
          />
        )}
      </SectionCard>

      <SectionCard
        id="fees"
        title="Fee collection"
        icon={<BadgeDollarSign className="size-4 text-gray-500" />}
        state={overview.status}
        error={overview.error}
        onRetry={overview.refetch}
      >
        {data && data.fees.voucher_count > 0 ? (
          <DataTable
            rows={[
              { key: 'Invoiced', amount: data.fees.total_invoiced },
              { key: 'Collected', amount: data.fees.total_collected },
              { key: 'Outstanding', amount: data.fees.total_outstanding },
            ]}
            rowKey={(row) => row.key}
            state="success"
            totalLabel={`${data.fees.voucher_count} voucher${data.fees.voucher_count === 1 ? '' : 's'} · ${data.fees.source_module}`}
            columns={[
              { key: 'label', header: '', render: (r) => r.key },
              { key: 'amount', header: 'Amount', align: 'right', render: (r) => currency(r.amount) },
            ]}
          />
        ) : (
          <EmptyState
            title="No vouchers issued"
            description={
              data?.fees.collection_rate.no_data_reason ??
              'Generate fee vouchers and collection will be reported here.'
            }
          />
        )}
      </SectionCard>

      <SectionCard
        id="admissions"
        title="Admissions funnel"
        icon={<UserPlus className="size-4 text-gray-500" />}
        state={overview.status}
        error={overview.error}
        onRetry={overview.refetch}
      >
        {data && Object.keys(data.admissions.stage_counts).length > 0 ? (
          <DataTable
            rows={Object.entries(data.admissions.stage_counts).map(([stage, count]) => ({
              stage,
              count,
            }))}
            rowKey={(row) => row.stage}
            state="success"
            totalLabel={`${data.admissions.total_leads} lead${data.admissions.total_leads === 1 ? '' : 's'} · ${data.admissions.source_module}`}
            columns={[
              {
                key: 'stage',
                header: 'Stage',
                render: (r) => r.stage.replace(/_/g, ' ').toLowerCase(),
              },
              { key: 'count', header: 'Leads', align: 'right', render: (r) => r.count },
            ]}
          />
        ) : (
          <EmptyState
            title="No inquiries recorded"
            description={
              data?.admissions.conversion_rate.no_data_reason ??
              'Admissions inquiries appear here as they come in.'
            }
          />
        )}
      </SectionCard>
    </DashPageShell>
  )
}
