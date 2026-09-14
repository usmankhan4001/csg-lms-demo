import { EnvelopeOpen } from '@phosphor-icons/react'
import type { SearchMeta } from '@/lib/dashboard-search/types'

export const searchMeta: SearchMeta = {
  id: 'dash.attendance.excuses',
  titleKey: 'dashboard.search.entries.attendanceExcuses.title',
  descriptionKey: 'dashboard.search.entries.attendanceExcuses.description',
  keywordsKey: 'dashboard.search.entries.attendanceExcuses.keywords',
  icon: EnvelopeOpen,
  href: '/dash/attendance/excuses',
  group: 'navigation',
  schoolAccess: 'teach',
  featureKey: 'sms_attendance',
}
