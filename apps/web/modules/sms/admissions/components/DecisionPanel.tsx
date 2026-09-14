'use client'

/**
 * The admission decision trail.
 *
 * Append-only, and presented as a history rather than a current value. That
 * is the entire point of the module: a school challenged months later — by a
 * family, an inspector or a regulator — must be able to show what was
 * decided, by whom, and why. A reversed decision adds a row; it never edits
 * one, so the trail cannot be quietly rewritten.
 *
 * `reason` is required by the backend (min_length=1). A decision with no
 * recorded rationale is exactly what this exists to prevent.
 */

import { useState } from 'react'
import { Gavel } from 'lucide-react'
import {
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
import { recordDecision } from '../api'
import { DECISION_LABEL, DECISION_TONE, TERMINAL_STATUSES, formatDateTime } from '../presentation'
import type { AdmissionDecision, ApplicationStatus, DecisionRead } from '../types'

interface Props {
  applicationId: number
  decisions: DecisionRead[]
  status: ApplicationStatus
  /** Deciding is SUPER_ADMIN/SCHOOL_ADMIN server-side — refusing a child a place is a leadership act. */
  canDecide: boolean
  onChanged: () => void
}

export function DecisionPanel({ applicationId, decisions, status, canDecide, onChanged }: Props) {
  const [deciding, setDeciding] = useState(false)
  const isClosed = TERMINAL_STATUSES.includes(status)

  return (
    <SectionCard
      id="decisions"
      title="Decision trail"
      description="Every decision recorded against this application, oldest first."
      icon={<Gavel className="size-4 text-gray-500" />}
      action={
        canDecide ? (
          <button
            type="button"
            id="record-decision-button"
            className={LH_SECONDARY_BUTTON}
            disabled={isClosed}
            title={isClosed ? 'This application is closed and cannot be decided again.' : undefined}
            onClick={() => setDeciding(true)}
          >
            <span>Record decision</span>
          </button>
        ) : undefined
      }
    >
      {decisions.length === 0 ? (
        <EmptyState
          title="No decision recorded"
          description="Nobody has decided on this application yet."
        />
      ) : (
        <ol className="flex flex-col gap-3">
          {decisions.map((d) => (
            <li key={d.id} className="rounded-lg bg-white p-3 nice-shadow">
              <div className="flex items-center justify-between gap-3">
                <StatusChip label={DECISION_LABEL[d.decision]} tone={DECISION_TONE[d.decision]} />
                <span className="text-xs text-gray-500">
                  {formatDateTime(d.decided_at)} · by user #{d.decided_by_user_id}
                </span>
              </div>
              <p className="mt-2 text-sm text-gray-700">{d.reason}</p>
            </li>
          ))}
        </ol>
      )}

      {deciding && (
        <DecisionDialog
          applicationId={applicationId}
          onClose={() => setDeciding(false)}
          onDone={() => {
            setDeciding(false)
            onChanged()
          }}
        />
      )}
    </SectionCard>
  )
}

function DecisionDialog({
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
  const [decision, setDecision] = useState<AdmissionDecision>('OFFERED')

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const form = new FormData(e.currentTarget)
    const reason = String(form.get('reason') ?? '').trim()
    if (!reason) {
      setError('A decision needs a recorded reason — that is what the trail is for.')
      return
    }

    setSaving(true)
    setError(null)
    try {
      await recordDecision(applicationId, { decision, reason })
      onDone()
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.kind === 'permission_denied'
            ? 'Only school leadership can record an admission decision.'
            : err.message
          : 'Could not record that decision.'
      )
    } finally {
      setSaving(false)
    }
  }

  return (
    <SchoolDialog
      open
      onOpenChange={(o) => !o && onClose()}
      title="Record an admission decision"
      description="This is appended to the trail permanently. It cannot be edited or removed."
      onSubmit={handleSubmit}
      footer={
        <button type="submit" disabled={saving} className={LH_PRIMARY_BUTTON}>
          <span>{saving ? 'Recording…' : 'Record decision'}</span>
        </button>
      }
    >
      <SchoolField id="decision-type" label="Decision" required>
        <select
          id="decision-type"
          name="decision"
          className={LH_INPUT}
          value={decision}
          onChange={(e) => setDecision(e.target.value as AdmissionDecision)}
        >
          <option value="OFFERED">Offer a place</option>
          <option value="WAITLISTED">Waitlist</option>
          <option value="REJECTED">Refuse</option>
        </select>
      </SchoolField>

      <SchoolField
        id="decision-reason"
        label="Reason"
        required
        help="Required. A school challenged on this decision later has only what is written here."
      >
        <input id="decision-reason" name="reason" className={LH_INPUT} />
      </SchoolField>

      {error && <p className="text-sm text-rose-600">{error}</p>}
    </SchoolDialog>
  )
}
