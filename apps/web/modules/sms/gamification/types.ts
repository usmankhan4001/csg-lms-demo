/**
 * Mirrors `apps/api/src/schemas/sms_gamification.py`.
 *
 * A NOTE ON ZEROES IN THIS MODULE, because the rule elsewhere in this codebase
 * is "absence must never render as zero" and this file deliberately carries
 * zeroes.
 *
 * XP and badge counts are QUANTITIES, not measurements. A student who has
 * earned no points genuinely has zero points, exactly as a student with no
 * badges has zero badges -- so rendering 0 is honest here, unlike an
 * attendance RATE of 0% for a school that never took a register.
 *
 * The one thing the API cannot express: `get_profile`
 * (services/sms/gamification.py:155) returns `total_xp=0, level=1` both for a
 * student who has earned nothing AND for a student with no streak row at all.
 * Those are different facts -- "taking part, nothing yet" versus "not in the
 * scheme" -- and the response cannot distinguish them, so this client does not
 * invent a distinction it cannot see.
 */

export interface Badge {
  id: number
  org_id: number | null
  name: string
  description: string
  icon_name: string
  points_reward: number
  category: string
  created_at: string
}

export interface BadgeCreate {
  name: string
  description: string
  icon_name?: string
  points_reward?: number
  category?: string
}

export interface AwardBadgePayload {
  user_id: number
  badge_id: number
}

export interface AddPointsPayload {
  user_id: number
  points: number
  reason: string
}

export interface LeaderboardEntry {
  rank: number
  user_id: number
  name: string
  total_xp: number
  level: number
  current_streak_days: number
  badges_count: number
}

export interface StudentGamificationProfile {
  user_id: number
  total_xp: number
  level: number
  current_streak_days: number
  longest_streak_days: number
  badges: Badge[]
}

/** Matches the `category` default in BadgeCreate; free text server-side. */
export const BADGE_CATEGORIES = ['academic', 'attendance', 'behaviour', 'participation'] as const
export type BadgeCategory = (typeof BADGE_CATEGORIES)[number]
