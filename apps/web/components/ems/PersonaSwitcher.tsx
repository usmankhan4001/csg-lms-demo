'use client'

import React, { useState, useRef, useEffect } from 'react'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import {
  Compass,
  GraduationCap,
  Sparkles,
  HeartHandshake,
  ShieldAlert,
  UserPlus,
  Boxes,
  ChevronDown,
  LayoutDashboard,
  ShieldCheck,
  CheckCircle2,
  Lock,
  ArrowRight,
  School,
  ExternalLink,
  ChevronRight,
  Layers,
  Sparkle
} from 'lucide-react'
import { useOrg, useOrgMembership } from '@components/Contexts/OrgContext'
import { useSchoolSession } from '@/lib/api/useSchoolSession'
import { useLHSession } from '@components/Contexts/LHSessionContext'

export type PersonaPortalId =
  | 'executive'
  | 'teacher'
  | 'learner'
  | 'parent'
  | 'clinical'
  | 'admissions'
  | 'operations'

export interface PersonaPortalConfig {
  id: PersonaPortalId
  label: string
  shortLabel: string
  subtitle: string
  description: string
  icon: React.ComponentType<{ className?: string }>
  badge: string
  roles: string[]
  theme: {
    accentBg: string
    accentText: string
    accentBorder: string
    ringColor: string
    chipClass: string
  }
}

export const PERSONA_PORTALS: PersonaPortalConfig[] = [
  {
    id: 'executive',
    label: 'Executive Leadership Console',
    shortLabel: 'Executive',
    subtitle: 'AMI Index, Financial Health & Radar',
    description: 'Autonomous Institutional telemetry, faculty workload balance & financial health.',
    icon: Compass,
    badge: 'Governance',
    roles: ['SUPER_ADMIN', 'SCHOOL_ADMIN', 'HEAD_OF_SCHOOL', 'EXECUTIVE', 'DIRECTOR'],
    theme: {
      accentBg: 'bg-indigo-50 hover:bg-indigo-100/80',
      accentText: 'text-indigo-700',
      accentBorder: 'border-indigo-200',
      ringColor: 'ring-indigo-500/30',
      chipClass: 'bg-indigo-100/80 text-indigo-800 border-indigo-200',
    },
  },
  {
    id: 'teacher',
    label: 'Teacher Studio',
    shortLabel: 'Teacher',
    subtitle: 'Class Schedules, SpeedGrader & Roll Call',
    description: 'Frictionless classroom management, rapid grading rubrics & live studio telemetry.',
    icon: GraduationCap,
    badge: 'Faculty',
    roles: ['TEACHER', 'FACULTY', 'INSTRUCTOR', 'HOD'],
    theme: {
      accentBg: 'bg-emerald-50 hover:bg-emerald-100/80',
      accentText: 'text-emerald-700',
      accentBorder: 'border-emerald-200',
      ringColor: 'ring-emerald-500/30',
      chipClass: 'bg-emerald-100/80 text-emerald-800 border-emerald-200',
    },
  },
  {
    id: 'learner',
    label: 'Learner Hub',
    shortLabel: 'Learner',
    subtitle: 'My Flight Plan, Socratic AI & Mastery Graph',
    description: 'Adaptive 3-tier homework companion, socratic dialogue & competency skill trees.',
    icon: Sparkles,
    badge: 'Student',
    roles: ['STUDENT', 'LEARNER', 'SCHOLAR'],
    theme: {
      accentBg: 'bg-amber-50 hover:bg-amber-100/80',
      accentText: 'text-amber-700',
      accentBorder: 'border-amber-200',
      ringColor: 'ring-amber-500/30',
      chipClass: 'bg-amber-100/80 text-amber-800 border-amber-200',
    },
  },
  {
    id: 'parent',
    label: 'Parent Gateway',
    shortLabel: 'Parent',
    subtitle: 'Ward Timelines, 1-Click Pay & AI Caps',
    description: 'Multi-child real-time timeline, instant digital excuse notes & screen-time controls.',
    icon: HeartHandshake,
    badge: 'Family',
    roles: ['PARENT', 'GUARDIAN'],
    theme: {
      accentBg: 'bg-rose-50 hover:bg-rose-100/80',
      accentText: 'text-rose-700',
      accentBorder: 'border-rose-200',
      ringColor: 'ring-rose-500/30',
      chipClass: 'bg-rose-100/80 text-rose-800 border-rose-200',
    },
  },
  {
    id: 'clinical',
    label: 'Confidential Clinical Desk',
    shortLabel: 'Clinical',
    subtitle: 'Zero-Knowledge Notes & Crisis Triage',
    description: 'Client-side encrypted psychological logs, pastoral alerts & safeguarding triage.',
    icon: ShieldAlert,
    badge: 'Confidential',
    roles: ['PSYCHOLOGIST', 'COUNSELOR', 'NURSE', 'SPECIALIST', 'SAFEGUARDING_OFFICER'],
    theme: {
      accentBg: 'bg-teal-50 hover:bg-teal-100/80',
      accentText: 'text-teal-700',
      accentBorder: 'border-teal-200',
      ringColor: 'ring-teal-500/30',
      chipClass: 'bg-teal-100/80 text-teal-800 border-teal-200',
    },
  },
  {
    id: 'admissions',
    label: 'Admissions & RevOps Center',
    shortLabel: 'Admissions',
    subtitle: 'Kanban CRM, Yield Modeler & Matriculation',
    description: 'Full enrollment pipeline, net tuition yield simulator & 1-click SIS onboarding.',
    icon: UserPlus,
    badge: 'RevOps',
    roles: ['ADMISSIONS', 'REVOPS', 'MARKETING', 'REGISTRAR'],
    theme: {
      accentBg: 'bg-blue-50 hover:bg-blue-100/80',
      accentText: 'text-blue-700',
      accentBorder: 'border-blue-200',
      ringColor: 'ring-blue-500/30',
      chipClass: 'bg-blue-100/80 text-blue-800 border-blue-200',
    },
  },
  {
    id: 'operations',
    label: 'School Operations Desk',
    shortLabel: 'Operations',
    subtitle: 'Fee Billing, Library Loans & Transport Fleet',
    description: 'Cashflow telemetry, circulation tracking & real-time GPS bus manifest telemetry.',
    icon: Boxes,
    badge: 'Operations',
    roles: ['BURSAR', 'ACCOUNTANT', 'STAFF', 'OPERATIONS', 'LIBRARIAN', 'TRANSPORT_COORDINATOR'],
    theme: {
      accentBg: 'bg-purple-50 hover:bg-purple-100/80',
      accentText: 'text-purple-700',
      accentBorder: 'border-purple-200',
      ringColor: 'ring-purple-500/30',
      chipClass: 'bg-purple-100/80 text-purple-800 border-purple-200',
    },
  },
]

export interface BreadcrumbItem {
  label: string
  href?: string
}

export interface PersonaSwitcherProps {
  currentPortal?: PersonaPortalId
  breadcrumbs?: BreadcrumbItem[]
  titleOverride?: string
  actions?: React.ReactNode
  className?: string
}

export function PersonaSwitcher({
  currentPortal,
  breadcrumbs = [],
  titleOverride,
  actions,
  className = '',
}: PersonaSwitcherProps) {
  const pathname = usePathname()
  const router = useRouter()
  const { orgslug } = useOrgMembership()
  const org = useOrg() as any
  const lhSession = useLHSession() as any
  const { session: schoolSession, checked } = useSchoolSession()

  const [isOpen, setIsOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  // Close dropdown on click outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // Resolve active portal from prop or pathname
  const activePortalId: PersonaPortalId =
    currentPortal ||
    (PERSONA_PORTALS.find((p) => pathname?.includes(`/${p.id}`))?.id ?? 'executive')

  const activePortal = PERSONA_PORTALS.find((p) => p.id === activePortalId) ?? PERSONA_PORTALS[0]

  // Role permissions computation
  const userRoles = schoolSession?.roles ?? []
  const isSuperAdmin =
    userRoles.includes('SUPER_ADMIN') ||
    userRoles.includes('SCHOOL_ADMIN') ||
    lhSession?.data?.user?.is_superadmin ||
    userRoles.length === 0 // Unrestricted org admin setup mode

  // Compute allowed portals
  const accessiblePortals = PERSONA_PORTALS.filter((portal) => {
    if (isSuperAdmin) return true
    return portal.roles.some((r) => userRoles.includes(r))
  })

  // Has multiple personas available
  const hasMultiplePersonas = accessiblePortals.length > 1 || isSuperAdmin

  const ActiveIcon = activePortal.icon

  return (
    <header className={`sticky top-0 z-40 w-full border-b border-gray-200/80 bg-white/95 backdrop-blur-md transition-all ${className}`}>
      {/* Top Navbar */}
      <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-2.5 sm:px-6 lg:px-8">
        {/* Left: Org Logo, Divider & Persona Switcher Trigger */}
        <div className="flex items-center gap-3">
          <Link
            href={`/orgs/${orgslug}/dash`}
            className="group flex items-center gap-2 rounded-lg px-2 py-1 text-xs font-semibold text-gray-700 transition hover:bg-gray-100"
            title="Go to School Central Dashboard"
          >
            <div className="flex size-7 items-center justify-center rounded-md bg-gray-900 text-white shadow-sm transition group-hover:scale-105">
              <School className="size-4" />
            </div>
            <span className="hidden font-bold tracking-tight text-gray-900 sm:inline-block">
              {org?.name || 'CSG-EMS'}
            </span>
          </Link>

          <span className="text-gray-300 font-light">/</span>

          {/* Persona Switcher Dropdown Anchor */}
          <div className="relative" ref={dropdownRef}>
            <button
              id="persona-switcher-button"
              type="button"
              onClick={() => setIsOpen(!isOpen)}
              className={`group flex items-center gap-2.5 rounded-xl border px-3 py-1.5 text-xs font-medium transition-all shadow-sm ${
                activePortal.theme.accentBg
              } ${activePortal.theme.accentBorder} ${
                isOpen ? 'ring-2 ring-indigo-500/20 shadow-md' : 'hover:shadow'
              }`}
              aria-expanded={isOpen}
              aria-haspopup="true"
            >
              <div
                className={`flex size-6 items-center justify-center rounded-lg ${activePortal.theme.chipClass} shadow-2xs`}
              >
                <ActiveIcon className="size-3.5" />
              </div>
              <div className="flex flex-col text-left">
                <div className="flex items-center gap-1.5">
                  <span className={`font-semibold ${activePortal.theme.accentText}`}>
                    {activePortal.label}
                  </span>
                  <span className={`rounded-full px-1.5 py-0.2 text-[10px] font-bold uppercase tracking-wider ${activePortal.theme.chipClass}`}>
                    {activePortal.badge}
                  </span>
                </div>
              </div>
              <ChevronDown
                className={`size-3.5 text-gray-500 transition-transform duration-200 ${
                  isOpen ? 'rotate-180' : 'group-hover:translate-y-0.5'
                }`}
              />
            </button>

            {/* Dropdown Menu */}
            {isOpen && (
              <div className="absolute left-0 mt-2 w-[340px] sm:w-[420px] origin-top-left rounded-2xl border border-gray-200/90 bg-white p-2 shadow-2xl ring-1 ring-black/5 animate-in fade-in-0 zoom-in-95 duration-150 z-50">
                <div className="border-b border-gray-100 px-3 py-2.5">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold uppercase tracking-wider text-gray-500">
                      Select Dedicated Persona
                    </span>
                    {isSuperAdmin && (
                      <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-semibold text-emerald-700 border border-emerald-200">
                        <ShieldCheck className="size-3" /> All 7 Portals Unlocked
                      </span>
                    )}
                  </div>
                  <p className="mt-0.5 text-[11px] text-gray-400">
                    Switch context dynamically without signing out.
                  </p>
                </div>

                <div className="mt-1.5 max-h-[380px] space-y-1 overflow-y-auto px-1 py-1">
                  {PERSONA_PORTALS.map((portal) => {
                    const isSelected = portal.id === activePortalId
                    const isAllowed = isSuperAdmin || portal.roles.some((r) => userRoles.includes(r))
                    const PIcon = portal.icon

                    return (
                      <button
                        key={portal.id}
                        type="button"
                        disabled={!isAllowed}
                        onClick={() => {
                          setIsOpen(false)
                          router.push(`/orgs/${orgslug}/${portal.id}`)
                        }}
                        className={`group flex w-full items-start gap-3 rounded-xl p-2.5 text-left transition-all ${
                          isSelected
                            ? `${portal.theme.accentBg} ${portal.theme.accentBorder} border shadow-xs`
                            : isAllowed
                            ? 'hover:bg-gray-50 border border-transparent'
                            : 'opacity-40 cursor-not-allowed border border-transparent'
                        }`}
                      >
                        <div
                          className={`mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg shadow-2xs transition-transform group-hover:scale-105 ${
                            isSelected ? portal.theme.chipClass : 'bg-gray-100 text-gray-600'
                          }`}
                        >
                          <PIcon className="size-4" />
                        </div>
                        <div className="flex flex-1 flex-col min-w-0">
                          <div className="flex items-center justify-between">
                            <span
                              className={`text-xs font-bold ${
                                isSelected ? portal.theme.accentText : 'text-gray-900'
                              }`}
                            >
                              {portal.label}
                            </span>
                            <div className="flex items-center gap-1">
                              <span className="rounded bg-gray-100 px-1.5 py-0.5 text-[9px] font-medium text-gray-600 uppercase">
                                {portal.badge}
                              </span>
                              {isSelected && (
                                <CheckCircle2 className={`size-3.5 ${portal.theme.accentText}`} />
                              )}
                              {!isAllowed && <Lock className="size-3 text-gray-400" />}
                            </div>
                          </div>
                          <p className="mt-0.5 text-[11px] text-gray-500 line-clamp-1">
                            {portal.subtitle}
                          </p>
                        </div>
                      </button>
                    )
                  })}
                </div>

                {/* Footer Switcher Action */}
                <div className="mt-2 border-t border-gray-100 pt-2 px-2 pb-1 flex items-center justify-between text-xs">
                  <Link
                    href={`/orgs/${orgslug}/dash`}
                    onClick={() => setIsOpen(false)}
                    className="inline-flex items-center gap-1.5 font-medium text-gray-600 hover:text-gray-900 transition"
                  >
                    <LayoutDashboard className="size-3.5" />
                    School Classic Dash
                  </Link>
                  <span className="text-[10px] text-gray-400 font-mono">
                    EMS v4.2 • Autonomous OS
                  </span>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Right: Quick Portal Navigation Badges & Status */}
        <div className="flex items-center gap-2 sm:gap-3">
          {/* Quick jump badges for prominent multi-roles on desktop */}
          <div className="hidden items-center gap-1.5 xl:flex">
            {PERSONA_PORTALS.slice(0, 5).map((p) => {
              const isActive = p.id === activePortalId
              const PIcon = p.icon
              return (
                <Link
                  key={p.id}
                  href={`/orgs/${orgslug}/${p.id}`}
                  className={`flex items-center gap-1 rounded-lg px-2 py-1 text-[11px] font-medium transition ${
                    isActive
                      ? `${p.theme.chipClass} shadow-2xs font-semibold`
                      : 'text-gray-500 hover:bg-gray-100 hover:text-gray-900'
                  }`}
                >
                  <PIcon className="size-3" />
                  <span>{p.shortLabel}</span>
                </Link>
              )
            })}
          </div>

          {/* Active Academic Term Pill */}
          <div className="hidden sm:flex items-center gap-1.5 rounded-full bg-gray-100 px-2.5 py-1 text-[11px] font-medium text-gray-600 border border-gray-200/60">
            <span className="size-1.5 rounded-full bg-emerald-500 animate-pulse" />
            <span>Term 2 (2026-27)</span>
          </div>

          {/* Action Slots */}
          {actions}
        </div>
      </div>

      {/* Secondary Context Breadcrumbs Bar */}
      {breadcrumbs.length > 0 && (
        <div className="border-t border-gray-100/80 bg-gray-50/60 px-4 py-1.5 sm:px-6 lg:px-8">
          <nav className="mx-auto flex max-w-7xl items-center gap-1.5 text-xs text-gray-500">
            <Link
              href={`/orgs/${orgslug}/dash`}
              className="hover:text-gray-900 font-medium transition"
            >
              {org?.name || 'Dashboard'}
            </Link>
            <ChevronRight className="size-3 text-gray-400" />
            <Link
              href={`/orgs/${orgslug}/${activePortal.id}`}
              className={`font-semibold ${activePortal.theme.accentText} hover:underline`}
            >
              {activePortal.shortLabel} Portal
            </Link>
            {breadcrumbs.map((crumb, idx) => (
              <React.Fragment key={idx}>
                <ChevronRight className="size-3 text-gray-400" />
                {crumb.href ? (
                  <Link
                    href={crumb.href}
                    className="hover:text-gray-900 font-medium transition"
                  >
                    {crumb.label}
                  </Link>
                ) : (
                  <span className="font-semibold text-gray-800">{crumb.label}</span>
                )}
              </React.Fragment>
            ))}
          </nav>
        </div>
      )}
    </header>
  )
}

export default PersonaSwitcher
