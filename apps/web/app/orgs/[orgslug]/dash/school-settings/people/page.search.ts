import { Users } from '@phosphor-icons/react'
import type { SearchMeta } from '@/lib/dashboard-search/types'

// `titleKey` is a literal, not a key path: no translation exists for this
// screen yet, and i18next returns the key itself when it is missing, so this
// renders "School people" rather than a raw `dashboard.search.entries.*`
// string. Replace it with the real key once it is added to locales/en.json.
export const searchMeta: SearchMeta = {
  id: 'dash.school-settings.people',
  titleKey: 'School people',
  icon: Users,
  href: '/dash/school-settings/people',
  group: 'settings',
  // Deliberately NO featureKey, like the rest of School settings: this is
  // where module toggles and school roles are administered, so gating it
  // behind one could strand a school with no way back in.
  schoolAccess: 'administer',
}
