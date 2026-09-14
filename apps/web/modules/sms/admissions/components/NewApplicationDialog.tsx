'use client'

/**
 * Start an application.
 *
 * `lead_id` is deliberately absent from this form. A walk-in family may never
 * have been a tracked RevOps lead, and requiring one would force the front
 * desk to fabricate a marketing record in order to accept a paper form — the
 * exact coupling the backend avoided by making the column nullable.
 */

import { useState } from 'react'
import { FilePlus } from 'lucide-react'
import {
  LH_INPUT,
  LH_PRIMARY_BUTTON,
  LH_SECONDARY_BUTTON,
  SchoolDialog,
  SchoolField,
} from '@/components/widgets'
import { ApiError } from '@/lib/api/api-client'
import { createApplication } from '../api'

export interface NewApplicationDialogProps {
  campusId?: number
  academicYearId?: number
  onCreated: () => void
}

export function NewApplicationDialog({ campusId, academicYearId, onCreated }: NewApplicationDialogProps) {
  const [open, setOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const form = new FormData(e.currentTarget)
    const studentName = String(form.get('student_name') ?? '').trim()
    const guardianName = String(form.get('guardian_name') ?? '').trim()
    const grade = String(form.get('grade_applying_for') ?? '').trim()

    if (!studentName || !guardianName || !grade) {
      setError('Student name, guardian name and grade are all required.')
      return
    }

    setSaving(true)
    setError(null)
    try {
      await createApplication({
        campus_id: campusId ?? null,
        student_name: studentName,
        guardian_name: guardianName,
        grade_applying_for: grade,
        // Empty strings are sent as null, never as "": a blank field means the
        // school holds no contact detail, not that it holds an empty one.
        date_of_birth: String(form.get('date_of_birth') ?? '').trim() || null,
        guardian_email: String(form.get('guardian_email') ?? '').trim() || null,
        guardian_phone: String(form.get('guardian_phone') ?? '').trim() || null,
        academic_year_id: academicYearId ?? null,
        notes: String(form.get('notes') ?? '').trim() || null,
      })
      setOpen(false)
      onCreated()
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.kind === 'permission_denied'
            ? 'You need admissions access to start an application.'
            : err.message
          : 'Could not start the application. Try again.'
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
          <FilePlus className="size-4" /> <span>New application</span>
        </button>
      }
      title="Start an application"
      description="For a family who has applied — whether or not they were ever a tracked enquiry."
      onSubmit={handleSubmit}
      footer={
        <button type="submit" disabled={saving} className={LH_PRIMARY_BUTTON}>
          <span>{saving ? 'Starting…' : 'Start application'}</span>
        </button>
      }
    >
      <SchoolField id="app-student-name" label="Student name" required>
        <input id="app-student-name" name="student_name" className={LH_INPUT} autoComplete="off" />
      </SchoolField>

      <SchoolField id="app-dob" label="Date of birth">
        <input id="app-dob" name="date_of_birth" type="date" className={LH_INPUT} />
      </SchoolField>

      <SchoolField id="app-grade" label="Grade applying for" required>
        <input id="app-grade" name="grade_applying_for" className={LH_INPUT} placeholder="Grade 9" />
      </SchoolField>

      <SchoolField id="app-guardian-name" label="Guardian name" required>
        <input id="app-guardian-name" name="guardian_name" className={LH_INPUT} autoComplete="off" />
      </SchoolField>

      <SchoolField id="app-guardian-email" label="Guardian email">
        <input id="app-guardian-email" name="guardian_email" type="email" className={LH_INPUT} />
      </SchoolField>

      <SchoolField id="app-guardian-phone" label="Guardian phone">
        <input id="app-guardian-phone" name="guardian_phone" className={LH_INPUT} />
      </SchoolField>

      <SchoolField id="app-notes" label="Notes">
        <input id="app-notes" name="notes" className={LH_INPUT} placeholder="Optional" />
      </SchoolField>

      {error && <p className="text-sm text-rose-600">{error}</p>}
    </SchoolDialog>
  )
}
