/**
 * CSG-EMS Admissions CRM & RevOps Types
 * Phase 3 Autonomous Education Operating System
 */

export type PipelineStageId =
  | 'new_inquiry'
  | 'tour_scheduled'
  | 'application_submitted'
  | 'assessment'
  | 'offer_issued'
  | 'closed_enrolled'

export type LeadScoreTier = 'HOT' | 'WARM' | 'COLD'

export type LeadChannel =
  | 'website'
  | 'whatsapp'
  | 'meta_ads'
  | 'google_ads'
  | 'walk_in'
  | 'referral'

export type PriorityLevel = 'URGENT' | 'HIGH' | 'NORMAL' | 'LOW'

export interface ActivityEntry {
  id: string
  type: 'call' | 'whatsapp' | 'email' | 'tour' | 'assessment' | 'offer' | 'matriculation' | 'note'
  title: string
  description: string
  timestamp: string
  officer: string
}

export interface AdmissionsLeadCard {
  id: string
  studentName: string
  parentName: string
  parentPhone: string
  parentEmail: string
  targetGrade: string
  targetCampus: string
  campusId?: number
  feederSchool: string
  feederCategory: 'Private Grammar' | 'International Academy' | 'Montessori Pre-School' | 'Public Elementary' | 'Direct Inbound'
  stage: PipelineStageId
  leadScore: number // 0 - 100
  leadScoreTier: LeadScoreTier
  grossTuitionPKR: number
  scholarshipDiscountPercent: number // e.g. 15%
  netTuitionYieldPKR: number // gross - discount
  assignedOfficer: string
  source: LeadChannel
  lastContactedDate: string
  createdAt: string
  notes?: string
  priority: PriorityLevel
  tags?: string[]
  guardianCnic?: string
  emergencyPhone?: string
  proposedSection?: string
  recommendedPitch?: string
  scoreBreakdown?: {
    academicFit: number
    budgetReadiness: number
    parentEngagement: number
    decisionUrgency: number
  }
  activities?: ActivityEntry[]
}

export interface PipelineStageDefinition {
  id: PipelineStageId
  title: string
  shortTitle: string
  stepNumber: number
  colorTheme: string
  borderAccent: string
  bgAccent: string
  badgeClass: string
  iconName: string
  description: string
  targetSlaDays: number
}

export interface NetTuitionYieldModelConfig {
  cohortGrade: string
  targetCohortSize: number
  currentEnrolledCount: number
  baseAnnualTuitionPKR: number
  meritDiscountPercent: number
  meritQuotaPercent: number
  needBasedDiscountPercent: number
  needQuotaPercent: number
  siblingDiscountPercent: number
  siblingQuotaPercent: number
  attritionBufferPercent: number
}

export interface NetTuitionYieldSummary {
  grossPotentialTuitionPKR: number
  projectedEnrolledRevenuePKR: number
  totalInstitutionalDiscountsPKR: number
  totalNetTuitionYieldPKR: number
  netTuitionYieldPerStudentPKR: number
  yieldRealizationRatePercent: number
  breakevenThresholdStudents: number
  capacityFillRatePercent: number
}

export type FeePlanType =
  | 'ANNUAL_LUMP_SUM'
  | 'BI_ANNUAL'
  | 'QUARTERLY_4_PAY'
  | 'MONTHLY_10_PAY'

export interface BANTScoreBreakdown {
  budget: number
  authority: number
  need: number
  timeline: number
}

export interface MatriculationPayload {
  leadId: string
  studentName: string
  parentName: string
  guardianRelationship: 'Father' | 'Mother' | 'Legal Guardian'
  guardianCnic: string
  emergencyPhone: string
  billingEmail: string
  targetGrade: string
  targetCampus: string
  allocatedSection: string
  rollNumber: string
  feePlan: FeePlanType
  grossAnnualTuition: number
  scholarshipDiscountPercent: number
  netTuitionPayable: number
  admissionFee: number
  labTechDeposit: number
  quarterlyInstallment: number
  enableWhatsAppBilling: boolean
  generateLmsPortalAccount: boolean
  specialInstructions?: string
}

