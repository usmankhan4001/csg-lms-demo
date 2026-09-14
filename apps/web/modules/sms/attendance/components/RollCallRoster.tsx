'use client'

/**
 * The daily driver: a teacher marking one section's register.
 *
 * Built for someone with 28 students and six minutes between periods, so the
 * bulk path is first-class:
 *  - everyone defaults to PRESENT (the common case, and the fastest)
 *  - "Mark all" sets the whole roster in one action -- a closure or a trip
 *  - each row is a 4-way radio group, so a teacher can tab to a student and
 *    press one arrow key rather than reaching for the mouse 28 times
 *
 * Names come from `useStudentNames` because the roster payload carries only
 * `student_id` -- see that hook for why this needs a second call.
 *
 * Unsaved changes are tracked so the submit button can say what it will do
 * and warn on navigating away: a register lost to a mis-click is a register
 * a teacher has to take again from memory.
 */

import { useEffect, useMemo, useState } from 'react'
import toast from 'react-hot-toast'
import { CheckSquare } from 'lucide-react'
import {
  DataTable,
  LH_PRIMARY_BUTTON,
  LH_SECONDARY_BUTTON,
  SectionCard,
  StatusChip,
} from '@/components/widgets'
import { useApiResource } from '@/lib/api/useApiResource'
import { listSectionEnrollments } from '@/modules/sms/campus/api'
import { submitRollCall } from '../api'
import { ATTENDANCE_TONE, studentLabel } from '../presentation'
import { useStudentNames } from '../useStudentNames'
import type { AttendanceStatus } from '../types'

const STATUSES: AttendanceStatus[] = ['PRESENT', 'ABSENT', 'LATE', 'EXCUSED']

export interface RollCallRosterProps {
  sectionId: number
  campusId?: number
  markedBy?: number
  /** ISO date, defaults to today. */
  date?: string
  /** Records this period only; omitted records a whole-day register. */
  periodId?: number
}

export function RollCallRoster({
  sectionId,
  campusId,
  markedBy,
  date,
  periodId,
}: RollCallRosterProps) {
  const rollCallDate = date ?? new Date().toISOString().slice(0, 10)
  const enrollments = useApiResource(
    () => listSectionEnrollments(sectionId, 'active'),
    [sectionId],
    { isEmpty: (d) => d.length === 0 }
  )
  const { names, error: namesError } = useStudentNames(campusId)

  const [statuses, setStatuses] = useState<Record<number, AttendanceStatus>>({})
  const [submitting, setSubmitting] = useState(false)
  const [dirty, setDirty] = useState(false)

  useEffect(() => {
    if (!enrollments.data) return
    setStatuses((prev) => {
      const next = { ...prev }
      for (const e of enrollments.data!) {
        if (!(e.student_id in next)) next[e.student_id] = 'PRESENT'
      }
      return next
    })
  }, [enrollments.data])

  const rows = useMemo(() => enrollments.data ?? [], [enrollments.data])

  function setOne(studentId: number, status: AttendanceStatus) {
    setStatuses((prev) => ({ ...prev, [studentId]: status }))
    setDirty(true)
  }

  function setAll(status: AttendanceStatus) {
    setStatuses(() => {
      const next: Record<number, AttendanceStatus> = {}
      for (const r of rows) next[r.student_id] = status
      return next
    })
    setDirty(true)
  }

  const tally = useMemo(() => {
    const counts: Record<AttendanceStatus, number> = {
      PRESENT: 0,
      ABSENT: 0,
      LATE: 0,
      EXCUSED: 0,
    }
    for (const r of rows) counts[statuses[r.student_id] ?? 'PRESENT'] += 1
    return counts
  }, [rows, statuses])

  async function handleSubmit() {
    if (rows.length === 0) return
    setSubmitting(true)
    try {
      const result = await submitRollCall({
        section_id: sectionId,
        date: rollCallDate,
        marked_by: markedBy,
        period_id: periodId,
        entries: rows.map((r) => ({
          student_id: r.student_id,
          status: statuses[r.student_id] ?? 'PRESENT',
        })),
      })
      setDirty(false)
      toast.success(
        `Register saved — ${result.total_recorded} student${result.total_recorded === 1 ? '' : 's'}.`
      )
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Could not save the register.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <SectionCard
      id="roll-call"
      title="Take the register"
      description={`${rollCallDate}${periodId ? ` · period #${periodId}` : ' · whole day'}`}
      icon={<CheckSquare className="size-4 text-gray-500" />}
      state={enrollments.status}
      error={enrollments.error}
      onRetry={enrollments.refetch}
      emptyTitle="No students enrolled in this section"
      emptyDescription="Enrol students into this section before taking a register."
    >
      <div className="space-y-3">
        {namesError && (
          <p className="text-xs text-amber-600">
            Student names could not be loaded, so rows show ID numbers. The register
            still saves correctly.
          </p>
        )}

        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-medium uppercase tracking-wide text-gray-500">
            Mark all
          </span>
          {STATUSES.map((s) => (
            <button
              key={s}
              id={`rollcall-all-${s.toLowerCase()}`}
              type="button"
              className={LH_SECONDARY_BUTTON}
              onClick={() => setAll(s)}
            >
              {s.charAt(0) + s.slice(1).toLowerCase()}
            </button>
          ))}
        </div>

        <DataTable
          rows={rows}
          rowKey={(row) => row.id}
          state="success"
          totalLabel={`${tally.PRESENT} present · ${tally.ABSENT} absent · ${tally.LATE} late · ${tally.EXCUSED} excused`}
          columns={[
            {
              key: 'student',
              header: 'Student',
              render: (r) => studentLabel(r.student_id, names, r.roll_number),
            },
            {
              key: 'status',
              header: 'Status',
              render: (r) => {
                const current = statuses[r.student_id] ?? 'PRESENT'
                return (
                  <div
                    role="radiogroup"
                    aria-label={`Attendance for ${studentLabel(r.student_id, names, r.roll_number)}`}
                    className="flex flex-wrap gap-1.5"
                  >
                    {STATUSES.map((s) => {
                      const active = current === s
                      return (
                        <button
                          key={s}
                          id={`rollcall-${r.student_id}-${s.toLowerCase()}`}
                          type="button"
                          role="radio"
                          aria-checked={active}
                          // Only the selected chip is in the tab order, so a
                          // teacher tabs student-to-student and uses arrows
                          // within a row rather than tabbing 4x28 times.
                          tabIndex={active ? 0 : -1}
                          onKeyDown={(e) => {
                            if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return
                            e.preventDefault()
                            const i = STATUSES.indexOf(current)
                            const nextIndex =
                              e.key === 'ArrowRight'
                                ? (i + 1) % STATUSES.length
                                : (i - 1 + STATUSES.length) % STATUSES.length
                            const nextStatus = STATUSES[nextIndex]
                            setOne(r.student_id, nextStatus)
                            document
                              .getElementById(`rollcall-${r.student_id}-${nextStatus.toLowerCase()}`)
                              ?.focus()
                          }}
                          onClick={() => setOne(r.student_id, s)}
                          className={
                            active
                              ? 'rounded-full focus:outline-none focus:ring-2 focus:ring-black focus:ring-offset-1'
                              : 'rounded-full opacity-40 transition-opacity hover:opacity-70 focus:outline-none focus:ring-2 focus:ring-black focus:ring-offset-1'
                          }
                        >
                          <StatusChip label={s} tone={ATTENDANCE_TONE[s]} />
                        </button>
                      )
                    })}
                  </div>
                )
              },
            },
          ]}
        />

        {rows.length > 0 && (
          <div className="flex items-center justify-end gap-3">
            {dirty && (
              <span className="text-xs text-gray-500">Unsaved changes</span>
            )}
            <button
              id="rollcall-submit"
              type="button"
              className={LH_PRIMARY_BUTTON}
              onClick={handleSubmit}
              disabled={submitting}
            >
              <span>{submitting ? 'Saving…' : `Save register (${rows.length})`}</span>
            </button>
          </div>
        )}
      </div>
    </SectionCard>
  )
}
