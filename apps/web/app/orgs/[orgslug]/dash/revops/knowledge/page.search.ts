import { BookOpen } from '@phosphor-icons/react'
import type { SearchMeta } from '@/lib/dashboard-search/types'

export const searchMeta: SearchMeta = {
  id: 'dash.revops.knowledge',
  titleKey: 'dashboard.search.entries.revopsKnowledge.title',
  descriptionKey: 'dashboard.search.entries.revopsKnowledge.description',
  keywordsKey: 'dashboard.search.entries.revopsKnowledge.keywords',
  icon: BookOpen,
  href: '/dash/revops/knowledge',
  group: 'navigation',
  schoolAccess: 'administer',
  featureKey: 'revops',
}
