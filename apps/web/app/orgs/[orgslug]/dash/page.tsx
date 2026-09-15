'use client'

import React, { useEffect, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import Link from 'next/link'
import {
  Compass,
  GraduationCap,
  Sparkles,
  HeartHandshake,
  ShieldAlert,
  UserPlus,
  Boxes,
  ArrowRight,
  ShieldCheck,
  LayoutDashboard
} from 'lucide-react'
import SchoolDashboardHome from '@components/Dashboard/Home/SchoolDashboardHome'
import { useSchoolSession } from '@/lib/api/useSchoolSession'
import { useOrgMembership, useOrg } from '@components/Contexts/OrgContext'
import { PERSONA_PORTALS } from '@/components/ems/PersonaSwitcher'

/**
 * `/dash` is the central school entry point.
 * It checks the user's assigned EMS roles and intelligently navigates
 * to their primary native persona portal (e.g. Teacher Studio, Learner Hub,
 * Parent Gateway, Clinical Desk, Admissions Center, or Executive Console).
 *
 * Appending `?classic=true` renders the foundational Learnhouse/SMS dashboard.
 */
export default function DashboardPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { orgslug } = useOrgMembership()
  const org = useOrg() as any
  const { session: schoolSession, checked } = useSchoolSession()

  const isClassicExplicit = searchParams?.get('classic') === 'true'
  const [redirecting, setRedirecting] = useState(false)

  useEffect(() => {
    if (!checked || isClassicExplicit || !orgslug) return

    const roles = schoolSession?.roles ?? []

    // If pure student -> Learner Hub
    if (roles.includes('STUDENT') || roles.includes('LEARNER')) {
      setRedirecting(true)
      router.replace(`/orgs/${orgslug}/learner`)
      return
    }

    // If pure parent -> Parent Gateway
    if (roles.includes('PARENT') || roles.includes('GUARDIAN')) {
      setRedirecting(true)
      router.replace(`/orgs/${orgslug}/parent`)
      return
    }

    // If clinical specialist -> Clinical Desk
    if (
      (roles.includes('PSYCHOLOGIST') || roles.includes('COUNSELOR')) &&
      !roles.includes('SUPER_ADMIN') &&
      !roles.includes('SCHOOL_ADMIN')
    ) {
      setRedirecting(true)
      router.replace(`/orgs/${orgslug}/clinical`)
      return
    }

    // If teacher (and not admin) -> Teacher Studio
    if (
      roles.includes('TEACHER') &&
      !roles.includes('SUPER_ADMIN') &&
      !roles.includes('SCHOOL_ADMIN')
    ) {
      setRedirecting(true)
      router.replace(`/orgs/${orgslug}/teacher`)
      return
    }

    // If admissions -> Admissions Center
    if (
      (roles.includes('ADMISSIONS') || roles.includes('REVOPS')) &&
      !roles.includes('SUPER_ADMIN') &&
      !roles.includes('SCHOOL_ADMIN')
    ) {
      setRedirecting(true)
      router.replace(`/orgs/${orgslug}/admissions`)
      return
    }

    // If bursar/staff -> Operations Desk
    if (
      (roles.includes('BURSAR') || roles.includes('STAFF')) &&
      !roles.includes('SUPER_ADMIN') &&
      !roles.includes('SCHOOL_ADMIN')
    ) {
      setRedirecting(true)
      router.replace(`/orgs/${orgslug}/operations`)
      return
    }

    // If Super Admin / School Admin -> Executive Console by default
    if (roles.includes('SUPER_ADMIN') || roles.includes('SCHOOL_ADMIN')) {
      setRedirecting(true)
      router.replace(`/orgs/${orgslug}/executive`)
      return
    }
  }, [checked, schoolSession?.roles, orgslug, isClassicExplicit, router])

  if (redirecting) {
    return (
      <div className="flex min-h-[60vh] w-full items-center justify-center bg-[#f8f8f8]">
        <div className="flex flex-col items-center gap-3 text-center">
          <div className="size-8 animate-spin rounded-full border-3 border-indigo-600 border-t-transparent" />
          <p className="text-xs font-semibold text-gray-500">
            Connecting to your persona-native portal...
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col w-full">
      {/* Top Banner Prompt to Explore Persona Portals */}
      <div className="border-b border-indigo-100 bg-indigo-50/70 px-4 py-3 sm:px-10">
        <div className="mx-auto flex max-w-[1600px] flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <span className="flex size-6 items-center justify-center rounded-lg bg-indigo-600 text-white shadow-2xs">
              <Compass className="size-3.5" />
            </span>
            <div>
              <span className="text-xs font-bold text-indigo-950">
                Persona-Native Dedicated Portals Available
              </span>
              <p className="text-[11px] text-indigo-700">
                Switch instantly between role-dedicated portals for Executive, Teacher, Learner, Parent, Clinical, Admissions, and Operations.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            {PERSONA_PORTALS.map((p) => (
              <Link
                key={p.id}
                href={`/orgs/${orgslug}/${p.id}`}
                className="inline-flex items-center gap-1 rounded-lg bg-white px-2.5 py-1 text-xs font-bold text-gray-700 shadow-2xs hover:bg-gray-50 border border-gray-200 transition"
              >
                <span>{p.shortLabel}</span>
                <ArrowRight className="size-3 text-gray-400" />
              </Link>
            ))}
          </div>
        </div>
      </div>

      <SchoolDashboardHome />
    </div>
  )
}
