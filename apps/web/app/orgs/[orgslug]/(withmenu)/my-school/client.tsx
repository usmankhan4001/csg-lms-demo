'use client'

/**
 * "My School" -- the non-staff school surface, attached to Learnhouse's own
 * LEARNER shell ((withmenu)/ + OrgMenu) rather than the admin dash.
 *
 * Why here and not under dash/: Learnhouse ships two shells on purpose --
 * dash/ for people administering the org, (withmenu)/ for people learning in
 * it. A student already lives in this shell (courses, player, certificates),
 * so their timetable and grades belong beside those, not inside an admin
 * dashboard. A parent is the awkward case: Learnhouse has no parent concept
 * at all, but a parent is far closer to a learner-side consumer than to an
 * org administrator, so they land here too.
 *
 * One route, branching on the school role from GET /sms/me, rather than five
 * near-identical routes -- a student and a parent want different answers to
 * the same question ("how is school going"), not different sections of one
 * page.
 */

import { Award, BookMarked, CalendarClock, CheckSquare, CreditCard, GraduationCap, Users } from 'lucide-react'
import Link from 'next/link'
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { DataTable, EmptyState, KpiCard, SectionCard, StatGrid, StatusChip } from '@/components/widgets'
import { formatAttendancePercentage } from '@/modules/sms/attendance/presentation'
import { formatGpa } from '@/modules/sms/gradebook/presentation'
import { useApiResource } from '@/lib/api/useApiResource'
import { getChildContext, useSchoolSession } from '@/lib/api/useSchoolSession'
import { getMonthlyStudentAttendance } from '@/modules/sms/attendance/api'
import { getStudentFeeLedger } from '@/modules/sms/fees/api'
import { getStudentReportCard } from '@/modules/sms/gradebook/api'
import { listLoans } from '@/modules/sms/library/api'
import { getStudentTimetable, slotsForToday } from '@/modules/sms/timetable/api'

interface MySchoolClientProps {
  org_id: number
  orgslug: string
}

export default function MySchoolClient({ orgslug }: MySchoolClientProps) {
  const { session, checked } = useSchoolSession()

  if (!checked) {
    return (
      <div className="mx-auto w-full max-w-5xl px-4 py-8">
        <StatGrid state="loading" items={[]} />
      </div>
    )
  }

  const roles = session?.roles ?? []
  const isParent = roles.includes('PARENT')
  const isStudent = roles.includes('STUDENT')

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-6 px-4 py-8">
      <div>
        <h1 className="text-xl font-bold text-foreground">My School</h1>
        <p className="text-sm text-muted-foreground">
          {isParent ? "Your children's progress at a glance." : 'Your timetable, attendance and grades.'}
        </p>
      </div>

      {isParent ? (
        <ParentView />
      ) : isStudent ? (
        <StudentView session={session} orgslug={orgslug} />
      ) : (
        <EmptyState
          tone="caution"
          title="No school record linked to your account"
          description="Ask your school admin to enrol you in a class section, or to link you as a guardian."
        />
      )}
    </div>
  )
}

/* ---------------------------------------------------------------- student */

function StudentView({
  session,
  orgslug,
}: {
  session: ReturnType<typeof useSchoolSession>['session']
  orgslug: string
}) {
  const studentId = session?.student_id ?? undefined
  const sectionId = session?.section_id ?? undefined
  const termId = session?.academic_term_id ?? undefined
  const ready = studentId !== undefined && sectionId !== undefined
  const now = new Date()

  const timetable = useApiResource(
    () => getStudentTimetable(studentId as number, sectionId as number, termId),
    [studentId, sectionId, termId],
    { skip: !ready, isEmpty: (d) => d.slots.length === 0 }
  )
  const attendance = useApiResource(
    () => getMonthlyStudentAttendance(studentId as number, now.getFullYear(), now.getMonth() + 1, sectionId),
    [studentId, sectionId],
    { skip: !ready, isEmpty: (d) => d.stats.total_days === 0 }
  )
  const reportCard = useApiResource(
    () => getStudentReportCard(studentId as number, sectionId as number, termId as number),
    [studentId, sectionId, termId],
    { skip: !ready || termId === undefined, isEmpty: (d) => d.courses.length === 0 }
  )
  const loans = useApiResource(() => listLoans({ userId: studentId }), [studentId], { skip: !ready })

  if (!ready) {
    return (
      <EmptyState
        tone="caution"
        title="You're not enrolled in a section yet"
        description="Ask your school admin to enrol you so your timetable and grades appear here."
      />
    )
  }

  const todaySlots = timetable.data ? slotsForToday(timetable.data.slots) : []
  const activeLoans = (loans.data ?? []).filter((l) => l.status !== 'RETURNED')

  return (
    <>
      {/* The AI tutor lives in this shell too. Surfaced here as well as in
          OrgMenu because a student arriving at "My School" to check grades is
          exactly the moment they realise they are stuck on something. */}
      <Link
        href={`/orgs/${orgslug}/ai-tutor`}
        id="my-school-ai-tutor"
        className="flex items-center gap-3 rounded-xl bg-white px-4 py-3 nice-shadow transition-opacity hover:opacity-80"
      >
        <div className="rounded-full bg-gray-100 p-2">
          <GraduationCap className="size-4 text-gray-600" />
        </div>
        <div className="flex flex-col">
          <span className="text-sm font-medium text-foreground">Ask the AI Tutor</span>
          <span className="text-xs text-muted-foreground">
            Stuck on something? Work it through with your study coach.
          </span>
        </div>
      </Link>

      <StatGrid
        state={attendance.status === 'loading' ? 'loading' : 'success'}
        columns={4}
        items={[
          {
            // `attendance_percentage` is null when no register has been taken
            // this month. Calling .toFixed() on it threw at runtime, and
            // before the API started returning null it rendered "0.0%" -- to a
            // PARENT, which reads as "my child attended nothing" when the truth
            // is nobody marked a register. Tone follows suit: no data is not
            // good news.
            label: 'Attendance this month',
            value: formatAttendancePercentage(attendance.data?.stats.attendance_percentage),
            icon: CheckSquare,
            tone: attendance.data?.stats.attendance_percentage == null ? 'neutral' : 'positive',
          },
          { label: "Today's classes", value: todaySlots.length, icon: CalendarClock, tone: 'neutral' },
          {
            label: 'Cumulative GPA',
            // `cumulative_gpa` is null when the student has no graded
            // coursework. Calling .toFixed on it crashed this page outright
            // for a newly enrolled child, and before the API nulled it the
            // value shown to a parent was a fabricated one. No grades is not
            // a grade of zero, so it is reported as an absence.
            value: formatGpa(reportCard.data?.cumulative_gpa),
            icon: Award,
            tone: reportCard.data?.cumulative_gpa == null ? 'neutral' : 'positive',
          },
          { label: 'Library loans', value: activeLoans.length, icon: BookMarked, tone: 'neutral' },
        ]}
      />

      <SectionCard
        id="timetable"
        title="Today's Timetable"
        icon={<CalendarClock className="size-4 text-muted-foreground" />}
        state={timetable.status}
        error={timetable.error}
        onRetry={timetable.refetch}
        emptyTitle="No classes today"
      >
        <DataTable
          rows={todaySlots}
          rowKey={(row) => row.id}
          state="success"
          columns={[
            { key: 'period', header: 'Period', render: (r) => r.period_number ?? r.period_id },
            { key: 'time', header: 'Time', render: (r) => (r.start_time && r.end_time ? `${r.start_time} – ${r.end_time}` : '—') },
            { key: 'course', header: 'Course', render: (r) => `Course #${r.course_id}` },
            { key: 'room', header: 'Room', render: (r) => r.room_number ?? '—' },
          ]}
        />
      </SectionCard>

      <SectionCard
        id="attendance"
        title="Attendance Record"
        icon={<CheckSquare className="size-4 text-muted-foreground" />}
        state={attendance.status}
        error={attendance.error}
        onRetry={attendance.refetch}
        emptyTitle="No attendance recorded yet this month"
      >
        {attendance.data && (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <KpiCard label="Present" value={attendance.data.stats.present_days} tone="positive" />
            <KpiCard label="Absent" value={attendance.data.stats.absent_days} tone="critical" />
            <KpiCard label="Late" value={attendance.data.stats.late_days} tone="caution" />
            <KpiCard label="Excused" value={attendance.data.stats.excused_days} tone="neutral" />
          </div>
        )}
      </SectionCard>

      <SectionCard
        id="grades"
        title="Grades & Report Card"
        icon={<GraduationCap className="size-4 text-muted-foreground" />}
        state={termId === undefined ? 'empty' : reportCard.status}
        error={reportCard.error}
        onRetry={reportCard.refetch}
        emptyTitle="No grades published yet"
        emptyDescription="Your report card appears here once a term is scored and sent."
      >
        <DataTable
          rows={reportCard.data?.courses ?? []}
          rowKey={(row) => row.course_id}
          state="success"
          columns={[
            { key: 'course', header: 'Course', render: (r) => r.course_name || `Course #${r.course_id}` },
            { key: 'pct', header: 'Score', align: 'right', render: (r) => `${r.total_weighted_percentage.toFixed(1)}%` },
            { key: 'grade', header: 'Grade', render: (r) => <StatusChip label={r.letter_grade} tone="info" /> },
            { key: 'gpa', header: 'GPA Point', align: 'right', render: (r) => r.gpa_point.toFixed(2) },
          ]}
        />
      </SectionCard>
    </>
  )
}

/* ----------------------------------------------------------------- parent */

interface ChildSummary {
  studentId: number
  name: string | null
  attendancePct: number | null
  gpa: number | null
  outstanding: number
}

async function loadChild(studentId: number): Promise<ChildSummary> {
  const now = new Date()
  const context = await getChildContext(studentId).catch(() => null)
  const sectionId = context?.section_id ?? undefined
  const termId = context?.academic_term_id ?? undefined
  const [attendance, reportCard, ledger] = await Promise.all([
    getMonthlyStudentAttendance(studentId, now.getFullYear(), now.getMonth() + 1, sectionId).catch(() => null),
    sectionId !== undefined && termId !== undefined
      ? getStudentReportCard(studentId, sectionId, termId).catch(() => null)
      : Promise.resolve(null),
    getStudentFeeLedger(studentId).catch(() => null),
  ])
  return {
    studentId,
    name: context?.name ?? null,
    attendancePct: attendance?.stats.attendance_percentage ?? null,
    gpa: reportCard?.cumulative_gpa ?? null,
    outstanding: ledger?.total_outstanding ?? 0,
  }
}

function ParentView() {
  const { session } = useSchoolSession()
  const childrenIds = session?.children_ids ?? []
  const [activeChild, setActiveChild] = useState<string>('all')

  const children = useApiResource(
    () => Promise.all(childrenIds.map(loadChild)),
    [childrenIds.join(',')],
    { skip: childrenIds.length === 0, isEmpty: (d) => d.length === 0 }
  )

  if (childrenIds.length === 0) {
    return (
      <EmptyState
        tone="caution"
        title="No children linked to your account"
        description="Ask your school admin to link you as a guardian for your child's record."
      />
    )
  }

  const all = children.data ?? []
  const rows = activeChild === 'all' ? all : all.filter((r) => String(r.studentId) === activeChild)
  const totalOutstanding = rows.reduce((s, c) => s + c.outstanding, 0)

  return (
    <>
      {all.length > 1 && (
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setActiveChild('all')}
            className={`rounded-md border px-3 py-1.5 text-sm transition-colors ${
              activeChild === 'all' ? 'border-foreground bg-foreground text-background' : 'border-border hover:bg-muted'
            }`}
          >
            All children
          </button>
          {all.map((c) => (
            <button
              key={c.studentId}
              type="button"
              onClick={() => setActiveChild(String(c.studentId))}
              className={`rounded-md border px-3 py-1.5 text-sm transition-colors ${
                activeChild === String(c.studentId)
                  ? 'border-foreground bg-foreground text-background'
                  : 'border-border hover:bg-muted'
              }`}
            >
              {c.name ?? `Student #${c.studentId}`}
            </button>
          ))}
        </div>
      )}

      <StatGrid
        state={children.status === 'loading' ? 'loading' : 'success'}
        columns={3}
        items={[
          { label: 'Children', value: rows.length, icon: Users, tone: 'neutral' },
          {
            label: 'Avg. attendance',
            value: rows.length
              ? `${(rows.reduce((s, c) => s + (c.attendancePct ?? 0), 0) / rows.length).toFixed(1)}%`
              : '—',
            icon: CalendarClock,
            tone: 'positive',
          },
          {
            label: 'Outstanding fees',
            value: `Rs. ${totalOutstanding.toFixed(2)}`,
            icon: CreditCard,
            tone: totalOutstanding > 0 ? 'caution' : 'positive',
          },
        ]}
      />

      <SectionCard
        title="Progress"
        icon={<GraduationCap className="size-4 text-muted-foreground" />}
        state={children.status}
        error={children.error}
        onRetry={children.refetch}
        emptyTitle="No records yet"
      >
        <DataTable
          rows={rows}
          rowKey={(row) => row.studentId}
          state="success"
          columns={[
            { key: 'child', header: 'Child', render: (r) => r.name ?? `Student #${r.studentId}` },
            {
              key: 'att',
              header: 'Attendance',
              align: 'right',
              render: (r) => (r.attendancePct !== null ? `${r.attendancePct.toFixed(1)}%` : '—'),
            },
            { key: 'gpa', header: 'GPA', align: 'right', render: (r) => r.gpa?.toFixed(2) ?? '—' },
            {
              key: 'fees',
              header: 'Outstanding',
              align: 'right',
              render: (r) => `Rs. ${r.outstanding.toFixed(2)}`,
            },
          ]}
        />
      </SectionCard>
    </>
  )
}
