'use client'

/**
 * Campus & academic structure, attached as a first-class Learnhouse dash
 * module. Sits under `dash/` so it inherits ClientAdminLayout exactly like
 * Courses or Boards, rather than the parallel CSG portal shell.
 *
 * Scope note: this is deliberately NARROWER than the old
 * `app/(dashboard)/campus-admin` page it replaces. That page was a mixed
 * "console" showing campuses AND finance AND staff together; finance and
 * staff now have their own dash modules (`/dash/financials`, `/dash/hr`), so
 * duplicating them here would mean two places to read the same ledger. What
 * remains is the academic structure itself -- campus, year, term, section --
 * which is the tenancy root every other SMS module scopes against.
 *
 * This screen is effectively the setup entry point for the whole school
 * system, so its empty state explains the required order rather than just
 * saying "nothing here".
 */

import { useState } from 'react'
import { Building2, CalendarRange, GraduationCap, Layers } from 'lucide-react'
import { DashPageShell, DataTable, EmptyState, SectionCard, StatGrid, StatusChip } from '@/components/widgets'
import { useApiResource } from '@/lib/api/useApiResource'
import { SchoolSetup } from '@/modules/sms/campus/components/SchoolSetup'
import { useDeepLinkAction } from '@/lib/dashboard-search/useDeepLinkAction'
import { useSchoolSession } from '@/lib/api/useSchoolSession'
import {
  listAcademicTerms,
  listAcademicYears,
  listCampuses,
  listClassSections,
} from '@/modules/sms/campus/api'

interface CampusDashClientProps {
  org_id: number
  orgslug: string
}

export default function CampusDashClient({ org_id }: CampusDashClientProps) {
  const { session } = useSchoolSession()
  const [campusId, setCampusId] = useState<number | undefined>(undefined)

  const campuses = useApiResource(() => listCampuses({ orgId: org_id }), [org_id], {
    isEmpty: (d) => d.length === 0,
  })

  // Default to the caller's own campus when they have one, else the first.
  const effectiveCampusId = campusId ?? session?.campus_id ?? campuses.data?.[0]?.id
  const hasCampus = effectiveCampusId !== undefined

  const years = useApiResource(
    () => listAcademicYears(effectiveCampusId as number),
    [effectiveCampusId],
    { skip: !hasCampus, isEmpty: (d) => d.length === 0 }
  )

  const terms = useApiResource(
    () => listAcademicTerms({ campusId: effectiveCampusId }),
    [effectiveCampusId],
    { skip: !hasCampus, isEmpty: (d) => d.length === 0 }
  )

  const sections = useApiResource(
    () => listClassSections(effectiveCampusId as number),
    [effectiveCampusId],
    { skip: !hasCampus, isEmpty: (d) => d.length === 0 }
  )

  const activeCampuses = (campuses.data ?? []).filter((c) => c.is_active).length
  const activeYearId = (years.data ?? []).find((y) => y.is_active)?.id ?? years.data?.[0]?.id

  // One handler so creating anything refreshes every dependent list: adding a
  // year has to make the Term button reachable, adding a campus has to unlock
  // all three below it.
  const refetchAll = () => {
    campuses.refetch()
    years.refetch()
    terms.refetch()
    sections.refetch()
  }

  // Ctrl+K "Enrol a student" deep-links here with the dialog open.
  const enrolStudentRequested = useDeepLinkAction('enrol-student')

  return (
    <DashPageShell
      title="Campus & academic structure"
      description="Campuses, academic years, terms and class sections — the structure every other school module builds on."
    >
      <SchoolSetup
        enrolStudentOpen={enrolStudentRequested}
        orgId={org_id}
        campuses={campuses.data ?? []}
        years={years.data ?? []}
        sections={sections.data ?? []}
        activeCampusId={effectiveCampusId}
        activeYearId={activeYearId}
        onChanged={refetchAll}
      />

      <StatGrid
        state={campuses.status === 'loading' ? 'loading' : 'success'}
        columns={4}
        items={[
          { label: 'Campuses', value: campuses.data?.length ?? 0, icon: Building2, tone: 'neutral' },
          { label: 'Active', value: activeCampuses, icon: Building2, tone: 'positive' },
          { label: 'Academic terms', value: terms.data?.length ?? 0, icon: CalendarRange, tone: 'neutral' },
          { label: 'Class sections', value: sections.data?.length ?? 0, icon: Layers, tone: 'neutral' },
        ]}
      />

      <SectionCard
        id="campuses"
        title="Campuses"
        icon={<Building2 className="size-4 text-gray-500" />}
        state={campuses.status}
        error={campuses.error}
        onRetry={campuses.refetch}
        emptyTitle="No campuses yet — start here"
        emptyDescription="A campus is the root of the school structure. Nothing else works until one exists: academic years and class sections hang off a campus, and attendance, timetable and gradebook all scope to a section. Create a campus first, then an academic year, then its terms and sections."
      >
        <DataTable
          rows={campuses.data ?? []}
          rowKey={(row) => row.id}
          state="success"
          totalLabel={`${campuses.data?.length ?? 0} campus${(campuses.data?.length ?? 0) === 1 ? '' : 'es'}`}
          columns={[
            { key: 'name', header: 'Campus', render: (r) => r.name },
            { key: 'code', header: 'Code', render: (r) => r.code },
            { key: 'address', header: 'Address', render: (r) => r.address ?? '—' },
            { key: 'timezone', header: 'Timezone', render: (r) => r.timezone },
            {
              key: 'status',
              header: 'Status',
              render: (r) => (
                <StatusChip
                  label={r.is_active ? 'Active' : 'Inactive'}
                  tone={r.is_active ? 'positive' : 'neutral'}
                />
              ),
            },
          ]}
        />
      </SectionCard>

      {hasCampus && (campuses.data ?? []).length > 1 && (
        <label className="flex w-fit flex-col gap-1.5">
          <span className="text-xs font-medium text-gray-500">Viewing structure for</span>
          <select
            id="campus-picker"
            className="px-3 py-2 bg-white nice-shadow rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-black focus:ring-offset-2 border-0"
            value={effectiveCampusId ?? ''}
            onChange={(e) => setCampusId(Number(e.target.value))}
          >
            {(campuses.data ?? []).map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </label>
      )}

      <SectionCard
        id="academic-years"
        title="Academic years"
        icon={<CalendarRange className="size-4 text-gray-500" />}
        state={!hasCampus ? 'empty' : years.status}
        error={years.error}
        onRetry={years.refetch}
        emptyTitle={hasCampus ? 'No academic years yet' : 'Create a campus first'}
        emptyDescription={
          hasCampus
            ? 'An academic year groups the terms students are enrolled into. Student enrolment records point at a year, so grades and report cards need one.'
            : 'Academic years belong to a campus.'
        }
      >
        <DataTable
          rows={years.data ?? []}
          rowKey={(row) => row.id}
          state="success"
          columns={[
            { key: 'name', header: 'Year', render: (r) => r.name },
            { key: 'start', header: 'Starts', render: (r) => r.start_date ?? '—' },
            { key: 'end', header: 'Ends', render: (r) => r.end_date ?? '—' },
            {
              key: 'status',
              header: 'Status',
              render: (r) => (
                <StatusChip
                  label={r.is_active ? 'Active' : 'Inactive'}
                  tone={r.is_active ? 'positive' : 'neutral'}
                />
              ),
            },
          ]}
        />
      </SectionCard>

      <SectionCard
        id="terms"
        title="Terms"
        icon={<CalendarRange className="size-4 text-gray-500" />}
        state={!hasCampus ? 'empty' : terms.status}
        error={terms.error}
        onRetry={terms.refetch}
        emptyTitle={hasCampus ? 'No terms yet' : 'Create a campus first'}
        emptyDescription={
          hasCampus
            ? 'Terms carry the weighting used to calculate report-card grades, and the gradebook resolves the current term by today’s date falling inside its range.'
            : 'Terms belong to an academic year, which belongs to a campus.'
        }
      >
        <DataTable
          rows={terms.data ?? []}
          rowKey={(row) => row.id}
          state="success"
          columns={[
            { key: 'name', header: 'Term', render: (r) => r.name },
            { key: 'code', header: 'Code', render: (r) => r.term_code ?? '—' },
            {
              key: 'weight',
              header: 'Weight',
              align: 'right',
              render: (r) => `${r.weight_percentage}%`,
            },
            { key: 'start', header: 'Starts', render: (r) => r.start_date ?? '—' },
            { key: 'end', header: 'Ends', render: (r) => r.end_date ?? '—' },
          ]}
        />
      </SectionCard>

      <SectionCard
        id="sections"
        title="Class sections"
        icon={<GraduationCap className="size-4 text-gray-500" />}
        state={!hasCampus ? 'empty' : sections.status}
        error={sections.error}
        onRetry={sections.refetch}
        emptyTitle={hasCampus ? 'No class sections yet' : 'Create a campus first'}
        emptyDescription={
          hasCampus
            ? 'A section is the unit attendance, timetable and gradebook all work against. Students enrol into a section, and a class teacher owns it.'
            : 'Class sections belong to a campus.'
        }
      >
        <DataTable
          rows={sections.data ?? []}
          rowKey={(row) => row.id}
          state="success"
          totalLabel={`${sections.data?.length ?? 0} section${(sections.data?.length ?? 0) === 1 ? '' : 's'}`}
          columns={[
            { key: 'grade', header: 'Grade', render: (r) => r.grade_level },
            { key: 'section', header: 'Section', render: (r) => r.section_name },
            { key: 'room', header: 'Room', render: (r) => r.room_number ?? '—' },
            {
              key: 'teacher',
              header: 'Class teacher',
              render: (r) => (r.class_teacher_id ? `Staff #${r.class_teacher_id}` : 'Unassigned'),
            },
            {
              key: 'capacity',
              header: 'Capacity',
              align: 'right',
              render: (r) => r.max_capacity,
            },
            {
              key: 'status',
              header: 'Status',
              render: (r) => (
                <StatusChip
                  label={r.is_active ? 'Active' : 'Inactive'}
                  tone={r.is_active ? 'positive' : 'neutral'}
                />
              ),
            },
          ]}
        />
      </SectionCard>

      {!hasCampus && campuses.status !== 'loading' && (
        <EmptyState
          tone="caution"
          title="Nothing is set up yet"
          description="Create a campus to unlock academic years, terms, sections, attendance, timetable and the gradebook."
        />
      )}
    </DashPageShell>
  )
}
