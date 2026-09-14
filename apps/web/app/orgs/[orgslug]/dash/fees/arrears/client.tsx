'use client'

/**
 * Arrears worklist -- who owes money, how long they have owed it, and what has
 * already been done about it.
 *
 * ONE BACKEND REALITY SHAPES THIS SCREEN: there is no arrears endpoint.
 * `GET /sms/fees/vouchers` filters only by `student_id` and `status`, so
 * "overdue" is derived here from `due_date` against today and `balance_amount`
 * against zero. That derivation is honest for a school-sized voucher list, but
 * it means the whole list is fetched and narrowed in the browser; a school with
 * tens of thousands of live vouchers would need a real server-side filter.
 * Reported rather than hidden -- see the note under the table.
 *
 * "Overdue" is deliberately not a voucher status. The backend enum is
 * UNPAID/PARTIAL/PAID/CANCELLED, and a voucher becomes overdue by the passage
 * of time rather than by anyone setting a field.
 */

import { useState } from 'react'
import { AlarmClock, BadgeDollarSign, Receipt, Users } from 'lucide-react'
import Link from 'next/link'
import {
  DashPageShell,
  DataTable,
  LH_SECONDARY_BUTTON,
  SectionCard,
  StatGrid,
  StatusChip,
} from '@/components/widgets'
import type { DataTableColumn, StatusTone } from '@/components/widgets'
import { useApiResource } from '@/lib/api/useApiResource'
import { listVouchers } from '@/modules/sms/fees/api'
import { daysOverdue, isoDate, money } from '@/modules/sms/fees/format'
import type { StudentFeeVoucherRead } from '@/modules/sms/fees/types'

interface Props {
  org_id: number
  orgslug: string
}

/** Aging buckets. A bursar chases a 90-day debt differently from a 5-day one,
 * so the list is banded rather than just sorted. */
const BUCKETS = [
  { id: 'all', label: 'All overdue', min: 1, max: Infinity },
  { id: '1-30', label: '1–30 days', min: 1, max: 30 },
  { id: '31-60', label: '31–60 days', min: 31, max: 60 },
  { id: '61-90', label: '61–90 days', min: 61, max: 90 },
  { id: '90+', label: 'Over 90 days', min: 91, max: Infinity },
] as const

type BucketId = (typeof BUCKETS)[number]['id']

function ageTone(days: number): StatusTone {
  if (days > 90) return 'critical'
  if (days > 30) return 'caution'
  return 'neutral'
}

export default function FeesArrearsClient({ orgslug }: Props) {
  const [bucket, setBucket] = useState<BucketId>('all')

  // Fetched unfiltered because the endpoint offers no date or balance filter.
  const vouchers = useApiResource(() => listVouchers(), [])

  const all = vouchers.data ?? []

  // A voucher is in arrears when it is past its due date AND still owes money.
  // Both conditions matter: a PAID voucher past its due date is not arrears,
  // and an unpaid voucher due next week is not either.
  const overdue = all
    .map((v) => ({ voucher: v, age: daysOverdue(v.due_date) }))
    .filter(
      (r): r is { voucher: StudentFeeVoucherRead; age: number } =>
        r.age !== null && r.voucher.balance_amount > 0 && r.voucher.status !== 'CANCELLED'
    )
    .sort((a, b) => b.age - a.age)

  const active = BUCKETS.find((b) => b.id === bucket) ?? BUCKETS[0]
  const rows = overdue.filter((r) => r.age >= active.min && r.age <= active.max)

  // These sum the VISIBLE LIST, which is a property of what the bursar is
  // looking at, not a ledger balance. A single family's account total still
  // comes from the server's own ledger summary.
  const outstanding = rows.reduce((s, r) => s + r.voucher.balance_amount, 0)
  const families = new Set(rows.map((r) => r.voucher.student_id)).size
  const oldest = rows.length > 0 ? rows[0].age : null

  const columns: DataTableColumn<{ voucher: StudentFeeVoucherRead; age: number }>[] = [
    {
      key: 'age',
      header: 'Overdue',
      render: (r) => (
        <StatusChip
          tone={ageTone(r.age)}
          label={`${r.age} day${r.age === 1 ? '' : 's'}`}
        />
      ),
    },
    {
      key: 'voucher',
      header: 'Voucher',
      render: (r) => <span className="font-mono text-xs">{r.voucher.voucher_no}</span>,
    },
    {
      key: 'student',
      header: 'Student',
      render: (r) => (
        <Link
          href={`/orgs/${orgslug}/dash/fees/student/${r.voucher.student_id}`}
          className="text-sm font-medium text-gray-900 underline-offset-2 hover:underline"
        >
          Student #{r.voucher.student_id}
        </Link>
      ),
    },
    {
      key: 'due',
      header: 'Was due',
      render: (r) => <span className="tabular-nums">{isoDate(r.voucher.due_date)}</span>,
    },
    {
      key: 'billed',
      header: 'Billed',
      align: 'right',
      render: (r) => <span className="tabular-nums">{money(r.voucher.total_amount)}</span>,
    },
    {
      key: 'paid',
      header: 'Paid',
      align: 'right',
      render: (r) => <span className="tabular-nums">{money(r.voucher.paid_amount)}</span>,
    },
    {
      key: 'balance',
      header: 'Outstanding',
      align: 'right',
      render: (r) => (
        <span className="tabular-nums font-medium text-gray-900">
          {money(r.voucher.balance_amount)}
        </span>
      ),
    },
    {
      key: 'lateFee',
      header: 'Late fee charged',
      align: 'right',
      render: (r) =>
        r.voucher.late_fee_applied > 0 ? (
          <span className="tabular-nums">{money(r.voucher.late_fee_applied)}</span>
        ) : (
          <span className="text-gray-400">None</span>
        ),
    },
    {
      key: 'action',
      header: '',
      align: 'right',
      render: (r) => (
        <Link
          href={`/orgs/${orgslug}/dash/fees/student/${r.voucher.student_id}`}
          className={LH_SECONDARY_BUTTON}
        >
          <Receipt className="size-4" /> <span>Open account</span>
        </Link>
      ),
    },
  ]

  return (
    <DashPageShell
      title="Arrears"
      description="Vouchers past their due date with money still outstanding, oldest first."
      module="fees"
    >
      <StatGrid
        state={vouchers.status === 'loading' ? 'loading' : 'success'}
        columns={3}
        items={[
          {
            label: 'Outstanding in this band',
            value: money(outstanding),
            icon: BadgeDollarSign,
            tone: outstanding > 0 ? 'caution' : 'positive',
          },
          {
            label: 'Families affected',
            value: String(families),
            icon: Users,
            tone: families > 0 ? 'caution' : 'positive',
          },
          {
            label: 'Oldest debt',
            // Never "0 days" -- an empty band means nothing is overdue in it,
            // which is a different statement from "overdue by zero days".
            value: oldest === null ? 'Nothing overdue' : `${oldest} days`,
            icon: AlarmClock,
            tone: oldest !== null && oldest > 90 ? 'critical' : oldest !== null ? 'caution' : 'positive',
          },
        ]}
      />

      <SectionCard title="Age of debt" icon={<AlarmClock className="size-4 text-gray-500" />}>
        <div className="flex flex-wrap gap-2">
          {BUCKETS.map((b) => {
            const count = overdue.filter((r) => r.age >= b.min && r.age <= b.max).length
            const selected = b.id === bucket
            return (
              <button
                key={b.id}
                type="button"
                id={`arrears-bucket-${b.id}`}
                onClick={() => setBucket(b.id)}
                aria-pressed={selected}
                className={
                  selected
                    ? 'rounded-lg bg-gray-900 px-3 py-1.5 text-sm font-medium text-white'
                    : 'rounded-lg bg-white px-3 py-1.5 text-sm text-gray-700 nice-shadow hover:bg-gray-50'
                }
              >
                {b.label}
                <span className={selected ? 'ms-1.5 text-white/70' : 'ms-1.5 text-gray-400'}>
                  {count}
                </span>
              </button>
            )
          })}
        </div>
      </SectionCard>

      <SectionCard
        title={active.label}
        description="Every row is a family who has been billed and has not settled."
        icon={<Receipt className="size-4 text-gray-500" />}
      >
        <DataTable
          columns={columns}
          rows={rows}
          rowKey={(r) => r.voucher.id}
          state={vouchers.status}
          error={vouchers.error}
          onRetry={vouchers.refetch}
          emptyTitle={
            all.length === 0 ? 'No vouchers issued yet' : 'Nothing overdue in this band'
          }
          emptyDescription={
            all.length === 0
              ? 'Issue fee vouchers from the Vouchers tab. Until then there is nothing that could be overdue.'
              : 'Every family in this age band has settled, or has not reached its due date.'
          }
          emptyIcon={Receipt}
          totalLabel={
            rows.length > 0
              ? `${rows.length} voucher${rows.length === 1 ? '' : 's'} across ${families} famil${families === 1 ? 'y' : 'ies'}`
              : undefined
          }
        />
        <p className="mt-3 text-xs text-gray-500">
          Overdue status is worked out in this screen from each voucher&rsquo;s due date, because
          the fees API has no arrears filter. The whole voucher list is fetched and narrowed here,
          which is fine at school scale but would need a server-side filter for a very large school.
        </p>
      </SectionCard>
    </DashPageShell>
  )
}
