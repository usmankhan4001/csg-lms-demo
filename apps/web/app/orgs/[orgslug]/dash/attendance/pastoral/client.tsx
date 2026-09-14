'use client'

/**
 * The at-risk queue: which students are flagged right now, and what has been
 * done about it.
 *
 * This is the screen that makes the absence-streak detector mean something.
 * The detector has always fired correctly, and its only subscriber emailed a
 * guardian -- with email unconfigured by default, that meant nobody was told
 * and the escalation ended nowhere.
 *
 * SCOPE HONESTY. The backend permits TEACHER but narrows them to sections they
 * teach (`_pastoral_section_scope`, sms_attendance.py); leadership and the
 * counsellor see everything. So this page states which of the two the viewer
 * is getting, and never offers a "whole school" control that would 403. A
 * teacher seeing three concerns must not conclude the school has three.
 *
 * Resolution is deliberately a human act -- a concern is never auto-closed by
 * a student returning, because a child who missed four days and came back
 * still warrants a conversation.
 */

import { useMemo, useState } from 'react'
import { HeartPulse, ShieldAlert } from 'lucide-react'
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
import {
  listConcernInterventions,
  listPastoralConcerns,
  recordConcernIntervention,
  updatePastoralConcern,
} from '@/modules/sms/attendance/api'
import {
  CONCERN_LABEL,
  CONCERN_TONE,
  formatDate,
  formatDateTime,
  formatMagnitude,
  studentLabel,
} from '@/modules/sms/attendance/presentation'
import { useStudentNames } from '@/modules/sms/attendance/useStudentNames'
import type {
  PastoralConcernRead,
  PastoralConcernStatus,
} from '@/modules/sms/attendance/types'

interface Props {
  org_id: number
  orgslug: string
}

const STATUSES: PastoralConcernStatus[] = ['OPEN', 'IN_PROGRESS', 'RESOLVED']

export default function PastoralClient({ org_id }: Props) {
  const { session } = useSchoolSession()
  const campusId = session?.campus_id ?? undefined
  const { names } = useStudentNames(campusId)

  // Mirrors the server's own rule: a teacher who is not also leadership is
  // scoped to their sections. Stated, never silently applied.
  const roles = session?.roles ?? []
  const seesWholeSchool =
    roles.includes('SCHOOL_ADMIN') ||
    roles.includes('SUPER_ADMIN') ||
    roles.includes('PSYCHOLOGIST')

  const [statusFilter, setStatusFilter] = useState<PastoralConcernStatus | ''>('OPEN')
  const [acting, setActing] = useState<PastoralConcernRead | null>(null)
  const [resolving, setResolving] = useState<PastoralConcernRead | null>(null)
  const [action, setAction] = useState('')
  const [note, setNote] = useState('')
  const [outcomeText, setOutcomeText] = useState('')
  const [resolutionNote, setResolutionNote] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const concerns = useApiResource(
    () => listPastoralConcerns({ status: statusFilter || undefined }),
    [statusFilter],
    { isEmpty: (d) => d.length === 0 }
  )

  const rows = useMemo(() => concerns.data ?? [], [concerns.data])
  const openCount = useMemo(() => rows.filter((r) => r.status === 'OPEN').length, [rows])

  const interventions = useApiResource(
    () => listConcernInterventions(acting?.id ?? 0),
    [acting?.id],
    { skip: acting === null, isEmpty: (d) => d.length === 0 }
  )

  async function handleIntervention(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (!acting) return
    if (!action.trim()) {
      setError('Say what was done.')
      return
    }
    setSaving(true)
    setError(null)
    try {
      await recordConcernIntervention(acting.id, {
        action: action.trim(),
        note: note.trim() || null,
        outcome: outcomeText.trim() || null,
      })
      setAction('')
      setNote('')
      setOutcomeText('')
      interventions.refetch()
      concerns.refetch()
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.kind === 'permission_denied'
            ? 'You can only act on concerns for sections you teach.'
            : err.message
          : 'Could not record what was done.'
      )
    } finally {
      setSaving(false)
    }
  }

  async function handleResolve(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (!resolving) return
    setSaving(true)
    setError(null)
    try {
      await updatePastoralConcern(resolving.id, {
        status: 'RESOLVED',
        resolution_note: resolutionNote.trim() || null,
      })
      setResolving(null)
      setResolutionNote('')
      concerns.refetch()
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.kind === 'permission_denied'
            ? 'You can only resolve concerns for sections you teach.'
            : err.message
          : 'Could not resolve the concern.'
      )
    } finally {
      setSaving(false)
    }
  }

  return (
    <DashPageShell
      module="attendance"
      title="At-risk students"
      description="Students flagged by attendance patterns, and what staff have done about each one."
    >
      <div className="rounded-xl border border-gray-200/80 bg-white p-4 text-sm text-gray-600 nice-shadow">
        {seesWholeSchool ? (
          <>Showing concerns across <strong>all sections</strong> you oversee.</>
        ) : (
          <>
            Showing concerns for <strong>the sections you teach</strong> only. A colleague
            may see others.
          </>
        )}
      </div>

      <StatGrid
        state={concerns.status === 'loading' ? 'loading' : 'success'}
        columns={3}
        items={[
          {
            label: 'Open',
            value: openCount,
            icon: ShieldAlert,
            tone: openCount > 0 ? 'critical' : 'positive',
          },
          { label: 'Shown', value: rows.length, icon: HeartPulse, tone: 'neutral' },
          {
            label: 'Scope',
            value: seesWholeSchool ? 'All sections' : 'Your sections',
            icon: HeartPulse,
            tone: 'neutral',
          },
        ]}
      />

      <SectionCard
        id="pastoral-queue"
        title="Concerns"
        icon={<ShieldAlert className="size-4 text-gray-500" />}
        state={concerns.status}
        error={concerns.error}
        onRetry={concerns.refetch}
        emptyTitle={statusFilter === 'OPEN' ? 'No open concerns' : 'No concerns found'}
        emptyDescription={
          statusFilter === 'OPEN'
            ? 'Students flagged by an absence streak appear here. Nothing open means nothing needs chasing right now.'
            : 'Try a different status filter.'
        }
        action={
          <label className="flex items-center gap-2 text-xs text-gray-500">
            <span>Status</span>
            <select
              id="pastoral-status-filter"
              className={LH_INPUT}
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as PastoralConcernStatus | '')}
            >
              <option value="">All</option>
              {STATUSES.map((s) => (
                <option key={s} value={s}>
                  {CONCERN_LABEL[s]}
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
          totalLabel={`${rows.length} concern${rows.length === 1 ? '' : 's'}`}
          columns={[
            {
              key: 'student',
              header: 'Student',
              render: (r) => studentLabel(r.student_id, names),
            },
            { key: 'trigger', header: 'Why', render: (r) => r.trigger },
            {
              key: 'magnitude',
              header: 'Extent',
              render: (r) => formatMagnitude(r.magnitude),
            },
            { key: 'raised', header: 'Raised', render: (r) => formatDate(r.created_at) },
            {
              key: 'status',
              header: 'Status',
              render: (r) => (
                <StatusChip label={CONCERN_LABEL[r.status]} tone={CONCERN_TONE[r.status]} />
              ),
            },
            {
              key: 'actions',
              header: '',
              render: (r) => (
                <div className="flex gap-2">
                  <button
                    id={`pastoral-act-${r.id}`}
                    type="button"
                    className={LH_SECONDARY_BUTTON}
                    onClick={() => {
                      setActing(r)
                      setError(null)
                    }}
                  >
                    Log action
                  </button>
                  {r.status !== 'RESOLVED' && (
                    <button
                      id={`pastoral-resolve-${r.id}`}
                      type="button"
                      className={LH_SECONDARY_BUTTON}
                      onClick={() => {
                        setResolving(r)
                        setError(null)
                      }}
                    >
                      Resolve
                    </button>
                  )}
                </div>
              ),
            },
          ]}
        />
      </SectionCard>

      {/* Log an intervention, and show what has already been done. */}
      <SchoolDialog
        open={acting !== null}
        onOpenChange={(open) => !open && setActing(null)}
        title={acting ? `What has been done — ${studentLabel(acting.student_id, names)}` : ''}
        description="Interventions are append-only: to correct a mistake, add another. Each one records an action that happened at a point in time."
        onSubmit={handleIntervention}
        footer={
          <button type="submit" disabled={saving} className={LH_PRIMARY_BUTTON}>
            <span>{saving ? 'Saving…' : 'Record action'}</span>
          </button>
        }
      >
        <div className="max-h-48 overflow-y-auto rounded-lg bg-gray-50 p-3 text-sm">
          {interventions.status === 'loading' && (
            <p className="text-gray-400">Loading what has been done…</p>
          )}
          {interventions.status === 'empty' && (
            <p className="text-gray-500">Nothing recorded yet. This will be the first action.</p>
          )}
          {interventions.status === 'error' && (
            <p className="text-rose-600">Could not load previous actions.</p>
          )}
          {(interventions.data ?? []).map((i) => (
            <div key={i.id} className="border-b border-gray-200 py-2 last:border-0">
              <div className="font-medium text-gray-800">{i.action}</div>
              {i.note && <div className="text-gray-600">{i.note}</div>}
              {i.outcome && <div className="text-gray-600">Outcome: {i.outcome}</div>}
              <div className="text-xs text-gray-400">{formatDateTime(i.created_at)}</div>
            </div>
          ))}
        </div>

        <SchoolField id="pastoral-action" label="What was done" required>
          <input
            id="pastoral-action"
            className={LH_INPUT}
            value={action}
            onChange={(e) => setAction(e.target.value)}
            placeholder="e.g. Called guardian"
          />
        </SchoolField>

        <SchoolField id="pastoral-note" label="Note">
          <input
            id="pastoral-note"
            className={LH_INPUT}
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Optional detail"
          />
        </SchoolField>

        <SchoolField id="pastoral-outcome" label="Outcome">
          <input
            id="pastoral-outcome"
            className={LH_INPUT}
            value={outcomeText}
            onChange={(e) => setOutcomeText(e.target.value)}
            placeholder="Optional — what came of it"
          />
        </SchoolField>

        {error && <p className="text-sm text-rose-600">{error}</p>}
      </SchoolDialog>

      <SchoolDialog
        open={resolving !== null}
        onOpenChange={(open) => !open && setResolving(null)}
        title="Resolve this concern"
        description="Resolving is a human judgement, not an automatic consequence of the student returning. Say what happened."
        onSubmit={handleResolve}
        footer={
          <button type="submit" disabled={saving} className={LH_PRIMARY_BUTTON}>
            <span>{saving ? 'Saving…' : 'Resolve'}</span>
          </button>
        }
      >
        <SchoolField
          id="pastoral-resolution"
          label="Resolution note"
          help="Recorded against the concern so the next person reading it knows why it was closed."
        >
          <input
            id="pastoral-resolution"
            className={LH_INPUT}
            value={resolutionNote}
            onChange={(e) => setResolutionNote(e.target.value)}
            placeholder="e.g. Family meeting held, attendance improved"
          />
        </SchoolField>
        {error && <p className="text-sm text-rose-600">{error}</p>}
      </SchoolDialog>
    </DashPageShell>
  )
}
