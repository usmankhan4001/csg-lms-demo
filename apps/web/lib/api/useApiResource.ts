'use client'

/**
 * One small shared data-fetching hook, reused by every SMS module instead of
 * pulling in SWR/React Query. Wraps `fetch` (via each module's `api.ts`,
 * which itself goes through `./api-client`) with loading/error/data state
 * that maps directly onto the DESIGN-SYSTEM.md §4 state model:
 *
 *   'loading' -> Loading skeleton
 *   'error'   -> Error (network/server) or Offline, distinguished via error.kind
 *   'empty'   -> Empty state (no rows) -- only reachable once data has loaded
 *   'success' -> Default/Success rendering
 *
 * Deliberately NOT permission-denied here: that state is entered explicitly
 * by callers that already know the required role client-side (nav is built
 * from resolved features/roles), or by checking `error.kind === 'permission_denied'`.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError } from './api-client'

export type ResourceStatus = 'loading' | 'error' | 'empty' | 'success'

export interface UseApiResourceResult<T> {
  status: ResourceStatus
  data: T | null
  error: ApiError | null
  /** Re-runs the fetcher, e.g. from a Retry button. */
  refetch: () => void
}

export interface UseApiResourceOptions<T> {
  /** Determines whether successfully-loaded data counts as "empty" (default: array with length 0). */
  isEmpty?: (data: T) => boolean
  /** Skip fetching entirely (e.g. while a required id isn't known yet). Renders as 'loading' while skipped is true and no data has ever loaded. */
  skip?: boolean
}

function defaultIsEmpty(data: unknown): boolean {
  if (Array.isArray(data)) return data.length === 0
  if (data && typeof data === 'object') return Object.keys(data as object).length === 0
  return data === null || data === undefined
}

export function useApiResource<T>(
  fetcher: () => Promise<T>,
  deps: React.DependencyList,
  options: UseApiResourceOptions<T> = {}
): UseApiResourceResult<T> {
  const { isEmpty = defaultIsEmpty, skip = false } = options
  const [status, setStatus] = useState<ResourceStatus>('loading')
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<ApiError | null>(null)
  const [reloadCounter, setReloadCounter] = useState(0)
  const fetcherRef = useRef(fetcher)
  fetcherRef.current = fetcher

  const refetch = useCallback(() => setReloadCounter((n) => n + 1), [])

  useEffect(() => {
    if (skip) {
      setStatus('loading')
      return
    }

    let cancelled = false
    setStatus('loading')
    setError(null)

    fetcherRef
      .current()
      .then((result) => {
        if (cancelled) return
        setData(result)
        setStatus(isEmpty(result) ? 'empty' : 'success')
      })
      .catch((err: unknown) => {
        if (cancelled) return
        const apiError = err instanceof ApiError ? err : new ApiError(0, err instanceof Error ? err.message : 'Unknown error', 'unknown')
        setError(apiError)
        setStatus('error')
      })

    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [skip, reloadCounter, ...deps])

  return { status, data, error, refetch }
}
