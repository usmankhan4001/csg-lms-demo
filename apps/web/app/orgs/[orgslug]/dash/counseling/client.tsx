'use client'

/**
 * The counselling workspace -- the first UI this module has ever had. Nine
 * endpoints in `sms_counseling.py` were live and unreachable.
 *
 * IT IS STUDENT-SCOPED, NOT A CASELOAD, AND THAT IS A BACKEND LIMIT, NOT A
 * DESIGN CHOICE. Every session read in that router is keyed on a student
 * (`/sessions/student/{id}`, `sms_counseling.py:127`); there is no endpoint
 * that lists a psychologist's own sessions across students. A "my caseload"
 * screen cannot be built without one, so this asks for a student and says so
 * plainly rather than implying the list shown is everything.
 *
 * THE CONFIDENTIALITY RULE (DESIGN-SYSTEM.md, enforced in
 * `services/sms/counseling.py`): an unauthorised caller receives an EMPTY
 * LIST, never a 403, because a 403 confirms the record exists. This screen
 * therefore has NO permission-denied branch for session reads -- deliberately.
 * "No sessions recorded" is the single rendering for both "this child has
 * never been seen" and "you may not see this", and those two must remain
 * indistinguishable. Adding a "you do not have access" message here would
 * leak, in words, exactly what the backend goes to such lengths to hide.
 *
 * No student names anywhere: `/sms/identity/people` is gated
 * `[SUPER_ADMIN, SCHOOL_ADMIN, STAFF, TEACHER]` (`sms_identity.py:383`) and
 * PSYCHOLOGIST is not in it, so the name join every other module uses would
 * 403 for the only role that can open this page.
 */

import { useState } from 'react'
import { HeartHandshake, NotebookPen, ShieldAlert, Signal } from 'lucide-react'
import {
  DashPageShell,
  DataTable,
  EmptyState,
  LH_INPUT,
  LH_LABEL,
  LH_PRIMARY_BUTTON,
  LH_SECONDARY_BUTTON,
  SchoolDialog,
  SchoolField,
  SectionCard,
  StatusChip,
} from '@/components/widgets'
import { ApiError } from '@/lib/api/api-client'
import { useApiResource } from '@/lib/api/useApiResource'
import {
  createActivityLog,
  createSession,
  listStudentActivityLogs,
  listStudentSessions,
} from '@/modules/sms/counseling/api'
import { listPastoralConcerns } from '@/modules/sms/attendance/api'
import type { PastoralConcernRead } from '@/modules/sms/attendance/types'
import {
  formatDate,
  formatDateTime,
  formatDuration,
  severityTone,
  sharingLabel,
  studentLabel,
} from '@/modules/sms/counseling/presentation'
import type {
  ActivityLogRead,
  CounselingSessionRead,
} from '@/modules/sms/counseling/types'
import { SessionDetailDialog } from '@/modules/sms/counseling/components/SessionDetailDialog'

interface Props {
  org_id: number
  orgslug: string
}

const SEVERITIES = ['low', 'medium', 'high']

export default function CounselingDashClient({ org_id }: Props) {
  const [studentInput, setStudentInput] = useState('')
  const [studentId, setStudentId] = useState<number | null>(null)
  const [openSession, setOpenSession] = useState<CounselingSessionRead | null>(null)
  const [creatingSession, setCreatingSession] = useState(false)
  const [loggingSignal, setLoggingSignal] = useState(false)
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)

  const sessions = useApiResource(
    () => listStudentSessions(studentId as number),
    [studentId],
    { skip: studentId === null, isEmpty: (d) => d.length === 0 }
  )

  // THE WAY IN. This module has no caseload endpoint -- every session read is
  // keyed on a student id (`sms_counseling.py:127`) -- so without this a
  // counsellor would have to already know which child to type. Attendance's
  // pastoral queue is the school's own at-risk list, and PSYCHOLOGIST is
  // explicitly in `_PASTORAL_VIEWERS` (`sms_attendance.py:107`), so reading it
  // here is permitted rather than a borrowed privilege. This is the truancy
  // detection -> counsellor handoff actually closing.
  const concerns = useApiResource(
    () => listPastoralConcerns({ status: 'OPEN' }),
    [],
    { isEmpty: (d) => d.length === 0 }
  )

  const signals = useApiResource(
    () => listStudentActivityLogs(studentId as number),
    [studentId],
    { skip: studentId === null, isEmpty: (d) => d.length === 0 }
  )

  function selectStudent(e: React.FormEvent) {
    e.preventDefault()
    const parsed = Number(studentInput.trim())
    if (!parsed || parsed < 1 || !Number.isInteger(parsed)) {
      setFormError('Enter a numeric student id.')
      return
    }
    setFormError(null)
    setStudentId(parsed)
  }

  function describeError(err: unknown): string {
    if (err instanceof ApiError) {
      // NOTE: a 404 here is the confidentiality 404, not a missing page. It
      // is deliberately worded as absence, never as refusal.
      if (err.status === 404) return 'No matching record.'
      return err.message
    }
    return 'Could not save. Try again.'
  }

  async function submitSession(values: {
    session_date: string
    duration_minutes: string
    notes: string
    follow_up_plan: string
    share_summary_with_parent: boolean
    parent_visible_summary: string
  }) {
    if (studentId === null) return
    setSaving(true)
    setFormError(null)
    try {
      await createSession({
        student_id: studentId,
        session_date: new Date(values.session_date).toISOString(),
        duration_minutes: Number(values.duration_minutes),
        notes: values.notes,
        follow_up_plan: values.follow_up_plan || null,
        share_summary_with_parent: values.share_summary_with_parent,
        parent_visible_summary: values.parent_visible_summary || null,
      })
      setCreatingSession(false)
      sessions.refetch()
    } catch (err) {
      setFormError(describeError(err))
    } finally {
      setSaving(false)
    }
  }

  async function submitSignal(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (studentId === null) return
    const form = new FormData(e.currentTarget)
    const signalType = String(form.get('signal_type') ?? '').trim()
    const description = String(form.get('description') ?? '').trim()
    if (!signalType || !description) {
      setFormError('Signal type and description are both required.')
      return
    }
    setSaving(true)
    setFormError(null)
    try {
      await createActivityLog({
        student_id: studentId,
        signal_type: signalType,
        description,
        severity: String(form.get('severity') ?? 'low'),
      })
      setLoggingSignal(false)
      signals.refetch()
    } catch (err) {
      setFormError(describeError(err))
    } finally {
      setSaving(false)
    }
  }

  const hasStudent = studentId !== null

  return (
    <DashPageShell
      module="counseling"
      title="Counselling"
      description="Confidential 1:1 session records and wellbeing signals. Visible only to the counsellor who recorded them."
    >
      <SectionCard
        id="counseling-referrals"
        title="Flagged by attendance"
        icon={<ShieldAlert className="size-4 text-gray-500" />}
        state={concerns.status}
        error={concerns.error}
        onRetry={concerns.refetch}
        emptyTitle="No open pastoral concerns"
        emptyDescription="Nobody is currently flagged at risk by attendance. This is the school's own at-risk queue, not a counselling record."
      >
        <DataTable
          rows={concerns.data ?? []}
          rowKey={(r: PastoralConcernRead) => r.id}
          state="success"
          totalLabel={`${(concerns.data ?? []).length} open`}
          columns={[
            {
              key: 'student',
              header: 'Student',
              render: (r: PastoralConcernRead) => studentLabel(r.student_id),
            },
            { key: 'trigger', header: 'Trigger', render: (r: PastoralConcernRead) => r.trigger },
            {
              key: 'magnitude',
              header: 'Magnitude',
              align: 'right',
              /* null where the trigger has no natural magnitude -- never 0,
                 because "no measure" and "a measure of zero" differ. */
              render: (r: PastoralConcernRead) =>
                r.magnitude == null ? 'Not measured' : String(r.magnitude),
            },
            {
              key: 'raised',
              header: 'Raised',
              render: (r: PastoralConcernRead) => formatDate(r.created_at),
            },
            {
              key: 'open',
              header: '',
              render: (r: PastoralConcernRead) => (
                <button
                  type="button"
                  id={`counseling-open-concern-${r.id}`}
                  className={LH_SECONDARY_BUTTON}
                  onClick={() => {
                    setStudentInput(String(r.student_id))
                    setStudentId(r.student_id)
                    setFormError(null)
                  }}
                >
                  <span>Open record</span>
                </button>
              ),
            },
          ]}
        />
        <p className="mt-3 text-xs text-gray-500">
          These are attendance flags, not counselling records — everyone with a
          pastoral role can see them. Opening a record here shows only what you
          yourself have recorded.
        </p>
      </SectionCard>

      <SectionCard
        id="counseling-student"
        title="Choose a student"
        icon={<HeartHandshake className="size-4 text-gray-500" />}
      >
        <form onSubmit={selectStudent} className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1.5">
            <span className={LH_LABEL}>Student id</span>
            <input
              id="counseling-student-id"
              name="student_id"
              inputMode="numeric"
              className={LH_INPUT}
              placeholder="e.g. 37"
              value={studentInput}
              onChange={(e) => setStudentInput(e.target.value)}
            />
          </label>
          <button type="submit" id="counseling-student-go" className={LH_PRIMARY_BUTTON}>
            <span>Open record</span>
          </button>
          {hasStudent && (
            <span className="text-sm text-gray-500">
              Showing {studentLabel(studentId as number)}
            </span>
          )}
        </form>
        <p className="mt-3 text-xs text-gray-500">
          Records are looked up per student. This module has no cross-student
          caseload list, so what you see below is this student only — not
          everyone you are working with.
        </p>
        {formError && !creatingSession && !loggingSignal && (
          <p className="mt-2 text-sm text-rose-600">{formError}</p>
        )}
      </SectionCard>

      {!hasStudent ? (
        <SectionCard title="Sessions" icon={<NotebookPen className="size-4 text-gray-500" />}>
          <EmptyState
            title="No student selected"
            description="Enter a student id above to open their counselling record."
          />
        </SectionCard>
      ) : (
        <>
          <SectionCard
            id="counseling-sessions"
            title="Counselling sessions"
            icon={<NotebookPen className="size-4 text-gray-500" />}
            state={sessions.status}
            error={sessions.error}
            onRetry={sessions.refetch}
            /* Absence and non-authorisation share this one wording, on
               purpose. See the file header. */
            emptyTitle="No sessions recorded"
            emptyDescription="Nothing has been recorded for this student under your account."
            action={
              <button
                type="button"
                id="counseling-new-session"
                className={LH_SECONDARY_BUTTON}
                onClick={() => {
                  setFormError(null)
                  setCreatingSession(true)
                }}
              >
                <span>Log a session</span>
              </button>
            }
          >
            <DataTable
              rows={sessions.data ?? []}
              rowKey={(r) => r.id}
              state="success"
              totalLabel={`${sessions.data?.length ?? 0} session${
                (sessions.data?.length ?? 0) === 1 ? '' : 's'
              }`}
              columns={[
                {
                  key: 'date',
                  header: 'Date',
                  render: (r: CounselingSessionRead) => formatDate(r.session_date),
                },
                {
                  key: 'duration',
                  header: 'Duration',
                  render: (r: CounselingSessionRead) => formatDuration(r.duration_minutes),
                },
                {
                  key: 'followup',
                  header: 'Follow-up',
                  render: (r: CounselingSessionRead) =>
                    r.follow_up_plan ? 'Planned' : 'None recorded',
                },
                {
                  key: 'sharing',
                  header: 'Family',
                  render: (r: CounselingSessionRead) => {
                    const s = sharingLabel(r.share_summary_with_parent)
                    return <StatusChip label={s.label} tone={s.tone} />
                  },
                },
                {
                  key: 'open',
                  header: '',
                  align: 'right',
                  render: (r: CounselingSessionRead) => (
                    <button
                      type="button"
                      id={`counseling-open-${r.id}`}
                      className="text-sm font-medium text-gray-700 underline-offset-2 hover:underline"
                      onClick={() => setOpenSession(r)}
                    >
                      Open
                    </button>
                  ),
                },
              ]}
            />
          </SectionCard>

          <SectionCard
            id="counseling-signals"
            title="Wellbeing signals"
            icon={<Signal className="size-4 text-gray-500" />}
            state={signals.status}
            error={signals.error}
            onRetry={signals.refetch}
            emptyTitle="No signals recorded"
            emptyDescription="Nothing has been logged for this student under your account."
            action={
              <button
                type="button"
                id="counseling-new-signal"
                className={LH_SECONDARY_BUTTON}
                onClick={() => {
                  setFormError(null)
                  setLoggingSignal(true)
                }}
              >
                <span>Log a signal</span>
              </button>
            }
          >
            <DataTable
              rows={signals.data ?? []}
              rowKey={(r) => r.id}
              state="success"
              columns={[
                {
                  key: 'when',
                  header: 'Recorded',
                  render: (r: ActivityLogRead) => formatDateTime(r.recorded_at),
                },
                { key: 'type', header: 'Signal', render: (r: ActivityLogRead) => r.signal_type },
                {
                  key: 'severity',
                  header: 'Severity',
                  render: (r: ActivityLogRead) => (
                    <StatusChip label={r.severity} tone={severityTone(r.severity)} />
                  ),
                },
                {
                  key: 'desc',
                  header: 'Description',
                  render: (r: ActivityLogRead) => r.description,
                },
              ]}
            />
          </SectionCard>
        </>
      )}

      {openSession && (
        <SessionDetailDialog
          session={openSession}
          onClose={() => setOpenSession(null)}
          onSaved={() => {
            setOpenSession(null)
            sessions.refetch()
          }}
        />
      )}

      <NewSessionDialog
        open={creatingSession}
        onOpenChange={setCreatingSession}
        saving={saving}
        error={formError}
        onSubmit={submitSession}
      />

      <SchoolDialog
        open={loggingSignal}
        onOpenChange={setLoggingSignal}
        title="Log a wellbeing signal"
        description="A short, dated observation. Visible only to you."
        onSubmit={submitSignal}
        footer={
          <button type="submit" disabled={saving} className={LH_PRIMARY_BUTTON}>
            <span>{saving ? 'Saving…' : 'Log signal'}</span>
          </button>
        }
      >
        <SchoolField id="signal-type" label="Signal type" required>
          <input
            id="signal-type"
            name="signal_type"
            className={LH_INPUT}
            placeholder="attendance_pattern, behavioral_flag, academic_concern"
          />
        </SchoolField>
        <SchoolField id="signal-severity" label="Severity">
          <select id="signal-severity" name="severity" className={LH_INPUT} defaultValue="low">
            {SEVERITIES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </SchoolField>
        <SchoolField id="signal-description" label="Description" required>
          <textarea
            id="signal-description"
            name="description"
            rows={4}
            className={LH_INPUT}
            placeholder="What was observed."
          />
        </SchoolField>
        {formError && <p className="text-sm text-rose-600">{formError}</p>}
      </SchoolDialog>
    </DashPageShell>
  )
}

/**
 * Kept separate because the shared/private distinction needs its own
 * explanation next to the field, and burying that in the parent component
 * makes it easy to drop.
 */
function NewSessionDialog({
  open,
  onOpenChange,
  saving,
  error,
  onSubmit,
}: {
  open: boolean
  onOpenChange: (v: boolean) => void
  saving: boolean
  error: string | null
  onSubmit: (values: {
    session_date: string
    duration_minutes: string
    notes: string
    follow_up_plan: string
    share_summary_with_parent: boolean
    parent_visible_summary: string
  }) => void
}) {
  const [share, setShare] = useState(false)

  function handle(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const f = new FormData(e.currentTarget)
    onSubmit({
      session_date: String(f.get('session_date') ?? ''),
      duration_minutes: String(f.get('duration_minutes') ?? ''),
      notes: String(f.get('notes') ?? ''),
      follow_up_plan: String(f.get('follow_up_plan') ?? ''),
      share_summary_with_parent: share,
      parent_visible_summary: String(f.get('parent_visible_summary') ?? ''),
    })
  }

  return (
    <SchoolDialog
      open={open}
      onOpenChange={onOpenChange}
      title="Log a counselling session"
      description="The full record is visible only to you. A family sees nothing from this unless you write a summary and share it below."
      onSubmit={handle}
      footer={
        <button type="submit" disabled={saving} className={LH_PRIMARY_BUTTON}>
          <span>{saving ? 'Saving…' : 'Save session'}</span>
        </button>
      }
    >
      <SchoolField id="session-date" label="Session date" required>
        <input
          id="session-date"
          name="session_date"
          type="datetime-local"
          className={LH_INPUT}
          defaultValue={new Date().toISOString().slice(0, 16)}
        />
      </SchoolField>
      <SchoolField id="session-duration" label="Duration (minutes)" required>
        <input
          id="session-duration"
          name="duration_minutes"
          type="number"
          min={1}
          max={480}
          className={LH_INPUT}
          defaultValue={45}
        />
      </SchoolField>
      <SchoolField
        id="session-notes"
        label="Clinical notes"
        required
        help="Never shown to the student or their family."
      >
        <textarea id="session-notes" name="notes" rows={5} className={LH_INPUT} />
      </SchoolField>
      <SchoolField id="session-followup" label="Follow-up plan" help="Also private to you.">
        <textarea id="session-followup" name="follow_up_plan" rows={3} className={LH_INPUT} />
      </SchoolField>

      <div className="rounded-lg border border-gray-200 p-3">
        <label className="flex items-start gap-2 text-sm">
          <input
            id="session-share"
            name="share_summary_with_parent"
            type="checkbox"
            className="mt-0.5"
            checked={share}
            onChange={(e) => setShare(e.target.checked)}
          />
          <span>
            <span className="font-medium text-gray-800">Share a summary with the family</span>
            <span className="mt-0.5 block text-xs text-gray-500">
              Only the summary below is shared. Clinical notes and the
              follow-up plan are never included.
            </span>
          </span>
        </label>
        {share && (
          <div className="mt-3">
            <SchoolField
              id="session-parent-summary"
              label="Summary for the family"
              help="Write this as something you would be comfortable reading aloud to them."
            >
              <textarea
                id="session-parent-summary"
                name="parent_visible_summary"
                rows={3}
                className={LH_INPUT}
              />
            </SchoolField>
          </div>
        )}
      </div>

      {error && <p className="text-sm text-rose-600">{error}</p>}
    </SchoolDialog>
  )
}
