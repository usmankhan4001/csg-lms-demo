import React from 'react'
import {
  GraduationCap,
  BookOpen,
  Calendar,
  Clock,
  Sparkles,
  CheckCircle2,
  Users,
  Award,
  CreditCard,
  Building2,
  TrendingUp,
  Activity,
  FileText,
  CheckSquare,
  Layers,
  Settings,
  Bell,
  User,
  BrainCircuit,
  MessageSquare,
  BarChart3,
  BookMarked,
  ShieldCheck,
  FolderLock,
  Compass,
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

export const ROLE_NAV_ITEMS: Record<UserRole, NavItem[]> = {
  STUDENT: [
    {
      id: 'student-dashboard',
      title: 'Student Dashboard',
      href: '/student',
      icon: GraduationCap,
      description: 'Overview, timetable, active courses',
    },
    {
      id: 'student-timetable',
      title: 'Timetable & Schedule',
      href: '/student#timetable',
      icon: Clock,
      badge: 'Today',
      badgeColor: 'primary',
    },
    {
      id: 'student-courses',
      title: 'Active Courses',
      href: '/student#courses',
      icon: BookOpen,
      badge: 6,
    },
    {
      id: 'student-ai-tutor',
      title: 'Socratic AI Tutor',
      href: '/student#ai-tutor',
      icon: BrainCircuit,
      badge: 'AI Powered',
      badgeColor: 'success',
    },
    {
      id: 'student-attendance',
      title: 'Attendance Record',
      href: '/student#attendance',
      icon: CheckSquare,
      badge: '96.4%',
      badgeColor: 'success',
    },
    {
      id: 'student-grades',
      title: 'Grades & Report Card',
      href: '/student#grades',
      icon: Award,
    },
    {
      id: 'student-library',
      title: 'Digital Library & Notes',
      href: '/student#library',
      icon: BookMarked,
    },
  ],
  TEACHER: [
    {
      id: 'teacher-hub',
      title: 'Classroom Hub',
      href: '/teacher',
      icon: Layers,
      description: 'Active classes, attendance & gradebook',
    },
    {
      id: 'teacher-rollcall',
      title: '1-Click Roll-Call',
      href: '/teacher#rollcall',
      icon: CheckSquare,
      badge: 'Quick Action',
      badgeColor: 'warning',
    },
    {
      id: 'teacher-classes',
      title: 'My Classes Today',
      href: '/teacher#classes',
      icon: Users,
      badge: 4,
    },
    {
      id: 'teacher-gradebook',
      title: 'Gradebook & Marking',
      href: '/teacher#gradebook',
      icon: Award,
      badge: '14 Pending',
      badgeColor: 'danger',
    },
    {
      id: 'teacher-courses',
      title: 'Course & Lesson Editor',
      href: '/teacher#editor',
      icon: BookOpen,
    },
    {
      id: 'teacher-announcements',
      title: 'Announcements & SMS',
      href: '/teacher#announcements',
      icon: MessageSquare,
    },
    {
      id: 'teacher-analytics',
      title: 'Class Analytics',
      href: '/teacher#analytics',
      icon: BarChart3,
    },
  ],
  PARENT: [
    {
      id: 'parent-portal',
      title: 'Parent Portal',
      href: '/parent',
      icon: Users,
      description: 'Children progress, attendance & fees',
    },
    {
      id: 'parent-attendance',
      title: 'Attendance Calendar',
      href: '/parent#attendance',
      icon: Calendar,
      badge: 'Live',
      badgeColor: 'success',
    },
    {
      id: 'parent-fees',
      title: 'Fee Vouchers & Bills',
      href: '/parent/fees',
      icon: CreditCard,
      badge: 'Due in 12d',
      badgeColor: 'warning',
    },
    {
      id: 'parent-ai-report',
      title: 'Weekly AI Summary',
      href: '/parent#ai-report',
      icon: Sparkles,
      badge: 'New',
      badgeColor: 'primary',
    },
    {
      id: 'parent-academic',
      title: 'Performance & Tests',
      href: '/parent#performance',
      icon: TrendingUp,
    },
    {
      id: 'parent-messages',
      title: 'Teacher Communications',
      href: '/parent#communications',
      icon: MessageSquare,
      badge: 2,
    },
  ],
  ADMIN: [
    {
      id: 'admin-console',
      title: 'Admin Console',
      href: '/admin',
      icon: ShieldCheck,
      description: 'Campuses, admissions, finance & health',
    },
    {
      id: 'admin-admissions-crm',
      title: 'Admissions CRM & SDR',
      href: '/admin/admissions/crm',
      icon: Users,
      badge: '540 Leads',
      badgeColor: 'primary',
      description: 'Kanban pipeline & SDR RevOps bot',
    },
    {
      id: 'admin-campuses',
      title: 'Campus Manager',
      href: '/admin#campuses',
      icon: Building2,
      badge: '4 Campuses',
    },
    {
      id: 'admin-finance',
      title: 'Fee Collection & KPIs',
      href: '/admin#finance',
      icon: CreditCard,
      badge: '88.4%',
      badgeColor: 'success',
    },
    {
      id: 'admin-health',
      title: 'System Health & Logs',
      href: '/admin#health',
      icon: Activity,
      badge: '99.98%',
      badgeColor: 'success',
    },
    {
      id: 'admin-faculty',
      title: 'Staff & HR Directory',
      href: '/admin#faculty',
      icon: FolderLock,
    },
    {
      id: 'admin-settings',
      title: 'System Settings',
      href: '/admin#settings',
      icon: Settings,
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
