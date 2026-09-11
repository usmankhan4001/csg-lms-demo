/**
 * The mobile counterpart of `apps/web/lib/api/useApiResource.ts`, extended
 * with the offline-cache behaviour described in `./cache.ts`'s doc comment
 * (read that file first — it documents what is and is NOT implemented here
 * relative to DESIGN-SYSTEM.md §8's full WatermelonDB sync spec).
 *
 * Maps onto the DESIGN-SYSTEM.md §4 state model:
 *   'loading' -> Loading skeleton
 *   'error'   -> Error state (no cached data available to fall back to)
 *   'empty'   -> Empty state (loaded successfully, zero rows)
 *   'success' -> Default/Success rendering (live data OR a served-from-cache
 *                copy while offline — check `sync.status` to tell which)
 *
 * Deliberately NOT 'permission-denied' here, same reasoning as the web
 * version: callers branch on `error.kind === 'permission_denied'` themselves
 * (see `src/components/ui/SectionState.tsx`), since that state needs
 * different copy/icon than a generic error, not a different hook state.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError } from './client';
import { readCache, writeCache } from './cache';

export type ResourceStatus = 'loading' | 'error' | 'empty' | 'success';
export type SyncStatus = 'synced' | 'pending' | 'offline' | 'conflict';

export interface SyncInfo {
  status: SyncStatus;
  /** epoch ms of the data currently being shown, if any. */
  lastUpdatedAt: number | null;
}

export interface UseApiResourceResult<T> {
  status: ResourceStatus;
  data: T | null;
  error: ApiError | null;
  sync: SyncInfo;
  /** Re-runs the fetcher, e.g. from a Retry button or pull-to-refresh. */
  refetch: () => void;
}

export interface UseApiResourceOptions<T> {
  /** Determines whether successfully-loaded data counts as "empty" (default: array with length 0). */
  isEmpty?: (data: T) => boolean;
  /** Skip fetching entirely (e.g. while a required id isn't known yet). */
  skip?: boolean;
  /**
   * AsyncStorage cache key for this resource. When set, a successful fetch
   * is cached, and a network failure falls back to serving that cache (with
   * `sync.status === 'offline'`) instead of an Error state. Omit for
   * resources where a stale cache would be actively misleading (e.g.
   * anything involving a live "can I still submit this" check).
   */
  cacheKey?: string;
}

function defaultIsEmpty(data: unknown): boolean {
  if (Array.isArray(data)) return data.length === 0;
  if (data && typeof data === 'object') return Object.keys(data as object).length === 0;
  return data === null || data === undefined;
}

export function useApiResource<T>(
  fetcher: () => Promise<T>,
  deps: React.DependencyList,
  options: UseApiResourceOptions<T> = {}
): UseApiResourceResult<T> {
  const { isEmpty = defaultIsEmpty, skip = false, cacheKey } = options;
  const [status, setStatus] = useState<ResourceStatus>('loading');
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [sync, setSync] = useState<SyncInfo>({ status: 'synced', lastUpdatedAt: null });
  const [reloadCounter, setReloadCounter] = useState(0);
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const refetch = useCallback(() => setReloadCounter((n) => n + 1), []);

  useEffect(() => {
    if (skip) {
      setStatus('loading');
      return;
    }

    let cancelled = false;
    setStatus('loading');
    setError(null);

    (async () => {
      try {
        const result = await fetcherRef.current();
        if (cancelled) return;
        const now = Date.now();
        setData(result);
        setStatus(isEmpty(result) ? 'empty' : 'success');
        setSync({ status: 'synced', lastUpdatedAt: now });
        if (cacheKey) void writeCache(cacheKey, result);
      } catch (err) {
        if (cancelled) return;
        const apiError = err instanceof ApiError ? err : new ApiError(0, err instanceof Error ? err.message : 'Unknown error', 'unknown');

        if (apiError.kind === 'network' && cacheKey) {
          const cached = await readCache<T>(cacheKey);
          if (cancelled) return;
          if (cached) {
            setData(cached.data);
            setStatus(isEmpty(cached.data) ? 'empty' : 'success');
            setSync({ status: 'offline', lastUpdatedAt: cached.cachedAt });
            return;
          }
        }

        setError(apiError);
        setStatus('error');
        setSync((prev) => (apiError.kind === 'network' ? { status: 'offline', lastUpdatedAt: prev.lastUpdatedAt } : prev));
      }
    })();

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [skip, reloadCounter, cacheKey, ...deps]);

  return { status, data, error, sync, refetch };
}
