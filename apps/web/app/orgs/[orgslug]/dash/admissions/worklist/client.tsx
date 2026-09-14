'use client'

/**
 * Officer worklist -- "what needs doing today", ordered by what is going cold.
 *
 * The kanban shows where every lead sits; this shows which ones are rotting.
 * A family that enquired nine days ago and has heard nothing is the single
 * most expensive thing in an admissions funnel, and neither the board nor the
 * list surfaces it, because both sort by stage or recency rather than by
 * neglect.
 *
 * Staleness is computed from `last_contacted_at`, falling back to
 * `created_at`. Where neither parses it reports UNKNOWN rather than 0 days --
 * "contacted today" and "we have no record of contacting them" are opposite
 * facts, and this codebase has had to tear out three separate instances of
 * missing data being rendered as a confident number.
 *
 * Assignment is filtered CLIENT-side: `GET /revops/leads` has no
 * assigned_officer_id filter (sms_revops.py:122-127), so the rows are fetched
 * campus-scoped and narrowed here. The UI says so rather than implying the
 * server did it.
 */

import { useMemo, useState } from 'react'
import Link from 'next/link'
import { AlarmClock, Flame, UserCheck, Users } from 'lucide-react'
import {
  DashPageShell,
  DataTable,
  LH_INPUT,
  SectionCard,
  StatGrid,
  StatusChip,
} from '@/components/widgets'
import { useApiResource } from '@/lib/api/useApiResource'
import { useSchoolSession } from '@/lib/api/useSchoolSession'
import { listSchoolPeople } from '@/modules/sms/campus/api'
import { listLeads } from '@/modules/sms/revops/api'
import {
  INTENT_TONE,
  STALENESS_TONE,
  STAGE_LABEL,
  STAGE_TONE,
  consentSummary,
  daysSinceContact,
  isActiveStage,
  staleness,
} from '@/modules/sms/revops/presentation'
import type { LeadRead } from '@/modules/sms/revops/types'

interface Props {
  org_id: number
  orgslug: string
}

export default function AdmissionsWorklistClient({ orgslug }: Props) {
  const { session } = useSchoolSession()
  const campusId = session?.campus_id ?? undefined
  // `staff_id` is this user's own StaffProfile id, which is what
  // `assigned_officer_id` is keyed on.
  const myId = session?.staff_id ?? undefined
  const [owner, setOwner] = useState<'mine' | 'unassigned' | 'all'>(myId ? 'mine' : 'all')

  const leads = useApiResource(() => listLeads({ campus_id: campusId }), [campusId], {
    isEmpty: (d) => d.length === 0,
  })

  const officers = useApiResource(() => listSchoolPeople('STAFF', campusId), [campusId], {
    isEmpty: () => false,
  })

  const officerName = useMemo(() => {
    const m = new Map<number, string>()
    for (const p of officers.data ?? []) m.set(p.user_id, p.name ?? `Staff #${p.user_id}`)
    return m
  }, [officers.data])

  const rows = useMemo(() => {
    let data = (leads.data ?? []).filter((l) => isActiveStage(l.stage))
    if (owner === 'mine' && myId !== undefined) {
      data = data.filter((l) => l.assigned_officer_id === myId)
    } else if (owner === 'unassigned') {
      data = data.filter((l) => l.assigned_officer_id === null || l.assigned_officer_id === undefined)
    }
    // Coldest first: the whole point of this screen.
    return data.sort((a, b) => (daysSinceContact(b) ?? -1) - (daysSinceContact(a) ?? -1))
  }, [leads.data, owner, myId])

  const stats = useMemo(() => {
    const stale = rows.filter((l) => staleness(l) === 'stale').length
    const hot = rows.filter((l) => l.intent_level === 'HOT').length
    const blocked = rows.filter((l) => consentSummary(l).blocked).length
    return { total: rows.length, stale, hot, blocked }
  }, [rows])

  return (
    <DashPageShell
      module="admissions"
      title="My worklist"
      description="Active leads that need attention, coldest first. Assignment and staleness are worked out from the leads this campus returned."
    >
      <StatGrid
        state={leads.status === 'loading' ? 'loading' : 'success'}
        columns={4}
        items={[
          { label: 'In my funnel', value: stats.total, icon: Users, tone: 'neutral' },
          {
            label: 'Going cold',
            value: stats.stale,
            icon: AlarmClock,
            tone: stats.stale > 0 ? 'critical' : 'positive',
          },
          { label: 'Hot intent', value: stats.hot, icon: Flame, tone: 'positive' },
          {
            label: 'Cannot contact',
            value: stats.blocked,
            icon: UserCheck,
            tone: stats.blocked > 0 ? 'caution' : 'neutral',
          },
        ]}
      />

      <SectionCard
        title="Needs attention"
        description="Leads still in the funnel, ordered by how long since anyone contacted them."
        icon={<AlarmClock className="size-4 text-gray-500" />}
        state={leads.status === 'success' && rows.length === 0 ? 'empty' : leads.status}
        error={leads.error}
        onRetry={leads.refetch}
        emptyTitle="Nothing needs chasing"
        emptyDescription="No active lead matches this view. Try 'Everyone' to see the whole campus."
        action={
          <label className="flex items-center gap-2 text-xs text-gray-500">
            <span>Showing</span>
            <select
              id="worklist-owner"
              className={LH_INPUT}
              value={owner}
              onChange={(e) => setOwner(e.target.value as 'mine' | 'unassigned' | 'all')}
            >
              <option value="mine" disabled={myId === undefined}>
                Assigned to me
              </option>
              <option value="unassigned">Unassigned</option>
              <option value="all">Everyone</option>
            </select>
          </label>
        }
      >
        <DataTable
          rows={rows}
          rowKey={(r: LeadRead) => r.id}
          state="success"
          totalLabel={`${rows.length} lead${rows.length === 1 ? '' : 's'} · filtered in this view, not by the server`}
          columns={[
            {
              key: 'student',
              header: 'Student',
              render: (r) => (
                <Link
                  href={`/dash/admissions/leads/${r.id}`}
                  className="font-medium text-gray-900 hover:underline"
                >
                  {r.student_name}
                </Link>
              ),
            },
            { key: 'parent', header: 'Parent', render: (r) => r.parent_name },
            {
              key: 'stage',
              header: 'Stage',
              render: (r) => <StatusChip label={STAGE_LABEL[r.stage]} tone={STAGE_TONE[r.stage]} />,
            },
            {
              key: 'stale',
              header: 'Since contact',
              render: (r) => {
                const d = daysSinceContact(r)
                const band = staleness(r)
                return (
                  <StatusChip
                    label={d === null ? 'Unknown' : `${d}d`}
                    tone={STALENESS_TONE[band]}
                  />
                )
              },
            },
            {
              key: 'intent',
              header: 'Intent',
              render: (r) => (
                <StatusChip label={r.intent_level} tone={INTENT_TONE[r.intent_level] ?? 'neutral'} />
              ),
            },
            {
              key: 'owner',
              header: 'Officer',
              render: (r) =>
                r.assigned_officer_id
                  ? officerName.get(r.assigned_officer_id) ?? `Staff #${r.assigned_officer_id}`
                  : 'Unassigned',
            },
            {
              key: 'consent',
              header: 'Outbound',
              render: (r) => {
                const c = consentSummary(r)
                return <StatusChip label={c.blocked ? 'Blocked' : c.label} tone={c.tone} />
              },
            },
          ]}
        />
      </SectionCard>
    </DashPageShell>
  )
}
