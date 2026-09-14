'use client'

/**
 * School module toggles.
 *
 * Why this page exists: the eleven CSG school feature flags were fully
 * enforced -- resolved by features_utils/resolve.py, gated per-router by the
 * require_<feature>_feature dependencies, and read by both the desktop and
 * mobile menus -- but NOTHING could set them. The only feature-toggle UI
 * (OrgEditMenu) knows Learnhouse's own six keys, so disabling a school module
 * meant hand-editing the org config JSON in Postgres. That is enforcement
 * without control.
 *
 * Grouped the way the sidebar groups them rather than alphabetically by key,
 * so the page reads like the product an admin actually uses. The raw feature
 * key is shown alongside each label for support purposes.
 *
 * sms_campus is deliberately not here: it is the multi-campus tenancy root
 * every other module hangs off, and is hardcoded into ALWAYS_ON_FEATURES.
 */

import React from 'react'
import { useOrg } from '@components/Contexts/OrgContext'
import { useLHSession } from '@components/Contexts/LHSessionContext'
import { toast } from 'react-hot-toast'
import { useQueryClient } from '@tanstack/react-query'
import { queryKeys } from '@/lib/query/keys'
import { getAPIUrl } from '@services/config/config'
import { revalidateTags } from '@services/utils/ts/requests'
import { useTranslation } from 'react-i18next'
import useAdminStatus from '@components/Hooks/useAdminStatus'
import { Switch } from '@components/ui/switch'
import { ShieldAlert, Blocks, AlertTriangle } from 'lucide-react'

interface SchoolModule {
  /** The real feature key, as registered in ALL_FEATURES. */
  key: string
  label: string
  description: string
}

interface ModuleGroup {
  heading: string
  modules: SchoolModule[]
}

/**
 * Mirrors the grouping and labels in DashLeftMenu / DashMobileMenu so the same
 * module is called the same thing everywhere an admin might meet it.
 */
const MODULE_GROUPS: ModuleGroup[] = [
  {
    heading: 'School setup',
    modules: [
      {
        key: 'sms_reports',
        label: 'Reports',
        description:
          'Whole-school attendance, grades, fees and admissions in one place.',
      },
      {
        key: 'revops',
        label: 'Admissions & RevOps',
        description:
          'Admissions CRM, lead pipeline, AI outreach agents and consent tracking.',
      },
    ],
  },
  {
    heading: 'Teaching',
    modules: [
      {
        key: 'sms_timetable',
        label: 'Timetable',
        description: 'Class periods, schedules and substitutions.',
      },
      {
        key: 'sms_attendance',
        label: 'Attendance',
        description: 'Daily roll-call, leave requests and absence alerts.',
      },
      {
        key: 'sms_gradebook',
        label: 'Gradebook',
        description:
          'Assessment plans, grade entry, GPA and report cards.',
      },
      {
        key: 'sms_exam',
        label: 'Exams',
        description: 'Exam scheduling and results.',
      },
      {
        key: 'tutor_counseling',
        label: 'AI Tutor & Counseling',
        description:
          'Socratic tutor, wellbeing detection, counseling records and career guidance.',
      },
    ],
  },
  {
    heading: 'Finance & staff',
    modules: [
      {
        key: 'sms_fees',
        label: 'Fees',
        description: 'Fee structures, vouchers, payments and late fees.',
      },
      {
        key: 'sms_financials',
        label: 'Financials',
        description: 'Chart of accounts, journal entries and trial balance.',
      },
      {
        key: 'sms_hr_payroll',
        label: 'Staff & Payroll',
        description:
          'Staff records, leave approval, salary structures and payslips.',
      },
    ],
  },
  {
    heading: 'Resources',
    modules: [
      {
        key: 'sms_library',
        label: 'School Library',
        description: 'Book catalogue, loans and overdue fines.',
      },
    ],
  },
]

const OrgEditModules: React.FC = () => {
  const { t } = useTranslation()
  const session = useLHSession() as any
  const access_token = session?.data?.tokens?.access_token
  const org = useOrg() as any
  const queryClient = useQueryClient()
  const { rights } = useAdminStatus()
  const canEditOrgSettings = rights?.organizations?.action_update === true

  const [enabled, setEnabled] = React.useState<Record<string, boolean>>({})
  const [updating, setUpdating] = React.useState<string | null>(null)
  const [confirming, setConfirming] = React.useState<SchoolModule | null>(null)

  React.useEffect(() => {
    const config = org?.config?.config
    if (!config) return

    // resolved_features is the authoritative view -- it is what the routers and
    // the menus actually gate on, after plan/deployment/toggle resolution.
    const next: Record<string, boolean> = {}
    for (const group of MODULE_GROUPS) {
      for (const mod of group.modules) {
        const resolved = config.resolved_features?.[mod.key]
        if (resolved && typeof resolved.enabled === 'boolean') {
          next[mod.key] = resolved.enabled
        } else if (config.admin_toggles?.[mod.key]) {
          next[mod.key] = !config.admin_toggles[mod.key].disabled
        } else {
          // No stored toggle means the module has never been switched off.
          next[mod.key] = true
        }
      }
    }
    setEnabled(next)
  }, [org])

  const applyToggle = async (mod: SchoolModule, nextEnabled: boolean) => {
    setUpdating(mod.key)
    const loadingToast = toast.loading(
      t('dashboard.organization.settings.updating')
    )

    // Optimistic, so the switch does not lag behind the click.
    setEnabled((prev) => ({ ...prev, [mod.key]: nextEnabled }))

    try {
      const response = await fetch(
        `${getAPIUrl()}orgs/${org.id}/config/school-module?module=${encodeURIComponent(
          mod.key
        )}&enabled=${nextEnabled}`,
        {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${access_token}`,
          },
        }
      )

      if (!response.ok) {
        throw new Error(`Failed to update ${mod.key}`)
      }

      await revalidateTags(['organizations'], org.slug)
      queryClient.invalidateQueries({ queryKey: queryKeys.org.detail(org.slug) })
      toast.success(`${mod.label} ${nextEnabled ? 'enabled' : 'disabled'}`, {
        id: loadingToast,
      })
    } catch (err) {
      // Roll the switch back so the UI never claims a change that did not land.
      setEnabled((prev) => ({ ...prev, [mod.key]: !nextEnabled }))
      toast.error(`Could not update ${mod.label}`, { id: loadingToast })
    } finally {
      setUpdating(null)
    }
  }

  const onToggle = (mod: SchoolModule, nextEnabled: boolean) => {
    // Turning a module ON needs no warning -- it only restores access.
    if (nextEnabled) {
      applyToggle(mod, true)
      return
    }
    setConfirming(mod)
  }

  return (
    <div className="sm:mx-10 mx-0 space-y-4">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Blocks className="w-6 h-6 text-gray-700" />
        <div>
          <h1 className="font-bold text-lg text-gray-800">School modules</h1>
          <p className="text-sm text-gray-500">
            Switch parts of the school system on or off for this organization.
          </p>
        </div>
      </div>

      {!canEditOrgSettings && (
        <div className="flex items-center gap-3 px-4 py-3 rounded-xl bg-amber-50 border border-amber-200/80">
          <ShieldAlert className="w-4 h-4 text-amber-600 flex-shrink-0" />
          <p className="text-sm text-amber-800">
            You need organization administrator rights to change these.
          </p>
        </div>
      )}

      {/* What disabling actually does. Stated once, up front, because the
          consequence is not obvious from a switch. */}
      <div className="px-4 py-3 rounded-xl bg-gray-50 border border-gray-200/80">
        <p className="text-sm text-gray-600">
          Disabling a module hides it from the menu and blocks its API. Existing
          records are <strong>never deleted</strong> — they stay in the database
          and reappear intact when you switch the module back on.
        </p>
      </div>

      {MODULE_GROUPS.map((group) => (
        <div key={group.heading} className="space-y-2">
          <h2 className="px-1 pt-2 text-[11px] font-semibold uppercase tracking-wider text-gray-400">
            {group.heading}
          </h2>
          <div className="rounded-xl bg-white nice-shadow divide-y divide-gray-100">
            {group.modules.map((mod) => (
              <div
                key={mod.key}
                className="flex items-center justify-between gap-4 px-4 py-3"
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-gray-800">
                      {mod.label}
                    </span>
                    {/* The raw key, for support: an admin on a call needs to
                        be able to say which flag they mean. */}
                    <code className="text-[10px] text-gray-400 bg-gray-50 px-1.5 py-0.5 rounded">
                      {mod.key}
                    </code>
                  </div>
                  <p className="text-xs text-gray-500 mt-0.5">
                    {mod.description}
                  </p>
                </div>
                <Switch
                  id={`module-toggle-${mod.key}`}
                  checked={enabled[mod.key] ?? true}
                  disabled={!canEditOrgSettings || updating === mod.key}
                  onCheckedChange={(checked: boolean) => onToggle(mod, checked)}
                />
              </div>
            ))}
          </div>
        </div>
      ))}

      {/* Confirmation before switching a module OFF. */}
      {confirming && (
        <div
          className="fixed inset-0 z-modal flex items-center justify-center bg-black/40 px-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="disable-module-title"
        >
          <div className="w-full max-w-md rounded-2xl bg-white shadow-2xl p-6 space-y-4">
            <div className="flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
              <div>
                <h3
                  id="disable-module-title"
                  className="font-bold text-gray-900"
                >
                  Disable {confirming.label}?
                </h3>
                <p className="text-sm text-gray-600 mt-1">
                  Staff will no longer see {confirming.label} in the menu, and
                  its API will refuse requests.
                </p>
                <p className="text-sm text-gray-600 mt-2">
                  Any records already in {confirming.label} stay in the database
                  and become reachable again the moment you re-enable it.{' '}
                  <strong>Nothing is deleted.</strong>
                </p>
              </div>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                id="cancel-disable-module"
                className="px-4 py-2 text-sm rounded-lg text-gray-600 hover:bg-gray-100 transition-colors"
                onClick={() => setConfirming(null)}
              >
                Cancel
              </button>
              <button
                type="button"
                id="confirm-disable-module"
                className="px-4 py-2 text-sm rounded-lg bg-gray-900 text-white hover:bg-black transition-colors"
                onClick={() => {
                  const mod = confirming
                  setConfirming(null)
                  applyToggle(mod, false)
                }}
              >
                Disable {confirming.label}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default OrgEditModules
