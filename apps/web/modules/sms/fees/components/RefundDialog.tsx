'use client'

/**
 * Blocking decision to return money to a family, against one voucher.
 *
 * The amount is capped at what was actually PAID on the voucher, not at its
 * total: refunding more than was received would invent money. The backend
 * enforces this too — the client cap exists so a bursar is told before they
 * submit, not after.
 *
 * A reason is mandatory. A refund with no stated reason is unauditable, and
 * this is the one screen in the module that moves money back out of the
 * school.
 */

import { useState } from 'react'
import toast from 'react-hot-toast'
import { Undo2 } from 'lucide-react'
import {
  LH_GHOST_BUTTON,
  LH_INPUT,
  LH_PRIMARY_BUTTON,
  LH_SECONDARY_BUTTON,
  SchoolDialog,
  SchoolField,
} from '@/components/widgets'
import { issueRefund } from '../api'
import { money, today } from '../format'
import type { StudentFeeVoucherRead } from '../types'

/** Mirrors the `method` values the payment path uses. The backend takes a free
 * string and defaults to BANK_TRANSFER, but offering the same four the rest of
 * the module uses keeps a school's records consistent. */
const REFUND_METHODS = ['BANK_TRANSFER', 'CASH', 'CHEQUE', 'ONLINE'] as const

export interface RefundDialogProps {
  voucher: StudentFeeVoucherRead
  onRefunded?: () => void
  trigger?: React.ReactNode
}

export function RefundDialog({ voucher, onRefunded, trigger }: RefundDialogProps) {
  const [open, setOpen] = useState(false)
  const [amount, setAmount] = useState('')
  const [reason, setReason] = useState('')
  const [method, setMethod] = useState<string>('BANK_TRANSFER')
  const [refundDate, setRefundDate] = useState(today())
  const [submitting, setSubmitting] = useState(false)

  const maxRefundable = voucher.paid_amount

  async function handleSubmit() {
    const value = Number(amount)
    if (!Number.isFinite(value) || value <= 0) {
      toast.error('Enter a refund amount greater than zero.')
      return
    }
    if (value > maxRefundable) {
      toast.error(
        `This voucher has only received ${money(maxRefundable)}. A refund cannot exceed what was paid.`
      )
      return
    }
    if (!reason.trim()) {
      toast.error('Give a reason for the refund.')
      return
    }
    setSubmitting(true)
    try {
      const refund = await issueRefund({
        voucher_id: voucher.id,
        amount: value,
        reason: reason.trim(),
        method,
        refund_date: refundDate || null,
      })
      toast.success(`Refund ${refund.refund_no} issued (${money(refund.amount)}).`)
      setOpen(false)
      setAmount('')
      setReason('')
      onRefunded?.()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Could not issue that refund.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <SchoolDialog
      open={open}
      onOpenChange={setOpen}
      trigger={
        trigger ?? (
          <button type="button" className={LH_SECONDARY_BUTTON} disabled={maxRefundable <= 0}>
            <Undo2 className="size-4" /> <span>Refund</span>
          </button>
        )
      }
      title="Issue a refund"
      description={`Voucher ${voucher.voucher_no} has received ${money(maxRefundable)}. A refund cannot exceed that.`}
      footer={
        <>
          <button
            type="button"
            className={LH_GHOST_BUTTON}
            onClick={() => setOpen(false)}
            disabled={submitting}
          >
            Cancel
          </button>
          <button
            type="button"
            className={LH_PRIMARY_BUTTON}
            onClick={handleSubmit}
            disabled={submitting || maxRefundable <= 0}
          >
            <span>{submitting ? 'Issuing…' : 'Issue refund'}</span>
          </button>
        </>
      }
    >
      {maxRefundable <= 0 ? (
        <div className="rounded-lg bg-amber-50 px-3 py-2.5 text-sm text-amber-900">
          Nothing has been paid on this voucher, so there is nothing to refund.
        </div>
      ) : null}

      <SchoolField
        id="refund-amount"
        label="Amount"
        required
        help={`At most ${money(maxRefundable)}.`}
      >
        <input
          id="refund-amount"
          type="number"
          min="0"
          max={maxRefundable}
          step="0.01"
          className={LH_INPUT}
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          placeholder="0.00"
        />
      </SchoolField>

      <SchoolField
        id="refund-reason"
        label="Reason"
        required
        help="Recorded against the refund permanently. Say what happened, not just “refund”."
      >
        <input
          id="refund-reason"
          className={LH_INPUT}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="Overpaid term 2 by one instalment"
        />
      </SchoolField>

      <div className="grid grid-cols-2 gap-4">
        <SchoolField id="refund-method" label="Method">
          <select
            id="refund-method"
            className={LH_INPUT}
            value={method}
            onChange={(e) => setMethod(e.target.value)}
          >
            {REFUND_METHODS.map((m) => (
              <option key={m} value={m}>
                {m.replace(/_/g, ' ').toLowerCase()}
              </option>
            ))}
          </select>
        </SchoolField>

        <SchoolField id="refund-date" label="Refund date">
          <input
            id="refund-date"
            type="date"
            className={LH_INPUT}
            value={refundDate}
            onChange={(e) => setRefundDate(e.target.value)}
          />
        </SchoolField>
      </div>
    </SchoolDialog>
  )
}
