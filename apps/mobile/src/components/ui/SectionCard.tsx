import React from 'react';
import { Text, View } from 'react-native';
import { ShieldAlert, TriangleAlert, WifiOff, type LucideIcon } from 'lucide-react-native';
import { Card } from './Card';
import { EmptyState, type EmptyStateAction, type EmptyStateTone } from './EmptyState';
import { SkeletonRows } from './Skeleton';
import { SyncBadge } from './SyncBadge';
import type { ApiError } from '@/api/client';
import type { SyncInfo } from '@/api/useApiResource';

/**
 * RN port of `apps/web/components/widgets/SectionCard.tsx` — implements the
 * DESIGN-SYSTEM.md §4 state model generically (Default/Success, Loading,
 * Empty, Error, and — via `sync` — Offline) so screens compose this instead
 * of hand-rolling loading/empty/error markup per section. Permission-denied
 * is handled here too, keyed off `error.kind` exactly like the web version.
 */

export type SectionCardState = 'loading' | 'empty' | 'error' | 'success';

export interface SectionCardProps {
  title: string;
  description?: string;
  icon?: React.ReactNode;
  /** Header-right slot, e.g. a "View all" link. Hidden outside the success state. */
  action?: React.ReactNode;
  state: SectionCardState;
  error?: ApiError | null;
  /** When provided and offline/stale, renders a SyncBadge in the header even on Success (cached data being shown). */
  sync?: SyncInfo;
  onRetry?: () => void;
  emptyTitle?: string;
  emptyDescription?: string;
  emptyAction?: EmptyStateAction;
  emptyIcon?: LucideIcon;
  loadingRows?: number;
  /** Shown under the title on a Permission-denied error — e.g. "TEACHER". */
  requiredRoleLabel?: string;
  children?: React.ReactNode;
}

function errorPresentation(error: ApiError | null | undefined, requiredRoleLabel?: string) {
  if (error?.kind === 'permission_denied') {
    return {
      icon: ShieldAlert,
      tone: 'caution' as EmptyStateTone,
      title: 'Restricted',
      description: requiredRoleLabel
        ? `You need the ${requiredRoleLabel} role to view this.`
        : error.message || "You don't have the role required to view this.",
    };
  }
  if (error?.kind === 'network') {
    return {
      icon: WifiOff,
      tone: 'caution' as EmptyStateTone,
      title: "You're offline",
      description: error.message || 'Reconnect to load the latest data.',
    };
  }
  return {
    icon: TriangleAlert,
    tone: 'critical' as EmptyStateTone,
    title: "Couldn't load this",
    description: error?.message || 'The server did not respond in time.',
  };
}

export function SectionCard({
  title,
  description,
  icon,
  action,
  state,
  error,
  sync,
  onRetry,
  emptyTitle = 'Nothing here yet',
  emptyDescription,
  emptyAction,
  emptyIcon,
  loadingRows = 3,
  requiredRoleLabel,
  children,
}: SectionCardProps) {
  const errorInfo = errorPresentation(error, requiredRoleLabel);
  const showStaleBanner = state === 'success' && sync?.status === 'offline';

  return (
    <Card>
      <View className="flex-row items-start justify-between gap-3 border-b border-line px-4 py-3.5 dark:border-line-dark">
        <View className="min-w-0 flex-1 flex-row items-center gap-2.5">
          {icon}
          <View className="min-w-0 flex-1">
            <Text className="text-sm font-semibold text-ink dark:text-ink-dark">{title}</Text>
            {description ? <Text className="text-xs text-ink-muted dark:text-ink-muted-dark">{description}</Text> : null}
          </View>
        </View>
        {state === 'success' ? action : null}
      </View>

      <View className="p-4">
        {showStaleBanner ? (
          <View className="mb-3">
            <SyncBadge status="offline" lastUpdatedAt={sync?.lastUpdatedAt} />
          </View>
        ) : null}

        {state === 'loading' && <SkeletonRows rows={loadingRows} />}

        {state === 'error' && (
          <EmptyState
            icon={errorInfo.icon}
            tone={errorInfo.tone}
            title={errorInfo.title}
            description={errorInfo.description}
            code={error?.code}
            action={onRetry ? { label: 'Retry', onPress: onRetry } : undefined}
          />
        )}

        {state === 'empty' && (
          <EmptyState title={emptyTitle} description={emptyDescription} action={emptyAction} icon={emptyIcon} />
        )}

        {state === 'success' && children}
      </View>
    </Card>
  );
}
