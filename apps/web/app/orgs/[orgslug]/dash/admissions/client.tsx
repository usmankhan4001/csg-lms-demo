'use client'

/**
 * M01 Admissions & Registrar Intake Console
 *
 * Grounded in Pillar 1 SMS specification (01_PILLAR_1_LMS_SMS_REQUIREMENTS.md §4.1).
 * Operates the real-world student application lifecycle:
 * Intake -> Document Verification -> Assessment -> Decision -> Section Enrollment.
 */

import { useMemo, useState } from 'react'
import Link from 'next/link'
import {
  FileStack,
  Inbox,
  ListFilter,
  CheckCircle2,
  Clock,
  UserPlus,
  ArrowRight,
  ShieldCheck,
  Award,
  AlertCircle,
  FileCheck,
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

const STAGES: { id: ApplicationStatus | ''; label: string }[] = [
  { id: '', label: 'All Applications' },
  { id: 'SUBMITTED', label: 'Submitted' },
  { id: 'DOCUMENTS_PENDING', label: 'Documents Pending' },
  { id: 'UNDER_REVIEW', label: 'Under Review' },
  { id: 'ASSESSMENT_SCHEDULED', label: 'Assessment' },
  { id: 'OFFERED', label: 'Offered' },
  { id: 'ENROLLED', label: 'Enrolled' },
  { id: 'REJECTED', label: 'Rejected' },
]

export default function AdmissionsDashClient({ org_id, orgslug }: Props) {
  const { session } = useSchoolSession()
  const [statusFilter, setStatusFilter] = useState<ApplicationStatus | ''>('')
  const [gradeFilter, setGradeFilter] = useState('')
  const [searchQuery, setSearchQuery] = useState('')

  const applications = useApiResource(
    () => listApplications({ status: statusFilter || undefined }),
    [statusFilter],
    { isEmpty: (d) => d.length === 0 }
  )

  const all = useMemo(() => applications.data ?? [], [applications.data])

  const filteredRows = useMemo(() => {
    let list = all

    if (gradeFilter.trim()) {
      const g = gradeFilter.trim().toLowerCase()
      list = list.filter((a) => a.grade_applying_for.toLowerCase().includes(g))
    }

    if (searchQuery.trim()) {
      const q = searchQuery.trim().toLowerCase()
      list = list.filter(
        (a) =>
          a.student_name.toLowerCase().includes(q) ||
          a.guardian_name.toLowerCase().includes(q) ||
          (a.guardian_email && a.guardian_email.toLowerCase().includes(q)) ||
          (a.guardian_phone && a.guardian_phone.includes(q))
      )
    }

    // Sort: open applications first, sorted by waiting duration
    return [...list].sort((a, b) => {
      const aOpen = !TERMINAL_STATUSES.includes(a.status)
      const bOpen = !TERMINAL_STATUSES.includes(b.status)
      if (aOpen !== bOpen) return aOpen ? -1 : 1
      return new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
    })
  }, [all, gradeFilter, searchQuery])

  const totalCount = all.length
  const pendingDocs = all.filter((a) => a.status === 'DOCUMENTS_PENDING').length
  const underReview = all.filter((a) => a.status === 'UNDER_REVIEW').length
  const assessmentDue = all.filter((a) => a.status === 'ASSESSMENT_SCHEDULED' || a.status === 'ASSESSED').length
  const offeredCount = all.filter((a) => a.status === 'OFFERED' || a.status === 'ACCEPTED').length
  const enrolledCount = all.filter((a) => a.status === 'ENROLLED').length

  return (
    <DashPageShell
      module="admissions"
      title="Admissions & Enrollment Intake"
      description="Candidate application intake, document verification, entrance assessment scoring, admissions board decisions, and student section enrollment."
      action={
        <NewApplicationDialog
          campusId={session?.campus_id ?? undefined}
          onCreated={applications.refetch}
        />
      }
    >
      {/* 1. Executive Registrar KPIs */}
      <StatGrid
        state={applications.status === 'loading' ? 'loading' : applications.status === 'error' ? 'error' : 'success'}
        error={applications.error}
        columns={4}
        items={[
          { label: 'Total Applications', value: totalCount, icon: FileStack, tone: 'neutral' },
          { label: 'Pending Documents', value: pendingDocs, icon: Clock, tone: 'caution' },
          { label: 'Assessment & Review', value: assessmentDue + underReview, icon: FileCheck, tone: 'neutral' },
          { label: 'Enrolled Students', value: enrolledCount, icon: CheckCircle2, tone: 'positive' },
        ]}
      />

      {/* 2. Admissions Lifecycle Stage Filter Pills */}
      <div className="flex items-center gap-1.5 overflow-x-auto py-1 border-b border-slate-200">
        {STAGES.map((st) => {
          const count = st.id ? all.filter((a) => a.status === st.id).length : all.length
          const active = statusFilter === st.id
          return (
            <button
              key={st.id || 'all'}
              onClick={() => setStatusFilter(st.id)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold whitespace-nowrap transition-all flex items-center gap-1.5 ${
                active
                  ? 'bg-slate-900 text-white shadow-xs'
                  : 'bg-slate-100 text-slate-600 hover:text-slate-900'
              }`}
            >
              <span>{st.label}</span>
              <span
                className={`text-[10px] px-1.5 py-0.2 rounded-full font-bold ${
                  active
                    ? 'bg-white/20 text-white'
                    : 'bg-slate-200 text-slate-700'
                }`}
              >
                {count}
              </span>
            </button>
          )
        })}
      </div>

      {/* 3. Filter and Search Controls */}
      <SectionCard
        title="Candidate Filter & Search"
        icon={<ListFilter className="size-4 text-slate-500" />}
      >
        <div className="flex flex-wrap items-end gap-4">
          <label className="flex flex-col gap-1.5 flex-1 min-w-[200px]">
            <span className="text-xs font-medium text-slate-500">Search Candidate or Guardian</span>
            <input
              type="text"
              className={LH_INPUT}
              placeholder="Filter by student name, parent name, email, or phone..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </label>

          <label className="flex flex-col gap-1.5 min-w-[160px]">
            <span className="text-xs font-medium text-slate-500">Grade Level</span>
            <input
              type="text"
              className={LH_INPUT}
              placeholder="e.g. Grade 9"
              value={gradeFilter}
              onChange={(e) => setGradeFilter(e.target.value)}
            />
          </label>

          {(statusFilter || gradeFilter || searchQuery) && (
            <button
              onClick={() => {
                setStatusFilter('')
                setGradeFilter('')
                setSearchQuery('')
              }}
              className={`${LH_SECONDARY_BUTTON} text-xs py-2`}
            >
              Reset Filters
            </button>
          )}
        </div>
      </SectionCard>

      {/* 4. Active Applications Intake & Review Table */}
      <DataTable<ApplicationRead>
        state={
          applications.status === 'loading'
            ? 'loading'
            : applications.status === 'error'
            ? 'error'
            : filteredRows.length === 0
            ? 'empty'
            : 'success'
        }
        error={applications.error}
        onRetry={applications.refetch}
        rowKey={(a) => a.id}
        emptyTitle={
          statusFilter || gradeFilter || searchQuery
            ? 'No matching candidate applications'
            : 'No applications received yet'
        }
        emptyDescription={
          statusFilter || gradeFilter || searchQuery
            ? 'Try broadening your search or resetting active filters.'
            : 'Create a new candidate application using the button above.'
        }
        columns={[
          {
            key: 'student_name',
            header: 'Candidate Name',
            render: (a: ApplicationRead) => (
              <div className="flex flex-col">
                <Link
                  href={`/orgs/${orgslug}/dash/admissions/applications/${a.id}`}
                  className="font-semibold text-slate-900 hover:underline hover:text-indigo-600 flex items-center gap-1.5"
                >
                  <span>{a.student_name}</span>
                  <ArrowRight className="size-3 text-slate-400" />
                </Link>
                <span className="text-xs text-slate-500">
                  DOB: {a.date_of_birth ? formatDate(a.date_of_birth) : 'Not recorded'}
                </span>
              </div>
            ),
          },
          {
            key: 'guardian_contact',
            header: 'Guardian Contact',
            render: (a: ApplicationRead) => (
              <div className="flex flex-col text-xs text-slate-600">
                <span className="font-medium text-slate-900">{a.guardian_name}</span>
                <span>{a.guardian_phone || a.guardian_email || 'No contact provided'}</span>
              </div>
            ),
          },
          {
            key: 'grade_applying_for',
            header: 'Target Grade',
            render: (a: ApplicationRead) => (
              <span className="text-xs font-medium text-slate-800">
                {a.grade_applying_for}
              </span>
            ),
          },
          {
            key: 'status',
            header: 'Lifecycle Status',
            render: (a: ApplicationRead) => (
              <StatusChip
                label={STATUS_LABEL[a.status]}
                tone={STATUS_TONE[a.status]}
              />
            ),
          },
          {
            key: 'submission_age',
            header: 'Submission Age',
            render: (a: ApplicationRead) => (
              <span className="text-xs text-slate-500">
                {daysSince(a.created_at)}
              </span>
            ),
          },
          {
            key: 'action',
            header: 'Action',
            render: (a: ApplicationRead) => (
              <Link
                href={`/orgs/${orgslug}/dash/admissions/applications/${a.id}`}
                className="text-xs font-semibold text-indigo-600 hover:text-indigo-700 hover:underline"
              >
                Open File
              </Link>
            ),
          },
        ]}
        rows={filteredRows}
      />
    </DashPageShell>
  )
}
