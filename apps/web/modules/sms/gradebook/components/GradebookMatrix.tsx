'use client'

/**
 * Spreadsheet-style grade entry for one section: rows = enrolled students,
 * columns = assessment plans, editable score cells, with a running weighted
 * percentage and letter grade recomputed live as the teacher types.
 *
 * Saved marks ARE pre-loaded, via `GET /sms/gradebook/entries` -- a teacher who
 * enters marks, leaves and comes back sees their work. An empty cell therefore
 * means genuinely unmarked, NOT "saved but unreadable". That endpoint returns
 * only entries that exist, so a student with no mark stays visibly blank rather
 * than being zero-filled: on a report card those mean opposite things.
 *
 * One real backend limitation remains, surfaced honestly rather than papered
 * over: `StudentEnrollmentRead` carries `student_id`/`roll_number` only, with
 * no joined display name (the same constraint `RollCallRoster.tsx` documents),
 * so students are labelled "Student #<id>".
 *
 * The live weighted %/letter shown while typing is a CLIENT-SIDE PREVIEW that
 * deliberately mirrors the server formula in `sms_gradebook.py`
 * (`pct = raw / max * 100`, `weighted = pct * weight_percentage / 100`) and
 * maps to a letter using the real default grading scale fetched from
 * `GET /sms/gradebook/scales`. After a save, the server's own returned
 * `letter_grade`/`weighted_score` replace the preview for those cells.
 */

import { useEffect, useMemo, useState } from 'react'
import toast from 'react-hot-toast'
import { GraduationCap, History, Save } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { EmptyState, SectionCard, StatusChip } from '@/components/widgets'
import { useApiResource } from '@/lib/api/useApiResource'
import { listSectionEnrollments } from '@/modules/sms/campus/api'
import { useStudentNames } from '@/modules/sms/attendance/useStudentNames'
import { GradeHistoryDialog } from './GradeHistoryDialog'
import { studentLabel } from '../presentation'
import { DataExportToolbar } from '@/components/ems/DataExportToolbar'
import type { ExportColumn } from '@/lib/export/data-export'
import {
  batchEnterGrades,
  listAssessmentPlans,
  listGradingScales,
  listSectionGradebookEntries,
} from '../api'
import type { AssessmentPlanRead, GradebookEntryRead, GradeInterval } from '../types'

export interface GradebookMatrixProps {
  sectionId: number
  courseId?: number
  academicTermId?: number
  /** Learnhouse user id of the teacher entering marks, recorded as `graded_by`. */
  gradedBy?: number
  /** Campus the section belongs to — needed to resolve student display names,
   *  which the enrolment payload does not carry. */
  campusId?: number
}

/** Mirrors the server's `resolve_letter_and_gpa` using the real grading scale. */
function resolveLetter(pct: number, intervals: GradeInterval[]): GradeInterval | null {
  return intervals.find((i) => pct >= i.min_percentage && pct <= i.max_percentage) ?? null
}

export function GradebookMatrix({ sectionId, courseId, academicTermId, gradedBy, campusId }: GradebookMatrixProps) {
  const enrollments = useApiResource(() => listSectionEnrollments(sectionId, 'active'), [sectionId])
  const plans = useApiResource(
    () => listAssessmentPlans({ courseId, academicTermId }),
    [courseId, academicTermId]
  )
  const scales = useApiResource(() => listGradingScales(), [])
  const savedEntries = useApiResource(
    () => listSectionGradebookEntries({ sectionId, academicTermId }),
    [sectionId, academicTermId]
  )

  // scores[studentId][planId] = raw string as typed (kept as string so a
  // half-typed value isn't coerced to 0 mid-keystroke).
  const [scores, setScores] = useState<Record<number, Record<number, string>>>({})
  const [saved, setSaved] = useState<Record<number, GradebookEntryRead>>({})
  const [saving, setSaving] = useState(false)
  // Cells the teacher has touched this session. Pre-loading must never
  // overwrite in-progress typing, so a refetch reseeds only untouched cells.
  const [dirty, setDirty] = useState<Record<string, true>>({})
  // Which mark's audit trail is open, if any.
  const [historyFor, setHistoryFor] = useState<
    { entryId: number; student: string; assessment: string } | null
  >(null)

  const names = useStudentNames(campusId)

  // Seed the grid from marks already saved on the server. Without this the
  // teacher sees a blank grid after navigating back and cannot tell whether
  // their entry saved.
  useEffect(() => {
    const list = savedEntries.data?.entries
    if (!list) return
    setScores((prev) => {
      const next = { ...prev }
      for (const entry of list) {
        if (dirty[`${entry.student_id}:${entry.assessment_plan_id}`]) continue
        next[entry.student_id] = {
          ...(next[entry.student_id] ?? {}),
          [entry.assessment_plan_id]: String(entry.raw_score),
        }
      }
      return next
    })
    setSaved((prev) => {
      const next = { ...prev }
      for (const entry of list) next[entry.student_id] = entry
      return next
    })
  }, [savedEntries.data, dirty])

  const intervals = useMemo(() => {
    const list = scales.data ?? []
    const scale = list.find((s) => s.is_default) ?? list[0]
    return scale?.intervals ?? []
  }, [scales.data])

  const students = enrollments.data ?? []
  const planList: AssessmentPlanRead[] = useMemo(
    () => (plans.data ?? []).filter((p) => p.section_id == null || p.section_id === sectionId),
    [plans.data, sectionId]
  )

  /**
   * Arrow/Enter navigation across the grid.
   *
   * Mark entry is a keyboard task: a teacher entering a column of 28 marks
   * should never reach for the mouse. Tab alone walks ACROSS a row, which is
   * the wrong axis — marks are entered one assessment at a time, down the
   * class list. Enter and ArrowDown move to the next student in the same
   * column; ArrowUp goes back; ArrowLeft/Right move between assessments.
   *
   * Cells are addressed by a data attribute rather than refs so the lookup
   * survives re-renders and row reordering.
   */
  function focusCell(rowIndex: number, colIndex: number) {
    const el = document.querySelector<HTMLInputElement>(
      `[data-grade-cell="${rowIndex}:${colIndex}"]`
    )
    if (el) {
      el.focus()
      el.select()
    }
  }

  function handleCellKeyDown(
    e: React.KeyboardEvent<HTMLInputElement>,
    rowIndex: number,
    colIndex: number
  ) {
    // Let the browser handle text editing keys and modified combinations.
    if (e.altKey || e.ctrlKey || e.metaKey) return

    switch (e.key) {
      case 'Enter':
      case 'ArrowDown':
        e.preventDefault()
        focusCell(rowIndex + 1, colIndex)
        break
      case 'ArrowUp':
        e.preventDefault()
        focusCell(rowIndex - 1, colIndex)
        break
      case 'ArrowLeft':
        // Only jump cells when the caret is already at the start, so arrowing
        // within a half-typed number still works.
        if (e.currentTarget.selectionStart === 0) {
          e.preventDefault()
          focusCell(rowIndex, colIndex - 1)
        }
        break
      case 'ArrowRight':
        if (e.currentTarget.selectionStart === e.currentTarget.value.length) {
          e.preventDefault()
          focusCell(rowIndex, colIndex + 1)
        }
        break
      default:
        break
    }
  }

  function setScore(studentId: number, planId: number, value: string) {
    setScores((prev) => ({ ...prev, [studentId]: { ...(prev[studentId] ?? {}), [planId]: value } }))
    setDirty((prev) => ({ ...prev, [`${studentId}:${planId}`]: true }))
  }

  /** Live preview: total weighted % across every plan the teacher has filled in. */
  function weightedTotal(studentId: number): number | null {
    const row = scores[studentId]
    if (!row) return null
    let total = 0
    let any = false
    for (const plan of planList) {
      const raw = Number(row[plan.id])
      if (row[plan.id] === undefined || row[plan.id] === '' || Number.isNaN(raw)) continue
      if (plan.max_score <= 0) continue
      total += ((raw / plan.max_score) * 100 * plan.weight_percentage) / 100
      any = true
    }
    return any ? total : null
  }

  function isOverMax(planId: number, value: string): boolean {
    const plan = planList.find((p) => p.id === planId)
    if (!plan || value === '' || value === undefined) return false
    const raw = Number(value)
    return !Number.isNaN(raw) && raw > plan.max_score
  }

  const hasInvalid = useMemo(
    () =>
      Object.entries(scores).some(([, row]) =>
        Object.entries(row).some(([planId, v]) => isOverMax(Number(planId), v))
      ),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [scores, planList]
  )

  const dirtyCount = Object.keys(dirty).length

  async function handleSave() {
    // The API batches per assessment plan, so one request per plan that has
    // at least one entered score.
    const byPlan = planList
      .map((plan) => ({
        plan,
        entries: students
          .map((s) => ({ student_id: s.student_id, raw: scores[s.student_id]?.[plan.id] }))
          .filter((e) => e.raw !== undefined && e.raw !== '' && !Number.isNaN(Number(e.raw)))
          .map((e) => ({ student_id: e.student_id, raw_score: Number(e.raw) })),
      }))
      .filter((g) => g.entries.length > 0)

    if (byPlan.length === 0) {
      toast.error('Enter at least one score before saving.')
      return
    }

    setSaving(true)
    try {
      const results = await Promise.all(
        byPlan.map((g) =>
          batchEnterGrades({
            assessment_plan_id: g.plan.id,
            entries: g.entries,
            graded_by: gradedBy,
          })
        )
      )
      const next: Record<number, GradebookEntryRead> = {}
      for (const list of results) {
        for (const entry of list) next[entry.student_id] = entry
      }
      setSaved((prev) => ({ ...prev, ...next }))
      // Saved marks are now the server's, not local edits -- clear the dirty
      // marks so a refetch can legitimately reseed these cells.
      setDirty({})
      savedEntries.refetch()
      const count = results.reduce((n, r) => n + r.length, 0)
      toast.success(`Saved ${count} grade${count === 1 ? '' : 's'}.`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Could not save grades.')
    } finally {
      setSaving(false)
    }
  }

  const exportColumns: ExportColumn[] = useMemo(() => {
    const cols: ExportColumn[] = [
      { key: 'student_id', label: 'Student ID', type: 'number' },
      { key: 'student_name', label: 'Student Name', type: 'text' },
      { key: 'roll_number', label: 'Roll Number', type: 'text' },
    ]
    for (const plan of planList) {
      cols.push({
        key: `plan_${plan.id}`,
        label: `${plan.assessment_name} (${plan.weight_percentage}%)`,
        type: 'number',
      })
    }
    cols.push(
      { key: 'weighted_total', label: 'Weighted %', type: 'percentage' },
      { key: 'letter_grade', label: 'Grade', type: 'text' }
    )
    return cols
  }, [planList])

  const exportRows = useMemo(() => {
    return students.map((s) => {
      const total = weightedTotal(s.student_id)
      const serverEntry = saved[s.student_id]
      const preview = total !== null ? resolveLetter(total, intervals) : null
      const label = studentLabel(s.student_id, names.names)
      const row: Record<string, any> = {
        id: s.student_id,
        student_id: s.student_id,
        student_name: label,
        roll_number: s.roll_number ?? '—',
        weighted_total: total,
        letter_grade: serverEntry?.letter_grade ?? preview?.grade ?? '—',
      }
      for (const p of planList) {
        const val = scores[s.student_id]?.[p.id]
        row[`plan_${p.id}`] = val !== undefined && val !== '' ? Number(val) : ''
      }
      return row
    })
  }, [students, scores, saved, intervals, names.names, planList])

  const combinedStatus =
    enrollments.status === 'error' || plans.status === 'error'
      ? 'error'
      : enrollments.status === 'loading' || plans.status === 'loading'
        ? 'loading'
        : 'success'

  return (
    <SectionCard
      id="gradebook-matrix"
      title="Gradebook"
      description={`Section #${sectionId}`}
      icon={<GraduationCap className="size-4 text-muted-foreground" />}
      action={
        <div className="flex items-center gap-2">
          {students.length > 0 && (
            <DataExportToolbar
              data={exportRows}
              columns={exportColumns}
              filenamePrefix={`gradebook_section_${sectionId}`}
              title={`Gradebook Matrix - Section #${sectionId}`}
              activeFilters={{ sectionId, courseId, academicTermId }}
            />
          )}
          {dirtyCount > 0 && (
            <Button
              size="sm"
              disabled={saving || hasInvalid}
              onClick={handleSave}
              className="gap-1.5"
            >
              <Save className="size-3.5" />
              {saving ? 'Saving...' : `Save ${dirtyCount} mark${dirtyCount === 1 ? '' : 's'}`}
            </Button>
          )}
        </div>
      }
      state={combinedStatus}
      error={enrollments.error ?? plans.error}
      onRetry={() => {
        enrollments.refetch()
        plans.refetch()
      }}
      bodyClassName="p-0"
    >
      {students.length === 0 ? (
        <EmptyState
          title="No students enrolled in this section"
          description="Enroll students in this section to enter grades."
        />
      ) : planList.length === 0 ? (
        <EmptyState
          title="No assessment plans yet"
          description="Create an assessment plan (with its weighting) before entering marks."
        />
      ) : (
        <div className="space-y-3">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-muted/50">
                <tr>
                  <th className="px-3 py-2 text-start font-medium text-muted-foreground">Student</th>
                  {planList.map((p) => (
                    <th key={p.id} className="px-3 py-2 text-center font-medium text-muted-foreground whitespace-nowrap">
                      <div>{p.assessment_name}</div>
                      <div className="text-[11px] font-normal text-muted-foreground/70">
                        {p.weight_percentage}% · max {p.max_score}
                      </div>
                    </th>
                  ))}
                  <th className="px-3 py-2 text-end font-medium text-muted-foreground">Weighted %</th>
                  <th className="px-3 py-2 text-center font-medium text-muted-foreground">Grade</th>
                </tr>
              </thead>
              <tbody>
                {students.map((s, rowIndex) => {
                  const total = weightedTotal(s.student_id)
                  const serverEntry = saved[s.student_id]
                  const preview = total !== null ? resolveLetter(total, intervals) : null
                  const label = studentLabel(s.student_id, names.names)
                  return (
                    <tr key={s.id} className="border-t border-border">
                      <td className="px-3 py-1.5 whitespace-nowrap">
                        {label}
                        <span className="ms-1 text-xs text-muted-foreground">(Roll {s.roll_number ?? '—'})</span>
                      </td>
                      {planList.map((p, colIndex) => {
                        const value = scores[s.student_id]?.[p.id] ?? ''
                        const invalid = isOverMax(p.id, value)
                        return (
                          <td key={p.id} className="px-2 py-1.5 text-center">
                            <div className="flex items-center justify-center gap-1">
                              <Input
                                type="number"
                                min={0}
                                max={p.max_score}
                                value={value}
                                data-grade-cell={`${rowIndex}:${colIndex}`}
                                onChange={(e) => setScore(s.student_id, p.id, e.target.value)}
                                onKeyDown={(e) => handleCellKeyDown(e, rowIndex, colIndex)}
                                id={`grade-${s.student_id}-${p.id}`}
                                aria-label={`${p.assessment_name} score for ${label}`}
                                aria-invalid={invalid}
                                className={
                                  invalid
                                    ? 'h-8 w-20 text-center border-destructive focus-visible:ring-destructive'
                                    : 'h-8 w-20 text-center'
                                }
                              />
                              {/* The trail only exists once a mark has been saved. */}
                              {serverEntry && serverEntry.assessment_plan_id === p.id && (
                                <button
                                  type="button"
                                  id={`grade-history-${s.student_id}-${p.id}`}
                                  title="Who changed this mark, and when"
                                  aria-label={`Mark history for ${label}, ${p.assessment_name}`}
                                  className="text-muted-foreground hover:text-foreground"
                                  onClick={() =>
                                    setHistoryFor({
                                      entryId: serverEntry.id,
                                      student: label,
                                      assessment: p.assessment_name,
                                    })
                                  }
                                >
                                  <History className="size-3.5" />
                                </button>
                              )}
                            </div>
                          </td>
                        )
                      })}
                      <td className="px-3 py-1.5 text-end tabular-nums">
                        {total !== null ? `${total.toFixed(1)}%` : '—'}
                      </td>
                      <td className="px-3 py-1.5 text-center">
                        {serverEntry?.letter_grade ? (
                          <StatusChip label={serverEntry.letter_grade} tone="info" />
                        ) : preview ? (
                          <span className="text-xs text-muted-foreground">{preview.grade} (preview)</span>
                        ) : (
                          '—'
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          <div className="flex items-center justify-between gap-3 px-4 pb-4">
            <p className="text-xs text-muted-foreground">
              {savedEntries.status === 'loading'
                ? 'Loading saved marks…'
                : `${savedEntries.data?.entries.length ?? 0} saved mark${
                    (savedEntries.data?.entries.length ?? 0) === 1 ? '' : 's'
                  } loaded. A blank cell means not marked yet — which is not the same as a zero.`}
            </p>
            <Button size="sm" onClick={handleSave} disabled={saving || hasInvalid}>
              <Save className="size-4" />
              {saving ? 'Saving…' : 'Save Grades'}
            </Button>
          </div>

          {names.error && (
            <p className="px-4 pb-3 text-xs text-amber-700">
              Student names could not be loaded, so rows show ids. Marks are unaffected.
            </p>
          )}

          <p className="px-4 pb-4 text-xs text-muted-foreground">
            Keyboard: Enter or ↓ moves to the next student in the same column, ↑ goes back, and
            ←/→ move between assessments.
          </p>
        </div>
      )}

      {historyFor && (
        <GradeHistoryDialog
          entryId={historyFor.entryId}
          studentLabel={historyFor.student}
          assessmentName={historyFor.assessment}
          open
          onOpenChange={(open) => {
            if (!open) setHistoryFor(null)
          }}
        />
      )}
    </SectionCard>
  )
}
