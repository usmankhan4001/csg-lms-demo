import { GraduationCap } from '@phosphor-icons/react'
import type { SearchMeta } from '@/lib/dashboard-search/types'

export const searchMeta: SearchMeta = {
  id: 'dash.gradebook',
  titleKey: 'dashboard.search.entries.gradebook.title',
  descriptionKey: 'dashboard.search.entries.gradebook.description',
  keywordsKey: 'dashboard.search.entries.gradebook.keywords',
  icon: GraduationCap,
  href: '/dash/gradebook',
  group: 'navigation',
  schoolAccess: 'teach',
  featureKey: 'sms_gradebook',
}
