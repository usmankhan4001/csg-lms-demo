import { WarningOctagon } from '@phosphor-icons/react'
import type { SearchMeta } from '@/lib/dashboard-search/types'

export const searchMeta: SearchMeta = {
  id: 'dash.timetable.conflicts',
  titleKey: 'dashboard.search.entries.timetableConflicts.title',
  descriptionKey: 'dashboard.search.entries.timetableConflicts.description',
  keywordsKey: 'dashboard.search.entries.timetableConflicts.keywords',
  icon: WarningOctagon,
  href: '/dash/timetable/conflicts',
  group: 'navigation',
  schoolAccess: 'teach',
  featureKey: 'sms_timetable',
}
