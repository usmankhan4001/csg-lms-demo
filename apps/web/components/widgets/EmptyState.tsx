'use client'

import * as React from 'react'
import { Inbox, type LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'
import { LH_GHOST_BUTTON, LH_PRIMARY_BUTTON } from './lh-styles'

/**
 * The shared placeholder used for the Empty, Error, Offline and
 * Permission-denied states (DESIGN-SYSTEM.md §4) so every module renders
 * them consistently: icon + one-line explanation + primary action, never a
 * blank panel or a raw status code.
 */

export interface EmptyStateAction {
  label: string
  onClick?: () => void
  href?: string
}

export type EmptyStateTone = 'neutral' | 'critical' | 'caution'

export interface EmptyStateProps {
  icon?: LucideIcon
  title: string
  description?: string
  action?: EmptyStateAction
  secondaryAction?: EmptyStateAction
  tone?: EmptyStateTone
  /** Small-print RFC 7807-style code for support, shown under the description on Error states. */
  code?: string
  className?: string
}

// Mirrors Learnhouse's own empty state (dash/podcasts/client.tsx): a large
// muted circle holding a faint icon, on the light dash ground.
const TONE_CLASSES: Record<EmptyStateTone, string> = {
  neutral: 'bg-gray-100 text-gray-300',
  critical: 'bg-rose-50 text-rose-400',
  caution: 'bg-amber-50 text-amber-400',
}

export function EmptyState({
  icon: Icon = Inbox,
  title,
  description,
  action,
  secondaryAction,
  tone = 'neutral',
  code,
  className,
}: EmptyStateProps) {
  return (
    <div className={cn('flex flex-col items-center justify-center gap-3 px-6 py-12 text-center', className)}>
      <div className={cn('flex size-16 items-center justify-center rounded-full', TONE_CLASSES[tone])}>
        <Icon className="size-8" aria-hidden="true" />
      </div>
      <div className="max-w-md space-y-1">
        <p className="text-lg font-bold text-gray-600">{title}</p>
        {description && <p className="text-sm text-gray-400">{description}</p>}
      </div>
      {(action || secondaryAction) && (
        <div className="mt-2 flex items-center gap-2">
          {action &&
            (action.href ? (
              <a href={action.href} className={LH_PRIMARY_BUTTON}>
                {action.label}
              </a>
            ) : (
              <button type="button" onClick={action.onClick} className={LH_PRIMARY_BUTTON}>
                {action.label}
              </button>
            ))}
          {secondaryAction && (
            <button type="button" onClick={secondaryAction.onClick} className={LH_GHOST_BUTTON}>
              {secondaryAction.label}
            </button>
          )}
        </div>
      )}
      {code && <p className="mt-1 font-mono text-[11px] text-gray-400">Code: {code}</p>}
    </div>
  )
}
