import { ListBullets } from '@phosphor-icons/react'
import type { SearchMeta } from '@/lib/dashboard-search/types'

export const searchMeta: SearchMeta = {
  id: 'dash.admissions.leads',
  titleKey: 'dashboard.search.entries.admissionsLeads.title',
  descriptionKey: 'dashboard.search.entries.admissionsLeads.description',
  keywordsKey: 'dashboard.search.entries.admissionsLeads.keywords',
  icon: ListBullets,
  href: '/dash/admissions/leads',
  group: 'navigation',
  schoolAccess: 'administer',
  featureKey: 'revops',
}
