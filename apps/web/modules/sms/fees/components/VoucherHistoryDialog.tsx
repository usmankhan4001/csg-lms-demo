'use client'

/**
 * A voucher's money trail — every mutation, in order, with what the balance was
 * before and after.
 *
 * The trail is append-only on the server: no endpoint updates or deletes a row
 * in it, because a trail that can be rewritten is not a trail. This dialog
 * therefore has no edit affordances at all, deliberately.
 *
 * It exists for the conversation that starts "we paid that in March" — a bursar
 * can show exactly what was received, when, and what it did to the balance.
 */

import { useState } from 'react'
import { History } from 'lucide-react'
import {
  DataTable,
  LH_GHOST_BUTTON,
  LH_SECONDARY_BUTTON,
  SchoolDialog,
  StatusChip,
} from '@/components/widgets'
import type { DataTableColumn, StatusTone } from '@/components/widgets'
import { useApiResource } from '@/lib/api/useApiResource'
import { getVoucherHistory } from '../api'
import { humanEnum, isoDateTime, money, moneyOrUnknown } from '../format'
import type { FeeChangeAction, FeeChangeEventRead, StudentFeeVoucherRead } from '../types'

const ACTION_TONE: Record<FeeChangeAction, StatusTone> = {
  VOUCHER_CREATED: 'neutral',
  PAYMENT_RECORDED: 'positive',
  REFUND_ISSUED: 'caution',
  CONCESSION_APPLIED: 'neutral',
  TRANSFER_MATCHED: 'positive',
}

export interface VoucherHistoryDialogProps {
  voucher: StudentFeeVoucherRead
  trigger?: React.ReactNode
}

export function VoucherHistoryDialog({ voucher, trigger }: VoucherHistoryDialogProps) {
  const [open, setOpen] = useState(false)

  const history = useApiResource(() => getVoucherHistory(voucher.id), [voucher.id, open], {
    skip: !open,
  })

  const columns: DataTableColumn<FeeChangeEventRead>[] = [
    {
      key: 'when',
      header: 'When',
      render: (e) => <span className="tabular-nums text-xs">{isoDateTime(e.created_at)}</span>,
    },
    {
      key: 'action',
      header: 'What happened',
      render: (e) => <StatusChip tone={ACTION_TONE[e.action]} label={humanEnum(e.action)} />,
    },
    {
      key: 'amount',
      header: 'Amount',
      align: 'right',
      // moneyOrUnknown, not money: several actions legitimately carry no
      // amount, and rendering those as "Rs. 0.00" would read as a zero-value
      // payment rather than as "this event was not about a sum of money".
      render: (e) => <span className="tabular-nums">{moneyOrUnknown(e.amount)}</span>,
    },
    {
      key: 'balance',
      header: 'Balance after',
      align: 'right',
      render: (e) => (
        <span className="tabular-nums">
          {e.previous_balance !== null && e.previous_balance !== undefined ? (
            <span className="text-gray-400">{money(e.previous_balance)} → </span>
          ) : null}
          {moneyOrUnknown(e.new_balance)}
        </span>
      ),
    },
    {
      key: 'reason',
      header: 'Reason',
      render: (e) => e.reason || <span className="text-gray-400">—</span>,
    },
  ]

  return (
    <SchoolDialog
      open={open}
      onOpenChange={setOpen}
      trigger={
        trigger ?? (
          <button type="button" className={LH_SECONDARY_BUTTON}>
            <History className="size-4" /> <span>History</span>
          </button>
        )
      }
      title={`Money trail — ${voucher.voucher_no}`}
      description="Append-only. Nothing in this system edits or removes an entry here."
      footer={
        <button type="button" className={LH_GHOST_BUTTON} onClick={() => setOpen(false)}>
          Close
        </button>
      }
    >
      <DataTable
        columns={columns}
        rows={history.data ?? []}
        rowKey={(e) => e.id}
        state={history.status}
        error={history.error}
        onRetry={history.refetch}
        emptyTitle="No entries recorded"
        emptyDescription="Nothing has changed on this voucher since it was raised."
        emptyIcon={History}
      />
    </SchoolDialog>
  )
}
