import { CalendarBlank } from '@phosphor-icons/react'
import type { SearchMeta } from '@/lib/dashboard-search/types'

export const searchMeta: SearchMeta = {
  id: 'dash.attendance.history',
  titleKey: 'dashboard.search.entries.attendanceHistory.title',
  descriptionKey: 'dashboard.search.entries.attendanceHistory.description',
  keywordsKey: 'dashboard.search.entries.attendanceHistory.keywords',
  icon: CalendarBlank,
  href: '/dash/attendance/history',
  group: 'navigation',
  schoolAccess: 'teach',
  featureKey: 'sms_attendance',
}
