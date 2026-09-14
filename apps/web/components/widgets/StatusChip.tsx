'use client'

import * as React from 'react'
import { AlertCircle, CheckCircle2, Circle, Clock, XCircle, type LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'

/**
 * DESIGN-SYSTEM.md §1.1: "Never encode meaning in colour alone... every
 * status pairs a colour with an icon and a text label." Used across
 * attendance/fees/library/HR statuses so every module renders status the
 * same way instead of ad hoc colored `<span>`s.
 */

export type StatusTone = 'positive' | 'caution' | 'critical' | 'info' | 'neutral'

export interface StatusChipProps {
  label: string
  tone?: StatusTone
  icon?: LucideIcon
  className?: string
}

// Flat light-ground fills, no border -- Learnhouse's dash surface is light
// only, and its own chips/badges sit borderless on white cards.
const TONE_CLASSES: Record<StatusTone, string> = {
  positive: 'bg-emerald-50 text-emerald-700',
  caution: 'bg-amber-50 text-amber-700',
  critical: 'bg-rose-50 text-rose-700',
  info: 'bg-blue-50 text-blue-700',
  neutral: 'bg-gray-100 text-gray-600',
}

const DEFAULT_ICON: Record<StatusTone, LucideIcon> = {
  positive: CheckCircle2,
  caution: Clock,
  critical: XCircle,
  info: AlertCircle,
  neutral: Circle,
}

export function StatusChip({ label, tone = 'neutral', icon, className }: StatusChipProps) {
  const Icon = icon ?? DEFAULT_ICON[tone]
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium',
        TONE_CLASSES[tone],
        className
      )}
    >
      <Icon className="size-3" aria-hidden="true" />
      {label}
    </span>
  )
}
