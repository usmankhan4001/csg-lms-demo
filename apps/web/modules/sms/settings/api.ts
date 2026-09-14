/**
 * Real fetch calls against `apps/api/src/routers/sms_settings.py`, mounted at
 * `/api/v1/sms/settings` (verified by resolving the include prefix, not by
 * reading the source -- a wrong prefix silently broke a module here for a
 * whole release).
 */

import { apiGet, apiPut, toQueryString } from '@/lib/api/api-client'
import type { ResolvedSettingsGroup, SchoolSettingsRead, SettingsGroupKey } from './types'

/**
 * Omitting `campusId` asks for the organisation-wide view. Note the server
 * narrows this: a campus-bound admin always gets their own campus back,
 * whatever they ask for, so the returned `campus_id` is authoritative rather
 * than the one requested.
 */
export function getSchoolSettings(campusId?: number): Promise<SchoolSettingsRead> {
  return apiGet<SchoolSettingsRead>(`/sms/settings${toQueryString({ campus_id: campusId })}`)
}

/**
 * Writes one group. Omitting `campusId` writes the ORG-WIDE default that every
 * campus without its own row inherits -- a broader act than editing one
 * campus, and one the server refuses for campus-bound administrators.
 */
export function updateSettingsGroup(
  group: SettingsGroupKey,
  values: Record<string, any>,
  campusId?: number
): Promise<ResolvedSettingsGroup> {
  return apiPut<ResolvedSettingsGroup>(
    `/sms/settings/${group}${toQueryString({ campus_id: campusId })}`,
    { values }
  )
}
