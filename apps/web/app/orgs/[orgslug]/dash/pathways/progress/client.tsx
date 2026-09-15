'use client'

/**
 * A student's pathway enrolments.
 *
 * THE POINT OF THIS SCREEN IS WHAT IT REFUSES TO DRAW.
 *
 * `GET /progress/{student_id}` returns `earned_credits: null` and
 * `progress_percentage: null` for every enrolment, and it is correct to do so:
 * credit completion is not tracked anywhere in this system. Nothing links a
 * `StudentPathwayEnrollment` to completed work.
 *
 * Until hours ago it returned something else. `earned_credits` was computed as
 * `min(required_credits, len(pathway.courses) * 3)` -- where `courses` is the
 * pathway's OWN curriculum, not the student's completed work -- so every
 * enrolled student was credited with the entire syllabus and the min() clamp
 * reported most of them at 100% of their graduation requirements on the day
 * they enrolled. A student could be told they had finished a track they had
 * not started.
 *
 * So this screen shows enrolment status and the credit REQUIREMENT, and says
 * plainly that completion is not counted. It draws no progress bar. A bar at
 * 0% would be the same lie in the other direction: it asserts the student has
 * earned nothing, when the truth is that nobody is counting.
 */

import { useState } from 'react'
import { Info, Route } from 'lucide-react'

import {
  DashPageShell,
  DataTable,
  SectionCard,
  StatusChip,
  LH_INPUT,
  type DataTableColumn,
  type DataTableState,
} from '@/components/widgets'
import { useApiResource } from '@/lib/api/useApiResource'
import { listSchoolPeople, type SchoolPerson } from '@/modules/sms/campus/api'
import { getStudentPathwayProgress } from '@/modules/sms/pathways/api'
import type { StudentPathwayProgress } from '@/modules/sms/pathways/types'

const STATUS_TONE: Record<string, 'positive' | 'info' | 'neutral' | 'caution'> = {
  completed: 'positive',
  in_progress: 'info',
  withdrawn: 'neutral',
  paused: 'caution',
}

export default function PathwayProgressClient({
  org_id,
  orgslug,
}: {
  org_id: number
  orgslug: string
}) {
  void org_id
  void orgslug

  const [studentId, setStudentId] = useState('')

  // A picker, never a raw-id text box. `/sms/identity/people?role=STUDENT`
  // describes itself as "the picker source for enrolling a student", and its
  // gate matches the set that may use this module.
  const students = useApiResource<SchoolPerson[]>(() => listSchoolPeople('STUDENT'), [])

  const progress = useApiResource<StudentPathwayProgress[]>(
    () => getStudentPathwayProgress(Number(studentId)),
    [studentId],
    { skip: !studentId }
  )

  const rows = progress.data ?? []

  const tableState: DataTableState = !studentId
    ? 'empty'
    : progress.status === 'loading'
      ? 'loading'
      : progress.status === 'error'
        ? 'error'
        : rows.length === 0
          ? 'empty'
          : 'success'

  const columns: DataTableColumn<StudentPathwayProgress>[] = [
    {
      key: 'pathway',
      header: 'Pathway',
      render: (row) => <span className="font-medium">{row.pathway_name}</span>,
    },
    {
      key: 'status',
      header: 'Status',
      render: (row) => (
        <StatusChip
          label={row.status.replace(/_/g, ' ')}
          tone={STATUS_TONE[row.status] ?? 'neutral'}
        />
      ),
    },
    {
      key: 'required',
      header: 'Credits required',
      render: (row) => <span className="tabular-nums">{row.total_required_credits}</span>,
    },
    {
      key: 'earned',
      header: 'Credits earned',
      render: (row) =>
        row.earned_credits === null ? (
          // NOT "0". Nobody is counting; that is a different fact from zero.
          <span className="text-xs text-gray-500">Not tracked</span>
        ) : (
          <span className="tabular-nums">{row.earned_credits}</span>
        ),
    },
    {
      key: 'enrolled',
      header: 'Enrolled',
      render: (row) => (
        <span className="tabular-nums">{row.enrolled_at.slice(0, 10)}</span>
      ),
    },
  ]

  // Every row carries the same reason, so show it once rather than repeating it
  // in every cell.
  const reason = rows.find((r) => r.detail)?.detail ?? null

  return (
    <DashPageShell
      title="Pathway enrolments"
      description="Which pathways a student is on. Credit completion is not tracked by this system."
      module="pathways"
    >
      <SectionCard
        title="Choose a student"
        description="Enrolments are listed per student; there is no endpoint listing a pathway's cohort."
      >
        <div className="max-w-md">
          <label className="sr-only" htmlFor="pathways-progress-student">
            Student
          </label>
          <select
            id="pathways-progress-student"
            className={LH_INPUT}
            value={studentId}
            onChange={(e) => setStudentId(e.target.value)}
            disabled={students.status === 'loading' || students.status === 'error'}
          >
            <option value="">
              {students.status === 'loading'
                ? 'Loading students…'
                : students.status === 'error'
                  ? 'Student list unavailable'
                  : 'Choose a student…'}
            </option>
            {(students.data ?? []).map((p) => (
              <option key={p.user_id} value={p.user_id}>
                {p.name ?? `Student #${p.user_id}`}
              </option>
            ))}
          </select>
        </div>
      </SectionCard>

      <SectionCard title="Enrolments">
        {reason ? (
          <p className="mb-3 flex items-start gap-2 rounded-md bg-amber-50 p-3 text-sm text-amber-900">
            <Info className="mt-0.5 size-4 shrink-0" />
            <span>{reason}</span>
          </p>
        ) : null}

        <DataTable<StudentPathwayProgress>
          columns={columns}
          rows={rows}
          rowKey={(row) => row.id}
          state={tableState}
          error={progress.error}
          onRetry={progress.refetch}
          emptyIcon={Route}
          emptyTitle={studentId ? 'Not enrolled on any pathway' : 'Choose a student'}
          emptyDescription={
            studentId
              ? 'This student is not enrolled on a pathway. Enrol them from the Pathways tab.'
              : 'Pick a student above to see the pathways they are enrolled on.'
          }
        />
      </SectionCard>
    </DashPageShell>
  )
}
