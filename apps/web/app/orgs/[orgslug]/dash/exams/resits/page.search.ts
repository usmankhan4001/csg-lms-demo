import { ArrowsClockwise } from '@phosphor-icons/react'
import type { SearchMeta } from '@/lib/dashboard-search/types'

export const searchMeta: SearchMeta = {
  id: 'dash.exams.resits',
  titleKey: 'dashboard.search.entries.examResits.title',
  descriptionKey: 'dashboard.search.entries.examResits.description',
  keywordsKey: 'dashboard.search.entries.examResits.keywords',
  icon: ArrowsClockwise,
  href: '/dash/exams/resits',
  group: 'navigation',
  schoolAccess: 'administer',
  featureKey: 'sms_exam',
}
