'use client'

/**
 * Campaigns -- segment-level outreach planning.
 *
 * Two things this screen is deliberate about:
 *
 * 1. It PROPOSES. `POST /revops/agents/campaign/plan` returns
 *    `status: 'PROPOSED'` and contacts nobody (revops_agents.py:148).
 *    Delivery is the hourly nurture runner's job. Nothing here has a Send
 *    button, because there is no send endpoint and inventing one in the UI
 *    would imply a capability the system does not have.
 *
 * 2. Consent exclusions are shown, not hidden. Outbound is opt-IN for
 *    campaigns -- stricter than the SDR reply path -- so a family without
 *    explicit consent for the channel is excluded and COUNTED. A planner who
 *    cannot see that 40 of their 60 families are unreachable will draw the
 *    wrong conclusion about why a campaign underperformed.
 *
 * Copy drafting is per-lead (`POST /revops/agents/copy/{id}`), so it lives on
 * the lead page rather than here.
 */

import { useState } from 'react'
import { Ban, Megaphone, Target, Users } from 'lucide-react'
import {
  DashPageShell,
  DataTable,
  LH_INPUT,
  LH_PRIMARY_BUTTON,
  SectionCard,
  StatGrid,
  StatusChip,
} from '@/components/widgets'
import { ApiError } from '@/lib/api/api-client'
import { useSchoolSession } from '@/lib/api/useSchoolSession'
import { planCampaign } from '@/modules/sms/revops/api'
import { STAGE_LABEL } from '@/modules/sms/revops/presentation'
import type { CampaignPlan, LeadStage } from '@/modules/sms/revops/types'

interface Props {
  org_id: number
  orgslug: string
}

const CHANNELS = ['email', 'whatsapp'] as const

export default function AdmissionsCampaignsClient({ orgslug }: Props) {
  const { session } = useSchoolSession()
  const campusId = session?.campus_id ?? undefined

  const [channel, setChannel] = useState<string>('email')
  const [name, setName] = useState('')
  const [minScore, setMinScore] = useState('')
  const [plan, setPlan] = useState<CampaignPlan | null>(null)
  const [planning, setPlanning] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handlePlan(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setPlanning(true)
    setError(null)
    try {
      setPlan(
        await planCampaign({
          channel,
          campaign_name: name.trim() || null,
          min_score: minScore ? Number(minScore) : null,
          campus_id: campusId ?? null,
        })
      )
    } catch (err) {
      // The planner refuses with an actionable reason rather than inventing a
      // segment; show it verbatim.
      setError(
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

  const audience = plan?.audience

  return (
    <DashPageShell
      module="admissions"
      title="Campaigns"
      description="Plan a segment-level outreach campaign. Planning proposes an audience and an angle — it never contacts anyone."
    >
      <SectionCard
        title="Plan a campaign"
        description="Segment by channel and score. The result is a proposal you can act on, not a send."
        icon={<Target className="size-4 text-gray-500" />}
      >
        <form className="flex flex-wrap items-end gap-3" onSubmit={handlePlan}>
          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-medium text-gray-500">Campaign name</span>
            <input
              id="campaign-name"
              className={LH_INPUT}
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Optional"
            />
          </label>
          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-medium text-gray-500">Channel</span>
            <select
              id="campaign-channel"
              className={LH_INPUT}
              value={channel}
              onChange={(e) => setChannel(e.target.value)}
            >
              {CHANNELS.map((c) => (
                <option key={c} value={c}>
                  {c === 'email' ? 'Email' : 'WhatsApp'}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-medium text-gray-500">Minimum score</span>
            <input
              id="campaign-min-score"
              type="number"
              min={0}
              max={100}
              className={LH_INPUT}
              value={minScore}
              onChange={(e) => setMinScore(e.target.value)}
              placeholder="Any"
            />
          </label>
          <button type="submit" className={LH_PRIMARY_BUTTON} disabled={planning}>
            <Megaphone className="size-4" />
            <span>{planning ? 'Planning…' : 'Plan campaign'}</span>
          </button>
        </form>
        {error && <p className="mt-3 text-sm text-rose-600">{error}</p>}
      </SectionCard>

      {plan && audience && (
        <>
          <StatGrid
            columns={4}
            items={[
              { label: 'Eligible', value: audience.eligible_count, icon: Users, tone: 'positive' },
              {
                label: 'No consent',
                value: audience.excluded_no_consent,
                icon: Ban,
                tone: audience.excluded_no_consent > 0 ? 'caution' : 'neutral',
              },
              {
                label: 'Excluded by stage',
                value: audience.excluded_by_stage,
                icon: Target,
                tone: 'neutral',
              },
              {
                label: 'Excluded by filter',
                value: audience.excluded_by_filter,
                icon: Target,
                tone: 'neutral',
              },
            ]}
          />

          <SectionCard
            title={plan.campaign_name}
            description={plan.note}
            icon={<Megaphone className="size-4 text-gray-500" />}
            action={<StatusChip label={plan.status} tone="caution" />}
          >
            <dl className="grid gap-3 text-sm sm:grid-cols-2">
              <div>
                <dt className="text-gray-500">Angle</dt>
                <dd className="text-gray-900">{plan.angle}</dd>
              </div>
              <div>
                <dt className="text-gray-500">Timing</dt>
                <dd className="text-gray-900">{plan.timing}</dd>
              </div>
              <div>
                <dt className="text-gray-500">Channel</dt>
                <dd className="text-gray-900">{plan.channel}</dd>
              </div>
              <div>
                <dt className="text-gray-500">Dominant stage</dt>
                <dd className="text-gray-900">
                  {plan.dominant_stage
                    ? STAGE_LABEL[plan.dominant_stage as LeadStage] ?? plan.dominant_stage
                    : '—'}
                </dd>
              </div>
            </dl>

            {audience.excluded_no_consent > 0 && (
              <p className="mt-4 rounded-xl bg-amber-50 p-3 text-sm text-amber-900">
                {audience.excluded_no_consent} famil
                {audience.excluded_no_consent === 1 ? 'y has' : 'ies have'} not consented to{' '}
                {plan.channel} and {audience.excluded_no_consent === 1 ? 'is' : 'are'} excluded from
                this campaign. They must be asked before they can be contacted.
              </p>
            )}

            {plan.warnings.length > 0 && (
              <ul className="mt-3 space-y-1 text-sm text-gray-600">
                {plan.warnings.map((w, i) => (
                  <li key={i}>• {w}</li>
                ))}
              </ul>
            )}
          </SectionCard>

          <SectionCard
            title="Stage mix"
            description="Where the eligible audience currently sits in the funnel."
            icon={<Users className="size-4 text-gray-500" />}
            state={Object.keys(plan.stage_mix).length === 0 ? 'empty' : 'success'}
            emptyTitle="No eligible leads"
            emptyDescription="This segment matched nobody who has consented on this channel."
          >
            <DataTable
              rows={Object.entries(plan.stage_mix).map(([stage, count]) => ({ stage, count }))}
              rowKey={(r) => r.stage}
              state="success"
              columns={[
                {
                  key: 'stage',
                  header: 'Stage',
                  render: (r) => STAGE_LABEL[r.stage as LeadStage] ?? r.stage,
                },
                { key: 'count', header: 'Leads', align: 'right', render: (r) => r.count },
              ]}
            />
          </SectionCard>
        </>
      )}
    </DashPageShell>
  )
}
