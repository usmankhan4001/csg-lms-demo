'use client'

/**
 * Resits — a candidate's approved second sitting.
 *
 * The thing this screen must never do is imply the original mark changed. A
 * resit is a LINK between two sittings (`sms_exam_extended.py`), never an edit
 * of the first result, precisely so a school asked "why did this grade change"
 * can show both. The table therefore always names the original exam alongside
 * the resit, and an unscheduled resit reads "Not scheduled yet" rather than
 * borrowing the original's date.
 *
 * SUGGESTED CANDIDATES ARE SUGGESTIONS. `suggested_reason: null` means the
 * record shows a gap to chase — sat the paper, no mark recorded yet — and that
 * is emphatically NOT a failure. Rendering it as one would invent a result for
 * a child whose paper simply has not been marked, which is the fabrication
 * pattern this codebase has torn out seven times.
 */

import { useMemo, useState } from 'react'
import { RefreshCw, ClipboardList } from 'lucide-react'
import {
  DashPageShell,
  DataTable,
  EmptyState,
  LH_INPUT,
  LH_PRIMARY_BUTTON,
  LH_SECONDARY_BUTTON,
  SchoolDialog,
  SchoolField,
  SectionCard,
  StatGrid,
  StatusChip,
} from '@/components/widgets'
import { ApiError } from '@/lib/api/api-client'
import { useApiResource } from '@/lib/api/useApiResource'
import { useSchoolSession } from '@/lib/api/useSchoolSession'
import {
  approveResit,
  listExams,
  listResitCandidates,
  listResits,
  scheduleResit,
} from '@/modules/sms/exams/api'
import { studentLabel } from '@/modules/sms/attendance/presentation'
import { useStudentNames } from '@/modules/sms/attendance/useStudentNames'
import type {
  ResitCandidate,
  ResitRead,
  ResitReason,
  ResitStatus,
} from '@/modules/sms/exams/types'

interface Props {
  org_id: number
  orgslug: string
}

const REASONS: ResitReason[] = [
  'ABSENT',
  'ILLNESS',
  'TIMETABLE_CLASH',
  'FAILED',
  'MALPRACTICE',
  'OTHER',
]

const STATUSES: ResitStatus[] = ['APPROVED', 'SCHEDULED', 'COMPLETED', 'CANCELLED']

/** MALPRACTICE is kept visually distinct: it carries entirely different
 *  consequences for a child than simply having failed. */
const REASON_TONE: Record<ResitReason, 'neutral' | 'caution' | 'critical'> = {
  ABSENT: 'caution',
  ILLNESS: 'neutral',
  TIMETABLE_CLASH: 'neutral',
  FAILED: 'caution',
  MALPRACTICE: 'critical',
  OTHER: 'neutral',
}

const STATUS_TONE: Record<ResitStatus, 'neutral' | 'positive' | 'caution'> = {
  APPROVED: 'caution',
  SCHEDULED: 'neutral',
  COMPLETED: 'positive',
  CANCELLED: 'neutral',
}

function formatDateTime(value: string | null): string {
  if (!value) return 'Not recorded'
  const d = new Date(value)
  return Number.isNaN(d.getTime()) ? 'Not recorded' : d.toLocaleString()
}

export default function ResitsClient({ org_id }: Props) {
  const { session } = useSchoolSession()
  const campusId = session?.campus_id ?? undefined
  const { names } = useStudentNames(campusId)

  const [examId, setExamId] = useState<number | undefined>(undefined)
  const [statusFilter, setStatusFilter] = useState<ResitStatus | ''>('')
  const [approving, setApproving] = useState<ResitCandidate | null>(null)
  const [scheduling, setScheduling] = useState<ResitRead | null>(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const exams = useApiResource(() => listExams({ campusId }), [campusId], {
    isEmpty: (d) => d.length === 0,
  })

  const resits = useApiResource(
    () =>
      listResits({
        originalExamId: examId,
        resitStatus: statusFilter || undefined,
      }),
    [examId, statusFilter],
    { isEmpty: (d) => d.length === 0 }
  )

  // Candidates only make sense for one named exam — "who might resit" is not a
  // question you can ask across every exam at once.
  const candidates = useApiResource(
    () => listResitCandidates(examId as number),
    [examId],
    { skip: examId === undefined, isEmpty: (d) => d.length === 0 }
  )

  const examName = useMemo(() => {
    const map = new Map<number, string>()
    for (const e of exams.data ?? []) map.set(e.id, e.title)
    return map
  }, [exams.data])

  const rows = resits.data ?? []
  const counts = useMemo(
    () => ({
      approved: rows.filter((r) => r.status === 'APPROVED').length,
      scheduled: rows.filter((r) => r.status === 'SCHEDULED').length,
      completed: rows.filter((r) => r.status === 'COMPLETED').length,
    }),
    [rows]
  )

  async function handleApprove(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (!approving || examId === undefined) return
    const form = new FormData(e.currentTarget)
    const reason = String(form.get('reason') || '') as ResitReason
    const detail = String(form.get('reason_detail') || '').trim()
    if (!reason) {
      setError('Pick a reason — a school is regularly asked to justify a resit.')
      return
    }
    setSaving(true)
    setError(null)
    try {
      await approveResit(examId, {
        student_id: approving.student_id,
        reason,
        reason_detail: detail || null,
      })
      setApproving(null)
      resits.refetch()
      candidates.refetch()
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.kind === 'permission_denied'
            ? 'You need school-admin access to approve a resit.'
            : err.message
          : 'Could not approve. Try again.'
      )
    } finally {
      setSaving(false)
    }
  }

  async function handleSchedule(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (!scheduling) return
    const form = new FormData(e.currentTarget)
    const target = Number(form.get('resit_exam_id'))
    if (!target) {
      setError('Pick the exam the candidate will actually sit.')
      return
    }
    setSaving(true)
    setError(null)
    try {
      await scheduleResit(scheduling.id, target)
      setScheduling(null)
      resits.refetch()
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : 'Could not schedule. Try again.'
      )
    } finally {
      setSaving(false)
    }
  }

  return (
    <DashPageShell
      module="exams"
      title="Resits"
      description="Approved second sittings. The original result is never edited — both sittings stay on the record."
    >
      <StatGrid
        state={resits.status === 'loading' ? 'loading' : 'success'}
        columns={3}
        items={[
          {
            label: 'Approved, not scheduled',
            value: counts.approved,
            icon: ClipboardList,
            tone: counts.approved > 0 ? 'caution' : 'neutral',
          },
          { label: 'Scheduled', value: counts.scheduled, icon: RefreshCw, tone: 'neutral' },
          {
            label: 'Completed',
            value: counts.completed,
            icon: ClipboardList,
            tone: 'neutral',
          },
        ]}
      />

      <SectionCard title="Filter">
        <div className="flex flex-wrap items-end gap-4">
          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-medium text-gray-500">Original exam</span>
            <select
              id="resits-exam"
              className={LH_INPUT}
              value={examId ?? ''}
              onChange={(ev) =>
                setExamId(ev.target.value ? Number(ev.target.value) : undefined)
              }
            >
              <option value="">All exams</option>
              {(exams.data ?? []).map((e) => (
                <option key={e.id} value={e.id}>
                  {e.title}
                </option>
              ))}
            </select>
          </label>

          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-medium text-gray-500">Status</span>
            <select
              id="resits-status"
              className={LH_INPUT}
              value={statusFilter}
              onChange={(ev) => setStatusFilter(ev.target.value as ResitStatus | '')}
            >
              <option value="">Any status</option>
              {STATUSES.map((s) => (
                <option key={s} value={s}>
                  {s.charAt(0) + s.slice(1).toLowerCase()}
                </option>
              ))}
            </select>
          </label>
        </div>
      </SectionCard>

      {examId !== undefined && (
        <SectionCard
          title="Suggested candidates"
          description="What the record shows, never an inference. A school decides whether a child resits."
          state={candidates.status}
          error={candidates.error}
          onRetry={candidates.refetch}
          emptyTitle="No candidates to suggest"
          emptyDescription="Nobody on this exam is recorded absent or unmarked."
        >
          <DataTable
            rows={candidates.data ?? []}
            rowKey={(r) => r.student_id}
            state="success"
            columns={[
              {
                key: 'student',
                header: 'Candidate',
                render: (r) => studentLabel(r.student_id, names),
              },
              {
                key: 'suggestion',
                header: 'Suggestion',
                render: (r) =>
                  r.suggested_reason ? (
                    <StatusChip
                      label={r.suggested_reason.replace('_', ' ').toLowerCase()}
                      tone={REASON_TONE[r.suggested_reason]}
                    />
                  ) : (
                    // Deliberately NOT a resit reason. An unmarked paper is a
                    // gap to chase, not a failure.
                    <StatusChip label="Chase — not a resit" tone="neutral" />
                  ),
              },
              { key: 'evidence', header: 'Evidence', render: (r) => r.evidence },
              {
                key: 'action',
                header: '',
                align: 'right',
                render: (r) =>
                  r.suggested_reason ? (
                    <button
                      type="button"
                      id={`approve-${r.student_id}`}
                      className={LH_SECONDARY_BUTTON}
                      onClick={() => {
                        setError(null)
                        setApproving(r)
                      }}
                    >
                      Approve resit
                    </button>
                  ) : null,
              },
            ]}
          />
        </SectionCard>
      )}

      <SectionCard
        title="Resits"
        state={resits.status}
        error={resits.error}
        onRetry={resits.refetch}
        emptyTitle="No resits recorded"
        emptyDescription="Approved second sittings appear here with their reason and both exams."
      >
        <DataTable
          rows={rows}
          rowKey={(r) => r.id}
          state="success"
          totalLabel={`${rows.length} resit${rows.length === 1 ? '' : 's'}`}
          columns={[
            {
              key: 'student',
              header: 'Candidate',
              render: (r) => studentLabel(r.student_id, names),
            },
            {
              key: 'original',
              header: 'Original exam',
              render: (r) => examName.get(r.original_exam_id) ?? `Exam #${r.original_exam_id}`,
            },
            {
              key: 'resit_exam',
              header: 'Resit exam',
              render: (r) =>
                r.resit_exam_id
                  ? examName.get(r.resit_exam_id) ?? `Exam #${r.resit_exam_id}`
                  : // Approval comes before scheduling, so this is a real and
                    // common state — not a missing value to paper over.
                    'Not scheduled yet',
            },
            {
              key: 'reason',
              header: 'Reason',
              render: (r) => (
                <StatusChip
                  label={r.reason.replace('_', ' ').toLowerCase()}
                  tone={REASON_TONE[r.reason]}
                />
              ),
            },
            {
              key: 'status',
              header: 'Status',
              render: (r) => (
                <StatusChip
                  label={r.status.charAt(0) + r.status.slice(1).toLowerCase()}
                  tone={STATUS_TONE[r.status]}
                />
              ),
            },
            {
              key: 'approved',
              header: 'Approved',
              render: (r) => formatDateTime(r.approved_at),
            },
            {
              key: 'action',
              header: '',
              align: 'right',
              render: (r) =>
                r.status === 'APPROVED' ? (
                  <button
                    type="button"
                    id={`schedule-${r.id}`}
                    className={LH_SECONDARY_BUTTON}
                    onClick={() => {
                      setError(null)
                      setScheduling(r)
                    }}
                  >
                    Schedule
                  </button>
                ) : null,
            },
          ]}
        />
      </SectionCard>

      {approving && (
        <SchoolDialog
          open
          onOpenChange={(o) => !o && setApproving(null)}
          title="Approve a resit"
          description="Recorded rather than inferred — a school is regularly asked to justify a resit, and 'the system decided' is not an answer."
          onSubmit={handleApprove}
          footer={
            <button type="submit" disabled={saving} className={LH_PRIMARY_BUTTON}>
              <span>{saving ? 'Approving…' : 'Approve'}</span>
            </button>
          }
        >
          <p className="text-sm text-gray-600">
            {studentLabel(approving.student_id, names)} — {approving.evidence}
          </p>

          <SchoolField id="reason" label="Reason" required>
            <select
              id="reason"
              name="reason"
              className={LH_INPUT}
              defaultValue={approving.suggested_reason ?? ''}
            >
              <option value="" disabled>
                Choose a reason…
              </option>
              {REASONS.map((r) => (
                <option key={r} value={r}>
                  {r.replace('_', ' ').toLowerCase()}
                </option>
              ))}
            </select>
          </SchoolField>

          <SchoolField
            id="reason_detail"
            label="Detail"
            help="Optional. Anything a colleague would need to understand this decision later."
          >
            <input id="reason_detail" name="reason_detail" className={LH_INPUT} />
          </SchoolField>

          {error && <p className="text-sm text-rose-600">{error}</p>}
        </SchoolDialog>
      )}

      {scheduling && (
        <SchoolDialog
          open
          onOpenChange={(o) => !o && setScheduling(null)}
          title="Schedule the second sitting"
          description="Attach this approved resit to the exam the candidate will actually sit. The original result is untouched."
          onSubmit={handleSchedule}
          footer={
            <button type="submit" disabled={saving} className={LH_PRIMARY_BUTTON}>
              <span>{saving ? 'Scheduling…' : 'Schedule'}</span>
            </button>
          }
        >
          <SchoolField id="resit_exam_id" label="Resit exam" required>
            <select id="resit_exam_id" name="resit_exam_id" className={LH_INPUT} defaultValue="">
              <option value="" disabled>
                Choose an exam…
              </option>
              {(exams.data ?? [])
                // A resit cannot point at the exam it is a resit OF — the API
                // refuses it, so it is not offered here either.
                .filter((e) => e.id !== scheduling.original_exam_id)
                .map((e) => (
                  <option key={e.id} value={e.id}>
                    {e.title}
                  </option>
                ))}
            </select>
          </SchoolField>

          {error && <p className="text-sm text-rose-600">{error}</p>}
        </SchoolDialog>
      )}

      {resits.status === 'success' && rows.length === 0 && examId === undefined && (
        <EmptyState
          title="Pick an exam to see who might resit"
          description="Suggested candidates are drawn from what the record shows for one named exam."
        />
      )}
    </DashPageShell>
  )
}
