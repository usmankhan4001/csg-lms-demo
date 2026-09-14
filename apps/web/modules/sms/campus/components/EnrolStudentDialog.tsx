'use client'

/**
 * Enrol a student into a class section.
 *
 * This was the last gap keeping the school unusable: campuses, years, terms
 * and sections could all be created, but with no enrolment every downstream
 * module -- attendance roll-call, gradebook, report cards, fees -- rendered
 * an empty roster, which reads as "broken" rather than "not set up yet".
 *
 * The picker lists people who already hold the STUDENT school role rather
 * than every org member, because enrolment is the SECOND step: a person is
 * made a student in Learnhouse's own user record (Users -> School), then
 * enrolled into a section here. Listing arbitrary org members would invite
 * enrolling a teacher as a pupil.
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
import { useApiResource } from '@/lib/api/useApiResource'
import { enrollStudent, listSchoolPeople } from '../api'
import type { ClassSectionRead } from '../types'

export interface EnrolStudentDialogProps {
  /**
   * Opens the dialog on first render. Set by the campus page when Ctrl+K's
   * "Enrol a student" deep-links here, so the palette lands the user on the
   * form rather than on the page beside it.
   */
  defaultOpen?: boolean
  sections: ClassSectionRead[]
  activeYearId?: number
  campusId?: number
  onDone: () => void
}

export function EnrolStudentDialog({
  defaultOpen = false,
  sections,
  activeYearId,
  campusId,
  onDone,
}: EnrolStudentDialogProps) {
  const [open, setOpen] = useState(defaultOpen)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const students = useApiResource(() => listSchoolPeople('STUDENT', campusId), [campusId], {
    skip: !open,
    isEmpty: (d) => d.length === 0,
  })

  const blockedReason =
    activeYearId === undefined
      ? 'Create an academic year first.'
      : sections.length === 0
        ? 'Create a class section first.'
        : undefined

  if (blockedReason) {
    return (
      <button type="button" className={LH_SECONDARY_BUTTON} disabled title={blockedReason}>
        <UserPlus className="size-4" /> <span>Enrol student</span>
      </button>
    )
  }

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const form = new FormData(e.currentTarget)
    const studentId = Number(form.get('student_id'))
    const sectionId = Number(form.get('section_id'))
    const rollNumber = String(form.get('roll_number') ?? '').trim()

    if (!studentId || !sectionId) {
      setError('Pick both a student and a section.')
      return
    }

    setSaving(true)
    setError(null)
    try {
      await enrollStudent({
        student_id: studentId,
        section_id: sectionId,
        academic_year_id: activeYearId as number,
        roll_number: rollNumber || null,
      })
      setOpen(false)
      onDone()
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.status === 409
            ? 'That student is already enrolled for this academic year.'
            : err.kind === 'permission_denied'
              ? 'You need school-admin or staff access to enrol students.'
              : err.message
          : 'Could not enrol. Try again.'
      )
    } finally {
      setSaving(false)
    }
  }

  const people = students.data ?? []

  return (
    <SchoolDialog
      open={open}
      onOpenChange={setOpen}
      trigger={
        <button type="button" className={LH_SECONDARY_BUTTON}>
          <UserPlus className="size-4" /> <span>Enrol student</span>
        </button>
      }
      title="Enrol a student"
      description="Places a student in a class section for the current academic year. Attendance, gradebook and fees all work section by section, so nothing appears for a student until they are enrolled."
      onSubmit={handleSubmit}
      footer={
        <button
          type="submit"
          disabled={saving || people.length === 0}
          className={LH_PRIMARY_BUTTON}
        >
          <span>{saving ? 'Enrolling…' : 'Enrol'}</span>
        </button>
      }
    >
      <SchoolField id="enrol-student" label="Student" required>
        {students.status === 'loading' ? (
          <p className="text-sm text-gray-400">Loading students…</p>
        ) : people.length === 0 ? (
          <p className="text-sm text-gray-500">
            Nobody holds the Student role yet. Grant it first in Users → a person → School.
          </p>
        ) : (
          <select id="enrol-student" name="student_id" className={LH_INPUT} defaultValue="">
            <option value="" disabled>
              Choose a student…
            </option>
            {people.map((p) => (
              <option key={p.user_id} value={p.user_id}>
                {p.name ?? `User #${p.user_id}`}
                {p.email ? ` — ${p.email}` : ''}
              </option>
            ))}
          </select>
        )}
      </SchoolField>

      <SchoolField id="enrol-section" label="Class section" required>
        <select id="enrol-section" name="section_id" className={LH_INPUT} defaultValue="">
          <option value="" disabled>
            Choose a section…
          </option>
          {sections.map((s) => (
            <option key={s.id} value={s.id}>
              {s.grade_level} — {s.section_name}
            </option>
          ))}
        </select>
      </SchoolField>

      <SchoolField id="enrol-roll" label="Roll number">
        <input id="enrol-roll" name="roll_number" className={LH_INPUT} placeholder="Optional" />
      </SchoolField>

      {error && <p className="text-sm text-rose-600">{error}</p>}
    </SchoolDialog>
  )
}
