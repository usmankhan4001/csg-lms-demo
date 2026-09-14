import { ShieldWarning } from '@phosphor-icons/react'
import type { SearchMeta } from '@/lib/dashboard-search/types'

export const searchMeta: SearchMeta = {
  id: 'dash.attendance.pastoral',
  titleKey: 'dashboard.search.entries.attendancePastoral.title',
  descriptionKey: 'dashboard.search.entries.attendancePastoral.description',
  keywordsKey: 'dashboard.search.entries.attendancePastoral.keywords',
  icon: ShieldWarning,
  href: '/dash/attendance/pastoral',
  group: 'navigation',
  schoolAccess: 'teach',
  featureKey: 'sms_attendance',
}
