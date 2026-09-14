'use client'

/**
 * Attendance, attached as a first-class Learnhouse dash module.
 *
 * This replaces the parallel CSG portal shell: the page sits under
 * `dash/`, so it inherits ClientAdminLayout (left menu + header) exactly
 * like Courses, Boards or Playgrounds, and its nav entry in DashLeftMenu is
 * gated on the real `sms_attendance` feature toggle already resolved by the
 * backend into `org.config.config.resolved_features`.
 *
 * Staff pick a campus and section here; the roster itself is the same
 * `RollCallRoster` the teacher portal used, unchanged -- the module moved
 * shells, it wasn't rewritten.
 */

import { useState } from 'react'
import { CalendarCheck } from 'lucide-react'
import { DashPageShell, EmptyState, SectionCard } from '@/components/widgets'
import { useApiResource } from '@/lib/api/useApiResource'
import { useSchoolSession } from '@/lib/api/useSchoolSession'
import { listCampuses, listClassSections } from '@/modules/sms/campus/api'
import { RollCallRoster } from '@/modules/sms/attendance/components/RollCallRoster'

interface AttendanceDashClientProps {
  org_id: number
  orgslug: string
}

export default function AttendanceDashClient({ org_id }: AttendanceDashClientProps) {
  const { session, checked } = useSchoolSession()
  const [campusId, setCampusId] = useState<number | undefined>(undefined)
  const [sectionId, setSectionId] = useState<number | undefined>(undefined)

  const campuses = useApiResource(() => listCampuses({ orgId: org_id, isActive: true }), [org_id], {
    isEmpty: (d) => d.length === 0,
  })

  // Default to the caller's own campus when they have one, else the first.
  const effectiveCampusId = campusId ?? session?.campus_id ?? campuses.data?.[0]?.id

  const sections = useApiResource(
    () => listClassSections(effectiveCampusId as number, { isActive: true }),
    [effectiveCampusId],
    { skip: effectiveCampusId === undefined, isEmpty: (d) => d.length === 0 }
  )

  const effectiveSectionId = sectionId ?? sections.data?.[0]?.id

  return (
    <DashPageShell
      module="attendance"
      title={"Attendance"}
      description="Take daily roll-call and review attendance for any section."
    >
      <SectionCard
        title="Choose a section"
        icon={<CalendarCheck className="size-4 text-gray-500" />}
        state={campuses.status === 'loading' || sections.status === 'loading' ? 'loading' : campuses.status}
        error={campuses.error ?? sections.error}
        onRetry={campuses.refetch}
        emptyTitle="No campuses set up yet"
        emptyDescription="Add a campus and class sections before taking attendance."
      >
        <div className="flex flex-wrap items-end gap-4">
          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-medium text-gray-500">Campus</span>
            <select
              id="attendance-campus"
              className="px-3 py-2 bg-white nice-shadow rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-black focus:ring-offset-2 border-0"
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

          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-medium text-gray-500">Section</span>
            <select
              id="attendance-section"
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
        </div>
      </SectionCard>

      {effectiveSectionId !== undefined ? (
        <RollCallRoster
          sectionId={effectiveSectionId}
          campusId={effectiveCampusId}
          markedBy={checked ? session?.staff_id ?? undefined : undefined}
        />
      ) : (
        <SectionCard title="Roll-call" icon={<CalendarCheck className="size-4 text-gray-500" />}>
          <EmptyState
            title="No section selected"
            description="Pick a campus and section above to start taking attendance."
          />
        </SectionCard>
      )}
    </DashPageShell>
  )
}
