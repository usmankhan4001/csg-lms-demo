'use client'

/**
 * Fee collection over a date range: billed against collected.
 *
 * `collection_rate` is a `Metric` and may have no value. The distinction is
 * sharper here than anywhere else in reporting: a bursar reading
 * "Rs. 0.00 outstanding" stops chasing families, while the truth is usually
 * that no vouchers have been raised yet. Amounts are plain numbers from the
 * API and are rendered through the shared `currency` helper; only the RATE is
 * a Metric, because a rate over zero vouchers is not zero — it is unanswerable.
 */

import { useState } from 'react'
import { BadgeDollarSign, Receipt, TrendingUp, Wallet } from 'lucide-react'
import { DashPageShell, EmptyState, SectionCard, StatGrid, StatusChip } from '@/components/widgets'
import { useApiResource } from '@/lib/api/useApiResource'
import { useSchoolSession } from '@/lib/api/useSchoolSession'
import { listCampuses } from '@/modules/sms/campus/api'
import { getFeeCollection } from '@/modules/sms/reports/api'
import { ReportFilters } from '@/modules/sms/reports/components/ReportFilters'
import { currency, formatMetric, metricHint, metricTone } from '@/modules/sms/reports/presentation'

interface Props {
  org_id: number
  orgslug: string
}

export default function FeesReportClient({ org_id }: Props) {
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
      getFeeCollection({
        campusId: effectiveCampusId,
        dateFrom: dateFrom || undefined,
        dateTo: dateTo || undefined,
      }),
    [effectiveCampusId, dateFrom, dateTo],
    { skip: effectiveCampusId === undefined, isEmpty: () => false }
  )

  const data = report.data
  const hasVouchers = (data?.voucher_count ?? 0) > 0
  const statuses = Object.entries(data?.status_breakdown ?? {})

  return (
    <DashPageShell
      module="reports"
      title="Fee collection"
      description="What was billed, what came in, and what is still outstanding."
    >
      <ReportFilters
        idPrefix="report-fees"
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
            label: 'Collection rate',
            value: data ? formatMetric(data.collection_rate) : '—',
            hint: data ? metricHint(data.collection_rate) : undefined,
            icon: TrendingUp,
            tone: data ? metricTone(data.collection_rate) : 'neutral',
          },
          {
            // Amounts are only shown once vouchers exist. Rendering
            // "Rs. 0.00" for a school that has raised nothing states a
            // settled account where there is simply no account yet.
            label: 'Invoiced',
            value: data && hasVouchers ? currency(data.total_invoiced) : 'Nothing billed',
            icon: Receipt,
            tone: 'neutral',
          },
          {
            label: 'Collected',
            value: data && hasVouchers ? currency(data.total_collected) : 'No payments',
            icon: Wallet,
            tone: 'neutral',
          },
          {
            label: 'Outstanding',
            value: data && hasVouchers ? currency(data.total_outstanding) : 'Not known',
            hint: hasVouchers ? undefined : 'No vouchers raised for this range',
            icon: BadgeDollarSign,
            tone: 'neutral',
          },
        ]}
      />

      <SectionCard
        title="Vouchers by status"
        description={
          hasVouchers
            ? `${data?.voucher_count} voucher${data?.voucher_count === 1 ? '' : 's'} from ${data?.source_module}.`
            : undefined
        }
        state={report.status === 'loading' ? 'loading' : 'success'}
      >
        {!hasVouchers || statuses.length === 0 ? (
          <EmptyState
            title="No fee vouchers in this range"
            description={
              data?.collection_rate.no_data_reason ??
              'Nothing has been billed for these dates, so there is no collection rate to report.'
            }
          />
        ) : (
          <ul className="flex flex-wrap gap-3">
            {statuses.map(([status, count]) => (
              <li key={status} className="flex items-center gap-2">
                <StatusChip label={status} />
                <span className="text-sm tabular-nums text-gray-600">{count}</span>
              </li>
            ))}
          </ul>
        )}
      </SectionCard>
    </DashPageShell>
  )
}
