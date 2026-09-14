/**
 * Weekly family digest API.
 *
 * Mounted at `/ai/parent` (`apps/api/src/router.py:372`), NOT under `/sms/`.
 * Verified against the running API: an unauthenticated call returns 401, so
 * the route exists and is gated.
 *
 * Access is `require_own_student_or_privileged()`
 * (`ai_parent_digest.py:54`) -- a guardian may read their own child's digest,
 * and school staff may read any. Staff use is a PREVIEW: it is the only way to
 * see what a family is actually sent.
 */

import { apiGet } from '@/lib/api/api-client'
import type { ParentWeeklyDigest } from './types'

export function getParentWeeklyDigest(studentId: number): Promise<ParentWeeklyDigest> {
  return apiGet<ParentWeeklyDigest>(`/ai/parent/students/${studentId}/digest`)
}
