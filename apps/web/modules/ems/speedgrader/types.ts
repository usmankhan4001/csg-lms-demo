/**
 * CSG-EMS SpeedGrader & Analytical Rubric Types
 */

export type RubricScaleType = 'percentage' | 'points'

export type StandardRubricLevelId = 'exemplary' | 'proficient' | 'developing' | 'novice'

export interface RubricLevel {
  id: string
  name: string
  points: number
  percentage: number
  description: string
  color?: string
}

export interface RubricCriterion {
  id: string
  title: string
  description: string
  weight: number // e.g. 25% or 25 points
  maxPoints: number
  levels: RubricLevel[]
}

export interface LatePenaltyConfig {
  enabled: boolean
  decayPercentPer24h: number // e.g. 5 = 5% decay per 24 hours late
  maxPenaltyPercent: number // e.g. 50% max cap
  gracePeriodHours: number // e.g. 1 hour grace window
}

export interface Rubric {
  id: string
  title: string
  description?: string
  scaleType: RubricScaleType
  totalPoints: number
  criteria: RubricCriterion[]
  latePenaltyConfig: LatePenaltyConfig
  createdAt?: string
  updatedAt?: string
}

export type SubmissionContentType = 'pdf' | 'rich_text' | 'video' | 'code' | 'mixed'

export interface SubmissionAttachment {
  name: string
  url: string
  type: string
  sizeBytes?: number
}

export interface SubmissionAnnotation {
  id: string
  criterionId?: string
  lineOrPageIndex?: number
  selectedText?: string
  comment: string
  authorName: string
  timestamp: string
}

export interface SpeedGraderStudentSubmission {
  id: string
  userId: string
  studentName: string
  studentUsername?: string
  studentEmail: string
  avatarUrl?: string
  submissionDate: string
  dueDate: string
  status: 'SUBMITTED' | 'LATE' | 'GRADED' | 'PENDING' | 'NOT_SUBMITTED'
  attemptNumber?: number
  contentType: SubmissionContentType
  content: {
    text?: string
    pdfUrl?: string
    videoUrl?: string
    videoDurationSeconds?: number
    code?: string
    codeLanguage?: string
    attachments?: SubmissionAttachment[]
    tasks?: Array<{
      id: string
      title: string
      type: string
      studentAnswer?: any
      maxGrade?: number
      grade?: number
    }>
  }
  rubricScores: Record<string, string> // criterionId -> levelId
  manualScoreAdjustment?: number
  teacherFeedback?: string
  aiDraftedFeedback?: string
  aiDraftStatus?: 'idle' | 'drafting' | 'drafted' | 'accepted'
  annotations?: SubmissionAnnotation[]
  rawScore?: number
  finalScore?: number
  gradedAt?: string
  gradedBy?: string
}

export interface LatePenaltyCalculation {
  isLate: boolean
  hoursLate: number
  daysLate: number
  penaltyPercent: number
  rawScore: number
  deductionPoints: number
  finalDecayedScore: number
  decayRateDisplay: string
}
