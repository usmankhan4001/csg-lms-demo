import { Megaphone } from '@phosphor-icons/react'
import type { SearchMeta } from '@/lib/dashboard-search/types'

export const searchMeta: SearchMeta = {
  id: 'dash.admissions.campaigns',
  titleKey: 'dashboard.search.entries.admissionsCampaigns.title',
  descriptionKey: 'dashboard.search.entries.admissionsCampaigns.description',
  keywordsKey: 'dashboard.search.entries.admissionsCampaigns.keywords',
  icon: Megaphone,
  href: '/dash/admissions/campaigns',
  group: 'navigation',
  schoolAccess: 'administer',
  featureKey: 'revops',
}
