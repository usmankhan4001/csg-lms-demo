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
  // KNOWN MISMATCH -- flagged, not fixed here. This is the AI Tutor OVERSIGHT
  // page, and sms_ai_tutor.py gates its endpoints on _SAFEGUARDING =
  // [SUPER_ADMIN, SCHOOL_ADMIN, PSYCHOLOGIST]; TEACHER is deliberately
  // excluded (see the /safety-flags docstring). `teach` therefore offers the
  // page to a role the backend will 403. It is left as `teach` because that is
  // what SCHOOL_MODULES and the sidebar say, and narrowing only Ctrl+K would
  // hide the entry while the sidebar still links to it. The real fix belongs
  // in school-modules.ts so the sidebar, the tabs and Ctrl+K move together.
  schoolAccess: 'teach',
  featureKey: 'tutor_counseling',
}
