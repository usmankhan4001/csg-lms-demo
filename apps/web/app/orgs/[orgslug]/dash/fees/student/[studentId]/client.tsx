'use client'

/**
 * One family's fee account — the screen a bursar opens when a parent rings up.
 *
 * Pulls together the four things that were each reachable only through the API
 * before: the ledger, instalment plans, concessions, and each voucher's money
 * trail. Refunds are issued from here too, because a refund is always about one
 * named voucher on one named account.
 *
 * THE RULE THIS SCREEN IS BUILT AROUND: a student with no fee record owes
 * NOTHING KNOWN, which is not the same as owing zero. A family nobody has
 * billed must never render as "Rs. 0.00 outstanding" — a bursar reading that
 * concludes the account is settled and stops chasing. Every total below comes
 * from the server's own ledger summary, and the empty case says so in words.
 */

import { useState } from 'react'
import Link from 'next/link'
import {
  ArrowLeft,
  BadgeDollarSign,
  CalendarClock,
  Percent,
  Receipt,
  Wallet,
} from 'lucide-react'
import {
  DashPageShell,
  DataTable,
  EmptyState,
  LH_SECONDARY_BUTTON,
  SectionCard,
  StatGrid,
  StatusChip,
} from '@/components/widgets'
import type { DataTableColumn, StatusTone } from '@/components/widgets'
import { useApiResource } from '@/lib/api/useApiResource'
import { listCampuses } from '@/modules/sms/campus/api'
import {
  getStudentFeeLedger,
  listFeeReminders,
  listFeeStructures,
  listStudentConcessions,
  listStudentInstallmentPlans,
} from '@/modules/sms/fees/api'
import { ConcessionDialog } from '@/modules/sms/fees/components/ConcessionDialog'
import { InstallmentPlanDialog } from '@/modules/sms/fees/components/InstallmentPlanDialog'
import { PayVoucherDialog } from '@/modules/sms/fees/components/PayVoucherDialog'
import { RefundDialog } from '@/modules/sms/fees/components/RefundDialog'
import { VoucherHistoryDialog } from '@/modules/sms/fees/components/VoucherHistoryDialog'
import {
  concessionValue,
  daysOverdue,
  humanEnum,
  isoDate,
  money,
} from '@/modules/sms/fees/format'
import type {
  ConcessionRead,
  FeePaymentReceiptRead,
  InstallmentPlanSummary,
  StudentFeeVoucherRead,
  VoucherStatus,
} from '@/modules/sms/fees/types'

interface Props {
  org_id: number
  orgslug: string
  studentId: number
}

const STATUS_TONE: Record<VoucherStatus, StatusTone> = {
  PAID: 'positive',
  PARTIAL: 'caution',
  UNPAID: 'neutral',
  CANCELLED: 'neutral',
}

const PLAN_TONE: Record<InstallmentPlanSummary['status'], StatusTone> = {
  ACTIVE: 'caution',
  COMPLETED: 'positive',
  CANCELLED: 'neutral',
}

export default function StudentFeeAccountClient({ orgslug, studentId }: Props) {
  const [refreshKey, setRefreshKey] = useState(0)
  const bump = () => setRefreshKey((k) => k + 1)

  const ledger = useApiResource(
    () => getStudentFeeLedger(studentId),
    [studentId, refreshKey],
    // A ledger with no vouchers is a REAL, meaningful response -- it means
    // nobody has billed this family. Treating it as "empty" would render the
    // generic empty state and lose that distinction, so it never counts as
    // empty here.
    { isEmpty: () => false }
  )
  const plans = useApiResource(
    () => listStudentInstallmentPlans(studentId),
    [studentId, refreshKey]
  )
  const concessions = useApiResource(
    () => listStudentConcessions(studentId),
    [studentId, refreshKey]
  )
  const reminders = useApiResource(
    () => listFeeReminders({ studentId }),
    [studentId, refreshKey]
  )
  const structures = useApiResource(() => listFeeStructures(), [])
  const campuses = useApiResource(() => listCampuses(), [])
  const campusId = campuses.data?.[0]?.id

  const account = ledger.data
  const vouchers = account?.vouchers ?? []
  const receipts = account?.receipts ?? []
  const hasAnyRecord = vouchers.length > 0

  const voucherColumns: DataTableColumn<StudentFeeVoucherRead>[] = [
    {
      key: 'voucher',
      header: 'Voucher',
      render: (v) => <span className="font-mono text-xs">{v.voucher_no}</span>,
    },
    {
      key: 'due',
      header: 'Due',
      render: (v) => {
        const age = daysOverdue(v.due_date)
        return (
          <span className="tabular-nums">
            {isoDate(v.due_date)}
            {age !== null && v.balance_amount > 0 ? (
              <span className="ms-1.5 text-xs text-red-700">{age}d late</span>
            ) : null}
          </span>
        )
      },
    },
    {
      key: 'total',
      header: 'Billed',
      align: 'right',
      render: (v) => <span className="tabular-nums">{money(v.total_amount)}</span>,
    },
    {
      key: 'paid',
      header: 'Paid',
      align: 'right',
      render: (v) => <span className="tabular-nums">{money(v.paid_amount)}</span>,
    },
    {
      key: 'balance',
      header: 'Outstanding',
      align: 'right',
      render: (v) => (
        <span className="tabular-nums font-medium">{money(v.balance_amount)}</span>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (v) => <StatusChip tone={STATUS_TONE[v.status]} label={humanEnum(v.status)} />,
    },
    {
      key: 'actions',
      header: '',
      align: 'right',
      render: (v) => (
        <div className="flex flex-wrap justify-end gap-1.5">
          {v.balance_amount > 0 && v.status !== 'CANCELLED' ? (
            <PayVoucherDialog voucher={v} onPaid={bump} />
          ) : null}
          {v.paid_amount > 0 ? <RefundDialog voucher={v} onRefunded={bump} /> : null}
          <VoucherHistoryDialog voucher={v} />
        </div>
      ),
    },
  ]

  const receiptColumns: DataTableColumn<FeePaymentReceiptRead>[] = [
    {
      key: 'receipt',
      header: 'Receipt',
      render: (r) => <span className="font-mono text-xs">{r.receipt_no}</span>,
    },
    {
      key: 'date',
      header: 'Paid',
      render: (r) => <span className="tabular-nums">{isoDate(r.payment_date)}</span>,
    },
    {
      key: 'amount',
      header: 'Amount',
      align: 'right',
      render: (r) => <span className="tabular-nums font-medium">{money(r.amount_paid)}</span>,
    },
    {
      key: 'method',
      header: 'Method',
      render: (r) => humanEnum(r.payment_method),
    },
    {
      key: 'ref',
      header: 'Reference',
      render: (r) => (
        <span className="font-mono text-xs">
          {r.transaction_ref || <span className="text-gray-400">None</span>}
        </span>
      ),
    },
  ]

  const concessionColumns: DataTableColumn<ConcessionRead>[] = [
    {
      key: 'kind',
      header: 'Kind',
      render: (c) => <StatusChip tone="neutral" label={humanEnum(c.kind)} />,
    },
    {
      key: 'value',
      header: 'Reduction',
      align: 'right',
      render: (c) => (
        <span className="tabular-nums font-medium">
          {concessionValue(c.percentage, c.fixed_amount)}
        </span>
      ),
    },
    { key: 'reason', header: 'Reason', render: (c) => c.reason },
    {
      key: 'window',
      header: 'Applies',
      render: (c) => (
        <span className="tabular-nums text-xs">
          {c.valid_from ? isoDate(c.valid_from) : 'Immediately'} —{' '}
          {c.valid_until ? isoDate(c.valid_until) : 'no end date'}
        </span>
      ),
    },
    {
      key: 'active',
      header: 'Status',
      render: (c) =>
        c.is_active ? (
          <StatusChip tone="positive" label="Active" />
        ) : (
          <StatusChip tone="neutral" label="Inactive" />
        ),
    },
  ]

  const planColumns: DataTableColumn<InstallmentPlanSummary>[] = [
    { key: 'name', header: 'Plan', render: (p) => <span className="font-medium">{p.name}</span> },
    {
      key: 'progress',
      header: 'Instalments paid',
      render: (p) => (
        <span className="tabular-nums">
          {p.paid_count} of {p.installment_count}
        </span>
      ),
    },
    {
      key: 'total',
      header: 'Plan total',
      align: 'right',
      render: (p) => <span className="tabular-nums">{money(p.total_amount)}</span>,
    },
    {
      key: 'balance',
      header: 'Outstanding',
      align: 'right',
      render: (p) => (
        <span className="tabular-nums font-medium">{money(p.balance_amount)}</span>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (p) => <StatusChip tone={PLAN_TONE[p.status]} label={humanEnum(p.status)} />,
    },
  ]

  return (
    <DashPageShell
      title={`Fee account — student #${studentId}`}
      description="Everything billed, paid, reduced or returned on this family's account."
      module="fees"
      breadcrumbs={
        <Link
          href={`/orgs/${orgslug}/dash/fees/arrears`}
          className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-900"
        >
          <ArrowLeft className="size-4" /> <span>Back to arrears</span>
        </Link>
      }
      action={
        <div className="flex flex-wrap gap-2">
          <ConcessionDialog studentId={studentId} campusId={campusId} onCreated={bump} />
          <InstallmentPlanDialog
            studentId={studentId}
            campusId={campusId}
            structures={structures.data ?? []}
            onCreated={bump}
          />
        </div>
      }
    >
      {/* Totals come from the server's ledger summary, never from summing the
          rows below -- the two must never be able to disagree. */}
      <StatGrid
        state={ledger.status === 'loading' ? 'loading' : 'success'}
        columns={3}
        items={[
          {
            label: 'Invoiced',
            value: hasAnyRecord ? money(account?.total_invoiced ?? 0) : 'Nothing billed',
            icon: Receipt,
            tone: 'neutral',
          },
          {
            label: 'Paid',
            value: hasAnyRecord ? money(account?.total_paid ?? 0) : 'No payments',
            icon: Wallet,
            tone: 'positive',
          },
          {
            label: 'Outstanding',
            value: hasAnyRecord ? money(account?.total_outstanding ?? 0) : 'Not known',
            icon: BadgeDollarSign,
            tone:
              hasAnyRecord && (account?.total_outstanding ?? 0) > 0 ? 'caution' : 'positive',
          },
        ]}
      />

      {ledger.status === 'success' && !hasAnyRecord ? (
        <EmptyState
          icon={Receipt}
          tone="caution"
          title="No fee record for this student"
          description="Nobody has billed this family yet. That is not the same as a settled account — there is nothing to settle. Issue a voucher or set up an instalment plan to start one."
        />
      ) : null}

      <SectionCard
        title="Vouchers"
        description="Everything this family has been billed."
        icon={<Receipt className="size-4 text-gray-500" />}
      >
        <DataTable
          columns={voucherColumns}
          rows={vouchers}
          rowKey={(v) => v.id}
          state={ledger.status === 'success' && vouchers.length === 0 ? 'empty' : ledger.status}
          error={ledger.error}
          onRetry={ledger.refetch}
          emptyTitle="No vouchers raised"
          emptyDescription="This family has not been billed for anything."
          emptyIcon={Receipt}
        />
      </SectionCard>

      <SectionCard
        title="Instalment plans"
        description="Each instalment is its own voucher, chased on its own schedule."
        icon={<CalendarClock className="size-4 text-gray-500" />}
      >
        <DataTable
          columns={planColumns}
          rows={plans.data ?? []}
          rowKey={(p) => p.plan_id}
          state={plans.status}
          error={plans.error}
          onRetry={plans.refetch}
          emptyTitle="No instalment plans"
          emptyDescription="This family pays each voucher in full rather than in scheduled parts."
          emptyIcon={CalendarClock}
        />
      </SectionCard>

      <SectionCard
        title="Concessions"
        description="Why this family pays less, and who authorised it."
        icon={<Percent className="size-4 text-gray-500" />}
      >
        <DataTable
          columns={concessionColumns}
          rows={concessions.data ?? []}
          rowKey={(c) => c.id}
          state={concessions.status}
          error={concessions.error}
          onRetry={concessions.refetch}
          emptyTitle="No concessions"
          emptyDescription="This family is billed the full published fee."
          emptyIcon={Percent}
        />
      </SectionCard>

      <SectionCard
        title="Receipts"
        description="Money actually received against this account."
        icon={<Wallet className="size-4 text-gray-500" />}
      >
        <DataTable
          columns={receiptColumns}
          rows={receipts}
          rowKey={(r) => r.id}
          state={ledger.status === 'success' && receipts.length === 0 ? 'empty' : ledger.status}
          error={ledger.error}
          onRetry={ledger.refetch}
          emptyTitle="No payments received"
          emptyDescription="Nothing has been paid against this account yet."
          emptyIcon={Wallet}
        />
      </SectionCard>

      <SectionCard
        title="Reminders sent"
        description="What this family was actually told about their balance."
        icon={<Receipt className="size-4 text-gray-500" />}
        state={reminders.status === 'loading' ? 'loading' : 'success'}
      >
        {(reminders.data ?? []).length === 0 ? (
          <p className="text-sm text-gray-500">
            This family has never been chased about a fee balance.
          </p>
        ) : (
          <ul className="flex flex-col gap-1.5 text-sm">
            {(reminders.data ?? []).map((r) => (
              <li key={r.id} className="flex flex-wrap items-center gap-2">
                <span className="tabular-nums text-gray-500">{isoDate(r.sent_on)}</span>
                <StatusChip
                  tone={r.delivered < r.recipients ? 'critical' : 'positive'}
                  label={
                    r.delivered < r.recipients
                      ? `${humanEnum(r.kind)} — only ${r.delivered} of ${r.recipients} delivered`
                      : `${humanEnum(r.kind)} — delivered`
                  }
                />
                <span className="text-gray-500">balance was {money(r.balance_at_send)}</span>
              </li>
            ))}
          </ul>
        )}
      </SectionCard>
    </DashPageShell>
  )
}
