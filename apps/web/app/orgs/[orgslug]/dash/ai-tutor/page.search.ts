import { Robot } from '@phosphor-icons/react'
import type { SearchMeta } from '@/lib/dashboard-search/types'

export const searchMeta: SearchMeta = {
  id: 'dash.ai-tutor',
  titleKey: 'dashboard.search.entries.ai-tutor.title',
  descriptionKey: 'dashboard.search.entries.ai-tutor.description',
  keywordsKey: 'dashboard.search.entries.ai-tutor.keywords',
  icon: Robot,
  href: '/dash/ai-tutor',
  group: 'navigation',
  schoolAccess: 'teach',
  featureKey: 'tutor_counseling',
}
