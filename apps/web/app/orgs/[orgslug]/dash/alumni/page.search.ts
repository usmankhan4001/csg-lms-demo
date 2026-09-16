import { UsersThree } from '@phosphor-icons/react'
import type { SearchMeta } from '@/lib/dashboard-search/types'

// `titleKey` is a literal, not a key path: no translation exists for this
// screen yet, and i18next returns the key itself when it is missing, so this
// renders "Alumni" rather than a raw `dashboard.search.entries.*` string.
// Replace it with the real key once the string is added to locales/en.json.
export const searchMeta: SearchMeta = {
  id: 'dash.alumni',
  titleKey: 'Alumni',
  icon: UsersThree,
  href: '/dash/alumni',
  group: 'navigation',
  // Matches SCHOOL_MODULES and the sidebar (showAlumni = canAdminister). The
  // router is slightly wider -- sms_alumni.py lets STAFF write profiles -- so
  // this hides the register from back-office staff the backend would admit.
  schoolAccess: 'administer',
}
