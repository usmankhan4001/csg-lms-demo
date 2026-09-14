import { Armchair } from '@phosphor-icons/react'
import type { SearchMeta } from '@/lib/dashboard-search/types'

export const searchMeta: SearchMeta = {
  id: 'dash.exams.seating',
  titleKey: 'dashboard.search.entries.examSeating.title',
  descriptionKey: 'dashboard.search.entries.examSeating.description',
  keywordsKey: 'dashboard.search.entries.examSeating.keywords',
  icon: Armchair,
  href: '/dash/exams/seating',
  group: 'navigation',
  schoolAccess: 'teach',
  featureKey: 'sms_exam',
}
