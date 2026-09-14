import { Compass } from '@phosphor-icons/react'
import type { SearchMeta } from '@/lib/dashboard-search/types'

export const searchMeta: SearchMeta = {
  id: 'dash.counseling.career',
  titleKey: 'dashboard.search.entries.counselingCareer.title',
  descriptionKey: 'dashboard.search.entries.counselingCareer.description',
  keywordsKey: 'dashboard.search.entries.counselingCareer.keywords',
  icon: Compass,
  href: '/dash/counseling/career',
  group: 'navigation',
  // Career guidance is NOT confidential (sms_counseling.py:20) and generation
  // is open to teaching staff, so this is deliberately wider than the module
  // it sits under.
  schoolAccess: 'teach',
  featureKey: 'tutor_counseling',
}
