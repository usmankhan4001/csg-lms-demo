'use client'

import * as React from 'react'
import { cn } from '@/lib/utils'
import { LH_HEADER, LH_PAGE, LH_TITLE } from './lh-styles'
import { ModuleTabs } from './ModuleTabs'
import type { SchoolModuleKey } from '@/lib/school-modules'

/**
 * The page wrapper every Learnhouse dash route uses, so the school modules
 * stop hand-rolling their own (`p-6` + `text-xl`, which sat on the wrong
 * background at the wrong type scale).
 *
 * Mirrors `dash/podcasts/client.tsx` and `dash/playgrounds/client.tsx`:
 * a `#f8f8f8` full-height surface with responsive side gutters, a header
 * block, a 3xl bold title, and an optional right-aligned primary action that
 * drops below the title on narrow screens.
 */

export interface DashPageShellProps {
  title: string
  description?: string
  /** Right-aligned header slot -- typically the page's primary action. */
  action?: React.ReactNode
  /** Rendered above the title, e.g. <Breadcrumbs />. */
  breadcrumbs?: React.ReactNode
  /**
   * Renders this school module's tab strip under the header, so a module's
   * screens are reached from inside it rather than from 31 extra sidebar
   * entries. Tabs are role-gated individually -- see ModuleTabs.
   */
  module?: SchoolModuleKey
  className?: string
  children?: React.ReactNode
}

export function DashPageShell({
  title,
  description,
  action,
  breadcrumbs,
  module,
  className,
  children,
}: DashPageShellProps) {
  return (
    <div className={cn(LH_PAGE, className)}>
      <div className={LH_HEADER}>
        {breadcrumbs}
        <div
          className={cn(
            'flex flex-col sm:flex-row justify-between items-start sm:items-center',
            breadcrumbs && 'mt-4'
          )}
        >
          <div className="min-w-0">
            <h1 className={LH_TITLE}>{title}</h1>
            {description && <p className="text-sm text-gray-400 mt-1">{description}</p>}
          </div>
          {action}
        </div>
        {module && <ModuleTabs module={module} />}
      </div>
      <div className="flex flex-col gap-5 pb-10">{children}</div>
    </div>
  )
}
