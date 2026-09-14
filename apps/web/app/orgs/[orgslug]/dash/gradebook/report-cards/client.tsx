'use client'

/**
 * Report-card studio — the term-end screen.
 *
 * Report cards are the deliverable a school is judged on, and until now there
 * was no way to run a SECTION through them: a card was reachable one student
 * at a time, and nothing could answer "which cards in this section are still
 * drafts?".
 *
 * The workflow is deliberately three separate steps — draft, review, send —
 * rather than one button. Sending is irreversible and fans out to families, so
 * the review step exists to make the state of every card visible BEFORE
 * anybody commits.
 *
 * THE OUTCOME THAT MATTERS MOST is `drafted_ungraded`: a card that exists but
 * carries no grade, because nothing has been marked for that student. The API
 * returns it as its own outcome precisely so it cannot be mistaken for a
 * success, and this screen keeps that distinction in the tone, the label, the
 * explanation, and a dedicated warning above the send control. Collapsing it
 * into "drafted" would let a teacher send a section believing every card
 * carried a grade.
 */

import { useMemo, useState } from 'react'
import { GraduationCap, FileText, RefreshCw, Send, AlertTriangle } from 'lucide-react'
import {
  DashPageShell,
  DataTable,
  EmptyState,
  SectionCard,
  StatGrid,
  StatusChip,
  LH_PRIMARY_BUTTON,
  LH_SECONDARY_BUTTON,
  LH_INPUT,
} from '@/components/widgets'
import { ApiError } from '@/lib/api/api-client'
import { useApiResource } from '@/lib/api/useApiResource'
import { useSchoolSession } from '@/lib/api/useSchoolSession'
import { listAcademicTerms, listCampuses, listClassSections } from '@/modules/sms/campus/api'
import { useStudentNames } from '@/modules/sms/attendance/useStudentNames'
import {
  batchDraftReportCards,
  batchSendReportCards,
  downloadReportCardPdf,
  listReportCards,
  recalculateReportCards,
} from '@/modules/sms/gradebook/api'
import {
  OUTCOME_EXPLANATION,
  OUTCOME_LABEL,
  OUTCOME_TONE,
  REPORT_CARD_STATUS_LABEL,
  REPORT_CARD_STATUS_TONE,
  formatGpaShort,
  formatLetterGrade,
  formatTimestamp,
  studentLabel,
} from '@/modules/sms/gradebook/presentation'
import type {
  BatchReportCardOutcome,
  TermReportCardRecordRead,
} from '@/modules/sms/gradebook/types'

interface ReportCardStudioClientProps {
  org_id: number
  orgslug: string
}

export default function ReportCardStudioClient({ org_id }: ReportCardStudioClientProps) {
  const { session } = useSchoolSession()
  const [campusId, setCampusId] = useState<number | undefined>(undefined)
  const [sectionId, setSectionId] = useState<number | undefined>(undefined)
  const [termId, setTermId] = useState<number | undefined>(undefined)
  const [generateNarrative, setGenerateNarrative] = useState(false)
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [lastRun, setLastRun] = useState<{ label: string; results: BatchReportCardOutcome[] } | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const campuses = useApiResource(() => listCampuses({ orgId: org_id, isActive: true }), [org_id], {
    isEmpty: (d) => d.length === 0,
  })
  const effectiveCampusId = campusId ?? session?.campus_id ?? campuses.data?.[0]?.id

  const sections = useApiResource(
    () => listClassSections(effectiveCampusId as number, { isActive: true }),
    [effectiveCampusId],
    { skip: effectiveCampusId === undefined, isEmpty: (d) => d.length === 0 }
  )
  const effectiveSectionId = sectionId ?? sections.data?.[0]?.id

  const terms = useApiResource(
    () => listAcademicTerms({ campusId: effectiveCampusId }),
    [effectiveCampusId],
    { skip: effectiveCampusId === undefined, isEmpty: (d) => d.length === 0 }
  )
  const effectiveTermId = termId ?? terms.data?.[0]?.id

  const cards = useApiResource(
    () => listReportCards({ sectionId: effectiveSectionId, academicTermId: effectiveTermId }),
    [effectiveSectionId, effectiveTermId],
    {
      skip: effectiveSectionId === undefined || effectiveTermId === undefined,
      isEmpty: (d) => d.length === 0,
    }
  )

  const names = useStudentNames(effectiveCampusId)

  const rows = cards.data ?? []

  /**
   * An ungraded card is one with no credits and no letter — the persisted
   * shape of `drafted_ungraded`. Counted separately because it is the thing a
   * teacher must see before pressing send.
   */
  const ungraded = useMemo(
    () => rows.filter((r) => r.cumulative_gpa == null || r.total_credits === 0),
    [rows]
  )
  const drafts = useMemo(() => rows.filter((r) => r.status === 'draft'), [rows])
  const sent = useMemo(() => rows.filter((r) => r.status === 'sent'), [rows])

  /** Only drafts are selectable: a sent card cannot be sent again, and
   *  offering it would imply otherwise. */
  const selectableIds = useMemo(() => new Set(drafts.map((d) => d.id)), [drafts])
  const selectedDrafts = useMemo(
    () => [...selected].filter((id) => selectableIds.has(id)),
    [selected, selectableIds]
  )
  const selectedUngraded = useMemo(
    () => ungraded.filter((u) => selected.has(u.id)).length,
    [ungraded, selected]
  )

  function toggle(id: number) {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  function toggleAllDrafts() {
    setSelected((prev) =>
      prev.size >= drafts.length && drafts.length > 0 ? new Set() : new Set(drafts.map((d) => d.id))
    )
  }

  function describeError(err: unknown): string {
    if (err instanceof ApiError) {
      if (err.kind === 'permission_denied') {
        return 'You need teacher or school-admin access to run report cards.'
      }
      return err.message
    }
    return 'Something went wrong. Try again.'
  }

  async function run(
    label: string,
    fn: () => Promise<{ results: BatchReportCardOutcome[] }>
  ) {
    setBusy(label)
    setError(null)
    try {
      const res = await fn()
      setLastRun({ label, results: res.results })
      setSelected(new Set())
      cards.refetch()
    } catch (err) {
      setError(describeError(err))
    } finally {
      setBusy(null)
    }
  }

  const scopeReady = effectiveSectionId !== undefined && effectiveTermId !== undefined

  return (
    <DashPageShell
      module="gradebook"
      title="Report cards"
      description="Draft, review and send a whole section's report cards for a term."
    >
      <SectionCard
        title="Choose a section and term"
        icon={<GraduationCap className="size-4 text-gray-500" />}
        state={campuses.status === 'loading' || sections.status === 'loading' ? 'loading' : campuses.status}
        error={campuses.error ?? sections.error}
        onRetry={campuses.refetch}
        emptyTitle="No campuses set up yet"
        emptyDescription="Add a campus, sections and academic terms before running report cards."
      >
        <div className="flex flex-wrap items-end gap-4">
          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-medium text-gray-500">Campus</span>
            <select
              id="rc-campus"
              className={LH_INPUT}
              value={effectiveCampusId ?? ''}
              onChange={(e) => {
                setCampusId(Number(e.target.value))
                setSectionId(undefined)
                setTermId(undefined)
                setSelected(new Set())
                setLastRun(null)
              }}
            >
              {(campuses.data ?? []).map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>

          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-medium text-gray-500">Section</span>
            <select
              id="rc-section"
              className={LH_INPUT}
              value={effectiveSectionId ?? ''}
              onChange={(e) => {
                setSectionId(Number(e.target.value))
                setSelected(new Set())
                setLastRun(null)
              }}
              disabled={(sections.data ?? []).length === 0}
            >
              {(sections.data ?? []).map((s) => (
                <option key={s.id} value={s.id}>
                  {s.grade_level} — {s.section_name}
                </option>
              ))}
            </select>
          </label>

          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-medium text-gray-500">Term</span>
            <select
              id="rc-term"
              className={LH_INPUT}
              value={effectiveTermId ?? ''}
              onChange={(e) => {
                setTermId(Number(e.target.value))
                setSelected(new Set())
                setLastRun(null)
              }}
              disabled={(terms.data ?? []).length === 0}
            >
              {(terms.data ?? []).map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
          </label>
        </div>

        {(terms.data ?? []).length === 0 && terms.status !== 'loading' && (
          <p className="mt-3 text-sm text-gray-500">
            No academic terms exist for this campus. Report cards are keyed on a term, so one must
            be created first.
          </p>
        )}
      </SectionCard>

      <StatGrid
        state={cards.status === 'loading' ? 'loading' : 'success'}
        columns={4}
        items={[
          { label: 'Cards', value: rows.length, icon: FileText, tone: 'neutral' },
          { label: 'Drafts', value: drafts.length, icon: FileText, tone: 'caution' },
          { label: 'Sent', value: sent.length, icon: Send, tone: 'positive' },
          {
            label: 'Without grades',
            value: ungraded.length,
            icon: AlertTriangle,
            tone: ungraded.length > 0 ? 'caution' : 'neutral',
          },
        ]}
      />

      <SectionCard
        title="Term-end actions"
        icon={<RefreshCw className="size-4 text-gray-500" />}
      >
        {!scopeReady ? (
          <EmptyState
            title="Pick a section and term"
            description="Report cards are generated per section, per term."
          />
        ) : (
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap items-center gap-2">
              <button
                id="rc-draft-all"
                type="button"
                className={LH_PRIMARY_BUTTON}
                disabled={busy !== null}
                onClick={() =>
                  run('draft', () =>
                    batchDraftReportCards({
                      section_id: effectiveSectionId as number,
                      academic_term_id: effectiveTermId as number,
                      generate_narrative: generateNarrative,
                    })
                  )
                }
              >
                <span>{busy === 'draft' ? 'Drafting…' : 'Draft this section'}</span>
              </button>

              <button
                id="rc-recalculate"
                type="button"
                className={LH_SECONDARY_BUTTON}
                disabled={busy !== null}
                onClick={() =>
                  run('recalculate', () =>
                    recalculateReportCards({
                      section_id: effectiveSectionId as number,
                      academic_term_id: effectiveTermId as number,
                    })
                  )
                }
              >
                <RefreshCw className="size-4" />
                <span>{busy === 'recalculate' ? 'Recalculating…' : 'Recalculate drafts'}</span>
              </button>

              <label className="ms-2 flex items-center gap-2 text-sm text-gray-600">
                <input
                  id="rc-narrative"
                  type="checkbox"
                  checked={generateNarrative}
                  onChange={(e) => setGenerateNarrative(e.target.checked)}
                />
                <span>Generate AI narrative</span>
              </label>
            </div>

            <p className="text-xs text-gray-500">
              Recalculating updates drafts only. A card that has already been sent is never
              recomputed — a family has read that document, so changing it underneath them is a
              decision, not a side effect.
            </p>

            {error && <p className="text-sm text-rose-600">{error}</p>}
          </div>
        )}
      </SectionCard>

      {lastRun && (
        <SectionCard
          title={`Last run — ${lastRun.label}`}
          icon={<FileText className="size-4 text-gray-500" />}
        >
          {lastRun.results.length === 0 ? (
            <EmptyState
              title="Nothing to do"
              description="No actively enrolled students matched this section and term."
            />
          ) : (
            <DataTable
              rows={lastRun.results}
              rowKey={(r, i) => `${r.student_id ?? 'x'}-${r.report_card_id ?? i}`}
              state="success"
              totalLabel={`${lastRun.results.length} student${lastRun.results.length === 1 ? '' : 's'}`}
              columns={[
                {
                  key: 'student',
                  header: 'Student',
                  render: (r) =>
                    r.student_id != null ? studentLabel(r.student_id, names.names) : '—',
                },
                {
                  key: 'outcome',
                  header: 'Outcome',
                  render: (r) => (
                    <StatusChip label={OUTCOME_LABEL[r.outcome] ?? r.outcome} tone={OUTCOME_TONE[r.outcome] ?? 'neutral'} />
                  ),
                },
                {
                  key: 'meaning',
                  header: 'What that means',
                  render: (r) => (
                    <span className="text-xs text-gray-500">
                      {r.detail ?? OUTCOME_EXPLANATION[r.outcome] ?? ''}
                    </span>
                  ),
                },
                {
                  key: 'gpa',
                  header: 'GPA',
                  align: 'right',
                  render: (r) =>
                    r.previous_cumulative_gpa != null && r.cumulative_gpa != null
                      ? `${formatGpaShort(r.previous_cumulative_gpa)} → ${formatGpaShort(r.cumulative_gpa)}`
                      : formatGpaShort(r.cumulative_gpa),
                },
              ]}
            />
          )}
        </SectionCard>
      )}

      <SectionCard
        title="Cards in this section"
        icon={<FileText className="size-4 text-gray-500" />}
        state={!scopeReady ? 'empty' : cards.status}
        error={cards.error}
        onRetry={cards.refetch}
        emptyTitle={scopeReady ? 'No report cards yet' : 'Pick a section and term'}
        emptyDescription={
          scopeReady
            ? 'Draft this section to create a card for every actively enrolled student.'
            : 'Report cards are generated per section, per term.'
        }
      >
        <div className="flex flex-col gap-3">
          {names.error && (
            <p className="text-xs text-amber-700">
              Student names could not be loaded, so rows show ids. The cards themselves are
              unaffected.
            </p>
          )}

          {selectedUngraded > 0 && (
            <div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3">
              <AlertTriangle className="mt-0.5 size-4 shrink-0 text-amber-600" />
              <p className="text-sm text-amber-900">
                <strong>
                  {selectedUngraded} selected card{selectedUngraded === 1 ? '' : 's'} carr
                  {selectedUngraded === 1 ? 'ies' : 'y'} no grade.
                </strong>{' '}
                Nothing has been marked for {selectedUngraded === 1 ? 'that student' : 'those students'}, so the
                famil{selectedUngraded === 1 ? 'y' : 'ies'} would receive a blank report. Enter their
                marks first, or deselect them.
              </p>
            </div>
          )}

          <div className="flex flex-wrap items-center gap-2">
            <button
              id="rc-select-all"
              type="button"
              className={LH_SECONDARY_BUTTON}
              disabled={drafts.length === 0}
              onClick={toggleAllDrafts}
            >
              <span>{selected.size >= drafts.length && drafts.length > 0 ? 'Clear selection' : 'Select all drafts'}</span>
            </button>

            <button
              id="rc-send"
              type="button"
              className={LH_PRIMARY_BUTTON}
              disabled={busy !== null || selectedDrafts.length === 0}
              onClick={() =>
                run('send', () => batchSendReportCards({ report_card_ids: selectedDrafts }))
              }
            >
              <Send className="size-4" />
              <span>
                {busy === 'send'
                  ? 'Sending…'
                  : `Send ${selectedDrafts.length} selected`}
              </span>
            </button>

            <span className="text-xs text-gray-500">
              Sending is irreversible — a report card cannot be recalled once a family has it.
            </span>
          </div>

          <DataTable
            rows={rows}
            rowKey={(row) => row.id}
            state="success"
            totalLabel={`${rows.length} card${rows.length === 1 ? '' : 's'}`}
            columns={[
              {
                key: 'select',
                header: '',
                render: (r: TermReportCardRecordRead) =>
                  r.status === 'draft' ? (
                    <input
                      id={`rc-pick-${r.id}`}
                      type="checkbox"
                      checked={selected.has(r.id)}
                      onChange={() => toggle(r.id)}
                      aria-label={`Select report card for ${studentLabel(r.student_id, names.names)}`}
                    />
                  ) : null,
              },
              {
                key: 'student',
                header: 'Student',
                render: (r) => studentLabel(r.student_id, names.names),
              },
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
                key: 'sent_at',
                header: 'Sent',
                render: (r) => (r.status === 'sent' ? formatTimestamp(r.sent_at) : '—'),
              },
              {
                key: 'pdf',
                header: '',
                render: (r) =>
                  r.status === 'sent' ? (
                    <button
                      id={`rc-pdf-${r.id}`}
                      type="button"
                      className="text-xs text-gray-600 underline hover:text-gray-900"
                      onClick={() => {
                        downloadReportCardPdf(r.id).catch((err) => setError(describeError(err)))
                      }}
                    >
                      PDF
                    </button>
                  ) : (
                    <span className="text-xs text-gray-400" title="A draft has no PDF until it is sent">
                      —
                    </span>
                  ),
              },
            ]}
          />
        </div>
      </SectionCard>
    </DashPageShell>
  )
}
