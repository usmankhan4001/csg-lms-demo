import { CalendarCheck, FileText, Receipt, Student, UserPlus } from '@phosphor-icons/react'
import type { SearchMeta } from './types'

/**
 * Ctrl+K actions — entries that DO something rather than just navigate.
 *
 * These live together rather than in each page's `page.search.ts` because an
 * action is a property of the palette's vocabulary, not of the page: several
 * point at the same page, and a few are deliberately plain navigation (see
 * below). Keeping them in one list makes the whole verb surface reviewable at
 * a glance.
 *
 * Gating is identical to navigation entries — `featureKey` for the module
 * toggle, `schoolAccess` for the school role — so a TEACHER cannot find
 * "Generate fee vouchers" here any more than they can see Fees in the
 * sidebar. Discovery gating only; the backend authorizes every request
 * independently.
 *
 * Entries WITHOUT an `action` are intentional. Three of the obvious verbs do
 * not open a dialog that can be addressed from outside:
 *   - "Take roll-call" — the roster is rendered inline on the attendance
 *     page, not in a dialog, so landing on the page IS the action.
 *   - "New assessment" / "Add inquiry" — those dialogs live in page
 *     components owned by other concurrent work; a link that puts the user on
 *     the right page beats a button wired to something half-built.
 * Each is a navigation entry pointing at the right place, and should be
 * upgraded to a real action once its dialog accepts a deep link.
 */
export const dashboardActions: SearchMeta[] = [
  {
    id: 'action.fees.newStructure',
    titleKey: 'dashboard.search.entries.actionNewFeeStructure.title',
    descriptionKey: 'dashboard.search.entries.actionNewFeeStructure.description',
    keywordsKey: 'dashboard.search.entries.actionNewFeeStructure.keywords',
    icon: FileText,
    href: '/dash/fees',
    action: 'new-structure',
    group: 'navigation',
    featureKey: 'sms_fees',
    schoolAccess: 'backOffice',
  },
  {
    id: 'action.fees.generateVouchers',
    titleKey: 'dashboard.search.entries.actionGenerateVouchers.title',
    descriptionKey: 'dashboard.search.entries.actionGenerateVouchers.description',
    keywordsKey: 'dashboard.search.entries.actionGenerateVouchers.keywords',
    icon: Receipt,
    href: '/dash/fees',
    action: 'generate-vouchers',
    group: 'navigation',
    featureKey: 'sms_fees',
    schoolAccess: 'backOffice',
  },
  {
    id: 'action.campus.enrolStudent',
    titleKey: 'dashboard.search.entries.actionEnrolStudent.title',
    descriptionKey: 'dashboard.search.entries.actionEnrolStudent.description',
    keywordsKey: 'dashboard.search.entries.actionEnrolStudent.keywords',
    icon: UserPlus,
    href: '/dash/campus',
    action: 'enrol-student',
    group: 'navigation',
    schoolAccess: 'administer',
  },
  // Navigation-only, for the reasons in the module docstring above.
  {
    id: 'action.attendance.rollCall',
    titleKey: 'dashboard.search.entries.actionTakeRollCall.title',
    descriptionKey: 'dashboard.search.entries.actionTakeRollCall.description',
    keywordsKey: 'dashboard.search.entries.actionTakeRollCall.keywords',
    icon: CalendarCheck,
    href: '/dash/attendance',
    group: 'navigation',
    featureKey: 'sms_attendance',
    schoolAccess: 'teach',
  },
  {
    id: 'action.gradebook.newAssessment',
    titleKey: 'dashboard.search.entries.actionNewAssessment.title',
    descriptionKey: 'dashboard.search.entries.actionNewAssessment.description',
    keywordsKey: 'dashboard.search.entries.actionNewAssessment.keywords',
    icon: Student,
    href: '/dash/gradebook',
    group: 'navigation',
    featureKey: 'sms_gradebook',
    schoolAccess: 'teach',
  },
]
