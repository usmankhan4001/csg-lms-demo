import { UserPlus } from '@phosphor-icons/react'
import type { SearchMeta } from '@/lib/dashboard-search/types'

export const searchMeta: SearchMeta = {
  id: 'dash.admissions',
  titleKey: 'dashboard.search.entries.admissions.title',
  descriptionKey: 'dashboard.search.entries.admissions.description',
  keywordsKey: 'dashboard.search.entries.admissions.keywords',
  icon: UserPlus,
  href: '/dash/admissions',
  group: 'navigation',
  schoolAccess: 'administer',
  featureKey: 'revops',
}
