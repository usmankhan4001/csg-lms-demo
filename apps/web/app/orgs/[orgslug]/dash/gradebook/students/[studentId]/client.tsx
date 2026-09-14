'use client'

/**
 * One student across their courses: marks, GPA, standing.
 *
 * THE GPA FIELDS ARE NULLABLE AND THAT IS THE POINT. This endpoint used to
 * return a hardcoded `unweighted_gpa: 4.0`, `academic_standing: "Good
 * Standing"`, `honor_roll: true` for a student with ZERO grades — a flawless
 * record and an honour-roll place for a child who had never been marked. It
 * was live in the router for weeks. The fix makes those fields null, and this
 * screen renders the absence as an absence.
 *
 * `weighted_gpa` is gone rather than reimplemented: the old one added +0.5 to
 * every course as "standard honors weighting", but nothing in the model marks
 * a course as honours, so it inflated every GPA on a distinction the system
 * cannot make.
 */

import { GraduationCap, BookOpen, Award } from 'lucide-react'
import {
  DashPageShell,
  DataTable,
  EmptyState,
  SectionCard,
  StatGrid,
  StatusChip,
} from '@/components/widgets'
import { useApiResource } from '@/lib/api/useApiResource'
import { useSchoolSession } from '@/lib/api/useSchoolSession'
import { useStudentNames } from '@/modules/sms/attendance/useStudentNames'
import { getStudentGpa, listReportCards } from '@/modules/sms/gradebook/api'
import {
  REPORT_CARD_STATUS_LABEL,
  REPORT_CARD_STATUS_TONE,
  formatCredits,
  formatGpa,
  formatGpaShort,
  formatLetterGrade,
  formatTimestamp,
  studentLabel,
} from '@/modules/sms/gradebook/presentation'

interface StudentGradesClientProps {
  org_id: number
  orgslug: string
  studentId: number
}

export default function StudentGradesClient({ studentId }: StudentGradesClientProps) {
  const { session } = useSchoolSession()
  const names = useStudentNames(session?.campus_id ?? undefined)

  const gpa = useApiResource(() => getStudentGpa(studentId), [studentId])
  const cards = useApiResource(() => listReportCards({ studentId }), [studentId], {
    isEmpty: (d) => d.length === 0,
  })

  const data = gpa.data
  const hasGpa = data?.unweighted_gpa != null

  return (
    <DashPageShell
      module="gradebook"
      title={studentLabel(studentId, names.names)}
      description="Cumulative grades and report-card history."
    >
      <SectionCard
        title="Cumulative standing"
        icon={<GraduationCap className="size-4 text-gray-500" />}
        state={gpa.status}
        error={gpa.error}
        onRetry={gpa.refetch}
        emptyTitle="No grade record"
        emptyDescription="This student has no gradebook record yet."
      >
        {!hasGpa ? (
          <EmptyState
            title="No grades recorded"
            description={
              data?.detail ??
              'This student has no graded coursework on file, so there is no GPA to report. That is different from a GPA of zero.'
            }
          />
        ) : (
          <div className="flex flex-col gap-4">
            <StatGrid
              state="success"
              columns={4}
              items={[
                {
                  label: 'Cumulative GPA',
                  value: formatGpa(data?.unweighted_gpa),
                  icon: GraduationCap,
                  tone: 'neutral',
                },
                {
                  label: 'Graded courses',
                  value: `${data?.graded_courses ?? 0} of ${data?.total_courses ?? 0}`,
                  icon: BookOpen,
                  tone: 'neutral',
                },
                {
                  label: 'Credits',
                  value: formatCredits(data?.total_credits),
                  icon: BookOpen,
                  tone: 'neutral',
                },
                {
                  label: 'Standing',
                  value: data?.academic_standing ?? 'Not assessed',
                  icon: Award,
                  tone: data?.honor_roll ? 'positive' : 'neutral',
                },
              ]}
            />

            {(data?.total_courses ?? 0) > (data?.graded_courses ?? 0) && (
              <p className="text-xs text-gray-500">
                {(data?.total_courses ?? 0) - (data?.graded_courses ?? 0)} course
                {(data?.total_courses ?? 0) - (data?.graded_courses ?? 0) === 1 ? ' has' : 's have'} nothing
                marked yet and {(data?.total_courses ?? 0) - (data?.graded_courses ?? 0) === 1 ? 'is' : 'are'} excluded
                from this GPA — unmarked work is not failed work.
              </p>
            )}
          </div>
        )}
      </SectionCard>

      <SectionCard
        title="Report cards"
        icon={<GraduationCap className="size-4 text-gray-500" />}
        state={cards.status}
        error={cards.error}
        onRetry={cards.refetch}
        emptyTitle="No report cards yet"
        emptyDescription="Report cards appear here once a teacher drafts them for this student's section and term."
      >
        <DataTable
          rows={cards.data ?? []}
          rowKey={(row) => row.id}
          state="success"
          totalLabel={`${(cards.data ?? []).length} card${(cards.data ?? []).length === 1 ? '' : 's'}`}
          columns={[
            { key: 'term', header: 'Term', render: (r) => `Term #${r.academic_term_id}` },
            {
              key: 'status',
              header: 'Status',
              render: (r) => (
                <StatusChip
                  label={REPORT_CARD_STATUS_LABEL[r.status] ?? r.status}
                  tone={REPORT_CARD_STATUS_TONE[r.status] ?? 'neutral'}
                />
              ),
            },
            {
              key: 'gpa',
              header: 'GPA',
              align: 'right',
              render: (r) =>
                r.cumulative_gpa == null ? (
                  <span className="text-xs text-amber-700">No grades</span>
                ) : (
                  <span className="tabular-nums">{formatGpaShort(r.cumulative_gpa)}</span>
                ),
            },
            {
              key: 'letter',
              header: 'Grade',
              align: 'center',
              render: (r) => formatLetterGrade(r.overall_letter_grade),
            },
            {
              key: 'sent',
              header: 'Sent',
              render: (r) => (r.status === 'sent' ? formatTimestamp(r.sent_at) : '—'),
            },
          ]}
        />
      </SectionCard>
    </DashPageShell>
  )
}
