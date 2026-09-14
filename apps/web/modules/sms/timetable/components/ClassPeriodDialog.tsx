'use client'

/**
 * Define a class period — the daily time slots every timetable entry sits in.
 *
 * Exists so "no class periods defined yet" is not a dead end. A timetable slot
 * requires a `period_id`, so without this the timetable module blocks at the
 * first step with an instruction the user has no way to act on -- the same
 * trap as a fee dialog saying "no fee structures exist" and offering no way to
 * create one.
 */

import { useState } from 'react'
import { Clock } from 'lucide-react'
import {
  LH_INPUT,
  LH_PRIMARY_BUTTON,
  LH_SECONDARY_BUTTON,
  SchoolDialog,
  SchoolField,
} from '@/components/widgets'
import { ApiError } from '@/lib/api/api-client'
import { createClassPeriod } from '../api'
import type { ClassPeriodRead } from '../types'

export interface ClassPeriodDialogProps {
  campusId?: number
  existingPeriods: ClassPeriodRead[]
  onCreated: () => void
}

export function ClassPeriodDialog({ campusId, existingPeriods, onCreated }: ClassPeriodDialogProps) {
  const [open, setOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const nextNumber =
    existingPeriods.reduce((max, p) => Math.max(max, p.period_number ?? 0), 0) + 1

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const form = new FormData(e.currentTarget)
    const periodNumber = Number(form.get('period_number'))
    const startTime = String(form.get('start_time') ?? '').trim()
    const endTime = String(form.get('end_time') ?? '').trim()
    const name = String(form.get('name') ?? '').trim()

    if (!periodNumber || periodNumber < 1) {
      setError('Period number must be 1 or more.')
      return
    }
    if (!startTime || !endTime) {
      setError('Start and end time are both required.')
      return
    }
    if (endTime <= startTime) {
      // Plain string compare is correct for zero-padded HH:MM.
      setError('The end time must be after the start time.')
      return
    }

    setSaving(true)
    setError(null)
    try {
      await createClassPeriod({
        campus_id: campusId ?? null,
        period_number: periodNumber,
        start_time: startTime,
        end_time: endTime,
        name: name || null,
      })
      setOpen(false)
      onCreated()
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.kind === 'permission_denied'
            ? 'You need school-admin access to define class periods.'
            : err.message
          : 'Could not save the period.'
      )
    } finally {
      setSaving(false)
    }
  }

  return (
    <SchoolDialog
      open={open}
      onOpenChange={setOpen}
      trigger={
        <button type="button" className={LH_SECONDARY_BUTTON}>
          <Clock className="size-4" /> <span>Add period</span>
        </button>
      }
      title="Add a class period"
      description="The daily time slots lessons are scheduled into — period 1, period 2, and so on."
      onSubmit={handleSubmit}
      footer={
        <button type="submit" disabled={saving} className={LH_PRIMARY_BUTTON}>
          <span>{saving ? 'Saving…' : 'Create'}</span>
        </button>
      }
    >
      <SchoolField id="period-number" label="Period number" required>
        <input
          id="period-number"
          name="period_number"
          type="number"
          min={1}
          defaultValue={nextNumber}
          className={LH_INPUT}
        />
      </SchoolField>

      <SchoolField id="period-start" label="Start time" required>
        <input id="period-start" name="start_time" type="time" defaultValue="08:00" className={LH_INPUT} />
      </SchoolField>

      <SchoolField id="period-end" label="End time" required>
        <input id="period-end" name="end_time" type="time" defaultValue="08:45" className={LH_INPUT} />
      </SchoolField>

      <SchoolField id="period-name" label="Name" help="Optional — e.g. “Assembly” or “Break”.">
        <input id="period-name" name="name" className={LH_INPUT} placeholder={`Period ${nextNumber}`} />
      </SchoolField>

      {error && <p className="text-sm text-rose-600">{error}</p>}
    </SchoolDialog>
  )
}
