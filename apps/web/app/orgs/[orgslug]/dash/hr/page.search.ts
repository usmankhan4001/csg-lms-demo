import { IdentificationBadge } from '@phosphor-icons/react'
import type { SearchMeta } from '@/lib/dashboard-search/types'

export const searchMeta: SearchMeta = {
  id: 'dash.hr',
  titleKey: 'dashboard.search.entries.hr.title',
  descriptionKey: 'dashboard.search.entries.hr.description',
  keywordsKey: 'dashboard.search.entries.hr.keywords',
  icon: IdentificationBadge,
  href: '/dash/hr',
  group: 'navigation',
  schoolAccess: 'administer',
  featureKey: 'sms_hr_payroll',
}
