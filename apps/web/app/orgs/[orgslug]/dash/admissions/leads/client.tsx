'use client'

/**
 * Admissions lead list -- the flat, filterable view of every enquiry.
 *
 * Deliberately beside the kanban rather than replacing it. A board is the
 * right tool for moving a lead through the funnel; it is the wrong tool for
 * "show me every unconverted enquiry from March", which is a list question.
 * Both read the same leads, so they can never disagree.
 *
 * Filter honesty: stage, source, intent, campus and search are SERVER-side
 * (`GET /revops/leads` -- sms_revops.py:117). Sorting and the officer column
 * are client-side over the returned rows, because the endpoint always orders
 * by created_at DESC and has no officer filter. The footer says which is
 * which rather than implying the server narrowed something it did not.
 */

import { useMemo, useState } from 'react'
import Link from 'next/link'
import { ListFilter, Sparkles, Users } from 'lucide-react'
import {
  DashPageShell,
  DataTable,
  LH_SECONDARY_BUTTON,
  SectionCard,
  StatGrid,
  StatusChip,
} from '@/components/widgets'
import { ApiError } from '@/lib/api/api-client'
import { useApiResource } from '@/lib/api/useApiResource'
import { useSchoolSession } from '@/lib/api/useSchoolSession'
import { listCampuses } from '@/modules/sms/campus/api'
import { batchScoreLeads, listLeads } from '@/modules/sms/revops/api'
import { LeadFilterBar } from '@/modules/sms/revops/components/LeadFilterBar'
import { NewLeadDialog } from '@/modules/sms/revops/components/NewLeadDialog'
import {
  INTENT_TONE,
  SOURCE_LABEL,
  STAGE_LABEL,
  STAGE_TONE,
  consentSummary,
  daysSinceContact,
  formatDate,
  isActiveStage,
} from '@/modules/sms/revops/presentation'
import type { LeadListFilters, LeadRead } from '@/modules/sms/revops/types'
import { DataExportToolbar } from '@/components/ems/DataExportToolbar'
import type { ExportColumn } from '@/lib/export/data-export'

interface Props {
  org_id: number
  orgslug: string
}

type SortKey = 'created' | 'score' | 'name' | 'stale'

export default function AdmissionsLeadsClient({ org_id, orgslug }: Props) {
  const { session } = useSchoolSession()
  const [filters, setFilters] = useState<LeadListFilters>({})
  const [sort, setSort] = useState<SortKey>('created')
  const [scoring, setScoring] = useState(false)
  const [scoreNote, setScoreNote] = useState<string | null>(null)

  const campuses = useApiResource(() => listCampuses({ orgId: org_id, isActive: true }), [org_id], {
    isEmpty: (d) => d.length === 0,
  })

  const effectiveFilters = useMemo<LeadListFilters>(
    () => ({
      ...filters,
      campus_id: filters.campus_id ?? session?.campus_id ?? undefined,
    }),
    [filters, session?.campus_id]
  )

  const leads = useApiResource(() => listLeads(effectiveFilters), [effectiveFilters], {
    isEmpty: (d) => d.length === 0,
  })

  const rows = useMemo(() => {
    const data = [...(leads.data ?? [])]
    switch (sort) {
      case 'score':
        return data.sort((a, b) => b.lead_score - a.lead_score)
      case 'name':
        return data.sort((a, b) => a.student_name.localeCompare(b.student_name))
      case 'stale':
        return data.sort((a, b) => (daysSinceContact(b) ?? -1) - (daysSinceContact(a) ?? -1))
      default:
        return data
    }
  }, [leads.data, sort])

  const stats = useMemo(() => {
    const all = leads.data ?? []
    const active = all.filter((l) => isActiveStage(l.stage)).length
    const noConsent = all.filter((l) => consentSummary(l).blocked).length
    const hot = all.filter((l) => l.intent_level === 'HOT').length
    return { total: all.length, active, hot, noConsent }
  }, [leads.data])

  async function handleBatchScore() {
    setScoring(true)
    setScoreNote(null)
    try {
      const res = await batchScoreLeads({
        campus_id: effectiveFilters.campus_id ?? null,
      })
      setScoreNote(`Re-scored ${res.scored_count} lead${res.scored_count === 1 ? '' : 's'}.`)
      leads.refetch()
    } catch (err) {
      setScoreNote(
        err instanceof ApiError
          ? err.kind === 'permission_denied'
            ? 'You do not have access to run lead scoring.'
            : err.message
          : 'Could not run scoring.'
      )
    } finally {
      setScoring(false)
    }
  }

  const leadExportColumns: ExportColumn<LeadRead>[] = useMemo(
    () => [
      { key: 'id', label: 'Lead ID', type: 'number' },
      { key: 'parent_name', label: 'Parent Name', type: 'text' },
      { key: 'student_name', label: 'Student Name', type: 'text' },
      { key: 'email', label: 'Email', type: 'masked_pii', formatOptions: { piiType: 'email' } },
      { key: 'phone', label: 'Phone', type: 'masked_pii', formatOptions: { piiType: 'phone' } },
      { key: 'grade_applying_for', label: 'Grade Applying', type: 'text' },
      { key: 'stage', label: 'Stage', type: 'text', accessor: (l) => STAGE_LABEL[l.stage] || l.stage },
      { key: 'intent_level', label: 'Intent', type: 'text' },
      { key: 'lead_score', label: 'Lead Score', type: 'number' },
      { key: 'source', label: 'Source', type: 'text', accessor: (l) => SOURCE_LABEL[l.source] || l.source },
      { key: 'created_at', label: 'Created Date', type: 'datetime' },
    ],
    []
  )

  return (
    <DashPageShell
      module="admissions"
      title="Leads"
      description="Every admissions enquiry, filterable and sortable. The board at Admissions is for moving leads along; this is for finding them."
      action={
        <div className="flex items-center gap-2">
          <DataExportToolbar
            data={rows}
            columns={leadExportColumns}
            filenamePrefix="admissions_leads"
            title="Admissions Leads"
            activeFilters={effectiveFilters}
            classification="RESTRICTED"
          />
          <button
            type="button"
            id="leads-batch-score"
            className={LH_SECONDARY_BUTTON}
            onClick={handleBatchScore}
            disabled={scoring || (leads.data ?? []).length === 0}
            title="Re-runs the 5-factor scoring engine and saves the result on each lead"
          >
            <Sparkles className="size-4" />
            <span>{scoring ? 'Scoring…' : 'Re-score'}</span>
          </button>
          <NewLeadDialog campusId={effectiveFilters.campus_id} onCreated={() => leads.refetch()} />
        </div>
      }
    >
      <StatGrid
        state={leads.status === 'loading' ? 'loading' : 'success'}
        columns={4}
        items={[
          { label: 'Leads', value: stats.total, icon: Users, tone: 'neutral' },
          { label: 'In funnel', value: stats.active, icon: ListFilter, tone: 'positive' },
          { label: 'Hot intent', value: stats.hot, icon: Sparkles, tone: 'positive' },
          {
            label: 'Cannot contact',
            value: stats.noConsent,
            icon: Users,
            tone: stats.noConsent > 0 ? 'caution' : 'neutral',
          },
        ]}
      />

      <SectionCard
        title="Filter"
        description="Stage, source, intent, campus and search are applied by the server. Sorting is applied to the results below."
        icon={<ListFilter className="size-4 text-gray-500" />}
        action={
          <label className="flex items-center gap-2 text-xs text-gray-500">
            <span>Sort</span>
            <select
              id="leads-sort"
              className="rounded-lg border-0 bg-white px-2 py-1.5 text-sm nice-shadow focus:outline-none focus:ring-2 focus:ring-black"
              value={sort}
              onChange={(e) => setSort(e.target.value as SortKey)}
            >
              <option value="created">Newest first</option>
              <option value="score">Highest score</option>
              <option value="stale">Longest since contact</option>
              <option value="name">Student name</option>
            </select>
          </label>
        }
      >
        <LeadFilterBar
          filters={filters}
          onChange={setFilters}
          campuses={campuses.data ?? []}
          showCampus={session?.campus_id === null || session?.campus_id === undefined}
        />
        {scoreNote && <p className="mt-3 text-sm text-gray-600">{scoreNote}</p>}
      </SectionCard>

      <SectionCard
        title="All leads"
        icon={<Users className="size-4 text-gray-500" />}
        state={leads.status}
        error={leads.error}
        onRetry={leads.refetch}
        emptyTitle="No leads match"
        emptyDescription="No enquiry matches these filters. Clear them, or capture a walk-in with New lead."
      >
        <DataTable
          rows={rows}
          rowKey={(r) => r.id}
          state="success"
          totalLabel={`${rows.length} lead${rows.length === 1 ? '' : 's'}`}
          columns={[
            {
              key: 'student',
              header: 'Student',
              render: (r: LeadRead) => (
                <Link
                  href={`/dash/admissions/leads/${r.id}`}
                  className="font-medium text-gray-900 hover:underline"
                >
                  {r.student_name}
                </Link>
              ),
            },
            { key: 'parent', header: 'Parent', render: (r: LeadRead) => r.parent_name },
            { key: 'grade', header: 'Grade', render: (r: LeadRead) => r.grade_applying_for },
            {
              key: 'stage',
              header: 'Stage',
              render: (r: LeadRead) => (
                <StatusChip label={STAGE_LABEL[r.stage]} tone={STAGE_TONE[r.stage]} />
              ),
            },
            {
              key: 'source',
              header: 'Source',
              render: (r: LeadRead) => SOURCE_LABEL[r.source] ?? r.source,
            },
            {
              key: 'intent',
              header: 'Intent',
              render: (r: LeadRead) => (
                <StatusChip
                  label={r.intent_level}
                  tone={INTENT_TONE[r.intent_level] ?? 'neutral'}
                />
              ),
            },
            {
              key: 'score',
              header: 'Score',
              align: 'right',
              render: (r: LeadRead) => r.lead_score,
            },
            {
              key: 'consent',
              header: 'Outbound',
              render: (r: LeadRead) => {
                const c = consentSummary(r)
                return <StatusChip label={c.blocked ? 'Blocked' : c.label} tone={c.tone} />
              },
            },
            {
              key: 'created',
              header: 'Enquired',
              render: (r: LeadRead) => formatDate(r.created_at),
            },
          ]}
        />
      </SectionCard>
    </DashPageShell>
  )
}
