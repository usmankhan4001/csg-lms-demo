import { Receipt } from '@phosphor-icons/react'
import type { SearchMeta } from '@/lib/dashboard-search/types'

export const searchMeta: SearchMeta = {
  id: 'dash.fees',
  titleKey: 'dashboard.search.entries.fees.title',
  descriptionKey: 'dashboard.search.entries.fees.description',
  keywordsKey: 'dashboard.search.entries.fees.keywords',
  icon: Receipt,
  href: '/dash/fees',
  group: 'navigation',
  schoolAccess: 'backOffice',
  featureKey: 'sms_fees',
}
