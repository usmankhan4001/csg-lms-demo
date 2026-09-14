import { Books } from '@phosphor-icons/react'
import type { SearchMeta } from '@/lib/dashboard-search/types'

export const searchMeta: SearchMeta = {
  id: 'dash.school-library',
  titleKey: 'dashboard.search.entries.school-library.title',
  descriptionKey: 'dashboard.search.entries.school-library.description',
  keywordsKey: 'dashboard.search.entries.school-library.keywords',
  icon: Books,
  href: '/dash/school-library',
  group: 'navigation',
  schoolAccess: 'backOffice',
  featureKey: 'sms_library',
}
