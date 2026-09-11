'use client'

import React, { useState, useMemo } from 'react'
import { usePathname, useRouter } from 'next/navigation'
import { RoleSidebar } from '@/components/navigation/RoleSidebar'
import { PortalHeader } from '@/components/navigation/PortalHeader'
import { UserRole, Campus, AcademicTerm, CAMPUSES, ACADEMIC_TERMS } from '@/components/navigation/types'
import Toast from '@/components/Objects/StyledElements/Toast/Toast'

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const pathname = usePathname()
  const router = useRouter()
  const [isMobileOpen, setIsMobileOpen] = useState(false)
  const [isCollapsed, setIsCollapsed] = useState(false)
  const [activeCampus, setActiveCampus] = useState<Campus>(CAMPUSES[0])
  const [activeTerm, setActiveTerm] = useState<AcademicTerm>(ACADEMIC_TERMS[0])

  // Derive active role from current URL path
  const currentRole = useMemo<UserRole>(() => {
    if (pathname.startsWith('/teacher')) return 'TEACHER'
    if (pathname.startsWith('/parent')) return 'PARENT'
    if (pathname.startsWith('/admin')) return 'ADMIN'
    return 'STUDENT'
  }, [pathname])

  const handleRoleChange = (newRole: UserRole) => {
    const roleRoutes: Record<UserRole, string> = {
      STUDENT: '/student',
      TEACHER: '/teacher',
      PARENT: '/parent',
      ADMIN: '/admin',
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
