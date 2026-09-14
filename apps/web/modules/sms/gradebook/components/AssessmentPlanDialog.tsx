'use client'

/**
 * Create an assessment plan.
 *
 * The gradebook matrix draws one COLUMN per assessment plan, so a section with
 * no plans renders a grid with nothing to mark against -- the single thing
 * that made the gradebook unusable rather than merely empty. This is the form
 * that fills it.
 *
 * `weight_percentage` is what the server's weighted-GPA engine multiplies by,
 * so the help text says plainly that the plans for a course are meant to total
 * 100 -- the API does not enforce that, and silently letting a teacher build a
 * set summing to 140 would skew every grade in the section.
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
import { createAssessmentPlan } from '../api'
import type { AssessmentPlanRead } from '../types'

export interface CourseOption {
  id: number
  name: string
}

export interface AssessmentPlanDialogProps {
  sectionId?: number
  academicTermId?: number
  courses: CourseOption[]
  /** Plans already defined, so the dialog can show the running weight total. */
  existingPlans: AssessmentPlanRead[]
  onCreated: () => void
}

export function AssessmentPlanDialog({
  sectionId,
  academicTermId,
  courses,
  existingPlans,
  onCreated,
}: AssessmentPlanDialogProps) {
  const [open, setOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [courseId, setCourseId] = useState<string>('')

  const usedWeight = existingPlans
    .filter((p) => (courseId ? p.course_id === Number(courseId) : false))
    .reduce((sum, p) => sum + (p.weight_percentage ?? 0), 0)

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const form = new FormData(e.currentTarget)
    const course = Number(form.get('course_id'))
    const name = String(form.get('assessment_name') ?? '').trim()
    const weight = Number(form.get('weight_percentage'))
    const maxScore = Number(form.get('max_score'))

    if (!course) {
      setError('Pick a course.')
      return
    }
    if (!name) {
      setError('Give the assessment a name.')
      return
    }
    if (Number.isNaN(weight) || weight < 0 || weight > 100) {
      setError('Weight must be between 0 and 100.')
      return
    }
    if (Number.isNaN(maxScore) || maxScore <= 0) {
      setError('Max score must be greater than 0.')
      return
    }

    setSaving(true)
    setError(null)
    try {
      await createAssessmentPlan({
        course_id: course,
        section_id: sectionId ?? null,
        academic_term_id: academicTermId ?? null,
        assessment_name: name,
        weight_percentage: weight,
        max_score: maxScore,
      })
      setOpen(false)
      setCourseId('')
      onCreated()
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.kind === 'permission_denied'
            ? 'You need teacher or school-admin access to define assessments.'
            : err.message
          : 'Could not save the assessment plan.'
      )
    } finally {
      setSaving(false)
    }
  }

  if (courses.length === 0) {
    return (
      <button
        type="button"
        className={LH_SECONDARY_BUTTON}
        disabled
        title="No courses exist in this organisation yet. Create one under Courses first."
      >
        <Plus className="size-4" /> <span>New assessment</span>
      </button>
    )
  }

  return (
    <SchoolDialog
      open={open}
      onOpenChange={setOpen}
      trigger={
        <button type="button" className={LH_SECONDARY_BUTTON}>
          <Plus className="size-4" /> <span>New assessment</span>
        </button>
      }
      title="New assessment"
      description="A column in the gradebook — a quiz, an assignment, a final exam — and how much of the course grade it carries."
      onSubmit={handleSubmit}
      footer={
        <button type="submit" disabled={saving} className={LH_PRIMARY_BUTTON}>
          <span>{saving ? 'Saving…' : 'Create'}</span>
        </button>
      }
    >
      <SchoolField id="plan-course" label="Course" required>
        <select
          id="plan-course"
          name="course_id"
          className={LH_INPUT}
          value={courseId}
          onChange={(e) => setCourseId(e.target.value)}
        >
          <option value="">Choose a course…</option>
          {courses.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      </SchoolField>

      <SchoolField id="plan-name" label="Assessment name" required>
        <input
          id="plan-name"
          name="assessment_name"
          className={LH_INPUT}
          placeholder="Mid-term exam"
        />
      </SchoolField>

      <SchoolField
        id="plan-weight"
        label="Weight (%)"
        required
        help={
          courseId
            ? `This course's assessments currently total ${usedWeight}%. They are meant to add up to 100.`
            : 'Share of the course grade. All assessments for a course are meant to add up to 100.'
        }
      >
        <input
          id="plan-weight"
          name="weight_percentage"
          type="number"
          min={0}
          max={100}
          step="0.1"
          defaultValue={courseId ? Math.max(0, 100 - usedWeight) : 100}
          className={LH_INPUT}
        />
      </SchoolField>

      <SchoolField id="plan-max" label="Max score" required help="The score a perfect paper earns.">
        <input
          id="plan-max"
          name="max_score"
          type="number"
          min={1}
          step="0.5"
          defaultValue={100}
          className={LH_INPUT}
        />
      </SchoolField>

      {error && <p className="text-sm text-rose-600">{error}</p>}
    </SchoolDialog>
  )
}
