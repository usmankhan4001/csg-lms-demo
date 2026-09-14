import { CalendarPlus } from '@phosphor-icons/react'
import type { SearchMeta } from '@/lib/dashboard-search/types'

export const searchMeta: SearchMeta = {
  id: 'dash.attendance.bulk',
  titleKey: 'dashboard.search.entries.attendanceBulkMark.title',
  descriptionKey: 'dashboard.search.entries.attendanceBulkMark.description',
  keywordsKey: 'dashboard.search.entries.attendanceBulkMark.keywords',
  icon: CalendarPlus,
  href: '/dash/attendance/bulk',
  group: 'navigation',
  schoolAccess: 'teach',
  featureKey: 'sms_attendance',
}
