import { ClipboardText } from '@phosphor-icons/react'
import type { SearchMeta } from '@/lib/dashboard-search/types'

export const searchMeta: SearchMeta = {
  id: 'dash.admissions.worklist',
  titleKey: 'dashboard.search.entries.admissionsWorklist.title',
  descriptionKey: 'dashboard.search.entries.admissionsWorklist.description',
  keywordsKey: 'dashboard.search.entries.admissionsWorklist.keywords',
  icon: ClipboardText,
  href: '/dash/admissions/worklist',
  group: 'navigation',
  schoolAccess: 'administer',
  featureKey: 'revops',
}
