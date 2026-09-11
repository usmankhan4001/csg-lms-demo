'use client'

import * as React from 'react'
import { KpiCard, type KpiCardProps } from './KpiCard'
import { EmptyState } from './EmptyState'
import { ApiError } from '@/lib/api/api-client'
import { cn } from '@/lib/utils'

export type StatGridState = 'loading' | 'error' | 'empty' | 'success'

export interface StatGridProps {
  items: KpiCardProps[]
  state?: StatGridState
  error?: ApiError | null
  onRetry?: () => void
  columns?: 2 | 3 | 4 | 5
  skeletonCount?: number
  className?: string
}

const GRID_COLS: Record<2 | 3 | 4 | 5, string> = {
  2: 'sm:grid-cols-2',
  3: 'sm:grid-cols-2 lg:grid-cols-3',
  4: 'sm:grid-cols-2 lg:grid-cols-4',
  5: 'sm:grid-cols-2 lg:grid-cols-5',
}

/** Responsive row of `KpiCard`s with a shared loading/error/empty treatment. */
export function StatGrid({ items, state = 'success', error, onRetry, columns = 4, skeletonCount = 4, className }: StatGridProps) {
  if (state === 'error') {
    return (
      <div className={cn('rounded-xl border border-border bg-card', className)}>
        <EmptyState
          tone="critical"
          title="Couldn't load these metrics"
          description={error?.message || 'The server did not respond in time.'}
          code={error?.code}
          action={onRetry ? { label: 'Retry', onClick: onRetry } : undefined}
        />
      </div>
    )
  }

  if (state === 'loading') {
    return (
      <div className={cn('grid grid-cols-1 gap-3', GRID_COLS[columns], className)}>
        {Array.from({ length: skeletonCount }).map((_, i) => (
          <KpiCard key={i} label="" value="" loading />
        ))}
      </div>
    )
  }

  if (state === 'empty' || items.length === 0) {
    return (
      <div className={cn('rounded-xl border border-border bg-card', className)}>
        <EmptyState title="No metrics yet" description="Data will appear here once activity is recorded." />
      </div>
    )
  }

  return (
    <div className={cn('grid grid-cols-1 gap-3', GRID_COLS[columns], className)}>
      {items.map((item, i) => (
        <KpiCard key={i} {...item} />
      ))}
    </div>
  )
}
