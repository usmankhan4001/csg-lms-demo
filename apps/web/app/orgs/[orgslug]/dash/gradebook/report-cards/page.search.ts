import { Certificate } from '@phosphor-icons/react'
import type { SearchMeta } from '@/lib/dashboard-search/types'

export const searchMeta: SearchMeta = {
  id: 'dash.gradebook.reportCards',
  titleKey: 'dashboard.search.entries.gradebookReportCards.title',
  descriptionKey: 'dashboard.search.entries.gradebookReportCards.description',
  keywordsKey: 'dashboard.search.entries.gradebookReportCards.keywords',
  icon: Certificate,
  href: '/dash/gradebook/report-cards',
  group: 'navigation',
  schoolAccess: 'teach',
  featureKey: 'sms_gradebook',
}
