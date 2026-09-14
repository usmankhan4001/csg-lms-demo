'use client'

/**
 * Assisted timetable generation.
 *
 * The screen that stops a school hand-typing forty slots per section per term.
 *
 * TWO THINGS THIS UI MUST NOT DO, because the backend deliberately does not:
 *
 * 1. Present a generated week as complete when it is not. `unplaced` is given
 *    equal billing to `placed` -- a scheduler who cannot see that three periods
 *    failed to place will believe the section's week is finished.
 * 2. Write anything the user did not ask for. The preview runs with
 *    `dry_run: true` and the save is a separate, explicit action.
 */

import { useState } from 'react'
import { CalendarCog, AlertTriangle, CheckCircle2, Plus, Trash2 } from 'lucide-react'
import toast from 'react-hot-toast'
import {
  DashPageShell,
  DataTable,
  EmptyState,
  LH_INPUT,
  LH_PRIMARY_BUTTON,
  LH_SECONDARY_BUTTON,
  SectionCard,
  StatGrid,
  StatusChip,
} from '@/components/widgets'
import { ApiError, apiGet } from '@/lib/api/api-client'
import { useApiResource } from '@/lib/api/useApiResource'
import { useSchoolSession } from '@/lib/api/useSchoolSession'
import { listCampuses, listClassSections, listSchoolPeople } from '@/modules/sms/campus/api'
import { generateTimetable, listClassPeriods } from '@/modules/sms/timetable/api'
import type { GenerationRequirement, GenerationResponse } from '@/modules/sms/timetable/types'

interface OrgCourse {
  id: number
  name: string
}

interface GenerateClientProps {
  org_id: number
  orgslug: string
}

/** A requirement row being edited. Strings, because they come from inputs. */
interface DraftRequirement {
  key: number
  courseId: string
  teacherId: string
  periodsPerWeek: string
  roomNumber: string
}

let nextKey = 1

function emptyRequirement(): DraftRequirement {
  return { key: nextKey++, courseId: '', teacherId: '', periodsPerWeek: '1', roomNumber: '' }
}

export default function TimetableGenerateClient({ org_id, orgslug }: GenerateClientProps) {
  const { session } = useSchoolSession()
  const [campusId, setCampusId] = useState<number | undefined>(undefined)
  const [sectionId, setSectionId] = useState<number | undefined>(undefined)
  const [requirements, setRequirements] = useState<DraftRequirement[]>([emptyRequirement()])
  const [preview, setPreview] = useState<GenerationResponse | null>(null)
  const [running, setRunning] = useState(false)
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

  const teachers = useApiResource(
    () => listSchoolPeople('TEACHER', effectiveCampusId),
    [effectiveCampusId],
    { skip: effectiveCampusId === undefined, isEmpty: (d) => d.length === 0 }
  )

  const periods = useApiResource(
    () => listClassPeriods(effectiveCampusId),
    [effectiveCampusId],
    { skip: effectiveCampusId === undefined, isEmpty: (d) => d.length === 0 }
  )

  const courses = useApiResource(
    () => apiGet<OrgCourse[]>(`/courses/org_slug/${orgslug}/page/1/limit/100?include_unpublished=true`),
    [orgslug],
    { isEmpty: (d) => d.length === 0 }
  )

  const courseName = (id: number) => courses.data?.find((c) => c.id === id)?.name ?? `Course #${id}`
  const teacherName = (id: number) =>
    teachers.data?.find((t) => t.user_id === id)?.name ?? `Teacher #${id}`
  const periodLabel = (id: number) => {
    const p = periods.data?.find((x) => x.id === id)
    if (!p) return `Period #${id}`
    return p.name ?? `Period ${p.period_number}`
  }

  function buildRequirements(): GenerationRequirement[] | null {
    const built: GenerationRequirement[] = []
    for (const r of requirements) {
      const courseId = Number(r.courseId)
      const teacherId = Number(r.teacherId)
      const perWeek = Number(r.periodsPerWeek)
      if (!courseId || !teacherId || !perWeek) return null
      built.push({
        course_id: courseId,
        teacher_id: teacherId,
        periods_per_week: perWeek,
        room_number: r.roomNumber.trim() || null,
      })
    }
    return built.length ? built : null
  }

  async function run(dryRun: boolean) {
    if (effectiveSectionId === undefined) return
    const built = buildRequirements()
    if (!built) {
      setError('Every row needs a course, a teacher and a number of periods.')
      return
    }
    dryRun ? setRunning(true) : setSaving(true)
    setError(null)
    try {
      const result = await generateTimetable({
        section_id: effectiveSectionId,
        requirements: built,
        dry_run: dryRun,
      })
      setPreview(result)
      if (!dryRun) {
        toast.success(`Saved ${result.placed.length} slot(s) to the timetable.`)
      }
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.kind === 'permission_denied'
            ? 'You need school-admin access to build a timetable for this section.'
            : err.message
          : 'Could not run generation. Try again.'
      )
    } finally {
      setRunning(false)
      setSaving(false)
    }
  }

  const blocked = periods.data?.length === 0
  const hasUnplaced = (preview?.unplaced.length ?? 0) > 0

  return (
    <DashPageShell
      module="timetable"
      title="Generate timetable"
      description="Bulk-place a section's weekly lessons into free slots, then review before saving."
    >
      <SectionCard
        title="Section"
        icon={<CalendarCog className="size-4 text-gray-500" />}
        state={campuses.status === 'loading' || sections.status === 'loading' ? 'loading' : campuses.status}
        error={campuses.error ?? sections.error}
        onRetry={campuses.refetch}
        emptyTitle="No campuses set up yet"
        emptyDescription="Add a campus and class sections before building a timetable."
      >
        <div className="flex flex-wrap items-end gap-4">
          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-medium text-gray-500">Campus</span>
            <select
              id="generate-campus"
              className={LH_INPUT}
              value={effectiveCampusId ?? ''}
              onChange={(e) => {
                setCampusId(Number(e.target.value))
                setSectionId(undefined)
                setPreview(null)
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
              id="generate-section"
              className={LH_INPUT}
              value={effectiveSectionId ?? ''}
              onChange={(e) => {
                setSectionId(Number(e.target.value))
                setPreview(null)
              }}
              disabled={(sections.data ?? []).length === 0}
            >
              {(sections.data ?? []).map((s) => (
                <option key={s.id} value={s.id}>
                  {s.grade_level} — {s.section_name}
                </option>
              ))}
            </select>
          </label>
        </div>

        {blocked && (
          <p className="mt-3 text-sm text-amber-700">
            No class periods are defined for this campus, so there are no slots to place
            lessons into. Define the bell schedule on the Timetable page first.
          </p>
        )}
      </SectionCard>

      <SectionCard
        title="What this section needs"
        description="One row per course: how many periods a week, and who teaches it."
        icon={<CalendarCog className="size-4 text-gray-500" />}
      >
        <div className="flex flex-col gap-3">
          {requirements.map((r, i) => (
            <div key={r.key} className="flex flex-wrap items-end gap-3">
              <label className="flex flex-col gap-1.5">
                <span className="text-xs font-medium text-gray-500">Course</span>
                <select
                  id={`req-course-${r.key}`}
                  className={LH_INPUT}
                  value={r.courseId}
                  onChange={(e) => {
                    const next = [...requirements]
                    next[i] = { ...r, courseId: e.target.value }
                    setRequirements(next)
                  }}
                >
                  <option value="">Choose a course…</option>
                  {(courses.data ?? []).map((c) => (
                    <option key={c.id} value={c.id}>{c.name}</option>
                  ))}
                </select>
              </label>

              <label className="flex flex-col gap-1.5">
                <span className="text-xs font-medium text-gray-500">Teacher</span>
                <select
                  id={`req-teacher-${r.key}`}
                  className={LH_INPUT}
                  value={r.teacherId}
                  onChange={(e) => {
                    const next = [...requirements]
                    next[i] = { ...r, teacherId: e.target.value }
                    setRequirements(next)
                  }}
                >
                  <option value="">Choose a teacher…</option>
                  {(teachers.data ?? []).map((t) => (
                    <option key={t.user_id} value={t.user_id}>
                      {t.name ?? `User #${t.user_id}`}
                    </option>
                  ))}
                </select>
              </label>

              <label className="flex flex-col gap-1.5">
                <span className="text-xs font-medium text-gray-500">Periods / week</span>
                <input
                  id={`req-perweek-${r.key}`}
                  type="number"
                  min={1}
                  max={40}
                  className={`${LH_INPUT} w-28`}
                  value={r.periodsPerWeek}
                  onChange={(e) => {
                    const next = [...requirements]
                    next[i] = { ...r, periodsPerWeek: e.target.value }
                    setRequirements(next)
                  }}
                />
              </label>

              <label className="flex flex-col gap-1.5">
                <span className="text-xs font-medium text-gray-500">Room (optional)</span>
                <input
                  id={`req-room-${r.key}`}
                  className={`${LH_INPUT} w-32`}
                  value={r.roomNumber}
                  placeholder="204"
                  onChange={(e) => {
                    const next = [...requirements]
                    next[i] = { ...r, roomNumber: e.target.value }
                    setRequirements(next)
                  }}
                />
              </label>

              {requirements.length > 1 && (
                <button
                  type="button"
                  id={`req-remove-${r.key}`}
                  className={LH_SECONDARY_BUTTON}
                  onClick={() => setRequirements(requirements.filter((x) => x.key !== r.key))}
                  aria-label="Remove this course"
                >
                  <Trash2 className="size-4" />
                </button>
              )}
            </div>
          ))}

          <div className="flex flex-wrap items-center gap-2 pt-1">
            <button
              type="button"
              id="req-add"
              className={LH_SECONDARY_BUTTON}
              onClick={() => setRequirements([...requirements, emptyRequirement()])}
            >
              <Plus className="size-4" /> <span>Add a course</span>
            </button>
            <button
              type="button"
              id="generate-preview"
              className={LH_PRIMARY_BUTTON}
              disabled={running || blocked || effectiveSectionId === undefined}
              onClick={() => run(true)}
            >
              <span>{running ? 'Working…' : 'Preview timetable'}</span>
            </button>
          </div>

          {error && <p className="text-sm text-rose-600">{error}</p>}
        </div>
      </SectionCard>

      {preview && (
        <>
          <StatGrid
            columns={3}
            items={[
              { label: 'Requested', value: preview.requested_periods, icon: CalendarCog, tone: 'neutral' },
              { label: 'Placed', value: preview.placed.length, icon: CheckCircle2, tone: 'positive' },
              {
                label: 'Could not place',
                value: preview.unplaced.length,
                icon: AlertTriangle,
                // Zero unplaced is genuinely good news; any other number is not.
                tone: hasUnplaced ? 'critical' : 'neutral',
              },
            ]}
          />

          {hasUnplaced && (
            <SectionCard
              title="Could not be placed"
              description="These periods have no conflict-free slot. Nothing was invented to fill them."
              icon={<AlertTriangle className="size-4 text-rose-500" />}
            >
              <DataTable
                rows={preview.unplaced}
                rowKey={(r) => `${r.course_id}-${r.teacher_id}-${r.occurrence}`}
                state="success"
                columns={[
                  { key: 'course', header: 'Course', render: (r) => courseName(r.course_id) },
                  { key: 'teacher', header: 'Teacher', render: (r) => teacherName(r.teacher_id) },
                  { key: 'occurrence', header: 'Period', render: (r) => `#${r.occurrence}` },
                  { key: 'reason', header: 'Why', render: (r) => r.reason },
                ]}
              />
            </SectionCard>
          )}

          <SectionCard
            title={preview.dry_run ? 'Preview — nothing saved yet' : 'Saved to the timetable'}
            description={preview.message}
            icon={<CalendarCog className="size-4 text-gray-500" />}
          >
            {preview.placed.length === 0 ? (
              <EmptyState
                tone="caution"
                title="Nothing could be placed"
                description="Every requested period conflicted with an existing booking, or there are no periods defined."
              />
            ) : (
              <>
                <DataTable
                  rows={preview.placed}
                  rowKey={(r) => `${r.day_of_week}-${r.period_id}-${r.course_id}`}
                  state="success"
                  totalLabel={`${preview.placed.length} slot${preview.placed.length === 1 ? '' : 's'}`}
                  columns={[
                    { key: 'day', header: 'Day', render: (r) => r.day_of_week },
                    { key: 'period', header: 'Period', render: (r) => periodLabel(r.period_id) },
                    { key: 'course', header: 'Course', render: (r) => courseName(r.course_id) },
                    { key: 'teacher', header: 'Teacher', render: (r) => teacherName(r.teacher_id) },
                    { key: 'room', header: 'Room', render: (r) => r.room_number ?? '—' },
                  ]}
                />
                {preview.dry_run && (
                  <div className="mt-4 flex flex-wrap items-center gap-3">
                    <button
                      type="button"
                      id="generate-save"
                      className={LH_PRIMARY_BUTTON}
                      disabled={saving}
                      onClick={() => run(false)}
                    >
                      <span>{saving ? 'Saving…' : `Save ${preview.placed.length} slot(s)`}</span>
                    </button>
                    {hasUnplaced && (
                      <span className="text-sm text-amber-700">
                        {preview.unplaced.length} period(s) will still be missing after saving.
                      </span>
                    )}
                  </div>
                )}
                {!preview.dry_run && (
                  <p className="mt-4 text-sm text-gray-600">
                    <StatusChip label="Saved" tone="positive" /> These slots are now on the
                    timetable.
                  </p>
                )}
              </>
            )}
          </SectionCard>
        </>
      )}
    </DashPageShell>
  )
}
