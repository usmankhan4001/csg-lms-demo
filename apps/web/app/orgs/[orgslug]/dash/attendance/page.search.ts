import { CalendarCheck } from '@phosphor-icons/react'
import type { SearchMeta } from '@/lib/dashboard-search/types'

export const searchMeta: SearchMeta = {
  id: 'dash.attendance',
  titleKey: 'dashboard.search.entries.attendance.title',
  descriptionKey: 'dashboard.search.entries.attendance.description',
  keywordsKey: 'dashboard.search.entries.attendance.keywords',
  icon: CalendarCheck,
  href: '/dash/attendance',
  group: 'navigation',
  schoolAccess: 'teach',
  featureKey: 'sms_attendance',
}
