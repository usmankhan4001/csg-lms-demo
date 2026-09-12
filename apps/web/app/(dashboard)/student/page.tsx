'use client'

/**
 * Student dashboard -- thin composition over the real SMS modules.
 *
 * Every section below fetches from the real backend via `modules/sms/*`
 * (no mock arrays). "My" identity (student_id/section_id/academic_term_id)
 * comes from the real school session -- see `lib/api/useSchoolSession.ts`.
 *
 * AI Tutor and course/lesson sections were intentionally removed from this
 * rewrite: they belong to a separate, still-in-flight AI RevOps/Tutor
 * workstream (see AGENT scope boundary) and aren't backed by any of the 7
 * SMS modules this task covers. The lesson-player route itself
 * (`student/courses/[courseId]/lesson/[lessonId]`) is untouched and still
 * reachable directly.
 */

import { Award, BookMarked, CalendarClock, CheckSquare, Clock, GraduationCap } from 'lucide-react'
import { DataTable, EmptyState, KpiCard, SectionCard, StatGrid, StatusChip } from '@/components/widgets'
import { useApiResource } from '@/lib/api/useApiResource'
import { useSchoolSession } from '@/lib/api/useSchoolSession'
import { getMonthlyStudentAttendance } from '@/modules/sms/attendance/api'
import { getStudentReportCard } from '@/modules/sms/gradebook/api'
import { listLoans } from '@/modules/sms/library/api'
import { getStudentTimetable, slotsForToday } from '@/modules/sms/timetable/api'

export default function StudentDashboardPage() {
  const { session, checked } = useSchoolSession()
  const studentId = session?.student_id ?? undefined
  const sectionId = session?.section_id ?? undefined
  const termId = session?.academic_term_id ?? undefined
  const ready = checked && studentId !== undefined && sectionId !== undefined

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

  const todaySlots = timetable.data ? slotsForToday(timetable.data.slots) : []
  const activeLoans = (loans.data ?? []).filter((l) => l.status !== 'RETURNED')

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-foreground">
          {checked ? `Welcome back, ${session?.name ?? 'Student'}` : 'Welcome back'}
        </h1>
        <p className="text-sm text-muted-foreground">Here&apos;s what&apos;s happening today.</p>
      </div>

      {!checked ? (
        <StatGrid state="loading" items={[]} />
      ) : !ready ? (
        <EmptyState
          tone="caution"
          title="No dev session found"
          description="Ask your school admin to enroll you in a class section."
        />
      ) : (
        <>
          <StatGrid
            state={attendance.status === 'loading' || reportCard.status === 'loading' ? 'loading' : 'success'}
            columns={4}
            items={[
              {
                label: 'Attendance this month',
                value: attendance.data ? `${attendance.data.stats.attendance_percentage.toFixed(1)}%` : '—',
                icon: CheckSquare,
                tone: 'positive',
              },
              {
                label: "Today's classes",
                value: todaySlots.length,
                icon: Clock,
                tone: 'neutral',
              },
              {
                label: 'Cumulative GPA',
                value: reportCard.data ? reportCard.data.cumulative_gpa.toFixed(2) : '—',
                icon: Award,
                tone: 'positive',
              },
              {
                label: 'Active library loans',
                value: activeLoans.length,
                icon: BookMarked,
                tone: 'neutral',
              },
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
            emptyDescription="Nothing scheduled for today on your timetable."
          >
            <DataTable
              rows={todaySlots}
              rowKey={(row) => row.id}
              state="success"
              columns={[
                { key: 'period', header: 'Period', render: (r) => r.period_number ?? r.period_id },
                { key: 'time', header: 'Time', render: (r) => (r.start_time && r.end_time ? `${r.start_time} – ${r.end_time}` : '—') },
                { key: 'course', header: 'Course', render: (r) => `Course #${r.course_id}` },
                { key: 'teacher', header: 'Teacher', render: (r) => `Staff #${r.teacher_id}` },
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
            emptyDescription="Your report card will appear here once a term is scored."
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

          <SectionCard
            id="library"
            title="Library Loans"
            icon={<BookMarked className="size-4 text-muted-foreground" />}
            state={loans.status}
            error={loans.error}
            onRetry={loans.refetch}
            emptyTitle="No active loans"
            emptyDescription="Books you borrow from the digital library will show up here."
          >
            <DataTable
              rows={activeLoans}
              rowKey={(row) => row.id}
              state="success"
              columns={[
                { key: 'title', header: 'Title', render: (r) => r.book_title || `Book #${r.book_id}` },
                { key: 'due', header: 'Due date', render: (r) => r.due_date },
                {
                  key: 'status',
                  header: 'Status',
                  render: (r) => <StatusChip label={r.status} tone={r.status === 'OVERDUE' ? 'critical' : 'positive'} />,
                },
                { key: 'fine', header: 'Fine', align: 'right', render: (r) => (r.fine_amount > 0 ? `Rs. ${r.fine_amount.toFixed(2)}` : '—') },
              ]}
            />
          </SectionCard>
        </>
      )}
    </div>
  )
}
