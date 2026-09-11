import React from 'react';
import { Text, View } from 'react-native';
import { CircleCheck, CloudOff, RefreshCw, TriangleAlert } from 'lucide-react-native';
import type { SyncStatus } from '@/api/useApiResource';

/**
 * DESIGN-SYSTEM.md §8 offline/sync indicator. Renders all four documented
 * states, but see `src/api/cache.ts`'s doc comment for what this scaffold
 * actually drives: only `synced` and `offline` are ever set by real data
 * flow (`useApiResource`). `pending` and `conflict` render correctly here
 * and are ready for a future write-queue/sync-engine to trigger — this pass
 * does not fabricate data to exercise them.
 */

export interface SyncBadgeProps {
  status: SyncStatus;
  /** For `pending`: number of queued local changes. Ignored otherwise. */
  pendingCount?: number;
  /** epoch ms — rendered as "Updated Xm ago" / "Showing data from Xm ago". */
  lastUpdatedAt?: number | null;
}

function relativeTime(ms: number | null | undefined): string | null {
  if (!ms) return null;
  const deltaSeconds = Math.max(0, Math.round((Date.now() - ms) / 1000));
  if (deltaSeconds < 30) return 'just now';
  if (deltaSeconds < 60) return `${deltaSeconds}s ago`;
  const minutes = Math.round(deltaSeconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

export function SyncBadge({ status, pendingCount, lastUpdatedAt }: SyncBadgeProps) {
  const rel = relativeTime(lastUpdatedAt);

  if (status === 'synced') {
    return (
      <View className="flex-row items-center gap-1.5 self-start rounded-full bg-positive/10 px-2.5 py-1">
        <CircleCheck size={12} color="hsl(142, 76%, 36%)" />
        <Text className="text-[11px] font-medium text-positive dark:text-positive-dark">
          {rel ? `Updated ${rel}` : 'Synced'}
        </Text>
      </View>
    );
  }

  if (status === 'pending') {
    return (
      <View className="flex-row items-center gap-1.5 self-start rounded-full bg-caution/10 px-2.5 py-1">
        <RefreshCw size={12} color="hsl(38, 92%, 50%)" />
        <Text className="text-[11px] font-medium text-caution dark:text-caution-dark">
          {pendingCount ? `${pendingCount} change${pendingCount === 1 ? '' : 's'} waiting to sync` : 'Sync pending'}
        </Text>
      </View>
    );
  }

  if (status === 'conflict') {
    return (
      <View className="flex-row items-center gap-1.5 self-start rounded-full bg-critical/10 px-2.5 py-1">
        <TriangleAlert size={12} color="hsl(346, 84%, 61%)" />
        <Text className="text-[11px] font-medium text-critical dark:text-critical-dark">Sync conflict</Text>
      </View>
    );
  }

  // offline
  return (
    <View className="flex-row items-center gap-1.5 self-start rounded-full bg-caution/10 px-2.5 py-1">
      <CloudOff size={12} color="hsl(38, 92%, 50%)" />
      <Text className="text-[11px] font-medium text-caution dark:text-caution-dark">
        {rel ? `You're offline — showing data from ${rel}` : "You're offline"}
      </Text>
    </View>
  );
}
