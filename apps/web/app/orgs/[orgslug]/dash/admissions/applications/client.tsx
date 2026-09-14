'use client'

/**
 * The registrar's daily screen: where is every application right now.
 *
 * Distinct from `/dash/admissions/leads`, which lists ENQUIRIES being
 * nurtured. An application is a family that has actually applied — and it
 * does not require a lead, so this list is never a subset of that one.
 *
 * Filter honesty: status, academic year and campus are SERVER-side
 * (`GET /sms/admissions/applications` — sms_admissions.py:160). The grade
 * filter and sorting are client-side over the returned page, because the
 * endpoint offers neither. The footer says which is which rather than
 * implying the server narrowed something it did not.
 */

import { useMemo, useState } from 'react'
import Link from 'next/link'
import { FileStack, Inbox, ListFilter } from 'lucide-react'
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
import { listApplications } from '@/modules/sms/admissions/api'
import { NewApplicationDialog } from '@/modules/sms/admissions/components/NewApplicationDialog'
import {
  AWAITING_FAMILY,
  STATUS_LABEL,
  STATUS_TONE,
  TERMINAL_STATUSES,
  daysSince,
  formatDate,
} from '@/modules/sms/admissions/presentation'
import type { ApplicationRead, ApplicationStatus } from '@/modules/sms/admissions/types'

interface Props {
  org_id: number
  orgslug: string
}

const STATUSES: ApplicationStatus[] = [
  'DRAFT',
  'SUBMITTED',
  'DOCUMENTS_PENDING',
  'UNDER_REVIEW',
  'ASSESSMENT_SCHEDULED',
  'ASSESSED',
  'OFFERED',
  'ACCEPTED',
  'ENROLLED',
  'REJECTED',
  'WITHDRAWN',
]

export default function ApplicationsClient({ org_id, orgslug }: Props) {
  const { session } = useSchoolSession()
  const [statusFilter, setStatusFilter] = useState<ApplicationStatus | ''>('')
  const [gradeFilter, setGradeFilter] = useState('')

  const applications = useApiResource(
    () => listApplications({ status: statusFilter || undefined }),
    [statusFilter],
    { isEmpty: (d) => d.length === 0 }
  )

  const all = useMemo(() => applications.data ?? [], [applications.data])

  const rows = useMemo(() => {
    const needle = gradeFilter.trim().toLowerCase()
    const filtered = needle
      ? all.filter((a) => a.grade_applying_for.toLowerCase().includes(needle))
      : all
    // Oldest-waiting first: a registrar's question is "what is going stale",
    // not "what arrived most recently".
    return [...filtered].sort((a, b) => {
      const aOpen = !TERMINAL_STATUSES.includes(a.status)
      const bOpen = !TERMINAL_STATUSES.includes(b.status)
      if (aOpen !== bOpen) return aOpen ? -1 : 1
      return new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
    })
  }, [all, gradeFilter])

  const open = all.filter((a) => !TERMINAL_STATUSES.includes(a.status)).length
  const awaitingFamily = all.filter((a) => AWAITING_FAMILY.includes(a.status)).length
  const enrolled = all.filter((a) => a.status === 'ENROLLED').length

  return (
    <DashPageShell
      module="admissions"
      title="Applications"
      description="Every family that has applied — and exactly where each application stands."
      action={
        <NewApplicationDialog
          campusId={session?.campus_id ?? undefined}
          onCreated={applications.refetch}
        />
      }
    >
      <StatGrid
        state={applications.status === 'loading' ? 'loading' : 'success'}
        columns={4}
        items={[
          { label: 'Applications', value: all.length, icon: FileStack, tone: 'neutral' },
          { label: 'Still open', value: open, icon: Inbox, tone: 'neutral' },
          { label: 'Awaiting the family', value: awaitingFamily, icon: Inbox, tone: 'caution' },
          { label: 'Enrolled', value: enrolled, icon: FileStack, tone: 'positive' },
        ]}
      />

      <SectionCard
        title="Filter"
        icon={<ListFilter className="size-4 text-gray-500" />}
      >
        <div className="flex flex-wrap items-end gap-4">
          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-medium text-gray-500">Status</span>
            <select
              id="applications-status-filter"
              className={LH_INPUT}
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as ApplicationStatus | '')}
            >
              <option value="">All statuses</option>
              {STATUSES.map((s) => (
                <option key={s} value={s}>
                  {STATUS_LABEL[s]}
                </option>
              ))}
            </select>
          </label>

          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-medium text-gray-500">Grade</span>
            <input
              id="applications-grade-filter"
              className={LH_INPUT}
              value={gradeFilter}
              onChange={(e) => setGradeFilter(e.target.value)}
              placeholder="e.g. Grade 9"
            />
          </label>
        </div>
      </SectionCard>

      <SectionCard
        id="applications"
        title="Applications"
        state={applications.status}
        error={applications.error}
        onRetry={applications.refetch}
        emptyTitle="No applications yet"
        emptyDescription="When a family applies — at the desk or through an enquiry — their application appears here."
      >
        <DataTable
          rows={rows}
          rowKey={(r) => r.id}
          state="success"
          totalLabel={`${rows.length} of ${all.length} · status filtered on the server, grade and ordering in this page`}
          columns={[
            {
              key: 'number',
              header: 'Reference',
              render: (r) => <span className="font-mono text-xs">{r.application_number}</span>,
            },
            {
              key: 'student',
              header: 'Student',
              render: (r) => (
                <Link
                  href={`/dash/admissions/applications/${r.id}`}
                  className="font-medium text-gray-900 hover:underline"
                >
                  {r.student_name}
                </Link>
              ),
            },
            { key: 'grade', header: 'Grade', render: (r) => r.grade_applying_for },
            { key: 'guardian', header: 'Guardian', render: (r) => r.guardian_name },
            {
              key: 'status',
              header: 'Status',
              render: (r) => <StatusChip label={STATUS_LABEL[r.status]} tone={STATUS_TONE[r.status]} />,
            },
            {
              key: 'submitted',
              header: 'Submitted',
              render: (r) => (
                <span className="text-xs text-gray-600">{formatDate(r.submitted_at)}</span>
              ),
            },
            {
              key: 'waiting',
              header: 'Waiting',
              align: 'right',
              render: (r) => <WaitingCell application={r} />,
            },
          ]}
        />
      </SectionCard>
    </DashPageShell>
  )
}

/**
 * Days open — or an explicit "Closed"/"Unknown".
 *
 * Never renders 0 for a missing date: "applied today" and "we have no record
 * of when this arrived" are opposite facts to a registrar chasing a backlog.
 */
function WaitingCell({ application }: { application: ApplicationRead }) {
  if (TERMINAL_STATUSES.includes(application.status)) {
    return <span className="text-xs text-gray-400">Closed</span>
  }
  const days = daysSince(application.created_at)
  if (days === null) return <span className="text-xs text-gray-400">Unknown</span>
  return (
    <span className={days > 14 ? 'text-xs font-medium text-amber-700' : 'text-xs text-gray-600'}>
      {days === 0 ? 'Today' : `${days}d`}
    </span>
  )
}
