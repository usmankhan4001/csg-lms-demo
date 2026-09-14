'use client'

/**
 * Read and edit one counselling session.
 *
 * The whole point of this dialog is the separation it renders: `notes` and
 * `follow_up_plan` are clinical and never leave this screen, while
 * `parent_visible_summary` is the only field a family can ever see, and only
 * when `share_summary_with_parent` is true (`counseling.py:193-214` filters
 * on exactly that flag). They are visually separated and labelled, because a
 * counsellor pasting clinical detail into the shared box is the realistic
 * way this record leaks -- not a permissions bug.
 */

import { useState } from 'react'
import {
  LH_INPUT,
  LH_PRIMARY_BUTTON,
  SchoolDialog,
  SchoolField,
  StatusChip,
} from '@/components/widgets'
import { ApiError } from '@/lib/api/api-client'
import { updateSession } from '../api'
import { formatDateTime, formatDuration, sharingLabel } from '../presentation'
import type { CounselingSessionRead } from '../types'

export function SessionDetailDialog({
  session,
  onClose,
  onSaved,
}: {
  session: CounselingSessionRead
  onClose: () => void
  onSaved: () => void
}) {
  const [share, setShare] = useState(session.share_summary_with_parent)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handle(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const f = new FormData(e.currentTarget)
    setSaving(true)
    setError(null)
    try {
      await updateSession(session.id, {
        notes: String(f.get('notes') ?? ''),
        follow_up_plan: String(f.get('follow_up_plan') ?? '') || null,
        share_summary_with_parent: share,
        parent_visible_summary: String(f.get('parent_visible_summary') ?? '') || null,
      })
      onSaved()
    } catch (err) {
      // A 404 here is the confidentiality 404 -- worded as absence, never as
      // a refusal, so it cannot confirm anything to the wrong reader.
      setError(
        err instanceof ApiError
          ? err.status === 404
            ? 'This session is no longer available.'
            : err.message
          : 'Could not save. Try again.'
      )
    } finally {
      setSaving(false)
    }
  }

  const sharing = sharingLabel(session.share_summary_with_parent)

  return (
    <SchoolDialog
      open
      onOpenChange={(v) => {
        if (!v) onClose()
      }}
      /* Session #, never the student's name -- dialog titles land in
         screenshots and screen-share recordings. */
      title={`Session #${session.id}`}
      description={`${formatDateTime(session.session_date)} · ${formatDuration(
        session.duration_minutes
      )}`}
      onSubmit={handle}
      footer={
        <button type="submit" disabled={saving} className={LH_PRIMARY_BUTTON}>
          <span>{saving ? 'Saving…' : 'Save changes'}</span>
        </button>
      }
    >
      <div className="flex items-center gap-2">
        <StatusChip label={sharing.label} tone={sharing.tone} />
        <span className="text-xs text-gray-500">
          Recorded {formatDateTime(session.created_at)}
        </span>
      </div>

      <SchoolField
        id="detail-notes"
        label="Clinical notes"
        help="Private to you. Never shown to the student or their family."
      >
        <textarea
          id="detail-notes"
          name="notes"
          rows={6}
          className={LH_INPUT}
          defaultValue={session.notes}
        />
      </SchoolField>

      <SchoolField id="detail-followup" label="Follow-up plan" help="Also private to you.">
        <textarea
          id="detail-followup"
          name="follow_up_plan"
          rows={3}
          className={LH_INPUT}
          defaultValue={session.follow_up_plan ?? ''}
        />
      </SchoolField>

      <div className="rounded-lg border border-gray-200 p-3">
        <label className="flex items-start gap-2 text-sm">
          <input
            id="detail-share"
            name="share_summary_with_parent"
            type="checkbox"
            className="mt-0.5"
            checked={share}
            onChange={(e) => setShare(e.target.checked)}
          />
          <span>
            <span className="font-medium text-gray-800">Share a summary with the family</span>
            <span className="mt-0.5 block text-xs text-gray-500">
              Only the summary below is shared. Clinical notes and the
              follow-up plan are never included.
            </span>
          </span>
        </label>
        {share && (
          <div className="mt-3">
            <SchoolField id="detail-parent-summary" label="Summary for the family">
              <textarea
                id="detail-parent-summary"
                name="parent_visible_summary"
                rows={3}
                className={LH_INPUT}
                defaultValue={session.parent_visible_summary ?? ''}
              />
            </SchoolField>
          </div>
        )}
      </div>

      {error && <p className="text-sm text-rose-600">{error}</p>}
    </SchoolDialog>
  )
}
