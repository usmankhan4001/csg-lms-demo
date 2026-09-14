import { BookmarkSimple } from '@phosphor-icons/react'
import type { SearchMeta } from '@/lib/dashboard-search/types'

export const searchMeta: SearchMeta = {
  id: 'dash.library.reservations',
  titleKey: 'dashboard.search.entries.libraryHolds.title',
  descriptionKey: 'dashboard.search.entries.libraryHolds.description',
  keywordsKey: 'dashboard.search.entries.libraryHolds.keywords',
  icon: BookmarkSimple,
  href: '/dash/school-library/reservations',
  group: 'navigation',
  schoolAccess: 'backOffice',
  featureKey: 'sms_library',
}
