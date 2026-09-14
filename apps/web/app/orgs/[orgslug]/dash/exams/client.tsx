'use client'

/**
 * School examinations (M04), attached as a Learnhouse dash module.
 *
 * Scope note on "proctoring": there is none, and this screen does not imply
 * any. Automated remote proctoring (webcam, lockdown, AI cheating detection)
 * is NOT implemented. What the backend records is the administrative trail a
 * physically invigilated exam produces -- room, invigilator, actual start and
 * end times, and incidents an invigilator writes down.
 *
 * Marks shown here are never defaulted. A student who has not been marked is
 * rendered as "Not marked", never as 0 -- this codebase has twice had to tear
 * out endpoints that turned missing academic data into a plausible number.
 */

import { useState } from 'react'
import { ClipboardList, GraduationCap, Users } from 'lucide-react'
import {
  DashPageShell,
  DataTable,
  SectionCard,
  StatGrid,
  StatusChip,
  LH_INPUT,
  LH_PRIMARY_BUTTON,
} from '@/components/widgets'
import { ApiError } from '@/lib/api/api-client'
import { useApiResource } from '@/lib/api/useApiResource'
import { useSchoolSession } from '@/lib/api/useSchoolSession'
import { listCampuses } from '@/modules/sms/campus/api'
import {
  getExamSummary,
  listExamResults,
  listExams,
  postResultsToGradebook,
} from '@/modules/sms/exams/api'
import type { ExamRead, ExamStatus } from '@/modules/sms/exams/types'

interface ExamsDashClientProps {
  org_id: number
  orgslug: string
}

const STATUS_TONE: Record<ExamStatus, 'neutral' | 'positive' | 'caution' | 'critical' | 'info'> = {
  SCHEDULED: 'info',
  IN_PROGRESS: 'caution',
  COMPLETED: 'neutral',
  RESULTS_POSTED: 'positive',
  CANCELLED: 'critical',
}

export default function ExamsDashClient({ org_id }: ExamsDashClientProps) {
  const { session } = useSchoolSession()
  const [campusId, setCampusId] = useState<number | undefined>(undefined)
  const [selectedExamId, setSelectedExamId] = useState<number | undefined>(undefined)
  const [posting, setPosting] = useState(false)
  const [postMessage, setPostMessage] = useState<string | null>(null)
  const [postError, setPostError] = useState<string | null>(null)

  const campuses = useApiResource(() => listCampuses({ orgId: org_id, isActive: true }), [org_id], {
    isEmpty: (d) => d.length === 0,
  })

  const effectiveCampusId = campusId ?? session?.campus_id ?? campuses.data?.[0]?.id

  const exams = useApiResource(
    () => listExams({ campusId: effectiveCampusId }),
    [effectiveCampusId],
    { skip: effectiveCampusId === undefined, isEmpty: (d) => d.length === 0 }
  )

  const examList = exams.data ?? []
  const effectiveExamId = selectedExamId ?? examList[0]?.id
  const selectedExam: ExamRead | undefined = examList.find((e) => e.id === effectiveExamId)

  const results = useApiResource(
    () => listExamResults(effectiveExamId as number),
    [effectiveExamId],
    { skip: effectiveExamId === undefined, isEmpty: (d) => d.length === 0 }
  )

  const summary = useApiResource(
    () => getExamSummary(effectiveExamId as number),
    [effectiveExamId],
    { skip: effectiveExamId === undefined }
  )

  const today = new Date().toISOString().slice(0, 10)
  const upcoming = examList.filter((e) => e.exam_date >= today && e.status !== 'CANCELLED')

  async function handlePostToGradebook() {
    if (effectiveExamId === undefined) return
    setPosting(true)
    setPostMessage(null)
    setPostError(null)
    try {
      const res = await postResultsToGradebook(effectiveExamId)
      setPostMessage(
        `${res.entries_written} result(s) written to the gradebook` +
          (res.entries_skipped > 0
            ? `, ${res.entries_skipped} skipped (unmarked, absent or exempt — deliberately not scored zero).`
            : '.')
      )
      exams.refetch()
      results.refetch()
      summary.refetch()
    } catch (err) {
      setPostError(
        err instanceof ApiError
          ? err.status === 409
            ? 'Results for this exam have already been posted to the gradebook.'
            : err.message
          : 'Could not post results. Try again.'
      )
    } finally {
      setPosting(false)
    }
  }

  const s = summary.data

  return (
    <DashPageShell
      module="exams"
      title="Exams"
      description="Schedule examinations, record marks, and post results into the gradebook."
    >
      <SectionCard
        title="Campus"
        icon={<ClipboardList className="size-4 text-gray-500" />}
        state={campuses.status === 'loading' ? 'loading' : campuses.status}
        error={campuses.error}
        onRetry={campuses.refetch}
        emptyTitle="No campuses set up yet"
        emptyDescription="Create a campus, academic year and term before scheduling exams."
      >
        <div className="flex flex-wrap items-end gap-4">
          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-medium text-gray-500">Campus</span>
            <select
              id="exams-campus"
              className={LH_INPUT}
              value={effectiveCampusId ?? ''}
              onChange={(e) => {
                setCampusId(Number(e.target.value))
                setSelectedExamId(undefined)
              }}
            >
              {(campuses.data ?? []).map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>

          {examList.length > 0 && (
            <label className="flex flex-col gap-1.5">
              <span className="text-xs font-medium text-gray-500">Exam</span>
              <select
                id="exams-exam"
                className={LH_INPUT}
                value={effectiveExamId ?? ''}
                onChange={(e) => setSelectedExamId(Number(e.target.value))}
              >
                {examList.map((e) => (
                  <option key={e.id} value={e.id}>
                    {e.title} — {e.exam_date}
                  </option>
                ))}
              </select>
            </label>
          )}
        </div>
      </SectionCard>

      <StatGrid
        state={exams.status === 'loading' ? 'loading' : 'success'}
        columns={4}
        items={[
          { label: 'Exams', value: examList.length, icon: ClipboardList, tone: 'neutral' },
          { label: 'Upcoming', value: upcoming.length, icon: ClipboardList, tone: 'neutral' },
          {
            label: 'Marked',
            value: s ? `${s.marked} of ${s.total_students}` : '—',
            icon: Users,
            tone: 'neutral',
          },
          {
            // Absence is shown as absence. A cohort with nobody marked has no
            // average, and renders as a dash rather than a fabricated figure.
            label: 'Average mark',
            value: s?.average_marks != null ? s.average_marks.toFixed(1) : '—',
            icon: GraduationCap,
            tone: 'neutral',
            hint: s && s.marked === 0 ? 'No marks entered yet' : undefined,
          },
        ]}
      />

      <SectionCard
        id="schedule"
        title="Examination schedule"
        icon={<ClipboardList className="size-4 text-gray-500" />}
        state={effectiveCampusId === undefined ? 'empty' : exams.status}
        error={exams.error}
        onRetry={exams.refetch}
        emptyTitle="No exams scheduled"
        emptyDescription="Exams scheduled for this campus will appear here."
      >
        <DataTable
          rows={examList}
          rowKey={(row) => row.id}
          state="success"
          totalLabel={`${examList.length} exam${examList.length === 1 ? '' : 's'}`}
          columns={[
            { key: 'title', header: 'Exam', render: (r) => r.title },
            { key: 'type', header: 'Type', render: (r) => r.exam_type ?? '—' },
            { key: 'date', header: 'Date', render: (r) => r.exam_date },
            {
              key: 'time',
              header: 'Time',
              render: (r) => (r.start_time ? `${r.start_time} (${r.duration_minutes}m)` : `${r.duration_minutes}m`),
            },
            { key: 'marks', header: 'Total', align: 'right', render: (r) => r.total_marks },
            { key: 'pass', header: 'Pass', align: 'right', render: (r) => r.pass_marks },
            {
              key: 'status',
              header: 'Status',
              render: (r) => (
                <StatusChip label={r.status.replace(/_/g, ' ')} tone={STATUS_TONE[r.status]} />
              ),
            },
          ]}
        />
      </SectionCard>

      <SectionCard
        id="results"
        title={selectedExam ? `Results — ${selectedExam.title}` : 'Results'}
        description={
          s
            ? `${s.marked} marked · ${s.not_yet_marked} not yet marked · ${s.absent} absent`
            : undefined
        }
        icon={<GraduationCap className="size-4 text-gray-500" />}
        state={effectiveExamId === undefined ? 'empty' : results.status}
        error={results.error}
        onRetry={results.refetch}
        emptyTitle="No results recorded"
        emptyDescription="Marks entered for this exam will appear here."
        action={
          selectedExam && selectedExam.status !== 'RESULTS_POSTED' ? (
            <button
              type="button"
              className={LH_PRIMARY_BUTTON}
              onClick={handlePostToGradebook}
              disabled={posting || selectedExam.assessment_plan_id == null}
              title={
                selectedExam.assessment_plan_id == null
                  ? 'Link this exam to an assessment plan first — it defines how much the exam counts toward the course grade.'
                  : undefined
              }
            >
              <span>{posting ? 'Posting…' : 'Post to gradebook'}</span>
            </button>
          ) : undefined
        }
      >
        <>
          {postMessage && <p className="mb-3 text-sm text-emerald-700">{postMessage}</p>}
          {postError && <p className="mb-3 text-sm text-rose-600">{postError}</p>}
          {selectedExam?.assessment_plan_id == null && (
            <p className="mb-3 text-sm text-gray-500">
              This exam is not linked to an assessment plan, so its marks cannot reach the
              gradebook yet. An assessment plan defines the exam&apos;s weight toward the course
              grade — that has to be a human decision, so it is never guessed.
            </p>
          )}
          <DataTable
            rows={results.data ?? []}
            rowKey={(row) => row.id}
            state="success"
            columns={[
              { key: 'student', header: 'Student', render: (r) => `Student #${r.student_id}` },
              {
                key: 'marks',
                header: 'Marks',
                align: 'right',
                render: (r) =>
                  r.marks_obtained != null ? (
                    r.marks_obtained
                  ) : (
                    <span className="text-gray-400">Not marked</span>
                  ),
              },
              {
                key: 'pct',
                header: 'Percentage',
                align: 'right',
                render: (r) => (r.percentage != null ? `${r.percentage.toFixed(1)}%` : '—'),
              },
              {
                key: 'attendance',
                header: 'Attendance',
                render: (r) => (
                  <StatusChip
                    label={r.attendance_status}
                    tone={
                      r.attendance_status === 'PRESENT'
                        ? 'positive'
                        : r.attendance_status === 'MALPRACTICE'
                          ? 'critical'
                          : 'neutral'
                    }
                  />
                ),
              },
              {
                key: 'posted',
                header: 'In gradebook',
                render: (r) =>
                  r.posted_to_gradebook_at ? (
                    <StatusChip label="Posted" tone="positive" />
                  ) : (
                    <span className="text-gray-400">—</span>
                  ),
              },
            ]}
          />
        </>
      </SectionCard>
    </DashPageShell>
  )
}
