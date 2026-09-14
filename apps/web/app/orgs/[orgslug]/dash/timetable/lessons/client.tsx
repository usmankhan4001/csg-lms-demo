'use client'

/**
 * Lesson logs -- what was actually taught, and the handover to whoever is next.
 *
 * THE PROBLEM THIS SOLVES: a substitute covering an unfamiliar class has no way
 * to find out what that class last did or what homework is due. An AI lesson
 * PLAN does not answer it -- a plan is written beforehand and may never have
 * been followed.
 *
 * THE DISTINCTION THIS SCREEN MUST KEEP: "no lesson recorded" means nobody
 * wrote one down. It does NOT mean nothing was taught, and the UI says so
 * rather than rendering an empty lesson.
 */

import { useState } from 'react'
import { BookOpenCheck, NotebookPen, History } from 'lucide-react'
import toast from 'react-hot-toast'
import {
  DashPageShell,
  DataTable,
  EmptyState,
  LH_INPUT,
  LH_PRIMARY_BUTTON,
  SchoolDialog,
  SchoolField,
  SectionCard,
} from '@/components/widgets'
import { ApiError } from '@/lib/api/api-client'
import { useApiResource } from '@/lib/api/useApiResource'
import { useSchoolSession } from '@/lib/api/useSchoolSession'
import { listCampuses, listClassSections } from '@/modules/sms/campus/api'
import {
  getPreviousLesson,
  listLessonLogs,
  listTimetableSchedules,
  recordLessonLog,
} from '@/modules/sms/timetable/api'

interface LessonsClientProps {
  org_id: number
  orgslug: string
}

function todayIso(): string {
  return new Date().toISOString().slice(0, 10)
}

export default function TimetableLessonsClient({ org_id }: LessonsClientProps) {
  const { session } = useSchoolSession()
  const [campusId, setCampusId] = useState<number | undefined>(undefined)
  const [sectionId, setSectionId] = useState<number | undefined>(undefined)
  const [open, setOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const campuses = useApiResource(() => listCampuses({ orgId: org_id, isActive: true }), [org_id], {
    isEmpty: (d) => d.length === 0,
  })
  const effectiveCampusId = campusId ?? session?.campus_id ?? campuses.data?.[0]?.id

  const sections = useApiResource(
    () => listClassSections(effectiveCampusId as number, { isActive: true }),
    [effectiveCampusId],
    { skip: effectiveCampusId === undefined, isEmpty: (d) => d.length === 0 }
  )
  const effectiveSectionId = sectionId ?? sections.data?.[0]?.id

  const logs = useApiResource(
    () => listLessonLogs({ sectionId: effectiveSectionId }),
    [effectiveSectionId],
    { skip: effectiveSectionId === undefined, isEmpty: (d) => d.length === 0 }
  )

  const slots = useApiResource(
    () => listTimetableSchedules({ sectionId: effectiveSectionId }),
    [effectiveSectionId],
    { skip: effectiveSectionId === undefined, isEmpty: (d) => d.length === 0 }
  )

  // The substitute's question, asked for today.
  const previous = useApiResource(
    () => getPreviousLesson({ sectionId: effectiveSectionId as number, beforeDate: todayIso() }),
    [effectiveSectionId],
    { skip: effectiveSectionId === undefined }
  )

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const form = new FormData(e.currentTarget)
    const scheduleId = Number(form.get('schedule_id'))
    const lessonDate = String(form.get('lesson_date') ?? '').trim()
    const topic = String(form.get('topic_covered') ?? '').trim()

    if (!scheduleId || !lessonDate || !topic) {
      setError('A lesson needs a slot, a date and a topic.')
      return
    }

    setSaving(true)
    setError(null)
    try {
      await recordLessonLog({
        schedule_id: scheduleId,
        lesson_date: lessonDate,
        topic_covered: topic,
        homework_set: String(form.get('homework_set') ?? '').trim() || null,
        notes_for_next_teacher: String(form.get('notes_for_next_teacher') ?? '').trim() || null,
      })
      setOpen(false)
      toast.success('Lesson recorded.')
      logs.refetch()
      previous.refetch()
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.kind === 'permission_denied'
            ? 'You need teaching access to record a lesson.'
            : err.message
          : 'Could not record the lesson. Try again.'
      )
    } finally {
      setSaving(false)
    }
  }

  const slotLabel = (id: number) => {
    const s = slots.data?.find((x) => x.id === id)
    if (!s) return `Slot #${id}`
    const period = s.period_number != null ? `P${s.period_number}` : `#${s.period_id}`
    return `${s.day_of_week} ${period}`
  }

  return (
    <DashPageShell
      module="timetable"
      title="Lesson log"
      description="What was actually taught, the homework set, and the handover for whoever takes the class next."
    >
      <SectionCard
        title="Choose a section"
        icon={<BookOpenCheck className="size-4 text-gray-500" />}
        state={campuses.status === 'loading' || sections.status === 'loading' ? 'loading' : campuses.status}
        error={campuses.error ?? sections.error}
        onRetry={campuses.refetch}
        emptyTitle="No campuses set up yet"
        emptyDescription="Add a campus and class sections before recording lessons."
      >
        <div className="flex flex-wrap items-end gap-4">
          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-medium text-gray-500">Campus</span>
            <select
              id="lessons-campus"
              className={LH_INPUT}
              value={effectiveCampusId ?? ''}
              onChange={(e) => {
                setCampusId(Number(e.target.value))
                setSectionId(undefined)
              }}
            >
              {(campuses.data ?? []).map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </label>

          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-medium text-gray-500">Section</span>
            <select
              id="lessons-section"
              className={LH_INPUT}
              value={effectiveSectionId ?? ''}
              onChange={(e) => setSectionId(Number(e.target.value))}
              disabled={(sections.data ?? []).length === 0}
            >
              {(sections.data ?? []).map((s) => (
                <option key={s.id} value={s.id}>
                  {s.grade_level} — {s.section_name}
                </option>
              ))}
            </select>
          </label>

          <SchoolDialog
            open={open}
            onOpenChange={setOpen}
            trigger={
              <button type="button" id="lessons-record" className={LH_PRIMARY_BUTTON} disabled={(slots.data ?? []).length === 0}>
                <NotebookPen className="size-4" /> <span>Record a lesson</span>
              </button>
            }
            title="Record what was taught"
            description="Attributed to you automatically. Recording the same slot and date again corrects the existing entry rather than adding a second one."
            onSubmit={handleSubmit}
            footer={
              <button type="submit" disabled={saving} className={LH_PRIMARY_BUTTON}>
                <span>{saving ? 'Saving…' : 'Save lesson'}</span>
              </button>
            }
          >
            <SchoolField id="lesson-slot" label="Timetable slot" required>
              <select id="lesson-slot" name="schedule_id" className={LH_INPUT} defaultValue="">
                <option value="" disabled>Choose a slot…</option>
                {(slots.data ?? []).map((s) => (
                  <option key={s.id} value={s.id}>{slotLabel(s.id)}</option>
                ))}
              </select>
            </SchoolField>

            <SchoolField id="lesson-date" label="Date" required>
              <input id="lesson-date" name="lesson_date" type="date" className={LH_INPUT} defaultValue={todayIso()} />
            </SchoolField>

            <SchoolField id="lesson-topic" label="Topic covered" required>
              <input id="lesson-topic" name="topic_covered" className={LH_INPUT} placeholder="Photosynthesis: light-dependent reactions" />
            </SchoolField>

            <SchoolField id="lesson-homework" label="Homework set">
              <input id="lesson-homework" name="homework_set" className={LH_INPUT} placeholder="Worksheet 4, questions 1-6" />
            </SchoolField>

            <SchoolField
              id="lesson-notes"
              label="Notes for the next teacher"
              help="Read by whoever covers this class next."
            >
              <input id="lesson-notes" name="notes_for_next_teacher" className={LH_INPUT} placeholder="Class found the electron transport chain hard." />
            </SchoolField>

            {error && <p className="text-sm text-rose-600">{error}</p>}
          </SchoolDialog>
        </div>
      </SectionCard>

      <SectionCard
        title="Last recorded lesson"
        description="What this section did most recently — the first thing to read if you are covering them."
        icon={<History className="size-4 text-gray-500" />}
        state={previous.status === 'loading' ? 'loading' : 'success'}
        error={previous.error}
        onRetry={previous.refetch}
      >
        {previous.data ? (
          <div className="flex flex-col gap-2 text-sm">
            <div><span className="text-gray-500">Date:</span> {previous.data.lesson_date}</div>
            <div><span className="text-gray-500">Topic:</span> {previous.data.topic_covered}</div>
            <div>
              <span className="text-gray-500">Homework:</span>{' '}
              {previous.data.homework_set ?? 'None recorded'}
            </div>
            <div>
              <span className="text-gray-500">Handover note:</span>{' '}
              {previous.data.notes_for_next_teacher ?? 'None left'}
            </div>
          </div>
        ) : (
          <EmptyState
            title="No lesson recorded"
            /* Deliberate wording: an absent log means nobody wrote one down. It
               does not mean the class did nothing, and a substitute must not
               read it that way. */
            description="Nobody has logged a lesson for this section yet. That is not a record that nothing was taught — it means no one has written one down."
          />
        )}
      </SectionCard>

      <SectionCard
        title="Lesson history"
        icon={<BookOpenCheck className="size-4 text-gray-500" />}
        state={effectiveSectionId === undefined ? 'empty' : logs.status}
        error={logs.error}
        onRetry={logs.refetch}
        emptyTitle="No lessons recorded yet"
        emptyDescription="Record a lesson to start building the handover trail for this section."
      >
        <DataTable
          rows={logs.data ?? []}
          rowKey={(r) => r.id}
          state="success"
          totalLabel={`${logs.data?.length ?? 0} lesson${(logs.data?.length ?? 0) === 1 ? '' : 's'}`}
          columns={[
            { key: 'date', header: 'Date', render: (r) => r.lesson_date },
            { key: 'slot', header: 'Slot', render: (r) => slotLabel(r.schedule_id) },
            { key: 'topic', header: 'Topic', render: (r) => r.topic_covered },
            { key: 'homework', header: 'Homework', render: (r) => r.homework_set ?? '—' },
            {
              key: 'notes',
              header: 'Handover note',
              render: (r) => r.notes_for_next_teacher ?? '—',
            },
          ]}
        />
      </SectionCard>
    </DashPageShell>
  )
}
