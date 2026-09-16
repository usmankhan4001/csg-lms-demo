import { CalendarDots } from '@phosphor-icons/react'
import type { SearchMeta } from '@/lib/dashboard-search/types'

// `titleKey` is a literal, not a key path: no translation exists for this
// screen yet, and i18next returns the key itself when it is missing, so this
// renders "Exam sittings" rather than a raw `dashboard.search.entries.*`
// string. Replace it with the real key once it is added to locales/en.json.
export const searchMeta: SearchMeta = {
  id: 'dash.exams.sittings',
  titleKey: 'Exam sittings',
  icon: CalendarDots,
  href: '/dash/exams/sittings',
  group: 'navigation',
  schoolAccess: 'teach',
  featureKey: 'sms_exam',
}
