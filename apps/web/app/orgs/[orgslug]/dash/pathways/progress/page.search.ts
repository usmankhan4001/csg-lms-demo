import { Target } from '@phosphor-icons/react'
import type { SearchMeta } from '@/lib/dashboard-search/types'

// `titleKey` is a literal, not a key path: no translation exists for this
// screen yet, and i18next returns the key itself when it is missing, so this
// renders "Pathway enrolments" rather than a raw `dashboard.search.entries.*`
// string. Replace it with the real key once it is added to locales/en.json.
export const searchMeta: SearchMeta = {
  id: 'dash.pathways.progress',
  titleKey: 'Pathway enrolments',
  icon: Target,
  href: '/dash/pathways/progress',
  group: 'navigation',
  schoolAccess: 'teach',
}
