import { Buildings } from '@phosphor-icons/react'
import type { SearchMeta } from '@/lib/dashboard-search/types'

export const searchMeta: SearchMeta = {
  id: 'dash.campus',
  titleKey: 'dashboard.search.entries.campus.title',
  descriptionKey: 'dashboard.search.entries.campus.description',
  keywordsKey: 'dashboard.search.entries.campus.keywords',
  icon: Buildings,
  href: '/dash/campus',
  group: 'navigation',
  schoolAccess: 'administer',
}
