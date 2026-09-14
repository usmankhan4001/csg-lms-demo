'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { cn } from '@/lib/utils'
import { useSchoolAccess } from '@/lib/school-access'
import { SCHOOL_MODULES, type SchoolModuleKey } from '@/lib/school-modules'

/**
 * A school module's internal navigation.
 *
 * Modules used to spill their sub-screens into the sidebar as flat siblings,
 * which is what made the nav unreadable at 55 entries. The module now owns its
 * own navigation and the sidebar carries one entry per module.
 *
 * Tabs are gated individually. Collapsing a module's screens behind one
 * sidebar entry must not widen access: a teacher opening Timetable still must
 * not see Generate, so a tab whose `access` the viewer fails is not rendered
 * at all -- not disabled, not greyed. The backend still authorizes every
 * request regardless.
 */

export interface ModuleTabsProps {
  module: SchoolModuleKey
  className?: string
}

export function ModuleTabs({ module, className }: ModuleTabsProps) {
  const pathname = usePathname()
  const { allows } = useSchoolAccess()

  const def = SCHOOL_MODULES[module]
  const visible = def.tabs.filter((t) => allows(t.access))

  // One reachable screen is not a choice; a lone tab is chrome with no
  // purpose, so render nothing rather than a decorative strip.
  if (visible.length < 2) return null

  return (
    <nav
      aria-label={`${module} sections`}
      className={cn(
        'mt-4 flex items-center gap-1 overflow-x-auto',
        '[&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]',
        className
      )}
    >
      {visible.map((tab) => {
        // The module root must match EXACTLY. A prefix match would leave
        // "Roll-call" lit while the viewer is on History, so two tabs would
        // claim to be current at once.
        const isRoot = tab.href === def.root
        const active = isRoot
          ? pathname === tab.href || pathname === `${tab.href}/`
          : pathname === tab.href || pathname.startsWith(`${tab.href}/`)

        return (
          <Link
            key={tab.href}
            id={`module-tab-${tab.href.split('/').filter(Boolean).join('-')}`}
            href={tab.href}
            aria-current={active ? 'page' : undefined}
            className={cn(
              'whitespace-nowrap rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors',
              active
                ? 'bg-white text-gray-900 nice-shadow'
                : 'text-gray-500 hover:bg-white/60 hover:text-gray-700'
            )}
          >
            {tab.label}
          </Link>
        )
      })}
    </nav>
  )
}
