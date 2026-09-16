import { Certificate } from '@phosphor-icons/react'
import type { SearchMeta } from '@/lib/dashboard-search/types'

// `titleKey` is a literal, not a key path: no translation exists for this
// screen yet, and i18next returns the key itself when it is missing, so this
// renders "Certificates" rather than a raw `dashboard.search.entries.*`
// string. Replace it with the real key once it is added to locales/en.json.
export const searchMeta: SearchMeta = {
  id: 'dash.certificates-manager',
  titleKey: 'Certificates',
  icon: Certificate,
  href: '/dash/certificates-manager',
  group: 'navigation',
  // sms_certificates.py lets TEACHER read templates and issuances but only
  // SCHOOL_ADMIN / SUPER_ADMIN create them, so `teach` is the read gate.
  schoolAccess: 'teach',
}
