import { HeartHalf } from '@phosphor-icons/react'
import type { SearchMeta } from '@/lib/dashboard-search/types'

export const searchMeta: SearchMeta = {
  id: 'dash.counseling',
  titleKey: 'dashboard.search.entries.counseling.title',
  descriptionKey: 'dashboard.search.entries.counseling.description',
  keywordsKey: 'dashboard.search.entries.counseling.keywords',
  icon: HeartHalf,
  href: '/dash/counseling',
  group: 'navigation',
  // PSYCHOLOGIST + leadership. Not 'teach': a teacher cannot read any of it.
  schoolAccess: 'counsel',
  featureKey: 'tutor_counseling',
}
