import { Bank } from '@phosphor-icons/react'
import type { SearchMeta } from '@/lib/dashboard-search/types'

export const searchMeta: SearchMeta = {
  id: 'dash.financials',
  titleKey: 'dashboard.search.entries.financials.title',
  descriptionKey: 'dashboard.search.entries.financials.description',
  keywordsKey: 'dashboard.search.entries.financials.keywords',
  icon: Bank,
  href: '/dash/financials',
  group: 'navigation',
  schoolAccess: 'backOffice',
  featureKey: 'sms_financials',
}
