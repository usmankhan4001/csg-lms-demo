'use client'

/**
 * M30 — RevOps admin configuration.
 *
 * Scoring weights, nurture cadence and consent policy were hardcoded Python
 * constants until today's backend landed, and the backend alone did not solve
 * the problem: a school still could not change what "qualified" means for its
 * own intake without a developer. This is that screen.
 *
 * The single most important thing it does is show WHERE each group's values
 * come from. The backend resolves campus -> org -> code default and reports
 * which layer won; an admin editing what they believe is their campus's
 * setting, while actually looking at an inherited org default, is the worst
 * failure this screen can have.
 */

import { useEffect, useMemo, useState } from 'react'
import { Bot, MessageSquare, ShieldCheck, SlidersHorizontal } from 'lucide-react'
import {
  DashPageShell,
  LH_INPUT,
  LH_PRIMARY_BUTTON,
  SectionCard,
  StatusChip,
} from '@/components/widgets'
import { ApiError } from '@/lib/api/api-client'
import { useApiResource } from '@/lib/api/useApiResource'
import { useSchoolSession } from '@/lib/api/useSchoolSession'
import { listCampuses } from '@/modules/sms/campus/api'
import { getRevOpsConfig, updateRevOpsConfigGroup } from '@/modules/sms/revops-admin/api'
import {
  describeConfigSource,
  describeReviewGate,
  scoringWeightTotal,
} from '@/modules/sms/revops-admin/presentation'
import type {
  ConsentPolicySettings,
  LeadScoringSettings,
  NurtureSettings,
  ResolvedRevOpsGroup,
  RevOpsConfigGroupKey,
} from '@/modules/sms/revops-admin/types'

interface RevOpsConfigClientProps {
  org_id: number
  orgslug: string
}

/** The inheritance badge plus the sentence explaining what saving will do. */
function SourceBanner({ group }: { group: ResolvedRevOpsGroup }) {
  const meta = describeConfigSource(group.source)
  return (
    <div className="mb-4 flex flex-col gap-1.5 rounded-lg bg-gray-50 px-3 py-2.5">
      <div className="flex items-center gap-2">
        <StatusChip label={meta.label} tone={meta.tone} />
        {group.updated_at && (
          <span className="text-xs text-gray-500">
            Last changed {new Date(group.updated_at).toLocaleDateString()}
          </span>
        )}
      </div>
      <p className="text-xs text-gray-600">{meta.explanation}</p>
    </div>
  )
}

function NumberField({
  id,
  label,
  value,
  onChange,
  help,
  max = 100,
}: {
  id: string
  label: string
  value: number
  onChange: (n: number) => void
  help?: string
  max?: number
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-sm font-medium text-gray-700">
        {label}
      </label>
      <input
        id={id}
        type="number"
        min={0}
        max={max}
        step="0.5"
        className={LH_INPUT}
        value={Number.isFinite(value) ? value : 0}
        onChange={(e) => onChange(Number(e.target.value))}
      />
      {help && <p className="text-xs text-gray-400">{help}</p>}
    </div>
  )
}

export default function RevOpsConfigClient({ org_id }: RevOpsConfigClientProps) {
  const { session } = useSchoolSession()
  const [campusId, setCampusId] = useState<number | undefined>(undefined)
  const [saving, setSaving] = useState<RevOpsConfigGroupKey | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState<RevOpsConfigGroupKey | null>(null)

  const campuses = useApiResource(() => listCampuses({ orgId: org_id, isActive: true }), [org_id], {
    isEmpty: (d) => d.length === 0,
  })

  // A campus-bound admin is narrowed server-side regardless of what is asked
  // for, so their own campus is the honest default here too.
  const effectiveCampusId = campusId ?? session?.campus_id ?? undefined

  const config = useApiResource(
    () => getRevOpsConfig(effectiveCampusId),
    [effectiveCampusId],
    { isEmpty: (d) => d.groups.length === 0 }
  )

  const groups = useMemo(() => {
    const map = new Map<RevOpsConfigGroupKey, ResolvedRevOpsGroup>()
    for (const g of config.data?.groups ?? []) map.set(g.group, g)
    return map
  }, [config.data])

  const scoringGroup = groups.get('lead_scoring')
  const nurtureGroup = groups.get('nurture')
  const consentGroup = groups.get('consent_policy')

  // Local edit buffers, re-seeded whenever the resolved values change.
  const [scoring, setScoring] = useState<LeadScoringSettings | null>(null)
  const [nurture, setNurture] = useState<NurtureSettings | null>(null)
  const [consent, setConsent] = useState<ConsentPolicySettings | null>(null)

  useEffect(() => {
    if (scoringGroup) setScoring(scoringGroup.values as unknown as LeadScoringSettings)
  }, [scoringGroup])
  useEffect(() => {
    if (nurtureGroup) setNurture(nurtureGroup.values as unknown as NurtureSettings)
  }, [nurtureGroup])
  useEffect(() => {
    if (consentGroup) setConsent(consentGroup.values as unknown as ConsentPolicySettings)
  }, [consentGroup])

  async function save(group: RevOpsConfigGroupKey, values: Record<string, unknown>) {
    setSaving(group)
    setError(null)
    setSaved(null)
    try {
      await updateRevOpsConfigGroup(group, values, effectiveCampusId)
      setSaved(group)
      config.refetch()
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.kind === 'permission_denied'
            ? 'You need school-admin access to change this, and a campus-bound admin cannot write the organisation-wide default.'
            : err.message
          : 'Could not save. Try again.'
      )
    } finally {
      setSaving(null)
    }
  }

  const weightTotal = scoring ? scoringWeightTotal(scoring) : 0
  const reviewGate = scoring ? describeReviewGate(scoring.human_review_below_score) : null

  return (
    <DashPageShell
      title="Agent configuration"
      description="How the admissions agents score, chase and obtain consent. Set per campus, inherited from the organisation, or left on the built-in defaults."
      module="revops"
    >
      {(campuses.data ?? []).length > 1 && (
        <label className="flex w-fit flex-col gap-1.5">
          <span className="text-xs font-medium text-gray-500">Configuring</span>
          <select
            id="revops-config-campus"
            className={LH_INPUT}
            value={effectiveCampusId ?? ''}
            onChange={(e) => setCampusId(e.target.value ? Number(e.target.value) : undefined)}
          >
            <option value="">Whole organisation</option>
            {(campuses.data ?? []).map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </label>
      )}

      {error && (
        <div className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div>
      )}

      {/* ---------------------------------------------------------------- */}
      <SectionCard
        id="lead-scoring"
        title="Lead scoring"
        description="What makes a lead hot, warm or cold for this school."
        icon={<SlidersHorizontal className="size-4 text-gray-500" />}
        state={config.status === 'loading' ? 'loading' : config.status}
        error={config.error}
        onRetry={config.refetch}
        emptyTitle="No scoring configuration"
        emptyDescription="The agents are running on their built-in weights."
      >
        {scoringGroup && scoring && (
          <div className="flex flex-col gap-4">
            <SourceBanner group={scoringGroup} />

            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <NumberField
                id="w-completeness"
                label="Completeness"
                value={scoring.weight_completeness}
                onChange={(n) => setScoring({ ...scoring, weight_completeness: n })}
              />
              <NumberField
                id="w-responsiveness"
                label="Responsiveness"
                value={scoring.weight_responsiveness}
                onChange={(n) => setScoring({ ...scoring, weight_responsiveness: n })}
              />
              <NumberField
                id="w-grade-demand"
                label="Grade demand"
                value={scoring.weight_grade_demand}
                onChange={(n) => setScoring({ ...scoring, weight_grade_demand: n })}
              />
              <NumberField
                id="w-budget-fit"
                label="Budget fit"
                value={scoring.weight_budget_fit}
                onChange={(n) => setScoring({ ...scoring, weight_budget_fit: n })}
              />
              <NumberField
                id="w-timeline"
                label="Timeline"
                value={scoring.weight_timeline}
                onChange={(n) => setScoring({ ...scoring, weight_timeline: n })}
              />
            </div>

            {/*
              The weights are a ratio, not a percentage of 100. Saying so
              explicitly stops an admin reading a 60-point total as "40 points
              missing" and inventing weight to fill a gap that does not exist.
            */}
            <p className="text-xs text-gray-500">
              These five weights total <strong>{weightTotal}</strong>, which becomes the highest
              score a lead can reach. They are a ratio, not a percentage — a total other than 100
              is not an error, it just changes the ceiling every score is measured against.
            </p>

            <div className="grid gap-4 sm:grid-cols-2">
              <NumberField
                id="hot-threshold"
                label="Hot at or above"
                value={scoring.hot_threshold}
                onChange={(n) => setScoring({ ...scoring, hot_threshold: n })}
              />
              <NumberField
                id="warm-threshold"
                label="Warm at or above"
                value={scoring.warm_threshold}
                onChange={(n) => setScoring({ ...scoring, warm_threshold: n })}
              />
            </div>

            <div className="flex flex-col gap-1.5 rounded-lg bg-gray-50 px-3 py-2.5">
              <NumberField
                id="human-review"
                label="Hold for human review below"
                value={scoring.human_review_below_score}
                onChange={(n) => setScoring({ ...scoring, human_review_below_score: n })}
                help="0 means no gate — this is the shipped default."
              />
              {reviewGate && (
                <StatusChip
                  label={reviewGate.label}
                  tone={reviewGate.active ? 'positive' : 'neutral'}
                />
              )}
            </div>

            <div className="flex items-center gap-3">
              <button
                type="button"
                id="save-lead-scoring"
                className={LH_PRIMARY_BUTTON}
                disabled={saving === 'lead_scoring'}
                onClick={() =>
                  save('lead_scoring', scoring as unknown as Record<string, unknown>)
                }
              >
                <span>{saving === 'lead_scoring' ? 'Saving…' : 'Save scoring'}</span>
              </button>
              {saved === 'lead_scoring' && (
                <span className="text-sm text-emerald-700">Saved.</span>
              )}
            </div>
          </div>
        )}
      </SectionCard>

      {/* ---------------------------------------------------------------- */}
      <SectionCard
        id="nurture"
        title="Nurture cadence"
        description="When each follow-up goes out, on which channel, and whether it runs at all."
        icon={<MessageSquare className="size-4 text-gray-500" />}
        state={config.status === 'loading' ? 'loading' : config.status}
        error={config.error}
        onRetry={config.refetch}
        emptyTitle="No nurture configuration"
        emptyDescription="The drip sequence is running on its built-in schedule."
      >
        {nurtureGroup && nurture && (
          <div className="flex flex-col gap-4">
            <SourceBanner group={nurtureGroup} />

            {/*
              The message COPY is deliberately not editable. Saying so here
              stops an admin hunting for a text field that does not exist, and
              explains why the omission is on purpose rather than unfinished.
            */}
            <div className="rounded-lg bg-blue-50 px-3 py-2.5 text-xs text-blue-900">
              <strong>The message wording is not editable here.</strong> Each stage&apos;s text is
              generated from your school&apos;s own record — its real name, campus and contact
              details — by code that refuses to send at all if those are missing, rather than
              inventing a school that does not exist. You control the timing, the channel and
              whether a stage runs; the words stay under that guard.
            </div>

            <div className="flex flex-col gap-3">
              {nurture.stages.map((stage, idx) => (
                <div
                  key={stage.stage}
                  className="flex flex-wrap items-end gap-4 rounded-lg bg-white nice-shadow p-3"
                >
                  <span className="text-sm font-medium text-gray-700">Stage {stage.stage}</span>
                  <div className="flex flex-col gap-1.5">
                    <label
                      htmlFor={`stage-${stage.stage}-day`}
                      className="text-xs font-medium text-gray-500"
                    >
                      Day
                    </label>
                    <input
                      id={`stage-${stage.stage}-day`}
                      type="number"
                      min={0}
                      className={LH_INPUT}
                      value={stage.day}
                      onChange={(e) => {
                        const stages = [...nurture.stages]
                        stages[idx] = { ...stage, day: Number(e.target.value) }
                        setNurture({ ...nurture, stages })
                      }}
                    />
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <label
                      htmlFor={`stage-${stage.stage}-channel`}
                      className="text-xs font-medium text-gray-500"
                    >
                      Channel
                    </label>
                    <input
                      id={`stage-${stage.stage}-channel`}
                      className={LH_INPUT}
                      value={stage.channel}
                      onChange={(e) => {
                        const stages = [...nurture.stages]
                        stages[idx] = { ...stage, channel: e.target.value }
                        setNurture({ ...nurture, stages })
                      }}
                    />
                  </div>
                  <label className="flex items-center gap-2 text-sm text-gray-700">
                    <input
                      id={`stage-${stage.stage}-enabled`}
                      type="checkbox"
                      checked={stage.enabled}
                      onChange={(e) => {
                        const stages = [...nurture.stages]
                        stages[idx] = { ...stage, enabled: e.target.checked }
                        setNurture({ ...nurture, stages })
                      }}
                    />
                    <span>Enabled</span>
                  </label>
                </div>
              ))}
            </div>

            <div className="flex items-center gap-3">
              <button
                type="button"
                id="save-nurture"
                className={LH_PRIMARY_BUTTON}
                disabled={saving === 'nurture'}
                onClick={() => save('nurture', nurture as unknown as Record<string, unknown>)}
              >
                <span>{saving === 'nurture' ? 'Saving…' : 'Save cadence'}</span>
              </button>
              {saved === 'nurture' && <span className="text-sm text-emerald-700">Saved.</span>}
            </div>
          </div>
        )}
      </SectionCard>

      {/* ---------------------------------------------------------------- */}
      <SectionCard
        id="consent-policy"
        title="Consent policy"
        description="Whether a family must opt in before the agents contact them, and on which channels consent is tracked."
        icon={<ShieldCheck className="size-4 text-gray-500" />}
        state={config.status === 'loading' ? 'loading' : config.status}
        error={config.error}
        onRetry={config.refetch}
        emptyTitle="No consent configuration"
        emptyDescription="Consent is being tracked on the built-in policy."
      >
        {consentGroup && consent && (
          <div className="flex flex-col gap-4">
            <SourceBanner group={consentGroup} />

            <label className="flex items-start gap-2 text-sm text-gray-700">
              <input
                id="require-opt-in"
                type="checkbox"
                className="mt-1"
                checked={consent.require_explicit_opt_in}
                onChange={(e) =>
                  setConsent({ ...consent, require_explicit_opt_in: e.target.checked })
                }
              />
              <span>
                <strong>Require an explicit opt-in before contacting a family.</strong>
                <span className="block text-xs text-gray-500">
                  With this off, a family whose consent is simply unrecorded may still be
                  contacted. A recorded refusal is always honoured either way.
                </span>
              </span>
            </label>

            <div className="flex flex-col gap-1.5">
              <label htmlFor="tracked-channels" className="text-sm font-medium text-gray-700">
                Channels where consent is tracked
              </label>
              <input
                id="tracked-channels"
                className={LH_INPUT}
                value={consent.consent_tracked_channels.join(', ')}
                onChange={(e) =>
                  setConsent({
                    ...consent,
                    consent_tracked_channels: e.target.value
                      .split(',')
                      .map((s) => s.trim())
                      .filter(Boolean),
                  })
                }
              />
              <p className="text-xs text-gray-400">Comma separated, e.g. email, whatsapp.</p>
            </div>

            <div className="flex items-center gap-3">
              <button
                type="button"
                id="save-consent"
                className={LH_PRIMARY_BUTTON}
                disabled={saving === 'consent_policy'}
                onClick={() =>
                  save('consent_policy', consent as unknown as Record<string, unknown>)
                }
              >
                <span>{saving === 'consent_policy' ? 'Saving…' : 'Save policy'}</span>
              </button>
              {saved === 'consent_policy' && (
                <span className="text-sm text-emerald-700">Saved.</span>
              )}
            </div>
          </div>
        )}
      </SectionCard>

      <p className="text-xs text-gray-400">
        <Bot className="mr-1 inline size-3" />
        These settings govern the automated agents only. A member of staff acting manually is
        never blocked by them.
      </p>
    </DashPageShell>
  )
}
