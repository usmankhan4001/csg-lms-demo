'use client'

/**
 * Blocking decision to record a payment against a voucher
 * (DESIGN-SYSTEM.md §7: "Modal | Blocking decision | Title states the
 * decision. Primary action names the verb.") -- posts to the real
 * `POST /sms/fees/payments` endpoint.
 */

import { useState } from 'react'
import toast from 'react-hot-toast'
import {
  LH_GHOST_BUTTON,
  LH_INPUT,
  LH_PRIMARY_BUTTON,
  LH_SECONDARY_BUTTON,
  SchoolDialog,
  SchoolField,
} from '@/components/widgets'
import { recordPayment } from '../api'
import type { PaymentMethod, StudentFeeVoucherRead } from '../types'

/** The backend's real `PaymentMethod` enum. `CARD` used to be offered here
 * and would have been rejected on submit -- it is not a value the API accepts. */
const PAYMENT_METHODS: PaymentMethod[] = ['CASH', 'BANK_TRANSFER', 'ONLINE', 'CHEQUE']

export interface PayVoucherDialogProps {
  voucher: StudentFeeVoucherRead
  onPaid?: () => void
  trigger?: React.ReactNode
}

export function PayVoucherDialog({ voucher, onPaid, trigger }: PayVoucherDialogProps) {
  const [open, setOpen] = useState(false)
  const [amount, setAmount] = useState(String(voucher.balance_amount))
  const [method, setMethod] = useState<PaymentMethod>('ONLINE')
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit() {
    const amountPaid = Number(amount)
    if (!Number.isFinite(amountPaid) || amountPaid <= 0) {
      toast.error('Enter a valid payment amount.')
      return
    }
    setSubmitting(true)
    try {
      await recordPayment({ voucher_id: voucher.id, amount_paid: amountPaid, payment_method: method })
      toast.success(`Payment of Rs. ${amountPaid.toFixed(2)} recorded for ${voucher.voucher_no}.`)
      setOpen(false)
      onPaid?.()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Could not record payment.')
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
          <button type="button" className={LH_SECONDARY_BUTTON}>
            <span>Pay voucher</span>
          </button>
        )
      }
      title={`Record payment for ${voucher.voucher_no}`}
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
            disabled={submitting}
          >
            <span>{submitting ? 'Recording…' : 'Record payment'}</span>
          </button>
        </>
      }
    >
      <p className="text-sm text-gray-500">
        Outstanding balance:{' '}
        <span className="font-semibold text-gray-900">
          Rs. {voucher.balance_amount.toFixed(2)}
        </span>
      </p>

      <SchoolField id="pay-amount" label="Amount paid">
        <input
          id="pay-amount"
          type="number"
          min={0}
          step="0.01"
          className={LH_INPUT}
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
        />
      </SchoolField>

      <SchoolField id="pay-method" label="Payment method">
        <select
          id="pay-method"
          className={LH_INPUT}
          value={method}
          onChange={(e) => setMethod(e.target.value as PaymentMethod)}
        >
          {PAYMENT_METHODS.map((m) => (
            <option key={m} value={m}>
              {m.replace('_', ' ')}
            </option>
          ))}
        </select>
      </SchoolField>
    </SchoolDialog>
  )
}
