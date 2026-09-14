import { ChartLineUp } from '@phosphor-icons/react'
import type { SearchMeta } from '@/lib/dashboard-search/types'

export const searchMeta: SearchMeta = {
  id: 'dash.revops',
  titleKey: 'dashboard.search.entries.revops.title',
  descriptionKey: 'dashboard.search.entries.revops.description',
  keywordsKey: 'dashboard.search.entries.revops.keywords',
  icon: ChartLineUp,
  href: '/dash/revops',
  group: 'navigation',
  schoolAccess: 'administer',
  featureKey: 'revops',
}
