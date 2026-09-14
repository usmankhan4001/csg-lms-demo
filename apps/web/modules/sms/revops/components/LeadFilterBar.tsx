'use client'

/**
 * Filter bar for the admissions lead list.
 *
 * Only the filters the API actually supports are sent to the server
 * (`GET /revops/leads` takes campus_id, stage, source, origin, intent_level
 * and search -- sms_revops.py:122-127). Anything else is applied client-side
 * over the returned rows and is labelled as such in the calling screen, so an
 * operator is never misled about whether a filter narrowed the query or just
 * the view.
 */

import { Search, X } from 'lucide-react'
import { LH_GHOST_BUTTON, LH_INPUT } from '@/components/widgets'
import type { CampusRead } from '@/modules/sms/campus/types'
import { SOURCE_LABEL, STAGE_LABEL, STAGE_ORDER } from '../presentation'
import type { LeadIntent, LeadListFilters, LeadSource, LeadStage } from '../types'

const SOURCES: LeadSource[] = [
  'WEBSITE_FORM',
  'WHATSAPP',
  'META_ADS',
  'GOOGLE_ADS',
  'WALK_IN',
  'REFERRAL',
]

const INTENTS: LeadIntent[] = ['HOT', 'WARM', 'COLD']

export interface LeadFilterBarProps {
  filters: LeadListFilters
  onChange: (next: LeadListFilters) => void
  campuses?: CampusRead[]
  /** Hidden when the caller already scopes to one campus (e.g. a bound admin). */
  showCampus?: boolean
}

export function LeadFilterBar({
  filters,
  onChange,
  campuses = [],
  showCampus = true,
}: LeadFilterBarProps) {
  const active =
    Object.entries(filters).filter(([, v]) => v !== undefined && v !== '').length > 0

  function set<K extends keyof LeadListFilters>(key: K, value: LeadListFilters[K]) {
    const next = { ...filters }
    if (value === undefined || value === ('' as unknown as LeadListFilters[K])) {
      delete next[key]
    } else {
      next[key] = value
    }
    onChange(next)
  }

  return (
    <div className="flex flex-wrap items-end gap-3">
      <label className="flex flex-col gap-1.5">
        <span className="text-xs font-medium text-gray-500">Search</span>
        <div className="relative">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-gray-400" />
          <input
            id="lead-filter-search"
            className={`${LH_INPUT} ps-8`}
            placeholder="Name, email or phone"
            value={filters.search ?? ''}
            onChange={(e) => set('search', e.target.value || undefined)}
          />
        </div>
      </label>

      <label className="flex flex-col gap-1.5">
        <span className="text-xs font-medium text-gray-500">Stage</span>
        <select
          id="lead-filter-stage"
          className={LH_INPUT}
          value={filters.stage ?? ''}
          onChange={(e) => set('stage', (e.target.value || undefined) as LeadStage | undefined)}
        >
          <option value="">All stages</option>
          {STAGE_ORDER.map((s) => (
            <option key={s} value={s}>
              {STAGE_LABEL[s]}
            </option>
          ))}
        </select>
      </label>

      <label className="flex flex-col gap-1.5">
        <span className="text-xs font-medium text-gray-500">Source</span>
        <select
          id="lead-filter-source"
          className={LH_INPUT}
          value={filters.source ?? ''}
          onChange={(e) => set('source', (e.target.value || undefined) as LeadSource | undefined)}
        >
          <option value="">All sources</option>
          {SOURCES.map((s) => (
            <option key={s} value={s}>
              {SOURCE_LABEL[s] ?? s}
            </option>
          ))}
        </select>
      </label>

      <label className="flex flex-col gap-1.5">
        <span className="text-xs font-medium text-gray-500">Intent</span>
        <select
          id="lead-filter-intent"
          className={LH_INPUT}
          value={filters.intent_level ?? ''}
          onChange={(e) =>
            set('intent_level', (e.target.value || undefined) as LeadIntent | undefined)
          }
        >
          <option value="">Any intent</option>
          {INTENTS.map((i) => (
            <option key={i} value={i}>
              {i.charAt(0) + i.slice(1).toLowerCase()}
            </option>
          ))}
        </select>
      </label>

      {showCampus && campuses.length > 1 && (
        <label className="flex flex-col gap-1.5">
          <span className="text-xs font-medium text-gray-500">Campus</span>
          <select
            id="lead-filter-campus"
            className={LH_INPUT}
            value={filters.campus_id ?? ''}
            onChange={(e) =>
              set('campus_id', e.target.value ? Number(e.target.value) : undefined)
            }
          >
            <option value="">All campuses</option>
            {campuses.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </label>
      )}

      {active && (
        <button
          type="button"
          id="lead-filter-clear"
          className={LH_GHOST_BUTTON}
          onClick={() => onChange({})}
        >
          <X className="size-4" /> <span>Clear</span>
        </button>
      )}
    </div>
  )
}
