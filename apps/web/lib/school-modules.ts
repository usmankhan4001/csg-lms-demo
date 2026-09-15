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

export interface ModuleTabDef {
  /** Route, absolute under the org's dash (e.g. `/dash/attendance/history`). */
  href: string
  label: string
  /** Omitted means every viewer who can open the module sees the tab. */
  access?: SearchMetaSchoolAccess
}

export interface SchoolModuleDef {
  /** The module's home route, and the sidebar entry's href. */
  root: string
  tabs: ModuleTabDef[]
}

const MODULE_DEFS = {
  admissions: {
    root: '/dash/admissions',
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
    tabs: [
      { href: '/dash/timetable', label: 'Week grid' },
      { href: '/dash/timetable/generate', label: 'Generate', access: 'administer' },
      { href: '/dash/timetable/lessons', label: 'Lesson log' },
      { href: '/dash/timetable/conflicts', label: 'Conflicts' },
    ],
  },
  gradebook: {
    root: '/dash/gradebook',
    tabs: [
      { href: '/dash/gradebook', label: 'Marks' },
      { href: '/dash/gradebook/report-cards', label: 'Report cards' },
    ],
  },
  exams: {
    root: '/dash/exams',
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
    tabs: [
      { href: '/dash/school-library', label: 'Catalogue' },
      { href: '/dash/school-library/reservations', label: 'Holds' },
    ],
  },
  fees: {
    root: '/dash/fees',
    tabs: [
      { href: '/dash/fees', label: 'Vouchers' },
      { href: '/dash/fees/arrears', label: 'Arrears' },
      { href: '/dash/fees/reconciliation', label: 'Reconciliation' },
      { href: '/dash/fees/reminders', label: 'Reminders' },
    ],
  },
  reports: {
    root: '/dash/reports',
    tabs: [
      { href: '/dash/reports', label: 'Overview', access: 'administer' },
      { href: '/dash/reports/attendance', label: 'Attendance', access: 'administer' },
      { href: '/dash/reports/grades', label: 'Grades', access: 'administer' },
      { href: '/dash/reports/fees', label: 'Fees', access: 'administer' },
      { href: '/dash/reports/admissions', label: 'Admissions', access: 'administer' },
    ],
  },
  counseling: {
    root: '/dash/counseling',
    tabs: [
      { href: '/dash/counseling', label: 'Sessions' },
      { href: '/dash/counseling/career', label: 'Career guidance' },
    ],
  },
  gamification: {
    root: '/dash/gamification',
    tabs: [
      { href: '/dash/gamification', label: 'Badges', access: 'teach' },
      { href: '/dash/gamification/leaderboard', label: 'Leaderboard', access: 'teach' },
    ],
  },
  certificates: {
    root: '/dash/certificates-manager',
    tabs: [
      { href: '/dash/certificates-manager', label: 'Templates', access: 'teach' },
      { href: '/dash/certificates-manager/issued', label: 'Issued', access: 'teach' },
    ],
  },
  pathways: {
    root: '/dash/pathways',
    tabs: [
      { href: '/dash/pathways', label: 'Pathways', access: 'teach' },
      { href: '/dash/pathways/progress', label: 'Enrolments', access: 'teach' },
    ],
  },
  discipline: {
    root: '/dash/discipline',
    tabs: [
      { href: '/dash/discipline', label: 'Incidents', access: 'teach' },
    ],
  },
  alumni: {
    root: '/dash/alumni',
    tabs: [
      { href: '/dash/alumni', label: 'Register', access: 'administer' },
    ],
  },
  revops: {
    root: '/dash/revops',
    tabs: [
      { href: '/dash/revops', label: 'Insights' },
      { href: '/dash/revops/config', label: 'Agent config', access: 'administer' },
      { href: '/dash/revops/knowledge', label: 'Knowledge base', access: 'administer' },
    ],
  },
  'school-settings': {
    root: '/dash/school-settings',
    tabs: [
      { href: '/dash/school-settings', label: 'Settings', access: 'administer' },
      { href: '/dash/school-settings/people', label: 'People', access: 'administer' },
      { href: '/dash/school-settings/roles', label: 'Roles', access: 'administer' },
    ],
  },
} satisfies Record<string, SchoolModuleDef>

export type SchoolModuleKey = keyof typeof MODULE_DEFS

export const SCHOOL_MODULES: Record<SchoolModuleKey, SchoolModuleDef> = MODULE_DEFS
