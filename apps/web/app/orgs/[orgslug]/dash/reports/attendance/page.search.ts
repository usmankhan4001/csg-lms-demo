import { CalendarCheck } from '@phosphor-icons/react'
import type { SearchMeta } from '@/lib/dashboard-search/types'

// `titleKey` is a literal, not a key path: no translation exists for this
// screen yet, and i18next returns the key itself when it is missing, so this
// renders "Attendance report" rather than a raw `dashboard.search.entries.*`
// string. Replace it with the real key once it is added to locales/en.json.
export const searchMeta: SearchMeta = {
  id: 'dash.reports.attendance',
  titleKey: 'Attendance report',
  icon: CalendarCheck,
  href: '/dash/reports/attendance',
  group: 'navigation',
  // sms_reports.py gates every endpoint on _REPORT_ROLES =
  // SUPER_ADMIN / SCHOOL_ADMIN, which is `administer`.
  schoolAccess: 'administer',
  featureKey: 'sms_reports',
}
