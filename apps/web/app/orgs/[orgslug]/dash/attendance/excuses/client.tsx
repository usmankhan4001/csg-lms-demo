'use client'

/**
 * The absence-note review queue.
 *
 * Parents send notes explaining an absence that already happened; until now
 * there was nowhere for them to go. Approving CONVERTS that day's ABSENT
 * records to EXCUSED (`sms_attendance.py:653`), which moves the attendance
 * percentage -- so the response reports `records_converted` and this screen
 * surfaces it verbatim.
 *
 * ZERO IS A LEGITIMATE ANSWER and the single most important thing on this
 * page. An approved note for a day where the register was never taken, or
 * where the child was marked present, converts nothing. A reviewer who sees
 * "Approved" and no other feedback will assume it failed and press again. So
 * the count is always stated, and the zero case gets its own explanation.
 */

import { useMemo, useState } from 'react'
import { MailOpen, Inbox } from 'lucide-react'
import {
  DashPageShell,
  DataTable,
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
import { listAbsenceExcuses, reviewAbsenceExcuse } from '@/modules/sms/attendance/api'
import {
  EXCUSE_TONE,
  formatDate,
  formatDateTime,
  studentLabel,
} from '@/modules/sms/attendance/presentation'
import { useStudentNames } from '@/modules/sms/attendance/useStudentNames'
import type { AbsenceExcuseRead, ExcuseStatus } from '@/modules/sms/attendance/types'

interface Props {
  org_id: number
  orgslug: string
}

const STATUSES: ExcuseStatus[] = ['PENDING', 'APPROVED', 'REJECTED']

export default function ExcusesClient({ org_id }: Props) {
  const { session } = useSchoolSession()
  const campusId = session?.campus_id ?? undefined
  const { names } = useStudentNames(campusId)

  const [statusFilter, setStatusFilter] = useState<ExcuseStatus | ''>('PENDING')
  const [reviewing, setReviewing] = useState<AbsenceExcuseRead | null>(null)
  const [decision, setDecision] = useState<'APPROVED' | 'REJECTED'>('APPROVED')
  const [note, setNote] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [outcome, setOutcome] = useState<string | null>(null)

  const excuses = useApiResource(
    () => listAbsenceExcuses({ status: statusFilter || undefined }),
    [statusFilter],
    { isEmpty: (d) => d.length === 0 }
  )

  const rows = useMemo(() => excuses.data ?? [], [excuses.data])
  const pendingCount = useMemo(
    () => rows.filter((r) => r.status === 'PENDING').length,
    [rows]
  )

  function openReview(excuse: AbsenceExcuseRead, initial: 'APPROVED' | 'REJECTED') {
    setReviewing(excuse)
    setDecision(initial)
    setNote('')
    setError(null)
    setOutcome(null)
  }

  async function handleReview(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (!reviewing) return
    setSaving(true)
    setError(null)
    try {
      const result = await reviewAbsenceExcuse(reviewing.id, {
        status: decision,
        review_note: note.trim() || null,
      })
      // Always state what actually changed. `records_converted` is the point
      // of this whole screen -- see the file header.
      const n = result.records_converted
      if (decision === 'REJECTED') {
        setOutcome('Note rejected. No register was changed.')
      } else if (n === 0) {
        setOutcome(
          'Note approved, but no register changed. Either no register was taken ' +
            'that day, or the student was not marked absent.'
        )
      } else {
        setOutcome(`Note approved. ${n} register${n === 1 ? '' : 's'} changed to Excused.`)
      }
      setReviewing(null)
      excuses.refetch()
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.kind === 'permission_denied'
            ? 'You can only review notes for sections you teach.'
            : err.message
          : 'Could not save the review.'
      )
    } finally {
      setSaving(false)
    }
  }

  return (
    <DashPageShell
      module="attendance"
      title="Absence notes"
      description="Parents' explanations for absences that have already happened. Approving changes that day's register to Excused."
    >
      <StatGrid
        state={excuses.status === 'loading' ? 'loading' : 'success'}
        columns={3}
        items={[
          { label: 'Awaiting review', value: pendingCount, icon: Inbox, tone: pendingCount > 0 ? 'caution' : 'neutral' },
          { label: 'Shown', value: rows.length, icon: MailOpen, tone: 'neutral' },
          {
            label: 'Scope',
            value: session?.roles?.includes('TEACHER') && !session?.roles?.includes('SCHOOL_ADMIN')
              ? 'Your sections'
              : 'All sections',
            icon: MailOpen,
            tone: 'neutral',
          },
        ]}
      />

      {outcome && (
        <div
          id="excuse-outcome"
          className="rounded-xl border border-gray-200/80 bg-white p-4 text-sm text-gray-700 nice-shadow"
        >
          {outcome}
        </div>
      )}

      <SectionCard
        id="excuse-queue"
        title="Review queue"
        icon={<MailOpen className="size-4 text-gray-500" />}
        state={excuses.status}
        error={excuses.error}
        onRetry={excuses.refetch}
        emptyTitle={statusFilter === 'PENDING' ? 'Nothing awaiting review' : 'No notes found'}
        emptyDescription={
          statusFilter === 'PENDING'
            ? 'Absence notes submitted by parents appear here for approval.'
            : 'Try a different status filter.'
        }
        action={
          <label className="flex items-center gap-2 text-xs text-gray-500">
            <span>Status</span>
            <select
              id="excuse-status-filter"
              className={LH_INPUT}
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as ExcuseStatus | '')}
            >
              <option value="">All</option>
              {STATUSES.map((s) => (
                <option key={s} value={s}>
                  {s.charAt(0) + s.slice(1).toLowerCase()}
                </option>
              ))}
            </select>
          </label>
        }
      >
        <DataTable
          rows={rows}
          rowKey={(r) => r.id}
          state="success"
          totalLabel={`${rows.length} note${rows.length === 1 ? '' : 's'}`}
          columns={[
            {
              key: 'student',
              header: 'Student',
              render: (r) => studentLabel(r.student_id, names),
            },
            { key: 'date', header: 'Absence date', render: (r) => formatDate(r.date) },
            {
              key: 'reason',
              header: 'Reason given',
              render: (r) => <span className="text-gray-700">{r.reason}</span>,
            },
            {
              key: 'status',
              header: 'Status',
              render: (r) => (
                <StatusChip
                  label={r.status.charAt(0) + r.status.slice(1).toLowerCase()}
                  tone={EXCUSE_TONE[r.status]}
                />
              ),
            },
            {
              key: 'reviewed',
              header: 'Reviewed',
              render: (r) => (r.reviewed_at ? formatDateTime(r.reviewed_at) : 'Not yet'),
            },
            {
              key: 'actions',
              header: '',
              render: (r) =>
                r.status === 'PENDING' ? (
                  <div className="flex gap-2">
                    <button
                      id={`excuse-approve-${r.id}`}
                      type="button"
                      className={LH_SECONDARY_BUTTON}
                      onClick={() => openReview(r, 'APPROVED')}
                    >
                      Approve
                    </button>
                    <button
                      id={`excuse-reject-${r.id}`}
                      type="button"
                      className={LH_SECONDARY_BUTTON}
                      onClick={() => openReview(r, 'REJECTED')}
                    >
                      Reject
                    </button>
                  </div>
                ) : (
                  <span className="text-xs text-gray-400">Reviewed</span>
                ),
            },
          ]}
        />
      </SectionCard>

      <SchoolDialog
        open={reviewing !== null}
        onOpenChange={(open) => !open && setReviewing(null)}
        title={decision === 'APPROVED' ? 'Approve this absence note' : 'Reject this absence note'}
        description={
          decision === 'APPROVED'
            ? "Approving changes that day's register from Absent to Excused. The original status is kept in the attendance trail."
            : 'Rejecting leaves the register unchanged. The family can see the reason you give.'
        }
        onSubmit={handleReview}
        footer={
          <button type="submit" disabled={saving} className={LH_PRIMARY_BUTTON}>
            <span>{saving ? 'Saving…' : decision === 'APPROVED' ? 'Approve' : 'Reject'}</span>
          </button>
        }
      >
        {reviewing && (
          <div className="rounded-lg bg-gray-50 p-3 text-sm text-gray-600">
            <div>
              <strong>{studentLabel(reviewing.student_id, names)}</strong> ·{' '}
              {formatDate(reviewing.date)}
            </div>
            <div className="mt-1">{reviewing.reason}</div>
          </div>
        )}

        <SchoolField
          id="excuse-review-note"
          label="Note for the record"
          help="Optional. Recorded against the review, not sent as a message."
        >
          <input
            id="excuse-review-note"
            className={LH_INPUT}
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="e.g. Doctor's letter seen"
          />
        </SchoolField>

        {error && <p className="text-sm text-rose-600">{error}</p>}
      </SchoolDialog>
    </DashPageShell>
  )
}
