import { Exam } from '@phosphor-icons/react'
import type { SearchMeta } from '@/lib/dashboard-search/types'

export const searchMeta: SearchMeta = {
  id: 'dash.exams',
  titleKey: 'dashboard.search.entries.exams.title',
  descriptionKey: 'dashboard.search.entries.exams.description',
  keywordsKey: 'dashboard.search.entries.exams.keywords',
  icon: Exam,
  href: '/dash/exams',
  group: 'navigation',
  schoolAccess: 'teach',
  featureKey: 'sms_exam',
}
