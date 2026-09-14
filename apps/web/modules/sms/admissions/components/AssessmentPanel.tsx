'use client'

/**
 * Admission assessments — schedule one, record its result.
 *
 * The score field disappears entirely for a NOT_ATTENDED outcome. A candidate
 * who never sat the paper did not score zero on it, and the backend refuses
 * to store a score for that outcome; showing the input would invite a
 * fabricated academic record and then fail the request anyway.
 */

import { useState } from 'react'
import { ClipboardList } from 'lucide-react'
import {
  DataTable,
  EmptyState,
  LH_INPUT,
  LH_PRIMARY_BUTTON,
  LH_SECONDARY_BUTTON,
  SchoolDialog,
  SchoolField,
  SectionCard,
  StatusChip,
} from '@/components/widgets'
import { ApiError } from '@/lib/api/api-client'
import { recordAssessmentResult, scheduleAssessment } from '../api'
import { OUTCOME_LABEL, OUTCOME_TONE, formatDateTime, formatScore } from '../presentation'
import type { AssessmentOutcome, AssessmentRead } from '../types'

interface Props {
  applicationId: number
  assessments: AssessmentRead[]
  onChanged: () => void
}

export function AssessmentPanel({ applicationId, assessments, onChanged }: Props) {
  const [scheduling, setScheduling] = useState(false)
  const [recording, setRecording] = useState<AssessmentRead | null>(null)

  return (
    <SectionCard
      id="assessments"
      title="Assessment"
      description="Entrance assessments scheduled for this applicant, and their results."
      icon={<ClipboardList className="size-4 text-gray-500" />}
      action={
        <button
          type="button"
          id="schedule-assessment-button"
          className={LH_SECONDARY_BUTTON}
          onClick={() => setScheduling(true)}
        >
          <span>Schedule assessment</span>
        </button>
      }
    >
      {assessments.length === 0 ? (
        <EmptyState
          title="No assessment recorded"
          description="This applicant has not been assessed. That is different from having failed — nothing has been scheduled yet."
        />
      ) : (
        <DataTable
          rows={assessments}
          rowKey={(r) => r.id}
          state="success"
          columns={[
            { key: 'name', header: 'Assessment', render: (r) => r.assessment_name },
            {
              key: 'scheduled',
              header: 'Scheduled',
              render: (r) => (
                <span className="text-xs text-gray-600">{formatDateTime(r.scheduled_for)}</span>
              ),
            },
            {
              key: 'venue',
              header: 'Venue',
              render: (r) => r.venue ?? <span className="text-xs text-gray-400">Not set</span>,
            },
            {
              key: 'outcome',
              header: 'Outcome',
              render: (r) =>
                r.outcome ? (
                  <StatusChip label={OUTCOME_LABEL[r.outcome]} tone={OUTCOME_TONE[r.outcome]} />
                ) : (
                  <span className="text-xs text-gray-400">Not recorded</span>
                ),
            },
            {
              key: 'score',
              header: 'Score',
              align: 'right',
              render: (r) => <span className="text-sm">{formatScore(r)}</span>,
            },
            {
              key: 'actions',
              header: '',
              align: 'right',
              render: (r) => (
                <button
                  type="button"
                  id={`assessment-result-${r.id}`}
                  className={LH_SECONDARY_BUTTON}
                  onClick={() => setRecording(r)}
                >
                  <span>{r.outcome ? 'Amend result' : 'Record result'}</span>
                </button>
              ),
            },
          ]}
        />
      )}

      {scheduling && (
        <ScheduleDialog
          applicationId={applicationId}
          onClose={() => setScheduling(false)}
          onDone={() => {
            setScheduling(false)
            onChanged()
          }}
        />
      )}

      {recording && (
        <ResultDialog
          assessment={recording}
          onClose={() => setRecording(null)}
          onDone={() => {
            setRecording(null)
            onChanged()
          }}
        />
      )}
    </SectionCard>
  )
}

function ScheduleDialog({
  applicationId,
  onClose,
  onDone,
}: {
  applicationId: number
  onClose: () => void
  onDone: () => void
}) {
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const form = new FormData(e.currentTarget)
    const name = String(form.get('assessment_name') ?? '').trim()
    if (!name) {
      setError('Give the assessment a name.')
      return
    }
    const when = String(form.get('scheduled_for') ?? '').trim()

    setSaving(true)
    setError(null)
    try {
      await scheduleAssessment(applicationId, {
        assessment_name: name,
        // datetime-local has no timezone; sending it as-is matches what the
        // school typed rather than silently shifting it.
        scheduled_for: when || null,
        venue: String(form.get('venue') ?? '').trim() || null,
      })
      onDone()
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.kind === 'permission_denied'
            ? 'You need admissions access to schedule an assessment.'
            : err.message
          : 'Could not schedule that assessment.'
      )
    } finally {
      setSaving(false)
    }
  }

  return (
    <SchoolDialog
      open
      onOpenChange={(o) => !o && onClose()}
      title="Schedule an assessment"
      description="Set when and where this applicant will be assessed."
      onSubmit={handleSubmit}
      footer={
        <button type="submit" disabled={saving} className={LH_PRIMARY_BUTTON}>
          <span>{saving ? 'Scheduling…' : 'Schedule'}</span>
        </button>
      }
    >
      <SchoolField id="assessment-name" label="Assessment name" required>
        <input
          id="assessment-name"
          name="assessment_name"
          className={LH_INPUT}
          placeholder="Grade 9 entrance paper"
        />
      </SchoolField>
      <SchoolField id="assessment-when" label="Scheduled for">
        <input id="assessment-when" name="scheduled_for" type="datetime-local" className={LH_INPUT} />
      </SchoolField>
      <SchoolField id="assessment-venue" label="Venue">
        <input id="assessment-venue" name="venue" className={LH_INPUT} placeholder="Optional" />
      </SchoolField>
      {error && <p className="text-sm text-rose-600">{error}</p>}
    </SchoolDialog>
  )
}

function ResultDialog({
  assessment,
  onClose,
  onDone,
}: {
  assessment: AssessmentRead
  onClose: () => void
  onDone: () => void
}) {
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [outcome, setOutcome] = useState<AssessmentOutcome>(assessment.outcome ?? 'PASSED')

  const scoreApplies = outcome !== 'NOT_ATTENDED'

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const form = new FormData(e.currentTarget)
    const rawScore = String(form.get('score') ?? '').trim()
    const rawMax = String(form.get('max_score') ?? '').trim()

    setSaving(true)
    setError(null)
    try {
      await recordAssessmentResult(assessment.id, {
        outcome,
        // Explicitly null for a no-show. An absent score is the honest record;
        // 0 would be a mark the candidate never earned or lost.
        score: scoreApplies && rawScore ? Number(rawScore) : null,
        max_score: scoreApplies && rawMax ? Number(rawMax) : null,
        assessor_notes: String(form.get('assessor_notes') ?? '').trim() || null,
      })
      onDone()
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.kind === 'permission_denied'
            ? 'You need admissions access to record a result.'
            : err.message
          : 'Could not record that result.'
      )
    } finally {
      setSaving(false)
    }
  }

  return (
    <SchoolDialog
      open
      onOpenChange={(o) => !o && onClose()}
      title={`Result — ${assessment.assessment_name}`}
      description="Record the outcome. A candidate who did not attend has no score."
      onSubmit={handleSubmit}
      footer={
        <button type="submit" disabled={saving} className={LH_PRIMARY_BUTTON}>
          <span>{saving ? 'Saving…' : 'Record result'}</span>
        </button>
      }
    >
      <SchoolField id="result-outcome" label="Outcome" required>
        <select
          id="result-outcome"
          name="outcome"
          className={LH_INPUT}
          value={outcome}
          onChange={(e) => setOutcome(e.target.value as AssessmentOutcome)}
        >
          <option value="PASSED">Passed</option>
          <option value="BORDERLINE">Borderline</option>
          <option value="FAILED">Failed</option>
          <option value="NOT_ATTENDED">Did not attend</option>
        </select>
      </SchoolField>

      {scoreApplies ? (
        <>
          <SchoolField id="result-score" label="Score">
            <input
              id="result-score"
              name="score"
              type="number"
              step="any"
              className={LH_INPUT}
              defaultValue={assessment.score ?? ''}
            />
          </SchoolField>
          <SchoolField id="result-max" label="Out of">
            <input
              id="result-max"
              name="max_score"
              type="number"
              step="any"
              className={LH_INPUT}
              defaultValue={assessment.max_score ?? ''}
            />
          </SchoolField>
        </>
      ) : (
        <p className="text-sm text-gray-500">
          No score is recorded for a candidate who did not attend — they did not score zero,
          they did not sit the paper.
        </p>
      )}

      <SchoolField id="result-notes" label="Assessor notes">
        <input
          id="result-notes"
          name="assessor_notes"
          className={LH_INPUT}
          defaultValue={assessment.assessor_notes ?? ''}
        />
      </SchoolField>

      {error && <p className="text-sm text-rose-600">{error}</p>}
    </SchoolDialog>
  )
}
