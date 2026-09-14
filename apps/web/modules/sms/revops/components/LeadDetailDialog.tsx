'use client'

/**
 * Everything known about one lead, in one place.
 *
 * Before this, a lead could be dragged between kanban columns and nothing
 * else -- no way to see why it scored what it scored, log that someone rang
 * the parent, or record a consent opt-in. The board was a picture of the
 * funnel rather than a tool for working it.
 *
 * Two deliberate honesty rules, both carried over from `adapt.ts`:
 *
 * 1. The score breakdown is only shown once `POST /leads/{id}/ai-qualify` has
 *    actually been run in this session. The pipeline payload carries the
 *    NUMBER (`lead_score`) but not the five components behind it, so
 *    rendering a breakdown on load would mean inventing the split. Until
 *    then the panel says the breakdown has not been computed.
 *
 * 2. Outbound actions are hidden, not merely disabled, for a channel the
 *    lead has not consented to -- and the panel says why. Consent here is a
 *    compliance record that the backend's SDR agent and drip engine actually
 *    enforce (sms_revops.py:272-289); showing a send button that will be
 *    refused server-side would misrepresent what the system will do.
 *
 * 3. Nothing here sends. Every AI action below produces a DRAFT for a human
 *    to review; the hourly nurture runner is the only thing that delivers,
 *    and only to a lead that has consented. The generators also REFUSE
 *    rather than invent -- a lead with no campus, or an offer with no
 *    tuition, comes back as a 4xx naming the fix, and that message is shown
 *    verbatim so the operator learns what to configure.
 */

import { useState } from 'react'
import {
  BadgeCheck,
  Ban,
  Bot,
  FileText,
  Mail,
  MessageSquare,
  Phone,
  Send,
  Sparkles,
  StickyNote,
  Users,
} from 'lucide-react'
import {
  DataTable,
  EmptyState,
  LH_INPUT,
  LH_PRIMARY_BUTTON,
  LH_SECONDARY_BUTTON,
  SchoolDialog,
  SchoolField,
  StatusChip,
} from '@/components/widgets'
import { ApiError } from '@/lib/api/api-client'
import { useApiResource } from '@/lib/api/useApiResource'
import {
  aiQualifyLead,
  draftOutreachCopy,
  draftSdrReply,
  generateOfferCopy,
  getLeadConversation,
  getLeadOutboundTouches,
  getLeadResearchBrief,
  listLeadActivities,
  logLeadActivity,
  startNurtureSequence,
  updateLeadConsent,
} from '../api'
import type {
  ActivityType,
  LeadQualifyResult,
  LeadRead,
  NurtureSequenceResult,
  OutreachCopyDraft,
  ResearchBrief,
  SdrReplyResult,
  TouchStatus,
} from '../types'

const INTENT_TONE: Record<string, 'positive' | 'caution' | 'neutral'> = {
  HOT: 'positive',
  WARM: 'caution',
  COLD: 'neutral',
}

/** Activity kinds a human logs by hand. STAGE_CHANGE and CONSENT_UPDATE are
 *  written by the server as side effects, so offering them here would let a
 *  user fabricate an audit entry. */
const MANUAL_ACTIVITY_TYPES: ActivityType[] = ['NOTE', 'CALL', 'EMAIL', 'WHATSAPP', 'TOUR']

const SCORE_FACTOR_LABELS: Record<string, { label: string; max: number }> = {
  completeness_score: { label: 'Inquiry completeness', max: 25 },
  responsiveness_score: { label: 'Responsiveness', max: 20 },
  grade_demand_score: { label: 'Grade demand', max: 15 },
  budget_fit_score: { label: 'Budget fit', max: 20 },
  timeline_score: { label: 'Timeline urgency', max: 20 },
}

/** A FAILED or CONSENT_BLOCKED touch is the reason this table exists, so it
 *  is coloured to read at a glance rather than blending into the list. */
const TOUCH_TONE: Record<TouchStatus, 'positive' | 'critical' | 'caution' | 'neutral'> = {
  SENT: 'positive',
  FAILED: 'critical',
  CONSENT_BLOCKED: 'caution',
  SKIPPED: 'neutral',
}

export interface LeadDetailDialogProps {
  lead: LeadRead
  open: boolean
  onOpenChange: (open: boolean) => void
  /** Called after any mutation so the caller can refetch the pipeline. */
  onChanged: () => void
}

export function LeadDetailDialog({ lead, open, onOpenChange, onChanged }: LeadDetailDialogProps) {
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [qualified, setQualified] = useState<LeadQualifyResult | null>(null)
  const [activityType, setActivityType] = useState<ActivityType>('CALL')
  const [activitySummary, setActivitySummary] = useState('')

  // AI outputs. All are drafts held in local state -- none of them are
  // persisted or sent by opening this dialog.
  const [research, setResearch] = useState<ResearchBrief | null>(null)
  const [sdrMessage, setSdrMessage] = useState('')
  const [sdrResult, setSdrResult] = useState<SdrReplyResult | null>(null)
  const [copyDraft, setCopyDraft] = useState<OutreachCopyDraft | null>(null)
  const [nurture, setNurture] = useState<NurtureSequenceResult | null>(null)
  const [offerCopy, setOfferCopy] = useState<string | null>(null)

  const activities = useApiResource(() => listLeadActivities(lead.id), [lead.id, open], {
    skip: !open,
    isEmpty: (d) => d.length === 0,
  })

  const conversation = useApiResource(() => getLeadConversation(lead.id), [lead.id, open], {
    skip: !open,
    isEmpty: (d) => d.turns.length === 0,
  })

  const touches = useApiResource(() => getLeadOutboundTouches(lead.id), [lead.id, open], {
    skip: !open,
    isEmpty: (d) => d.touches.length === 0,
  })

  function describe(err: unknown, fallback: string): string {
    if (err instanceof ApiError) {
      if (err.kind === 'permission_denied') return 'You do not have access to change this lead.'
      return err.message
    }
    return fallback
  }

  async function run(key: string, fn: () => Promise<unknown>, fallbackMsg: string) {
    setBusy(key)
    setError(null)
    try {
      await fn()
    } catch (err) {
      setError(describe(err, fallbackMsg))
    } finally {
      setBusy(null)
    }
  }

  const handleQualify = () =>
    run(
      'qualify',
      async () => {
        const result = await aiQualifyLead(lead.id)
        setQualified(result)
        // ai-qualify PERSISTS the new score onto the lead, so the board is
        // now stale -- refetch rather than leaving two different numbers.
        onChanged()
      },
      'Could not score this lead.'
    )

  const handleConsent = (channel: 'whatsapp' | 'email', next: boolean) =>
    run(
      `consent-${channel}`,
      async () => {
        await updateLeadConsent(lead.id,
          channel === 'whatsapp' ? { whatsapp_consent: next } : { email_consent: next }
        )
        onChanged()
        activities.refetch()
      },
      'Could not record the consent change.'
    )

  const handleLogActivity = () => {
    const summary = activitySummary.trim()
    if (!summary) {
      setError('Write a short summary of what happened.')
      return
    }
    return run(
      'activity',
      async () => {
        await logLeadActivity(lead.id, { activity_type: activityType, summary })
        setActivitySummary('')
        activities.refetch()
        onChanged()
      },
      'Could not log that activity.'
    )
  }

  const handleResearch = () =>
    run(
      'research',
      async () => setResearch(await getLeadResearchBrief(lead.id)),
      'Could not build a research brief.'
    )

  const handleSdrReply = () => {
    const message = sdrMessage.trim()
    if (!message) {
      setError('Paste the parent’s message so the agent has something to answer.')
      return
    }
    return run(
      'sdr',
      async () => {
        setSdrResult(await draftSdrReply(lead.id, { message }))
        // Both turns are stored server-side, so the thread below is stale.
        conversation.refetch()
      },
      'Could not draft a reply.'
    )
  }

  const handleCopy = () =>
    run(
      'copy',
      async () => setCopyDraft(await draftOutreachCopy(lead.id, { channel: 'email' })),
      'Could not draft outreach copy.'
    )

  const handleNurture = () =>
    run(
      'nurture',
      async () => {
        setNurture(await startNurtureSequence(lead.id))
        // Enrolling writes an activity row and may change what is scheduled.
        activities.refetch()
        touches.refetch()
        onChanged()
      },
      'Could not start the nurture sequence.'
    )

  const handleOfferCopy = () =>
    run(
      'offer',
      async () => setOfferCopy((await generateOfferCopy(lead.id)).letter_markdown),
      'Could not generate offer copy.'
    )

  const noConsent = !lead.whatsapp_consent && !lead.email_consent

  return (
    <SchoolDialog
      open={open}
      onOpenChange={onOpenChange}
      title={lead.student_name}
      description={`Applying for ${lead.grade_applying_for} · parent ${lead.parent_name}`}
      className="sm:max-w-2xl"
    >
      {/* ---------------------------------------------------------- contact */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <DetailRow icon={<Phone className="size-3.5" />} label="Phone" value={lead.phone} />
        <DetailRow icon={<Mail className="size-3.5" />} label="Email" value={lead.email} />
        <DetailRow
          icon={<Users className="size-3.5" />}
          label="Assigned officer"
          value={lead.assigned_officer_id ? `Officer #${lead.assigned_officer_id}` : 'Unassigned'}
        />
        <DetailRow
          icon={<BadgeCheck className="size-3.5" />}
          label="Source"
          value={`${lead.source.replace(/_/g, ' ')} · ${lead.origin}`}
        />
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <StatusChip label={lead.stage.replace(/_/g, ' ')} tone="info" />
        <StatusChip label={lead.intent_level} tone={INTENT_TONE[lead.intent_level] ?? 'neutral'} />
        <span className="text-sm text-gray-500">
          Score <span className="font-semibold tabular-nums text-gray-900">{lead.lead_score}</span>/100
        </span>
        {lead.budget_range && (
          <span className="text-sm text-gray-500">Budget: {lead.budget_range}</span>
        )}
      </div>

      {/* ------------------------------------------------------ score detail */}
      <section className="rounded-lg bg-gray-50 p-4">
        <div className="mb-2 flex items-center justify-between gap-3">
          <h3 className="flex items-center gap-1.5 text-sm font-semibold text-gray-900">
            <Sparkles className="size-4 text-gray-500" /> Lead score breakdown
          </h3>
          <button
            type="button"
            className={LH_SECONDARY_BUTTON}
            onClick={handleQualify}
            disabled={busy === 'qualify'}
          >
            <span>{busy === 'qualify' ? 'Scoring…' : 'Re-score now'}</span>
          </button>
        </div>

        {qualified ? (
          <div className="flex flex-col gap-2">
            {Object.entries(qualified.breakdown).map(([key, value]) => {
              const meta = SCORE_FACTOR_LABELS[key]
              if (!meta) return null
              const pct = meta.max > 0 ? (Number(value) / meta.max) * 100 : 0
              return (
                <div key={key} className="flex items-center gap-3">
                  <span className="w-40 shrink-0 text-xs text-gray-600">{meta.label}</span>
                  <div className="h-2 flex-1 overflow-hidden rounded-full bg-gray-200">
                    <div className="h-full rounded-full bg-black/80" style={{ width: `${pct}%` }} />
                  </div>
                  <span className="w-14 shrink-0 text-end text-xs tabular-nums text-gray-700">
                    {Number(value)}/{meta.max}
                  </span>
                </div>
              )
            })}

            {qualified.key_conversion_factors.length > 0 && (
              <ul className="mt-1 list-disc ps-5 text-xs text-gray-600">
                {qualified.key_conversion_factors.map((f) => (
                  <li key={f}>{f}</li>
                ))}
              </ul>
            )}
            <p className="mt-1 text-xs font-medium text-gray-800">
              Next: {qualified.recommended_next_action}
            </p>
          </div>
        ) : (
          <p className="text-xs text-gray-500">
            The stored score is {lead.lead_score}/100, but the five factors behind it are computed
            on demand and are not part of the pipeline data. Run “Re-score now” to see the
            breakdown and refresh the score.
          </p>
        )}
      </section>

      {/* ---------------------------------------------------------- consent */}
      <section className="rounded-lg bg-gray-50 p-4">
        <h3 className="mb-2 text-sm font-semibold text-gray-900">Outreach consent</h3>
        {noConsent && (
          <p className="mb-2 flex items-start gap-1.5 text-xs text-amber-700">
            <Ban className="mt-0.5 size-3.5 shrink-0" />
            No channel is consented, so automated nurture and SDR replies are blocked for this
            lead. Record an opt-in below once the parent has given it.
          </p>
        )}
        <div className="flex flex-col gap-2">
          <ConsentToggle
            label="WhatsApp"
            granted={lead.whatsapp_consent}
            busy={busy === 'consent-whatsapp'}
            onToggle={(next) => handleConsent('whatsapp', next)}
          />
          <ConsentToggle
            label="Email"
            granted={lead.email_consent}
            busy={busy === 'consent-email'}
            onToggle={(next) => handleConsent('email', next)}
          />
        </div>
      </section>

      {/* --------------------------------------------------------- activity */}
      <section>
        <h3 className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-gray-900">
          <StickyNote className="size-4 text-gray-500" /> Activity
        </h3>

        <div className="mb-3 flex flex-wrap items-end gap-2">
          <SchoolField id="lead-activity-type" label="Type">
            <select
              id="lead-activity-type"
              className={LH_INPUT}
              value={activityType}
              onChange={(e) => setActivityType(e.target.value as ActivityType)}
            >
              {MANUAL_ACTIVITY_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t.charAt(0) + t.slice(1).toLowerCase()}
                </option>
              ))}
            </select>
          </SchoolField>
          <div className="min-w-[14rem] flex-1">
            <SchoolField id="lead-activity-summary" label="What happened">
              <input
                id="lead-activity-summary"
                className={LH_INPUT}
                value={activitySummary}
                onChange={(e) => setActivitySummary(e.target.value)}
                placeholder="Spoke to parent about the tour"
              />
            </SchoolField>
          </div>
          <button
            type="button"
            className={LH_PRIMARY_BUTTON}
            onClick={handleLogActivity}
            disabled={busy === 'activity'}
          >
            <span>{busy === 'activity' ? 'Logging…' : 'Log'}</span>
          </button>
        </div>

        {activities.status === 'empty' ? (
          <EmptyState
            icon={MessageSquare}
            title="Nothing logged yet"
            description="Calls, messages and tours recorded here build the engagement signal the lead score uses."
          />
        ) : (
          <DataTable
            rows={activities.data ?? []}
            rowKey={(row) => row.id}
            state={activities.status === 'error' ? 'error' : 'success'}
            columns={[
              {
                key: 'type',
                header: 'Type',
                render: (r) => <StatusChip label={r.activity_type.replace(/_/g, ' ')} tone="info" />,
              },
              { key: 'summary', header: 'Summary', render: (r) => r.summary },
              {
                key: 'when',
                header: 'When',
                render: (r) => new Date(r.created_at).toLocaleString(),
              },
            ]}
          />
        )}
      </section>

      {/* ----------------------------------------------------- conversation */}
      <section>
        <h3 className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-gray-900">
          <MessageSquare className="size-4 text-gray-500" /> Conversation
        </h3>
        {conversation.status === 'empty' ? (
          <p className="text-xs text-gray-500">
            No messages exchanged yet. Drafting an SDR reply below records both the parent’s
            message and the reply, so the next one is answered with context.
          </p>
        ) : (
          <div className="flex max-h-56 flex-col gap-2 overflow-y-auto">
            {(conversation.data?.turns ?? []).map((turn, i) => (
              <div
                key={`${turn.created_at ?? 'turn'}-${i}`}
                className={
                  turn.direction === 'INBOUND'
                    ? 'rounded-lg bg-gray-100 p-2.5'
                    : 'rounded-lg bg-blue-50 p-2.5'
                }
              >
                <div className="mb-0.5 flex items-center gap-2 text-[11px] text-gray-500">
                  <span className="font-medium">
                    {turn.direction === 'INBOUND' ? 'Parent' : 'School'}
                  </span>
                  {turn.channel && <span>· {turn.channel}</span>}
                  {turn.detected_intent && <span>· {turn.detected_intent}</span>}
                  {turn.created_at && <span>· {new Date(turn.created_at).toLocaleString()}</span>}
                </div>
                <p className="whitespace-pre-wrap text-sm text-gray-800">{turn.message}</p>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* -------------------------------------------------- outbound record */}
      <section>
        <h3 className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-gray-900">
          <Send className="size-4 text-gray-500" /> Automated outbound
        </h3>
        {touches.status === 'empty' ? (
          <p className="text-xs text-gray-500">
            Nothing has been sent automatically to this lead. Starting a nurture sequence below
            schedules the drip; every attempt then appears here with what actually happened to it.
          </p>
        ) : (
          <DataTable
            rows={touches.data?.touches ?? []}
            rowKey={(row) => `${row.stage}-${row.at ?? ''}`}
            state={touches.status === 'error' ? 'error' : 'success'}
            columns={[
              { key: 'stage', header: 'Stage', render: (r) => `#${r.stage}` },
              { key: 'channel', header: 'Channel', render: (r) => r.channel },
              { key: 'subject', header: 'Subject', render: (r) => r.subject ?? '—' },
              {
                key: 'status',
                header: 'Result',
                render: (r) => (
                  <StatusChip
                    label={r.status.replace(/_/g, ' ')}
                    tone={TOUCH_TONE[r.status] ?? 'neutral'}
                  />
                ),
              },
              // The reason a send failed or was suppressed is the whole point
              // of keeping this record, so it gets its own column.
              { key: 'detail', header: 'Detail', render: (r) => r.detail ?? '—' },
              {
                key: 'at',
                header: 'When',
                render: (r) => (r.at ? new Date(r.at).toLocaleString() : '—'),
              },
            ]}
          />
        )}
      </section>

      {/* ------------------------------------------------------- AI actions */}
      <section className="rounded-lg bg-gray-50 p-4">
        <h3 className="mb-1 flex items-center gap-1.5 text-sm font-semibold text-gray-900">
          <Bot className="size-4 text-gray-500" /> AI assistance
        </h3>
        <p className="mb-3 text-xs text-gray-500">
          Everything here produces a draft for you to review. Nothing is sent from this panel —
          the nurture scheduler delivers, and only to a consented channel.
        </p>

        <div className="mb-3 flex flex-wrap gap-2">
          <button
            type="button"
            id="lead-ai-research"
            className={LH_SECONDARY_BUTTON}
            onClick={handleResearch}
            disabled={busy === 'research'}
          >
            <span>{busy === 'research' ? 'Compiling…' : 'Research brief'}</span>
          </button>
          <button
            type="button"
            id="lead-ai-copy"
            className={LH_SECONDARY_BUTTON}
            onClick={handleCopy}
            disabled={busy === 'copy'}
          >
            <span>{busy === 'copy' ? 'Drafting…' : 'Draft outreach copy'}</span>
          </button>
          <button
            type="button"
            id="lead-ai-nurture"
            className={LH_SECONDARY_BUTTON}
            onClick={handleNurture}
            disabled={busy === 'nurture'}
          >
            <span>{busy === 'nurture' ? 'Scheduling…' : 'Start nurture sequence'}</span>
          </button>
          <button
            type="button"
            id="lead-ai-offer"
            className={LH_SECONDARY_BUTTON}
            onClick={handleOfferCopy}
            disabled={busy === 'offer'}
          >
            <span>{busy === 'offer' ? 'Writing…' : 'Draft offer letter'}</span>
          </button>
        </div>

        {/* SDR reply drafting needs the parent's message as input. */}
        <div className="mb-3 flex flex-wrap items-end gap-2">
          <div className="min-w-[16rem] flex-1">
            <SchoolField id="lead-sdr-message" label="Parent’s message">
              <input
                id="lead-sdr-message"
                className={LH_INPUT}
                value={sdrMessage}
                onChange={(e) => setSdrMessage(e.target.value)}
                placeholder="Do you have space in Grade 4 for January?"
              />
            </SchoolField>
          </div>
          <button
            type="button"
            id="lead-ai-sdr"
            className={LH_PRIMARY_BUTTON}
            onClick={handleSdrReply}
            disabled={busy === 'sdr'}
          >
            <span>{busy === 'sdr' ? 'Drafting…' : 'Draft reply'}</span>
          </button>
        </div>

        {sdrResult && (
          <AiResult title="Suggested reply">
            {sdrResult.consent_blocked ? (
              <p className="flex items-start gap-1.5 text-xs text-amber-700">
                <Ban className="mt-0.5 size-3.5 shrink-0" />
                {sdrResult.detail}
              </p>
            ) : (
              <>
                <p className="whitespace-pre-wrap text-sm text-gray-800">{sdrResult.response}</p>
                {(sdrResult.suggested_actions?.length ?? 0) > 0 && (
                  <ul className="mt-2 list-disc ps-5 text-xs text-gray-600">
                    {sdrResult.suggested_actions?.map((a) => <li key={a}>{a}</li>)}
                  </ul>
                )}
                <p className="mt-1 text-[11px] text-gray-400">
                  Answered using {sdrResult.history_turns_used} earlier turn(s).
                </p>
              </>
            )}
          </AiResult>
        )}

        {research && (
          <AiResult title="Research brief">
            {research.talking_points.length > 0 && (
              <ul className="list-disc ps-5 text-sm text-gray-700">
                {research.talking_points.map((t) => <li key={t}>{t}</li>)}
              </ul>
            )}
            {research.questions_to_ask.length > 0 && (
              <>
                <p className="mt-2 text-xs font-medium text-gray-800">Worth asking</p>
                <ul className="list-disc ps-5 text-xs text-gray-600">
                  {research.questions_to_ask.map((q) => <li key={q}>{q}</li>)}
                </ul>
              </>
            )}
            {/* Gaps are reported, never filled -- the agent performs no
                external lookup and infers nothing about the family. */}
            {research.unknown_fields.length > 0 && (
              <p className="mt-2 text-xs text-gray-500">
                Not known: {research.unknown_fields.join(', ')}
              </p>
            )}
            <p className="mt-1 text-[11px] text-gray-400">{research.disclaimer}</p>
          </AiResult>
        )}

        {copyDraft && (
          <AiResult title={`Outreach draft · ${copyDraft.channel}`}>
            {copyDraft.subject && (
              <p className="mb-1 text-sm font-medium text-gray-900">{copyDraft.subject}</p>
            )}
            <p className="whitespace-pre-wrap text-sm text-gray-800">{copyDraft.body}</p>
            {copyDraft.refinement_note && (
              <p className="mt-1 text-[11px] text-gray-400">{copyDraft.refinement_note}</p>
            )}
          </AiResult>
        )}

        {nurture && (
          <AiResult title="Nurture sequence scheduled">
            <p className="text-xs text-gray-600">
              {nurture.stages.length} stage(s) queued.
              {nurture.next_due_at
                ? ` Next send ${new Date(nurture.next_due_at).toLocaleString()}.`
                : ' Nothing is due yet.'}
            </p>
            {!nurture.consent.whatsapp && !nurture.consent.email && (
              <p className="mt-1 flex items-start gap-1.5 text-xs text-amber-700">
                <Ban className="mt-0.5 size-3.5 shrink-0" />
                No channel is consented, so the scheduler will suppress every stage until an
                opt-in is recorded above.
              </p>
            )}
          </AiResult>
        )}

        {offerCopy && (
          <AiResult title="Offer letter draft">
            <p className="mb-1 flex items-center gap-1.5 text-[11px] text-gray-500">
              <FileText className="size-3.5" /> Draft only — issuing the offer is a separate step.
            </p>
            <pre className="max-h-56 overflow-auto whitespace-pre-wrap text-xs text-gray-800">
              {offerCopy}
            </pre>
          </AiResult>
        )}
      </section>

      {lead.notes && (
        <section>
          <h3 className="mb-1 text-sm font-semibold text-gray-900">Notes</h3>
          <p className="whitespace-pre-wrap text-sm text-gray-600">{lead.notes}</p>
        </section>
      )}

      {/* The generators refuse rather than invent, so this message is often
          actionable ("assign the lead to a campus first") -- show it as-is. */}
      {error && <p className="text-sm text-rose-600">{error}</p>}
    </SchoolDialog>
  )
}

/** A generated draft, visually separated from the real record above it so a
 *  suggestion is never mistaken for something the school actually sent. */
function AiResult({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mt-2 rounded-lg border border-gray-200 bg-white p-3">
      <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-gray-400">{title}</p>
      {children}
    </div>
  )
}

function DetailRow({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode
  label: string
  value: string
}) {
  return (
    <div className="flex items-start gap-2">
      <span className="mt-0.5 text-gray-400">{icon}</span>
      <span className="flex flex-col">
        <span className="text-xs text-gray-500">{label}</span>
        <span className="text-sm text-gray-900">{value}</span>
      </span>
    </div>
  )
}

function ConsentToggle({
  label,
  granted,
  busy,
  onToggle,
}: {
  label: string
  granted: boolean
  busy: boolean
  onToggle: (next: boolean) => void
}) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="flex items-center gap-2 text-sm text-gray-700">
        {label}
        <StatusChip
          label={granted ? 'Opted in' : 'No consent'}
          tone={granted ? 'positive' : 'neutral'}
        />
      </span>
      <button
        type="button"
        className={LH_SECONDARY_BUTTON}
        onClick={() => onToggle(!granted)}
        disabled={busy}
      >
        <span>{busy ? 'Saving…' : granted ? 'Record opt-out' : 'Record opt-in'}</span>
      </button>
    </div>
  )
}
