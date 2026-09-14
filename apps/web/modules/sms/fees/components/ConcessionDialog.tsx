'use client'

/**
 * Authorises a fee concession for one named student.
 *
 * Two constraints come straight from the backend and are enforced here so the
 * bursar is told before submitting rather than by a 400:
 *
 *  - EXACTLY ONE of percentage or fixed amount. Both would be ambiguous;
 *    neither would be a concession that reduces nothing.
 *  - A REASON IS MANDATORY. A flat discount number can express the amount but
 *    never the justification, and "why does this family pay less" is precisely
 *    what a bursar is asked at audit.
 *
 * The concession attaches to a named student rather than being inferred from,
 * say, sibling count — which child counts as the "second child" is a school
 * policy question, and guessing it would quietly award or withhold money from
 * a real family.
 */

import { useState } from 'react'
import toast from 'react-hot-toast'
import { Percent } from 'lucide-react'
import {
  LH_GHOST_BUTTON,
  LH_INPUT,
  LH_PRIMARY_BUTTON,
  LH_SECONDARY_BUTTON,
  SchoolDialog,
  SchoolField,
} from '@/components/widgets'
import { createConcession } from '../api'
import { humanEnum } from '../format'
import type { ConcessionKind } from '../types'

const KINDS: ConcessionKind[] = ['SIBLING', 'SCHOLARSHIP', 'HARDSHIP', 'STAFF_CHILD', 'OTHER']

type Basis = 'percentage' | 'fixed'

export interface ConcessionDialogProps {
  studentId: number
  campusId?: number
  onCreated?: () => void
  trigger?: React.ReactNode
}

export function ConcessionDialog({
  studentId,
  campusId,
  onCreated,
  trigger,
}: ConcessionDialogProps) {
  const [open, setOpen] = useState(false)
  const [kind, setKind] = useState<ConcessionKind>('SIBLING')
  const [basis, setBasis] = useState<Basis>('percentage')
  const [percentage, setPercentage] = useState('')
  const [fixedAmount, setFixedAmount] = useState('')
  const [reason, setReason] = useState('')
  const [validFrom, setValidFrom] = useState('')
  const [validUntil, setValidUntil] = useState('')
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit() {
    if (!reason.trim()) {
      toast.error('Give the reason this family pays less.')
      return
    }

    let percentageValue: number | null = null
    let fixedValue: number | null = null

    if (basis === 'percentage') {
      const p = Number(percentage)
      if (!Number.isFinite(p) || p <= 0 || p > 100) {
        toast.error('Enter a percentage between 0 and 100.')
        return
      }
      percentageValue = p
    } else {
      const f = Number(fixedAmount)
      if (!Number.isFinite(f) || f <= 0) {
        toast.error('Enter a fixed amount greater than zero.')
        return
      }
      fixedValue = f
    }

    if (validFrom && validUntil && validUntil < validFrom) {
      toast.error('The end date cannot be before the start date.')
      return
    }

    setSubmitting(true)
    try {
      await createConcession({
        student_id: studentId,
        kind,
        percentage: percentageValue,
        fixed_amount: fixedValue,
        reason: reason.trim(),
        campus_id: campusId ?? null,
        valid_from: validFrom || null,
        valid_until: validUntil || null,
      })
      toast.success('Concession authorised.')
      setOpen(false)
      setPercentage('')
      setFixedAmount('')
      setReason('')
      onCreated?.()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Could not authorise that concession.')
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
            <Percent className="size-4" /> <span>Authorise concession</span>
          </button>
        )
      }
      title="Authorise a fee concession"
      description="Recorded against this student with your name on it. Applies to vouchers generated afterwards."
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
            <span>{submitting ? 'Authorising…' : 'Authorise'}</span>
          </button>
        </>
      }
    >
      <SchoolField id="conc-kind" label="Kind" required>
        <select
          id="conc-kind"
          className={LH_INPUT}
          value={kind}
          onChange={(e) => setKind(e.target.value as ConcessionKind)}
        >
          {KINDS.map((k) => (
            <option key={k} value={k}>
              {humanEnum(k)}
            </option>
          ))}
        </select>
      </SchoolField>

      <SchoolField
        id="conc-basis"
        label="Reduce by"
        required
        help="A concession is either a share of the fee or a flat sum — never both."
      >
        <select
          id="conc-basis"
          className={LH_INPUT}
          value={basis}
          onChange={(e) => setBasis(e.target.value as Basis)}
        >
          <option value="percentage">A percentage of the fee</option>
          <option value="fixed">A fixed amount</option>
        </select>
      </SchoolField>

      {basis === 'percentage' ? (
        <SchoolField id="conc-percentage" label="Percentage" required>
          <input
            id="conc-percentage"
            type="number"
            min="0"
            max="100"
            step="0.01"
            className={LH_INPUT}
            value={percentage}
            onChange={(e) => setPercentage(e.target.value)}
            placeholder="25"
          />
        </SchoolField>
      ) : (
        <SchoolField id="conc-fixed" label="Fixed amount" required>
          <input
            id="conc-fixed"
            type="number"
            min="0"
            step="0.01"
            className={LH_INPUT}
            value={fixedAmount}
            onChange={(e) => setFixedAmount(e.target.value)}
            placeholder="5000"
          />
        </SchoolField>
      )}

      <SchoolField
        id="conc-reason"
        label="Reason"
        required
        help="Kept permanently. This is what the school shows when asked to justify the reduction."
      >
        <input
          id="conc-reason"
          className={LH_INPUT}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="Second child enrolled, per sibling policy 2026"
        />
      </SchoolField>

      <div className="grid grid-cols-2 gap-4">
        <SchoolField id="conc-from" label="Valid from" help="Leave blank for immediately.">
          <input
            id="conc-from"
            type="date"
            className={LH_INPUT}
            value={validFrom}
            onChange={(e) => setValidFrom(e.target.value)}
          />
        </SchoolField>

        <SchoolField id="conc-until" label="Valid until" help="Leave blank for no end date.">
          <input
            id="conc-until"
            type="date"
            className={LH_INPUT}
            value={validUntil}
            onChange={(e) => setValidUntil(e.target.value)}
          />
        </SchoolField>
      </div>
    </SchoolDialog>
  )
}
