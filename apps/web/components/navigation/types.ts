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

export interface Campus {
  id: string
  name: string
  code: string
  city: string
  studentCount: number
  facultyCount: number
  status: 'active' | 'maintenance'
  director: string
}

export interface AcademicTerm {
  id: string
  name: string
  code: string
  academicYear: string
  startDate: string
  endDate: string
  isCurrent: boolean
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

export interface UserProfile {
  id: string
  name: string
  email: string
  avatarUrl?: string
  role: UserRole
  roleTitle: string
  campus: string
  gradeOrDept?: string
  studentId?: string
}

export const CAMPUSES: Campus[] = [
  {
    id: 'isb-main',
    name: 'CSG Islamabad Main Campus',
    code: 'ISB-01',
    city: 'Islamabad (H-8/4)',
    studentCount: 1250,
    facultyCount: 68,
    status: 'active',
    director: 'Dr. Tariq Mehmood',
  },
  {
    id: 'rwp-north',
    name: 'CSG Rawalpindi North Campus',
    code: 'RWP-02',
    city: 'Rawalpindi (Westridge)',
    studentCount: 890,
    facultyCount: 45,
    status: 'active',
    director: 'Prof. Sajjad Akhtar',
  },
  {
    id: 'lhr-gulberg',
    name: 'CSG Lahore Gulberg Campus',
    code: 'LHR-03',
    city: 'Lahore (Gulberg III)',
    studentCount: 1100,
    facultyCount: 58,
    status: 'active',
    director: 'Engr. Ayesha Malik',
  },
  {
    id: 'khi-dha',
    name: 'CSG Karachi DHA Campus',
    code: 'KHI-04',
    city: 'Karachi (DHA Phase VI)',
    studentCount: 680,
    facultyCount: 35,
    status: 'active',
    director: 'Syed Hamza Ali',
  },
]

export const ACADEMIC_TERMS: AcademicTerm[] = [
  {
    id: 'term-fall-2026',
    name: 'Term 1 - Fall 2026',
    code: 'F26-T1',
    academicYear: '2026-2027',
    startDate: '2026-08-15',
    endDate: '2026-12-20',
    isCurrent: true,
  },
  {
    id: 'term-spring-2027',
    name: 'Term 2 - Spring 2027',
    code: 'S27-T2',
    academicYear: '2026-2027',
    startDate: '2027-01-10',
    endDate: '2027-06-15',
    isCurrent: false,
  },
]

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

export const SAMPLE_USERS: Record<UserRole, UserProfile> = {
  STUDENT: {
    id: 'usr_std_101',
    name: 'Zaid Usman Khan',
    email: 'zaid.khan@student.csg.edu.pk',
    role: 'STUDENT',
    roleTitle: 'Grade 11 Student (Pre-Engineering)',
    campus: 'CSG Islamabad Main Campus',
    gradeOrDept: 'Grade 11 - Section A',
    studentId: 'CSG-2024-ISB-4921',
  },
  TEACHER: {
    id: 'usr_tch_202',
    name: 'Dr. Fatima Noor',
    email: 'fatima.noor@faculty.csg.edu.pk',
    role: 'TEACHER',
    roleTitle: 'Senior Physics & STEM Faculty',
    campus: 'CSG Islamabad Main Campus',
    gradeOrDept: 'Dept. of Physical Sciences',
  },
  PARENT: {
    id: 'usr_par_303',
    name: 'Muhammad Usman Khan',
    email: 'm.usman.khan@gmail.com',
    role: 'PARENT',
    roleTitle: 'Guardian of Zaid Khan & Amina Khan',
    campus: 'CSG Islamabad Main Campus',
    studentId: 'PAR-ISB-88301',
  },
  ADMIN: {
    id: 'usr_adm_404',
    name: 'Syed Tariq Mehmood',
    email: 'tariq.mehmood@admin.csg.edu.pk',
    role: 'ADMIN',
    roleTitle: 'Executive Director & Campus Admin',
    campus: 'CSG Islamabad Main Campus',
    gradeOrDept: 'Central Directorate',
  },
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
