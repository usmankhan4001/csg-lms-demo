'use client'

/**
 * Admissions funnel: where leads currently stand, and how many convert.
 *
 * Takes neither a date range nor a term, because the API offers neither — a
 * funnel is a snapshot of current occupancy, not a window. Adding a date
 * picker here would let a reader ask a question the endpoint cannot answer
 * and then quietly ignore it.
 *
 * `conversion_rate` is a `Metric`. A school with no enquiries has NO
 * conversion rate — "0% conversion" says the marketing failed, which is a
 * very different message from "nobody has entered an enquiry yet". This
 * codebase already shipped "0% Enrolled Conversion Rate" on the admissions
 * board of a school with no leads; this page is where that must not recur.
 */

import { useState } from 'react'
import { TrendingUp, UserPlus, UserMinus, PauseCircle } from 'lucide-react'
import { DashPageShell, EmptyState, SectionCard, StatGrid } from '@/components/widgets'
import { useApiResource } from '@/lib/api/useApiResource'
import { useSchoolSession } from '@/lib/api/useSchoolSession'
import { listCampuses } from '@/modules/sms/campus/api'
import { getAdmissionsFunnel } from '@/modules/sms/reports/api'
import { ReportFilters } from '@/modules/sms/reports/components/ReportFilters'
import { formatMetric, metricHint, metricTone } from '@/modules/sms/reports/presentation'

interface Props {
  org_id: number
  orgslug: string
}

export default function AdmissionsReportClient({ org_id }: Props) {
  const { session } = useSchoolSession()
  const [campusId, setCampusId] = useState<number | undefined>(undefined)

  const campuses = useApiResource(() => listCampuses({ orgId: org_id, isActive: true }), [org_id], {
    isEmpty: (d) => d.length === 0,
  })

  const effectiveCampusId = campusId ?? session?.campus_id ?? campuses.data?.[0]?.id

  const report = useApiResource(
    () => getAdmissionsFunnel({ campusId: effectiveCampusId }),
    [effectiveCampusId],
    { skip: effectiveCampusId === undefined, isEmpty: () => false }
  )

  const data = report.data
  const hasLeads = (data?.total_leads ?? 0) > 0
  const stages = Object.entries(data?.stage_counts ?? {})
  const maxStage = stages.reduce((m, [, n]) => Math.max(m, n), 0)

  return (
    <DashPageShell
      module="reports"
      title="Admissions funnel"
      description="Where enquiries currently sit, and how many become enrolments."
    >
      <ReportFilters
        idPrefix="report-admissions"
        campuses={campuses.data ?? []}
        campusId={effectiveCampusId}
        onCampusChange={setCampusId}
      />

      <StatGrid
        state={report.status === 'error' ? 'error' : report.status === 'loading' ? 'loading' : 'success'}
        error={report.error}
        onRetry={report.refetch}
        columns={4}
        items={[
          {
            label: 'Conversion rate',
            value: data ? formatMetric(data.conversion_rate) : '—',
            hint: data ? metricHint(data.conversion_rate) : undefined,
            icon: TrendingUp,
            tone: data ? metricTone(data.conversion_rate) : 'neutral',
          },
          {
            label: 'Enrolled',
            value: data ? String(data.enrolled_count) : '—',
            icon: UserPlus,
            tone: 'neutral',
          },
          {
            label: 'Lost',
            value: data ? String(data.lost_count) : '—',
            icon: UserMinus,
            tone: 'neutral',
          },
          {
            label: 'Stalled',
            value: data ? String(data.stalled_count) : '—',
            hint: 'Looped back for re-nurture',
            icon: PauseCircle,
            tone: 'neutral',
          },
        ]}
      />

      <SectionCard
        title="Funnel occupancy"
        description={
          hasLeads
            ? `${data?.total_leads} lead${data?.total_leads === 1 ? '' : 's'} from ${data?.source_module}.`
            : undefined
        }
        state={report.status === 'loading' ? 'loading' : 'success'}
      >
        {!hasLeads || stages.length === 0 || maxStage === 0 ? (
          <EmptyState
            title="No enquiries yet"
            description={
              data?.conversion_rate.no_data_reason ??
              'No leads have been entered, so there is no funnel to show and no conversion rate to calculate.'
            }
          />
        ) : (
          <ul className="flex flex-col gap-2">
            {stages.map(([stage, count]) => (
              <li key={stage} className="flex items-center gap-3">
                <span className="w-40 shrink-0 truncate text-sm font-medium text-gray-700">
                  {stage}
                </span>
                <div className="h-2 flex-1 overflow-hidden rounded-full bg-gray-100">
                  <div
                    className="h-full rounded-full bg-gray-800"
                    style={{ width: `${Math.round((count / maxStage) * 100)}%` }}
                  />
                </div>
                <span className="w-10 shrink-0 text-right text-sm tabular-nums text-gray-600">
                  {count}
                </span>
              </li>
            ))}
          </ul>
        )}
      </SectionCard>
    </DashPageShell>
  )
}
