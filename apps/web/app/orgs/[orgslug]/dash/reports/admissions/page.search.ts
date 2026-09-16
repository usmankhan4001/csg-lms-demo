import { UserPlus } from '@phosphor-icons/react'
import type { SearchMeta } from '@/lib/dashboard-search/types'

// `titleKey` is a literal, not a key path: no translation exists for this
// screen yet, and i18next returns the key itself when it is missing, so this
// renders "Admissions report" rather than a raw `dashboard.search.entries.*`
// string. Replace it with the real key once it is added to locales/en.json.
export const searchMeta: SearchMeta = {
  id: 'dash.reports.admissions',
  titleKey: 'Admissions report',
  icon: UserPlus,
  href: '/dash/reports/admissions',
  group: 'navigation',
  schoolAccess: 'administer',
  featureKey: 'sms_reports',
}
