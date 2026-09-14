'use client'

/**
 * Splits a term or year fee into scheduled instalments.
 *
 * Each instalment becomes a REAL voucher, which is the design decision worth
 * knowing when reading this form: payments, receipts, the ledger and late-fee
 * accrual all work on them unchanged, and a family that misses instalment 2 is
 * charged a late fee on instalment 2 rather than on the whole year.
 *
 * The backend requires between 2 and 24 due dates and rejects one — a single
 * "instalment" is just an ordinary voucher. The form therefore starts with two
 * rows and will not let you delete below two.
 */

import { useState } from 'react'
import toast from 'react-hot-toast'
import { CalendarClock, Plus, X } from 'lucide-react'
import {
  LH_GHOST_BUTTON,
  LH_INPUT,
  LH_PRIMARY_BUTTON,
  LH_SECONDARY_BUTTON,
  SchoolDialog,
  SchoolField,
} from '@/components/widgets'
import { createInstallmentPlan } from '../api'
import { today } from '../format'
import type { FeeStructureRead } from '../types'

const MIN_INSTALMENTS = 2
const MAX_INSTALMENTS = 24

/** Monthly dates starting one month out, as a sensible default a bursar can
 * then edit. Uses UTC arithmetic so a date never shifts by a day. */
function defaultDueDates(count: number): string[] {
  const base = new Date()
  return Array.from({ length: count }, (_, i) => {
    const d = new Date(Date.UTC(base.getUTCFullYear(), base.getUTCMonth() + i + 1, 1))
    return d.toISOString().slice(0, 10)
  })
}

export interface InstallmentPlanDialogProps {
  studentId: number
  campusId?: number
  structures: FeeStructureRead[]
  onCreated?: () => void
  trigger?: React.ReactNode
}

export function InstallmentPlanDialog({
  studentId,
  campusId,
  structures,
  onCreated,
  trigger,
}: InstallmentPlanDialogProps) {
  const [open, setOpen] = useState(false)
  const [name, setName] = useState('')
  const [structureId, setStructureId] = useState<number | ''>('')
  const [issueDate, setIssueDate] = useState(today())
  const [dueDates, setDueDates] = useState<string[]>(() => defaultDueDates(MIN_INSTALMENTS))
  const [applyConcessions, setApplyConcessions] = useState(true)
  const [submitting, setSubmitting] = useState(false)

  const selected = structures.find((s) => s.id === structureId)

  function updateDate(index: number, value: string) {
    setDueDates((prev) => prev.map((d, i) => (i === index ? value : d)))
  }

  function addDate() {
    if (dueDates.length >= MAX_INSTALMENTS) return
    setDueDates((prev) => [...prev, ''])
  }

  function removeDate(index: number) {
    if (dueDates.length <= MIN_INSTALMENTS) return
    setDueDates((prev) => prev.filter((_, i) => i !== index))
  }

  async function handleSubmit() {
    if (!name.trim()) {
      toast.error('Name the plan so staff can recognise it.')
      return
    }
    if (structureId === '') {
      toast.error('Choose the fee structure this plan splits.')
      return
    }
    const filled = dueDates.map((d) => d.trim()).filter(Boolean)
    if (filled.length !== dueDates.length) {
      toast.error('Every instalment needs a due date.')
      return
    }
    if (filled.length < MIN_INSTALMENTS) {
      toast.error('A plan needs at least two instalments.')
      return
    }
    const sorted = [...filled].sort()
    if (sorted.join() !== filled.join()) {
      toast.error('Instalment dates must be in order, earliest first.')
      return
    }
    if (new Set(filled).size !== filled.length) {
      toast.error('Two instalments cannot fall on the same date.')
      return
    }

    setSubmitting(true)
    try {
      const plan = await createInstallmentPlan({
        student_id: studentId,
        fee_structure_id: structureId,
        name: name.trim(),
        issue_date: issueDate,
        due_dates: filled,
        campus_id: campusId ?? null,
        apply_concessions: applyConcessions,
      })
      toast.success(
        `Created “${plan.name}” — ${plan.installment_count} instalments.`
      )
      setOpen(false)
      setName('')
      setStructureId('')
      setDueDates(defaultDueDates(MIN_INSTALMENTS))
      onCreated?.()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Could not create that plan.')
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
            <CalendarClock className="size-4" /> <span>New instalment plan</span>
          </button>
        )
      }
      title="Split a fee into instalments"
      description="Each instalment becomes its own voucher, so a missed instalment is chased on its own rather than the whole year."
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
            disabled={submitting || structures.length === 0}
          >
            <span>
              {submitting ? 'Creating…' : `Create ${dueDates.length} instalments`}
            </span>
          </button>
        </>
      }
    >
      {structures.length === 0 ? (
        <div className="rounded-lg bg-amber-50 px-3 py-2.5 text-sm text-amber-900">
          No fee structures exist yet. Create one on the Vouchers tab first — a plan splits a
          priced structure, so there is nothing to split until then.
        </div>
      ) : null}

      <SchoolField id="plan-name" label="Plan name" required help="e.g. “Grade 9 — 2026 monthly”.">
        <input
          id="plan-name"
          className={LH_INPUT}
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Grade 9 — 2026 monthly"
        />
      </SchoolField>

      <SchoolField
        id="plan-structure"
        label="Fee structure"
        required
        help={selected ? `Total to split: Rs. ${selected.total_amount.toFixed(2)}` : undefined}
      >
        <select
          id="plan-structure"
          className={LH_INPUT}
          value={structureId}
          onChange={(e) => setStructureId(e.target.value === '' ? '' : Number(e.target.value))}
        >
          <option value="">Choose a structure…</option>
          {structures.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name} — Rs. {s.total_amount.toFixed(2)}
            </option>
          ))}
        </select>
      </SchoolField>

      <SchoolField id="plan-issue" label="Issue date" required>
        <input
          id="plan-issue"
          type="date"
          className={LH_INPUT}
          value={issueDate}
          onChange={(e) => setIssueDate(e.target.value)}
        />
      </SchoolField>

      <SchoolField
        id="plan-dates"
        label={`Instalment due dates (${dueDates.length})`}
        required
        help="Between 2 and 24, earliest first. The amount is divided across them by the server."
      >
        <div className="flex flex-col gap-2">
          {dueDates.map((d, i) => (
            <div key={i} className="flex items-center gap-2">
              <span className="w-6 text-xs tabular-nums text-gray-500">{i + 1}.</span>
              <input
                id={`plan-date-${i}`}
                type="date"
                className={LH_INPUT}
                value={d}
                onChange={(e) => updateDate(i, e.target.value)}
              />
              <button
                type="button"
                className={LH_GHOST_BUTTON}
                onClick={() => removeDate(i)}
                disabled={dueDates.length <= MIN_INSTALMENTS}
                aria-label={`Remove instalment ${i + 1}`}
              >
                <X className="size-4" />
              </button>
            </div>
          ))}
          <button
            type="button"
            className={LH_SECONDARY_BUTTON}
            onClick={addDate}
            disabled={dueDates.length >= MAX_INSTALMENTS}
          >
            <Plus className="size-4" /> <span>Add instalment</span>
          </button>
        </div>
      </SchoolField>

      <SchoolField
        id="plan-concessions"
        label="Concessions"
        help="Applies this student's active concessions to the instalment amounts."
      >
        <label className="flex items-center gap-2 text-sm text-gray-700">
          <input
            id="plan-concessions"
            type="checkbox"
            checked={applyConcessions}
            onChange={(e) => setApplyConcessions(e.target.checked)}
          />
          <span>Apply active concessions</span>
        </label>
      </SchoolField>
    </SchoolDialog>
  )
}
