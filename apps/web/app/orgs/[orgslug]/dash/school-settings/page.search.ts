import { Gear } from '@phosphor-icons/react'
import type { SearchMeta } from '@/lib/dashboard-search/types'

export const searchMeta: SearchMeta = {
  id: 'dash.school-settings',
  titleKey: 'dashboard.search.entries.schoolSettings.title',
  descriptionKey: 'dashboard.search.entries.schoolSettings.description',
  keywordsKey: 'dashboard.search.entries.schoolSettings.keywords',
  icon: Gear,
  href: '/dash/school-settings',
  group: 'settings',
  // Matches the router's own gate (SUPER_ADMIN / SCHOOL_ADMIN). Deliberately
  // NO featureKey: this is where module toggles are administered, so putting
  // it behind one would create a state a school cannot get out of without a
  // database client.
  schoolAccess: 'administer',
}
