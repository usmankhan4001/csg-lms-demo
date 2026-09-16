'use client'

/**
 * The school's home screen.
 *
 * Before this, `/dash` was Learnhouse's own course-authoring landing page:
 * create a course, view analytics, invite members. A school admin logging in
 * saw an LMS, not their school — no attendance, no fees, no admissions, no
 * indication that today had happened at all.
 *
 * WHAT A PERSON SEES DEPENDS ON WHO THEY ARE, because the answer to "how is
 * the school doing" is different for a head teacher and a form tutor:
 *
 *   - SCHOOL_ADMIN / SUPER_ADMIN -> today's shape across the whole school:
 *     attendance, grades, fee collection, the admissions funnel.
 *   - TEACHER -> their own job: the students they need to chase, and the
 *     registers and marks waiting for them.
 *   - STAFF (back office) -> the money.
 *   - No school role (a plain Learnhouse org admin) -> the original
 *     Learnhouse dashboard, unchanged. Setting the school up requires those
 *     screens, and taking them away would strand a fresh deployment.
 *
 * Role and feature resolution is LIFTED FROM DashLeftMenu rather than
 * re-derived: same `resolved_features` toggle, same `GET /sms/me` roles, same
 * `noSchoolRole` escape hatch. A second derivation would eventually disagree
 * with the sidebar, and then a module would be visible in one and not the
 * other.
 *
 * Learnhouse's own surfaces are KEPT, not thrown away — a school runs courses,
 * and the content/member overviews are genuinely useful. They move below the
 * school's own figures rather than above them.
 */

import React from 'react'
import Link from 'next/link'
import {
  CalendarCheck,
  GraduationCap,
  Wallet,
  UserPlus,
  ShieldAlert,
  ClipboardList,
  CalendarClock,
  BookOpen,
} from 'lucide-react'
import { useOrg } from '@components/Contexts/OrgContext'
import { useLHSession } from '@components/Contexts/LHSessionContext'
import { useSchoolSession } from '@/lib/api/useSchoolSession'
import { useApiResource } from '@/lib/api/useApiResource'
import { DataTable, SectionCard, StatGrid, StatusChip } from '@/components/widgets'
import { getSchoolOverview } from '@/modules/sms/reports/api'
import { formatMetric, metricHint, metricTone, currency } from '@/modules/sms/reports/presentation'
import { listPastoralConcerns } from '@/modules/sms/attendance/api'
import type { PastoralConcernRead } from '@/modules/sms/attendance/types'
import RecentCourses from './RecentCourses'
import RecentMembers from './RecentMembers'
import ContentOverview from './ContentOverview'

/** Quick actions are plain links — no data source, so nothing here can lie. */
interface QuickAction {
  href: string
  label: string
  icon: React.ComponentType<{ className?: string }>
}

function QuickActions({ actions }: { actions: QuickAction[] }) {
  if (actions.length === 0) return null
  return (
    <div className="flex flex-wrap gap-2">
      {actions.map((a) => (
        <Link
          key={a.href}
          id={`quick-${a.href.replace(/[^a-z]+/gi, '-')}`}
          href={a.href}
          className="inline-flex items-center gap-2 rounded-lg bg-white px-3.5 py-2 text-xs font-medium text-gray-600 nice-shadow transition-colors hover:bg-gray-50"
        >
          <a.icon className="size-3.5" />
          {a.label}
        </Link>
      ))}
    </div>
  )
}

/**
 * At-risk students from ATTENDANCE, deliberately not counselling.
 *
 * The backend scopes a teacher to their own sections and lets leadership and
 * counsellors see all (`_PASTORAL_VIEWERS`, sms_attendance.py:107). Counselling
 * records and AI safety incidents are NOT surfaced here at all: the backend
 * enforces 404-never-403 precisely so a teacher cannot learn that a child is
 * seeing a counsellor, and a shared dashboard is the easiest place to undo
 * that. These are attendance flags, and the card says so.
 */
function AtRiskCard({ canSeeAllSections }: { canSeeAllSections: boolean }) {
  const concerns = useApiResource(() => listPastoralConcerns({ status: 'OPEN', limit: 5 }), [], {
    isEmpty: (d) => d.length === 0,
  })

  return (
    <SectionCard
      id="at-risk"
      title="At-risk attendance"
      description={
        canSeeAllSections
          ? 'Open attendance concerns across the school.'
          : 'Open attendance concerns in your sections. Colleagues may see others.'
      }
      icon={<ShieldAlert className="size-4 text-gray-500" />}
      state={concerns.status}
      error={concerns.error}
      onRetry={concerns.refetch}
      emptyTitle="No open concerns"
      emptyDescription="Nobody is currently flagged by the absence detector."
      action={
        <Link href="/dash/attendance/pastoral" className="text-xs font-medium text-gray-500 hover:text-gray-900">
          View all
        </Link>
      }
    >
      <DataTable<PastoralConcernRead>
        rows={concerns.data ?? []}
        rowKey={(r) => r.id}
        state="success"
        columns={[
          { key: 'student', header: 'Student', render: (r) => `Student #${r.student_id}` },
          { key: 'trigger', header: 'Trigger', render: (r) => r.trigger },
          {
            key: 'magnitude',
            header: 'Extent',
            align: 'right',
            // null magnitude is a trigger with no natural number, NOT a zero.
            render: (r) => (r.magnitude == null ? 'Not measured' : String(r.magnitude)),
          },
          {
            key: 'status',
            header: 'Status',
            render: (r) => <StatusChip label={r.status.replace('_', ' ')} tone="caution" />,
          },
        ]}
      />
    </SectionCard>
  )
}

/**
 * The whole-school figures. ADMIN ONLY, and that is not a style choice:
 * `GET /sms/reports/overview` is gated `[SUPER_ADMIN, SCHOOL_ADMIN]`
 * (sms_reports.py:53), so calling it as a teacher returns 403. Fetching it for
 * everyone would paint a permission error across a teacher's home screen.
 */
function SchoolOverviewStats() {
  const overview = useApiResource(() => getSchoolOverview({}), [], { isEmpty: () => false })
  const d = overview.data

  return (
    <>
      <StatGrid
        state={overview.status === 'loading' ? 'loading' : 'success'}
        columns={4}
        items={[
          {
            label: 'Attendance',
            value: d ? formatMetric(d.attendance.attendance_rate) : '—',
            hint: d ? metricHint(d.attendance.attendance_rate) : undefined,
            icon: CalendarCheck,
            tone: d ? metricTone(d.attendance.attendance_rate) : 'neutral',
          },
          {
            label: 'Average grade',
            value: d ? formatMetric(d.grades.average_percentage) : '—',
            hint: d ? metricHint(d.grades.average_percentage) : undefined,
            icon: GraduationCap,
            tone: d ? metricTone(d.grades.average_percentage) : 'neutral',
          },
          {
            label: 'Fees collected',
            value: d ? formatMetric(d.fees.collection_rate) : '—',
            hint: d ? metricHint(d.fees.collection_rate) : undefined,
            icon: Wallet,
            tone: d ? metricTone(d.fees.collection_rate) : 'neutral',
          },
          {
            label: 'Admissions conversion',
            value: d ? formatMetric(d.admissions.conversion_rate) : '—',
            hint: d ? metricHint(d.admissions.conversion_rate) : undefined,
            icon: UserPlus,
            tone: d ? metricTone(d.admissions.conversion_rate) : 'neutral',
          },
        ]}
      />

      {/*
        `warnings` is the backend's own list of what could not be computed and
        why. Rendering it is what stops an empty dashboard being read as a bad
        one — "no roll-call has been taken" and "attendance is poor" are
        opposite findings.
      */}
      {d && d.warnings.length > 0 && (
        <SectionCard
          title="Not enough data to report"
          description="These figures are missing rather than low."
          icon={<ClipboardList className="size-4 text-gray-500" />}
        >
          <ul className="space-y-1.5">
            {d.warnings.map((w) => (
              <li key={w} className="text-sm text-gray-600">
                • {w}
              </li>
            ))}
          </ul>
        </SectionCard>
      )}

      {/*
        Counts, not rates. "0 outstanding" is a real and honest answer, so
        these are NOT nulled — the distinction the whole module turns on.
      */}
      {d && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <SectionCard
            title="Fees"
            description={d.fees.source_module}
            icon={<Wallet className="size-4 text-gray-500" />}
          >
            <dl className="space-y-2 text-sm">
              <div className="flex justify-between">
                <dt className="text-gray-500">Invoiced</dt>
                <dd className="font-medium">{currency(d.fees.total_invoiced)}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">Collected</dt>
                <dd className="font-medium">{currency(d.fees.total_collected)}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">Outstanding</dt>
                <dd className="font-medium">{currency(d.fees.total_outstanding)}</dd>
              </div>
              <div className="flex justify-between border-t border-gray-100 pt-2">
                <dt className="text-gray-400">Vouchers</dt>
                <dd className="text-gray-500">{d.fees.voucher_count}</dd>
              </div>
            </dl>
          </SectionCard>

          <SectionCard
            title="Admissions"
            description={d.admissions.source_module}
            icon={<UserPlus className="size-4 text-gray-500" />}
          >
            <dl className="space-y-2 text-sm">
              <div className="flex justify-between">
                <dt className="text-gray-500">Total leads</dt>
                <dd className="font-medium">{d.admissions.total_leads}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">Enrolled</dt>
                <dd className="font-medium">{d.admissions.enrolled_count}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">Stalled</dt>
                <dd className="font-medium">{d.admissions.stalled_count}</dd>
              </div>
              <div className="flex justify-between border-t border-gray-100 pt-2">
                <dt className="text-gray-400">Lost</dt>
                <dd className="text-gray-500">{d.admissions.lost_count}</dd>
              </div>
            </dl>
          </SectionCard>
        </div>
      )}
    </>
  )
}

export default function SchoolDashboardHome() {
  const org = useOrg() as any
  const session = useLHSession() as any
  const username = session?.data?.user?.username || ''

  // Same resolution as DashLeftMenu — deliberately not a second derivation.
  const rf = org?.config?.config?.resolved_features
  const isEnabled = (feature: string) => rf?.[feature]?.enabled === true

  const { session: schoolSession, checked } = useSchoolSession()
  const schoolRoles = schoolSession?.roles ?? []
  const isSuper = schoolRoles.includes('SUPER_ADMIN')
  const isSchoolAdmin = isSuper || schoolRoles.includes('SCHOOL_ADMIN')
  const isTeacher = schoolRoles.includes('TEACHER')
  const isSchoolStaff = schoolRoles.includes('STAFF')
  const noSchoolRole = schoolRoles.length === 0
  const canAdminister = isSchoolAdmin || noSchoolRole
  const canTeach = canAdminister || isTeacher
  const canBackOffice = canAdminister || isSchoolStaff

  // SMS-first: all administrators and school staff see the school operations dashboard
  const isPureLearnhouse = false

  const showAttendance = isEnabled('sms_attendance') && canTeach
  const showGradebook = isEnabled('sms_gradebook') && canTeach
  const showTimetable = isEnabled('sms_timetable') && canTeach
  const showFees = isEnabled('sms_fees') && canBackOffice
  const showAdmissions = isEnabled('revops') && canAdminister
  const showCampus = canAdminister

  const quickActions: QuickAction[] = [
    showAttendance && { href: '/dash/attendance', label: 'Take register', icon: CalendarCheck },
    showGradebook && { href: '/dash/gradebook', label: 'Enter marks', icon: GraduationCap },
    showTimetable && { href: '/dash/timetable', label: 'Timetable', icon: CalendarClock },
    showAdmissions && { href: '/dash/admissions', label: 'Admissions', icon: UserPlus },
    showFees && { href: '/dash/fees', label: 'Fees', icon: Wallet },
    showCampus && { href: '/dash/campus', label: 'Campus', icon: BookOpen },
  ].filter(Boolean) as QuickAction[]

  // Wait for /sms/me before deciding which dashboard to render
  const roleResolved = checked

  return (
    <div className="h-full w-full bg-[#f8f8f8]">
      <div className="px-4 pt-8 pb-10 sm:px-10">
        <div className="mx-auto w-full max-w-[1600px] space-y-6">
          <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">
                Welcome back{username ? `, ${username}` : ''}
              </h1>
              {org?.name && <p className="mt-1.5 text-xs text-gray-400">{org.name} • School Management Console</p>}
            </div>
            <QuickActions actions={quickActions} />
          </div>

          {roleResolved && (
            <div className="space-y-6">
              {/* Whole-school figures: admin only */}
              {canAdminister && <SchoolOverviewStats />}

              {/* Attendance flags. Teachers see their own sections only. */}
              {showAttendance && <AtRiskCard canSeeAllSections={canAdminister} />}
            </div>
          )}

          {/*
            Learnhouse's own surfaces, kept. A school runs courses, and these
            are useful to everyone — they simply sit below the school's own
            figures rather than replacing them.
          */}
          <div className="space-y-6">
            {canAdminister && <ContentOverview />}
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
              <div className="space-y-6 lg:col-span-2">
                <RecentCourses />
                {canAdminister && <RecentMembers />}
              </div>
              <div className="space-y-6">
                <SectionCard
                  title="Learning"
                  description="Learnhouse course tools."
                  icon={<BookOpen className="size-4 text-gray-500" />}
                >
                  <div className="flex flex-col gap-2">
                    <Link
                      id="quick-create-course"
                      href="/dash/courses?new=true"
                      className="rounded-lg bg-gray-900 px-3.5 py-2 text-center text-xs font-medium text-white transition-colors hover:bg-gray-800"
                    >
                      Create a course
                    </Link>
                    <Link
                      id="quick-courses"
                      href="/dash/courses"
                      className="rounded-lg bg-white px-3.5 py-2 text-center text-xs font-medium text-gray-600 nice-shadow transition-colors hover:bg-gray-50"
                    >
                      All courses
                    </Link>
                  </div>
                </SectionCard>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
