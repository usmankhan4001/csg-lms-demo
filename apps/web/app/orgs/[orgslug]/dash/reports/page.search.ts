import { ChartBar } from '@phosphor-icons/react'
import type { SearchMeta } from '@/lib/dashboard-search/types'

export const searchMeta: SearchMeta = {
  id: 'dash.reports',
  titleKey: 'dashboard.search.entries.reports.title',
  descriptionKey: 'dashboard.search.entries.reports.description',
  keywordsKey: 'dashboard.search.entries.reports.keywords',
  icon: ChartBar,
  href: '/dash/reports',
  group: 'navigation',
  // Matches the router's own gate (SUPER_ADMIN / SCHOOL_ADMIN): this mixes fee
  // collection and admissions with academics, so it is office data rather than
  // something every class teacher should discover.
  schoolAccess: 'administer',
  featureKey: 'sms_reports',
}
