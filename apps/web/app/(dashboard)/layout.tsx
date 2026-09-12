'use client'

import React, { useState, useMemo } from 'react'
import { usePathname, useRouter } from 'next/navigation'
import { RoleSidebar } from '@/components/navigation/RoleSidebar'
import { PortalHeader } from '@/components/navigation/PortalHeader'
import { UserRole, Campus, AcademicTerm, CAMPUSES, ACADEMIC_TERMS } from '@/components/navigation/types'
import Toast from '@/components/Objects/StyledElements/Toast/Toast'
import { useDevSession } from '@/lib/api/useDevSession'

// Real Keycloak realm roles (7: SUPER_ADMIN, SCHOOL_ADMIN, TEACHER, STUDENT,
// PARENT, STAFF, PSYCHOLOGIST -- see src/core/keycloak_auth.py) bucketed
// into this UI's 4 nav personas. STAFF/PSYCHOLOGIST have no dedicated portal
// built yet (same as web's own scope), so they fall back to STUDENT nav
// rather than crashing on an unmapped value.
function bucketRealmRole(realmRole: string | undefined): UserRole {
  switch (realmRole) {
    case 'SCHOOL_ADMIN':
    case 'SUPER_ADMIN':
      return 'ADMIN'
    case 'TEACHER':
      return 'TEACHER'
    case 'PARENT':
      return 'PARENT'
    default:
      return 'STUDENT'
  }
}

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const pathname = usePathname()
  const router = useRouter()
  const { session, checked } = useDevSession()
  const [isMobileOpen, setIsMobileOpen] = useState(false)
  const [isCollapsed, setIsCollapsed] = useState(false)
  const [activeCampus, setActiveCampus] = useState<Campus>(CAMPUSES[0])
  const [activeTerm, setActiveTerm] = useState<AcademicTerm>(ACADEMIC_TERMS[0])

  // Path-derived guess, used only until the real session is checked (avoids
  // a hydration mismatch, since useDevSession() intentionally reads
  // localStorage after mount, not during render).
  const pathRole = useMemo<UserRole>(() => {
    if (pathname.startsWith('/teacher')) return 'TEACHER'
    if (pathname.startsWith('/parent')) return 'PARENT'
    if (pathname.startsWith('/campus-admin')) return 'ADMIN'
    return 'STUDENT'
  }, [pathname])

  // Once the real Keycloak dev session is known, it is authoritative --
  // NOT the URL. Bug this replaces: the previous path-only check tested
  // `pathname.startsWith('/admin')`, but the real route is `/campus-admin`,
  // so it never matched and every visitor saw STUDENT nav regardless of
  // their actual role or token.
  const currentRole = useMemo<UserRole>(() => {
    if (checked && session) return bucketRealmRole(session.realm_access?.roles?.[0])
    return pathRole
  }, [checked, session, pathRole])

  const handleRoleChange = (newRole: UserRole) => {
    const roleRoutes: Record<UserRole, string> = {
      STUDENT: '/student',
      TEACHER: '/teacher',
      PARENT: '/parent',
      ADMIN: '/campus-admin',
    }
    router.push(roleRoutes[newRole])
  }

  return (
    <div className="min-h-screen bg-neutral-50/60 dark:bg-neutral-950 text-neutral-900 dark:text-neutral-100 flex flex-col md:flex-row antialiased">
      {/* Background-action confirmations (DESIGN-SYSTEM.md §7 Feedback: toast for background results). */}
      <Toast />

      {/* Dynamic Role Sidebar */}
      <RoleSidebar
        currentRole={currentRole}
        onRoleChange={handleRoleChange}
        isMobileOpen={isMobileOpen}
        onMobileClose={() => setIsMobileOpen(false)}
        isCollapsed={isCollapsed}
        onToggleCollapse={() => setIsCollapsed(!isCollapsed)}
      />

      {/* Main App Container */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Global Portal Header */}
        <PortalHeader
          currentRole={currentRole}
          onRoleChange={handleRoleChange}
          onToggleMobileSidebar={() => setIsMobileOpen(true)}
          activeCampus={activeCampus}
          onCampusChange={setActiveCampus}
          activeTerm={activeTerm}
          onTermChange={setActiveTerm}
        />

        {/* Dynamic Role Portal Content Area */}
        <main className="flex-1 p-4 md:p-6 lg:p-8 max-w-7xl w-full mx-auto animate-fade-in focus:outline-hidden">
          {children}
        </main>
      </div>
    </div>
  )
}
