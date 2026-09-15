import { apiGet, apiPost, apiPatch, toQueryString } from '@/lib/api/api-client'
import { PipelineResponse, LeadRead, LeadStageUpdate } from '@/modules/sms/revops/types'
import {
  MatriculationPayload,
  BANTScoreBreakdown,
  AdmissionsLeadCard,
} from './types'

export async function getAdmissionsPipeline(campusId?: number): Promise<PipelineResponse> {
  return apiGet<PipelineResponse>(`/revops/leads/pipeline${toQueryString({ campus_id: campusId })}`)
}

export async function updateAdmissionsLeadStage(leadId: number, stage: string, notes?: string): Promise<LeadRead> {
  return apiPatch<LeadRead>(`/revops/leads/${leadId}/stage`, { stage, notes })
}

export interface MatriculationHandshakeResult {
  success: boolean
  message: string
  matriculation_id: string
  student: {
    id: number
    username: string
    email: string
    full_name: string
  }
  parent?: {
    id: number
    username: string
    email: string
    full_name: string
  }
  enrollment: {
    enrollment_id: number
    section_id: number
    section_name?: string
    academic_year_id?: number
    enrolled_at: string
  }
  fee_schedule: {
    total_fee: number
    vouchers_created: number
    vouchers: Array<{
      voucher_id: number
      voucher_code: string
      amount_due: number
      due_date: string
      title: string
    }>
  }
}

export async function executeMatriculationHandshake(payload: {
  lead_id: number
  section_id: number
  tuition_plan_id?: number
  annual_tuition_fee?: number
  scholarship_percentage?: number
  payment_terms?: string
}): Promise<MatriculationHandshakeResult> {
  return apiPost<MatriculationHandshakeResult>('/sms/matriculation/handshake', payload)
}

export async function qualifyLeadBANT(leadId: number, payload: {
  budget_bracket?: string
  decision_maker_status?: string
  urgency_level?: string
  curriculum_fit?: string
  interaction_count?: number
}): Promise<{
  lead_id: number
  bant_score: number
  tier: string
  breakdown: Record<string, number>
  recommended_action: string
}> {
  return apiPost(`/sms/matriculation/leads/${leadId}/qualify-bant`, payload)
}

export async function queryAdmissionsCounselor(query: string, leadId?: number): Promise<{
  answer: string
  sources: string[]
  recommended_next_step: string
}> {
  return apiPost('/sms/matriculation/counselor/query', { query, lead_id: leadId })
}
