'use client'

import * as React from 'react'
import { AlertTriangle, ShieldAlert, WifiOff, type LucideIcon } from 'lucide-react'
import { Skeleton } from '@/components/ui/skeleton'
import { EmptyState, type EmptyStateAction } from './EmptyState'
import { ApiError } from '@/lib/api/api-client'
import { cn } from '@/lib/utils'

/**
 * Generic card shell for a dashboard panel that implements the
 * DESIGN-SYSTEM.md §4 state model generically, so pages compose it instead
 * of hand-rolling loading/empty/error markup per section.
 */

export type SectionCardState = 'loading' | 'empty' | 'error' | 'success'

export interface SectionCardProps {
  /** DOM id, e.g. for sidebar anchor links like `/student#timetable`. */
  id?: string
  title: string
  description?: string
  icon?: React.ReactNode
  /** Header-right slot, e.g. a "View all" link or filter control. Hidden while loading. */
  action?: React.ReactNode
  state?: SectionCardState
  error?: ApiError | null
  onRetry?: () => void
  emptyTitle?: string
  emptyDescription?: string
  emptyAction?: EmptyStateAction
  emptyIcon?: LucideIcon
  loadingRows?: number
  className?: string
  bodyClassName?: string
  children?: React.ReactNode
}

function errorPresentation(error?: ApiError | null) {
  if (error?.kind === 'permission_denied') {
    return {
      icon: ShieldAlert,
      tone: 'caution' as const,
      title: 'Restricted',
      description: error.message || "You don't have the role required to view this.",
    }
  }
  if (error?.kind === 'network') {
    return {
      icon: WifiOff,
      tone: 'caution' as const,
      title: "You're offline",
      description: error.message || 'Reconnect to load the latest data.',
    }
  }
  return {
    icon: AlertTriangle,
    tone: 'critical' as const,
    title: "Couldn't load this",
    description: error?.message || 'The server did not respond in time.',
  }
}

export function SectionCard({
  id,
  title,
  description,
  icon,
  action,
  state = 'success',
  error,
  onRetry,
  emptyTitle = 'Nothing here yet',
  emptyDescription,
  emptyAction,
  emptyIcon,
  loadingRows = 3,
  className,
  bodyClassName,
  children,
}: SectionCardProps) {
  const errorInfo = errorPresentation(error)

  return (
    <section id={id} className={cn('scroll-mt-20 rounded-xl bg-white nice-shadow', className)}>
      <header className="flex items-start justify-between gap-3 border-b border-gray-100 px-5 py-4">
        <div className="flex min-w-0 items-center gap-2.5">
          {icon}
          <div className="min-w-0">
            <h3 className="truncate text-sm font-semibold text-gray-700">{title}</h3>
            {description && <p className="truncate text-xs text-gray-400">{description}</p>}
          </div>
        </div>
        {state === 'success' && action}
      </header>
      <div className={cn('p-5', bodyClassName)} aria-busy={state === 'loading'}>
        {state === 'loading' && (
          <div className="space-y-2.5">
            {Array.from({ length: loadingRows }).map((_, i) => (
              <Skeleton key={i} className="h-5 w-full" style={{ width: `${100 - i * 8}%` }} />
            ))}
          </div>
        )}
        {state === 'error' && (
          <EmptyState
            icon={errorInfo.icon}
            tone={errorInfo.tone}
            title={errorInfo.title}
            description={errorInfo.description}
            code={error?.code}
            action={onRetry ? { label: 'Retry', onClick: onRetry } : undefined}
          />
        )}
        {state === 'empty' && (
          <EmptyState title={emptyTitle} description={emptyDescription} action={emptyAction} icon={emptyIcon} />
        )}
        {state === 'success' && children}
      </div>
    </section>
  )
}
