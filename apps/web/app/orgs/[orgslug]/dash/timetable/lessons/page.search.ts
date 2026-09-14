import { NotePencil } from '@phosphor-icons/react'
import type { SearchMeta } from '@/lib/dashboard-search/types'

export const searchMeta: SearchMeta = {
  id: 'dash.timetable.lessons',
  titleKey: 'dashboard.search.entries.timetableLessons.title',
  descriptionKey: 'dashboard.search.entries.timetableLessons.description',
  keywordsKey: 'dashboard.search.entries.timetableLessons.keywords',
  icon: NotePencil,
  href: '/dash/timetable/lessons',
  group: 'navigation',
  schoolAccess: 'teach',
  featureKey: 'sms_timetable',
}
