/**
 * M01 Admissions — the APPLICATION lifecycle.
 *
 * Distinct from `modules/sms/revops`, which is the LEAD funnel (an enquiry
 * being nurtured toward interest). This is what happens once a family
 * actually applies: a submitted application, supporting documents, an
 * assessment, and a recorded decision.
 *
 * `lead_id` is nullable throughout on purpose — a walk-in family may never
 * have been a tracked lead, and the UI must never assume one exists.
 *
 * Mirrors `apps/api/src/schemas/sms_admissions.py`. Every field the backend
 * declares Optional is optional here too: `score`, `outcome`, `submitted_at`
 * and the verification fields stay null until something real fills them, so
 * an applicant with no assessment can never render as having scored zero.
 */

// ── Enums (mirror apps/api/src/db/sms_admissions.py) ────────────────────────

export type ApplicationStatus =
  | 'DRAFT'
  | 'SUBMITTED'
  | 'DOCUMENTS_PENDING'
  | 'UNDER_REVIEW'
  | 'ASSESSMENT_SCHEDULED'
  | 'ASSESSED'
  | 'OFFERED'
  | 'ACCEPTED'
  | 'ENROLLED'
  | 'REJECTED'
  | 'WITHDRAWN'

export type DocumentType =
  | 'BIRTH_CERTIFICATE'
  | 'PRIOR_SCHOOL_RECORD'
  | 'TRANSFER_CERTIFICATE'
  | 'MEDICAL_RECORD'
  | 'IMMUNISATION_RECORD'
  | 'PHOTOGRAPH'
  | 'GUARDIAN_ID'
  | 'PROOF_OF_ADDRESS'
  | 'OTHER'

export type DocumentVerificationStatus = 'PENDING' | 'VERIFIED' | 'REJECTED'

export type AssessmentOutcome = 'PASSED' | 'FAILED' | 'BORDERLINE' | 'NOT_ATTENDED'

export type AdmissionDecision = 'OFFERED' | 'REJECTED' | 'WAITLISTED'

// ── Reads ───────────────────────────────────────────────────────────────────

export interface ApplicationRead {
  id: number
  application_number: string
  org_id: number
  campus_id: number | null
  lead_id: number | null
  student_name: string
  date_of_birth: string | null
  guardian_name: string
  guardian_email: string | null
  guardian_phone: string | null
  grade_applying_for: string
  academic_year_id: number | null
  status: ApplicationStatus
  submitted_at: string | null
  enrolled_student_id: number | null
  notes: string | null
  created_at: string
  updated_at: string
}

/**
 * Document METADATA. Deliberately carries no url or path — the backend's
 * `DocumentRead` omits them so a document is never reachable by anyone who
 * merely saw this response. Bytes come only from the authorised content
 * endpoint. Do not add a `url` field here.
 */
export interface DocumentRead {
  id: number
  application_id: number
  document_type: DocumentType
  original_filename: string | null
  verification_status: DocumentVerificationStatus
  verified_by_user_id: number | null
  verified_at: string | null
  rejection_reason: string | null
  uploaded_by_user_id: number | null
  uploaded_at: string
}

export interface AssessmentRead {
  id: number
  application_id: number
  assessment_name: string
  scheduled_for: string | null
  venue: string | null
  score: number | null
  max_score: number | null
  outcome: AssessmentOutcome | null
  assessor_notes: string | null
  assessed_by_user_id: number | null
  assessed_at: string | null
  created_at: string
}

export interface DecisionRead {
  id: number
  application_id: number
  decision: AdmissionDecision
  reason: string
  decided_by_user_id: number
  decided_at: string
}

export interface ApplicationDetailRead {
  application: ApplicationRead
  documents: DocumentRead[]
  assessments: AssessmentRead[]
  decisions: DecisionRead[]
  /** True only when every REQUIRED document type is VERIFIED — computed server-side. */
  documents_complete: boolean
  missing_document_types: DocumentType[]
}

// ── Writes ──────────────────────────────────────────────────────────────────

export interface ApplicationCreatePayload {
  campus_id?: number | null
  lead_id?: number | null
  student_name: string
  date_of_birth?: string | null
  guardian_name: string
  guardian_email?: string | null
  guardian_phone?: string | null
  grade_applying_for: string
  academic_year_id?: number | null
  notes?: string | null
}

export interface ApplicationStatusUpdatePayload {
  status: ApplicationStatus
  note?: string | null
}

export interface DocumentVerifyPayload {
  verification_status: DocumentVerificationStatus
  /** Required by the service for a REJECTED status: a rejection with no reason
   *  tells the family nothing about what to resubmit. */
  rejection_reason?: string | null
}

export interface AssessmentSchedulePayload {
  assessment_name: string
  scheduled_for?: string | null
  venue?: string | null
}

export interface AssessmentResultPayload {
  outcome: AssessmentOutcome
  /** Stays absent for NOT_ATTENDED: an applicant who never sat the paper did
   *  not score zero on it. */
  score?: number | null
  max_score?: number | null
  assessor_notes?: string | null
}

export interface DecisionCreatePayload {
  decision: AdmissionDecision
  /** Required, min length 1 server-side. The reason IS the decision trail. */
  reason: string
}

export interface ApplicationListFilters {
  campus_id?: number
  status?: ApplicationStatus
  academic_year_id?: number
  limit?: number
  offset?: number
}
