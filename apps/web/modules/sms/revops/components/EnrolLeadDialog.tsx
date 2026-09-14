'use client'

/**
 * Enrol a won lead as a real student -- the seam between admissions and the
 * school proper.
 *
 * `POST /revops/leads/{id}/enroll` (sms_revops.py:255) creates the learner
 * account, grants the STUDENT school role, enrols them into a class section
 * and moves the lead to ENROLLED, in ONE transaction. Everything downstream
 * -- attendance, gradebook, fees -- works section by section, so until this
 * runs a won lead is not yet a pupil anywhere in the system.
 *
 * Two things this screen is careful about:
 *
 * 1. `student_email` is required and NOT derived from the lead.
 *    `AdmissionsLead.email` is the PARENT's address (the model carries
 *    `parent_name` beside `student_name`), so reusing it would mis-attribute
 *    the account or collide for a second sibling. The API refuses to guess
 *    and so does this form.
 *
 * 2. The call is idempotent. A repeat returns the existing student with
 *    `already_provisioned: true`, which is reported as "already enrolled"
 *    rather than implying a duplicate was created.
 */

import { useState } from 'react'
import { GraduationCap } from 'lucide-react'
import {
  LH_INPUT,
  LH_PRIMARY_BUTTON,
  LH_SECONDARY_BUTTON,
  SchoolDialog,
  SchoolField,
} from '@/components/widgets'
import { ApiError } from '@/lib/api/api-client'
import { useApiResource } from '@/lib/api/useApiResource'
import { listAcademicYears, listClassSections } from '@/modules/sms/campus/api'
import { enrollLead } from '../api'
import type { EnrollLeadResponse, LeadRead } from '../types'

export interface EnrolLeadDialogProps {
  lead: LeadRead
  onEnrolled: (result: EnrollLeadResponse) => void
}

export function EnrolLeadDialog({ lead, onEnrolled }: EnrolLeadDialogProps) {
  const [open, setOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const campusId = lead.campus_id ?? undefined

  const years = useApiResource(() => listAcademicYears(campusId as number), [campusId], {
    skip: !open || campusId === undefined,
    isEmpty: (d) => d.length === 0,
  })
  const sections = useApiResource(
    () => listClassSections(campusId as number, { isActive: true }),
    [campusId],
    { skip: !open || campusId === undefined, isEmpty: (d) => d.length === 0 }
  )

  // A lead with no campus cannot be enrolled: sections and years both hang
  // off one. Say which step is missing rather than showing an empty picker.
  const blockedReason =
    lead.stage === 'LOST'
      ? 'This lead is marked Lost and cannot be enrolled.'
      : campusId === undefined
        ? 'Assign this lead to a campus first — sections belong to a campus.'
        : undefined

  if (blockedReason) {
    return (
      <button type="button" className={LH_SECONDARY_BUTTON} disabled title={blockedReason}>
        <GraduationCap className="size-4" /> <span>Enrol as student</span>
      </button>
    )
  }

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const form = new FormData(e.currentTarget)
    const sectionId = Number(form.get('section_id'))
    const yearId = Number(form.get('academic_year_id'))
    const studentEmail = String(form.get('student_email') ?? '').trim()
    const rollNumber = String(form.get('roll_number') ?? '').trim()

    if (!sectionId || !yearId) {
      setError('Pick both a class section and an academic year.')
      return
    }
    if (!studentEmail) {
      setError("Enter the student's own email address — not the parent's.")
      return
    }

    setSaving(true)
    setError(null)
    try {
      const result = await enrollLead(lead.id, {
        section_id: sectionId,
        academic_year_id: yearId,
        student_email: studentEmail,
        roll_number: rollNumber || null,
      })
      setOpen(false)
      onEnrolled(result)
    } catch (err) {
      // The API refuses with an actionable reason (missing section/year, no
      // student email, lead is Lost). Surface it verbatim -- collapsing it
      // into "something went wrong" hides the fix from the operator.
      setError(
        err instanceof ApiError
          ? err.kind === 'permission_denied'
            ? 'You need school-admin or staff access to enrol a student.'
            : err.message
          : 'Could not enrol this lead. Try again.'
      )
    } finally {
      setSaving(false)
    }
  }

  const yearRows = years.data ?? []
  const sectionRows = sections.data ?? []
  const notReady = yearRows.length === 0 || sectionRows.length === 0

  return (
    <SchoolDialog
      open={open}
      onOpenChange={setOpen}
      trigger={
        <button type="button" id="enrol-lead-trigger" className={LH_SECONDARY_BUTTON}>
          <GraduationCap className="size-4" /> <span>Enrol as student</span>
        </button>
      }
      title={`Enrol ${lead.student_name}`}
      description="Creates the student account, grants the Student role and places them in a class section — in one step. Running it twice will not create a duplicate."
      onSubmit={handleSubmit}
      footer={
        <button type="submit" disabled={saving || notReady} className={LH_PRIMARY_BUTTON}>
          <span>{saving ? 'Enrolling…' : 'Enrol student'}</span>
        </button>
      }
    >
      <SchoolField
        id="enrol-lead-email"
        label="Student email"
        required
        help="The student's own address. The lead's email belongs to the parent, so it is deliberately not reused — a sibling would collide with it."
      >
        <input
          id="enrol-lead-email"
          name="student_email"
          type="email"
          className={LH_INPUT}
          placeholder="student@example.com"
        />
      </SchoolField>

      <SchoolField id="enrol-lead-year" label="Academic year" required>
        {years.status === 'loading' ? (
          <p className="text-sm text-gray-400">Loading years…</p>
        ) : yearRows.length === 0 ? (
          <p className="text-sm text-gray-500">
            No academic years exist for this campus yet. Create one in Campus first.
          </p>
        ) : (
          <select
            id="enrol-lead-year"
            name="academic_year_id"
            className={LH_INPUT}
            defaultValue={yearRows.find((y) => y.is_active)?.id ?? ''}
          >
            <option value="" disabled>
              Choose a year…
            </option>
            {yearRows.map((y) => (
              <option key={y.id} value={y.id}>
                {y.name}
                {y.is_active ? ' (current)' : ''}
              </option>
            ))}
          </select>
        )}
      </SchoolField>

      <SchoolField id="enrol-lead-section" label="Class section" required>
        {sections.status === 'loading' ? (
          <p className="text-sm text-gray-400">Loading sections…</p>
        ) : sectionRows.length === 0 ? (
          <p className="text-sm text-gray-500">
            No class sections exist for this campus yet. Create one in Campus first.
          </p>
        ) : (
          <select id="enrol-lead-section" name="section_id" className={LH_INPUT} defaultValue="">
            <option value="" disabled>
              Choose a section…
            </option>
            {sectionRows.map((s) => (
              <option key={s.id} value={s.id}>
                {s.grade_level} — {s.section_name}
              </option>
            ))}
          </select>
        )}
      </SchoolField>

      <SchoolField id="enrol-lead-roll" label="Roll number">
        <input
          id="enrol-lead-roll"
          name="roll_number"
          className={LH_INPUT}
          placeholder="Optional"
        />
      </SchoolField>

      {error && <p className="text-sm text-rose-600">{error}</p>}
    </SchoolDialog>
  )
}
