'use client'

/**
 * AI Tutor oversight (M46) -- what students asked, what was blocked, and the
 * kill switch.
 *
 * Deliberately shows blocked SAFETY turns alongside ordinary ones: the point
 * of oversight is that a teacher can see a worrying pattern building before
 * it becomes an incident, not only after the crisis classifier fires.
 */

import { useState } from 'react'
import { Bot, ShieldAlert, Slash } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  DashPageShell,
  DataTable,
  SectionCard,
  StatGrid,
  StatusChip,
} from '@/components/widgets'
import { ApiError } from '@/lib/api/api-client'
import { useApiResource } from '@/lib/api/useApiResource'
import { useSchoolSession } from '@/lib/api/useSchoolSession'
import { listCampuses, listClassSections } from '@/modules/sms/campus/api'
import {
  createAccessBlock,
  liftAccessBlock,
  listAccessBlocks,
  listSafetyIncidents,
  listTranscripts,
} from '@/modules/sms/ai-tutor/api'
import type { TranscriptOutcome } from '@/modules/sms/ai-tutor/types'

interface AITutorOversightClientProps {
  org_id: number
  orgslug: string
}

const OUTCOME_TONE: Record<TranscriptOutcome, 'positive' | 'caution' | 'critical' | 'neutral'> = {
  answered: 'positive',
  blocked_safety: 'critical',
  blocked_disabled: 'neutral',
  blocked_offtopic: 'caution',
  blocked_rate_limit: 'caution',
  blocked_session_limit: 'caution',
}

const OUTCOME_LABEL: Record<TranscriptOutcome, string> = {
  answered: 'Answered',
  blocked_safety: 'Safety block',
  blocked_disabled: 'AI switched off',
  blocked_offtopic: 'Off topic',
  blocked_rate_limit: 'Daily limit',
  blocked_session_limit: 'Time limit',
}

export default function AITutorOversightClient({ org_id }: AITutorOversightClientProps) {
  const { session } = useSchoolSession()
  const [sectionId, setSectionId] = useState<number | undefined>(undefined)
  const [busy, setBusy] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)

  const campuses = useApiResource(() => listCampuses({ orgId: org_id, isActive: true }), [org_id])
  const effectiveCampusId = session?.campus_id ?? campuses.data?.[0]?.id

  const sections = useApiResource(
    () => listClassSections(effectiveCampusId as number, { isActive: true }),
    [effectiveCampusId],
    { skip: effectiveCampusId === undefined }
  )
  const effectiveSectionId = sectionId ?? sections.data?.[0]?.id

  const transcripts = useApiResource(
    () => listTranscripts({ sectionId: effectiveSectionId, limit: 100 }),
    [effectiveSectionId],
    { isEmpty: (d) => d.length === 0 }
  )
  const incidents = useApiResource(() => listSafetyIncidents({ limit: 50 }), [], {
    isEmpty: (d) => d.length === 0,
  })
  const blocks = useApiResource(() => listAccessBlocks({ activeOnly: true }), [], {
    isEmpty: (d) => d.length === 0,
  })

  const rows = transcripts.data ?? []
  const answered = rows.filter((r) => r.outcome === 'answered').length
  const safetyBlocked = rows.filter((r) => r.outcome === 'blocked_safety').length
  const activeBlocks = blocks.data ?? []
  const sectionBlocked = activeBlocks.some((b) => b.section_id === effectiveSectionId)

  async function runAction(fn: () => Promise<unknown>) {
    setBusy(true)
    setActionError(null)
    try {
      await fn()
      blocks.refetch()
      transcripts.refetch()
    } catch (err) {
      setActionError(
        err instanceof ApiError
          ? err.kind === 'permission_denied'
            ? 'You need teacher or school-admin access to change this.'
            : err.message
          : 'Could not update AI access. Try again.'
      )
    } finally {
      setBusy(false)
    }
  }

  return (
    <DashPageShell
      title="AI Tutor"
      description="See what students are asking, review anything the safety filter stopped, and switch AI tutoring off when you need to."
    >
      <StatGrid
        state={transcripts.status === 'loading' ? 'loading' : 'success'}
        columns={4}
        items={[
          { label: 'Questions answered', value: answered, icon: Bot, tone: 'neutral' },
          {
            label: 'Stopped by safety filter',
            value: safetyBlocked,
            icon: ShieldAlert,
            tone: safetyBlocked > 0 ? 'critical' : 'positive',
          },
          {
            label: 'Safety incidents logged',
            value: incidents.data?.length ?? 0,
            icon: ShieldAlert,
            tone: (incidents.data?.length ?? 0) > 0 ? 'caution' : 'positive',
          },
          {
            label: 'AI currently switched off',
            value: activeBlocks.length,
            icon: Slash,
            tone: activeBlocks.length > 0 ? 'caution' : 'neutral',
          },
        ]}
      />

      {(sections.data ?? []).length > 0 && (
        <div className="flex flex-wrap items-end gap-4">
          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-medium text-muted-foreground">Section</span>
            <select
              id="ai-tutor-section"
              className="h-9 rounded-md border border-border bg-background px-3 text-sm"
              value={effectiveSectionId ?? ''}
              onChange={(e) => setSectionId(Number(e.target.value))}
            >
              {(sections.data ?? []).map((s) => (
                <option key={s.id} value={s.id}>
                  {s.grade_level} — {s.section_name}
                </option>
              ))}
            </select>
          </label>

          {effectiveSectionId !== undefined && (
            sectionBlocked ? (
              <Button
                size="sm"
                variant="outline"
                disabled={busy}
                onClick={() => {
                  const block = activeBlocks.find((b) => b.section_id === effectiveSectionId)
                  if (block) runAction(() => liftAccessBlock(block.id))
                }}
              >
                Turn AI back on for this section
              </Button>
            ) : (
              <Button
                size="sm"
                variant="outline"
                disabled={busy}
                onClick={() =>
                  runAction(() =>
                    createAccessBlock({
                      section_id: effectiveSectionId,
                      reason: 'Switched off from AI Tutor oversight',
                    })
                  )
                }
              >
                <Slash className="size-4" /> Switch AI off for this section
              </Button>
            )
          )}
        </div>
      )}

      {actionError && <p className="text-sm text-destructive">{actionError}</p>}

      <SectionCard
        id="blocks"
        title="AI switched off for"
        icon={<Slash className="size-4 text-muted-foreground" />}
        state={blocks.status}
        error={blocks.error}
        onRetry={blocks.refetch}
        emptyTitle="AI tutoring is on for everyone"
        emptyDescription="Nobody's AI access is currently switched off."
      >
        <DataTable
          rows={activeBlocks}
          rowKey={(row) => row.id}
          state="success"
          columns={[
            {
              key: 'who',
              header: 'Scope',
              render: (r) =>
                r.student_id ? `Student #${r.student_id}` : `Whole section #${r.section_id}`,
            },
            { key: 'reason', header: 'Reason', render: (r) => r.reason ?? '—' },
            { key: 'by', header: 'Switched off by', render: (r) => `User #${r.blocked_by_user_id}` },
            {
              key: 'when',
              header: 'Since',
              render: (r) => new Date(r.created_at).toLocaleDateString(),
            },
            {
              key: 'action',
              header: '',
              align: 'right',
              render: (r) => (
                <Button size="sm" variant="ghost" disabled={busy} onClick={() => runAction(() => liftAccessBlock(r.id))}>
                  Turn back on
                </Button>
              ),
            },
          ]}
        />
      </SectionCard>

      <SectionCard
        id="transcripts"
        title="Recent tutor activity"
        description="Newest first. Blocked questions are shown too, so patterns are visible before they become incidents."
        icon={<Bot className="size-4 text-muted-foreground" />}
        state={transcripts.status}
        error={transcripts.error}
        onRetry={transcripts.refetch}
        emptyTitle="No AI tutor activity yet"
        emptyDescription="Questions students ask the AI tutor will appear here."
      >
        <DataTable
          rows={rows}
          rowKey={(row) => row.id}
          state="success"
          columns={[
            { key: 'student', header: 'Student', render: (r) => `#${r.student_id}` },
            { key: 'prompt', header: 'Asked', render: (r) => r.prompt },
            {
              key: 'outcome',
              header: 'Outcome',
              render: (r) => (
                <StatusChip label={OUTCOME_LABEL[r.outcome] ?? r.outcome} tone={OUTCOME_TONE[r.outcome] ?? 'neutral'} />
              ),
            },
            {
              key: 'when',
              header: 'When',
              render: (r) => new Date(r.created_at).toLocaleString(),
            },
          ]}
        />
      </SectionCard>

      <SectionCard
        id="incidents"
        title="Safety incidents"
        description="Messages the crisis filter stopped before they reached the model. Counsellors are emailed automatically."
        icon={<ShieldAlert className="size-4 text-muted-foreground" />}
        state={incidents.status}
        error={incidents.error}
        onRetry={incidents.refetch}
        emptyTitle="No safety incidents"
        emptyDescription="Nothing has tripped the crisis filter."
      >
        <DataTable
          rows={incidents.data ?? []}
          rowKey={(row) => row.id}
          state="success"
          columns={[
            { key: 'student', header: 'Student', render: (r) => `#${r.student_id}` },
            { key: 'cat', header: 'Category', render: (r) => r.trigger_category },
            {
              key: 'sev',
              header: 'Severity',
              render: (r) => (
                <StatusChip
                  label={r.severity}
                  tone={r.severity === 'CRITICAL' ? 'critical' : r.severity === 'HIGH' ? 'caution' : 'neutral'}
                />
              ),
            },
            {
              key: 'notified',
              header: 'Counsellor alerted',
              render: (r) => (
                <StatusChip
                  label={r.counselor_notified ? 'Alerted' : 'Not alerted'}
                  tone={r.counselor_notified ? 'positive' : 'critical'}
                />
              ),
            },
            { key: 'when', header: 'When', render: (r) => new Date(r.created_at).toLocaleString() },
          ]}
        />
      </SectionCard>
    </DashPageShell>
  )
}
