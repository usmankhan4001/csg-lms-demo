import { Certificate } from '@phosphor-icons/react'
import type { SearchMeta } from '@/lib/dashboard-search/types'

export const searchMeta: SearchMeta = {
  id: 'dash.admissions.offers',
  titleKey: 'dashboard.search.entries.admissionsOffers.title',
  descriptionKey: 'dashboard.search.entries.admissionsOffers.description',
  keywordsKey: 'dashboard.search.entries.admissionsOffers.keywords',
  icon: Certificate,
  href: '/dash/admissions/offers',
  group: 'navigation',
  schoolAccess: 'administer',
  featureKey: 'revops',
}
