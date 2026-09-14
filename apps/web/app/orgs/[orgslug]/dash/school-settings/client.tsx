'use client'

/**
 * CSG School Settings -- the operator layer.
 *
 * Why this page exists: grading scales and fee policy were hardcoded Python
 * constants, so a school on a different grading scale or a different late-fee
 * policy needed a developer. This is where a school configures itself.
 *
 * The `source` badge on each group is the load-bearing bit of UI. "Using the
 * built-in default", "inherited from the organisation" and "set for this
 * campus" lead an admin to different actions, and hiding that distinction
 * would make an inherited value look like one this campus owns.
 *
 * Three groups are editable today (profile, grading, fees). The rest are
 * shown as explicitly not-yet-configurable rather than as controls that look
 * editable and silently do nothing.
 */

import { useState } from 'react'
import { Building2, GraduationCap, Receipt, Settings2 } from 'lucide-react'
import {
  DashPageShell,
  LH_INPUT,
  LH_PRIMARY_BUTTON,
  LH_SECONDARY_BUTTON,
  SchoolDialog,
  SchoolField,
  SectionCard,
  StatusChip,
} from '@/components/widgets'
import { ApiError } from '@/lib/api/api-client'
import { useApiResource } from '@/lib/api/useApiResource'
import { useSchoolSession } from '@/lib/api/useSchoolSession'
import { getSchoolSettings, updateSettingsGroup } from '@/modules/sms/settings/api'
import {
  GROUP_DESCRIPTIONS,
  GROUP_LABELS,
  type FeePolicyValues,
  type GradingPolicyValues,
  type ResolvedSettingsGroup,
  type SchoolProfileValues,
  type SettingsGroupKey,
  type SettingsSource,
} from '@/modules/sms/settings/types'

interface SchoolSettingsClientProps {
  org_id: number
  orgslug: string
}

const SOURCE_LABEL: Record<SettingsSource, string> = {
  CAMPUS: 'Set for this campus',
  ORG: 'Inherited from organisation',
  DEFAULT: 'Using built-in default',
}

const SOURCE_TONE: Record<SettingsSource, 'positive' | 'neutral' | 'caution'> = {
  CAMPUS: 'positive',
  ORG: 'neutral',
  DEFAULT: 'caution',
}

function describeError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.kind === 'permission_denied') {
      return 'You need school-admin access to change settings.'
    }
    // The API's 403 for a campus-bound admin editing org defaults, and its 422
    // naming the invalid field, are both worth showing verbatim.
    return err.message
  }
  return 'Could not save. Try again.'
}

export default function SchoolSettingsClient({ org_id }: SchoolSettingsClientProps) {
  const { session } = useSchoolSession()
  const [reloadKey, setReloadKey] = useState(0)

  const settings = useApiResource(
    () => getSchoolSettings(session?.campus_id ?? undefined),
    [session?.campus_id, reloadKey],
    { isEmpty: (d) => d.groups.length === 0 }
  )

  const refresh = () => setReloadKey((k) => k + 1)
  const groups = settings.data?.groups ?? []
  const byKey = (k: SettingsGroupKey) => groups.find((g) => g.group === k)

  // The scope the server actually resolved, not the one we asked for -- a
  // campus-bound admin is narrowed server-side regardless of the request.
  const scopeCampusId = settings.data?.campus_id ?? undefined

  return (
    <DashPageShell
      title="School settings"
      description="Grading scale, fee policy and school identity — the things a school sets once and every module then follows."
    >
      <SectionCard
        title="School profile"
        description={GROUP_DESCRIPTIONS.school_profile}
        icon={<Building2 className="size-4 text-gray-500" />}
        state={settings.status}
        error={settings.error}
        onRetry={settings.refetch}
        action={<SourceBadge group={byKey('school_profile')} />}
      >
        <SchoolProfileSection
          group={byKey('school_profile')}
          campusId={scopeCampusId}
          onSaved={refresh}
        />
      </SectionCard>

      <SectionCard
        title="Grading policy"
        description={GROUP_DESCRIPTIONS.grading_policy}
        icon={<GraduationCap className="size-4 text-gray-500" />}
        state={settings.status}
        error={settings.error}
        onRetry={settings.refetch}
        action={<SourceBadge group={byKey('grading_policy')} />}
      >
        <GradingPolicySection
          group={byKey('grading_policy')}
          campusId={scopeCampusId}
          onSaved={refresh}
        />
      </SectionCard>

      <SectionCard
        title="Fee policy"
        description={GROUP_DESCRIPTIONS.fee_policy}
        icon={<Receipt className="size-4 text-gray-500" />}
        state={settings.status}
        error={settings.error}
        onRetry={settings.refetch}
        action={<SourceBadge group={byKey('fee_policy')} />}
      >
        <FeePolicySection group={byKey('fee_policy')} campusId={scopeCampusId} onSaved={refresh} />
      </SectionCard>

      <SectionCard
        title="Not yet configurable"
        description="These groups are stored and served by the API, but have no editing screen yet. They currently use their built-in defaults."
        icon={<Settings2 className="size-4 text-gray-500" />}
        state={settings.status}
        error={settings.error}
      >
        <ul className="flex flex-col gap-2">
          {groups
            .filter((g) => !g.editable_in_ui)
            .map((g) => (
              <li key={g.group} className="flex items-start justify-between gap-4 text-sm">
                <div>
                  <p className="font-medium text-gray-800">{GROUP_LABELS[g.group]}</p>
                  <p className="text-xs text-gray-500">{GROUP_DESCRIPTIONS[g.group]}</p>
                </div>
                <StatusChip label={SOURCE_LABEL[g.source]} tone={SOURCE_TONE[g.source]} />
              </li>
            ))}
        </ul>
      </SectionCard>
    </DashPageShell>
  )
}

function SourceBadge({ group }: { group?: ResolvedSettingsGroup }) {
  if (!group) return null
  return <StatusChip label={SOURCE_LABEL[group.source]} tone={SOURCE_TONE[group.source]} />
}

/** Shared save plumbing: every section needs the same error/loading handling. */
function useGroupSave(group: SettingsGroupKey, campusId: number | undefined, onSaved: () => void) {
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [open, setOpen] = useState(false)

  async function save(values: Record<string, any>) {
    setSaving(true)
    setError(null)
    try {
      await updateSettingsGroup(group, values, campusId)
      setOpen(false)
      onSaved()
    } catch (err) {
      setError(describeError(err))
    } finally {
      setSaving(false)
    }
  }

  return { saving, error, setError, open, setOpen, save }
}

function ReadOnlyRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-1.5 text-sm">
      <span className="text-gray-500">{label}</span>
      <span className="font-medium text-gray-900">{value}</span>
    </div>
  )
}

function SchoolProfileSection({
  group,
  campusId,
  onSaved,
}: {
  group?: ResolvedSettingsGroup
  campusId?: number
  onSaved: () => void
}) {
  const v = (group?.values ?? {}) as SchoolProfileValues
  const { saving, error, open, setOpen, save } = useGroupSave('school_profile', campusId, onSaved)

  // Unset fields render as "Not set", never as a plausible placeholder: this
  // codebase has had invented school names and principals torn out of outbound
  // documents, and a blank an admin can see is safer than a convincing guess.
  const shown = (x: string | null | undefined) => x || <span className="text-gray-400">Not set</span>

  return (
    <div className="flex flex-col gap-3">
      <div>
        <ReadOnlyRow label="Legal name" value={shown(v.legal_name)} />
        <ReadOnlyRow label="Principal" value={shown(v.principal_name)} />
        <ReadOnlyRow label="Contact email" value={shown(v.contact_email)} />
        <ReadOnlyRow label="Contact phone" value={shown(v.contact_phone)} />
        <ReadOnlyRow label="Address" value={shown(v.address)} />
      </div>

      <SchoolDialog
        open={open}
        onOpenChange={setOpen}
        trigger={
          <button type="button" className={LH_SECONDARY_BUTTON}>
            <span>Edit profile</span>
          </button>
        }
        title="School profile"
        description="Used on report cards, transcripts and outbound messages."
        onSubmit={(e) => {
          e.preventDefault()
          const f = new FormData(e.currentTarget)
          const str = (k: string) => String(f.get(k) ?? '').trim() || null
          save({
            legal_name: str('legal_name'),
            logo_url: str('logo_url'),
            principal_name: str('principal_name'),
            contact_email: str('contact_email'),
            contact_phone: str('contact_phone'),
            address: str('address'),
          })
        }}
        footer={
          <button type="submit" disabled={saving} className={LH_PRIMARY_BUTTON}>
            <span>{saving ? 'Saving…' : 'Save'}</span>
          </button>
        }
      >
        <SchoolField id="legal_name" label="Legal name">
          <input id="legal_name" name="legal_name" className={LH_INPUT} defaultValue={v.legal_name ?? ''} />
        </SchoolField>
        <SchoolField id="principal_name" label="Principal">
          <input id="principal_name" name="principal_name" className={LH_INPUT} defaultValue={v.principal_name ?? ''} />
        </SchoolField>
        <SchoolField id="contact_email" label="Contact email">
          <input id="contact_email" name="contact_email" type="email" className={LH_INPUT} defaultValue={v.contact_email ?? ''} />
        </SchoolField>
        <SchoolField id="contact_phone" label="Contact phone">
          <input id="contact_phone" name="contact_phone" className={LH_INPUT} defaultValue={v.contact_phone ?? ''} />
        </SchoolField>
        <SchoolField id="logo_url" label="Logo URL" help="Shown on documents the school issues.">
          <input id="logo_url" name="logo_url" className={LH_INPUT} defaultValue={v.logo_url ?? ''} />
        </SchoolField>
        <SchoolField id="address" label="Address">
          <input id="address" name="address" className={LH_INPUT} defaultValue={v.address ?? ''} />
        </SchoolField>
        {error && <p className="text-sm text-rose-600">{error}</p>}
      </SchoolDialog>
    </div>
  )
}

function GradingPolicySection({
  group,
  campusId,
  onSaved,
}: {
  group?: ResolvedSettingsGroup
  campusId?: number
  onSaved: () => void
}) {
  const v = (group?.values ?? {}) as GradingPolicyValues
  const intervals = v.intervals ?? []
  const { saving, error, open, setOpen, save } = useGroupSave('grading_policy', campusId, onSaved)

  return (
    <div className="flex flex-col gap-3">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs uppercase tracking-wide text-gray-500">
              <th className="pb-2 font-medium">Grade</th>
              <th className="pb-2 font-medium">From</th>
              <th className="pb-2 font-medium">To</th>
              <th className="pb-2 text-right font-medium">GPA</th>
            </tr>
          </thead>
          <tbody>
            {intervals.map((i) => (
              <tr key={i.grade} className="border-t border-gray-100">
                <td className="py-1.5 font-medium text-gray-900">{i.grade}</td>
                <td className="py-1.5 text-gray-600">{i.min_percentage}%</td>
                <td className="py-1.5 text-gray-600">{i.max_percentage}%</td>
                <td className="py-1.5 text-right text-gray-900">{i.gpa_point}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <ReadOnlyRow label="Pass mark" value={`${v.pass_mark ?? '—'}%`} />

      <SchoolDialog
        open={open}
        onOpenChange={setOpen}
        trigger={
          <button type="button" className={LH_SECONDARY_BUTTON}>
            <span>Edit grading scale</span>
          </button>
        }
        title="Grading policy"
        description="Every percentage in the gradebook becomes a letter and a GPA point through this scale. Changing it changes how existing marks are reported."
        onSubmit={(e) => {
          e.preventDefault()
          const f = new FormData(e.currentTarget)
          const next = intervals.map((i) => ({
            grade: i.grade,
            min_percentage: Number(f.get(`min_${i.grade}`)),
            max_percentage: Number(f.get(`max_${i.grade}`)),
            gpa_point: Number(f.get(`gpa_${i.grade}`)),
          }))
          save({ intervals: next, pass_mark: Number(f.get('pass_mark')) })
        }}
        footer={
          <button type="submit" disabled={saving} className={LH_PRIMARY_BUTTON}>
            <span>{saving ? 'Saving…' : 'Save scale'}</span>
          </button>
        }
      >
        {intervals.map((i) => (
          <div key={i.grade} className="flex items-end gap-2">
            <div className="w-12 pb-2 text-sm font-medium text-gray-900">{i.grade}</div>
            <SchoolField id={`min_${i.grade}`} label="From %">
              <input id={`min_${i.grade}`} name={`min_${i.grade}`} type="number" step="0.01" className={LH_INPUT} defaultValue={i.min_percentage} />
            </SchoolField>
            <SchoolField id={`max_${i.grade}`} label="To %">
              <input id={`max_${i.grade}`} name={`max_${i.grade}`} type="number" step="0.01" className={LH_INPUT} defaultValue={i.max_percentage} />
            </SchoolField>
            <SchoolField id={`gpa_${i.grade}`} label="GPA">
              <input id={`gpa_${i.grade}`} name={`gpa_${i.grade}`} type="number" step="0.1" className={LH_INPUT} defaultValue={i.gpa_point} />
            </SchoolField>
          </div>
        ))}
        <SchoolField id="pass_mark" label="Pass mark (%)">
          <input id="pass_mark" name="pass_mark" type="number" step="0.01" className={LH_INPUT} defaultValue={v.pass_mark ?? 50} />
        </SchoolField>
        {error && <p className="text-sm text-rose-600">{error}</p>}
      </SchoolDialog>
    </div>
  )
}

function FeePolicySection({
  group,
  campusId,
  onSaved,
}: {
  group?: ResolvedSettingsGroup
  campusId?: number
  onSaved: () => void
}) {
  const v = (group?.values ?? {}) as FeePolicyValues
  const { saving, error, open, setOpen, save } = useGroupSave('fee_policy', campusId, onSaved)

  return (
    <div className="flex flex-col gap-3">
      <div>
        <ReadOnlyRow label="Late fee per period" value={`${v.late_fee_percent_per_period}%`} />
        <ReadOnlyRow label="Grace period" value={`${v.late_fee_grace_days} days`} />
        <ReadOnlyRow label="Period length" value={`${v.late_fee_period_days} days`} />
        <ReadOnlyRow label="Maximum late fee" value={`${v.late_fee_max_percent}% of the overdue amount`} />
      </div>

      <SchoolDialog
        open={open}
        onOpenChange={setOpen}
        trigger={
          <button type="button" className={LH_SECONDARY_BUTTON}>
            <span>Edit fee policy</span>
          </button>
        }
        title="Fee policy"
        description="Applies to late-fee accrual on overdue vouchers."
        onSubmit={(e) => {
          e.preventDefault()
          const f = new FormData(e.currentTarget)
          save({
            late_fee_percent_per_period: Number(f.get('late_fee_percent_per_period')),
            late_fee_grace_days: Number(f.get('late_fee_grace_days')),
            late_fee_period_days: Number(f.get('late_fee_period_days')),
            late_fee_max_percent: Number(f.get('late_fee_max_percent')),
          })
        }}
        footer={
          <button type="submit" disabled={saving} className={LH_PRIMARY_BUTTON}>
            <span>{saving ? 'Saving…' : 'Save policy'}</span>
          </button>
        }
      >
        <SchoolField id="late_fee_percent_per_period" label="Late fee per period (%)">
          <input id="late_fee_percent_per_period" name="late_fee_percent_per_period" type="number" step="0.01" className={LH_INPUT} defaultValue={v.late_fee_percent_per_period} />
        </SchoolField>
        <SchoolField id="late_fee_grace_days" label="Grace days" help="Days after the due date before any late fee is charged.">
          <input id="late_fee_grace_days" name="late_fee_grace_days" type="number" className={LH_INPUT} defaultValue={v.late_fee_grace_days} />
        </SchoolField>
        <SchoolField id="late_fee_period_days" label="Period length (days)">
          <input id="late_fee_period_days" name="late_fee_period_days" type="number" className={LH_INPUT} defaultValue={v.late_fee_period_days} />
        </SchoolField>
        <SchoolField id="late_fee_max_percent" label="Maximum (%)" help="Hard ceiling. Without it, accrual on a long-unpaid voucher grows without bound.">
          <input id="late_fee_max_percent" name="late_fee_max_percent" type="number" step="0.01" className={LH_INPUT} defaultValue={v.late_fee_max_percent} />
        </SchoolField>
        {error && <p className="text-sm text-rose-600">{error}</p>}
      </SchoolDialog>
    </div>
  )
}
