'use client'

/**
 * Existing-conflict scan.
 *
 * `/check-clashes` (used by the slot dialog) answers "would this ONE proposed
 * slot conflict?" and runs on write. It cannot answer "is our timetable
 * sound?" -- which is the question that matters once slots have been created
 * with clash enforcement disabled, bulk-imported, or invalidated by a later
 * edit somewhere else.
 *
 * THE DISTINCTION THIS SCREEN KEEPS: "no conflicts across 40 slots" and
 * "nothing was checked" are different answers, and a scheduler acts differently
 * on each. A clean timetable is reassurance; an empty one means the filter
 * matched nothing and the reassurance is worthless.
 */

import { useState } from 'react'
import { AlertTriangle, CheckCircle2, ShieldAlert } from 'lucide-react'
import {
  DashPageShell,
  DataTable,
  EmptyState,
  LH_INPUT,
  SectionCard,
  StatGrid,
  StatusChip,
} from '@/components/widgets'
import { useApiResource } from '@/lib/api/useApiResource'
import { useSchoolSession } from '@/lib/api/useSchoolSession'
import { listCampuses, listClassSections } from '@/modules/sms/campus/api'
import { scanTimetableConflicts } from '@/modules/sms/timetable/api'
import type { ClashDetail } from '@/modules/sms/timetable/types'

interface ConflictsClientProps {
  org_id: number
  orgslug: string
}

const CLASH_LABEL: Record<string, string> = {
  TEACHER_DOUBLE_BOOKED: 'Teacher in two places',
  ROOM_DOUBLE_BOOKED: 'Room double-booked',
  SECTION_DOUBLE_BOOKED: 'Class in two lessons',
}

export default function TimetableConflictsClient({ org_id }: ConflictsClientProps) {
  const { session } = useSchoolSession()
  const [campusId, setCampusId] = useState<number | undefined>(undefined)
  const [sectionId, setSectionId] = useState<number | undefined>(undefined)

  const campuses = useApiResource(() => listCampuses({ orgId: org_id, isActive: true }), [org_id], {
    isEmpty: (d) => d.length === 0,
  })
  const effectiveCampusId = campusId ?? session?.campus_id ?? campuses.data?.[0]?.id

  const sections = useApiResource(
    () => listClassSections(effectiveCampusId as number, { isActive: true }),
    [effectiveCampusId],
    { skip: effectiveCampusId === undefined, isEmpty: (d) => d.length === 0 }
  )

  const scan = useApiResource(
    () => scanTimetableConflicts({ sectionId }),
    [sectionId],
    {}
  )

  const scanned = scan.data?.scanned_slots ?? 0
  const conflicts: ClashDetail[] = scan.data?.conflicts ?? []
  // Nothing checked is NOT a clean bill of health.
  const nothingChecked = scan.status === 'success' && scanned === 0
  const clean = scan.status === 'success' && scanned > 0 && conflicts.length === 0

  return (
    <DashPageShell
      module="timetable"
      title="Timetable conflicts"
      description="Double-bookings that already exist in the timetable, as opposed to checking one slot before you create it."
    >
      <SectionCard
        title="What to scan"
        icon={<ShieldAlert className="size-4 text-gray-500" />}
        state={campuses.status === 'loading' ? 'loading' : 'success'}
        error={campuses.error}
        onRetry={campuses.refetch}
      >
        <div className="flex flex-wrap items-end gap-4">
          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-medium text-gray-500">Campus</span>
            <select
              id="conflicts-campus"
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
              id="conflicts-section"
              className={LH_INPUT}
              value={sectionId ?? ''}
              onChange={(e) => setSectionId(e.target.value ? Number(e.target.value) : undefined)}
            >
              <option value="">All sections I can see</option>
              {(sections.data ?? []).map((s) => (
                <option key={s.id} value={s.id}>
                  {s.grade_level} — {s.section_name}
                </option>
              ))}
            </select>
          </label>
        </div>
      </SectionCard>

      <StatGrid
        state={scan.status === 'loading' ? 'loading' : 'success'}
        columns={2}
        items={[
          { label: 'Slots checked', value: scanned, icon: CheckCircle2, tone: 'neutral' },
          {
            label: 'Conflicts found',
            value: conflicts.length,
            icon: AlertTriangle,
            tone: conflicts.length > 0 ? 'critical' : 'positive',
          },
        ]}
      />

      <SectionCard
        title="Conflicts"
        description={scan.data?.message}
        icon={<AlertTriangle className="size-4 text-gray-500" />}
        state={scan.status === 'loading' ? 'loading' : scan.status === 'error' ? 'error' : 'success'}
        error={scan.error}
        onRetry={scan.refetch}
      >
        {nothingChecked ? (
          <EmptyState
            tone="caution"
            title="Nothing was checked"
            /* Critically NOT "no conflicts": the filter matched no slots, so
               this says nothing about whether the timetable is sound. */
            description="No timetable slots matched this filter, so this is not a clean bill of health — there was nothing to check. Build the timetable first, or widen the filter."
          />
        ) : clean ? (
          <EmptyState
            title="No conflicts found"
            description={`All ${scanned} scheduled slot${scanned === 1 ? '' : 's'} checked out — no teacher, room or class is double-booked.`}
          />
        ) : (
          <DataTable
            rows={conflicts}
            rowKey={(r, i) => `${r.clash_type}-${r.conflicting_schedule_id ?? i}`}
            state="success"
            totalLabel={`${conflicts.length} conflict${conflicts.length === 1 ? '' : 's'}`}
            columns={[
              {
                key: 'type',
                header: 'Type',
                render: (r) => (
                  <StatusChip
                    label={CLASH_LABEL[r.clash_type] ?? r.clash_type}
                    tone="critical"
                  />
                ),
              },
              { key: 'day', header: 'Day', render: (r) => r.day_of_week ?? '—' },
              { key: 'period', header: 'Period', render: (r) => (r.period_id != null ? `#${r.period_id}` : '—') },
              { key: 'room', header: 'Room', render: (r) => r.room_number ?? '—' },
              { key: 'detail', header: 'Detail', render: (r) => r.description },
            ]}
          />
        )}
      </SectionCard>
    </DashPageShell>
  )
}
