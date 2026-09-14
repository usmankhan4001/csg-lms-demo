import type { SearchMeta } from './types'
import { dashboardActions } from './actions'

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

// School (SMS) modules. Registered here so Ctrl+K reaches the whole app, not
// only Learnhouse's own pages.
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
import { searchMeta as schoolGradebookReportCards } from '@/app/orgs/[orgslug]/dash/gradebook/report-cards/page.search'
import { searchMeta as schoolReports } from '@/app/orgs/[orgslug]/dash/reports/page.search'
import { searchMeta as schoolSettings } from '@/app/orgs/[orgslug]/dash/school-settings/page.search'
import { searchMeta as schoolGradebook } from '@/app/orgs/[orgslug]/dash/gradebook/page.search'
import { searchMeta as schoolExams } from '@/app/orgs/[orgslug]/dash/exams/page.search'
import { searchMeta as schoolAiTutor } from '@/app/orgs/[orgslug]/dash/ai-tutor/page.search'
import { searchMeta as schoolFees } from '@/app/orgs/[orgslug]/dash/fees/page.search'
import { searchMeta as schoolFinancials } from '@/app/orgs/[orgslug]/dash/financials/page.search'
import { searchMeta as schoolHr } from '@/app/orgs/[orgslug]/dash/hr/page.search'
import { searchMeta as schoolLibrary } from '@/app/orgs/[orgslug]/dash/school-library/page.search'
import { searchMeta as schoolMessages } from '@/app/orgs/[orgslug]/dash/messages/page.search'
import { searchMeta as counseling } from '@/app/orgs/[orgslug]/dash/counseling/page.search'
import { searchMeta as counselingCareer } from '@/app/orgs/[orgslug]/dash/counseling/career/page.search'
import { searchMeta as examSeating } from '@/app/orgs/[orgslug]/dash/exams/seating/page.search'
import { searchMeta as examResits } from '@/app/orgs/[orgslug]/dash/exams/resits/page.search'
import { searchMeta as libraryHolds } from '@/app/orgs/[orgslug]/dash/school-library/reservations/page.search'
import { searchMeta as payroll } from '@/app/orgs/[orgslug]/dash/payroll/page.search'

export const dashboardPages: SearchMeta[] = [
  counseling,
  counselingCareer,
  examSeating,
  examResits,
  libraryHolds,
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
  schoolGradebookReportCards,
  schoolReports,
  schoolGradebook,
  schoolExams,
  schoolAiTutor,
  schoolFees,
  schoolFinancials,
  schoolHr,
  schoolLibrary,
  schoolMessages,
  schoolSettings,
  // Verbs, not destinations. The palette renders these in their own group;
  // they carry the same featureKey/schoolAccess gating as the pages above.
  ...dashboardActions,
  payroll,
]
