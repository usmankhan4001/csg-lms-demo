'use client'

import React, { useState, useEffect, useMemo } from 'react'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import {
  GraduationCap,
  Layers,
  Users,
  ShieldCheck,
  ChevronDown,
  LogOut,
  X,
  Building2,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useAuth } from '@/components/Contexts/AuthContext'
import {
  UserRole,
  ROLE_NAV_ITEMS,
  SAMPLE_USERS,
  NavItem,
} from './types'
import { useOrgFeatureFlags } from '@/lib/api/useOrgFeatureFlags'
import { isFeatureEnabled } from '@/lib/api/org-features'

interface RoleSidebarProps {
  currentRole: UserRole
  onRoleChange?: (role: UserRole) => void
  isMobileOpen?: boolean
  onMobileClose?: () => void
  isCollapsed?: boolean
  onToggleCollapse?: () => void
  className?: string
}

const ROLE_CONFIG: Record<
  UserRole,
  {
    label: string
    title: string
    accentColor: string
    badgeBg: string
    badgeText: string
    icon: React.ElementType
    path: string
  }
> = {
  STUDENT: {
    label: 'Student',
    title: 'Student Portal',
    accentColor: 'text-blue-500',
    badgeBg: 'bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20',
    badgeText: 'STUDENT',
    icon: GraduationCap,
    path: '/student',
  },
  TEACHER: {
    label: 'Teacher',
    title: 'Teacher Hub',
    accentColor: 'text-amber-500',
    badgeBg: 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20',
    badgeText: 'TEACHER',
    icon: Layers,
    path: '/teacher',
  },
  PARENT: {
    label: 'Parent',
    title: 'Parent Portal',
    accentColor: 'text-emerald-500',
    badgeBg: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20',
    badgeText: 'PARENT',
    icon: Users,
    path: '/parent',
  },
  ADMIN: {
    label: 'Admin',
    title: 'Admin Console',
    accentColor: 'text-purple-500',
    badgeBg: 'bg-purple-500/10 text-purple-600 dark:text-purple-400 border-purple-500/20',
    badgeText: 'ADMIN',
    icon: ShieldCheck,
    path: '/campus-admin',
  },
}

export function RoleSidebar({
  currentRole,
  onRoleChange,
  isMobileOpen = false,
  onMobileClose,
  isCollapsed = false,
  onToggleCollapse,
  className,
}: RoleSidebarProps) {
  const pathname = usePathname()
  const router = useRouter()
  const { signOut } = useAuth()
  const [roleMenuOpen, setRoleMenuOpen] = useState(false)
  const [currentHash, setCurrentHash] = useState('')

  useEffect(() => {
    if (typeof window !== 'undefined') {
      setCurrentHash(window.location.hash)
      const handleHashChange = () => setCurrentHash(window.location.hash)
      window.addEventListener('hashchange', handleHashChange)
      return () => window.removeEventListener('hashchange', handleHashChange)
    }
  }, [])

  // Close mobile sidebar on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isMobileOpen && onMobileClose) {
        onMobileClose()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isMobileOpen, onMobileClose])

  const { flags } = useOrgFeatureFlags()

  // Per DESIGN-SYSTEM.md §2.3: "Modules hidden by feature flag or RBAC are
  // removed from navigation, not disabled." Items with no `featureKey`
  // (the persona's home page) are always shown; `isFeatureEnabled` fails
  // open while flags haven't loaded yet (see lib/api/org-features.ts).
  const navItems = useMemo(
    () => (ROLE_NAV_ITEMS[currentRole] || []).filter((item) => isFeatureEnabled(flags, item.featureKey)),
    [currentRole, flags]
  )
  const user = SAMPLE_USERS[currentRole]
  const roleConfig = ROLE_CONFIG[currentRole]

  const handleSwitchRole = (role: UserRole) => {
    setRoleMenuOpen(false)
    if (onRoleChange) {
      onRoleChange(role)
    }
    const targetPath = ROLE_CONFIG[role].path
    router.push(targetPath)
    if (onMobileClose) {
      onMobileClose()
    }
  }

  const isItemActive = (item: NavItem) => {
    if (item.href.includes('#')) {
      const [itemPath, itemHash] = item.href.split('#')
      if (itemPath === pathname && currentHash === `#${itemHash}`) {
        return true
      }
      return false
    }
    if (item.href === '/admin' || item.href === '/student' || item.href === '/teacher' || item.href === '/parent') {
      return pathname === item.href && !currentHash
    }
    return (pathname === item.href || pathname.startsWith(item.href + '/')) && !currentHash
  }

  const renderBadge = (badge?: string | number, color?: string) => {
    if (!badge) return null
    let colorClass = 'bg-neutral-100 text-neutral-600 dark:bg-neutral-800 dark:text-neutral-300'
    if (color === 'success') {
      colorClass = 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20'
    } else if (color === 'warning') {
      colorClass = 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20'
    } else if (color === 'danger') {
      colorClass = 'bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/20'
    } else if (color === 'primary') {
      colorClass = 'bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20'
    }

    return (
      <span
        className={cn(
          'ms-auto inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium',
          colorClass
        )}
      >
        {badge}
      </span>
    )
  }

  const sidebarContent = (
    <div className="flex flex-col h-full bg-white dark:bg-neutral-900 border-e border-neutral-200 dark:border-neutral-800 select-none">
      {/* Brand & Portal Header */}
      <div className="p-4 border-b border-neutral-200 dark:border-neutral-800 flex items-center justify-between">
        <Link
          href="/"
          className="flex items-center gap-3 group focus:outline-hidden focus:ring-2 focus:ring-blue-500 rounded-lg p-1"
        >
          <div className="size-9 rounded-xl bg-gradient-to-br from-blue-600 to-indigo-700 flex items-center justify-center text-white font-bold shadow-md shadow-blue-500/20">
            <span className="text-base tracking-tighter">CSG</span>
          </div>
          {!isCollapsed && (
            <div className="flex flex-col">
              <span className="text-sm font-bold tracking-tight text-neutral-900 dark:text-white leading-tight">
                CSG LMS
              </span>
              <span className="text-xs text-neutral-500 dark:text-neutral-400 leading-tight">
                Next-Gen EduOS
              </span>
            </div>
          )}
        </Link>

        {/* Mobile close button */}
        {isMobileOpen && onMobileClose && (
          <button
            onClick={onMobileClose}
            className="p-1.5 rounded-lg text-neutral-500 hover:text-neutral-900 hover:bg-neutral-100 dark:hover:bg-neutral-800 transition-colors"
            aria-label="Close menu"
          >
            <X className="size-5" />
          </button>
        )}
      </div>

      {/* Active Role Selector Badge */}
      {!isCollapsed && (
        <div className="px-4 py-3 border-b border-neutral-100 dark:border-neutral-800/60 bg-neutral-50/70 dark:bg-neutral-900/50">
          <div className="relative">
            <button
              onClick={() => setRoleMenuOpen(!roleMenuOpen)}
              className="w-full flex items-center justify-between p-2 rounded-lg bg-white dark:bg-neutral-800 border border-neutral-200 dark:border-neutral-700 text-start shadow-xs hover:border-neutral-300 dark:hover:border-neutral-600 transition-all focus:outline-hidden focus:ring-2 focus:ring-blue-500"
              aria-expanded={roleMenuOpen}
              aria-label="Switch active portal role"
            >
              <div className="flex items-center gap-2.5 min-w-0">
                <div
                  className={cn(
                    'size-7 rounded-md flex items-center justify-center border',
                    roleConfig.badgeBg
                  )}
                >
                  <roleConfig.icon className="size-4" />
                </div>
                <div className="truncate">
                  <div className="text-xs font-semibold text-neutral-900 dark:text-neutral-100 truncate">
                    {roleConfig.title}
                  </div>
                  <div className="text-[11px] text-neutral-500 dark:text-neutral-400">
                    Switch role portal
                  </div>
                </div>
              </div>
              <ChevronDown
                className={cn(
                  'size-4 text-neutral-400 shrink-0 transition-transform duration-200',
                  roleMenuOpen && 'rotate-180'
                )}
              />
            </button>

            {/* Role dropdown list */}
            {roleMenuOpen && (
              <div className="absolute top-full start-0 end-0 mt-1.5 p-1.5 bg-white dark:bg-neutral-800 border border-neutral-200 dark:border-neutral-700 rounded-xl shadow-xl z-50 animate-in fade-in slide-in-from-top-1 duration-150">
                <div className="px-2 py-1 text-[11px] font-semibold text-neutral-400 uppercase tracking-wider">
                  Select Role Portal
                </div>
                {(['STUDENT', 'TEACHER', 'PARENT', 'ADMIN'] as UserRole[]).map((r) => {
                  const cfg = ROLE_CONFIG[r]
                  const Icon = cfg.icon
                  const isSelected = currentRole === r

                  return (
                    <button
                      key={r}
                      onClick={() => handleSwitchRole(r)}
                      className={cn(
                        'w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-xs font-medium text-start transition-colors',
                        isSelected
                          ? 'bg-neutral-100 dark:bg-neutral-700 text-neutral-900 dark:text-white font-semibold'
                          : 'text-neutral-600 dark:text-neutral-300 hover:bg-neutral-50 dark:hover:bg-neutral-700/50'
                      )}
                    >
                      <div
                        className={cn(
                          'size-6 rounded-md flex items-center justify-center border',
                          cfg.badgeBg
                        )}
                      >
                        <Icon className="size-3.5" />
                      </div>
                      <span className="flex-1">{cfg.title}</span>
                      {isSelected && (
                        <span className="size-1.5 rounded-full bg-blue-500" />
                      )}
                    </button>
                  )
                })}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Navigation Links */}
      <div className="flex-1 overflow-y-auto px-3 py-4 space-y-1.5 scrollbar-hide">
        {!isCollapsed && (
          <div className="px-3 pb-2 text-[11px] font-semibold text-neutral-400 dark:text-neutral-500 uppercase tracking-wider">
            {roleConfig.label} Navigation
          </div>
        )}

        {navItems.map((item) => {
          const Icon = item.icon
          const active = isItemActive(item)

          return (
            <Link
              key={item.id}
              href={item.href}
              onClick={() => {
                if (onMobileClose) onMobileClose()
              }}
              title={isCollapsed ? item.title : undefined}
              className={cn(
                'group flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all focus:outline-hidden focus:ring-2 focus:ring-blue-500',
                active
                  ? 'bg-blue-600 text-white shadow-sm shadow-blue-500/20'
                  : 'text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-neutral-100 hover:bg-neutral-100 dark:hover:bg-neutral-800/70'
              )}
            >
              <Icon
                className={cn(
                  'size-4.5 shrink-0 transition-transform duration-200 group-hover:scale-110',
                  active ? 'text-white' : 'text-neutral-500 dark:text-neutral-400 group-hover:text-neutral-900 dark:group-hover:text-neutral-100'
                )}
              />
              {!isCollapsed && (
                <>
                  <span className="truncate">{item.title}</span>
                  {renderBadge(item.badge, active ? 'default' : item.badgeColor)}
                </>
              )}
            </Link>
          )
        })}
      </div>

      {/* Footer User Info */}
      <div className="p-3 border-t border-neutral-200 dark:border-neutral-800 bg-neutral-50/50 dark:bg-neutral-900/30">
        <div className="flex items-center gap-3">
          <div className="size-9 rounded-full bg-gradient-to-tr from-blue-600 to-indigo-600 flex items-center justify-center text-white font-semibold text-sm shrink-0 shadow-xs">
            {user.name.charAt(0)}
          </div>
          {!isCollapsed && (
            <div className="min-w-0 flex-1">
              <div className="text-xs font-bold text-neutral-900 dark:text-white truncate">
                {user.name}
              </div>
              <div className="text-[11px] text-neutral-500 dark:text-neutral-400 truncate">
                {user.gradeOrDept || user.studentId || user.email}
              </div>
            </div>
          )}
          {!isCollapsed && (
            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={() => signOut({ callbackUrl: '/auth/login' })}
                title="Sign out"
                className="p-1.5 rounded-lg text-neutral-400 hover:text-rose-600 hover:bg-neutral-100 dark:hover:bg-neutral-800 transition-colors"
                aria-label="Sign out"
              >
                <LogOut className="size-4" />
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )

  return (
    <>
      {/* Desktop Persistent Sidebar */}
      <aside
        className={cn(
          'hidden md:flex flex-col shrink-0 h-screen sticky top-0 z-30 transition-all duration-300',
          isCollapsed ? 'w-20' : 'w-64',
          className
        )}
      >
        {sidebarContent}
      </aside>

      {/* Mobile Drawer Overlay */}
      {isMobileOpen && (
        <div
          className="fixed inset-0 z-50 md:hidden bg-black/60 backdrop-blur-xs transition-opacity animate-in fade-in"
          onClick={onMobileClose}
          aria-hidden="true"
        />
      )}

      {/* Mobile Slide-out Drawer */}
      <div
        className={cn(
          'fixed inset-y-0 start-0 z-50 w-72 md:hidden transform transition-transform duration-300 ease-in-out shadow-2xl',
          isMobileOpen ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        {sidebarContent}
      </div>
    </>
  )
}
