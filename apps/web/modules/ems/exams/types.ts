/**
 * CBT Exam & Psychometrics Types (CSG-EMS Phase 2)
 */

export type QuestionStatus = 'ANSWERED' | 'FLAGGED' | 'UNANSWERED'

export type QuestionType = 'SINGLE_CHOICE' | 'MULTIPLE_CHOICE' | 'TEXT_RESPONSE' | 'NUMERIC'

export interface QuestionOption {
  id: string
  label: string
  text: string
}

export interface CBTQuestion {
  id: string
  index: number
  title: string
  prompt: string
  type: QuestionType
  points: number
  options?: QuestionOption[]
  passage?: string
  hint?: string
  category?: string
}

export interface StudentAnswer {
  questionId: string
  selectedOptionIds: string[]
  textResponse: string
  flaggedForReview: boolean
  lastModified: number
  timeSpentSeconds: number
}

export interface ExamSessionState {
  examId: string | number
  studentId: string | number
  studentName: string
  examTitle: string
  courseName?: string
  durationMinutes: number
  startedAt: number
  expiresAt: number
  answers: Record<string, StudentAnswer>
  status: 'IN_PROGRESS' | 'SUBMITTED' | 'TIMED_OUT'
}

export interface KeystrokeLogEntry {
  questionId: string
  timestamp: number
  keyStrokeType: 'OPTION_SELECT' | 'TEXT_INPUT' | 'FLAG_TOGGLE' | 'PALETTE_JUMP'
  payload: string
}

export interface AutosaveBufferState {
  pendingCount: number
  lastSavedAt: number | null
  syncStatus: 'SYNCED' | 'SAVING' | 'OFFLINE_BUFFERED' | 'ERROR'
  errorMessage?: string
}

export interface FormulaItem {
  id: string
  category: 'Mathematics' | 'Physics' | 'Chemistry' | 'Statistics' | 'Computer Science'
  title: string
  formula: string
  description?: string
  variables?: Record<string, string>
}
