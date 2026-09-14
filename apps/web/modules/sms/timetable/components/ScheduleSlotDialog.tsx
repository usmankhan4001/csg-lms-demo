'use client'

/**
 * Add a slot to the weekly timetable.
 *
 * Runs `POST /check-clashes` BEFORE `POST /schedules` so a double-booking is
 * shown as a readable sentence ("Teacher already booked Monday period 3")
 * while the teacher can still change the inputs -- rather than submitting
 * blind and getting a 409 whose detail string is the first explanation they
 * see. The server re-validates on create regardless; this check is a courtesy,
 * not the enforcement, and the code says so rather than implying otherwise.
 *
 * A slot needs a class PERIOD to sit in, and periods are their own entity. If
 * none exist the form blocks with that reason instead of offering an empty
 * dropdown, since "create a period first" is not guessable from a blank select.
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
import type { SchoolPerson } from '@/modules/sms/campus/api'
import { checkTimetableClashes, createTimetableSchedule, DAY_ORDER } from '../api'
import type { ClassPeriodRead, ClashDetail, DayOfWeek } from '../types'

export interface CourseOption {
  id: number
  name: string
}

export interface ScheduleSlotDialogProps {
  sectionId?: number
  academicTermId?: number
  periods: ClassPeriodRead[]
  teachers: SchoolPerson[]
  courses: CourseOption[]
  onCreated: () => void
}

export function ScheduleSlotDialog({
  sectionId,
  academicTermId,
  periods,
  teachers,
  courses,
  onCreated,
}: ScheduleSlotDialogProps) {
  const [open, setOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [clashes, setClashes] = useState<ClashDetail[]>([])

  const blockedReason =
    sectionId === undefined
      ? 'Pick a section first.'
      : periods.length === 0
        ? 'No class periods defined yet — create the daily period structure first.'
        : courses.length === 0
          ? 'No courses exist in this organisation yet.'
          : teachers.length === 0
            ? 'Nobody holds the Teacher role yet. Grant it in Users → a person → School.'
            : undefined

  if (blockedReason) {
    return (
      <button type="button" className={LH_SECONDARY_BUTTON} disabled title={blockedReason}>
        <Plus className="size-4" /> <span>Add slot</span>
      </button>
    )
  }

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const form = new FormData(e.currentTarget)
    const courseId = Number(form.get('course_id'))
    const teacherId = Number(form.get('teacher_id'))
    const periodId = Number(form.get('period_id'))
    const dayOfWeek = String(form.get('day_of_week') ?? '') as DayOfWeek
    const room = String(form.get('room_number') ?? '').trim()

    if (!courseId || !teacherId || !periodId || !dayOfWeek) {
      setError('Course, teacher, day and period are all required.')
      return
    }

    setSaving(true)
    setError(null)
    setClashes([])

    const payload = {
      section_id: sectionId as number,
      course_id: courseId,
      teacher_id: teacherId,
      day_of_week: dayOfWeek,
      period_id: periodId,
      room_number: room || null,
      academic_term_id: academicTermId ?? null,
    }

    try {
      // Pre-flight: show conflicts while the inputs are still on screen.
      const check = await checkTimetableClashes(payload)
      if (check.has_clash) {
        setClashes(check.clashes)
        setError(check.message || 'This slot conflicts with the existing timetable.')
        setSaving(false)
        return
      }

      await createTimetableSchedule(payload, true)
      setOpen(false)
      setClashes([])
      onCreated()
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.status === 409
            ? err.message
            : err.kind === 'permission_denied'
              ? 'You need teacher or school-admin access to edit the timetable.'
              : err.message
          : 'Could not add the slot.'
      )
    } finally {
      setSaving(false)
    }
  }

  return (
    <SchoolDialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next)
        if (!next) {
          setError(null)
          setClashes([])
        }
      }}
      trigger={
        <button type="button" className={LH_SECONDARY_BUTTON}>
          <Plus className="size-4" /> <span>Add slot</span>
        </button>
      }
      title="Add a timetable slot"
      description="One recurring lesson: a course, taught by a teacher, on a day, in a period."
      onSubmit={handleSubmit}
      footer={
        <button type="submit" disabled={saving} className={LH_PRIMARY_BUTTON}>
          <span>{saving ? 'Checking…' : 'Add slot'}</span>
        </button>
      }
    >
      <SchoolField id="slot-course" label="Course" required>
        <select id="slot-course" name="course_id" className={LH_INPUT} defaultValue="">
          <option value="" disabled>
            Choose a course…
          </option>
          {courses.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      </SchoolField>

      <SchoolField id="slot-teacher" label="Teacher" required>
        <select id="slot-teacher" name="teacher_id" className={LH_INPUT} defaultValue="">
          <option value="" disabled>
            Choose a teacher…
          </option>
          {teachers.map((t) => (
            <option key={t.user_id} value={t.user_id}>
              {t.name ?? `User #${t.user_id}`}
            </option>
          ))}
        </select>
      </SchoolField>

      <SchoolField id="slot-day" label="Day" required>
        <select id="slot-day" name="day_of_week" className={LH_INPUT} defaultValue="MONDAY">
          {DAY_ORDER.map((d) => (
            <option key={d} value={d}>
              {d.charAt(0) + d.slice(1).toLowerCase()}
            </option>
          ))}
        </select>
      </SchoolField>

      <SchoolField id="slot-period" label="Period" required>
        <select id="slot-period" name="period_id" className={LH_INPUT} defaultValue="">
          <option value="" disabled>
            Choose a period…
          </option>
          {periods.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name ?? `Period ${p.period_number}`} ({p.start_time}–{p.end_time})
            </option>
          ))}
        </select>
      </SchoolField>

      <SchoolField id="slot-room" label="Room" help="Optional. Checked for double-booking too.">
        <input id="slot-room" name="room_number" className={LH_INPUT} placeholder="204" />
      </SchoolField>

      {clashes.length > 0 && (
        <div className="rounded-lg bg-rose-50 p-3">
          <p className="text-sm font-semibold text-rose-700">This slot conflicts with:</p>
          <ul className="mt-1 list-disc ps-5 text-sm text-rose-600">
            {clashes.map((c, i) => (
              <li key={`${c.conflicting_schedule_id}-${i}`}>{c.description}</li>
            ))}
          </ul>
        </div>
      )}

      {error && clashes.length === 0 && <p className="text-sm text-rose-600">{error}</p>}
    </SchoolDialog>
  )
}
