'use client'

/**
 * Two different questions about one student, answered side by side:
 *
 *  - the monthly SHEET: what their attendance actually was
 *  - the correction TRAIL: every change made to it, by whom and when
 *
 * The trail is append-only (`sms_attendance.py:547` -- there is deliberately
 * no endpoint to edit or delete an entry), which is what makes a register a
 * legal record rather than a mutable note. `action` distinguishes the first
 * marking from a later correction, and `previous_status` is null on MARKED
 * because there was no previous status -- distinct from PRESENT.
 *
 * The monthly percentage is `null` when no register has been taken, and is
 * rendered "Not recorded". A head of year seeing "0%" would read "attended
 * nothing"; the truth is nobody marked a register.
 */

import { useState } from 'react'
import { CalendarRange, History } from 'lucide-react'
import {
  DashPageShell,
  DataTable,
  LH_INPUT,
  LH_PRIMARY_BUTTON,
  SectionCard,
  StatGrid,
  StatusChip,
} from '@/components/widgets'
import { useApiResource } from '@/lib/api/useApiResource'
import { useSchoolSession } from '@/lib/api/useSchoolSession'
import {
  getMonthlyStudentAttendance,
  getStudentAttendanceHistory,
} from '@/modules/sms/attendance/api'
import {
  ATTENDANCE_TONE,
  formatAttendancePercentage,
  formatDate,
  formatDateTime,
  studentLabel,
} from '@/modules/sms/attendance/presentation'
import { useStudentNames } from '@/modules/sms/attendance/useStudentNames'
import { DataExportToolbar } from '@/components/ems/DataExportToolbar'
import type { ExportColumn } from '@/lib/export/data-export'

interface Props {
  org_id: number
  orgslug: string
}

export default function AttendanceHistoryClient({ org_id }: Props) {
  const { session } = useSchoolSession()
  const campusId = session?.campus_id ?? undefined
  const { names } = useStudentNames(campusId)

  const now = new Date()
  const [studentIdInput, setStudentIdInput] = useState('')
  const [studentId, setStudentId] = useState<number | null>(null)
  const [year, setYear] = useState(now.getFullYear())
  const [month, setMonth] = useState(now.getMonth() + 1)

  const sheet = useApiResource(
    () => getMonthlyStudentAttendance(studentId ?? 0, year, month),
    [studentId, year, month],
    { skip: studentId === null }
  )

  const trail = useApiResource(
    () => getStudentAttendanceHistory(studentId ?? 0),
    [studentId],
    { skip: studentId === null, isEmpty: (d) => d.length === 0 }
  )

  const stats = sheet.data?.stats

  const dailyExportColumns: ExportColumn[] = [
    { key: 'date', label: 'Date', type: 'date' },
    { key: 'period_id', label: 'Period', type: 'text', accessor: (r) => (r.period_id ? `#${r.period_id}` : 'Whole day') },
    { key: 'status', label: 'Status', type: 'text' },
    { key: 'remarks', label: 'Remarks', type: 'text' },
  ]

  const trailExportColumns: ExportColumn[] = [
    { key: 'date', label: 'Register Date', type: 'date' },
    { key: 'action', label: 'Action', type: 'text' },
    { key: 'previous_status', label: 'Previous Status', type: 'text' },
    { key: 'new_status', label: 'New Status', type: 'text' },
    { key: 'changed_by_user_id', label: 'Changed By User ID', type: 'number' },
    { key: 'reason', label: 'Reason', type: 'text' },
    { key: 'created_at', label: 'Timestamp', type: 'datetime' },
  ]

  return (
    <DashPageShell
      module="attendance"
      title="Attendance history"
      description="A student's month, and every correction ever made to their register."
    >
      <SectionCard
        id="history-picker"
        title="Choose a student"
        icon={<CalendarRange className="size-4 text-gray-500" />}
      >
        <form
          className="flex flex-wrap items-end gap-3"
          onSubmit={(e) => {
            e.preventDefault()
            const parsed = Number(studentIdInput)
            setStudentId(Number.isFinite(parsed) && parsed > 0 ? parsed : null)
          }}
        >
          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-medium text-gray-500">Student ID</span>
            <input
              id="history-student-id"
              className={LH_INPUT}
              value={studentIdInput}
              onChange={(e) => setStudentIdInput(e.target.value)}
              placeholder="e.g. 37"
              inputMode="numeric"
            />
          </label>
          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-medium text-gray-500">Year</span>
            <input
              id="history-year"
              className={LH_INPUT}
              value={year}
              onChange={(e) => setYear(Number(e.target.value) || now.getFullYear())}
              inputMode="numeric"
            />
          </label>
          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-medium text-gray-500">Month</span>
            <select
              id="history-month"
              className={LH_INPUT}
              value={month}
              onChange={(e) => setMonth(Number(e.target.value))}
            >
              {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
                <option key={m} value={m}>
                  {new Date(2000, m - 1, 1).toLocaleString(undefined, { month: 'long' })}
                </option>
              ))}
            </select>
          </label>
          <button id="history-load" type="submit" className={LH_PRIMARY_BUTTON}>
            <span>Load</span>
          </button>
        </form>
        {studentId !== null && (
          <p className="mt-3 text-sm text-gray-600">
            Showing <strong>{studentLabel(studentId, names)}</strong>
          </p>
        )}
      </SectionCard>

      {studentId !== null && (
        <>
          <StatGrid
            state={sheet.status === 'loading' ? 'loading' : 'success'}
            columns={4}
            items={[
              {
                label: 'Attendance',
                // Null -> "Not recorded", never 0%.
                value: formatAttendancePercentage(stats?.attendance_percentage),
                icon: CalendarRange,
                tone: 'neutral',
                hint:
                  stats && stats.total_days === 0
                    ? 'No register taken this month'
                    : undefined,
              },
              { label: 'Days recorded', value: stats?.total_days ?? 0, icon: CalendarRange, tone: 'neutral' },
              { label: 'Absent', value: stats?.absent_days ?? 0, icon: CalendarRange, tone: 'critical' },
              { label: 'Late', value: stats?.late_days ?? 0, icon: CalendarRange, tone: 'caution' },
            ]}
          />

          <SectionCard
            id="history-daily"
            title="This month, day by day"
            icon={<CalendarRange className="size-4 text-gray-500" />}
            state={sheet.status}
            error={sheet.error}
            onRetry={sheet.refetch}
            emptyTitle="No register taken this month"
            emptyDescription="Nothing has been marked for this student in the month selected."
            action={
              (sheet.data?.daily_records ?? []).length > 0 && (
                <DataExportToolbar
                  data={sheet.data?.daily_records ?? []}
                  columns={dailyExportColumns}
                  filenamePrefix={`attendance_student_${studentId}_${year}_${month}`}
                  title={`Daily Attendance - Student #${studentId}`}
                  activeFilters={{ studentId, year, month }}
                />
              )
            }
          >
            <DataTable
              rows={sheet.data?.daily_records ?? []}
              rowKey={(r) => r.id}
              state="success"
              columns={[
                { key: 'date', header: 'Date', render: (r) => formatDate(r.date) },
                {
                  key: 'period',
                  header: 'Period',
                  render: (r) => (r.period_id ? `#${r.period_id}` : 'Whole day'),
                },
                {
                  key: 'status',
                  header: 'Status',
                  render: (r) => (
                    <StatusChip label={r.status} tone={ATTENDANCE_TONE[r.status]} />
                  ),
                },
                { key: 'remarks', header: 'Remarks', render: (r) => r.remarks || '—' },
              ]}
            />
          </SectionCard>

          <SectionCard
            id="history-trail"
            title="Correction trail"
            description="Append-only. Every change to this student's register, including the first marking."
            icon={<History className="size-4 text-gray-500" />}
            state={trail.status}
            error={trail.error}
            onRetry={trail.refetch}
            emptyTitle="No changes recorded"
            emptyDescription="Nothing has been marked or corrected for this student yet."
            action={
              (trail.data ?? []).length > 0 && (
                <DataExportToolbar
                  data={trail.data ?? []}
                  columns={trailExportColumns}
                  filenamePrefix={`attendance_audit_trail_student_${studentId}`}
                  title={`Attendance Correction Trail - Student #${studentId}`}
                  activeFilters={{ studentId }}
                  classification="RESTRICTED"
                />
              )
            }
          >
            <DataTable
              rows={trail.data ?? []}
              rowKey={(r) => r.id}
              state="success"
              totalLabel={`${(trail.data ?? []).length} entr${(trail.data ?? []).length === 1 ? 'y' : 'ies'}`}
              columns={[
                { key: 'date', header: 'Register date', render: (r) => formatDate(r.date) },
                {
                  key: 'action',
                  header: 'Action',
                  render: (r) => (
                    <StatusChip
                      label={r.action === 'marked' ? 'First marking' : 'Correction'}
                      tone={r.action === 'marked' ? 'neutral' : 'caution'}
                    />
                  ),
                },
                {
                  key: 'change',
                  header: 'Change',
                  render: (r) =>
                    // Null previous_status means there was no previous status.
                    // Rendering it as "PRESENT" would invent a fact.
                    r.previous_status ? (
                      <span>
                        {r.previous_status} → {r.new_status}
                      </span>
                    ) : (
                      <span>Set to {r.new_status}</span>
                    ),
                },
                {
                  key: 'by',
                  header: 'By',
                  render: (r) =>
                    r.changed_by_user_id ? `User #${r.changed_by_user_id}` : 'Not recorded',
                },
                { key: 'reason', header: 'Reason', render: (r) => r.reason || '—' },
                { key: 'when', header: 'When', render: (r) => formatDateTime(r.created_at) },
              ]}
            />
          </SectionCard>
        </>
      )}
    </DashPageShell>
  )
}
