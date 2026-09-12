'use client'

/**
 * Parent fee vouchers page -- thin composition over the real `sms_fees`
 * module. "My children" comes from the real school session's
 * `children_ids` (see `lib/api/useSchoolSession.ts`).
 */

import { CreditCard } from 'lucide-react'
import { DataTable, EmptyState, SectionCard, StatGrid } from '@/components/widgets'
import { StatusChip } from '@/components/widgets'
import { useApiResource } from '@/lib/api/useApiResource'
import { useSchoolSession } from '@/lib/api/useSchoolSession'
import { getStudentFeeLedger } from '@/modules/sms/fees/api'
import { PayVoucherDialog } from '@/modules/sms/fees/components/PayVoucherDialog'
import type { StudentFeeVoucherRead, VoucherStatus } from '@/modules/sms/fees/types'

const VOUCHER_TONE: Record<VoucherStatus, 'positive' | 'caution' | 'critical' | 'neutral'> = {
  PAID: 'positive',
  PARTIALLY_PAID: 'caution',
  UNPAID: 'neutral',
  OVERDUE: 'critical',
  CANCELLED: 'neutral',
}

interface ChildVoucherRow extends StudentFeeVoucherRead {
  child_student_id: number
}

export default function ParentFeesPage() {
  const { session, checked } = useSchoolSession()
  const childrenIds = session?.children_ids ?? []
  const ready = checked && childrenIds.length > 0

  const ledgers = useApiResource(
    () => Promise.all(childrenIds.map((id) => getStudentFeeLedger(id).catch(() => null))),
    [childrenIds.join(',')],
    { skip: !ready }
  )

  const vouchers: ChildVoucherRow[] = (ledgers.data ?? [])
    .flatMap((ledger, i) => (ledger ? ledger.vouchers.map((v) => ({ ...v, child_student_id: childrenIds[i] })) : []))
    .sort((a, b) => (a.due_date < b.due_date ? 1 : -1))

  const totalOutstanding = (ledgers.data ?? []).reduce((sum, l) => sum + (l?.total_outstanding ?? 0), 0)
  const totalPaid = (ledgers.data ?? []).reduce((sum, l) => sum + (l?.total_paid ?? 0), 0)
  const overdueCount = vouchers.filter((v) => v.status === 'OVERDUE').length

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-foreground">Fee Vouchers & Bills</h1>
        <p className="text-sm text-muted-foreground">Every voucher and payment for your children, in one place.</p>
      </div>

      {!checked ? (
        <StatGrid state="loading" items={[]} />
      ) : !ready ? (
        <EmptyState
          tone="caution"
          title="No children linked to this session"
          description="Ask your school admin to link your account as a guardian for your child's record."
        />
      ) : (
        <>
          <StatGrid
            state={ledgers.status === 'loading' ? 'loading' : 'success'}
            columns={3}
            items={[
              { label: 'Outstanding balance', value: `Rs. ${totalOutstanding.toFixed(2)}`, icon: CreditCard, tone: totalOutstanding > 0 ? 'caution' : 'positive' },
              { label: 'Paid to date', value: `Rs. ${totalPaid.toFixed(2)}`, icon: CreditCard, tone: 'positive' },
              { label: 'Overdue vouchers', value: overdueCount, icon: CreditCard, tone: overdueCount > 0 ? 'critical' : 'neutral' },
            ]}
          />

          <SectionCard
            title="Vouchers"
            icon={<CreditCard className="size-4 text-muted-foreground" />}
            state={ledgers.status}
            error={ledgers.error}
            onRetry={ledgers.refetch}
            emptyTitle="No vouchers issued yet"
            emptyDescription="Fee vouchers will appear here once the school issues one for your child."
          >
            <DataTable
              rows={vouchers}
              rowKey={(row) => row.id}
              state="success"
              totalLabel={`${vouchers.length} voucher${vouchers.length === 1 ? '' : 's'}`}
              columns={[
                { key: 'child', header: 'Child', render: (r) => `Student #${r.child_student_id}` },
                { key: 'voucher', header: 'Voucher #', render: (r) => r.voucher_no },
                { key: 'due', header: 'Due date', render: (r) => r.due_date },
                { key: 'total', header: 'Total', align: 'right', render: (r) => `Rs. ${r.total_amount.toFixed(2)}` },
                { key: 'balance', header: 'Balance', align: 'right', render: (r) => `Rs. ${r.balance_amount.toFixed(2)}` },
                { key: 'status', header: 'Status', render: (r) => <StatusChip label={r.status.replace('_', ' ')} tone={VOUCHER_TONE[r.status]} /> },
                {
                  key: 'action',
                  header: '',
                  align: 'right',
                  render: (r) =>
                    r.balance_amount > 0 ? <PayVoucherDialog voucher={r} onPaid={ledgers.refetch} /> : <span className="text-xs text-muted-foreground">Settled</span>,
                },
              ]}
            />
          </SectionCard>
        </>
      )}
    </div>
  )
}
