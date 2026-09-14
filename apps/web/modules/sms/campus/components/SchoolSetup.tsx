'use client'

/**
 * School setup -- the create path for the academic structure.
 *
 * Why this exists: the backend has had create endpoints for campuses, years,
 * terms, sections and enrolments all along, but the frontend exposed only
 * reads. A school could therefore be displayed but never set up, and since
 * every other module hangs off a campus (no campus -> no sections -> no
 * enrolments -> nothing for attendance, gradebook or fees to point at), the
 * entire system was unusable from the UI for want of these forms.
 *
 * Deliberately ordered as a dependency chain rather than four independent
 * buttons, because that is what it actually is -- each step is disabled with
 * a stated reason until its parent exists, so the order is discoverable
 * instead of being something you learn from a failed request.
 */

import { useState } from 'react'
import { Plus } from 'lucide-react'
import {
  LH_INPUT,
  LH_PRIMARY_BUTTON,
  LH_SECONDARY_BUTTON,
  SchoolDialog,
  SchoolField,
} from '@/components/widgets'
import { ApiError } from '@/lib/api/api-client'
import {
  createAcademicTerm,
  createAcademicYear,
  createCampus,
  createClassSection,
} from '../api'
import type { AcademicYearRead, CampusRead, ClassSectionRead } from '../types'
import { EnrolStudentDialog } from './EnrolStudentDialog'

interface Field {
  name: string
  label: string
  required?: boolean
  type?: string
  placeholder?: string
  help?: string
  defaultValue?: string
}

interface CreateDialogProps {
  title: string
  description: string
  trigger: string
  fields: Field[]
  disabled?: boolean
  disabledReason?: string
  onSubmit: (values: Record<string, string>) => Promise<unknown>
  onDone: () => void
}

function CreateDialog({
  title,
  description,
  trigger,
  fields,
  disabled,
  disabledReason,
  onSubmit,
  onDone,
}: CreateDialogProps) {
  const [open, setOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const form = new FormData(e.currentTarget)
    const values: Record<string, string> = {}
    for (const f of fields) values[f.name] = String(form.get(f.name) ?? '').trim()

    const missing = fields.find((f) => f.required && !values[f.name])
    if (missing) {
      setError(`${missing.label} is required.`)
      return
    }

    setSaving(true)
    setError(null)
    try {
      await onSubmit(values)
      setOpen(false)
      onDone()
    } catch (err) {
      // Surface what actually went wrong -- a silent failure here leaves the
      // user believing the school was set up when it wasn't.
      setError(
        err instanceof ApiError
          ? err.kind === 'permission_denied'
            ? 'You need school-admin access to do this.'
            : err.message
          : 'Could not save. Try again.'
      )
    } finally {
      setSaving(false)
    }
  }

  if (disabled) {
    return (
      <button type="button" className={LH_SECONDARY_BUTTON} disabled title={disabledReason}>
        <Plus className="size-4" /> <span>{trigger}</span>
      </button>
    )
  }

  return (
    <SchoolDialog
      open={open}
      onOpenChange={setOpen}
      trigger={
        <button type="button" className={LH_SECONDARY_BUTTON}>
          <Plus className="size-4" /> <span>{trigger}</span>
        </button>
      }
      title={title}
      description={description}
      onSubmit={handleSubmit}
      footer={
        <button type="submit" disabled={saving} className={LH_PRIMARY_BUTTON}>
          <span>{saving ? 'Saving…' : 'Create'}</span>
        </button>
      }
    >
      {fields.map((f) => (
        <SchoolField
          key={f.name}
          id={`setup-${f.name}`}
          label={f.label}
          required={f.required}
          help={f.help}
        >
          <input
            id={`setup-${f.name}`}
            name={f.name}
            type={f.type ?? 'text'}
            placeholder={f.placeholder}
            defaultValue={f.defaultValue}
            className={LH_INPUT}
          />
        </SchoolField>
      ))}
      {error && <p className="text-sm text-rose-600">{error}</p>}
    </SchoolDialog>
  )
}

export interface SchoolSetupProps {
  /** Opens the enrol-student dialog on mount (Ctrl+K deep link). */
  enrolStudentOpen?: boolean
  orgId: number
  campuses: CampusRead[]
  years: AcademicYearRead[]
  sections?: ClassSectionRead[]
  activeCampusId?: number
  activeYearId?: number
  onChanged: () => void
}

export function SchoolSetup({
  enrolStudentOpen = false,
  orgId,
  campuses,
  years,
  sections = [],
  activeCampusId,
  activeYearId,
  onChanged,
}: SchoolSetupProps) {
  const hasCampus = activeCampusId !== undefined
  const hasYear = activeYearId !== undefined

  return (
    <div className="flex flex-wrap items-center gap-2 rounded-xl bg-white nice-shadow p-4">
      <span className="mr-1 text-xs font-medium uppercase tracking-wide text-gray-500">
        Set up
      </span>

      <CreateDialog
        trigger="Campus"
        title="Add a campus"
        description="A campus is the root of the school. Everything else — years, terms, sections, enrolments — belongs to one."
        fields={[
          { name: 'name', label: 'Campus name', required: true, placeholder: 'Lighthouse Main Campus' },
          {
            name: 'code',
            label: 'Campus code',
            required: true,
            placeholder: 'MAIN-01',
            help: 'Short unique identifier used across the system.',
          },
          { name: 'address', label: 'Address', placeholder: 'Street address' },
          {
            name: 'timezone',
            label: 'Timezone',
            defaultValue: 'Asia/Karachi',
            help: 'IANA name. Attendance and timetables are recorded against it.',
          },
        ]}
        onSubmit={(v) =>
          createCampus({
            org_id: orgId,
            name: v.name,
            code: v.code,
            address: v.address || null,
            timezone: v.timezone || 'UTC',
          })
        }
        onDone={onChanged}
      />

      <CreateDialog
        trigger="Academic year"
        title="Add an academic year"
        description="The session students are enrolled into, e.g. 2026–2027."
        disabled={!hasCampus}
        disabledReason="Create a campus first."
        fields={[
          { name: 'name', label: 'Year name', required: true, placeholder: '2026-2027' },
          { name: 'start_date', label: 'Start date', type: 'date' },
          { name: 'end_date', label: 'End date', type: 'date' },
        ]}
        onSubmit={(v) =>
          createAcademicYear(activeCampusId as number, {
            name: v.name,
            start_date: v.start_date || null,
            end_date: v.end_date || null,
          })
        }
        onDone={onChanged}
      />

      <CreateDialog
        trigger="Term"
        title="Add a term"
        description="Grading periods within the year. Report cards and timetables are keyed on a term, so a year without terms leaves the gradebook unusable."
        disabled={!hasYear}
        disabledReason={hasCampus ? 'Create an academic year first.' : 'Create a campus first.'}
        fields={[
          { name: 'name', label: 'Term name', required: true, placeholder: 'Term 1' },
          { name: 'term_code', label: 'Term code', placeholder: 'T1' },
          {
            name: 'weight_percentage',
            label: 'Grade weight (%)',
            type: 'number',
            defaultValue: '100',
            help: "How much this term contributes to the year's final grade.",
          },
          { name: 'start_date', label: 'Start date', type: 'date' },
          { name: 'end_date', label: 'End date', type: 'date' },
        ]}
        onSubmit={(v) =>
          createAcademicTerm(activeYearId as number, {
            name: v.name,
            term_code: v.term_code || null,
            weight_percentage: v.weight_percentage ? Number(v.weight_percentage) : 100,
            start_date: v.start_date || null,
            end_date: v.end_date || null,
          })
        }
        onDone={onChanged}
      />

      <CreateDialog
        trigger="Class section"
        title="Add a class section"
        description="The group students actually sit in. Roll-call, gradebook and timetable all work section by section."
        disabled={!hasCampus}
        disabledReason="Create a campus first."
        fields={[
          { name: 'grade_level', label: 'Grade level', required: true, placeholder: 'Grade 9' },
          { name: 'section_name', label: 'Section name', required: true, placeholder: 'A' },
          { name: 'room_number', label: 'Room', placeholder: '204' },
          { name: 'max_capacity', label: 'Capacity', type: 'number', defaultValue: '30' },
        ]}
        onSubmit={(v) =>
          createClassSection(activeCampusId as number, {
            grade_level: v.grade_level,
            section_name: v.section_name,
            room_number: v.room_number || null,
            max_capacity: v.max_capacity ? Number(v.max_capacity) : 30,
          })
        }
        onDone={onChanged}
      />

      <EnrolStudentDialog
        defaultOpen={enrolStudentOpen}
        sections={sections}
        activeYearId={activeYearId}
        campusId={activeCampusId}
        onDone={onChanged}
      />

      {campuses.length === 0 && (
        <span className="text-xs text-gray-500">
          Start with a campus — nothing else can be created until one exists.
        </span>
      )}
      {campuses.length > 0 && years.length === 0 && (
        <span className="text-xs text-gray-500">
          Next, add an academic year so students can be enrolled.
        </span>
      )}
    </div>
  )
}
