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
  // The career plan is NOT a confidential record (sms_counseling.py:20-21)
  // and the backend lets a TEACHER generate one (CAREER_GUIDANCE_STAFF_ROLES),
  // so discovery is `teach`. This screen renders the counselling tab strip,
  // but the confidential Sessions tab now carries access: 'counsel' in
  // school-modules.ts, so a teacher landing here is not shown it.
  schoolAccess: 'teach',
  featureKey: 'tutor_counseling',
}
