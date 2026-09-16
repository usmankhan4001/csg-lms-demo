import { Receipt } from '@phosphor-icons/react'
import type { SearchMeta } from '@/lib/dashboard-search/types'

// `titleKey` is a literal, not a key path: no translation exists for this
// screen yet, and i18next returns the key itself when it is missing, so this
// renders "Fees report" rather than a raw `dashboard.search.entries.*`
// string. Replace it with the real key once it is added to locales/en.json.
export const searchMeta: SearchMeta = {
  id: 'dash.reports.fees',
  titleKey: 'Fees report',
  icon: Receipt,
  href: '/dash/reports/fees',
  group: 'navigation',
  schoolAccess: 'administer',
  featureKey: 'sms_reports',
}
