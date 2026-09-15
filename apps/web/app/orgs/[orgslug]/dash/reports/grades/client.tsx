'use client'

/**
 * Grade distribution for a term.
 *
 * Scoped by TERM, not by date range, because a grade belongs to a term — the
 * API offers no date filter here and inventing one in the client would ask a
 * question the data cannot answer.
 *
 * Nothing is computed on this page. `average_percentage` and `average_gpa`
 * come from the gradebook's own `resolve_letter_and_gpa`, so there is exactly
 * one grading engine. A student body with no marks entered has NO average —
 * this repo once shipped an endpoint returning a 4.0 GPA and "honor roll" for
 * a student with zero grades, and that is the defect this rendering prevents.
 */

import { useState } from 'react'
import { GraduationCap, Percent } from 'lucide-react'
import { DashPageShell, EmptyState, SectionCard, StatGrid } from '@/components/widgets'
import { useApiResource } from '@/lib/api/useApiResource'
import { useSchoolSession } from '@/lib/api/useSchoolSession'
import { listCampuses } from '@/modules/sms/campus/api'
import { getGradeDistribution } from '@/modules/sms/reports/api'
import { ReportFilters } from '@/modules/sms/reports/components/ReportFilters'
import { formatMetric, metricHint, metricTone } from '@/modules/sms/reports/presentation'

interface Props {
  org_id: number
  orgslug: string
}

export default function GradesReportClient({ org_id }: Props) {
  const { session } = useSchoolSession()
  const [campusId, setCampusId] = useState<number | undefined>(undefined)
  const [termId, setTermId] = useState('')

  const campuses = useApiResource(() => listCampuses({ orgId: org_id, isActive: true }), [org_id], {
    isEmpty: (d) => d.length === 0,
  })

  const effectiveCampusId = campusId ?? session?.campus_id ?? campuses.data?.[0]?.id
  const numericTerm = termId.trim() === '' ? undefined : Number(termId)

  const report = useApiResource(
    () =>
      getGradeDistribution({
        campusId: effectiveCampusId,
        academicTermId: Number.isFinite(numericTerm) ? numericTerm : undefined,
      }),
    [effectiveCampusId, numericTerm],
    { skip: effectiveCampusId === undefined, isEmpty: () => false }
  )

  const data = report.data
  const letters = Object.entries(data?.letter_distribution ?? {})
  // The tallest bar sets the scale. Guarded against an all-zero set so the
  // chart is never drawn against a zero denominator.
  const maxCount = letters.reduce((m, [, n]) => Math.max(m, n), 0)

  return (
    <DashPageShell
      module="reports"
      title="Grade distribution"
      description="Averages and letter spread for a term, computed by the gradebook's own scale."
    >
      <ReportFilters
        idPrefix="report-grades"
        campuses={campuses.data ?? []}
        campusId={effectiveCampusId}
        onCampusChange={setCampusId}
        academicTermId={termId}
        onAcademicTermChange={setTermId}
      />

      <StatGrid
        state={report.status === 'error' ? 'error' : report.status === 'loading' ? 'loading' : 'success'}
        error={report.error}
        onRetry={report.refetch}
        columns={3}
        items={[
          {
            label: 'Average grade',
            value: data ? formatMetric(data.average_percentage) : '—',
            hint: data ? metricHint(data.average_percentage) : undefined,
            icon: Percent,
            tone: data ? metricTone(data.average_percentage) : 'neutral',
          },
          {
            label: 'Average GPA',
            value: data ? formatMetric(data.average_gpa) : '—',
            hint: data ? metricHint(data.average_gpa) : undefined,
            icon: GraduationCap,
            tone: data ? metricTone(data.average_gpa) : 'neutral',
          },
          {
            label: 'Entries counted',
            value: data ? String(data.entries_counted) : '—',
            hint: data?.source_module,
            tone: 'neutral',
          },
        ]}
      />

      <SectionCard
        title="Letter distribution"
        description="How many student-assessments landed on each grade."
        state={report.status === 'loading' ? 'loading' : 'success'}
      >
        {letters.length === 0 || maxCount === 0 ? (
          // An empty distribution is stated, never drawn as a row of flat bars
          // at zero — a chart of zeros reads as "everyone failed".
          <EmptyState
            title="Nothing graded yet"
            description={
              data?.average_percentage.no_data_reason ??
              'No marks have been entered for this term, so there is no distribution to show.'
            }
          />
        ) : (
          <ul className="flex flex-col gap-2">
            {letters.map(([letter, count]) => (
              <li key={letter} className="flex items-center gap-3">
                <span className="w-8 shrink-0 text-sm font-semibold text-gray-700">{letter}</span>
                <div className="h-2 flex-1 overflow-hidden rounded-full bg-gray-100">
                  <div
                    className="h-full rounded-full bg-gray-800"
                    style={{ width: `${Math.round((count / maxCount) * 100)}%` }}
                  />
                </div>
                <span className="w-10 shrink-0 text-right text-sm tabular-nums text-gray-600">
                  {count}
                </span>
              </li>
            ))}
          </ul>
        )}
      </SectionCard>
    </DashPageShell>
  )
}
