'use client'

import React, { Suspense, useEffect, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { GraduationCap, Layers, Users, ShieldCheck, AlertTriangle } from 'lucide-react'
import { useAuth } from '@/components/Contexts/AuthContext'
import { mintAndStoreDevToken, type DevRealmRole } from '@/lib/api/devLogin'

const PORTALS: { role: DevRealmRole; label: string; description: string; icon: React.ElementType; path: string }[] = [
  {
    role: 'STUDENT',
    label: 'Student',
    description: 'Timetable, courses, AI Tutor, attendance',
    icon: GraduationCap,
    path: '/student',
  },
  {
    role: 'TEACHER',
    label: 'Teacher',
    description: 'Classes, roll-call, gradebook, lesson planner',
    icon: Layers,
    path: '/teacher',
  },
  {
    role: 'PARENT',
    label: 'Parent',
    description: 'Attendance calendar, fees, AI progress digest',
    icon: Users,
    path: '/parent',
  },
  {
    role: 'SCHOOL_ADMIN',
    label: 'Campus Admin',
    description: 'Campuses, admissions, finance, staff',
    icon: ShieldCheck,
    path: '/campus-admin',
  },
]

function DevLoginInner() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { status, getAccessToken } = useAuth()
  const [loadingRole, setLoadingRole] = useState<DevRealmRole | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handlePick = async (portal: (typeof PORTALS)[number]) => {
    setError(null)
    setLoadingRole(portal.role)
    try {
      const accessToken = await getAccessToken()
      if (!accessToken) {
        setError('You need to be signed in first.')
        return
      }
      await mintAndStoreDevToken(portal.role, accessToken)
      router.push(portal.path)
    } catch (e: any) {
      setError(
        e?.status === 403
          ? 'Your Learnhouse account is not a superadmin, so it cannot mint a dev token. Sign in as admin@csg.dev.'
          : e?.message || 'Could not mint a dev token.'
      )
    } finally {
      setLoadingRole(null)
    }
  }

  // Deep-link support: /dev-login?role=STUDENT mints and redirects immediately,
  // so a plain <Link href="/dev-login?role=STUDENT"> elsewhere in the app is a
  // true one-click portal launcher instead of a second manual step.
  useEffect(() => {
    if (status !== 'authenticated') return
    const requested = searchParams.get('role')
    if (!requested) return
    const portal = PORTALS.find((p) => p.role === requested)
    if (!portal) return
    handlePick(portal)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status, searchParams])

  if (status === 'loading') {
    return <div className="max-w-xl mx-auto py-16 text-center text-neutral-500">Checking your session…</div>
  }

  if (status !== 'authenticated') {
    return (
      <div className="max-w-xl mx-auto py-16 text-center space-y-3">
        <AlertTriangle className="mx-auto text-amber-500" size={32} />
        <p className="text-neutral-700">Sign in first, then come back to this page.</p>
        <a href="/login" className="inline-block px-4 py-2 rounded-lg bg-black text-white text-sm font-semibold">
          Go to login
        </a>
      </div>
    )
  }

  return (
    <div className="max-w-2xl mx-auto py-12 px-4 space-y-6">
      <div className="text-center space-y-2">
        <h1 className="text-2xl font-bold text-neutral-900">Enter a CSG Portal</h1>
        <p className="text-sm text-neutral-500">
          Dev-only bridge: mints a Keycloak-shaped token for the SMS dashboards from your current
          Learnhouse session (no real Keycloak server is deployed yet).
        </p>
      </div>

      {error && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 text-rose-700 text-sm px-4 py-3">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {PORTALS.map((portal) => {
          const Icon = portal.icon
          const isLoading = loadingRole === portal.role
          return (
            <button
              key={portal.role}
              onClick={() => handlePick(portal)}
              disabled={loadingRole !== null}
              className="text-left p-5 rounded-2xl border border-neutral-200 bg-white hover:border-blue-400 hover:shadow-md transition-all disabled:opacity-50"
            >
              <Icon className="text-blue-600 mb-2" size={24} />
              <div className="font-semibold text-neutral-900">{portal.label}</div>
              <div className="text-xs text-neutral-500 mt-1">{portal.description}</div>
              {isLoading && <div className="text-xs text-blue-600 mt-2">Signing you in…</div>}
            </button>
          )
        })}
      </div>
    </div>
  )
}

/**
 * Dev-only bridge from a real Learnhouse login (admin@csg.dev, or any
 * superadmin) into the SMS dashboard's Keycloak-shaped auth. No real
 * Keycloak server has ever been deployed for this project (see
 * lib/api/dev-token.ts), so the SMS/RevOps routers accept a locally-minted
 * dev JWT instead -- this page mints one and stores it, so testing the app
 * doesn't require opening devtools and pasting a token by hand.
 *
 * Safe by construction in any real deployment: the backend endpoint this
 * calls requires a superadmin session AND independently 404s the instant a
 * real Keycloak server is configured (src/core/keycloak_auth.py's
 * is_hmac_dev_verification_active).
 */
export default function DevLoginPage() {
  return (
    <Suspense fallback={<div className="max-w-xl mx-auto py-16 text-center text-neutral-500">Loading…</div>}>
      <DevLoginInner />
    </Suspense>
  )
}
