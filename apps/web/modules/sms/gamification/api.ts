/**
 * Real calls against `apps/api/src/routers/sms_gamification.py`, mounted at
 * `/api/v1/sms/gamification` (the prefix lives on the APIRouter itself,
 * `sms_gamification.py:26`, not on the include_router call).
 *
 * WHAT THE API ACTUALLY ENFORCES, read from the router rather than assumed:
 *
 *   create_badge   POST /badges        [SUPER_ADMIN, SCHOOL_ADMIN, TEACHER]
 *   award_badge    POST /badges/award  [SUPER_ADMIN, SCHOOL_ADMIN, TEACHER]
 *   add_points     POST /points/add    [SUPER_ADMIN, SCHOOL_ADMIN, TEACHER]
 *   list_badges    GET  /badges        any authenticated principal
 *   get_profile    GET  /profile/{id}  any authenticated principal
 *   get_leaderboard GET /leaderboard   any authenticated principal
 *
 * So every write is teacher-or-above and every read is open to any signed-in
 * user. There is no parent- or student-specific gate, so this client does not
 * imply a family-facing view.
 *
 * Org scoping is applied server-side from the principal (`principal.org_id`),
 * never from anything sent here.
 */

import { apiGet, apiPost } from '@/lib/api/api-client'
import type {
  AddPointsPayload,
  AwardBadgePayload,
  Badge,
  BadgeCreate,
  LeaderboardEntry,
  StudentGamificationProfile,
} from './types'

const BASE = '/sms/gamification'

export function listBadges(): Promise<Badge[]> {
  return apiGet<Badge[]>(`${BASE}/badges`)
}

export function createBadge(payload: BadgeCreate): Promise<Badge> {
  return apiPost<Badge>(`${BASE}/badges`, payload)
}

export function awardBadge(payload: AwardBadgePayload): Promise<unknown> {
  return apiPost<unknown>(`${BASE}/badges/award`, payload)
}

export function addPoints(payload: AddPointsPayload): Promise<unknown> {
  return apiPost<unknown>(`${BASE}/points/add`, payload)
}

export function getLeaderboard(): Promise<LeaderboardEntry[]> {
  return apiGet<LeaderboardEntry[]>(`${BASE}/leaderboard`)
}

/**
 * The user id comes from a leaderboard row, never typed by hand.
 *
 * This matters: the exam seating screen shipped with a text box asking an
 * administrator to type a raw numeric sitting id ("e.g. 4") because the
 * endpoint that LISTS sittings was never wired, so there was nowhere in the
 * product to discover that number. The leaderboard is this module's equivalent
 * discovery surface, which is why profile is reached from a row rather than
 * from a search box.
 */
export function getGamificationProfile(userId: number): Promise<StudentGamificationProfile> {
  return apiGet<StudentGamificationProfile>(`${BASE}/profile/${userId}`)
}
