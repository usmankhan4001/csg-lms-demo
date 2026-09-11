/**
 * Last-successful-response cache, backed by AsyncStorage.
 * ===========================================================
 *
 * SCOPE LIMITATION (read this before extending): this is deliberately NOT an
 * offline write-queue or a sync engine. DESIGN-SYSTEM.md §8 describes a full
 * WatermelonDB delta-sync setup (`GET /v1/core/sync/delta`) with Last-Write-Wins
 * conflict resolution (ADR-025) for field-persona modules (attendance,
 * gradebook). That endpoint does not exist on the backend yet (confirmed:
 * no `/v1/core/sync/delta` route in `apps/api/src/router.py`), and building a
 * real embedded-database sync engine is a separate, much larger effort than
 * this scaffold.
 *
 * What this DOES provide, matching the task's explicitly reduced scope:
 *   - Cache the last successful GET response for a given key.
 *   - On a network failure, serve that cached copy with a "last updated"
 *     timestamp so read-only surfaces stay usable offline (§4 state 5).
 *   - No write queueing: an attendance/grade submission made while offline
 *     fails immediately with a clear Offline error (see useApiResource.ts /
 *     the Check-in screen) rather than silently "queuing" and risking data
 *     loss the UI never told the user about.
 *   - `SyncBadge` (src/components/ui/SyncBadge.tsx) renders all four states
 *     from DESIGN-SYSTEM.md §8 (Synced/Pending/Offline/Conflict) as a UI
 *     component, but only Synced/Offline are ever actually driven by real
 *     data flow here — Pending/Conflict are wired up for a future sync
 *     engine to use, not fabricated in this pass.
 */

import AsyncStorage from '@react-native-async-storage/async-storage';

const CACHE_PREFIX = 'csg_lms_cache:';

export interface CacheEntry<T> {
  data: T;
  cachedAt: number;
}

export async function readCache<T>(key: string): Promise<CacheEntry<T> | null> {
  try {
    const raw = await AsyncStorage.getItem(CACHE_PREFIX + key);
    if (!raw) return null;
    return JSON.parse(raw) as CacheEntry<T>;
  } catch {
    return null;
  }
}

export async function writeCache<T>(key: string, data: T): Promise<void> {
  try {
    const entry: CacheEntry<T> = { data, cachedAt: Date.now() };
    await AsyncStorage.setItem(CACHE_PREFIX + key, JSON.stringify(entry));
  } catch {
    // Best-effort only — a cache write failure (e.g. storage full) must never
    // break the live request that just succeeded.
  }
}
