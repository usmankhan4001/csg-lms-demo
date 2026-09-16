import { Gavel } from '@phosphor-icons/react'
import type { SearchMeta } from '@/lib/dashboard-search/types'

// `titleKey` is a literal, not a key path: no translation exists for this
// screen yet, and i18next returns the key itself when it is missing, so this
// renders "Discipline" rather than a raw `dashboard.search.entries.*` string.
// Replace it with the real key once the string is added to locales/en.json.
export const searchMeta: SearchMeta = {
  id: 'dash.discipline',
  titleKey: 'Discipline',
  icon: Gavel,
  href: '/dash/discipline',
  group: 'navigation',
  // Matches SCHOOL_MODULES and the sidebar (showDiscipline = canTeach). The
  // router is wider -- sms_discipline.py admits STAFF and PSYCHOLOGIST too --
  // so this hides incidents from staff the backend would let record them.
  schoolAccess: 'teach',
}
