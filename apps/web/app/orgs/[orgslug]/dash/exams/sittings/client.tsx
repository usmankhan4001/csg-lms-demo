'use client'

/**
 * Sittings — which sections sit an exam, in which room, watched by whom.
 *
 * WHY THIS SCREEN EXISTS: seats are allocated per SITTING, and incidents are
 * logged against one. Until now nothing listed sittings, so the seating page
 * asked an administrator to type a raw numeric schedule id they had no way to
 * discover. This is where that id comes from.
 *
 * `actual_start_at` / `actual_end_at` are the invigilator's record of what
 * happened, not the plan — a room routinely starts late. A null is "not
 * recorded", rendered as such and never as a time or a zero.
 */

import { useState } from 'react'
import { CalendarClock, DoorOpen } from 'lucide-react'
import {
  DashPageShell,
  DataTable,
  LH_INPUT,
  LH_PRIMARY_BUTTON,
  LH_SECONDARY_BUTTON,
  SchoolDialog,
  SchoolField,
  SectionCard,
} from '@/components/widgets'
import { useApiResource } from '@/lib/api/useApiResource'
import { useSchoolSession } from '@/lib/api/useSchoolSession'
import { listClassSections } from '@/modules/sms/campus/api'
import {
  listExamSittings,
  listExams,
  recordSittingTimes,
  scheduleSection,
} from '@/modules/sms/exams/api'

interface Props {
  org_id: number
  orgslug: string
}

/** A recorded time, or an explicit statement that none was recorded. */
function whenOrNotRecorded(value: string | null): string {
  if (!value) return 'Not recorded'
  const d = new Date(value)
  return Number.isNaN(d.getTime()) ? 'Not recorded' : d.toLocaleString()
}

export default function SittingsClient({ org_id }: Props) {
  const { session } = useSchoolSession()
  const campusId = session?.campus_id ?? undefined

  const [examId, setExamId] = useState<number | undefined>(undefined)
  const [addOpen, setAddOpen] = useState(false)
  const [sectionId, setSectionId] = useState('')
  const [room, setRoom] = useState('')
  const [busy, setBusy] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)

  const [timesFor, setTimesFor] = useState<number | null>(null)
  const [startAt, setStartAt] = useState('')
  const [endAt, setEndAt] = useState('')

  const exams = useApiResource(() => listExams({ campusId }), [campusId], {
    isEmpty: (d) => d.length === 0,
  })

  const effectiveExamId = examId ?? exams.data?.[0]?.id

  const sittings = useApiResource(
    () => listExamSittings(effectiveExamId as number),
    [effectiveExamId],
    { skip: effectiveExamId === undefined, isEmpty: (d) => d.length === 0 }
  )

  const sections = useApiResource(
    () => listClassSections(campusId as number, { isActive: true }),
    [campusId],
    { skip: campusId === undefined, isEmpty: (d) => d.length === 0 }
  )

  const sectionName = (id: number) =>
    (() => {
      const sec = sections.data?.find((s) => s.id === id)
      // ClassSectionRead has no single `name`: a section is its grade plus its
      // letter, e.g. "Grade 9 A". Joining them here keeps the label the same
      // shape a school says out loud.
      return sec ? `${sec.grade_level} ${sec.section_name}`.trim() : `Section ${id}`
    })()

  async function handleAdd(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setFormError(null)
    const sid = Number(sectionId)
    if (!Number.isFinite(sid) || sid <= 0) {
      setFormError('Choose the section that will sit this exam.')
      return
    }
    if (effectiveExamId === undefined) {
      setFormError('Choose an exam first.')
      return
    }
    setBusy(true)
    try {
      await scheduleSection(effectiveExamId, {
        section_id: sid,
        room_number: room.trim() || null,
      })
      setAddOpen(false)
      setSectionId('')
      setRoom('')
      sittings.refetch()
    } catch (err) {
      // The API answers 409 when a section is already scheduled. That is a
      // real answer to surface, not a failure to retry silently.
      setFormError(
        err instanceof Error ? err.message : 'Could not schedule that section for this exam.'
      )
    } finally {
      setBusy(false)
    }
  }

  async function handleTimes(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (timesFor === null) return
    setFormError(null)
    if (!startAt && !endAt) {
      setFormError('Record at least one of the start or end times.')
      return
    }
    setBusy(true)
    try {
      await recordSittingTimes(timesFor, {
        // Each field is sent only when filled: a room that has started but not
        // finished is a normal mid-exam state, not an incomplete record.
        actual_start_at: startAt ? new Date(startAt).toISOString() : undefined,
        actual_end_at: endAt ? new Date(endAt).toISOString() : undefined,
      })
      setTimesFor(null)
      setStartAt('')
      setEndAt('')
      sittings.refetch()
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Could not record those times.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <DashPageShell
      module="exams"
      title="Sittings"
      description="Which sections sit each exam, where, and when the room actually ran."
    >
      <div className="flex flex-wrap items-end gap-4">
        <label className="flex flex-col gap-1.5">
          <span className="text-xs font-medium text-gray-500">Exam</span>
          <select
            id="sittings-exam"
            className={LH_INPUT}
            value={effectiveExamId ?? ''}
            onChange={(e) => setExamId(Number(e.target.value))}
            disabled={(exams.data ?? []).length === 0}
          >
            {(exams.data ?? []).map((ex) => (
              <option key={ex.id} value={ex.id}>
                {ex.title}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          id="sittings-add"
          className={LH_PRIMARY_BUTTON}
          onClick={() => setAddOpen(true)}
          disabled={effectiveExamId === undefined}
        >
          Schedule a section
        </button>
      </div>

      <SectionCard
        title="Sittings for this exam"
        description="One exam is usually sat by several sections in different rooms."
        icon={<DoorOpen className="size-4 text-gray-500" />}
        state={
          exams.status === 'empty'
            ? 'empty'
            : sittings.status === 'loading'
              ? 'loading'
              : sittings.status === 'error'
                ? 'error'
                : sittings.status === 'empty'
                  ? 'empty'
                  : 'success'
        }
        error={sittings.error}
        onRetry={sittings.refetch}
        emptyTitle={exams.status === 'empty' ? 'No exams yet' : 'No sections scheduled'}
        emptyDescription={
          exams.status === 'empty'
            ? 'Create an exam before scheduling the sections that will sit it.'
            : 'Schedule a section to create the sitting that seats and incidents attach to.'
        }
      >
        <DataTable
          columns={[
            { key: 'section', header: 'Section', render: (r) => sectionName(r.section_id) },
            { key: 'room', header: 'Room', render: (r) => r.room_number ?? 'Not set' },
            {
              key: 'started',
              header: 'Actually started',
              render: (r) => whenOrNotRecorded(r.actual_start_at),
            },
            {
              key: 'ended',
              header: 'Actually ended',
              render: (r) => whenOrNotRecorded(r.actual_end_at),
            },
            {
              key: 'id',
              header: 'Sitting ID',
              // Shown on purpose: this is the id the seating screen needs, and
              // until this page existed there was nowhere to read it from.
              render: (r) => <span className="tabular-nums text-gray-500">{r.id}</span>,
            },
            {
              key: 'actions',
              header: '',
              render: (r) => (
                <button
                  type="button"
                  className={LH_SECONDARY_BUTTON}
                  onClick={() => {
                    setTimesFor(r.id)
                    setFormError(null)
                  }}
                >
                  Record times
                </button>
              ),
            },
          ]}
          rows={sittings.data ?? []}
          rowKey={(r) => r.id}
        />
      </SectionCard>

      <SchoolDialog
        open={addOpen}
        onOpenChange={setAddOpen}
        title="Schedule a section to sit this exam"
        description="Creates the sitting that seating and incidents hang off."
        onSubmit={handleAdd}
        footer={
          <>
            <button type="button" className={LH_SECONDARY_BUTTON} onClick={() => setAddOpen(false)}>
              Cancel
            </button>
            <button type="submit" className={LH_PRIMARY_BUTTON} disabled={busy}>
              {busy ? 'Scheduling…' : 'Schedule section'}
            </button>
          </>
        }
      >
        <SchoolField id="sitting-section" label="Section" required>
          <select
            id="sitting-section"
            className={LH_INPUT}
            value={sectionId}
            onChange={(e) => setSectionId(e.target.value)}
          >
            <option value="">Choose a section…</option>
            {(sections.data ?? []).map((s) => (
              <option key={s.id} value={s.id}>
                {sectionName(s.id)}
              </option>
            ))}
          </select>
        </SchoolField>
        <SchoolField
          id="sitting-room"
          label="Room"
          help="Optional. Leave blank if the room is not decided yet."
        >
          <input
            id="sitting-room"
            className={LH_INPUT}
            value={room}
            onChange={(e) => setRoom(e.target.value)}
            placeholder="e.g. Hall A"
          />
        </SchoolField>
        {formError && <p className="text-sm text-red-600">{formError}</p>}
      </SchoolDialog>

      <SchoolDialog
        open={timesFor !== null}
        onOpenChange={(o) => !o && setTimesFor(null)}
        title="Record what actually happened"
        description="The times the room really started and finished, which are often not the scheduled ones."
        onSubmit={handleTimes}
        footer={
          <>
            <button type="button" className={LH_SECONDARY_BUTTON} onClick={() => setTimesFor(null)}>
              Cancel
            </button>
            <button type="submit" className={LH_PRIMARY_BUTTON} disabled={busy}>
              {busy ? 'Saving…' : 'Save times'}
            </button>
          </>
        }
      >
        <SchoolField
          id="sitting-start"
          label="Actually started"
          help="Leave blank if not known — it stays 'Not recorded' rather than being guessed."
        >
          <input
            id="sitting-start"
            type="datetime-local"
            className={LH_INPUT}
            value={startAt}
            onChange={(e) => setStartAt(e.target.value)}
          />
        </SchoolField>
        <SchoolField id="sitting-end" label="Actually ended">
          <input
            id="sitting-end"
            type="datetime-local"
            className={LH_INPUT}
            value={endAt}
            onChange={(e) => setEndAt(e.target.value)}
          />
        </SchoolField>
        <p className="flex items-start gap-2 text-xs text-gray-500">
          <CalendarClock className="mt-0.5 size-3.5 shrink-0" />
          An exam in progress has a start and no end. That is a complete record, not a missing one.
        </p>
        {formError && <p className="text-sm text-red-600">{formError}</p>}
      </SchoolDialog>
    </DashPageShell>
  )
}
