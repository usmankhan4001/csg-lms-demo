'use client'

/**
 * The append-only audit trail for one mark.
 *
 * Answers the question a head of department actually asks: "this was 72 last
 * week, who changed it to 41, and why?". Until the trail existed, a corrected
 * mark overwrote its predecessor and the previous value was gone — so a grade
 * dispute had no evidence on either side.
 *
 * A `created` row carries `previous_raw_score: null`, which is deliberately
 * distinct from a previous score of 0.0 — one means "there was no mark before
 * this", the other means "somebody scored zero". Those must never render the
 * same, which is why `describeGradeChange` branches on the action rather than
 * formatting a number.
 */

import { History } from 'lucide-react'
import { EmptyState, SchoolDialog, StatusChip } from '@/components/widgets'
import { useApiResource } from '@/lib/api/useApiResource'
import { getGradeHistory } from '../api'
import { describeGradeChange, formatTimestamp } from '../presentation'

export interface GradeHistoryDialogProps {
  entryId: number
  /** Shown in the dialog title so the reader knows whose mark this is. */
  studentLabel: string
  assessmentName: string
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function GradeHistoryDialog({
  entryId,
  studentLabel,
  assessmentName,
  open,
  onOpenChange,
}: GradeHistoryDialogProps) {
  const history = useApiResource(() => getGradeHistory(entryId), [entryId], {
    skip: !open,
    isEmpty: (d) => d.events.length === 0,
  })

  const events = history.data?.events ?? []

  return (
    <SchoolDialog
      open={open}
      onOpenChange={onOpenChange}
      title="Mark history"
      description={`Every change to ${studentLabel}'s ${assessmentName} mark, oldest first.`}
    >
      {history.status === 'loading' ? (
        <p className="text-sm text-gray-400">Loading history…</p>
      ) : history.error ? (
        <p className="text-sm text-rose-600">
          Could not load the history for this mark. {history.error.message}
        </p>
      ) : events.length === 0 ? (
        <EmptyState
          title="No history"
          description="This mark has no recorded changes yet."
        />
      ) : (
        <ol className="flex flex-col gap-3">
          {events.map((e) => (
            <li
              key={e.id}
              className="flex flex-col gap-1 border-s-2 border-gray-200 ps-3"
            >
              <div className="flex flex-wrap items-center gap-2">
                <StatusChip
                  label={e.action === 'created' ? 'First entry' : 'Changed'}
                  tone={e.action === 'created' ? 'info' : 'caution'}
                  icon={History}
                />
                <span className="text-xs text-gray-500">{formatTimestamp(e.created_at)}</span>
              </div>

              <p className="text-sm text-gray-900">
                {describeGradeChange(e.action, e.previous_raw_score, e.new_raw_score, e.max_score)}
              </p>

              {(e.previous_letter_grade || e.new_letter_grade) && (
                <p className="text-xs text-gray-500">
                  {e.previous_letter_grade
                    ? `${e.previous_letter_grade} → ${e.new_letter_grade ?? '—'}`
                    : `Grade: ${e.new_letter_grade ?? '—'}`}
                </p>
              )}

              <p className="text-xs text-gray-500">
                {e.changed_by_user_id != null
                  ? `By user #${e.changed_by_user_id}`
                  : 'Author not recorded'}
                {e.reason ? ` — ${e.reason}` : ''}
              </p>
            </li>
          ))}
        </ol>
      )}
    </SchoolDialog>
  )
}
