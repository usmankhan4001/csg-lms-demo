/**
 * Real fetch calls against `apps/api/src/routers/sms_exam.py`
 * (mounted at `/api/v1/sms/exams` — see `src/router.py`).
 *
 * Exam marks are not graded here. Posting results writes ordinary
 * GradebookEntry rows, so `services/sms/gradebook.py` remains the single
 * grading engine.
 */

import { apiGet, apiPatch, apiPost, toQueryString } from '@/lib/api/api-client'
import type {
  AllocateSeatsResponse,
  ExamCreatePayload,
  ExamRead,
  ExamResultEntryInput,
  ExamResultRead,
  ExamResultSummary,
  ExamStatus,
  PostResultsResponse,
  ResitCandidate,
  ResitRead,
  ResitReason,
  ResitStatus,
  SeatAllocationInput,
  SeatAllocationRead,
  ExamIncidentCreate,
  ExamIncidentRead,
  ExamSectionScheduleCreate,
  ExamSectionScheduleRead,
  ExamSittingUpdate,
} from './types'

export function listExams(
  params: {
    campusId?: number
    academicTermId?: number
    courseId?: number
    examStatus?: ExamStatus
    upcomingOnly?: boolean
  } = {}
): Promise<ExamRead[]> {
  const qs = toQueryString({
    campus_id: params.campusId,
    academic_term_id: params.academicTermId,
    course_id: params.courseId,
    exam_status: params.examStatus,
    upcoming_only: params.upcomingOnly,
  })
  return apiGet<ExamRead[]>(`/sms/exams/${qs}`)
}

export function getExam(examId: number): Promise<ExamRead> {
  return apiGet<ExamRead>(`/sms/exams/${examId}`)
}

export function createExam(payload: ExamCreatePayload): Promise<ExamRead> {
  return apiPost<ExamRead>('/sms/exams/', payload)
}

export function listExamResults(examId: number): Promise<ExamResultRead[]> {
  return apiGet<ExamResultRead[]>(`/sms/exams/${examId}/results`)
}

export function enterExamResults(
  examId: number,
  entries: ExamResultEntryInput[]
): Promise<ExamResultRead[]> {
  return apiPost<ExamResultRead[]>(`/sms/exams/${examId}/results`, { entries })
}

export function getExamSummary(examId: number): Promise<ExamResultSummary> {
  return apiGet<ExamResultSummary>(`/sms/exams/${examId}/summary`)
}

export function postResultsToGradebook(examId: number): Promise<PostResultsResponse> {
  return apiPost<PostResultsResponse>(`/sms/exams/${examId}/post-to-gradebook`)
}

// ── Seating ────────────────────────────────────────────────────────────────
// Seats hang off a SITTING (an ExamSectionSchedule), not an exam: one exam is
// sat by several sections at once, each in its own room under its own
// invigilator, so a seat inherits the room it was allocated under.

export function listExamSeats(scheduleId: number): Promise<SeatAllocationRead[]> {
  return apiGet<SeatAllocationRead[]>(`/sms/exams/sittings/${scheduleId}/seats`)
}

/**
 * `replaceExisting` is off by default and the caller must opt in. A re-run
 * that silently moved candidates would send them to a chair someone else is
 * already sitting in on the day.
 */
export function allocateExamSeats(
  scheduleId: number,
  allocations: SeatAllocationInput[],
  replaceExisting = false
): Promise<AllocateSeatsResponse> {
  return apiPost<AllocateSeatsResponse>(`/sms/exams/sittings/${scheduleId}/seats`, {
    allocations,
    replace_existing: replaceExisting,
  })
}

// ── Resits ─────────────────────────────────────────────────────────────────
// A resit is a SECOND sitting linked to the first, never an edit of the
// original result. Both marks stay readable, and the school decides which
// counts — which is what a parent or an inspector asks about.

export function listResits(
  params: {
    originalExamId?: number
    studentId?: number
    resitStatus?: ResitStatus
  } = {}
): Promise<ResitRead[]> {
  const qs = toQueryString({
    original_exam_id: params.originalExamId,
    student_id: params.studentId,
    resit_status: params.resitStatus,
  })
  return apiGet<ResitRead[]>(`/sms/exams/resits${qs}`)
}

export function approveResit(
  examId: number,
  payload: { student_id: number; reason: ResitReason; reason_detail?: string | null }
): Promise<ResitRead> {
  return apiPost<ResitRead>(`/sms/exams/${examId}/resits`, payload)
}

export function scheduleResit(resitId: number, resitExamId: number): Promise<ResitRead> {
  return apiPatch<ResitRead>(`/sms/exams/resits/${resitId}/schedule`, {
    resit_exam_id: resitExamId,
  })
}

/**
 * Candidates a school MAY want to offer a resit, each with the evidence.
 * Deliberately a suggestion: whether an absent child resits is a judgement
 * about that child, not a rule. A `suggested_reason` of null means the record
 * shows a gap to chase (sat the paper, no mark yet) — not grounds for a resit.
 */
export function listResitCandidates(examId: number): Promise<ResitCandidate[]> {
  return apiGet<ResitCandidate[]>(`/sms/exams/${examId}/resit-candidates`)
}

// ─────────────────────────────────────────────────────────────────────────────
// Sittings (ExamSectionSchedule)
//
// These were the missing link in the seating screen: seats are allocated per
// SITTING, but nothing listed the sittings, so an administrator had to type a
// raw numeric schedule id they had no way to discover. `listExamSittings`
// turns that field into a picker.
// ─────────────────────────────────────────────────────────────────────────────

export function listExamSittings(examId: number): Promise<ExamSectionScheduleRead[]> {
  return apiGet<ExamSectionScheduleRead[]>(`/sms/exams/${examId}/sections`)
}

export function scheduleSection(
  examId: number,
  payload: ExamSectionScheduleCreate
): Promise<ExamSectionScheduleRead> {
  return apiPost<ExamSectionScheduleRead>(`/sms/exams/${examId}/sections`, payload)
}

/**
 * The invigilator's record of when the room ACTUALLY started and finished.
 * Both fields are optional and independently settable: a room that has begun
 * but not finished records a start with no end, which is the normal state
 * during an exam — not a half-filled record to be completed later.
 */
export function recordSittingTimes(
  scheduleId: number,
  payload: ExamSittingUpdate
): Promise<ExamSectionScheduleRead> {
  return apiPatch<ExamSectionScheduleRead>(`/sms/exams/sections/${scheduleId}/sitting`, payload)
}

// ─────────────────────────────────────────────────────────────────────────────
// Invigilation incidents
//
// A human's written record of something observed in the room. Not proctoring:
// the API performs no monitoring, and this client adds none.
// ─────────────────────────────────────────────────────────────────────────────

export function listExamIncidents(examId: number): Promise<ExamIncidentRead[]> {
  return apiGet<ExamIncidentRead[]>(`/sms/exams/${examId}/incidents`)
}

export function logExamIncident(
  examId: number,
  payload: ExamIncidentCreate
): Promise<ExamIncidentRead> {
  return apiPost<ExamIncidentRead>(`/sms/exams/${examId}/incidents`, payload)
}
