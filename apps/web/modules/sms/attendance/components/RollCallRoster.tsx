'use client'

/**
 * `AttendanceRoster` (see M06_Attendance UI_UX spec's Session Roster screen,
 * `/attendance/sections/{id}` -> `AttendanceRoster`, `StatusChips`). Lets a
 * teacher batch-mark today's roll-call for one section against the real
 * `POST /sms/attendance/roll-call` endpoint.
 *
 * Student names aren't available here: `StudentEnrollmentRead` (the only
 * roster source exposed by `sms_campus.py`) carries `student_id` and
 * `roll_number` only, not a joined display name -- so students are labelled
 * "Student #<id> (Roll <roll_number>)". A real deployment would need the
 * enrollment endpoint to join the Learnhouse `users` table, which is outside
 * this task's scope (no `sms_*`/`orgs` router edits).
 */

import { useEffect, useMemo, useState } from 'react'
import toast from 'react-hot-toast'
import { CheckSquare } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { DataTable, SectionCard, StatusChip, type StatusTone } from '@/components/widgets'
import { useApiResource } from '@/lib/api/useApiResource'
import { listSectionEnrollments } from '@/modules/sms/campus/api'
import { submitRollCall } from '../api'
import type { AttendanceStatus } from '../types'

const STATUS_OPTIONS: { status: AttendanceStatus; tone: StatusTone }[] = [
  { status: 'PRESENT', tone: 'positive' },
  { status: 'ABSENT', tone: 'critical' },
  { status: 'LATE', tone: 'caution' },
  { status: 'EXCUSED', tone: 'info' },
]

export interface RollCallRosterProps {
  sectionId: number
  markedBy?: number
  date?: string // ISO date, defaults to today
}

export function RollCallRoster({ sectionId, markedBy, date }: RollCallRosterProps) {
  const rollCallDate = date ?? new Date().toISOString().slice(0, 10)
  const enrollments = useApiResource(() => listSectionEnrollments(sectionId, 'active'), [sectionId])
  const [statuses, setStatuses] = useState<Record<number, AttendanceStatus>>({})
  const [submitting, setSubmitting] = useState(false)

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

  async function handleSubmit() {
    if (rows.length === 0) return
    setSubmitting(true)
    try {
      const result = await submitRollCall({
        section_id: sectionId,
        date: rollCallDate,
        marked_by: markedBy,
        entries: rows.map((r) => ({ student_id: r.student_id, status: statuses[r.student_id] ?? 'PRESENT' })),
      })
      toast.success(`Roll-call saved for ${result.total_recorded} student${result.total_recorded === 1 ? '' : 's'}.`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Could not save roll-call.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <SectionCard
      id="attendance"
      title="1-Click Roll-Call"
      description={`Section #${sectionId} · ${rollCallDate}`}
      icon={<CheckSquare className="size-4 text-muted-foreground" />}
      state={enrollments.status}
      error={enrollments.error}
      onRetry={enrollments.refetch}
      emptyTitle="No students enrolled in this section"
      emptyDescription="Enroll students in this section to take attendance."
    >
      <div className="space-y-3">
        <DataTable
          rows={rows}
          rowKey={(row) => row.id}
          state="success"
          columns={[
            { key: 'student', header: 'Student', render: (r) => `Student #${r.student_id} (Roll ${r.roll_number ?? '—'})` },
            {
              key: 'status',
              header: 'Status',
              render: (r) => (
                <div className="flex flex-wrap gap-1.5">
                  {STATUS_OPTIONS.map((opt) => {
                    const active = (statuses[r.student_id] ?? 'PRESENT') === opt.status
                    return (
                      <button
                        key={opt.status}
                        type="button"
                        onClick={() => setStatuses((prev) => ({ ...prev, [r.student_id]: opt.status }))}
                        className={active ? '' : 'opacity-40 hover:opacity-70 transition-opacity'}
                      >
                        <StatusChip label={opt.status} tone={opt.tone} />
                      </button>
                    )
                  })}
                </div>
              ),
            },
          ]}
        />
        {rows.length > 0 && (
          <div className="flex justify-end">
            <Button size="sm" onClick={handleSubmit} disabled={submitting}>
              {submitting ? 'Saving…' : 'Submit Roll-Call'}
            </Button>
          </div>
        )}
      </div>
    </SectionCard>
  )
}
