import { WarningOctagon } from '@phosphor-icons/react'
import type { SearchMeta } from '@/lib/dashboard-search/types'

// `titleKey` is a literal, not a key path: no translation exists for this
// screen yet, and i18next returns the key itself when it is missing, so this
// renders "Exam incidents" rather than a raw `dashboard.search.entries.*`
// string. Replace it with the real key once it is added to locales/en.json.
export const searchMeta: SearchMeta = {
  id: 'dash.exams.incidents',
  titleKey: 'Exam incidents',
  icon: WarningOctagon,
  href: '/dash/exams/incidents',
  group: 'navigation',
  schoolAccess: 'teach',
  featureKey: 'sms_exam',
}
