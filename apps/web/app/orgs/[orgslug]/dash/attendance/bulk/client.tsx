'use client'

/**
 * Mark a whole section across a date range: a trip, a closure, a correction.
 *
 * THE SKIPPED LIST IS THE POINT OF THIS SCREEN. `overwrite_existing` defaults
 * to false, so dates that already hold a differing record are REPORTED rather
 * than rewritten (`sms_attendance.py:869`). Hiding that behind a success toast
 * would be the worst possible outcome: a user would believe a whole week was
 * marked when three days kept their old values.
 *
 * So the result is rendered as a table with each skipped record's EXISTING
 * status, and the user decides whether to re-run with overwrite. Overwrites
 * are recorded in the attendance trail like any other correction, which is
 * what makes offering the option safe.
 */

import { useState } from 'react'
import { CalendarPlus, AlertTriangle } from 'lucide-react'
import {
  DashPageShell,
  DataTable,
  LH_INPUT,
  LH_PRIMARY_BUTTON,
  SectionCard,
  StatGrid,
  StatusChip,
} from '@/components/widgets'
import { ApiError } from '@/lib/api/api-client'
import { useApiResource } from '@/lib/api/useApiResource'
import { useSchoolSession } from '@/lib/api/useSchoolSession'
import { listCampuses, listClassSections } from '@/modules/sms/campus/api'
import { bulkMarkRange } from '@/modules/sms/attendance/api'
import {
  ATTENDANCE_TONE,
  formatDate,
  isoDate,
  studentLabel,
} from '@/modules/sms/attendance/presentation'
import { useStudentNames } from '@/modules/sms/attendance/useStudentNames'
import type {
  AttendanceStatus,
  BulkMarkRangeResponse,
} from '@/modules/sms/attendance/types'

interface Props {
  org_id: number
  orgslug: string
}

const STATUSES: AttendanceStatus[] = ['PRESENT', 'ABSENT', 'LATE', 'EXCUSED']

export default function BulkMarkClient({ org_id }: Props) {
  const { session } = useSchoolSession()

  const campuses = useApiResource(() => listCampuses({ orgId: org_id, isActive: true }), [org_id], {
    isEmpty: (d) => d.length === 0,
  })
  const [campusId, setCampusId] = useState<number | undefined>(undefined)
  const effectiveCampusId = campusId ?? session?.campus_id ?? campuses.data?.[0]?.id

  const sections = useApiResource(
    () => listClassSections(effectiveCampusId as number, { isActive: true }),
    [effectiveCampusId],
    { skip: effectiveCampusId === undefined, isEmpty: (d) => d.length === 0 }
  )
  const { names } = useStudentNames(effectiveCampusId)

  const [sectionId, setSectionId] = useState<number | undefined>(undefined)
  const [startDate, setStartDate] = useState(isoDate())
  const [endDate, setEndDate] = useState(isoDate())
  const [status, setStatus] = useState<AttendanceStatus>('PRESENT')
  const [reason, setReason] = useState('')
  const [overwrite, setOverwrite] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<BulkMarkRangeResponse | null>(null)

  const effectiveSectionId = sectionId ?? sections.data?.[0]?.id

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (effectiveSectionId === undefined) {
      setError('Pick a section first.')
      return
    }
    setSaving(true)
    setError(null)
    setResult(null)
    try {
      const res = await bulkMarkRange({
        section_id: effectiveSectionId,
        start_date: startDate,
        end_date: endDate,
        status,
        reason: reason.trim() || null,
        overwrite_existing: overwrite,
      })
      setResult(res)
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.kind === 'permission_denied'
            ? 'You can only mark sections you teach.'
            : err.message
          : 'Could not apply the bulk mark.'
      )
    } finally {
      setSaving(false)
    }
  }

  return (
    <DashPageShell
      module="attendance"
      title="Bulk marking"
      description="Mark a whole section across a date range — a trip, a closure, or a correction."
    >
      <SectionCard
        id="bulk-form"
        title="What to mark"
        icon={<CalendarPlus className="size-4 text-gray-500" />}
        state={sections.status === 'loading' ? 'loading' : sections.status}
        error={sections.error}
        onRetry={sections.refetch}
        emptyTitle="No class sections yet"
        emptyDescription="Create a class section before marking attendance in bulk."
      >
        <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
          <div className="flex flex-wrap items-end gap-3">
            {(campuses.data ?? []).length > 1 && (
              <label className="flex flex-col gap-1.5">
                <span className="text-xs font-medium text-gray-500">Campus</span>
                <select
                  id="bulk-campus"
                  className={LH_INPUT}
                  value={effectiveCampusId ?? ''}
                  onChange={(e) => {
                    setCampusId(Number(e.target.value))
                    setSectionId(undefined)
                  }}
                >
                  {(campuses.data ?? []).map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </label>
            )}

            <label className="flex flex-col gap-1.5">
              <span className="text-xs font-medium text-gray-500">Section</span>
              <select
                id="bulk-section"
                className={LH_INPUT}
                value={effectiveSectionId ?? ''}
                onChange={(e) => setSectionId(Number(e.target.value))}
              >
                {(sections.data ?? []).map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.grade_level} — {s.section_name}
                  </option>
                ))}
              </select>
            </label>

            <label className="flex flex-col gap-1.5">
              <span className="text-xs font-medium text-gray-500">From</span>
              <input
                id="bulk-start"
                type="date"
                className={LH_INPUT}
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
              />
            </label>

            <label className="flex flex-col gap-1.5">
              <span className="text-xs font-medium text-gray-500">To</span>
              <input
                id="bulk-end"
                type="date"
                className={LH_INPUT}
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
              />
            </label>

            <label className="flex flex-col gap-1.5">
              <span className="text-xs font-medium text-gray-500">Mark as</span>
              <select
                id="bulk-status"
                className={LH_INPUT}
                value={status}
                onChange={(e) => setStatus(e.target.value as AttendanceStatus)}
              >
                {STATUSES.map((s) => (
                  <option key={s} value={s}>
                    {s.charAt(0) + s.slice(1).toLowerCase()}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-medium text-gray-500">Reason</span>
            <input
              id="bulk-reason"
              className={LH_INPUT}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="e.g. Year 9 field trip"
            />
            <span className="text-xs text-gray-400">
              Optional, and recorded in the attendance trail against every record changed.
            </span>
          </label>

          <label className="flex items-center gap-2 text-sm text-gray-700">
            <input
              id="bulk-overwrite"
              type="checkbox"
              checked={overwrite}
              onChange={(e) => setOverwrite(e.target.checked)}
            />
            <span>
              Overwrite registers that already differ
              <span className="ml-1 text-xs text-gray-400">
                (off by default — existing records are reported instead, never silently changed)
              </span>
            </span>
          </label>

          {error && <p className="text-sm text-rose-600">{error}</p>}

          <div className="flex justify-end">
            <button id="bulk-submit" type="submit" disabled={saving} className={LH_PRIMARY_BUTTON}>
              <span>{saving ? 'Applying…' : 'Apply'}</span>
            </button>
          </div>
        </form>
      </SectionCard>

      {result && (
        <>
          <StatGrid
            state="success"
            columns={4}
            items={[
              { label: 'Dates covered', value: result.dates_covered, icon: CalendarPlus, tone: 'neutral' },
              { label: 'Created', value: result.records_created, icon: CalendarPlus, tone: 'positive' },
              { label: 'Updated', value: result.records_updated, icon: CalendarPlus, tone: 'caution' },
              {
                label: 'Skipped',
                value: result.skipped.length,
                icon: AlertTriangle,
                tone: result.skipped.length > 0 ? 'critical' : 'neutral',
              },
            ]}
          />

          <SectionCard
            id="bulk-skipped"
            title="Left unchanged"
            description={
              result.skipped.length > 0
                ? 'These already held a different status, so they were not touched. Re-run with overwrite if you intended to change them.'
                : 'Nothing was skipped.'
            }
            icon={<AlertTriangle className="size-4 text-gray-500" />}
            state={result.skipped.length === 0 ? 'empty' : 'success'}
            emptyTitle="Nothing skipped"
            emptyDescription="Every date in the range was created or updated."
          >
            <DataTable
              rows={result.skipped}
              rowKey={(r) => `${r.student_id}-${r.date}`}
              state="success"
              totalLabel={`${result.skipped.length} record${result.skipped.length === 1 ? '' : 's'} left alone`}
              columns={[
                {
                  key: 'student',
                  header: 'Student',
                  render: (r) => studentLabel(r.student_id, names),
                },
                { key: 'date', header: 'Date', render: (r) => formatDate(r.date) },
                {
                  key: 'existing',
                  header: 'Existing status',
                  render: (r) => (
                    <StatusChip
                      label={r.existing_status}
                      tone={ATTENDANCE_TONE[r.existing_status]}
                    />
                  ),
                },
              ]}
            />
          </SectionCard>
        </>
      )}
    </DashPageShell>
  )
}
