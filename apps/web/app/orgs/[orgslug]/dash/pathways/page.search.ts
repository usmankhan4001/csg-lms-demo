import { Signpost } from '@phosphor-icons/react'
import type { SearchMeta } from '@/lib/dashboard-search/types'

// `titleKey` is a literal, not a key path: no translation exists for this
// screen yet, and i18next returns the key itself when it is missing, so this
// renders "Pathways" rather than a raw `dashboard.search.entries.*` string.
// Replace it with the real key once it is added to locales/en.json.
export const searchMeta: SearchMeta = {
  id: 'dash.pathways',
  titleKey: 'Pathways',
  icon: Signpost,
  href: '/dash/pathways',
  group: 'navigation',
  // Matches SCHOOL_MODULES and the sidebar (showPathways = canTeach). The
  // router's read gate also admits STAFF, so this hides pathways from
  // back-office staff the backend would let browse them.
  schoolAccess: 'teach',
}
