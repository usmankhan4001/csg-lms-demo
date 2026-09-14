/**
 * Real fetch calls against `apps/api/src/routers/sms_revops_config.py`,
 * mounted at `/api/v1/sms/revops-admin` (router.py:598-602).
 *
 * Verified against the router rather than assumed: updating a knowledge entry
 * is PUT, not PATCH (sms_revops_config.py:336), and there is no
 * `GET /knowledge/{id}` -- a single entry is read from the list.
 */

import { apiDelete, apiGet, apiPost, apiPut, toQueryString } from '@/lib/api/api-client'
import type {
  KnowledgeEntryRead,
  KnowledgeEntryWrite,
  KnowledgeListFilters,
  KnowledgeSearchFilters,
  ResolvedRevOpsGroup,
  RevOpsConfigGroupKey,
  RevOpsConfigRead,
} from './types'

/**
 * `GET /config` -- sms_revops_config.py:96.
 *
 * Omitting `campusId` asks for the organisation-wide view. A campus-bound
 * admin is narrowed to their own campus server-side regardless
 * (`resolve_scoped_campus_id`), so the value that comes back is what they are
 * entitled to see, not necessarily what was asked for.
 */
export function getRevOpsConfig(campusId?: number): Promise<RevOpsConfigRead> {
  return apiGet<RevOpsConfigRead>(
    `/sms/revops-admin/config${toQueryString({ campus_id: campusId })}`
  )
}

/**
 * `PUT /config/{group}` -- sms_revops_config.py:135.
 *
 * Omitting `campusId` writes the ORGANISATION-WIDE default that every campus
 * without its own row inherits. That is a broader act than editing one
 * campus, and the server refuses it for campus-bound administrators.
 */
export function updateRevOpsConfigGroup(
  group: RevOpsConfigGroupKey,
  values: Record<string, unknown>,
  campusId?: number
): Promise<ResolvedRevOpsGroup> {
  return apiPut<ResolvedRevOpsGroup>(
    `/sms/revops-admin/config/${group}${toQueryString({ campus_id: campusId })}`,
    { values }
  )
}

/** `GET /knowledge` -- sms_revops_config.py:239. */
export function listKnowledgeEntries(
  filters: KnowledgeListFilters = {}
): Promise<KnowledgeEntryRead[]> {
  return apiGet<KnowledgeEntryRead[]>(
    `/sms/revops-admin/knowledge${toQueryString({
      campus_id: filters.campus_id,
      status: filters.status,
      category: filters.category,
      limit: filters.limit,
      offset: filters.offset,
    })}`
  )
}

/**
 * `GET /knowledge/search` -- sms_revops_config.py:271.
 *
 * KEYWORD search over title, body and category -- not semantic retrieval.
 * Returns PUBLISHED entries only unless `include_drafts` is set: a draft is a
 * human's working note and must not be quoted at a family.
 */
export function searchKnowledgeEntries(
  filters: KnowledgeSearchFilters
): Promise<KnowledgeEntryRead[]> {
  return apiGet<KnowledgeEntryRead[]>(
    `/sms/revops-admin/knowledge/search${toQueryString({
      q: filters.q,
      campus_id: filters.campus_id,
      include_drafts: filters.include_drafts,
      limit: filters.limit,
    })}`
  )
}

/** `POST /knowledge` -- sms_revops_config.py:302. */
export function createKnowledgeEntry(
  payload: KnowledgeEntryWrite
): Promise<KnowledgeEntryRead> {
  return apiPost<KnowledgeEntryRead>('/sms/revops-admin/knowledge', payload)
}

/** `PUT /knowledge/{id}` -- sms_revops_config.py:336. PUT, not PATCH. */
export function updateKnowledgeEntry(
  entryId: number,
  payload: KnowledgeEntryWrite
): Promise<KnowledgeEntryRead> {
  return apiPut<KnowledgeEntryRead>(`/sms/revops-admin/knowledge/${entryId}`, payload)
}

/**
 * `DELETE /knowledge/{id}` -- sms_revops_config.py:373. School-admin only.
 *
 * The endpoint's own description says archiving is the softer option and the
 * one the UI should prefer, so this is offered only for genuine mistakes.
 */
export function deleteKnowledgeEntry(entryId: number): Promise<void> {
  return apiDelete<void>(`/sms/revops-admin/knowledge/${entryId}`)
}
