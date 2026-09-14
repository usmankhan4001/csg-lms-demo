import { Money } from '@phosphor-icons/react'
import type { SearchMeta } from '@/lib/dashboard-search/types'

export const searchMeta: SearchMeta = {
  id: 'dash.payroll',
  titleKey: 'dashboard.search.entries.payroll.title',
  descriptionKey: 'dashboard.search.entries.payroll.description',
  keywordsKey: 'dashboard.search.entries.payroll.keywords',
  icon: Money,
  href: '/dash/payroll',
  group: 'navigation',
  // Payroll is staff compensation and carries a separation-of-duties control,
  // so it is administer-gated rather than back-office-wide.
  schoolAccess: 'administer',
  featureKey: 'sms_hr_payroll',
}
