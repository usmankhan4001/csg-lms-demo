'use client'

/**
 * Admissions Insights -- the analytics/ops view of the recruitment funnel.
 *
 * Sits BESIDE the kanban at /dash/admissions rather than replacing it: the
 * kanban is for working individual leads, this is for reading the funnel as
 * a whole (where leads stall, how many convert, who can legally be contacted).
 *
 * Everything here is derived from the one real `GET /revops/leads/pipeline`
 * response the kanban already uses -- no separate analytics endpoint, so the
 * two views can never disagree about the same leads.
 *
 * Note on the funnel bar: it is drawn from stage counts, not from a
 * time-series, because the API returns current stage occupancy only. It is
 * therefore a snapshot of where leads sit right now, NOT a cohort conversion
 * curve, and is labelled that way rather than implying a trend the data
 * cannot support.
 */

import { useMemo, useState } from 'react'
import { Ban, Bot, Filter, ShieldCheck, TrendingUp, Users } from 'lucide-react'
import {
  DashPageShell,
  DataTable,
  LH_GHOST_BUTTON,
  LH_INPUT,
  LH_PRIMARY_BUTTON,
  SectionCard,
  StatGrid,
  StatusChip,
} from '@/components/widgets'
import { ApiError } from '@/lib/api/api-client'
import { useApiResource } from '@/lib/api/useApiResource'
import { useSchoolSession } from '@/lib/api/useSchoolSession'
import { listCampuses } from '@/modules/sms/campus/api'
import { getLeadPipeline, planCampaign } from '@/modules/sms/revops/api'
import { LeadDetailDialog } from '@/modules/sms/revops/components/LeadDetailDialog'
import { NewLeadDialog } from '@/modules/sms/revops/components/NewLeadDialog'
import type { CampaignPlan, LeadRead, LeadStage } from '@/modules/sms/revops/types'

interface RevOpsDashClientProps {
  org_id: number
  orgslug: string
}

// Stages that represent a lead still moving through the funnel, in order.
// ENROLLED / LOST / STALLED are terminal-or-parked and reported separately.
const ACTIVE_FUNNEL: LeadStage[] = [
  'NEW_INQUIRY',
  'CONTACTED',
  'TOUR_BOOKED',
  'ASSESSMENT_SCHEDULED',
  'OFFER_SENT',
] as LeadStage[]

const INTENT_TONE: Record<string, 'positive' | 'caution' | 'neutral'> = {
  HOT: 'positive',
  WARM: 'caution',
  COLD: 'neutral',
}

export default function RevOpsDashClient({ org_id }: RevOpsDashClientProps) {
  const { session } = useSchoolSession()
  const [campusId, setCampusId] = useState<number | undefined>(undefined)
  const [selectedLead, setSelectedLead] = useState<LeadRead | null>(null)

  const campuses = useApiResource(() => listCampuses({ orgId: org_id, isActive: true }), [org_id], {
    isEmpty: (d) => d.length === 0,
  })

  const effectiveCampusId = campusId ?? session?.campus_id ?? undefined

  const pipeline = useApiResource(
    () => getLeadPipeline(effectiveCampusId),
    [effectiveCampusId],
    { isEmpty: (d) => d.total_leads === 0 }
  )

  // Campaign planning: a proposal held in local state. Nothing is persisted
  // and no lead is contacted by running it.
  const [campaignChannel, setCampaignChannel] = useState('email')
  const [campaign, setCampaign] = useState<CampaignPlan | null>(null)
  const [planning, setPlanning] = useState(false)
  const [campaignError, setCampaignError] = useState<string | null>(null)

  async function handlePlanCampaign() {
    setPlanning(true)
    setCampaignError(null)
    try {
      setCampaign(
        await planCampaign({ channel: campaignChannel, campus_id: effectiveCampusId ?? null })
      )
    } catch (err) {
      // The planner can refuse with an actionable reason; show it verbatim
      // rather than collapsing it into a generic failure.
      setCampaignError(
        err instanceof ApiError
          ? err.kind === 'permission_denied'
            ? 'You do not have access to plan campaigns.'
            : err.message
          : 'Could not plan a campaign.'
      )
    } finally {
      setPlanning(false)
    }
  }

  const stats = useMemo(() => {
    const stages = pipeline.data?.stages ?? []
    const countFor = (s: string) => stages.find((g) => g.stage === s)?.count ?? 0
    const total = pipeline.data?.total_leads ?? 0
    const enrolled = countFor('ENROLLED')
    const lost = countFor('LOST')
    const stalled = countFor('STALLED')
    const decided = enrolled + lost
    return {
      total,
      enrolled,
      lost,
      stalled,
      // Conversion measured against DECIDED leads, not all leads: counting
      // still-in-progress inquiries as failures would understate it badly
      // early in an admissions cycle.
      conversion: decided > 0 ? (enrolled / decided) * 100 : null,
    }
  }, [pipeline.data])

  const allLeads: LeadRead[] = useMemo(
    () => (pipeline.data?.stages ?? []).flatMap((g) => g.leads),
    [pipeline.data]
  )

  // Highest-scoring leads still in play -- the ones worth a call today.
  const priorityLeads = useMemo(
    () =>
      allLeads
        .filter((l) => ACTIVE_FUNNEL.includes(l.stage))
        .sort((a, b) => b.lead_score - a.lead_score)
        .slice(0, 10),
    [allLeads]
  )

  const noConsentCount = allLeads.filter((l) => !l.whatsapp_consent && !l.email_consent).length

  const campusFilter =
    (campuses.data ?? []).length > 1 ? (
      <label className="flex items-center gap-2">
        <Filter className="size-4 text-gray-400" aria-hidden="true" />
        <span className="sr-only">Campus</span>
        <select
          id="revops-campus"
          className={LH_INPUT}
          value={effectiveCampusId ?? ''}
          onChange={(e) => setCampusId(e.target.value ? Number(e.target.value) : undefined)}
        >
          <option value="">All campuses</option>
          {(campuses.data ?? []).map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      </label>
    ) : null

  const headerActions = (
    <div className="flex flex-wrap items-center gap-3">
      {campusFilter}
      <NewLeadDialog campusId={effectiveCampusId} onCreated={pipeline.refetch} />
    </div>
  )

  return (
    <DashPageShell
      title="Admissions Insights"
      description="Funnel performance, lead quality and outreach consent across the recruitment pipeline."
      action={headerActions}
      module="revops"
    >
      <StatGrid
        state={pipeline.status === 'loading' ? 'loading' : 'success'}
        columns={4}
        items={[
          { label: 'Total leads', value: stats.total, icon: Users, tone: 'neutral' },
          { label: 'Enrolled', value: stats.enrolled, icon: TrendingUp, tone: 'positive' },
          {
            label: 'Conversion',
            value: stats.conversion !== null ? `${stats.conversion.toFixed(1)}%` : '—',
            icon: TrendingUp,
            tone: 'positive',
          },
          {
            label: 'Stalled',
            value: stats.stalled,
            icon: Ban,
            tone: stats.stalled > 0 ? 'caution' : 'neutral',
          },
        ]}
      />

      <SectionCard
        id="funnel"
        title="Where leads sit right now"
        description="Current stage occupancy — a snapshot, not a conversion curve over time."
        icon={<TrendingUp className="size-4 text-muted-foreground" />}
        state={pipeline.status}
        error={pipeline.error}
        onRetry={pipeline.refetch}
        emptyTitle="No leads yet"
        emptyDescription="Leads captured from the website, WhatsApp or campaigns will appear here."
      >
        <div className="flex flex-col gap-2.5">
          {(pipeline.data?.stages ?? []).map((group) => {
            const pct = stats.total > 0 ? (group.count / stats.total) * 100 : 0
            return (
              <div key={group.stage} className="flex items-center gap-3">
                <span className="w-48 shrink-0 truncate text-sm text-gray-600">
                  {group.stage_name}
                </span>
                <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-gray-100">
                  <div
                    className="h-full rounded-full bg-black/80"
                    style={{ width: `${Math.max(pct, group.count > 0 ? 2 : 0)}%` }}
                  />
                </div>
                <span className="w-10 shrink-0 text-end text-sm font-semibold tabular-nums">
                  {group.count}
                </span>
              </div>
            )
          })}
        </div>
      </SectionCard>

      <SectionCard
        id="priority"
        title="Highest-scoring open leads"
        description="Ranked by the 5-factor lead score. Only leads still active in the funnel."
        icon={<Users className="size-4 text-muted-foreground" />}
        state={pipeline.status === 'success' && priorityLeads.length === 0 ? 'empty' : pipeline.status}
        error={pipeline.error}
        onRetry={pipeline.refetch}
        emptyTitle="No open leads"
        emptyDescription="Every lead has been enrolled, lost or stalled."
      >
        <DataTable
          rows={priorityLeads}
          rowKey={(row) => row.id}
          state="success"
          columns={[
            {
              key: 'student',
              header: 'Student',
              render: (r) => (
                <button
                  type="button"
                  className="text-start font-medium text-gray-900 underline-offset-2 hover:underline"
                  onClick={() => setSelectedLead(r)}
                >
                  {r.student_name}
                </button>
              ),
            },
            { key: 'grade', header: 'Grade', render: (r) => r.grade_applying_for },
            { key: 'stage', header: 'Stage', render: (r) => <StatusChip label={r.stage.replace(/_/g, ' ')} tone="info" /> },
            {
              key: 'score',
              header: 'Score',
              align: 'right',
              render: (r) => <span className="tabular-nums font-semibold">{r.lead_score}</span>,
            },
            {
              key: 'intent',
              header: 'Intent',
              render: (r) => (
                <StatusChip label={r.intent_level} tone={INTENT_TONE[r.intent_level] ?? 'neutral'} />
              ),
            },
            { key: 'source', header: 'Source', render: (r) => r.source.replace(/_/g, ' ') },
            {
              key: 'open',
              header: '',
              align: 'right',
              render: (r) => (
                <button type="button" className={LH_GHOST_BUTTON} onClick={() => setSelectedLead(r)}>
                  Open
                </button>
              ),
            },
          ]}
        />
      </SectionCard>

      <SectionCard
        id="consent"
        title="Outreach consent"
        description="Automated WhatsApp and email nurture may only fire for leads who opted in."
        icon={<ShieldCheck className="size-4 text-muted-foreground" />}
        state={pipeline.status}
        error={pipeline.error}
        onRetry={pipeline.refetch}
        emptyTitle="No leads yet"
      >
        <div className="flex flex-col gap-3">
          {noConsentCount > 0 && (
            <p className="text-sm text-amber-700">
              {noConsentCount} lead{noConsentCount === 1 ? '' : 's'} have granted no contact consent
              at all — outbound automation is blocked for them.
            </p>
          )}
          <DataTable
            rows={allLeads.slice(0, 25)}
            rowKey={(row) => row.id}
            state="success"
            totalLabel={`Showing ${Math.min(allLeads.length, 25)} of ${allLeads.length}`}
            columns={[
              {
                key: 'student',
                header: 'Student',
                render: (r) => (
                  <button
                    type="button"
                    className="text-start font-medium text-gray-900 underline-offset-2 hover:underline"
                    onClick={() => setSelectedLead(r)}
                  >
                    {r.student_name}
                  </button>
                ),
              },
              { key: 'parent', header: 'Parent', render: (r) => r.parent_name },
              {
                key: 'wa',
                header: 'WhatsApp',
                render: (r) => (
                  <StatusChip
                    label={r.whatsapp_consent ? 'Opted in' : 'No consent'}
                    tone={r.whatsapp_consent ? 'positive' : 'neutral'}
                  />
                ),
              },
              {
                key: 'em',
                header: 'Email',
                render: (r) => (
                  <StatusChip
                    label={r.email_consent ? 'Opted in' : 'No consent'}
                    tone={r.email_consent ? 'positive' : 'neutral'}
                  />
                ),
              },
              {
                key: 'contacted',
                header: 'Last contacted',
                render: (r) =>
                  r.last_contacted_at ? new Date(r.last_contacted_at).toLocaleDateString() : '—',
              },
            ]}
          />
        </div>
      </SectionCard>

      {/* Campaign planning is segment-level, so it belongs here rather than
          in a per-lead dialog. Research briefs, SDR replies, copy drafting
          and nurture sequences are all per-lead and live in LeadDetailDialog. */}
      <SectionCard
        id="ai-agents"
        title="Campaign planner"
        description="Segment the funnel for an outreach campaign. Proposes only — nothing is sent."
        icon={<Bot className="size-4 text-muted-foreground" />}
      >
        <div className="mb-3 flex flex-wrap items-end gap-2">
          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-medium text-gray-500">Channel</span>
            <select
              id="campaign-channel"
              className={LH_INPUT}
              value={campaignChannel}
              onChange={(e) => setCampaignChannel(e.target.value)}
            >
              <option value="email">Email</option>
              <option value="whatsapp">WhatsApp</option>
            </select>
          </label>
          <button
            type="button"
            id="campaign-plan"
            className={LH_PRIMARY_BUTTON}
            onClick={handlePlanCampaign}
            disabled={planning}
          >
            <span>{planning ? 'Segmenting…' : 'Propose campaign'}</span>
          </button>
        </div>

        {campaignError && <p className="mb-2 text-sm text-rose-600">{campaignError}</p>}

        {campaign ? (
          <div className="flex flex-col gap-2 rounded-lg border border-gray-200 bg-white p-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-semibold text-gray-900">{campaign.campaign_name}</span>
              <StatusChip label={campaign.status} tone="info" />
              <span className="text-xs text-gray-500">via {campaign.channel}</span>
            </div>
            <p className="text-sm text-gray-700">{campaign.angle}</p>
            <p className="text-xs text-gray-500">{campaign.timing}</p>

            <div className="mt-1 flex flex-wrap gap-4 text-sm">
              <span>
                <span className="font-semibold tabular-nums text-gray-900">
                  {campaign.audience.eligible_count}
                </span>{' '}
                <span className="text-gray-500">eligible</span>
              </span>
              {/* Excluded-for-consent is surfaced, not hidden: outbound here
                  is opt-IN, so unknown consent is a block, and the operator
                  needs to see how much of the list that removes. */}
              <span>
                <span className="font-semibold tabular-nums text-amber-700">
                  {campaign.audience.excluded_no_consent}
                </span>{' '}
                <span className="text-gray-500">excluded — no consent</span>
              </span>
              <span>
                <span className="font-semibold tabular-nums text-gray-500">
                  {campaign.audience.excluded_by_stage}
                </span>{' '}
                <span className="text-gray-500">not targetable</span>
              </span>
            </div>

            {campaign.warnings.length > 0 && (
              <ul className="list-disc ps-5 text-xs text-amber-700">
                {campaign.warnings.map((w) => (
                  <li key={w}>{w}</li>
                ))}
              </ul>
            )}
            <p className="text-[11px] text-gray-400">{campaign.note}</p>
          </div>
        ) : (
          <p className="text-sm text-gray-600">
            Choose a channel and propose a campaign. Leads without explicit consent for that
            channel are excluded and counted — outbound is opt-in, so unknown consent is not
            treated as permission.
          </p>
        )}
      </SectionCard>

      {selectedLead && (
        <LeadDetailDialog
          lead={selectedLead}
          open={selectedLead !== null}
          onOpenChange={(next) => {
            if (!next) setSelectedLead(null)
          }}
          onChanged={pipeline.refetch}
        />
      )}
    </DashPageShell>
  )
}
