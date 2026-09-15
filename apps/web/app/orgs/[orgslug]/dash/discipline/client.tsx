'use client'

/**
 * The behaviour-incident workspace -- the first UI this module has ever had.
 * Five endpoints in `sms_discipline.py` were live, role-gated and unreachable,
 * while BOTH sidebars already linked to `/dash/discipline`. The nav entry has
 * been a dead link (DashLeftMenu.tsx:817, DashMobileMenu.tsx:352).
 *
 * WHO CAN SEE WHAT, established from the router rather than assumed:
 * all four incident endpoints share ONE gate
 * `[SUPER_ADMIN, SCHOOL_ADMIN, TEACHER, STAFF, PSYCHOLOGIST]`
 * (sms_discipline.py:131,148,164,174), so a teacher, a staff member and a
 * psychologist see exactly the same incidents. The only genuine split is that
 * suspensions require `[SUPER_ADMIN, SCHOOL_ADMIN]` (`:184`). PARENT and
 * STUDENT appear in no gate, so there is no family-facing view and this screen
 * does not imply one.
 *
 * WHY THERE IS A PERMISSION-DENIED BRANCH HERE, unlike the counselling module:
 * the two have opposite disclosure rules and conflating them would be a leak
 * in one direction or a lie in the other. A counselling record's EXISTENCE is
 * confidential, so that module renders the empty state for an unauthorised
 * caller and never says "denied". A disciplinary incident is ordinary school
 * business -- the API answers a teacher hitting the suspension endpoint with a
 * plain 403, and showing that honestly is correct. What must NOT happen is the
 * reverse: rendering "you do not have permission" where the backend returned
 * an empty list, because that would assert a record exists.
 *
 * NO STUDENT NAMES. `/sms/identity/people` is gated
 * `[SUPER_ADMIN, SCHOOL_ADMIN, STAFF, TEACHER]` (sms_identity.py:383) and
 * PSYCHOLOGIST is not in it, so the name join other modules use would 403 for
 * one of the roles that can open this page. Students are shown by id, the same
 * compromise the counselling module made.
 */

import { useMemo, useState } from 'react'
import { AlertTriangle, ClipboardList, ShieldAlert } from 'lucide-react'

import {
  DashPageShell,
  DataTable,
  SchoolDialog,
  SchoolField,
  SectionCard,
  StatusChip,
  LH_INPUT,
  LH_PRIMARY_BUTTON,
  LH_SECONDARY_BUTTON,
  type DataTableColumn,
  type DataTableState,
  type StatusTone,
} from '@/components/widgets'
import { useApiResource } from '@/lib/api/useApiResource'
import { createIncident, listIncidents, updateIncident } from '@/modules/sms/discipline/api'
import {
  SEVERITY_ORDER,
  STATUS_ORDER,
  UNMUTABLE_SEVERITIES,
  type Incident,
  type IncidentSeverity,
  type IncidentStatus,
} from '@/modules/sms/discipline/types'

const SEVERITY_TONE: Record<IncidentSeverity, StatusTone> = {
  minor: 'neutral',
  moderate: 'caution',
  major: 'critical',
  critical: 'critical',
}

const STATUS_TONE: Record<IncidentStatus, StatusTone> = {
  open: 'caution',
  investigating: 'info',
  resolved: 'positive',
  appealed: 'caution',
}

function titleCase(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1)
}

export default function DisciplineDashClient({
  org_id,
  orgslug,
}: {
  org_id: number
  orgslug: string
}) {
  void org_id
  void orgslug

  const [severity, setSeverity] = useState<IncidentSeverity | ''>('')
  const [statusFilter, setStatusFilter] = useState<IncidentStatus | ''>('')
  const [logOpen, setLogOpen] = useState(false)

  const incidents = useApiResource<Incident[]>(
    () =>
      listIncidents({
        severity: severity || undefined,
        status_filter: statusFilter || undefined,
      }),
    [severity, statusFilter]
  )

  const rows = incidents.data ?? []

  // Counts describe the ROWS ON SCREEN, not the school. With a filter applied
  // "3 open" would otherwise read as the school's total, which it is not.
  const openOnScreen = useMemo(
    () => rows.filter((r) => r.status === 'open' || r.status === 'investigating').length,
    [rows]
  )

  const tableState: DataTableState =
    incidents.status === 'loading'
      ? 'loading'
      : incidents.status === 'error'
        ? 'error'
        : rows.length === 0
          ? 'empty'
          : 'success'

  const columns: DataTableColumn<Incident>[] = [
    {
      key: 'date',
      header: 'Date',
      render: (row) => <span className="tabular-nums">{row.incident_date}</span>,
    },
    {
      key: 'student',
      header: 'Student',
      render: (row) => <span className="tabular-nums">#{row.student_id}</span>,
    },
    {
      key: 'title',
      header: 'Incident',
      render: (row) => (
        <div className="min-w-0">
          <div className="font-medium truncate">{row.title}</div>
          {row.location ? (
            <div className="text-xs text-gray-500 truncate">{row.location}</div>
          ) : null}
        </div>
      ),
    },
    {
      key: 'severity',
      header: 'Severity',
      render: (row) => (
        <StatusChip label={titleCase(row.severity)} tone={SEVERITY_TONE[row.severity]} />
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (row) => (
        <StatusChip label={titleCase(row.status)} tone={STATUS_TONE[row.status]} />
      ),
    },
    {
      key: 'parent',
      header: 'Family told',
      render: (row) =>
        row.parent_notified ? (
          <StatusChip
            label={row.parent_acknowledgement ? 'Acknowledged' : 'Notified'}
            tone={row.parent_acknowledgement ? 'positive' : 'info'}
          />
        ) : (
          // Deliberately not "No" -- an unnotified family is an outstanding
          // action, not a settled state.
          <span className="text-xs text-gray-500">Not yet</span>
        ),
    },
  ]

  return (
    <DashPageShell
      title="Discipline"
      description="Behaviour incidents, severity and pastoral follow-up."
      module="discipline"
      action={
        <button
          type="button"
          id="discipline-log-incident"
          className={LH_PRIMARY_BUTTON}
          onClick={() => setLogOpen(true)}
        >
          Log incident
        </button>
      }
    >
      <SectionCard
        title="Incidents"
        description={
          incidents.status === 'success' && rows.length > 0
            ? `${rows.length} shown · ${openOnScreen} still open or under investigation`
            : undefined
        }
        action={
          <div className="flex flex-wrap items-center gap-2">
            <label className="sr-only" htmlFor="discipline-filter-severity">
              Filter by severity
            </label>
            <select
              id="discipline-filter-severity"
              className={LH_INPUT}
              value={severity}
              onChange={(e) => setSeverity(e.target.value as IncidentSeverity | '')}
            >
              <option value="">All severities</option>
              {SEVERITY_ORDER.map((s) => (
                <option key={s} value={s}>
                  {titleCase(s)}
                </option>
              ))}
            </select>

            <label className="sr-only" htmlFor="discipline-filter-status">
              Filter by status
            </label>
            <select
              id="discipline-filter-status"
              className={LH_INPUT}
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as IncidentStatus | '')}
            >
              <option value="">All statuses</option>
              {STATUS_ORDER.map((s) => (
                <option key={s} value={s}>
                  {titleCase(s)}
                </option>
              ))}
            </select>
          </div>
        }
      >
        <DataTable<Incident>
          columns={columns}
          rows={rows}
          rowKey={(row) => row.id}
          state={tableState}
          error={incidents.error}
          onRetry={incidents.refetch}
          emptyIcon={ClipboardList}
          emptyTitle={
            severity || statusFilter
              ? 'No incidents match this filter'
              : 'No incidents recorded'
          }
          // NOT "0 incidents -- all clear". Nothing recorded is not evidence
          // that nothing happened, and a pastoral lead reading "all clear"
          // would stop looking.
          emptyDescription={
            severity || statusFilter
              ? 'Clear the filters to see everything that has been logged.'
              : 'Nothing has been logged yet. That is not the same as nothing having happened — incidents appear here once staff record them.'
          }
        />
      </SectionCard>

      <LogIncidentDialog
        open={logOpen}
        onOpenChange={setLogOpen}
        onLogged={() => {
          setLogOpen(false)
          incidents.refetch()
        }}
      />

      <ResolutionHint incidents={rows} onUpdated={incidents.refetch} />
    </DashPageShell>
  )
}

/**
 * The severity notice is the point of this dialog, not decoration.
 * `sms_discipline.py:111` raises a different notification per band, and MAJOR
 * or CRITICAL produces a SAFEGUARDING message a family cannot mute. Staff
 * should know that before they choose, not afterwards.
 */
function LogIncidentDialog({
  open,
  onOpenChange,
  onLogged,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  onLogged: () => void
}) {
  const [studentId, setStudentId] = useState('')
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10))
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [location, setLocation] = useState('')
  const [severity, setSeverity] = useState<IncidentSeverity>('minor')
  const [actionTaken, setActionTaken] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const unmutable = UNMUTABLE_SEVERITIES.includes(severity)
  const studentIdNumber = Number(studentId)
  const studentIdValid = studentId.trim() !== '' && Number.isInteger(studentIdNumber) && studentIdNumber > 0

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (!studentIdValid) {
      setError('Enter the student’s numeric id.')
      return
    }
    setSubmitting(true)
    setError(null)
    try {
      await createIncident({
        student_id: studentIdNumber,
        incident_date: date,
        title: title.trim(),
        description: description.trim(),
        location: location.trim() || null,
        severity,
        action_taken: actionTaken.trim() || null,
      })
      setStudentId('')
      setTitle('')
      setDescription('')
      setLocation('')
      setActionTaken('')
      setSeverity('minor')
      onLogged()
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'The incident could not be saved. Nothing was recorded — try again.'
      )
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <SchoolDialog
      open={open}
      onOpenChange={onOpenChange}
      title="Log a behaviour incident"
      description="Recorded against the student and visible to teaching and pastoral staff."
      onSubmit={submit}
      footer={
        <>
          <button
            type="button"
            id="discipline-log-cancel"
            className={LH_SECONDARY_BUTTON}
            onClick={() => onOpenChange(false)}
          >
            Cancel
          </button>
          <button
            type="submit"
            id="discipline-log-submit"
            className={LH_PRIMARY_BUTTON}
            disabled={submitting}
          >
            {submitting ? 'Saving…' : 'Log incident'}
          </button>
        </>
      }
    >
      <div className="grid gap-4">
        <SchoolField id="discipline-student-id" label="Student id" required>
          <input
            id="discipline-student-id"
            className={LH_INPUT}
            inputMode="numeric"
            value={studentId}
            onChange={(e) => setStudentId(e.target.value)}
            required
          />
        </SchoolField>

        <SchoolField id="discipline-date" label="Date" required>
          <input
            id="discipline-date"
            type="date"
            className={LH_INPUT}
            value={date}
            onChange={(e) => setDate(e.target.value)}
            required
          />
        </SchoolField>

        <SchoolField id="discipline-title" label="Summary" required>
          <input
            id="discipline-title"
            className={LH_INPUT}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            required
          />
        </SchoolField>

        <SchoolField id="discipline-description" label="What happened" required>
          <textarea
            id="discipline-description"
            className={LH_INPUT}
            rows={4}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            required
          />
        </SchoolField>

        <SchoolField id="discipline-location" label="Location">
          <input
            id="discipline-location"
            className={LH_INPUT}
            value={location}
            onChange={(e) => setLocation(e.target.value)}
          />
        </SchoolField>

        <SchoolField
          id="discipline-severity"
          label="Severity"
          required
          help="Severity decides how the family is told."
        >
          <select
            id="discipline-severity"
            className={LH_INPUT}
            value={severity}
            onChange={(e) => setSeverity(e.target.value as IncidentSeverity)}
          >
            {SEVERITY_ORDER.map((s) => (
              <option key={s} value={s}>
                {titleCase(s)}
              </option>
            ))}
          </select>
        </SchoolField>

        {unmutable ? (
          <div
            className="flex items-start gap-2 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800"
            role="status"
          >
            <ShieldAlert size={16} className="mt-0.5 shrink-0" />
            <span>
              <strong>{titleCase(severity)}</strong> sends a safeguarding notification the
              family <strong>cannot mute</strong>. Choose this when it is warranted.
            </span>
          </div>
        ) : (
          <div
            className="flex items-start gap-2 rounded-md border border-gray-200 bg-gray-50 p-3 text-sm text-gray-700"
            role="status"
          >
            <AlertTriangle size={16} className="mt-0.5 shrink-0" />
            <span>
              {titleCase(severity)} sends a routine notification, which a family may have
              muted.
            </span>
          </div>
        )}

        <SchoolField id="discipline-action" label="Action taken">
          <input
            id="discipline-action"
            className={LH_INPUT}
            value={actionTaken}
            onChange={(e) => setActionTaken(e.target.value)}
          />
        </SchoolField>

        {error ? (
          <p className="text-sm text-red-700" role="alert">
            {error}
          </p>
        ) : null}
      </div>
    </SchoolDialog>
  )
}

/**
 * Outstanding pastoral follow-up. Shown only when there is something to act
 * on: an empty panel implying "all handled" would be a claim the data does not
 * support.
 */
function ResolutionHint({
  incidents,
  onUpdated,
}: {
  incidents: Incident[]
  onUpdated: () => void
}) {
  const [busyId, setBusyId] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  const awaitingFamily = incidents.filter((i) => !i.parent_notified)

  if (awaitingFamily.length === 0) return null

  async function markNotified(incident: Incident) {
    setBusyId(incident.id)
    setError(null)
    try {
      await updateIncident(incident.id, { parent_notified: true })
      onUpdated()
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Could not update the incident. It is unchanged.'
      )
    } finally {
      setBusyId(null)
    }
  }

  return (
    <SectionCard
      title="Families not yet told"
      description="Recording that a family has been contacted does not send anything — it notes what staff have already done."
    >
      {error ? (
        <p className="mb-3 text-sm text-red-700" role="alert">
          {error}
        </p>
      ) : null}
      <ul className="divide-y divide-gray-100">
        {awaitingFamily.map((incident) => (
          <li key={incident.id} className="flex items-center justify-between gap-3 py-2">
            <div className="min-w-0">
              <div className="truncate text-sm font-medium">{incident.title}</div>
              <div className="text-xs text-gray-500 tabular-nums">
                Student #{incident.student_id} · {incident.incident_date}
              </div>
            </div>
            <button
              type="button"
              id={`discipline-notified-${incident.id}`}
              className={LH_SECONDARY_BUTTON}
              disabled={busyId === incident.id}
              onClick={() => markNotified(incident)}
            >
              {busyId === incident.id ? 'Saving…' : 'Mark family told'}
            </button>
          </li>
        ))}
      </ul>
    </SectionCard>
  )
}
