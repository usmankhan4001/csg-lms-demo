import type { SearchMetaSchoolAccess } from '@/lib/dashboard-search/types'

/**
 * Every school module's internal screens, defined once.
 *
 * The sidebar had grown to 55 entries because each module's sub-screens were
 * appended as flat siblings -- Attendance sat beside History, Absence notes,
 * At-risk and Bulk marking as if they were five separate products. A school
 * admin could not tell where one module ended and the next began.
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
      { href: '/dash/admissions', label: 'Pipeline' },
      { href: '/dash/admissions/leads', label: 'Leads' },
      { href: '/dash/admissions/applications', label: 'Applications' },
      { href: '/dash/admissions/offers', label: 'Offers' },
      { href: '/dash/admissions/campaigns', label: 'Campaigns' },
      { href: '/dash/admissions/worklist', label: 'My worklist' },
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
      // A preview of what guardians are actually sent. Lives here because the
      // digest is overwhelmingly an attendance report, and the at-risk tab
      // next door is where staff are already thinking about one named child.
      { href: '/dash/attendance/digest', label: 'Family digest' },
    ],
  },
  timetable: {
    root: '/dash/timetable',
    tabs: [
      { href: '/dash/timetable', label: 'Week grid' },
      // Generating a week rewrites a section's whole schedule -- admin only,
      // exactly as its sidebar entry was gated before the collapse.
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
      { href: '/dash/exams/seating', label: 'Seating' },
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
  counseling: {
    root: '/dash/counseling',
    tabs: [
      { href: '/dash/counseling', label: 'Sessions' },
      { href: '/dash/counseling/career', label: 'Career guidance' },
    ],
  },
  revops: {
    root: '/dash/revops',
    tabs: [
      { href: '/dash/revops', label: 'Insights' },
      // Both are administer-gated to match their routers: config is
      // [SUPER_ADMIN, SCHOOL_ADMIN] (sms_revops_config.py:51), and while the
      // knowledge base itself admits STAFF, deleting an entry does not -- so
      // the tab keeps the narrower gate rather than offering a screen whose
      // controls a back-office user would find half-refused.
      { href: '/dash/revops/config', label: 'Agent config', access: 'administer' },
      { href: '/dash/revops/knowledge', label: 'Knowledge base', access: 'administer' },
    ],
  },
} satisfies Record<string, SchoolModuleDef>

/**
 * Keys stay literal so `module="attendnce"` is a compile error, while the
 * VALUE is widened to SchoolModuleDef. Without the widening, TypeScript infers
 * each tab as its own literal object type and `access` "does not exist" on the
 * ones that omit it -- so the gating read would not compile.
 */
export type SchoolModuleKey = keyof typeof MODULE_DEFS

export const SCHOOL_MODULES: Record<SchoolModuleKey, SchoolModuleDef> = MODULE_DEFS
