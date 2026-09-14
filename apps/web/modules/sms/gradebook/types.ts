/**
 * Types mirroring `apps/api/src/schemas/sms_gradebook.py`.
 */

export interface GradeInterval {
  grade: string
  min_percentage: number
  max_percentage: number
  gpa_point: number
}

export interface GradingScaleRead {
  id: number
  name: string
  description?: string | null
  intervals: GradeInterval[]
  is_default: boolean
}

export interface GradingScaleCreate {
  name: string
  description?: string | null
  intervals: GradeInterval[]
  is_default?: boolean
}

export interface AssessmentPlanRead {
  id: number
  course_id: number
  section_id?: number | null
  academic_term_id?: number | null
  assessment_name: string
  weight_percentage: number
  max_score: number
}

export interface AssessmentPlanCreate {
  course_id: number
  section_id?: number | null
  academic_term_id?: number | null
  assessment_name: string
  weight_percentage: number
  max_score?: number
}

export interface GradebookEntryInput {
  student_id: number
  raw_score: number
  remarks?: string | null
}

export interface BatchGradebookEntryRequest {
  assessment_plan_id: number
  entries: GradebookEntryInput[]
  graded_by?: number | null
}

export interface GradebookEntryRead {
  id: number
  student_id: number
  assessment_plan_id: number
  raw_score: number
  max_score: number
  weighted_score?: number | null
  letter_grade?: string | null
  gpa_point?: number | null
  remarks?: string | null
  graded_by?: number | null
  graded_at: string
}

export interface CourseGradeSummary {
  course_id: number
  course_name?: string | null
  credits: number
  total_raw_percentage: number
  total_weighted_percentage: number
  letter_grade: string
  gpa_point: number
  /**
   * False when nothing has been marked for this course yet. Such a course is
   * EXCLUDED from the cumulative GPA rather than counted as 0.0 quality points
   * over its credits — which silently dragged every average down and made
   * unmarked coursework look like failed coursework.
   */
  has_grades: boolean
  assessment_breakdown: Record<string, unknown>[]
}

/**
 * Mirrors `ReportCardStatus` in apps/api/src/schemas/sms_gradebook.py.
 *
 * LOWERCASE, and that casing is load-bearing. The Python enum is
 * `DRAFT = "draft"` / `SENT = "sent"` and Pydantic serialises the VALUE, so
 * the wire format is lowercase. This union previously declared 'DRAFT' |
 * 'SENT', which meant every `status === 'SENT'` / `=== 'DRAFT'` comparison in
 * ReportCardPanel was permanently false -- so after generating a draft neither
 * the Send nor the PDF button ever rendered and the lifecycle was unreachable
 * from the UI. Same dead-branch class as the PARTIALLY_PAID/OVERDUE voucher
 * statuses and OfferStatus.EXPIRED.
 */
export type ReportCardStatus = 'draft' | 'sent'

/**
 * The PERSISTED report-card record, distinct from
 * `StudentTermReportCardResponse` (which is the live-computed preview and
 * carries no id). This one has an `id`, which is what the send and PDF
 * endpoints key on.
 */
export interface TermReportCardRecordRead {
  id: number
  student_id: number
  section_id: number
  academic_term_id: number
  status: ReportCardStatus
  total_credits: number
  /**
   * NULL when total_credits is 0. The stored TermReportCard.gpa column is NOT
   * NULL so it holds 0.0 for an ungraded student; that is a storage artefact,
   * not a measured grade, and the API nulls it on the way out. Render it as
   * "No grades recorded" — never 0.00, never "F".
   */
  cumulative_gpa?: number | null
  overall_letter_grade?: string | null
  remarks?: string | null
  ai_narrative?: string | null
  courses?: CourseGradeSummary[]
  calculated_at?: string
  sent_at?: string | null
  sent_by?: string | null
}

export interface GenerateReportCardDraftRequest {
  section_id: number
  academic_term_id: number
  /** False refreshes grade data without spending an AI call or clobbering a
   *  narrative a teacher has hand-edited. */
  generate_narrative?: boolean
}

export interface StudentTermReportCardResponse {
  student_id: number
  section_id: number
  academic_term_id: number
  total_credits: number
  /** NULL when the student has no graded credits. Not 0.0 and not "F". */
  cumulative_gpa?: number | null
  overall_letter_grade?: string | null
  remarks?: string | null
  courses: CourseGradeSummary[]
  generated_at: string
  /** The persisted record this was upserted into — the id the send/PDF
   *  endpoints key on. Present for any card that exists server-side, which is
   *  what makes a card generated in an earlier session reachable. */
  report_card_id?: number | null
  report_card_status?: ReportCardStatus | null
}

/** Saved marks for a section. Only entries that EXIST are listed — a student
 *  with no mark is absent from `entries`, never zero-filled. */
export interface SectionGradebookEntriesResponse {
  section_id: number
  assessment_plan_ids: number[]
  entries: GradebookEntryRead[]
}

/* ------------------------------------------- whole-section term-end runs */

/**
 * What actually happened to ONE student's card in a batch run.
 *
 * Mirrors `BatchReportCardOutcome` in apps/api/src/schemas/sms_gradebook.py.
 * An outcome string rather than a success count, because at term end a teacher
 * needs to know WHICH students were skipped and why — not that "27 of 30
 * succeeded".
 */
export type ReportCardOutcome =
  | 'drafted'
  /** The card exists but carries NO grade: that student has nothing marked.
   *  Deliberately distinct from `drafted` — collapsing the two would let a
   *  teacher send a section believing every card was complete. */
  | 'drafted_ungraded'
  | 'skipped_sent'
  | 'recalculated'
  | 'no_report_card'
  | 'sent'
  | 'already_sent'
  | 'not_found'

export interface BatchReportCardOutcome {
  student_id?: number | null
  report_card_id?: number | null
  outcome: ReportCardOutcome
  detail?: string | null
  /** Present only on a recalculation, so a teacher can see what moved. */
  previous_cumulative_gpa?: number | null
  cumulative_gpa?: number | null
}

export interface BatchReportCardResponse {
  results: BatchReportCardOutcome[]
}

export interface BatchDraftRequest {
  section_id: number
  academic_term_id: number
  /** False refreshes grade data without spending an AI call or clobbering a
   *  narrative a teacher has hand-edited. */
  generate_narrative?: boolean
}

export interface BatchSendRequest {
  /** Explicit ids, never a section: a section is a moving target, and thirty
   *  report cards cannot be recalled. */
  report_card_ids: number[]
}

export interface RecalculateRequest {
  section_id: number
  academic_term_id: number
}

/* --------------------------------------------------- mark audit trail */

/**
 * One append-only entry in a mark's history.
 *
 * `previous_raw_score` is null on a `created` row — there was no previous
 * mark. That is deliberately distinct from 0.0, which is a real score.
 */
export interface GradeChangeEventRead {
  id: number
  gradebook_entry_id: number
  student_id: number
  assessment_plan_id: number
  section_id?: number | null
  action: string
  previous_raw_score?: number | null
  new_raw_score: number
  previous_letter_grade?: string | null
  new_letter_grade?: string | null
  max_score: number
  changed_by_user_id?: number | null
  reason?: string | null
  created_at: string
}

/** Oldest first — an audit trail reads as a narrative: what it was, then what
 *  happened to it. */
export interface GradeHistoryResponse {
  gradebook_entry_id: number
  student_id: number
  assessment_plan_id: number
  events: GradeChangeEventRead[]
}

/* ------------------------------------------------------ cumulative GPA */

/**
 * Mirrors the dict returned by `calculate_cumulative_gpa`.
 *
 * `weighted_gpa` is GONE, not optional: the old one added +0.5 to every course
 * as "standard honors weighting" while nothing in the model marks a course as
 * honours, so it inflated every GPA on a distinction the system cannot make.
 *
 * `unweighted_gpa`, `academic_standing` and `honor_roll` are NULLABLE. This
 * endpoint previously returned a hardcoded 4.0 / "Good Standing" /
 * honor_roll: true for a student with ZERO grades. A null here means no graded
 * coursework — render that, never 0.0 and never "F".
 */
export interface StudentGpaResponse {
  student_id: number
  total_courses: number
  graded_courses: number
  total_credits: number
  unweighted_gpa?: number | null
  academic_standing?: string | null
  honor_roll?: boolean | null
  /** Set when there is no GPA, explaining why. */
  detail?: string | null
}
