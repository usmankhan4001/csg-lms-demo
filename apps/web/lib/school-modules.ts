import type { SearchMetaSchoolAccess } from '@/lib/dashboard-search/types'

/**
 * Every school module's internal screens, defined once.
 *
 * A module is now ONE sidebar entry whose page carries its own tab strip, and
 * this table is where those tabs live. Defining them here rather than inline
 * in twenty client components means the sidebar, the tabs and Ctrl+K cannot
 * drift into disagreeing about what a module contains.
 *
 * `access` is per TAB, not per module, because they genuinely differ: a
 * teacher may take a register and read the lesson log, but must not generate a
 * timetable or run payroll. Collapsing entries into a module must not quietly
 * widen what a role can reach, so each tab keeps the gate its sidebar entry
 * had.
 */

/**
 * The four business domains the school modules group into. Consumers render
 * these as section headings; the ids are stable, so do not renumber them.
 */
export type SchoolDomainId =
  | 'academic-core'
  | 'learning-evaluation'
  | 'admissions-crm'
  | 'institutional-admin'

export interface SchoolDomainDef {
  id: SchoolDomainId
  label: string
  description: string
}

/** Ordered for display. Iterate this, do not hardcode the list elsewhere. */
export const SCHOOL_DOMAINS: readonly SchoolDomainDef[] = [
  {
    id: 'academic-core',
    label: 'Academic Core & School Operations',
    description:
      'Academic years and terms, campuses, class sections, attendance and timetable — the structure and daily rhythm every other module builds on.',
  },
  {
    id: 'learning-evaluation',
    label: 'Curriculum, Learning & Evaluation',
    description:
      'Courses, assignments, gradebook, exams, library, pathways, certificates, AI tutoring and live classes.',
  },
  {
    id: 'admissions-crm',
    label: 'Admissions, CRM & Student Recruitment',
    description:
      'Admissions, RevOps and the enquiry/lead pipeline that feeds them.',
  },
  {
    id: 'institutional-admin',
    label: 'Institutional Administration & Finance',
    description:
      'Fees, financials, HR, payroll, reporting, alumni, inventory, hostel, gamification, messaging and settings.',
  },
]

export interface ModuleTabDef {
  /** Route, absolute under the org's dash (e.g. `/dash/attendance/history`). */
  href: string
  label: string
  /** Omitted means every viewer who can open the module sees the tab. */
  access?: SearchMetaSchoolAccess
  /**
   * Org feature flag the screen sits behind, matching the route's
   * `page.search.ts`. Recorded for completeness; `ModuleTabs` does not filter
   * on it today, so populating it changes nothing until a consumer opts in.
   */
  featureKey?: string
}

export interface SchoolModuleDef {
  /** The module's home route, and the sidebar entry's href. */
  root: string
  /** Which of the four business domains this module belongs to. */
  domain: SchoolDomainId
  tabs: ModuleTabDef[]
}

const MODULE_DEFS = {
  admissions: {
    root: '/dash/admissions',
    domain: 'admissions-crm',
    tabs: [
      { href: '/dash/admissions', label: 'Intake & Review' },
      { href: '/dash/admissions/applications', label: 'All Applications' },
      { href: '/dash/admissions/offers', label: 'Offers & Decisions' },
      { href: '/dash/admissions/worklist', label: 'Registrar Worklist' },
      { href: '/dash/admissions/leads', label: 'Enquiries' },
    ],
  },
  attendance: {
    root: '/dash/attendance',
    domain: 'academic-core',
    tabs: [
      { href: '/dash/attendance', label: 'Roll-call' },
      { href: '/dash/attendance/history', label: 'History' },
      { href: '/dash/attendance/excuses', label: 'Absence notes' },
      { href: '/dash/attendance/pastoral', label: 'At-risk' },
      { href: '/dash/attendance/bulk', label: 'Bulk marking' },
      { href: '/dash/attendance/digest', label: 'Family digest' },
    ],
  },
  timetable: {
    root: '/dash/timetable',
    domain: 'academic-core',
    tabs: [
      { href: '/dash/timetable', label: 'Week grid' },
      { href: '/dash/timetable/generate', label: 'Generate', access: 'administer' },
      { href: '/dash/timetable/lessons', label: 'Lesson log' },
      { href: '/dash/timetable/conflicts', label: 'Conflicts' },
    ],
  },
  gradebook: {
    root: '/dash/gradebook',
    domain: 'learning-evaluation',
    tabs: [
      { href: '/dash/gradebook', label: 'Marks' },
      { href: '/dash/gradebook/report-cards', label: 'Report cards' },
    ],
  },
  exams: {
    root: '/dash/exams',
    domain: 'learning-evaluation',
    tabs: [
      { href: '/dash/exams', label: 'Exams' },
      { href: '/dash/exams/sittings', label: 'Sittings' },
      { href: '/dash/exams/seating', label: 'Seating' },
      { href: '/dash/exams/incidents', label: 'Incidents' },
      { href: '/dash/exams/resits', label: 'Resits', access: 'administer' },
    ],
  },
  'school-library': {
    root: '/dash/school-library',
    domain: 'learning-evaluation',
    tabs: [
      { href: '/dash/school-library', label: 'Catalogue' },
      { href: '/dash/school-library/reservations', label: 'Holds' },
    ],
  },
  fees: {
    root: '/dash/fees',
    domain: 'institutional-admin',
    tabs: [
      { href: '/dash/fees', label: 'Vouchers' },
      { href: '/dash/fees/arrears', label: 'Arrears' },
      { href: '/dash/fees/reconciliation', label: 'Reconciliation' },
      { href: '/dash/fees/reminders', label: 'Reminders' },
    ],
  },
  reports: {
    root: '/dash/reports',
    domain: 'institutional-admin',
    tabs: [
      { href: '/dash/reports', label: 'Overview', access: 'administer' },
      { href: '/dash/reports/attendance', label: 'Attendance', access: 'administer' },
      { href: '/dash/reports/grades', label: 'Grades', access: 'administer' },
      { href: '/dash/reports/fees', label: 'Fees', access: 'administer' },
      { href: '/dash/reports/admissions', label: 'Admissions', access: 'administer' },
    ],
  },
  counseling: {
    // Not named in the domain briefs. Placed with learning rather than
    // institutional admin because it shares the `tutor_counseling` feature
    // with AI Tutor and is learner-facing, not an administrative function.
    root: '/dash/counseling',
    domain: 'learning-evaluation',
    tabs: [
      // Sessions are confidential clinical records -- the backend enforces
      // 404-never-403, so discovery must not advertise them to teachers.
      { href: '/dash/counseling', label: 'Sessions', access: 'counsel' },
      // Career guidance is explicitly NOT a confidential record; the backend
      // allows TEACHER (CAREER_GUIDANCE_STAFF_ROLES), so it stays at teach.
      { href: '/dash/counseling/career', label: 'Career guidance', access: 'teach' },
    ],
  },
  gamification: {
    root: '/dash/gamification',
    domain: 'institutional-admin',
    tabs: [
      { href: '/dash/gamification', label: 'Badges', access: 'teach' },
      { href: '/dash/gamification/leaderboard', label: 'Leaderboard', access: 'teach' },
    ],
  },
  certificates: {
    root: '/dash/certificates-manager',
    domain: 'learning-evaluation',
    tabs: [
      { href: '/dash/certificates-manager', label: 'Templates', access: 'teach' },
      { href: '/dash/certificates-manager/issued', label: 'Issued', access: 'teach' },
    ],
  },
  pathways: {
    root: '/dash/pathways',
    domain: 'learning-evaluation',
    tabs: [
      { href: '/dash/pathways', label: 'Pathways', access: 'teach' },
      { href: '/dash/pathways/progress', label: 'Enrolments', access: 'teach' },
    ],
  },
  discipline: {
    // Not named in the domain briefs. Placed with school operations: conduct
    // is handled day-to-day alongside attendance and pastoral, not as an
    // institutional back-office function.
    root: '/dash/discipline',
    domain: 'academic-core',
    tabs: [
      { href: '/dash/discipline', label: 'Incidents', access: 'teach' },
    ],
  },
  alumni: {
    root: '/dash/alumni',
    domain: 'institutional-admin',
    tabs: [
      { href: '/dash/alumni', label: 'Register', access: 'administer' },
    ],
  },
  revops: {
    root: '/dash/revops',
    domain: 'admissions-crm',
    tabs: [
      { href: '/dash/revops', label: 'Insights' },
      { href: '/dash/revops/config', label: 'Agent config', access: 'administer' },
      { href: '/dash/revops/knowledge', label: 'Knowledge base', access: 'administer' },
    ],
  },
  'school-settings': {
    root: '/dash/school-settings',
    domain: 'institutional-admin',
    tabs: [
      { href: '/dash/school-settings', label: 'Settings', access: 'administer' },
      { href: '/dash/school-settings/people', label: 'People', access: 'administer' },
      { href: '/dash/school-settings/roles', label: 'Roles', access: 'administer' },
    ],
  },

  // ---------------------------------------------------------------------------
  // Single-screen modules.
  //
  // Each of these has exactly one route under `dash/` (verified: no sub-pages
  // exist), so each gets one tab. `ModuleTabs` returns null below two visible
  // tabs, so none of them renders a strip today -- they are listed here so the
  // sidebar, Ctrl+K and any future tab strip agree that the module exists and
  // what it contains. Do not invent sub-routes to force a strip to appear.
  // ---------------------------------------------------------------------------

  campus: {
    root: '/dash/campus',
    domain: 'academic-core',
    tabs: [{ href: '/dash/campus', label: 'Campuses', access: 'administer' }],
  },
  financials: {
    root: '/dash/financials',
    domain: 'institutional-admin',
    tabs: [
      {
        href: '/dash/financials',
        label: 'Financials',
        access: 'backOffice',
        featureKey: 'sms_financials',
      },
    ],
  },
  hr: {
    root: '/dash/hr',
    domain: 'institutional-admin',
    tabs: [
      {
        href: '/dash/hr',
        label: 'Staff',
        access: 'administer',
        featureKey: 'sms_hr_payroll',
      },
    ],
  },
  payroll: {
    // Reachable only via Ctrl+K today: it is in neither DashLeftMenu nor
    // DashMobileMenu. Kept administer-gated, matching its page.search.ts, so
    // the separation-of-duties control is not widened by adding it here.
    root: '/dash/payroll',
    domain: 'institutional-admin',
    tabs: [
      {
        href: '/dash/payroll',
        label: 'Payroll',
        access: 'administer',
        featureKey: 'sms_hr_payroll',
      },
    ],
  },
  'ai-tutor': {
    root: '/dash/ai-tutor',
    domain: 'learning-evaluation',
    tabs: [
      {
        href: '/dash/ai-tutor',
        label: 'AI Tutor',
        // This is the staff oversight surface. The backend gates its endpoints
        // on _SAFEGUARDING = [SUPER_ADMIN, SCHOOL_ADMIN, PSYCHOLOGIST] and
        // explicitly excludes TEACHER, which is exactly the `counsel` level.
        access: 'counsel',
        featureKey: 'tutor_counseling',
      },
    ],
  },
  'live-classes': {
    // `/dash/live-classes/[classId]` is a detail route reached from the list,
    // not a sibling screen, so it is not a tab.
    root: '/dash/live-classes',
    domain: 'learning-evaluation',
    tabs: [{ href: '/dash/live-classes', label: 'Live Classes', access: 'teach' }],
  },
  messages: {
    root: '/dash/messages',
    domain: 'institutional-admin',
    tabs: [{ href: '/dash/messages', label: 'Messages', access: 'anyRole' }],
  },
} satisfies Record<string, SchoolModuleDef>

export type SchoolModuleKey = keyof typeof MODULE_DEFS

export const SCHOOL_MODULES: Record<SchoolModuleKey, SchoolModuleDef> = MODULE_DEFS
