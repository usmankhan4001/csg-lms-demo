import { SquaresFour } from '@phosphor-icons/react'
import type { SearchMeta } from './types'
import { dashboardActions } from './actions'
import { SCHOOL_MODULES } from '@/lib/school-modules'

// ---------------------------------------------------------------------------
// Learnhouse's own pages. These are not school modules, so they are not in
// SCHOOL_MODULES and stay registered by hand.
// ---------------------------------------------------------------------------
import { searchMeta as home } from '@/app/orgs/[orgslug]/dash/page.search'
import { searchMeta as courses } from '@/app/orgs/[orgslug]/dash/courses/page.search'
import { searchMeta as coursesMigrate } from '@/app/orgs/[orgslug]/dash/courses/migrate/page.search'
import { searchMeta as assignments } from '@/app/orgs/[orgslug]/dash/assignments/page.search'
import { searchMeta as communities } from '@/app/orgs/[orgslug]/dash/communities/page.search'
import { searchMeta as podcasts } from '@/app/orgs/[orgslug]/dash/podcasts/page.search'
import { searchMeta as boards } from '@/app/orgs/[orgslug]/dash/boards/page.search'
import { searchMeta as playgrounds } from '@/app/orgs/[orgslug]/dash/playgrounds/page.search'
import { searchMeta as analytics } from '@/app/orgs/[orgslug]/dash/analytics/page.search'
import { searchMetas as users } from '@/app/orgs/[orgslug]/dash/users/page.search'
import { searchMetas as org } from '@/app/orgs/[orgslug]/dash/org/page.search'
import { searchMetas as payments } from '@/app/orgs/[orgslug]/dash/payments/page.search'
import { searchMetas as account } from '@/app/orgs/[orgslug]/(withmenu)/account/page.search'

// ---------------------------------------------------------------------------
// School (SMS) screens: PRESENTATION ONLY.
//
// These files say how a screen is labelled, described and iconed in the
// palette. They no longer say whether it exists or who may reach it -- that
// comes from SCHOOL_MODULES, which is iterated at the bottom of this file. A
// tab added to SCHOOL_MODULES becomes searchable with no change here; a tab
// with no file here still gets an entry, it just falls back to the tab's own
// label and its module's icon.
//
// The `schoolAccess` / `featureKey` in these files are kept in step with
// SCHOOL_MODULES by hand and are the FALLBACK, not the authority: when a tab
// declares its own `access` / `featureKey` in SCHOOL_MODULES, that wins.
// ---------------------------------------------------------------------------
import { searchMeta as schoolCampus } from '@/app/orgs/[orgslug]/dash/campus/page.search'
import { searchMeta as schoolAdmissions } from '@/app/orgs/[orgslug]/dash/admissions/page.search'
import { searchMeta as schoolAdmissionsLeads } from '@/app/orgs/[orgslug]/dash/admissions/leads/page.search'
import { searchMeta as schoolAdmissionsApplications } from '@/app/orgs/[orgslug]/dash/admissions/applications/page.search'
import { searchMeta as schoolAdmissionsOffers } from '@/app/orgs/[orgslug]/dash/admissions/offers/page.search'
import { searchMeta as schoolAdmissionsCampaigns } from '@/app/orgs/[orgslug]/dash/admissions/campaigns/page.search'
import { searchMeta as schoolAdmissionsWorklist } from '@/app/orgs/[orgslug]/dash/admissions/worklist/page.search'
import { searchMeta as schoolRevops } from '@/app/orgs/[orgslug]/dash/revops/page.search'
import { searchMeta as schoolRevopsConfig } from '@/app/orgs/[orgslug]/dash/revops/config/page.search'
import { searchMeta as schoolRevopsKnowledge } from '@/app/orgs/[orgslug]/dash/revops/knowledge/page.search'
import { searchMeta as schoolTimetable } from '@/app/orgs/[orgslug]/dash/timetable/page.search'
import { searchMeta as schoolTimetableGenerate } from '@/app/orgs/[orgslug]/dash/timetable/generate/page.search'
import { searchMeta as schoolTimetableLessons } from '@/app/orgs/[orgslug]/dash/timetable/lessons/page.search'
import { searchMeta as schoolTimetableConflicts } from '@/app/orgs/[orgslug]/dash/timetable/conflicts/page.search'
import { searchMeta as schoolLiveClasses } from '@/app/orgs/[orgslug]/dash/live-classes/page.search'
import { searchMeta as schoolAttendance } from '@/app/orgs/[orgslug]/dash/attendance/page.search'
import { searchMeta as schoolAttendanceHistory } from '@/app/orgs/[orgslug]/dash/attendance/history/page.search'
import { searchMeta as schoolAttendanceExcuses } from '@/app/orgs/[orgslug]/dash/attendance/excuses/page.search'
import { searchMeta as schoolAttendancePastoral } from '@/app/orgs/[orgslug]/dash/attendance/pastoral/page.search'
import { searchMeta as schoolAttendanceBulk } from '@/app/orgs/[orgslug]/dash/attendance/bulk/page.search'
import { searchMeta as schoolAttendanceDigest } from '@/app/orgs/[orgslug]/dash/attendance/digest/page.search'
import { searchMeta as schoolGradebook } from '@/app/orgs/[orgslug]/dash/gradebook/page.search'
import { searchMeta as schoolGradebookReportCards } from '@/app/orgs/[orgslug]/dash/gradebook/report-cards/page.search'
import { searchMeta as schoolExams } from '@/app/orgs/[orgslug]/dash/exams/page.search'
import { searchMeta as examSittings } from '@/app/orgs/[orgslug]/dash/exams/sittings/page.search'
import { searchMeta as examSeating } from '@/app/orgs/[orgslug]/dash/exams/seating/page.search'
import { searchMeta as examIncidents } from '@/app/orgs/[orgslug]/dash/exams/incidents/page.search'
import { searchMeta as examResits } from '@/app/orgs/[orgslug]/dash/exams/resits/page.search'
import { searchMeta as schoolAiTutor } from '@/app/orgs/[orgslug]/dash/ai-tutor/page.search'
import { searchMeta as schoolFees } from '@/app/orgs/[orgslug]/dash/fees/page.search'
import { searchMeta as feesArrears } from '@/app/orgs/[orgslug]/dash/fees/arrears/page.search'
import { searchMeta as feesReconciliation } from '@/app/orgs/[orgslug]/dash/fees/reconciliation/page.search'
import { searchMeta as feesReminders } from '@/app/orgs/[orgslug]/dash/fees/reminders/page.search'
import { searchMeta as schoolFinancials } from '@/app/orgs/[orgslug]/dash/financials/page.search'
import { searchMeta as schoolHr } from '@/app/orgs/[orgslug]/dash/hr/page.search'
import { searchMeta as payroll } from '@/app/orgs/[orgslug]/dash/payroll/page.search'
import { searchMeta as schoolLibrary } from '@/app/orgs/[orgslug]/dash/school-library/page.search'
import { searchMeta as libraryHolds } from '@/app/orgs/[orgslug]/dash/school-library/reservations/page.search'
import { searchMeta as schoolMessages } from '@/app/orgs/[orgslug]/dash/messages/page.search'
import { searchMeta as schoolReports } from '@/app/orgs/[orgslug]/dash/reports/page.search'
import { searchMeta as reportsAttendance } from '@/app/orgs/[orgslug]/dash/reports/attendance/page.search'
import { searchMeta as reportsGrades } from '@/app/orgs/[orgslug]/dash/reports/grades/page.search'
import { searchMeta as reportsFees } from '@/app/orgs/[orgslug]/dash/reports/fees/page.search'
import { searchMeta as reportsAdmissions } from '@/app/orgs/[orgslug]/dash/reports/admissions/page.search'
import { searchMeta as schoolSettings } from '@/app/orgs/[orgslug]/dash/school-settings/page.search'
import { searchMeta as settingsPeople } from '@/app/orgs/[orgslug]/dash/school-settings/people/page.search'
import { searchMeta as settingsRoles } from '@/app/orgs/[orgslug]/dash/school-settings/roles/page.search'
import { searchMeta as counseling } from '@/app/orgs/[orgslug]/dash/counseling/page.search'
import { searchMeta as counselingCareer } from '@/app/orgs/[orgslug]/dash/counseling/career/page.search'
import { searchMeta as schoolAlumni } from '@/app/orgs/[orgslug]/dash/alumni/page.search'
import { searchMeta as schoolDiscipline } from '@/app/orgs/[orgslug]/dash/discipline/page.search'
import { searchMeta as schoolGamification } from '@/app/orgs/[orgslug]/dash/gamification/page.search'
import { searchMeta as schoolGamificationLeaderboard } from '@/app/orgs/[orgslug]/dash/gamification/leaderboard/page.search'
import { searchMeta as schoolCertificates } from '@/app/orgs/[orgslug]/dash/certificates-manager/page.search'
import { searchMeta as schoolCertificatesIssued } from '@/app/orgs/[orgslug]/dash/certificates-manager/issued/page.search'
import { searchMeta as schoolPathways } from '@/app/orgs/[orgslug]/dash/pathways/page.search'
import { searchMeta as schoolPathwaysProgress } from '@/app/orgs/[orgslug]/dash/pathways/progress/page.search'

/** Presentation metadata for every school screen that has a `page.search.ts`. */
const SCHOOL_PAGE_META: Record<string, SearchMeta> = Object.fromEntries(
  (
    [
      schoolCampus,
      schoolAdmissions,
      schoolAdmissionsLeads,
      schoolAdmissionsApplications,
      schoolAdmissionsOffers,
      schoolAdmissionsCampaigns,
      schoolAdmissionsWorklist,
      schoolRevops,
      schoolRevopsConfig,
      schoolRevopsKnowledge,
      schoolTimetable,
      schoolTimetableGenerate,
      schoolTimetableLessons,
      schoolTimetableConflicts,
      schoolLiveClasses,
      schoolAttendance,
      schoolAttendanceHistory,
      schoolAttendanceExcuses,
      schoolAttendancePastoral,
      schoolAttendanceBulk,
      schoolAttendanceDigest,
      schoolGradebook,
      schoolGradebookReportCards,
      schoolExams,
      examSittings,
      examSeating,
      examIncidents,
      examResits,
      schoolAiTutor,
      schoolFees,
      feesArrears,
      feesReconciliation,
      feesReminders,
      schoolFinancials,
      schoolHr,
      payroll,
      schoolLibrary,
      libraryHolds,
      schoolMessages,
      schoolReports,
      reportsAttendance,
      reportsGrades,
      reportsFees,
      reportsAdmissions,
      schoolSettings,
      settingsPeople,
      settingsRoles,
      counseling,
      counselingCareer,
      schoolAlumni,
      schoolDiscipline,
      schoolGamification,
      schoolGamificationLeaderboard,
      schoolCertificates,
      schoolCertificatesIssued,
      schoolPathways,
      schoolPathwaysProgress,
    ] as SearchMeta[]
  ).map((m) => [m.href, m] as const)
)

/**
 * `dash.<module>.<sub-route>` for a tab that has no `page.search.ts` of its
 * own, e.g. `/dash/exams/sittings` -> `dash.exams.sittings`.
 */
function derivedId(moduleKey: string, root: string, href: string): string {
  const rest = href.startsWith(root) ? href.slice(root.length) : href
  const parts = rest.split('/').filter(Boolean)
  return parts.length ? `dash.${moduleKey}.${parts.join('.')}` : `dash.${moduleKey}`
}

/**
 * Every school module and tab, straight from SCHOOL_MODULES.
 *
 * This is the whole point of the file: the palette's school entries used to be
 * a hand-written list that had already drifted (five modules were in both
 * menus but not here, and `/dash/payroll` was here but in neither menu).
 * Iterating the module table means a screen cannot be in the sidebar and
 * missing from Ctrl+K again.
 *
 * Gating resolves in this order, and never widens:
 *   1. the tab's own `access` / `featureKey` in SCHOOL_MODULES, when set;
 *   2. the screen's own `page.search.ts`;
 *   3. the module root's `page.search.ts` -- a tab inherits its module's gate,
 *      so a screen nobody wrote a file for is not silently open to everyone.
 * Step 1 is authoritative because SCHOOL_MODULES is what the sidebar and the
 * in-module tabs read; the fallbacks exist only for tabs that predate it.
 */
const schoolModulePages: SearchMeta[] = Object.entries(SCHOOL_MODULES).flatMap(
  ([moduleKey, mod]) => {
    const rootMeta = SCHOOL_PAGE_META[mod.root]
    return mod.tabs.map<SearchMeta>((tab) => {
      const own = SCHOOL_PAGE_META[tab.href]
      return {
        ...(own ?? {}),
        id: own?.id ?? derivedId(moduleKey, mod.root, tab.href),
        // No translation exists for a tab with no `page.search.ts`, so the
        // label is used literally: i18next returns the key when it is missing,
        // which renders the English label rather than a raw key path.
        titleKey: own?.titleKey ?? tab.label,
        icon: own?.icon ?? rootMeta?.icon ?? SquaresFour,
        href: tab.href,
        group: own?.group ?? 'navigation',
        featureKey: tab.featureKey ?? own?.featureKey ?? rootMeta?.featureKey,
        schoolAccess: tab.access ?? own?.schoolAccess ?? rootMeta?.schoolAccess,
      }
    })
  }
)

/**
 * School routes that exist but are not a tab in SCHOOL_MODULES.
 *
 * `/dash/admissions/campaigns` is the only one: the page is built and was
 * reachable from Ctrl+K, but the admissions module's tab strip does not offer
 * it. Kept so nothing that used to be discoverable disappears; it should
 * either become a tab in SCHOOL_MODULES or be deleted.
 */
const EXTRA_SCHOOL_PAGES: SearchMeta[] = [schoolAdmissionsCampaigns]

export const dashboardPages: SearchMeta[] = [
  home,
  courses,
  coursesMigrate,
  assignments,
  communities,
  podcasts,
  boards,
  playgrounds,
  analytics,
  ...users,
  ...org,
  ...payments,
  ...account,
  ...schoolModulePages,
  ...EXTRA_SCHOOL_PAGES,
  // Verbs, not destinations. The palette renders these in their own group;
  // they carry the same featureKey/schoolAccess gating as the pages above.
  ...dashboardActions,
]
