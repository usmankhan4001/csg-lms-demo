'use client'

/**
 * Timetable, attached as a first-class Learnhouse dash module.
 *
 * The page sits under `dash/`, inheriting ClientAdminLayout exactly like
 * Courses or Playgrounds, gated on the real `sms_timetable` feature toggle.
 *
 * `TimetableGrid` is reused unchanged -- the module moved shells, it wasn't
 * rewritten. This page adds the campus/section/term scoping around it, plus a
 * substitutions panel over the real `/sms/timetable/substitutions` endpoints.
 *
 * Substitutions are DATE-SCOPED against one recurring slot and never mutate
 * the schedule's own teacher, so the original teacher is always restorable.
 * Cancelling is soft, keeping "who was asked to cover" auditable -- which is
 * why cancelled rows can be shown rather than vanishing.
 */

import { useState } from 'react'
import toast from 'react-hot-toast'
import { CalendarDays, Repeat2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { DashPageShell, DataTable, EmptyState, SectionCard, StatusChip } from '@/components/widgets'
import { apiGet } from '@/lib/api/api-client'
import { useApiResource } from '@/lib/api/useApiResource'
import { useSchoolSession } from '@/lib/api/useSchoolSession'
import { listAcademicTerms, listCampuses, listClassSections, listSchoolPeople } from '@/modules/sms/campus/api'
import {
  cancelSubstitution,
  createSubstitution,
  listClassPeriods,
  listSubstitutions,
  listTimetableSchedules,
} from '@/modules/sms/timetable/api'
import { ClassPeriodDialog } from '@/modules/sms/timetable/components/ClassPeriodDialog'
import { ScheduleSlotDialog } from '@/modules/sms/timetable/components/ScheduleSlotDialog'
import { TimetableGrid } from '@/modules/sms/timetable/components/TimetableGrid'

interface TimetableDashClientProps {
  org_id: number
  orgslug: string
}

/** Learnhouse's own courses — a timetable slot points at a real course_id. */
interface OrgCourse {
  id: number
  name: string
}

export default function TimetableDashClient({ org_id, orgslug }: TimetableDashClientProps) {
  const { session } = useSchoolSession()
  const [campusId, setCampusId] = useState<number | undefined>(undefined)
  const [sectionId, setSectionId] = useState<number | undefined>(undefined)
  const [termId, setTermId] = useState<number | undefined>(undefined)

  // Substitution form state
  const [subScheduleId, setSubScheduleId] = useState<string>('')
  const [subDate, setSubDate] = useState<string>('')
  const [subTeacherId, setSubTeacherId] = useState<string>('')
  const [subReason, setSubReason] = useState<string>('')
  const [submitting, setSubmitting] = useState(false)

  const campuses = useApiResource(() => listCampuses({ orgId: org_id, isActive: true }), [org_id], {
    isEmpty: (d) => d.length === 0,
  })

  const effectiveCampusId = campusId ?? session?.campus_id ?? campuses.data?.[0]?.id

  const sections = useApiResource(
    () => listClassSections(effectiveCampusId as number, { isActive: true }),
    [effectiveCampusId],
    { skip: effectiveCampusId === undefined, isEmpty: (d) => d.length === 0 }
  )

  const terms = useApiResource(
    () => listAcademicTerms({ campusId: effectiveCampusId }),
    [effectiveCampusId],
    { skip: effectiveCampusId === undefined, isEmpty: (d) => d.length === 0 }
  )

  const effectiveSectionId = sectionId ?? sections.data?.[0]?.id
  const effectiveTermId = termId ?? session?.academic_term_id ?? terms.data?.[0]?.id

  const schedules = useApiResource(
    () => listTimetableSchedules({ sectionId: effectiveSectionId, academicTermId: effectiveTermId }),
    [effectiveSectionId, effectiveTermId],
    { skip: effectiveSectionId === undefined, isEmpty: (d) => d.length === 0 }
  )

  const substitutions = useApiResource(() => listSubstitutions(), [], {
    isEmpty: (d) => d.length === 0,
  })

  // Teachers come from the school-role registry, which returns real names and
  // the Learnhouse `user_id` the backend expects for `teacher_id` /
  // `substitute_teacher_id` (every SMS table referencing "the teacher" keys on
  // the user id, not StaffProfile.id). Previously this read staff profiles,
  // which meant rows rendered as "Staff #12" wherever a profile was missing.
  const teachers = useApiResource(
    () => listSchoolPeople('TEACHER', effectiveCampusId),
    [effectiveCampusId],
    { isEmpty: (d) => d.length === 0 }
  )
  const substituteCandidates = teachers.data ?? []

  const periods = useApiResource(
    () => listClassPeriods(effectiveCampusId),
    [effectiveCampusId],
    { isEmpty: (d) => d.length === 0 }
  )

  const courses = useApiResource(
    () => apiGet<OrgCourse[]>(`/courses/org_slug/${orgslug}/page/1/limit/100?include_unpublished=true`),
    [orgslug],
    { isEmpty: (d) => d.length === 0 }
  )

  const slots = schedules.data ?? []

  async function handleCreateSubstitution(e: React.FormEvent) {
    e.preventDefault()
    if (!subScheduleId || !subDate || !subTeacherId) {
      toast.error('Pick a slot, a date and a substitute teacher.')
      return
    }
    setSubmitting(true)
    try {
      await createSubstitution({
        schedule_id: Number(subScheduleId),
        substitution_date: subDate,
        substitute_teacher_id: Number(subTeacherId),
        reason: subReason.trim() || null,
      })
      toast.success('Substitute assigned.')
      setSubScheduleId('')
      setSubDate('')
      setSubTeacherId('')
      setSubReason('')
      substitutions.refetch()
    } catch (err) {
      // The API returns 409 for a genuine scheduling conflict (e.g. the
      // substitute is already booked that period) -- surface its message.
      toast.error(err instanceof Error ? err.message : 'Could not assign a substitute.')
    } finally {
      setSubmitting(false)
    }
  }

  async function handleCancel(id: number) {
    try {
      await cancelSubstitution(id)
      toast.success('Substitution cancelled.')
      substitutions.refetch()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Could not cancel.')
    }
  }

  const staffName = (userId: number) =>
    substituteCandidates.find((s) => s.user_id === userId)?.name ?? `Teacher #${userId}`

  return (
    <DashPageShell
      module="timetable"
      title={"Timetable"}
      description="The weekly schedule for a section, with clashes flagged and cover arrangements."
      action={
        <div className="flex items-center gap-2">
          <ClassPeriodDialog
            campusId={effectiveCampusId}
            existingPeriods={periods.data ?? []}
            onCreated={periods.refetch}
          />
          <ScheduleSlotDialog
            sectionId={effectiveSectionId}
            academicTermId={effectiveTermId}
            periods={periods.data ?? []}
            teachers={teachers.data ?? []}
            courses={courses.data ?? []}
            onCreated={() => {
              schedules.refetch()
              toast.success('Slot added to the timetable.')
            }}
          />
        </div>
      }
    >
      <SectionCard
        title="Choose a section"
        icon={<CalendarDays className="size-4 text-gray-500" />}
        state={
          campuses.status === 'loading' || sections.status === 'loading' ? 'loading' : campuses.status
        }
        error={campuses.error ?? sections.error}
        onRetry={campuses.refetch}
        emptyTitle="No campuses set up yet"
        emptyDescription="Add a campus and class sections before building a timetable."
      >
        <div className="flex flex-wrap items-end gap-4">
          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-medium text-gray-500">Campus</span>
            <select
              id="timetable-campus"
              className="px-3 py-2 bg-white nice-shadow rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-black focus:ring-offset-2 border-0"
              value={effectiveCampusId ?? ''}
              onChange={(e) => {
                setCampusId(Number(e.target.value))
                setSectionId(undefined)
                setTermId(undefined)
              }}
            >
              {(campuses.data ?? []).map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>

          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-medium text-gray-500">Section</span>
            <select
              id="timetable-section"
              className="px-3 py-2 bg-white nice-shadow rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-black focus:ring-offset-2 border-0"
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

          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-medium text-gray-500">Term</span>
            <select
              id="timetable-term"
              className="px-3 py-2 bg-white nice-shadow rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-black focus:ring-offset-2 border-0"
              value={effectiveTermId ?? ''}
              onChange={(e) => setTermId(Number(e.target.value))}
              disabled={(terms.data ?? []).length === 0}
            >
              {(terms.data ?? []).map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
          </label>
        </div>
      </SectionCard>

      {effectiveSectionId !== undefined ? (
        <TimetableGrid
          slots={slots}
          state={schedules.status}
          error={schedules.error}
          onRetry={schedules.refetch}
          description="Clash flags here compare only the slots shown; the server validates across the whole timetable on save."
        />
      ) : (
        <SectionCard title="Weekly Timetable" icon={<CalendarDays className="size-4 text-gray-500" />}>
          <EmptyState
            title="No section selected"
            description="Pick a campus and section above to see its weekly schedule."
          />
        </SectionCard>
      )}

      <SectionCard
        id="substitutions"
        title="Teacher Substitutions"
        description="Cover for one slot on one date. The permanent timetable is never changed."
        icon={<Repeat2 className="size-4 text-gray-500" />}
        state={substitutions.status === 'empty' ? 'success' : substitutions.status}
        error={substitutions.error}
        onRetry={substitutions.refetch}
      >
        <div className="space-y-4">
          <form onSubmit={handleCreateSubstitution} className="flex flex-wrap items-end gap-3">
            <label className="flex flex-col gap-1.5">
              <span className="text-xs font-medium text-gray-500">Slot</span>
              <select
                id="substitution-slot"
                className="px-3 py-2 bg-white nice-shadow rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-black focus:ring-offset-2 border-0"
                value={subScheduleId}
                onChange={(e) => setSubScheduleId(e.target.value)}
                disabled={slots.length === 0}
              >
                <option value="">Select a slot…</option>
                {slots.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.day_of_week} P{s.period_number ?? s.period_id} · Course #{s.course_id}
                  </option>
                ))}
              </select>
            </label>

            <label className="flex flex-col gap-1.5">
              <span className="text-xs font-medium text-gray-500">Date</span>
              <Input
                id="substitution-date"
                type="date"
                className="h-9 w-44"
                value={subDate}
                onChange={(e) => setSubDate(e.target.value)}
              />
            </label>

            <label className="flex flex-col gap-1.5">
              <span className="text-xs font-medium text-gray-500">Substitute</span>
              <select
                id="substitution-teacher"
                className="px-3 py-2 bg-white nice-shadow rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-black focus:ring-offset-2 border-0"
                value={subTeacherId}
                onChange={(e) => setSubTeacherId(e.target.value)}
                disabled={substituteCandidates.length === 0}
              >
                <option value="">Select teacher…</option>
                {substituteCandidates.map((s) => (
                  <option key={s.user_id} value={s.user_id}>
                    {s.name ?? `Teacher #${s.user_id}`}
                  </option>
                ))}
              </select>
            </label>

            <label className="flex flex-col gap-1.5">
              <span className="text-xs font-medium text-gray-500">Reason (optional)</span>
              <Input
                id="substitution-reason"
                className="h-9 w-52"
                placeholder="Sick leave"
                value={subReason}
                onChange={(e) => setSubReason(e.target.value)}
              />
            </label>

            <Button type="submit" size="sm" disabled={submitting}>
              {submitting ? 'Assigning…' : 'Assign cover'}
            </Button>
          </form>

          {substituteCandidates.length === 0 && teachers.status !== 'loading' && (
            <p className="text-xs text-gray-500">
              Nobody holds the Teacher role yet, so there is no one to assign as a substitute. Grant
              it in Users → a person → School.
            </p>
          )}

          <DataTable
            rows={substitutions.data ?? []}
            rowKey={(row) => row.id}
            state="success"
            columns={[
              { key: 'date', header: 'Date', render: (r) => r.substitution_date },
              { key: 'slot', header: 'Slot', render: (r) => `Schedule #${r.schedule_id}` },
              { key: 'original', header: 'Original', render: (r) => staffName(r.original_teacher_id) },
              { key: 'substitute', header: 'Covering', render: (r) => staffName(r.substitute_teacher_id) },
              { key: 'reason', header: 'Reason', render: (r) => r.reason || '—' },
              {
                key: 'status',
                header: 'Status',
                render: (r) =>
                  r.is_active ? (
                    <StatusChip label="Active" tone="positive" />
                  ) : (
                    <StatusChip label="Cancelled" tone="neutral" />
                  ),
              },
              {
                key: 'action',
                header: '',
                align: 'right',
                render: (r) =>
                  r.is_active ? (
                    <Button size="sm" variant="ghost" onClick={() => handleCancel(r.id)}>
                      Cancel
                    </Button>
                  ) : null,
              },
            ]}
          />
        </div>
      </SectionCard>
    </DashPageShell>
  )
}
