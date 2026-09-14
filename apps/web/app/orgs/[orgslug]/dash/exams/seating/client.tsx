'use client'

/**
 * Exam seating.
 *
 * Seats hang off a SITTING, not an exam: one exam is sat by several sections
 * at once, each in its own room under its own invigilator, so a seat inherits
 * the room it was allocated under.
 *
 * THE SKIPPED LIST IS THE POINT OF THIS SCREEN. `allocate_seats` reports
 * clashes rather than resolving them, because an auto-reseated candidate turns
 * up on the day to find someone in their chair — a worse failure than an error
 * at allocation time. So every skipped row is rendered with its stated reason,
 * never collapsed into a success toast. `replace_existing` is off by default
 * and has to be ticked deliberately.
 */

import { useMemo, useState } from 'react'
import { Armchair, TriangleAlert } from 'lucide-react'
import {
  DashPageShell,
  DataTable,
  EmptyState,
  LH_INPUT,
  LH_PRIMARY_BUTTON,
  SectionCard,
  StatGrid,
} from '@/components/widgets'
import { ApiError } from '@/lib/api/api-client'
import { useApiResource } from '@/lib/api/useApiResource'
import { useSchoolSession } from '@/lib/api/useSchoolSession'
import { allocateExamSeats, listExamSeats } from '@/modules/sms/exams/api'
import { studentLabel } from '@/modules/sms/attendance/presentation'
import { useStudentNames } from '@/modules/sms/attendance/useStudentNames'
import type { SeatAllocationInput } from '@/modules/sms/exams/types'

interface Props {
  org_id: number
  orgslug: string
}

/**
 * Parses "37 A12" / "37,A12" / "37 A12 extra time" per line.
 * Deliberately forgiving about separators and deliberately strict about the
 * two required fields: a row that cannot be read is reported, never guessed.
 */
function parseAllocations(
  raw: string
): { rows: SeatAllocationInput[]; bad: string[] } {
  const rows: SeatAllocationInput[] = []
  const bad: string[] = []
  for (const line of raw.split('\n')) {
    const text = line.trim()
    if (!text) continue
    const parts = text.split(/[,\t]|\s+/).filter(Boolean)
    const studentId = Number(parts[0])
    const seat = parts[1]
    if (!Number.isFinite(studentId) || studentId <= 0 || !seat) {
      bad.push(text)
      continue
    }
    rows.push({
      student_id: studentId,
      seat_label: seat,
      notes: parts.slice(2).join(' ') || null,
    })
  }
  return { rows, bad }
}

export default function SeatingClient({ org_id }: Props) {
  const { session } = useSchoolSession()
  const campusId = session?.campus_id ?? undefined
  const { names } = useStudentNames(campusId)

  const [scheduleId, setScheduleId] = useState<string>('')
  const [raw, setRaw] = useState('')
  const [replaceExisting, setReplaceExisting] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [skipped, setSkipped] = useState<string[] | null>(null)
  const [allocatedCount, setAllocatedCount] = useState<number | null>(null)
  const [unreadable, setUnreadable] = useState<string[]>([])

  const numericScheduleId = Number(scheduleId)
  const hasSitting = Number.isFinite(numericScheduleId) && numericScheduleId > 0

  const seats = useApiResource(
    () => listExamSeats(numericScheduleId),
    [numericScheduleId],
    { skip: !hasSitting, isEmpty: (d) => d.length === 0 }
  )

  const rows = seats.data ?? []
  const withArrangements = useMemo(
    () => rows.filter((r) => (r.notes ?? '').trim().length > 0).length,
    [rows]
  )

  async function handleAllocate() {
    if (!hasSitting) {
      setError('Enter the sitting this seating plan is for.')
      return
    }
    const { rows: parsed, bad } = parseAllocations(raw)
    setUnreadable(bad)
    if (parsed.length === 0) {
      setError('Nothing to allocate — one line per candidate, e.g. "37 A12".')
      return
    }
    setSaving(true)
    setError(null)
    setSkipped(null)
    setAllocatedCount(null)
    try {
      const res = await allocateExamSeats(numericScheduleId, parsed, replaceExisting)
      setAllocatedCount(res.allocated.length)
      setSkipped(res.skipped)
      seats.refetch()
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.kind === 'permission_denied'
            ? 'You need exam-staff access to allocate seats.'
            : err.message
          : 'Could not allocate. Try again.'
      )
    } finally {
      setSaving(false)
    }
  }

  return (
    <DashPageShell
      module="exams"
      title="Exam seating"
      description="Allocate candidates to seats for one sitting. Clashes are reported, never silently resolved."
    >
      <SectionCard
        title="Choose a sitting"
        description="A seat belongs to a section's sitting, so it inherits that room and invigilator."
      >
        <label className="flex w-fit flex-col gap-1.5">
          <span className="text-xs font-medium text-gray-500">Sitting ID</span>
          <input
            id="seating-schedule-id"
            className={LH_INPUT}
            value={scheduleId}
            onChange={(e) => setScheduleId(e.target.value)}
            placeholder="e.g. 4"
            inputMode="numeric"
          />
        </label>
      </SectionCard>

      {hasSitting && (
        <>
          <StatGrid
            state={seats.status === 'loading' ? 'loading' : 'success'}
            columns={2}
            items={[
              { label: 'Seats allocated', value: rows.length, icon: Armchair, tone: 'neutral' },
              {
                label: 'With access arrangements',
                value: withArrangements,
                icon: TriangleAlert,
                tone: withArrangements > 0 ? 'caution' : 'neutral',
              },
            ]}
          />

          <SectionCard
            title="Allocate seats"
            description="One line per candidate: student id, seat label, then any access arrangement. e.g. “37 A12 extra time”."
          >
            <div className="flex flex-col gap-4">
              <SchoolTextArea value={raw} onChange={setRaw} />

              <label className="flex items-center gap-2 text-sm text-gray-700">
                <input
                  id="seating-replace"
                  type="checkbox"
                  checked={replaceExisting}
                  onChange={(e) => setReplaceExisting(e.target.checked)}
                />
                <span>
                  Reseat candidates who already have a seat
                  <span className="ms-1 text-gray-500">
                    (off by default, so a re-run cannot silently move anyone)
                  </span>
                </span>
              </label>

              <div>
                <button
                  type="button"
                  id="seating-allocate"
                  disabled={saving}
                  className={LH_PRIMARY_BUTTON}
                  onClick={handleAllocate}
                >
                  <span>{saving ? 'Allocating…' : 'Allocate seats'}</span>
                </button>
              </div>

              {error && <p className="text-sm text-rose-600">{error}</p>}

              {unreadable.length > 0 && (
                <div className="rounded-lg border border-amber-200 bg-amber-50 p-3">
                  <p className="text-sm font-medium text-amber-900">
                    {unreadable.length} line{unreadable.length === 1 ? '' : 's'} could not
                    be read and {unreadable.length === 1 ? 'was' : 'were'} not sent
                  </p>
                  <ul className="mt-1 list-inside list-disc text-sm text-amber-800">
                    {unreadable.map((l) => (
                      <li key={l}>{l}</li>
                    ))}
                  </ul>
                </div>
              )}

              {allocatedCount !== null && (
                <div className="rounded-lg border border-gray-200 bg-gray-50 p-3">
                  <p className="text-sm font-medium text-gray-900">
                    {allocatedCount} seat{allocatedCount === 1 ? '' : 's'} allocated
                  </p>
                  {skipped && skipped.length > 0 ? (
                    <>
                      <p className="mt-2 text-sm font-medium text-rose-700">
                        {skipped.length} not allocated — resolve these before exam day:
                      </p>
                      <ul className="mt-1 list-inside list-disc text-sm text-rose-700">
                        {skipped.map((s) => (
                          <li key={s}>{s}</li>
                        ))}
                      </ul>
                    </>
                  ) : (
                    <p className="mt-1 text-sm text-gray-600">
                      Nothing was skipped.
                    </p>
                  )}
                </div>
              )}
            </div>
          </SectionCard>

          <SectionCard
            title="Seating plan"
            state={seats.status}
            error={seats.error}
            onRetry={seats.refetch}
            emptyTitle="No seats allocated for this sitting"
            emptyDescription="Allocate candidates above to build the plan."
          >
            <DataTable
              rows={rows}
              rowKey={(r) => r.id}
              state="success"
              totalLabel={`${rows.length} seat${rows.length === 1 ? '' : 's'}`}
              columns={[
                { key: 'seat', header: 'Seat', render: (r) => r.seat_label },
                {
                  key: 'student',
                  header: 'Candidate',
                  render: (r) => studentLabel(r.student_id, names),
                },
                {
                  key: 'notes',
                  header: 'Access arrangements',
                  // An empty notes field means none were recorded — not that
                  // the candidate has none. Worded so nobody reads it as a
                  // positive statement.
                  render: (r) => r.notes || 'None recorded',
                },
              ]}
            />
          </SectionCard>
        </>
      )}

      {!hasSitting && (
        <EmptyState
          title="Enter a sitting to begin"
          description="Seating is allocated per sitting, because one exam is sat by several sections in different rooms."
        />
      )}
    </DashPageShell>
  )
}

/** Local textarea styled to match LH_INPUT — the shared widgets expose inputs
 *  and selects, not a multi-line field. */
function SchoolTextArea({
  value,
  onChange,
}: {
  value: string
  onChange: (v: string) => void
}) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-sm font-medium text-gray-700">Allocations</span>
      <textarea
        id="seating-allocations"
        className="min-h-[140px] rounded-lg border-0 bg-white px-3 py-2 font-mono text-sm nice-shadow focus:outline-none focus:ring-2 focus:ring-black focus:ring-offset-2"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={'37 A12\n38 A13\n39 B01 separate room'}
      />
    </label>
  )
}
