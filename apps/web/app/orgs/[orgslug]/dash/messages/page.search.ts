import { ChatCircle } from '@phosphor-icons/react'
import type { SearchMeta } from '@/lib/dashboard-search/types'

export const searchMeta: SearchMeta = {
  id: 'dash.messages',
  titleKey: 'dashboard.search.entries.messages.title',
  descriptionKey: 'dashboard.search.entries.messages.description',
  keywordsKey: 'dashboard.search.entries.messages.keywords',
  icon: ChatCircle,
  href: '/dash/messages',
  group: 'navigation',
  schoolAccess: 'anyRole',
}
