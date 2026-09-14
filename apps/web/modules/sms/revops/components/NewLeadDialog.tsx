'use client'

/**
 * Capture a walk-in or phone inquiry by hand.
 *
 * The funnel had exactly one way in: `POST /webhook/{channel}`, a
 * server-to-server intake guarded by a shared secret for website forms and
 * ad platforms. A parent who walked through the door or rang the office had
 * no route into the pipeline at all, which is the most common way a school
 * actually meets a family.
 *
 * Consent is captured at intake and defaults to OFF for both channels
 * (matching `LeadBase` -- schemas/sms_revops.py:32-35, "no consent assumed").
 * The checkboxes are worded as a record of what the parent actually agreed
 * to, not as a preference the office sets on their behalf.
 */

import { useState } from 'react'
import { UserPlus } from 'lucide-react'
import {
  LH_INPUT,
  LH_PRIMARY_BUTTON,
  LH_SECONDARY_BUTTON,
  SchoolDialog,
  SchoolField,
} from '@/components/widgets'
import { ApiError } from '@/lib/api/api-client'
import { createLead } from '../api'
import type { LeadSource } from '../types'

/** Sources a human would pick when typing a lead in. The ad-platform values
 *  (META_ADS / GOOGLE_ADS) are omitted: those arrive via the webhook, and
 *  offering them here would let someone mislabel where a lead came from,
 *  which then skews the source attribution the funnel reports on. */
const MANUAL_SOURCES: { value: LeadSource; label: string }[] = [
  { value: 'WALK_IN', label: 'Walk-in' },
  { value: 'REFERRAL', label: 'Referral' },
  { value: 'WHATSAPP', label: 'WhatsApp' },
  { value: 'WEBSITE_FORM', label: 'Website form' },
]

export interface NewLeadDialogProps {
  campusId?: number
  onCreated: () => void
}

export function NewLeadDialog({ campusId, onCreated }: NewLeadDialogProps) {
  const [open, setOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const form = new FormData(e.currentTarget)
    const get = (k: string) => String(form.get(k) ?? '').trim()

    const parent_name = get('parent_name')
    const student_name = get('student_name')
    const email = get('email')
    const phone = get('phone')
    const grade_applying_for = get('grade_applying_for')

    // The API requires all five; check here so the parent gets a pointed
    // message rather than a 422 listing field names.
    const missing = [
      !parent_name && 'parent name',
      !student_name && 'student name',
      !email && 'email',
      !phone && 'phone',
      !grade_applying_for && 'grade',
    ].filter(Boolean)
    if (missing.length > 0) {
      setError(`Still needed: ${missing.join(', ')}.`)
      return
    }

    setSaving(true)
    setError(null)
    try {
      await createLead({
        parent_name,
        student_name,
        email,
        phone,
        grade_applying_for,
        campus_id: campusId ?? null,
        source: (get('source') || 'WALK_IN') as LeadSource,
        budget_range: get('budget_range') || null,
        notes: get('notes') || null,
        whatsapp_consent: form.get('whatsapp_consent') === 'on',
        email_consent: form.get('email_consent') === 'on',
      })
      setOpen(false)
      onCreated()
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.kind === 'permission_denied'
            ? 'You do not have access to add leads.'
            : err.message
          : 'Could not save this lead. Try again.'
      )
    } finally {
      setSaving(false)
    }
  }

  return (
    <SchoolDialog
      open={open}
      onOpenChange={setOpen}
      onSubmit={handleSubmit}
      title="Add an inquiry"
      description="For a walk-in, a phone call, or anything that did not arrive through the website."
      trigger={
        <button type="button" className={LH_PRIMARY_BUTTON}>
          <UserPlus className="size-4" /> <span>Add inquiry</span>
        </button>
      }
      footer={
        <>
          <button
            type="button"
            className={LH_SECONDARY_BUTTON}
            onClick={() => setOpen(false)}
            disabled={saving}
          >
            <span>Cancel</span>
          </button>
          <button type="submit" className={LH_PRIMARY_BUTTON} disabled={saving}>
            <span>{saving ? 'Saving…' : 'Add inquiry'}</span>
          </button>
        </>
      }
    >
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <SchoolField id="lead-parent-name" label="Parent name" required>
          <input id="lead-parent-name" name="parent_name" className={LH_INPUT} />
        </SchoolField>
        <SchoolField id="lead-student-name" label="Student name" required>
          <input id="lead-student-name" name="student_name" className={LH_INPUT} />
        </SchoolField>
        <SchoolField id="lead-phone" label="Phone" required>
          <input id="lead-phone" name="phone" className={LH_INPUT} inputMode="tel" />
        </SchoolField>
        <SchoolField id="lead-email" label="Email" required>
          <input id="lead-email" name="email" type="email" className={LH_INPUT} />
        </SchoolField>
        <SchoolField id="lead-grade" label="Grade applying for" required>
          <input
            id="lead-grade"
            name="grade_applying_for"
            className={LH_INPUT}
            placeholder="Grade 9"
          />
        </SchoolField>
        <SchoolField id="lead-source" label="How did they reach us">
          <select id="lead-source" name="source" className={LH_INPUT} defaultValue="WALK_IN">
            {MANUAL_SOURCES.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        </SchoolField>
      </div>

      <SchoolField
        id="lead-budget"
        label="Budget range"
        help="Optional. Feeds the budget-fit factor of the lead score."
      >
        <input id="lead-budget" name="budget_range" className={LH_INPUT} />
      </SchoolField>

      <SchoolField id="lead-notes" label="Notes">
        <textarea id="lead-notes" name="notes" rows={3} className={LH_INPUT} />
      </SchoolField>

      <fieldset className="rounded-lg bg-gray-50 p-3">
        <legend className="px-1 text-xs font-semibold text-gray-600">
          Consent given by the parent
        </legend>
        <p className="mb-2 text-xs text-gray-500">
          Only tick what they actually agreed to. Automated nurture will not contact them on a
          channel left unticked.
        </p>
        <label htmlFor="lead-consent-wa" className="flex items-center gap-2 text-sm text-gray-700">
          <input id="lead-consent-wa" name="whatsapp_consent" type="checkbox" className="size-4" />
          May contact on WhatsApp
        </label>
        <label
          htmlFor="lead-consent-email"
          className="mt-1.5 flex items-center gap-2 text-sm text-gray-700"
        >
          <input id="lead-consent-email" name="email_consent" type="checkbox" className="size-4" />
          May contact by email
        </label>
      </fieldset>

      {error && <p className="text-sm text-rose-600">{error}</p>}
    </SchoolDialog>
  )
}
