'use client'

/**
 * Blocking decision to record a payment against a voucher
 * (DESIGN-SYSTEM.md §7: "Modal | Blocking decision | Title states the
 * decision. Primary action names the verb.") -- posts to the real
 * `POST /sms/fees/payments` endpoint.
 */

import { useState } from 'react'
import toast from 'react-hot-toast'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { recordPayment } from '../api'
import type { PaymentMethod, StudentFeeVoucherRead } from '../types'

const PAYMENT_METHODS: PaymentMethod[] = ['CASH', 'BANK_TRANSFER', 'CARD', 'ONLINE', 'CHEQUE']

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
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>{trigger ?? <Button size="sm">Pay voucher</Button>}</DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Record payment for {voucher.voucher_no}</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 px-6 py-2">
          <p className="text-sm text-muted-foreground">
            Outstanding balance: <span className="font-semibold text-foreground">Rs. {voucher.balance_amount.toFixed(2)}</span>
          </p>
          <div className="space-y-1.5">
            <Label htmlFor="pay-amount">Amount paid</Label>
            <Input id="pay-amount" type="number" min={0} step="0.01" value={amount} onChange={(e) => setAmount(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="pay-method">Payment method</Label>
            <select
              id="pay-method"
              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-xs focus-visible:outline-hidden focus-visible:ring-1 focus-visible:ring-ring"
              value={method}
              onChange={(e) => setMethod(e.target.value as PaymentMethod)}
            >
              {PAYMENT_METHODS.map((m) => (
                <option key={m} value={m}>
                  {m.replace('_', ' ')}
                </option>
              ))}
            </select>
          </div>
        </div>
        <DialogFooter className="px-6 pb-6">
          <Button variant="outline" onClick={() => setOpen(false)} disabled={submitting}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={submitting}>
            {submitting ? 'Recording…' : 'Record payment'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
