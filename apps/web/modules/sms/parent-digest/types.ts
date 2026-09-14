/**
 * The weekly family digest (M48).
 *
 * Mirrors `ParentWeeklyDigestResponse` in
 * `apps/api/src/routers/ai_parent_digest.py`.
 *
 * WHAT IS NOT HERE MATTERS AS MUCH AS WHAT IS. This endpoint once returned a
 * hardcoded `attendance_rate: "96.0%"`, an invented `classes_attended: 24`, a
 * fabricated literature lesson and invented teacher praise -- identical for
 * every child in the school. It was rewired to compute from real rows, and the
 * fields with no data source (`assignments_completed`, `average_weekly_score`,
 * `top_strengths`, `growth_areas`, `parent_action_items`, `teacher_praise`)
 * were REMOVED rather than defaulted, because an empty list still implies "we
 * looked and found none".
 *
 * So this type deliberately has no optional slots waiting to be filled. If a
 * figure is not in the response it is absent by design; do not add a field
 * here speculatively.
 */

export interface ParentWeeklyDigest {
  student_id: number
  week_start: string
  week_end: string
  /**
   * A STRING, not a number -- it carries "Not recorded" when no register was
   * taken that week. That is not 0%: a parent reading "0%" concludes their
   * child attended nothing, when the truth is nobody marked a register. The
   * two demand opposite responses from a school.
   */
  attendance_rate: string
  classes_attended: number
  total_classes: number
  tutor_sessions: number
  ai_tutor_topics_explored: string[]
  conversational_summary: string
  generated_at: string
}
