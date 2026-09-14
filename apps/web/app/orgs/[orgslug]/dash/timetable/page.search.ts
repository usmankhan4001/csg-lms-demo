import { CalendarBlank } from '@phosphor-icons/react'
import type { SearchMeta } from '@/lib/dashboard-search/types'

export const searchMeta: SearchMeta = {
  id: 'dash.timetable',
  titleKey: 'dashboard.search.entries.timetable.title',
  descriptionKey: 'dashboard.search.entries.timetable.description',
  keywordsKey: 'dashboard.search.entries.timetable.keywords',
  icon: CalendarBlank,
  href: '/dash/timetable',
  group: 'navigation',
  schoolAccess: 'teach',
  featureKey: 'sms_timetable',
}
