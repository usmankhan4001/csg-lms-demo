'use client'

import * as React from 'react'
import { TrendingDown, TrendingUp, type LucideIcon } from 'lucide-react'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'

export type KpiTone = 'neutral' | 'positive' | 'caution' | 'critical'

export interface KpiCardProps {
  label: string
  value: React.ReactNode
  icon?: LucideIcon
  hint?: string
  trend?: { value: string; direction: 'up' | 'down' | 'flat' }
  tone?: KpiTone
  loading?: boolean
  className?: string
}

const TONE_ICON_CLASSES: Record<KpiTone, string> = {
  neutral: 'bg-muted text-muted-foreground',
  positive: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400',
  caution: 'bg-amber-500/10 text-amber-600 dark:text-amber-400',
  critical: 'bg-rose-500/10 text-rose-600 dark:text-rose-400',
}

const TREND_CLASSES: Record<'up' | 'down' | 'flat', string> = {
  up: 'text-emerald-600 dark:text-emerald-400',
  down: 'text-rose-600 dark:text-rose-400',
  flat: 'text-muted-foreground',
}

/** A single KPI stat tile. Composes into `StatGrid`. */
export function KpiCard({ label, value, icon: Icon, hint, trend, tone = 'neutral', loading, className }: KpiCardProps) {
  if (loading) {
    return (
      <div className={cn('space-y-3 rounded-xl border border-border bg-card p-4', className)} aria-busy="true">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-7 w-16" />
        <Skeleton className="h-3 w-20" />
      </div>
    )
  }

  return (
    <div className={cn('flex flex-col gap-2 rounded-xl border border-border bg-card p-4', className)}>
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-medium text-muted-foreground">{label}</span>
        {Icon && (
          <div className={cn('flex size-8 shrink-0 items-center justify-center rounded-lg', TONE_ICON_CLASSES[tone])}>
            <Icon className="size-4" />
          </div>
        )}
      </div>
      <div className="text-2xl font-bold tabular-nums text-foreground">{value}</div>
      {(hint || trend) && (
        <div className="flex items-center gap-1.5 text-xs">
          {trend && (
            <span className={cn('inline-flex items-center gap-0.5 font-medium', TREND_CLASSES[trend.direction])}>
              {trend.direction === 'up' && <TrendingUp className="size-3" />}
              {trend.direction === 'down' && <TrendingDown className="size-3" />}
              {trend.value}
            </span>
          )}
          {hint && <span className="truncate text-muted-foreground">{hint}</span>}
        </div>
      )}
    </div>
  )
}
