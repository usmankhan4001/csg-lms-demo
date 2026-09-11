'use client'

/**
 * Teacher dashboard -- thin composition over the real SMS modules.
 * "My" identity (teacher/staff id, home section, academic term) comes from
 * the dev Keycloak session's convenience claims -- see
 * `lib/api/dev-token.ts`.
 */

import { Award, CalendarClock, Layers } from 'lucide-react'
import { DataTable, EmptyState, SectionCard, StatGrid } from '@/components/widgets'
import { useApiResource } from '@/lib/api/useApiResource'
import { useDevSession } from '@/lib/api/useDevSession'
import { listAssessmentPlans } from '@/modules/sms/gradebook/api'
import { getTeacherTimetable, slotsForToday } from '@/modules/sms/timetable/api'
import { RollCallRoster } from '@/modules/sms/attendance/components/RollCallRoster'

export default function TeacherDashboardPage() {
  const { session, checked } = useDevSession()
  const teacherId = session?.subject_id ?? undefined
  const sectionId = session?.section_id ?? undefined
  const termId = session?.academic_term_id ?? undefined
  const ready = checked && teacherId !== undefined

  const timetable = useApiResource(
    () => getTeacherTimetable(teacherId as number, termId),
    [teacherId, termId],
    { skip: !ready, isEmpty: (d) => d.slots.length === 0 }
  )

  const assessmentPlans = useApiResource(
    () => listAssessmentPlans({ academicTermId: termId }),
    [termId],
    { skip: !ready }
  )

  const todaySlots = timetable.data ? slotsForToday(timetable.data.slots) : []

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-foreground">
          {checked ? `Good day, ${session?.name ?? 'Teacher'}` : 'Good day'}
        </h1>
        <p className="text-sm text-muted-foreground">Your classroom hub for today.</p>
      </div>

      {!checked ? (
        <StatGrid state="loading" items={[]} />
      ) : !ready ? (
        <EmptyState
          tone="caution"
          title="No dev session found"
          description="Attach a dev Keycloak Bearer token to see your real data here -- see apps/api/scripts/mint_dev_keycloak_token.py."
        />
      ) : (
        <>
          <StatGrid
            state={timetable.status === 'loading' || assessmentPlans.status === 'loading' ? 'loading' : 'success'}
            columns={3}
            items={[
              { label: "Today's classes", value: todaySlots.length, icon: CalendarClock, tone: 'neutral' },
              { label: 'This week', value: timetable.data?.slots.length ?? 0, icon: Layers, tone: 'neutral' },
              { label: 'Assessment plans', value: assessmentPlans.data?.length ?? 0, icon: Award, tone: 'positive' },
            ]}
          />

          <SectionCard
            id="timetable"
            title="Today's Classes"
            icon={<CalendarClock className="size-4 text-muted-foreground" />}
            state={timetable.status}
            error={timetable.error}
            onRetry={timetable.refetch}
            emptyTitle="No classes scheduled today"
          >
            <DataTable
              rows={todaySlots}
              rowKey={(row) => row.id}
              state="success"
              columns={[
                { key: 'period', header: 'Period', render: (r) => r.period_number ?? r.period_id },
                { key: 'time', header: 'Time', render: (r) => (r.start_time && r.end_time ? `${r.start_time} – ${r.end_time}` : '—') },
                { key: 'section', header: 'Section', render: (r) => `Section #${r.section_id}` },
                { key: 'course', header: 'Course', render: (r) => `Course #${r.course_id}` },
                { key: 'room', header: 'Room', render: (r) => r.room_number ?? '—' },
              ]}
            />
          </SectionCard>

          {sectionId !== undefined ? (
            <RollCallRoster sectionId={sectionId} markedBy={teacherId} />
          ) : (
            <SectionCard id="attendance" title="1-Click Roll-Call" icon={<CalendarClock className="size-4 text-muted-foreground" />}>
              <EmptyState title="No home section on this session" description="Mint a dev token with --section-id to try roll-call." />
            </SectionCard>
          )}

          <SectionCard
            id="gradebook"
            title="Gradebook & Marking"
            icon={<Award className="size-4 text-muted-foreground" />}
            state={assessmentPlans.status}
            error={assessmentPlans.error}
            onRetry={assessmentPlans.refetch}
            emptyTitle="No assessment plans yet"
            emptyDescription="Assessment plans define the weighting for grades entered into the gradebook."
          >
            <DataTable
              rows={assessmentPlans.data ?? []}
              rowKey={(row) => row.id}
              state="success"
              columns={[
                { key: 'name', header: 'Assessment', render: (r) => r.assessment_name },
                { key: 'course', header: 'Course', render: (r) => `Course #${r.course_id}` },
                { key: 'weight', header: 'Weight', align: 'right', render: (r) => `${r.weight_percentage}%` },
                { key: 'max', header: 'Max score', align: 'right', render: (r) => r.max_score },
              ]}
            />
          </SectionCard>
        </>
      )}
    </div>
  )
}
