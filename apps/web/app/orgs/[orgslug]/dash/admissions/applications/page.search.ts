import { FileText } from '@phosphor-icons/react'
import type { SearchMeta } from '@/lib/dashboard-search/types'

export const searchMeta: SearchMeta = {
  id: 'dash.admissions.applications',
  titleKey: 'dashboard.search.entries.admissionsApplications.title',
  descriptionKey: 'dashboard.search.entries.admissionsApplications.description',
  keywordsKey: 'dashboard.search.entries.admissionsApplications.keywords',
  icon: FileText,
  href: '/dash/admissions/applications',
  group: 'navigation',
  schoolAccess: 'administer',
  featureKey: 'revops',
}
