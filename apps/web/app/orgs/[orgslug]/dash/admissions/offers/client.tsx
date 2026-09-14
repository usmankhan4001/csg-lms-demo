'use client'

/**
 * Offers -- every scholarship and tuition offer issued, and where it stands.
 *
 * This is the money end of admissions: an offer represents a discount the
 * school has committed to, so a registrar needs to see the whole book, not
 * one lead at a time.
 *
 * `OfferStatus` is exactly DRAFT | SENT | ACCEPTED | DECLINED
 * (db/sms_revops.py:81). There is deliberately NO expired state, so nothing
 * here branches on one -- the `valid_until` date is shown and a reader draws
 * their own conclusion rather than the UI inventing a status the API cannot
 * produce.
 */

import { useMemo, useState } from 'react'
import Link from 'next/link'
import { BadgePercent, CalendarClock, FileCheck2, Send } from 'lucide-react'
import {
  DashPageShell,
  DataTable,
  LH_INPUT,
  SectionCard,
  StatGrid,
  StatusChip,
} from '@/components/widgets'
import { useApiResource } from '@/lib/api/useApiResource'
import { useSchoolSession } from '@/lib/api/useSchoolSession'
import { listLeads, listOffers } from '@/modules/sms/revops/api'
import { OFFER_TONE, formatAmount, formatDate } from '@/modules/sms/revops/presentation'
import type { OfferStatus, ScholarshipOfferRead } from '@/modules/sms/revops/types'

interface Props {
  org_id: number
  orgslug: string
}

const STATUSES: OfferStatus[] = ['DRAFT', 'SENT', 'ACCEPTED', 'DECLINED']

export default function AdmissionsOffersClient({ orgslug }: Props) {
  const { session } = useSchoolSession()
  const [status, setStatus] = useState<OfferStatus | ''>('')

  const campusId = session?.campus_id ?? undefined

  const offers = useApiResource(
    () => listOffers({ campusId, status: status || undefined }),
    [campusId, status],
    { isEmpty: (d) => d.length === 0 }
  )

  // Offers carry only lead_id, so names come from the lead list. One extra
  // request rather than showing "Lead #12" -- a registrar needs the family.
  const leads = useApiResource(() => listLeads({ campus_id: campusId }), [campusId], {
    isEmpty: () => false,
  })

  const leadName = useMemo(() => {
    const map = new Map<number, string>()
    for (const l of leads.data ?? []) map.set(l.id, `${l.student_name} (${l.parent_name})`)
    return map
  }, [leads.data])

  const stats = useMemo(() => {
    const all = offers.data ?? []
    const by = (s: OfferStatus) => all.filter((o) => o.status === s).length
    return {
      total: all.length,
      sent: by('SENT'),
      accepted: by('ACCEPTED'),
      declined: by('DECLINED'),
    }
  }, [offers.data])

  return (
    <DashPageShell
      module="admissions"
      title="Offers"
      description="Scholarship and tuition offers issued to families, and where each one stands."
    >
      <StatGrid
        state={offers.status === 'loading' ? 'loading' : 'success'}
        columns={4}
        items={[
          { label: 'Offers', value: stats.total, icon: FileCheck2, tone: 'neutral' },
          { label: 'Awaiting reply', value: stats.sent, icon: Send, tone: 'caution' },
          { label: 'Accepted', value: stats.accepted, icon: BadgePercent, tone: 'positive' },
          { label: 'Declined', value: stats.declined, icon: CalendarClock, tone: 'neutral' },
        ]}
      />

      <SectionCard
        title="All offers"
        icon={<FileCheck2 className="size-4 text-gray-500" />}
        state={offers.status}
        error={offers.error}
        onRetry={offers.refetch}
        emptyTitle="No offers issued"
        emptyDescription="No scholarship or tuition offer has been generated yet. Offers are issued from a lead."
        action={
          <label className="flex items-center gap-2 text-xs text-gray-500">
            <span>Status</span>
            <select
              id="offers-status"
              className={LH_INPUT}
              value={status}
              onChange={(e) => setStatus(e.target.value as OfferStatus | '')}
            >
              <option value="">All</option>
              {STATUSES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </label>
        }
      >
        <DataTable
          rows={offers.data ?? []}
          rowKey={(o: ScholarshipOfferRead) => o.id}
          state="success"
          totalLabel={`${(offers.data ?? []).length} offer${
            (offers.data ?? []).length === 1 ? '' : 's'
          }`}
          columns={[
            {
              key: 'family',
              header: 'Family',
              render: (o) => (
                <Link
                  href={`/dash/admissions/leads/${o.lead_id}`}
                  className="font-medium text-gray-900 hover:underline"
                >
                  {leadName.get(o.lead_id) ?? `Lead #${o.lead_id}`}
                </Link>
              ),
            },
            {
              key: 'discount',
              header: 'Discount',
              align: 'right',
              render: (o) => `${o.tuition_discount_percentage}%`,
            },
            {
              key: 'amount',
              header: 'Final tuition',
              align: 'right',
              render: (o) => formatAmount(o.final_tuition_amount),
            },
            { key: 'valid', header: 'Valid until', render: (o) => formatDate(o.valid_until) },
            {
              key: 'status',
              header: 'Status',
              render: (o) => <StatusChip label={o.status} tone={OFFER_TONE[o.status]} />,
            },
            { key: 'created', header: 'Issued', render: (o) => formatDate(o.created_at) },
          ]}
        />
      </SectionCard>
    </DashPageShell>
  )
}
