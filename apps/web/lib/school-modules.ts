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
      // Sittings sits before Seating deliberately: a seat is allocated per
      // SITTING, so the sitting must exist (and be findable) first. Without
      // this screen the seating page asked an administrator to type a raw
      // numeric schedule id they had no way to look up.
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
      // Arrears is the screen a bursar actually lives in, so it sits second
      // rather than at the end. There is no arrears ENDPOINT -- the tab derives
      // overdue status from each voucher's due date -- but that is a backend
      // gap, not a reason to hide the screen a school needs daily.
      { href: '/dash/fees/arrears', label: 'Arrears' },
      { href: '/dash/fees/reconciliation', label: 'Reconciliation' },
      { href: '/dash/fees/reminders', label: 'Reminders' },
    ],
  },
  // M19 cross-module reporting. Every tab is `administer`: the router gates on
  // [SUPER_ADMIN, SCHOOL_ADMIN] and deliberately NOT teacher-wide, because it
  // puts fee collection and admissions next to academics -- principal/office
  // data rather than something every class teacher should read.
  //
  // The per-domain tabs are not duplicates of Overview. Overview applies ONE
  // date window across all four domains; each tab carries only the filters its
  // own domain understands, so "grades for term 2" and "fees this month" can
  // be asked separately -- which the single view cannot express.
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
  // Its OWN module, deliberately not a tab under `counseling`, for two
  // reasons. The sidebar already carries a separate `/dash/discipline` entry
  // (DashLeftMenu.tsx:817, gated `canTeach`), and a module's `root` must match
  // its sidebar entry or the tab strip highlights the wrong module. More
  // importantly the two have opposite disclosure rules: a counselling record's
  // EXISTENCE is confidential and its endpoints answer an unauthorised caller
  // with an empty result, never a 403, while a disciplinary incident is
  // ordinary school business visible to every teacher. Nesting a
  // teacher-visible tab inside the psychologist-confidential module is exactly
  // the conflation that rule exists to prevent.
  // Three SEPARATE module keys, not one merged "Recognition" surface.
  //
  // Each has its own sidebar entry behind its own feature toggle
  // (`showPathways` / `showGamification` / `showCertificates`,
  // DashLeftMenu.tsx:319-321), and a module's `root` MUST match its sidebar
  // entry or the tab strip highlights the wrong module. Merging them would
  // also show a school that enabled only one of the three a surface containing
  // two tabs it cannot use. They are not one domain either: a pathway is
  // curriculum planning, a certificate is a credential, and points are
  // engagement -- filing them together would be a cabinet, not a workflow.
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
      // NO Suspensions tab, though the sidebar's shape invites one. The API
      // has POST /suspensions and nothing else -- no list, no get, no update
      // (sms_discipline.py:180 is the only suspension route, and
      // DisciplineService has no read method for them). A tab could therefore
      // create a suspension but never show one, and a write-only screen that
      // cannot display what it recorded is worse than no screen: an admin
      // cannot tell whether the last one saved. Restore the tab when a read
      // endpoint exists.
    ],
  },
  alumni: {
    root: '/dash/alumni',
    tabs: [
      { href: '/dash/alumni', label: 'Register', access: 'administer' },
      // One tab only, and that is the API's doing rather than a design
      // choice. sms_alumni.py exposes exactly three routes -- list profiles,
      // create a profile, add a milestone -- and milestones come back NESTED
      // on the list, so they belong inside a profile rather than on a tab of
      // their own. There is no PATCH and no DELETE, so there is nothing to
      // build an "edit" surface against either.
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
  'school-settings': {
    root: '/dash/school-settings',
    tabs: [
      { href: '/dash/school-settings', label: 'Settings', access: 'administer' },
      // People is where accounts are CREATED; Roles grants a role to somebody
      // who already has one. Both are administer-gated to match their routers
      // ([SUPER_ADMIN, SCHOOL_ADMIN] on every provisioning and role endpoint
      // in routers/sms_identity.py) -- a teacher must not be offered a screen
      // whose every control would be refused.
      { href: '/dash/school-settings/people', label: 'People', access: 'administer' },
      { href: '/dash/school-settings/roles', label: 'Roles', access: 'administer' },
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
