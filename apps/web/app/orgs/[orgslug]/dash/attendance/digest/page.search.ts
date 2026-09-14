import { Envelope } from '@phosphor-icons/react'
import type { SearchMeta } from '@/lib/dashboard-search/types'

export const searchMeta: SearchMeta = {
  id: 'dash.attendance.digest',
  titleKey: 'dashboard.search.entries.attendanceDigest.title',
  descriptionKey: 'dashboard.search.entries.attendanceDigest.description',
  keywordsKey: 'dashboard.search.entries.attendanceDigest.keywords',
  icon: Envelope,
  href: '/dash/attendance/digest',
  group: 'navigation',
  schoolAccess: 'teach',
  featureKey: 'sms_attendance',
}
