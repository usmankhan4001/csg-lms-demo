'use client'

import * as React from 'react'
import { Inbox, type LucideIcon } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

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

const TONE_CLASSES: Record<EmptyStateTone, string> = {
  neutral: 'bg-muted text-muted-foreground',
  critical: 'bg-destructive/10 text-destructive',
  caution: 'bg-amber-500/10 text-amber-600 dark:text-amber-400',
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
      <div className={cn('flex size-12 items-center justify-center rounded-full', TONE_CLASSES[tone])}>
        <Icon className="size-6" aria-hidden="true" />
      </div>
      <div className="max-w-sm space-y-1">
        <p className="text-sm font-semibold text-foreground">{title}</p>
        {description && <p className="text-sm text-muted-foreground">{description}</p>}
      </div>
      {(action || secondaryAction) && (
        <div className="flex items-center gap-2">
          {action &&
            (action.href ? (
              <Button asChild size="sm" variant={tone === 'critical' ? 'default' : 'outline'}>
                <a href={action.href}>{action.label}</a>
              </Button>
            ) : (
              <Button size="sm" variant={tone === 'critical' ? 'default' : 'outline'} onClick={action.onClick}>
                {action.label}
              </Button>
            ))}
          {secondaryAction && (
            <Button size="sm" variant="ghost" onClick={secondaryAction.onClick}>
              {secondaryAction.label}
            </Button>
          )}
        </div>
      )}
      {code && <p className="mt-1 font-mono text-[11px] text-muted-foreground/70">Code: {code}</p>}
    </div>
  )
}
