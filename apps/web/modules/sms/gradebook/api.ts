/**
 * Real fetch calls against `apps/api/src/routers/sms_gradebook.py`
 * (mounted at `/api/v1/sms/gradebook`).
 */

import { ApiError, apiGet, apiPost, toQueryString } from '@/lib/api/api-client'
import { authReadyPromise, getActiveAccessToken } from '@/lib/api/session-token-bridge'
import { getAPIUrl } from '@services/config/config'
import type {
  AssessmentPlanCreate,
  BatchDraftRequest,
  BatchReportCardResponse,
  BatchSendRequest,
  GradeHistoryResponse,
  RecalculateRequest,
  ReportCardStatus,
  StudentGpaResponse,
  AssessmentPlanRead,
  BatchGradebookEntryRequest,
  GenerateReportCardDraftRequest,
  GradebookEntryRead,
  GradingScaleCreate,
  GradingScaleRead,
  SectionGradebookEntriesResponse,
  StudentTermReportCardResponse,
  TermReportCardRecordRead,
} from './types'

export function listGradingScales(): Promise<GradingScaleRead[]> {
  return apiGet<GradingScaleRead[]>('/sms/gradebook/scales')
}

export function createGradingScale(payload: GradingScaleCreate): Promise<GradingScaleRead> {
  return apiPost<GradingScaleRead>('/sms/gradebook/scales', payload)
}

export function listAssessmentPlans(params: { courseId?: number; academicTermId?: number } = {}): Promise<AssessmentPlanRead[]> {
  const qs = toQueryString({ course_id: params.courseId, academic_term_id: params.academicTermId })
  return apiGet<AssessmentPlanRead[]>(`/sms/gradebook/plans${qs}`)
}

export function createAssessmentPlan(payload: AssessmentPlanCreate): Promise<AssessmentPlanRead> {
  return apiPost<AssessmentPlanRead>('/sms/gradebook/plans', payload)
}

export function batchEnterGrades(payload: BatchGradebookEntryRequest): Promise<GradebookEntryRead[]> {
  return apiPost<GradebookEntryRead[]>('/sms/gradebook/entries/batch', payload)
}

/**
 * Saved marks for a section, so the grade matrix can pre-load rather than
 * starting blank on every mount.
 *
 * Returns only entries that exist — a student with no mark is simply absent,
 * never zero-filled, because "not marked yet" and "scored 0" mean opposite
 * things on a report card.
 */
export function listSectionGradebookEntries(params: {
  sectionId: number
  assessmentPlanId?: number
  academicTermId?: number
}): Promise<SectionGradebookEntriesResponse> {
  const qs = toQueryString({
    section_id: params.sectionId,
    assessment_plan_id: params.assessmentPlanId,
    academic_term_id: params.academicTermId,
  })
  return apiGet<SectionGradebookEntriesResponse>(`/sms/gradebook/entries${qs}`)
}

export function getStudentReportCard(studentId: number, sectionId: number, academicTermId: number): Promise<StudentTermReportCardResponse> {
  const qs = toQueryString({ section_id: sectionId, academic_term_id: academicTermId })
  return apiGet<StudentTermReportCardResponse>(`/sms/gradebook/report-card/student/${studentId}${qs}`)
}

/* ------------------------------------------------- report-card lifecycle
 * Draft -> Sent. `getStudentReportCard` above now returns `report_card_id`
 * and `report_card_status` for the row it upserts, so send and PDF are
 * reachable for a card generated in ANY session -- not only one whose draft
 * was minted in this one. (TermReportCard is unique on
 * student_id + academic_term_id, so that one lookup is unambiguous.)
 */

export function generateReportCardDraft(
  studentId: number,
  payload: GenerateReportCardDraftRequest
): Promise<TermReportCardRecordRead> {
  return apiPost<TermReportCardRecordRead>(`/sms/gradebook/report-card/student/${studentId}/draft`, payload)
}

export function getReportCardRecord(reportCardId: number): Promise<TermReportCardRecordRead> {
  return apiGet<TermReportCardRecordRead>(`/sms/gradebook/report-card/${reportCardId}`)
}

/** Marks a draft as SENT. The server 409s if it was already sent. */
export function sendReportCard(reportCardId: number): Promise<TermReportCardRecordRead> {
  return apiPost<TermReportCardRecordRead>(`/sms/gradebook/report-card/${reportCardId}/send`)
}

/**
 * Downloads a report card PDF.
 *
 * Deliberately NOT a plain <a href>: the endpoint requires a Bearer token,
 * and an anchor cannot carry one -- the browser would navigate to a 401.
 * This fetches the bytes with the same auth the rest of the module uses and
 * hands the blob to the browser, revoking the object URL afterwards so the
 * blob is not retained for the life of the page.
 */
export async function downloadReportCardPdf(reportCardId: number, filename?: string): Promise<void> {
  await authReadyPromise
  const base = getAPIUrl().replace(/\/+$/, '')
  const token = getActiveAccessToken()

  const response = await fetch(`${base}/sms/gradebook/report-card/${reportCardId}/pdf`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })

  if (!response.ok) {
    // A DRAFT is deliberately not exportable: a PDF is detachable and carries
    // no authorization once saved, so export is stricter than read.
    const detail =
      response.status === 409
        ? 'This report card is still a draft. Send it before downloading a PDF.'
        : response.status === 404
          ? 'That report card no longer exists.'
          : 'Could not download the PDF.'
    throw new ApiError(response.status, detail, response.status === 409 ? 'validation' : 'not_found')
  }

  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  try {
    const link = document.createElement('a')
    link.href = url
    link.download = filename ?? `report-card-${reportCardId}.pdf`
    document.body.appendChild(link)
    link.click()
    link.remove()
  } finally {
    URL.revokeObjectURL(url)
  }
}

/* ------------------------------------------- whole-section term-end runs
 * These are the term-end operations. A teacher runs a SECTION through report
 * cards, not one child at a time.
 */

/**
 * Persisted report cards for a section, with their draft/sent state.
 *
 * This is the only thing that can answer "which cards in this section are
 * still drafts?" — a single card was reachable by id and a single student's by
 * (student, term), but a section was not visible at a glance.
 */
export function listReportCards(params: {
  sectionId?: number
  academicTermId?: number
  studentId?: number
  status?: ReportCardStatus
} = {}): Promise<TermReportCardRecordRead[]> {
  const qs = toQueryString({
    section_id: params.sectionId,
    academic_term_id: params.academicTermId,
    student_id: params.studentId,
    status: params.status,
  })
  return apiGet<TermReportCardRecordRead[]>(`/sms/gradebook/report-cards${qs}`)
}

/** Drafts a card for every actively enrolled student in the section.
 *  Already-sent cards are skipped and reported, never regenerated. */
export function batchDraftReportCards(payload: BatchDraftRequest): Promise<BatchReportCardResponse> {
  return apiPost<BatchReportCardResponse>('/sms/gradebook/report-cards/batch-draft', payload)
}

/**
 * Sends an EXPLICIT list of ids.
 *
 * Deliberately not keyed on a section: a section is a moving target, and
 * "send this section" would fan out to whoever happens to be enrolled at the
 * moment the button is pressed — including a student added since the teacher
 * last looked. Thirty report cards cannot be recalled.
 */
export function batchSendReportCards(payload: BatchSendRequest): Promise<BatchReportCardResponse> {
  return apiPost<BatchReportCardResponse>('/sms/gradebook/report-cards/batch-send', payload)
}

/** Recomputes DRAFT cards after a late mark or a weighting change. SENT cards
 *  are skipped and reported, never silently recomputed under a family. */
export function recalculateReportCards(payload: RecalculateRequest): Promise<BatchReportCardResponse> {
  return apiPost<BatchReportCardResponse>('/sms/gradebook/report-cards/recalculate', payload)
}

/* ---------------------------------------------------- mark audit trail */

/** Append-only change history for one mark: what it was, who changed it, why. */
export function getGradeHistory(entryId: number): Promise<GradeHistoryResponse> {
  return apiGet<GradeHistoryResponse>(`/sms/gradebook/entries/${entryId}/history`)
}

/* ------------------------------------------------------ cumulative GPA */

/** Cumulative GPA across a student's courses. Fields are nullable: a student
 *  with no graded coursework has NO GPA, which is not 0.0. */
export function getStudentGpa(studentId: number): Promise<StudentGpaResponse> {
  return apiGet<StudentGpaResponse>(`/sms/gradebook/students/${studentId}/gpa`)
}
