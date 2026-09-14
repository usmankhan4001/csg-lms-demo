import { MagicWand } from '@phosphor-icons/react'
import type { SearchMeta } from '@/lib/dashboard-search/types'

export const searchMeta: SearchMeta = {
  id: 'dash.timetable.generate',
  titleKey: 'dashboard.search.entries.timetableGenerate.title',
  descriptionKey: 'dashboard.search.entries.timetableGenerate.description',
  keywordsKey: 'dashboard.search.entries.timetableGenerate.keywords',
  icon: MagicWand,
  href: '/dash/timetable/generate',
  group: 'navigation',
  schoolAccess: 'administer',
  featureKey: 'sms_timetable',
}
