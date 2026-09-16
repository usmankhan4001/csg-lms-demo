import { Trophy } from '@phosphor-icons/react'
import type { SearchMeta } from '@/lib/dashboard-search/types'

// `titleKey` is a literal, not a key path: no translation exists for this
// screen yet, and i18next returns the key itself when it is missing, so this
// renders "Gamification" rather than a raw `dashboard.search.entries.*`
// string. Replace it with the real key once it is added to locales/en.json.
export const searchMeta: SearchMeta = {
  id: 'dash.gamification',
  titleKey: 'Gamification',
  icon: Trophy,
  href: '/dash/gamification',
  group: 'navigation',
  // Exact match with the router: sms_gamification.py gates every endpoint on
  // SUPER_ADMIN / SCHOOL_ADMIN / TEACHER, which is `teach`.
  schoolAccess: 'teach',
}
