'use client'

/**
 * Lead detail as a PAGE, not only a dialog.
 *
 * An admissions officer works one family over days and needs a URL they can
 * send to a colleague ("can you call this one?"). A dialog cannot be linked,
 * survive a refresh, or be opened in a second tab beside the board.
 *
 * One request populates most of this: `GET /revops/leads/{id}` returns
 * `LeadDetailResponse` -- the lead PLUS its activities and offers
 * (sms_revops.py:165, schemas/sms_revops.py:175).
 *
 * Everything shown here is real. Nothing is generated to fill a panel, and
 * the AI actions all produce DRAFTS -- the hourly nurture runner is what
 * actually sends, and only to a family that consented.
 */

import { useState } from 'react'
import Link from 'next/link'
import {
  ArrowLeft,
  BadgeCheck,
  ClipboardList,
  MessageSquare,
  Phone,
  Send,
  ShieldCheck,
  Sparkles,
  Users,
} from 'lucide-react'
import {
  DashPageShell,
  DataTable,
  LH_INPUT,
  LH_SECONDARY_BUTTON,
  SectionCard,
  StatGrid,
  StatusChip,
} from '@/components/widgets'
import { ApiError } from '@/lib/api/api-client'
import { useApiResource } from '@/lib/api/useApiResource'
import {
  aiQualifyLead,
  getLead,
  getLeadConversation,
  getLeadOutboundTouches,
  logLeadActivity,
  updateLeadConsent,
} from '@/modules/sms/revops/api'
import { EnrolLeadDialog } from '@/modules/sms/revops/components/EnrolLeadDialog'
import {
  INTENT_TONE,
  OFFER_TONE,
  SOURCE_LABEL,
  STAGE_LABEL,
  STAGE_TONE,
  TOUCH_TONE,
  consentSummary,
  daysSinceContact,
  formatAmount,
  formatDate,
  formatDateTime,
} from '@/modules/sms/revops/presentation'
import type {
  EnrollLeadResponse,
  LeadActivityRead,
  LeadOutboundTouch,
  ScholarshipOfferRead,
} from '@/modules/sms/revops/types'

interface Props {
  org_id: number
  orgslug: string
  leadId: number
}

export default function LeadDetailClient({ leadId }: Props) {
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [actionNote, setActionNote] = useState<string | null>(null)
  const [enrolled, setEnrolled] = useState<EnrollLeadResponse | null>(null)

  const lead = useApiResource(() => getLead(leadId), [leadId], { isEmpty: () => false })
  const conversation = useApiResource(() => getLeadConversation(leadId), [leadId], {
    isEmpty: (d) => d.turns.length === 0,
  })
  const touches = useApiResource(() => getLeadOutboundTouches(leadId), [leadId], {
    isEmpty: (d) => d.touches.length === 0,
  })

  const data = lead.data
  const consent = data ? consentSummary(data) : null
  const days = data ? daysSinceContact(data) : null

  async function run(fn: () => Promise<unknown>, ok: string) {
    setBusy(true)
    setActionNote(null)
    try {
      await fn()
      setActionNote(ok)
      lead.refetch()
    } catch (err) {
      // These endpoints REFUSE rather than invent -- a lead with no campus
      // raises MissingSchoolIdentity and comes back as a 4xx naming the fix.
      // Showing it verbatim is how the operator learns what to configure.
      setActionNote(
        err instanceof ApiError
          ? err.kind === 'permission_denied'
            ? 'You do not have access to do that.'
            : err.message
          : 'That did not work. Try again.'
      )
    } finally {
      setBusy(false)
    }
  }

  return (
    <DashPageShell
      title={data ? data.student_name : `Lead #${leadId}`}
      description={
        data
          ? `${data.grade_applying_for} · enquiry from ${SOURCE_LABEL[data.source] ?? data.source} · parent ${data.parent_name}`
          : 'Loading lead…'
      }
      breadcrumbs={
        <Link
          href="/dash/admissions/leads"
          className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-900"
        >
          <ArrowLeft className="size-4" /> All leads
        </Link>
      }
      action={
        data ? (
          <div className="flex items-center gap-2">
            <button
              type="button"
              id="lead-rescore"
              className={LH_SECONDARY_BUTTON}
              disabled={busy}
              onClick={() => run(() => aiQualifyLead(leadId), 'Lead re-scored.')}
            >
              <Sparkles className="size-4" /> <span>Re-score</span>
            </button>
            <EnrolLeadDialog
              lead={data}
              onEnrolled={(res) => {
                setEnrolled(res)
                lead.refetch()
              }}
            />
          </div>
        ) : undefined
      }
    >
      {/* Enrolment outcome -- the seam into the school proper. `already_provisioned`
          is reported honestly so a repeat call never looks like a duplicate. */}
      {enrolled && (
        <SectionCard
          title={enrolled.already_provisioned ? 'Already enrolled' : 'Enrolled'}
          icon={<BadgeCheck className="size-4 text-emerald-600" />}
        >
          <p className="text-sm text-gray-700">
            {enrolled.already_provisioned
              ? 'This lead was already provisioned. No duplicate student was created.'
              : 'Student account created, Student role granted, and placed in a class section.'}{' '}
            <Link href="/dash/campus#sections" className="font-medium underline">
              View in Campus
            </Link>
          </p>
          <p className="mt-1 text-xs text-gray-500">
            Student #{enrolled.student_id} · enrolment #{enrolled.enrollment_id}
          </p>
        </SectionCard>
      )}

      <StatGrid
        state={lead.status === 'loading' ? 'loading' : 'success'}
        columns={4}
        items={[
          {
            label: 'Stage',
            value: data ? STAGE_LABEL[data.stage] : '—',
            icon: ClipboardList,
            tone: data ? (STAGE_TONE[data.stage] === 'critical' ? 'critical' : 'neutral') : 'neutral',
          },
          {
            label: 'Score',
            value: data?.lead_score ?? '—',
            icon: Sparkles,
            tone: 'neutral',
          },
          {
            label: 'Intent',
            value: data?.intent_level ?? '—',
            icon: Users,
            tone: data ? (INTENT_TONE[data.intent_level] ?? 'neutral') : 'neutral',
          },
          {
            label: 'Since contact',
            // null means we genuinely do not know, which is not "0 days ago".
            value: days === null ? 'Unknown' : `${days}d`,
            icon: Phone,
            tone: days !== null && days > 7 ? 'caution' : 'neutral',
          },
        ]}
      />

      <SectionCard
        title="Contact & consent"
        description="Outbound automation is gated on these flags server-side."
        icon={<ShieldCheck className="size-4 text-gray-500" />}
        state={lead.status}
        error={lead.error}
        onRetry={lead.refetch}
      >
        {data && consent && (
          <div className="grid gap-4 sm:grid-cols-2">
            <dl className="space-y-2 text-sm">
              <div className="flex gap-2">
                <dt className="w-28 text-gray-500">Parent</dt>
                <dd className="text-gray-900">{data.parent_name}</dd>
              </div>
              <div className="flex gap-2">
                <dt className="w-28 text-gray-500">Email</dt>
                <dd className="text-gray-900">{data.email}</dd>
              </div>
              <div className="flex gap-2">
                <dt className="w-28 text-gray-500">Phone</dt>
                <dd className="text-gray-900">{data.phone}</dd>
              </div>
              <div className="flex gap-2">
                <dt className="w-28 text-gray-500">Enquired</dt>
                <dd className="text-gray-900">{formatDate(data.created_at)}</dd>
              </div>
            </dl>

            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <StatusChip
                  label={consent.blocked ? 'Outbound blocked' : `Consented: ${consent.label}`}
                  tone={consent.tone}
                />
              </div>
              {consent.blocked && (
                <p className="text-sm text-gray-600">
                  This family has not consented on any channel, so automated outreach will not
                  contact them. Record their decision below once you have asked.
                </p>
              )}
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  id="lead-consent-email"
                  className={LH_SECONDARY_BUTTON}
                  disabled={busy}
                  onClick={() =>
                    run(
                      () =>
                        updateLeadConsent(leadId, {
                          email_consent: !data.email_consent,
                          reason: 'Updated by admissions officer',
                        }),
                      'Email consent updated.'
                    )
                  }
                >
                  <span>{data.email_consent ? 'Withdraw email' : 'Record email consent'}</span>
                </button>
                <button
                  type="button"
                  id="lead-consent-whatsapp"
                  className={LH_SECONDARY_BUTTON}
                  disabled={busy}
                  onClick={() =>
                    run(
                      () =>
                        updateLeadConsent(leadId, {
                          whatsapp_consent: !data.whatsapp_consent,
                          reason: 'Updated by admissions officer',
                        }),
                      'WhatsApp consent updated.'
                    )
                  }
                >
                  <span>
                    {data.whatsapp_consent ? 'Withdraw WhatsApp' : 'Record WhatsApp consent'}
                  </span>
                </button>
              </div>
            </div>
          </div>
        )}
        {actionNote && <p className="mt-3 text-sm text-gray-600">{actionNote}</p>}
      </SectionCard>

      <SectionCard
        title="Offers"
        description="Issued from this lead."
        icon={<Send className="size-4 text-gray-500" />}
        state={lead.status === 'success' && (data?.offers ?? []).length === 0 ? 'empty' : lead.status}
        error={lead.error}
        onRetry={lead.refetch}
        emptyTitle="No offers yet"
        emptyDescription="No scholarship or tuition offer has been issued to this family."
      >
        <DataTable
          rows={data?.offers ?? []}
          rowKey={(o: ScholarshipOfferRead) => o.id}
          state="success"
          columns={[
            { key: 'id', header: 'Offer', render: (o) => `#${o.id}` },
            {
              key: 'discount',
              header: 'Discount',
              align: 'right',
              render: (o) => `${o.tuition_discount_percentage}%`,
            },
            {
              key: 'amount',
              header: 'Final tuition',
              align: 'right',
              render: (o) => formatAmount(o.final_tuition_amount),
            },
            { key: 'valid', header: 'Valid until', render: (o) => formatDate(o.valid_until) },
            {
              key: 'status',
              header: 'Status',
              render: (o) => <StatusChip label={o.status} tone={OFFER_TONE[o.status]} />,
            },
          ]}
        />
      </SectionCard>

      <SectionCard
        title="Conversation"
        description="Inbound messages and the replies drafted for them."
        icon={<MessageSquare className="size-4 text-gray-500" />}
        state={conversation.status}
        error={conversation.error}
        onRetry={conversation.refetch}
        emptyTitle="No conversation yet"
        emptyDescription="Nothing has been received from or drafted for this family."
      >
        <ul className="space-y-3">
          {(conversation.data?.turns ?? []).map((t, i) => (
            <li
              key={`${t.created_at ?? i}-${i}`}
              className={`rounded-xl p-3 text-sm ${
                t.direction === 'INBOUND' ? 'bg-gray-50' : 'bg-blue-50'
              }`}
            >
              <div className="mb-1 flex items-center gap-2 text-xs text-gray-500">
                <StatusChip
                  label={t.direction === 'INBOUND' ? 'From family' : 'To family'}
                  tone={t.direction === 'INBOUND' ? 'neutral' : 'positive'}
                />
                {t.channel && <span>{t.channel}</span>}
                <span>{formatDateTime(t.created_at)}</span>
              </div>
              <p className="whitespace-pre-wrap text-gray-800">{t.message}</p>
            </li>
          ))}
        </ul>
      </SectionCard>

      <SectionCard
        title="Automated outreach"
        description="What the nurture runner actually attempted, and what happened to it."
        icon={<Send className="size-4 text-gray-500" />}
        state={touches.status}
        error={touches.error}
        onRetry={touches.refetch}
        emptyTitle="Nothing sent yet"
        emptyDescription="This lead is not in a nurture sequence, or no touch has come due."
      >
        <DataTable
          rows={touches.data?.touches ?? []}
          rowKey={(t: LeadOutboundTouch, i) => `${t.stage}-${t.channel}-${i}`}
          state="success"
          columns={[
            { key: 'stage', header: 'Stage', render: (t) => t.stage },
            { key: 'channel', header: 'Channel', render: (t) => t.channel },
            { key: 'subject', header: 'Subject', render: (t) => t.subject ?? '—' },
            {
              key: 'status',
              header: 'Outcome',
              render: (t) => <StatusChip label={t.status} tone={TOUCH_TONE[t.status]} />,
            },
            // The reason a message was suppressed is the point of this table,
            // so it gets its own column rather than a tooltip.
            { key: 'detail', header: 'Detail', render: (t) => t.detail ?? '—' },
            { key: 'at', header: 'When', render: (t) => formatDateTime(t.at) },
          ]}
        />
      </SectionCard>

      <SectionCard
        title="Activity"
        description="Calls, notes, tours and stage changes."
        icon={<ClipboardList className="size-4 text-gray-500" />}
        state={lead.status === 'success' && (data?.activities ?? []).length === 0 ? 'empty' : lead.status}
        error={lead.error}
        onRetry={lead.refetch}
        emptyTitle="No activity logged"
        emptyDescription="Log a call or a note below to start the trail."
      >
        <DataTable
          rows={data?.activities ?? []}
          rowKey={(a: LeadActivityRead) => a.id}
          state="success"
          columns={[
            { key: 'type', header: 'Type', render: (a) => <StatusChip label={a.activity_type} tone="neutral" /> },
            { key: 'summary', header: 'Summary', render: (a) => a.summary },
            { key: 'at', header: 'When', render: (a) => formatDateTime(a.created_at) },
          ]}
        />

        <form
          className="mt-4 flex flex-wrap items-end gap-2"
          onSubmit={(e) => {
            e.preventDefault()
            if (!note.trim()) return
            run(
              () => logLeadActivity(leadId, { activity_type: 'NOTE', summary: note.trim() }),
              'Note logged.'
            ).then(() => setNote(''))
          }}
        >
          <label className="flex flex-1 flex-col gap-1.5">
            <span className="text-xs font-medium text-gray-500">Log a note</span>
            <input
              id="lead-note"
              className={LH_INPUT}
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Called mother, tour booked for Tuesday"
            />
          </label>
          <button type="submit" className={LH_SECONDARY_BUTTON} disabled={busy || !note.trim()}>
            <span>Log</span>
          </button>
        </form>
      </SectionCard>
    </DashPageShell>
  )
}
