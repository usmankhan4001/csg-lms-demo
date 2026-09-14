'use client'

/**
 * Live Classes -- the management window.
 *
 * The in-room experience already existed (`components/Objects/Activities/
 * LiveClass/`: video, chat, Boards/Playground tools), and so did the whole
 * `/live/classes/*` backend -- scheduling, recording policy, coursework. What
 * was missing was any operator surface at all: a teacher could join a class
 * they already had a link to, but could not see what was coming, schedule one,
 * cancel one, or find a recording. This is that screen.
 *
 * Recording is deliberately opt-in per class. These are rooms full of
 * children, so the server defaults `recording_enabled` to false and this form
 * does not pre-tick it -- a recording nobody consciously turned on is a
 * recording nobody consented to.
 */

import { useState } from 'react'
import { Video, Plus, CalendarBlank } from '@phosphor-icons/react'
import {
  DashPageShell,
  DataTable,
  SectionCard,
  StatusChip,
  SchoolDialog,
  SchoolField,
  LH_INPUT,
  LH_PRIMARY_BUTTON,
  LH_SECONDARY_BUTTON,
} from '@/components/widgets'
import { ApiError } from '@/lib/api/api-client'
import { useApiResource } from '@/lib/api/useApiResource'
import { useSchoolSession } from '@/lib/api/useSchoolSession'
import { listCampuses, listClassSections } from '@/modules/sms/campus/api'
import {
  listLiveClasses,
  scheduleLiveClass,
  startLiveClass,
} from '@/modules/sms/live-class/api'
import {
  describeClassStatus,
  describeRecording,
  formatWhen,
  isJoinable,
} from '@/modules/sms/live-class/presentation'
import type { LiveClassDetailRead } from '@/modules/sms/live-class/types'

interface LiveClassesDashClientProps {
  org_id: number
  orgslug: string
}

export default function LiveClassesDashClient({ org_id, orgslug }: LiveClassesDashClientProps) {
  const { session } = useSchoolSession()
  const [upcoming, setUpcoming] = useState(true)
  const [scheduleOpen, setScheduleOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)
  const [startError, setStartError] = useState<string | null>(null)

  const campuses = useApiResource(() => listCampuses({ orgId: org_id, isActive: true }), [org_id], {
    isEmpty: (d) => d.length === 0,
  })
  const effectiveCampusId = session?.campus_id ?? campuses.data?.[0]?.id

  const sections = useApiResource(
    () => listClassSections(effectiveCampusId as number, { isActive: true }),
    [effectiveCampusId],
    { skip: effectiveCampusId === undefined, isEmpty: (d) => d.length === 0 }
  )

  const classes = useApiResource(
    () => listLiveClasses({ upcoming, campusId: effectiveCampusId }),
    [upcoming, effectiveCampusId],
    { isEmpty: (d) => d.length === 0 }
  )

  async function handleSchedule(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const form = new FormData(e.currentTarget)
    const title = String(form.get('title') ?? '').trim()
    const startLocal = String(form.get('start_time') ?? '')
    const endLocal = String(form.get('end_time') ?? '')
    const sectionRaw = String(form.get('section_id') ?? '')

    if (!title || !startLocal) {
      setFormError('A title and a start time are required.')
      return
    }

    setSaving(true)
    setFormError(null)
    try {
      await scheduleLiveClass({
        title,
        start_time: new Date(startLocal).toISOString(),
        end_time: endLocal ? new Date(endLocal).toISOString() : null,
        section_id: sectionRaw ? Number(sectionRaw) : null,
        // Never pre-enabled. The tick below is the teacher's explicit consent.
        recording_enabled: form.get('recording_enabled') === 'on',
      })
      setScheduleOpen(false)
      classes.refetch()
    } catch (err) {
      setFormError(
        err instanceof ApiError
          ? err.kind === 'permission_denied'
            ? 'You need teaching or school-admin access to schedule a class.'
            : err.message
          : 'Could not schedule the class. Try again.'
      )
    } finally {
      setSaving(false)
    }
  }

  async function handleStart(row: LiveClassDetailRead) {
    setStartError(null)
    try {
      const res = await startLiveClass(row.id)
      // The room name is what the in-room page joins on.
      window.location.href = `/live/${encodeURIComponent(res.session.room_name)}`
    } catch (err) {
      setStartError(
        err instanceof ApiError
          ? err.message
          : 'Could not start the class. Try again.'
      )
    }
  }

  const rows = classes.data ?? []

  return (
    <DashPageShell
      title="Live classes"
      description="Schedule, run and review live classes for any section."
      action={
        <button
          type="button"
          id="live-class-schedule-open"
          className={LH_PRIMARY_BUTTON}
          onClick={() => setScheduleOpen(true)}
        >
          <Plus className="size-4" /> <span>Schedule a class</span>
        </button>
      }
    >
      <SectionCard
        title={upcoming ? 'Upcoming classes' : 'Past classes'}
        icon={<Video className="size-4 text-gray-500" />}
        state={classes.status}
        error={classes.error}
        onRetry={classes.refetch}
        emptyTitle={upcoming ? 'No classes scheduled' : 'No past classes'}
        emptyDescription={
          upcoming
            ? 'Nothing is scheduled yet. Use "Schedule a class" to add one.'
            : 'No class has finished yet. This is a record of what has already run, not a sign anything is wrong.'
        }
      >
        <div className="mb-4 flex items-center gap-2">
          <button
            type="button"
            id="live-class-filter-upcoming"
            className={upcoming ? LH_PRIMARY_BUTTON : LH_SECONDARY_BUTTON}
            onClick={() => setUpcoming(true)}
          >
            <span>Upcoming</span>
          </button>
          <button
            type="button"
            id="live-class-filter-past"
            className={!upcoming ? LH_PRIMARY_BUTTON : LH_SECONDARY_BUTTON}
            onClick={() => setUpcoming(false)}
          >
            <span>Past</span>
          </button>
        </div>

        {startError && (
          <p className="mb-3 text-sm text-rose-600" role="alert">
            {startError}
          </p>
        )}

        <DataTable
          rows={rows}
          rowKey={(r) => r.id}
          state="success"
          totalLabel={`${rows.length} class${rows.length === 1 ? '' : 'es'}`}
          columns={[
            { key: 'title', header: 'Class', render: (r) => r.title },
            {
              key: 'start',
              header: 'Starts',
              render: (r) => formatWhen(r.start_time),
            },
            {
              key: 'status',
              header: 'Status',
              render: (r) => {
                const d = describeClassStatus(r.status)
                return <StatusChip label={d.label} tone={d.tone} />
              },
            },
            {
              key: 'recording',
              header: 'Recording',
              render: (r) => {
                const d = describeRecording(r.recording.status)
                return <StatusChip label={d.label} tone={d.tone} />
              },
            },
            {
              key: 'actions',
              header: '',
              align: 'right',
              render: (r) => (
                <div className="flex items-center justify-end gap-2">
                  <a
                    id={`live-class-open-${r.id}`}
                    href={`/orgs/${orgslug}/dash/live-classes/${r.id}`}
                    className={LH_SECONDARY_BUTTON}
                  >
                    <span>Open</span>
                  </a>
                  {/* `can_host` is the server's answer for THIS caller. A
                      student never sees a start button, and a teacher never
                      sees one for a colleague's class. */}
                  {r.can_host && isJoinable(r.status) && (
                    <button
                      type="button"
                      id={`live-class-start-${r.id}`}
                      className={LH_PRIMARY_BUTTON}
                      onClick={() => handleStart(r)}
                    >
                      <span>{r.status === 'LIVE' ? 'Rejoin' : 'Start'}</span>
                    </button>
                  )}
                </div>
              ),
            },
          ]}
        />
      </SectionCard>

      <SchoolDialog
        open={scheduleOpen}
        onOpenChange={setScheduleOpen}
        title="Schedule a live class"
        description="Creates the room in advance so students can find it. Recording stays off unless you turn it on."
        onSubmit={handleSchedule}
        footer={
          <button type="submit" id="live-class-schedule-submit" disabled={saving} className={LH_PRIMARY_BUTTON}>
            <span>{saving ? 'Scheduling…' : 'Schedule'}</span>
          </button>
        }
      >
        <SchoolField id="live-class-title" label="Title" required>
          <input id="live-class-title" name="title" className={LH_INPUT} placeholder="Algebra — revision" />
        </SchoolField>

        <SchoolField id="live-class-section" label="Class section">
          <select id="live-class-section" name="section_id" className={LH_INPUT} defaultValue="">
            <option value="">No section</option>
            {(sections.data ?? []).map((s) => (
              <option key={s.id} value={s.id}>
                {s.grade_level} — {s.section_name}
              </option>
            ))}
          </select>
        </SchoolField>

        <SchoolField id="live-class-start" label="Starts" required>
          <input id="live-class-start" name="start_time" type="datetime-local" className={LH_INPUT} />
        </SchoolField>

        <SchoolField id="live-class-end" label="Ends">
          <input id="live-class-end" name="end_time" type="datetime-local" className={LH_INPUT} />
        </SchoolField>

        <SchoolField
          id="live-class-recording"
          label="Record this class"
          help="Off by default. Recording a room full of children is never implicit — turn it on only when you mean to, and you choose separately whether students can watch it back."
        >
          <input id="live-class-recording" name="recording_enabled" type="checkbox" className="size-4" />
        </SchoolField>

        {formError && <p className="text-sm text-rose-600">{formError}</p>}
      </SchoolDialog>

      {campuses.status === 'empty' && (
        <SectionCard title="Set up a campus first" icon={<CalendarBlank className="size-4 text-gray-500" />}>
          <p className="text-sm text-gray-500">
            Live classes attach to a class section, which belongs to a campus.
          </p>
        </SectionCard>
      )}
    </DashPageShell>
  )
}
