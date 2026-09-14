/**
 * The signed-in guardian's children, each with their resolved academic
 * context (name, section, term).
 *
 * `GET /sms/me` returns only ids; the name/section/term for each child comes
 * from `GET /sms/identity/children/{id}/context`, so this fans out one
 * request per child. Schools have a handful of children per guardian, so a
 * fan-out is fine and keeps us on the endpoints that actually exist rather
 * than inventing a batch route.
 *
 * A child whose context request fails is kept in the list with `context:
 * null` rather than dropped -- silently omitting one of a parent's children
 * would be worse than showing it with its details unavailable.
 */

import { useCallback } from 'react'
import { useApiResource } from '@/api/useApiResource'
import { useSchoolIdentity } from '@/auth/useSchoolIdentity'
import { getChildContext } from './api'
import type { ChildContext } from './types'

export interface ChildEntry {
  studentId: number
  context: ChildContext | null
}

export function useChildren() {
  const { childrenIds, status: identityStatus, error: identityError, refetch: refetchIdentity } = useSchoolIdentity()
  const idsKey = childrenIds.join(',')

  const children = useApiResource<ChildEntry[]>(
    async () => {
      const entries = await Promise.all(
        childrenIds.map(async (studentId): Promise<ChildEntry> => {
          try {
            return { studentId, context: await getChildContext(studentId) }
          } catch {
            return { studentId, context: null }
          }
        })
      )
      return entries
    },
    [idsKey],
    {
      skip: identityStatus === 'loading' || childrenIds.length === 0,
      cacheKey: idsKey ? `parent-children-${idsKey}` : undefined,
    }
  )

  const refetch = useCallback(() => {
    refetchIdentity()
    children.refetch()
  }, [refetchIdentity, children])

  // Surface the identity failure rather than a confusing empty child list:
  // "we could not work out who you are" and "you have no children linked"
  // need different copy.
  if (identityStatus === 'error') {
    return { children: [] as ChildEntry[], status: 'error' as const, error: identityError, sync: children.sync, refetch }
  }
  if (identityStatus !== 'loading' && childrenIds.length === 0) {
    return { children: [] as ChildEntry[], status: 'empty' as const, error: null, sync: children.sync, refetch }
  }

  return {
    children: children.data ?? [],
    status: identityStatus === 'loading' ? ('loading' as const) : children.status,
    error: children.error,
    sync: children.sync,
    refetch,
  }
}

/** Display label for a child, never inventing a name the server did not give. */
export function childLabel(entry: ChildEntry): string {
  return entry.context?.name?.trim() || `Student #${entry.studentId}`
}
