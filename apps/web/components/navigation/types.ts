import React from 'react'
import {
  GraduationCap,
  Calendar,
  Clock,
  Users,
  Award,
  CreditCard,
  Building2,
  TrendingUp,
  CheckSquare,
  Layers,
  BookMarked,
  ShieldCheck,
  FolderLock,
} from 'lucide-react'

export type UserRole = 'STUDENT' | 'TEACHER' | 'PARENT' | 'ADMIN'

/**
 * Real school roles (7: SUPER_ADMIN, SCHOOL_ADMIN, TEACHER, STUDENT, PARENT,
 * STAFF, PSYCHOLOGIST -- see apps/api/src/db/sms_identity.py's SchoolRole)
 * bucketed into this UI's 4 nav personas. STAFF/PSYCHOLOGIST have no
 * dedicated portal built yet, so they fall back to STUDENT nav rather than
 * crashing on an unmapped value. Shared by `the retired `app/(dashboard)/layout.tsx`
 * (which persona is "current") and `RoleSidebar`/`PortalHeader` (which
 * personas a multi-role user can switch between).
 */
export function bucketRealmRole(realmRole: string | undefined): UserRole {
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

/**
 * Single source of truth for "which route does this persona's portal live
 * at" -- shared by `RoleSidebar` (role-switcher dropdown), `PortalHeader`
 * (quick portal switcher), and `the retired `app/(dashboard)/layout.tsx`
 * (`handleRoleChange`), which previously each hardcoded their own copy of
 * this same 4-entry map.
 */
export const ROLE_PORTAL_PATHS: Record<UserRole, string> = {
  STUDENT: '/student',
  TEACHER: '/teacher',
  PARENT: '/parent',
  ADMIN: '/campus-admin',
}

export interface NavItem {
  id: string
  title: string
  href: string
  icon: React.ElementType
  badge?: string | number
  badgeColor?: 'default' | 'success' | 'warning' | 'primary' | 'danger'
  description?: string
  /**
   * Resolved-feature key (see `src/security/features_utils/dependencies.py`
   * `FeatureName` / `src/security/features_utils/resolve.py` `ALL_FEATURES`)
   * gating this item. Undefined = always shown (e.g. the persona's home
   * page). `RoleSidebar` hides the item when the org's resolved feature is
   * explicitly disabled -- see `lib/api/org-features.ts`.
   */
  featureKey?: string
  subItems?: {
    title: string
    href: string
    badge?: string
  }[]
}

export interface NotificationItem {
  id: string
  title: string
  description: string
  timestamp: string
  read: boolean
  category: 'academic' | 'finance' | 'attendance' | 'ai_tutor' | 'system'
  priority: 'low' | 'medium' | 'high'
  actionUrl?: string
}

/**
 * Persona navigation per DESIGN-SYSTEM.md §2.3 ("Navigation IA per persona"),
 * adapted to the routes that actually exist in this app. Items carry
 * `featureKey` where a real SMS module backs them so `RoleSidebar` can hide
 * a disabled module's entry per that same section ("Modules hidden by
 * feature flag or RBAC are removed from navigation, not disabled").
 *
 * `Admissions CRM` (revops), the course/lesson player, and the live
 * classroom are owned by a separate in-flight AI RevOps/Tutor workstream
 * (see AGENT scope boundary) -- their nav entries stay untouched/linked so
 * that work remains reachable, but this file doesn't add new mock content
 * for them.
 */
export const ROLE_NAV_ITEMS: Record<UserRole, NavItem[]> = {
  STUDENT: [
    {
      id: 'student-home',
      title: 'Home',
      href: '/student',
      icon: GraduationCap,
      description: 'Overview, today at a glance',
    },
    {
      id: 'student-timetable',
      title: 'Timetable',
      href: '/student#timetable',
      icon: Clock,
      featureKey: 'sms_timetable',
    },
    {
      id: 'student-attendance',
      title: 'Attendance',
      href: '/student#attendance',
      icon: CheckSquare,
      featureKey: 'sms_attendance',
    },
    {
      id: 'student-grades',
      title: 'Grades',
      href: '/student#grades',
      icon: Award,
      featureKey: 'sms_gradebook',
    },
    {
      id: 'student-library',
      title: 'Library',
      href: '/student#library',
      icon: BookMarked,
      featureKey: 'sms_library',
    },
  ],
  TEACHER: [
    {
      id: 'teacher-today',
      title: 'Today',
      href: '/teacher',
      icon: Layers,
      description: "Today's classes at a glance",
    },
    {
      id: 'teacher-timetable',
      title: 'Classes',
      href: '/teacher#timetable',
      icon: Clock,
      featureKey: 'sms_timetable',
    },
    {
      id: 'teacher-gradebook',
      title: 'Gradebook',
      href: '/teacher#gradebook',
      icon: Award,
      featureKey: 'sms_gradebook',
    },
    {
      id: 'teacher-attendance',
      title: 'Attendance',
      href: '/teacher#attendance',
      icon: CheckSquare,
      featureKey: 'sms_attendance',
    },
  ],
  PARENT: [
    {
      id: 'parent-home',
      title: 'Home',
      href: '/parent',
      icon: Users,
      description: "Children's progress at a glance",
    },
    {
      id: 'parent-attendance',
      title: 'My Children',
      href: '/parent#attendance',
      icon: Calendar,
      featureKey: 'sms_attendance',
    },
    {
      id: 'parent-fees',
      title: 'Fees',
      href: '/parent/fees',
      icon: CreditCard,
      featureKey: 'sms_fees',
    },
    {
      id: 'parent-performance',
      title: 'Grades',
      href: '/parent#performance',
      icon: TrendingUp,
      featureKey: 'sms_gradebook',
    },
  ],
  ADMIN: [
    {
      id: 'admin-dashboard',
      title: 'Dashboard',
      href: '/campus-admin',
      icon: ShieldCheck,
      description: 'Campuses, finance & staff at a glance',
    },
    {
      id: 'admin-admissions-crm',
      title: 'Admissions',
      href: '/admissions/crm',
      icon: Users,
      featureKey: 'revops',
      description: 'Kanban pipeline & SDR RevOps bot',
    },
    {
      id: 'admin-finance',
      title: 'Finance',
      href: '/campus-admin#finance',
      icon: CreditCard,
      featureKey: 'sms_fees',
    },
    {
      id: 'admin-people',
      title: 'People',
      href: '/campus-admin#people',
      icon: FolderLock,
      featureKey: 'sms_hr_payroll',
    },
    {
      id: 'admin-campuses',
      title: 'Campuses',
      href: '/campus-admin#campuses',
      icon: Building2,
    },
  ],
}

export const INITIAL_NOTIFICATIONS: NotificationItem[] = [
  {
    id: 'notif-1',
    title: 'New AI Weekly Summary Generated',
    description: 'Weekly AI learning analysis for Term 1 Week 4 is ready to review.',
    timestamp: '10 minutes ago',
    read: false,
    category: 'ai_tutor',
    priority: 'medium',
    actionUrl: '/parent#ai-report',
  },
  {
    id: 'notif-2',
    title: 'September Fee Voucher Issued',
    description: 'Voucher #CSG-2026-09-8839 is now available for download and online payment.',
    timestamp: '2 hours ago',
    read: false,
    category: 'finance',
    priority: 'high',
    actionUrl: '/parent#fees',
  },
  {
    id: 'notif-3',
    title: 'Physics Lab Test Graded',
    description: 'Dr. Fatima Noor published marks for Experiment 3: Modern Optics (Score: 28/30).',
    timestamp: '5 hours ago',
    read: true,
    category: 'academic',
    priority: 'low',
    actionUrl: '/student#grades',
  },
  {
    id: 'notif-4',
    title: 'Automated Attendance Alert',
    description: 'Grade 11-A morning roll call finalized: 96.4% present rate recorded.',
    timestamp: 'Yesterday at 09:15 AM',
    read: true,
    category: 'attendance',
    priority: 'low',
    actionUrl: '/teacher#rollcall',
  },
]
