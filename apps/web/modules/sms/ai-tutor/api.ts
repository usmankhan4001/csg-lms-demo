/**
 * Real fetch calls against `apps/api/src/routers/ai_oversight.py`, mounted at
 * `/api/v1/ai/oversight` (see `src/router.py`'s include_router prefix --
 * verified, not assumed, after a sibling module was found calling a wrong
 * prefix for an entire release).
 */

import { apiDelete, apiGet, apiPost, toQueryString } from '@/lib/api/api-client'
import type {
  AccessBlockRead,
  CreateBlockPayload,
  SafetyIncidentRead,
  TranscriptRead,
} from './types'

export function listTranscripts(
  params: { studentId?: number; sectionId?: number; outcome?: string; limit?: number } = {}
): Promise<TranscriptRead[]> {
  const qs = toQueryString({
    student_id: params.studentId,
    section_id: params.sectionId,
    outcome: params.outcome,
    limit: params.limit,
  })
  return apiGet<TranscriptRead[]>(`/ai/oversight/transcripts${qs}`)
}

export function listSafetyIncidents(params: { limit?: number } = {}): Promise<SafetyIncidentRead[]> {
  return apiGet<SafetyIncidentRead[]>(`/ai/oversight/incidents${toQueryString({ limit: params.limit })}`)
}

export function listAccessBlocks(params: { activeOnly?: boolean } = {}): Promise<AccessBlockRead[]> {
  return apiGet<AccessBlockRead[]>(`/ai/oversight/blocks${toQueryString({ active_only: params.activeOnly })}`)
}

export function createAccessBlock(payload: CreateBlockPayload): Promise<AccessBlockRead> {
  return apiPost<AccessBlockRead>('/ai/oversight/blocks', payload)
}

export function liftAccessBlock(blockId: number): Promise<AccessBlockRead> {
  return apiDelete<AccessBlockRead>(`/ai/oversight/blocks/${blockId}`)
}
