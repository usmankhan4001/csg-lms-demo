import { VideoCamera } from '@phosphor-icons/react'
import type { SearchMeta } from '@/lib/dashboard-search/types'

export const searchMeta: SearchMeta = {
  id: 'dash.live-classes',
  titleKey: 'dashboard.search.entries.liveClasses.title',
  descriptionKey: 'dashboard.search.entries.liveClasses.description',
  keywordsKey: 'dashboard.search.entries.liveClasses.keywords',
  icon: VideoCamera,
  href: '/dash/live-classes',
  group: 'navigation',
  // Teaching staff run live classes; the backend's `_CLASS_STAFF` gate and
  // per-class `can_host` check do the real authorization.
  schoolAccess: 'teach',
}
