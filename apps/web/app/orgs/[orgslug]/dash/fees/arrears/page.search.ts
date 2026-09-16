import { TrendDown } from '@phosphor-icons/react'
import type { SearchMeta } from '@/lib/dashboard-search/types'

// `titleKey` is a literal, not a key path: no translation exists for this
// screen yet, and i18next returns the key itself when it is missing, so this
// renders "Fee arrears" rather than a raw `dashboard.search.entries.*`
// string. Replace it with the real key once it is added to locales/en.json.
export const searchMeta: SearchMeta = {
  id: 'dash.fees.arrears',
  titleKey: 'Fee arrears',
  icon: TrendDown,
  href: '/dash/fees/arrears',
  group: 'navigation',
  // Same gate as the rest of Fees: sms_fees.py's _BURSAR is
  // SUPER_ADMIN / SCHOOL_ADMIN / STAFF, which is `backOffice`.
  schoolAccess: 'backOffice',
  featureKey: 'sms_fees',
}
