import { SlidersHorizontal } from '@phosphor-icons/react'
import type { SearchMeta } from '@/lib/dashboard-search/types'

export const searchMeta: SearchMeta = {
  id: 'dash.revops.config',
  titleKey: 'dashboard.search.entries.revopsConfig.title',
  descriptionKey: 'dashboard.search.entries.revopsConfig.description',
  keywordsKey: 'dashboard.search.entries.revopsConfig.keywords',
  icon: SlidersHorizontal,
  href: '/dash/revops/config',
  group: 'navigation',
  schoolAccess: 'administer',
  featureKey: 'revops',
}
