'use client'

/**
 * Report cards for one section/term: generate a draft, review, send, download.
 *
 * `GET /report-card/student/{id}` now returns `report_card_id` and
 * `report_card_status` for the row it upserts, so the panel resolves the REAL
 * state of every student's card on load -- including one sent in an earlier
 * session, which previously displayed as "not generated yet" because the only
 * source of an id was the draft POST response.
 *
 * Status values are LOWERCASE on the wire ("draft"/"sent"). This component
 * previously compared against 'DRAFT'/'SENT', which could never match, so
 * neither the Send nor the PDF button ever rendered.
 *
 * The PDF is fetched as an authenticated blob (see `downloadReportCardPdf`)
 * because a bare link cannot carry the bearer token.
 */

import { useEffect, useState } from 'react'
import toast from 'react-hot-toast'
import { FileText, ScrollText, Send } from 'lucide-react'
import { DataTable, EmptyState, LH_PRIMARY_BUTTON, LH_SECONDARY_BUTTON, SectionCard, StatusChip } from '@/components/widgets'
import { ApiError } from '@/lib/api/api-client'
import { useApiResource } from '@/lib/api/useApiResource'
import { listSectionEnrollments } from '@/modules/sms/campus/api'
import {
  downloadReportCardPdf,
  generateReportCardDraft,
  getStudentReportCard,
  sendReportCard,
} from '../api'
import type { ReportCardStatus, TermReportCardRecordRead } from '../types'

export interface ReportCardPanelProps {
  sectionId: number
  academicTermId?: number
}

/** What the panel knows about one student's card: either the full persisted
 *  record, or just the id/status resolved from the report-card endpoint. */
interface CardState {
  id: number
  status: ReportCardStatus
  /** Null when the student has no graded coursework — not 0.0, not "F". */
  cumulative_gpa?: number | null
  overall_letter_grade?: string | null
}

function toCardState(record: TermReportCardRecordRead): CardState {
  return {
    id: record.id,
    status: record.status,
    cumulative_gpa: record.cumulative_gpa,
    overall_letter_grade: record.overall_letter_grade,
  }
}

export function ReportCardPanel({ sectionId, academicTermId }: ReportCardPanelProps) {
  const enrollments = useApiResource(() => listSectionEnrollments(sectionId, 'active'), [sectionId], {
    isEmpty: (d) => d.length === 0,
  })

  /** student_id -> that student's card state, resolved on load or after an action. */
  const [records, setRecords] = useState<Record<number, CardState>>({})
  const [busy, setBusy] = useState<number | null>(null)
  const [resolving, setResolving] = useState(false)

  const students = enrollments.data ?? []
  const canAct = academicTermId !== undefined

  // Resolve the real state of each student's card, so one generated in an
  // earlier session shows as Draft/Sent with a working Send or PDF button
  // instead of "Not generated yet".
  useEffect(() => {
    if (!canAct || students.length === 0) return
    let cancelled = false
    setResolving(true)
    Promise.all(
      students.map((s) =>
        getStudentReportCard(s.student_id, sectionId, academicTermId as number)
          .then((r) =>
            r.report_card_id != null && r.report_card_status != null
              ? ([s.student_id, {
                  id: r.report_card_id,
                  status: r.report_card_status,
                  cumulative_gpa: r.cumulative_gpa,
                  overall_letter_grade: r.overall_letter_grade,
                }] as const)
              : null
          )
          // A student with no computable card simply has none — not an error
          // worth interrupting the whole table for.
          .catch(() => null)
      )
    ).then((pairs) => {
      if (cancelled) return
      const next: Record<number, CardState> = {}
      for (const pair of pairs) if (pair) next[pair[0]] = pair[1]
      setRecords((prev) => ({ ...next, ...prev }))
      setResolving(false)
    })
    return () => {
      cancelled = true
    }
  }, [students, sectionId, academicTermId, canAct])

  function describe(err: unknown, fallback: string): string {
    if (err instanceof ApiError) {
      if (err.kind === 'permission_denied') return 'Only teachers or school admins can do that.'
      return err.message || fallback
    }
    return err instanceof Error ? err.message : fallback
  }

  async function handleGenerate(studentId: number) {
    if (!canAct) return
    setBusy(studentId)
    try {
      const record = await generateReportCardDraft(studentId, {
        section_id: sectionId,
        academic_term_id: academicTermId,
        generate_narrative: true,
      })
      setRecords((prev) => ({ ...prev, [studentId]: toCardState(record) }))
      toast.success('Draft report card generated.')
    } catch (err) {
      toast.error(describe(err, 'Could not generate the draft.'))
    } finally {
      setBusy(null)
    }
  }

  async function handleSend(studentId: number) {
    const record = records[studentId]
    if (!record) return
    setBusy(studentId)
    try {
      const updated = await sendReportCard(record.id)
      setRecords((prev) => ({ ...prev, [studentId]: toCardState(updated) }))
      toast.success('Report card sent.')
    } catch (err) {
      // 409 means it was already sent -- reflect that rather than leaving the
      // row looking like the action simply failed.
      toast.error(describe(err, 'Could not send the report card.'))
    } finally {
      setBusy(null)
    }
  }

  async function handleDownload(studentId: number) {
    const record = records[studentId]
    if (!record) return
    setBusy(studentId)
    try {
      await downloadReportCardPdf(record.id, `report-card-student-${studentId}.pdf`)
    } catch (err) {
      toast.error(describe(err, 'Could not download the PDF.'))
    } finally {
      setBusy(null)
    }
  }

  return (
    <SectionCard
      id="report-cards"
      title="Report Cards"
      description="Generate a draft from the marks entered above, then send it."
      icon={<ScrollText className="size-4 text-gray-500" />}
      state={enrollments.status === 'empty' ? 'empty' : enrollments.status}
      error={enrollments.error}
      onRetry={enrollments.refetch}
      emptyTitle="No students enrolled in this section"
      emptyDescription="Enrol students before generating report cards."
    >
      {!canAct ? (
        <EmptyState
          title="No academic term selected"
          description="A report card is scoped to a term. Pick one above, or create a term for this campus."
        />
      ) : (
        <div className="space-y-3">
          <DataTable
            rows={students}
            rowKey={(row) => row.id}
            state="success"
            columns={[
              {
                key: 'student',
                header: 'Student',
                render: (r) => (
                  <span>
                    Student #{r.student_id}
                    <span className="ms-1 text-xs text-gray-400">(Roll {r.roll_number ?? '—'})</span>
                  </span>
                ),
              },
              {
                key: 'status',
                header: 'Status',
                render: (r) => {
                  const rec = records[r.student_id]
                  if (!rec) return <span className="text-xs text-gray-400">Not generated yet</span>
                  return rec.status === 'sent' ? (
                    <StatusChip label="Sent" tone="positive" />
                  ) : (
                    <StatusChip label="Draft" tone="caution" />
                  )
                },
              },
              {
                key: 'gpa',
                header: 'GPA',
                align: 'right',
                render: (r) => {
                  const rec = records[r.student_id]
                  return rec?.cumulative_gpa != null ? rec.cumulative_gpa.toFixed(2) : '—'
                },
              },
              {
                key: 'grade',
                header: 'Grade',
                render: (r) => records[r.student_id]?.overall_letter_grade ?? '—',
              },
              {
                key: 'actions',
                header: '',
                align: 'right',
                render: (r) => {
                  const rec = records[r.student_id]
                  const isBusy = busy === r.student_id
                  return (
                    <div className="flex items-center justify-end gap-2">
                      <button
                        type="button"
                        className={LH_SECONDARY_BUTTON}
                        disabled={isBusy}
                        onClick={() => handleGenerate(r.student_id)}
                      >
                        <span>{rec ? 'Refresh draft' : 'Generate draft'}</span>
                      </button>
                      {rec && rec.status === 'draft' && (
                        <button
                          type="button"
                          className={LH_PRIMARY_BUTTON}
                          disabled={isBusy}
                          onClick={() => handleSend(r.student_id)}
                        >
                          <Send className="size-3.5" /> <span>Send</span>
                        </button>
                      )}
                      {rec && rec.status === 'sent' && (
                        <button
                          type="button"
                          className={LH_SECONDARY_BUTTON}
                          disabled={isBusy}
                          onClick={() => handleDownload(r.student_id)}
                        >
                          <FileText className="size-3.5" /> <span>PDF</span>
                        </button>
                      )}
                    </div>
                  )
                },
              },
            ]}
          />

          <p className="px-1 text-xs text-gray-400">
            {resolving
              ? 'Checking which report cards already exist…'
              : 'Existing report cards are resolved automatically, including ones sent in an earlier session.'}
          </p>
        </div>
      )}
    </SectionCard>
  )
}
