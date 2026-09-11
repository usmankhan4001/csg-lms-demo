'use client'

/**
 * Parent dashboard -- thin composition over the real SMS modules.
 *
 * "My children" come from the dev Keycloak session's `children_ids`
 * convenience claim (see `lib/api/dev-token.ts`). Per-child grades use the
 * session's single `section_id`/`academic_term_id` claims for every child --
 * a documented simplification of this dev harness (a real token would carry
 * each child's own section).
 */

import { CalendarClock, CreditCard, TrendingUp, Users } from 'lucide-react'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { DataTable, EmptyState, SectionCard, StatGrid } from '@/components/widgets'
import { useApiResource } from '@/lib/api/useApiResource'
import { useDevSession } from '@/lib/api/useDevSession'
import { getMonthlyStudentAttendance } from '@/modules/sms/attendance/api'
import { getStudentFeeLedger } from '@/modules/sms/fees/api'
import { getStudentReportCard } from '@/modules/sms/gradebook/api'
import type { MonthlyStudentAttendanceSheet } from '@/modules/sms/attendance/types'
import type { StudentTermReportCardResponse } from '@/modules/sms/gradebook/types'
import type { StudentFeeLedgerResponse } from '@/modules/sms/fees/types'

interface ChildSummary {
  studentId: number
  attendance: MonthlyStudentAttendanceSheet | null
  reportCard: StudentTermReportCardResponse | null
  ledger: StudentFeeLedgerResponse | null
}

async function loadChildSummary(studentId: number, sectionId?: number, termId?: number): Promise<ChildSummary> {
  const now = new Date()
  const [attendance, reportCard, ledger] = await Promise.all([
    getMonthlyStudentAttendance(studentId, now.getFullYear(), now.getMonth() + 1, sectionId).catch(() => null),
    sectionId !== undefined && termId !== undefined ? getStudentReportCard(studentId, sectionId, termId).catch(() => null) : Promise.resolve(null),
    getStudentFeeLedger(studentId).catch(() => null),
  ])
  return { studentId, attendance, reportCard, ledger }
}

export default function ParentDashboardPage() {
  const { session, checked } = useDevSession()
  const childrenIds = session?.children_ids ?? []
  const sectionId = session?.section_id ?? undefined
  const termId = session?.academic_term_id ?? undefined
  const ready = checked && childrenIds.length > 0

  const children = useApiResource(
    () => Promise.all(childrenIds.map((id) => loadChildSummary(id, sectionId, termId))),
    [childrenIds.join(','), sectionId, termId],
    { skip: !ready, isEmpty: (d) => d.length === 0 }
  )

  const rows = children.data ?? []
  const avgAttendance = rows.length
    ? rows.reduce((sum, c) => sum + (c.attendance?.stats.attendance_percentage ?? 0), 0) / rows.length
    : null
  const totalOutstanding = rows.reduce((sum, c) => sum + (c.ledger?.total_outstanding ?? 0), 0)

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-foreground">
          {checked ? `Welcome, ${session?.name ?? 'Parent'}` : 'Welcome'}
        </h1>
        <p className="text-sm text-muted-foreground">Your children&apos;s progress at a glance.</p>
      </div>

      {!checked ? (
        <StatGrid state="loading" items={[]} />
      ) : !ready ? (
        <EmptyState
          tone="caution"
          title="No children linked to this session"
          description="Mint a dev token with --children-ids to see this dashboard populated -- see apps/api/scripts/mint_dev_keycloak_token.py."
        />
      ) : (
        <>
          <StatGrid
            state={children.status === 'loading' ? 'loading' : 'success'}
            columns={3}
            items={[
              { label: 'Children', value: childrenIds.length, icon: Users, tone: 'neutral' },
              {
                label: 'Avg. attendance',
                value: avgAttendance !== null ? `${avgAttendance.toFixed(1)}%` : '—',
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
            id="attendance"
            title="My Children — Attendance"
            icon={<CalendarClock className="size-4 text-muted-foreground" />}
            state={children.status}
            error={children.error}
            onRetry={children.refetch}
            emptyTitle="No attendance data yet"
          >
            <DataTable
              rows={rows}
              rowKey={(row) => row.studentId}
              state="success"
              columns={[
                { key: 'child', header: 'Child', render: (r) => `Student #${r.studentId}` },
                {
                  key: 'pct',
                  header: 'Attendance this month',
                  align: 'right',
                  render: (r) => (r.attendance ? `${r.attendance.stats.attendance_percentage.toFixed(1)}%` : '—'),
                },
                { key: 'present', header: 'Present', align: 'right', render: (r) => r.attendance?.stats.present_days ?? '—' },
                { key: 'absent', header: 'Absent', align: 'right', render: (r) => r.attendance?.stats.absent_days ?? '—' },
              ]}
            />
          </SectionCard>

          <SectionCard
            id="performance"
            title="Performance & Grades"
            icon={<TrendingUp className="size-4 text-muted-foreground" />}
            state={children.status}
            error={children.error}
            onRetry={children.refetch}
            emptyTitle="No report card published yet"
          >
            <DataTable
              rows={rows}
              rowKey={(row) => row.studentId}
              state="success"
              columns={[
                { key: 'child', header: 'Child', render: (r) => `Student #${r.studentId}` },
                { key: 'gpa', header: 'Cumulative GPA', align: 'right', render: (r) => r.reportCard?.cumulative_gpa.toFixed(2) ?? '—' },
                { key: 'grade', header: 'Overall Grade', render: (r) => r.reportCard?.overall_letter_grade ?? '—' },
              ]}
            />
          </SectionCard>

          <div className="flex justify-end">
            <Button asChild variant="outline" size="sm">
              <Link href="/parent/fees">
                <CreditCard className="size-4" /> View fee vouchers & pay
              </Link>
            </Button>
          </div>
        </>
      )}
    </div>
  )
}
