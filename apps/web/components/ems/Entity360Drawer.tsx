'use client'

import React, { useEffect, useCallback } from 'react'
import { X, Sparkles } from 'lucide-react'
import { cn } from '@/lib/utils'

export interface Entity360Badge {
  label: string
  variant?: 'default' | 'success' | 'warning' | 'destructive' | 'outline' | 'purple' | 'amber' | 'cyan' | 'blue'
  icon?: React.ReactNode
}

export interface Entity360QuickAction {
  label: string
  icon?: React.ReactNode
  onClick: () => void
  variant?: 'default' | 'primary' | 'outline' | 'destructive' | 'secondary'
  disabled?: boolean
  tooltip?: string
}

export interface Entity360Tab {
  id: string
  label: string
  icon?: React.ReactNode
  count?: number | string
  badgeVariant?: string
}

export interface Entity360Avatar {
  src?: string
  initials?: string
  icon?: React.ReactNode
  bgClass?: string
  statusDot?: 'online' | 'offline' | 'busy' | 'away' | 'verified'
}

export interface Entity360DrawerProps {
  isOpen: boolean
  onClose: () => void
  title: string
  subtitle?: string
  entityTypeBadge?: string
  avatar?: Entity360Avatar
  badges?: Entity360Badge[]
  quickActions?: Entity360QuickAction[]
  tabs: Entity360Tab[]
  activeTab: string
  onTabChange: (tabId: string) => void
  children: React.ReactNode
  widthClass?: string // default max-w-4xl w-full
  metaBar?: React.ReactNode
  footer?: React.ReactNode
  className?: string
}

const BADGE_VARIANT_MAP: Record<string, string> = {
  default: 'bg-zinc-100 text-zinc-800 dark:bg-zinc-800 dark:text-zinc-200 border-zinc-200 dark:border-zinc-700',
  success: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800',
  warning: 'bg-amber-50 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300 border-amber-200 dark:border-amber-800',
  destructive: 'bg-rose-50 text-rose-700 dark:bg-rose-950/60 dark:text-rose-300 border-rose-200 dark:border-rose-800',
  outline: 'bg-transparent text-zinc-600 dark:text-zinc-400 border-zinc-300 dark:border-zinc-700',
  purple: 'bg-purple-50 text-purple-700 dark:bg-purple-950/60 dark:text-purple-300 border-purple-200 dark:border-purple-800',
  amber: 'bg-amber-50 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300 border-amber-200 dark:border-amber-800',
  cyan: 'bg-cyan-50 text-cyan-700 dark:bg-cyan-950/60 dark:text-cyan-300 border-cyan-200 dark:border-cyan-800',
  blue: 'bg-blue-50 text-blue-700 dark:bg-blue-950/60 dark:text-blue-300 border-blue-200 dark:border-blue-800',
}

const ACTION_VARIANT_MAP: Record<string, string> = {
  default: 'bg-zinc-100 hover:bg-zinc-200 text-zinc-700 dark:bg-zinc-800 dark:hover:bg-zinc-700 dark:text-zinc-200 border border-zinc-200/80 dark:border-zinc-700',
  primary: 'bg-indigo-600 hover:bg-indigo-700 text-white shadow-sm hover:shadow dark:bg-indigo-600 dark:hover:bg-indigo-500',
  outline: 'bg-white hover:bg-zinc-50 text-zinc-700 dark:bg-zinc-900 dark:hover:bg-zinc-800 dark:text-zinc-200 border border-zinc-300 dark:border-zinc-700',
  destructive: 'bg-rose-50 hover:bg-rose-100 text-rose-700 dark:bg-rose-950/50 dark:hover:bg-rose-900/60 dark:text-rose-300 border border-rose-200 dark:border-rose-800',
  secondary: 'bg-zinc-900 hover:bg-zinc-800 text-white dark:bg-white dark:hover:bg-zinc-100 dark:text-zinc-900',
}

export const Entity360Drawer: React.FC<Entity360DrawerProps> = ({
  isOpen,
  onClose,
  title,
  subtitle,
  entityTypeBadge,
  avatar,
  badges = [],
  quickActions = [],
  tabs,
  activeTab,
  onTabChange,
  children,
  widthClass = 'max-w-4xl w-full',
  metaBar,
  footer,
  className,
}) => {
  // ESC key handler
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose()
      }
    },
    [onClose]
  )

  useEffect(() => {
    if (isOpen) {
      document.addEventListener('keydown', handleKeyDown)
      document.body.style.overflow = 'hidden'
    } else {
      document.removeEventListener('keydown', handleKeyDown)
      document.body.style.overflow = ''
    }
    return () => {
      document.removeEventListener('keydown', handleKeyDown)
      document.body.style.overflow = ''
    }
  }, [isOpen, handleKeyDown])

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex justify-end overflow-hidden">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/60 backdrop-blur-xs transition-opacity duration-300 animate-in fade-in"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Slide-over Drawer Panel */}
      <div
        className={cn(
          'relative z-50 flex h-full flex-col bg-white dark:bg-zinc-950 shadow-2xl border-l border-zinc-200 dark:border-zinc-800 transition-all duration-300 ease-out animate-in slide-in-from-right sm:duration-400',
          widthClass,
          className
        )}
        role="dialog"
        aria-modal="true"
        aria-labelledby="entity-360-title"
      >
        {/* Top Header Section */}
        <div className="border-b border-zinc-200 bg-zinc-50/90 dark:border-zinc-800 dark:bg-zinc-900/90 backdrop-blur-md px-6 pt-5 pb-0 shrink-0">
          <div className="flex items-start justify-between gap-4 pb-4">
            {/* Left: Avatar & Title & Badges */}
            <div className="flex items-start gap-3.5 min-w-0 flex-1">
              {avatar && (
                <div className="relative shrink-0 mt-0.5">
                  <div
                    className={cn(
                      'h-12 w-12 rounded-xl flex items-center justify-center font-bold text-base shadow-xs overflow-hidden border border-zinc-200 dark:border-zinc-700',
                      avatar.bgClass || 'bg-gradient-to-br from-indigo-500 to-purple-600 text-white'
                    )}
                  >
                    {avatar.src ? (
                      <img src={avatar.src} alt={title} className="h-full w-full object-cover" />
                    ) : avatar.icon ? (
                      avatar.icon
                    ) : (
                      avatar.initials || title.slice(0, 2).toUpperCase()
                    )}
                  </div>
                  {avatar.statusDot && (
                    <span
                      className={cn(
                        'absolute -bottom-1 -right-1 h-3.5 w-3.5 rounded-full ring-2 ring-white dark:ring-zinc-900',
                        avatar.statusDot === 'online' && 'bg-emerald-500',
                        avatar.statusDot === 'busy' && 'bg-rose-500',
                        avatar.statusDot === 'away' && 'bg-amber-500',
                        avatar.statusDot === 'verified' && 'bg-blue-500',
                        avatar.statusDot === 'offline' && 'bg-zinc-400'
                      )}
                    />
                  )}
                </div>
              )}

              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 flex-wrap mb-1">
                  {entityTypeBadge && (
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold uppercase tracking-wider bg-indigo-100 text-indigo-800 dark:bg-indigo-950/80 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800">
                      {entityTypeBadge}
                    </span>
                  )}
                  <h2
                    id="entity-360-title"
                    className="text-lg font-bold text-zinc-900 dark:text-zinc-100 tracking-tight truncate max-w-md"
                  >
                    {title}
                  </h2>
                  {badges.map((b, idx) => (
                    <span
                      key={idx}
                      className={cn(
                        'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium border',
                        BADGE_VARIANT_MAP[b.variant || 'default']
                      )}
                    >
                      {b.icon}
                      {b.label}
                    </span>
                  ))}
                </div>

                {subtitle && (
                  <p className="text-xs text-zinc-500 dark:text-zinc-400 flex items-center gap-1.5 truncate">
                    {subtitle}
                  </p>
                )}
              </div>
            </div>

            {/* Right: Quick Action Buttons & Close */}
            <div className="flex items-center gap-2 shrink-0">
              <div className="hidden sm:flex items-center gap-1.5">
                {quickActions.map((action, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={action.onClick}
                    disabled={action.disabled}
                    title={action.tooltip || action.label}
                    className={cn(
                      'inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg transition-all focus:outline-hidden focus:ring-2 focus:ring-indigo-500/20 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer',
                      ACTION_VARIANT_MAP[action.variant || 'default']
                    )}
                  >
                    {action.icon}
                    <span>{action.label}</span>
                  </button>
                ))}
              </div>

              {/* Close Button */}
              <button
                type="button"
                onClick={onClose}
                className="inline-flex items-center justify-center h-8 w-8 rounded-lg text-zinc-500 hover:text-zinc-800 hover:bg-zinc-200/80 dark:text-zinc-400 dark:hover:text-zinc-100 dark:hover:bg-zinc-800 transition-colors focus:outline-hidden focus:ring-2 focus:ring-zinc-400 cursor-pointer ml-1"
                aria-label="Close inspection drawer"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>

          {/* Mobile Quick Actions Row */}
          {quickActions.length > 0 && (
            <div className="flex sm:hidden items-center gap-1.5 pb-3 overflow-x-auto">
              {quickActions.map((action, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={action.onClick}
                  disabled={action.disabled}
                  className={cn(
                    'inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded-md whitespace-nowrap',
                    ACTION_VARIANT_MAP[action.variant || 'default']
                  )}
                >
                  {action.icon}
                  <span>{action.label}</span>
                </button>
              ))}
            </div>
          )}

          {/* Meta Bar Slot (Summary stats / KPI pills) */}
          {metaBar && <div className="py-2.5 border-t border-zinc-200/70 dark:border-zinc-800/80">{metaBar}</div>}

          {/* Tab Navigation Bar */}
          <div className="flex items-center gap-1 overflow-x-auto no-scrollbar border-t border-zinc-200/60 dark:border-zinc-800/70 pt-1 -mb-[1px]">
            {tabs.map((tab) => {
              const isActive = activeTab === tab.id
              return (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => onTabChange(tab.id)}
                  className={cn(
                    'group relative inline-flex items-center gap-2 px-3.5 py-2.5 text-xs font-semibold whitespace-nowrap transition-all border-b-2 cursor-pointer',
                    isActive
                      ? 'border-indigo-600 text-indigo-600 dark:border-indigo-400 dark:text-indigo-400'
                      : 'border-transparent text-zinc-500 hover:text-zinc-800 hover:border-zinc-300 dark:text-zinc-400 dark:hover:text-zinc-200 dark:hover:border-zinc-700'
                  )}
                >
                  {tab.icon && (
                    <span
                      className={cn(
                        'transition-colors',
                        isActive ? 'text-indigo-600 dark:text-indigo-400' : 'text-zinc-400 group-hover:text-zinc-600 dark:text-zinc-500'
                      )}
                    >
                      {tab.icon}
                    </span>
                  )}
                  <span>{tab.label}</span>
                  {tab.count !== undefined && (
                    <span
                      className={cn(
                        'inline-flex items-center justify-center px-1.5 py-0.5 text-[10px] font-bold rounded-full',
                        isActive
                          ? 'bg-indigo-100 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300'
                          : 'bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400'
                      )}
                    >
                      {tab.count}
                    </span>
                  )}
                </button>
              )
            })}
          </div>
        </div>

        {/* Scrollable Content Body */}
        <div className="flex-1 overflow-y-auto p-6 bg-zinc-50/50 dark:bg-zinc-950">
          {children}
        </div>

        {/* Optional Footer */}
        {footer && (
          <div className="border-t border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900/90 px-6 py-3.5 shrink-0">
            {footer}
          </div>
        )}
      </div>
    </div>
  )
}
