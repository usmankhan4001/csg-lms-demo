/**
 * CSG-EMS (Autonomous Education Operating System)
 * Role-Based Access Control (RBAC) & Fine-Grained Permission System
 */

'use client'

import { useMemo } from 'react'
import { useSchoolSession } from '@/lib/api/useSchoolSession'

/**
 * Standard resource domains across the education operating system.
 */
export type ResourceDomain =
  | 'admissions'
  | 'attendance'
  | 'timetable'
  | 'gradebook'
  | 'exams'
  | 'school-library'
  | 'fees'
  | 'reports'
  | 'counseling'
  | 'gamification'
  | 'certificates'
  | 'pathways'
  | 'discipline'
  | 'alumni'
  | 'revops'
  | 'school-settings'
  | 'people'
  | 'roles'
  | 'finance'
  | 'academics'
  | 'communication'
  | (string & {})

/**
 * Granular actions executable on resource domains.
 */
export type PermissionAction =
  | 'read'
  | 'create'
  | 'update'
  | 'delete'
  | 'approve'
  | 'export'

/**
 * Hierarchical Scope Levels for data segmentation.
 */
export type ScopeLevel =
  | 'all'          // Cross-organization / Global
  | 'campus'       // Campus-wide constraint
  | 'department'   // Departmental constraint (e.g. Science, Maths)
  | 'own_section'  // Assigned classroom / section
  | 'own_only'     // Self-authored records only

export interface ScopeDefinition {
  level: ScopeLevel
  label: string
  description: string
}

export const SCOPE_DEFINITIONS: ScopeDefinition[] = [
  { level: 'all', label: 'All (Organization)', description: 'Full access across all campuses, departments and sections' },
  { level: 'campus', label: 'Campus', description: 'Restricted to records belonging to assigned campus' },
  { level: 'department', label: 'Department', description: 'Restricted to department/faculty scope' },
  { level: 'own_section', label: 'Own Section', description: 'Restricted to assigned classes and sections' },
  { level: 'own_only', label: 'Own Only', description: 'Restricted to self-created or directly assigned personal records' },
]

export interface ResourceDomainMeta {
  key: ResourceDomain
  label: string
  category: 'Academics' | 'Administration' | 'Operations' | 'Student Services' | 'Settings'
  description: string
}

export const RESOURCE_DOMAINS: ResourceDomainMeta[] = [
  { key: 'admissions', label: 'Admissions & Leads', category: 'Student Services', description: 'Application pipeline, inquiries, enrollment verification' },
  { key: 'attendance', label: 'Attendance & Rolls', category: 'Academics', description: 'Class roll-calls, absence notes, at-risk pastoral monitoring' },
  { key: 'timetable', label: 'Timetable & Scheduling', category: 'Academics', description: 'Schedules, period slots, clash resolution, room assignments' },
  { key: 'gradebook', label: 'Gradebook & Marks', category: 'Academics', description: 'Assessment scores, report card publishing, transcript generation' },
  { key: 'exams', label: 'Exams & Sittings', category: 'Academics', description: 'Exam hall seating, invigilation rosters, incident management' },
  { key: 'fees', label: 'Fee Management & Arrears', category: 'Operations', description: 'Voucher generation, bank reconciliation, payment reminders' },
  { key: 'school-library', label: 'Library Catalogue', category: 'Operations', description: 'Book inventory, loans, reservations, fines' },
  { key: 'counseling', label: 'Pastoral & Counseling', category: 'Student Services', description: 'Confidential psychological notes, career counseling sessions' },
  { key: 'discipline', label: 'Discipline & Conduct', category: 'Student Services', description: 'Behavior incidents, restorative actions, sanctions' },
  { key: 'reports', label: 'Cross-Module Reports', category: 'Administration', description: 'Executive analytics, enrollment trends, academic KPIs' },
  { key: 'gamification', label: 'Badges & Recognition', category: 'Student Services', description: 'Student merits, engagement badges, leaderboards' },
  { key: 'certificates', label: 'Certificates & Credentials', category: 'Administration', description: 'Certificate issuance, diploma templates, verification' },
  { key: 'pathways', label: 'Learning Pathways', category: 'Academics', description: 'Curriculum milestones, prerequisites, student tracks' },
  { key: 'alumni', label: 'Alumni Network', category: 'Student Services', description: 'Graduate directory, post-graduation achievements' },
  { key: 'revops', label: 'AI RevOps & Agents', category: 'Administration', description: 'School AI agent configuration, knowledge base indexing' },
  { key: 'people', label: 'People & Directory', category: 'Settings', description: 'Account provisioning, teacher/student/parent invitations' },
  { key: 'roles', label: 'Roles & Permissions (RBAC)', category: 'Settings', description: 'Custom role matrix definitions and scope assignments' },
  { key: 'school-settings', label: 'General School Settings', category: 'Settings', description: 'Academic years, campuses, grading scales, terms' },
]

/**
 * Individual Rule for a specific resource domain in a role.
 */
export interface EMSPermissionRule {
  resource: ResourceDomain
  actions: {
    read?: boolean
    create?: boolean
    update?: boolean
    delete?: boolean
    approve?: boolean
    export?: boolean
  }
  scope: ScopeLevel
  customConditions?: Record<string, any>
}

/**
 * Complete Role Definition.
 */
export interface EMSRole {
  id: string
  name: string
  code: string
  description: string
  isSystem: boolean
  inheritsFrom?: string
  permissions: EMSPermissionRule[]
  created_at?: string
  updated_at?: string
}

/**
 * User Role Assignment binding a user to a role under specific organizational constraints.
 */
export interface EMSUserRoleAssignment {
  id?: string | number
  userId: number
  userName?: string
  userEmail?: string
  roleId: string
  roleCode?: string
  roleName?: string
  campusId?: number | null
  campusName?: string
  departmentId?: string | number | null
  departmentName?: string
  sectionId?: number | null
  sectionName?: string
  academicYearId?: number | null
  assignedAt?: string
  expiresAt?: string | null
  isActive?: boolean
}

/**
 * Dynamic context passed during permission checks.
 */
export interface EMSPermissionContext {
  campusId?: number | null
  departmentId?: string | number | null
  sectionId?: number | null
  ownerId?: number | null
  recordId?: string | number | null
}

/**
 * Lightweight representation of user context.
 */
export interface EMSUserContext {
  id?: number
  user_id?: number
  roles?: string[]
  assignments?: EMSUserRoleAssignment[]
  noSchoolRole?: boolean
}

/**
 * Default System Role Templates.
 */
export const SYSTEM_ROLE_TEMPLATES: EMSRole[] = [
  {
    id: 'sys-super-admin',
    name: 'Super Administrator',
    code: 'SUPER_ADMIN',
    description: 'Unrestricted full access across all campuses, settings, and domains.',
    isSystem: true,
    permissions: RESOURCE_DOMAINS.map((domain) => ({
      resource: domain.key,
      actions: { read: true, create: true, update: true, delete: true, approve: true, export: true },
      scope: 'all',
    })),
  },
  {
    id: 'sys-school-admin',
    name: 'School Administrator',
    code: 'SCHOOL_ADMIN',
    description: 'Full administrative control over campus operations, academics, and staff.',
    isSystem: true,
    permissions: RESOURCE_DOMAINS.map((domain) => ({
      resource: domain.key,
      actions: {
        read: true,
        create: true,
        update: true,
        delete: domain.key !== 'school-settings',
        approve: true,
        export: true,
      },
      scope: 'campus',
    })),
  },
  {
    id: 'sys-teacher',
    name: 'Teacher / Faculty',
    code: 'TEACHER',
    description: 'Manages class rosters, takes attendance, grades assessments, and views curriculum.',
    isSystem: true,
    permissions: [
      {
        resource: 'attendance',
        actions: { read: true, create: true, update: true, delete: false, approve: false, export: true },
        scope: 'own_section',
      },
      {
        resource: 'gradebook',
        actions: { read: true, create: true, update: true, delete: false, approve: false, export: true },
        scope: 'own_section',
      },
      {
        resource: 'timetable',
        actions: { read: true, create: false, update: false, delete: false, approve: false, export: false },
        scope: 'campus',
      },
      {
        resource: 'exams',
        actions: { read: true, create: false, update: false, delete: false, approve: false, export: false },
        scope: 'campus',
      },
      {
        resource: 'discipline',
        actions: { read: true, create: true, update: true, delete: false, approve: false, export: false },
        scope: 'campus',
      },
      {
        resource: 'gamification',
        actions: { read: true, create: true, update: true, delete: false, approve: false, export: false },
        scope: 'own_section',
      },
      {
        resource: 'school-library',
        actions: { read: true, create: false, update: false, delete: false, approve: false, export: false },
        scope: 'campus',
      },
    ],
  },
  {
    id: 'sys-student',
    name: 'Student',
    code: 'STUDENT',
    description: 'Enrolled learner access to timetables, coursework, grade reports, and library.',
    isSystem: true,
    permissions: [
      {
        resource: 'attendance',
        actions: { read: true, create: false, update: false, delete: false, approve: false, export: false },
        scope: 'own_only',
      },
      {
        resource: 'gradebook',
        actions: { read: true, create: false, update: false, delete: false, approve: false, export: false },
        scope: 'own_only',
      },
      {
        resource: 'timetable',
        actions: { read: true, create: false, update: false, delete: false, approve: false, export: false },
        scope: 'own_section',
      },
      {
        resource: 'school-library',
        actions: { read: true, create: false, update: false, delete: false, approve: false, export: false },
        scope: 'campus',
      },
      {
        resource: 'gamification',
        actions: { read: true, create: false, update: false, delete: false, approve: false, export: false },
        scope: 'own_only',
      },
    ],
  },
  {
    id: 'sys-parent',
    name: 'Parent / Guardian',
    code: 'PARENT',
    description: 'View ward attendance, term reports, fee arrears, and school announcements.',
    isSystem: true,
    permissions: [
      {
        resource: 'attendance',
        actions: { read: true, create: false, update: false, delete: false, approve: false, export: false },
        scope: 'own_only',
      },
      {
        resource: 'gradebook',
        actions: { read: true, create: false, update: false, delete: false, approve: false, export: false },
        scope: 'own_only',
      },
      {
        resource: 'fees',
        actions: { read: true, create: false, update: false, delete: false, approve: false, export: false },
        scope: 'own_only',
      },
      {
        resource: 'timetable',
        actions: { read: true, create: false, update: false, delete: false, approve: false, export: false },
        scope: 'own_only',
      },
    ],
  },
  {
    id: 'sys-psychologist',
    name: 'Counselor / Psychologist',
    code: 'PSYCHOLOGIST',
    description: 'Confidential pastoral guidance, mental health records, and career sessions.',
    isSystem: true,
    permissions: [
      {
        resource: 'counseling',
        actions: { read: true, create: true, update: true, delete: true, approve: true, export: true },
        scope: 'campus',
      },
      {
        resource: 'attendance',
        actions: { read: true, create: false, update: false, delete: false, approve: false, export: false },
        scope: 'campus',
      },
      {
        resource: 'discipline',
        actions: { read: true, create: false, update: false, delete: false, approve: false, export: false },
        scope: 'campus',
      },
    ],
  },
  {
    id: 'sys-bursar',
    name: 'Bursar / Accountant',
    code: 'BURSAR',
    description: 'Manages student fee billing, reconciliation, vouchers, and financial reports.',
    isSystem: false,
    permissions: [
      {
        resource: 'fees',
        actions: { read: true, create: true, update: true, delete: true, approve: true, export: true },
        scope: 'campus',
      },
      {
        resource: 'reports',
        actions: { read: true, create: false, update: false, delete: false, approve: false, export: true },
        scope: 'campus',
      },
    ],
  },
]

/**
 * Core Permission Evaluation Function.
 * Evaluates whether a user can perform an action on a given resourceDomain under a given context.
 */
export function hasPermission(
  user: EMSUserContext | null | undefined,
  resourceKey: ResourceDomain,
  action: PermissionAction = 'read',
  context?: EMSPermissionContext,
  customRoles: EMSRole[] = SYSTEM_ROLE_TEMPLATES
): boolean {
  if (!user) return false

  const userRoles = user.roles ?? []
  const userId = user.id ?? user.user_id

  // 1. Super Admin or unconstrained Org Admin (setup mode) has unconditional bypass
  if (userRoles.includes('SUPER_ADMIN') || user.noSchoolRole) {
    return true
  }

  // 2. School Admin has full campus access
  if (userRoles.includes('SCHOOL_ADMIN')) {
    if (!context?.campusId) return true
    // If context specifies a campus, check if matches or user is admin
    return true
  }

  // 3. Evaluate through assigned roles or role list
  const activeRoleCodes = new Set<string>(userRoles)
  const assignments = user.assignments?.filter((a) => a.isActive !== false) ?? []

  // Add role codes from active assignments
  assignments.forEach((a) => {
    if (a.roleCode) activeRoleCodes.add(a.roleCode)
  })

  // Look up matching role definitions
  const candidateRoles = customRoles.filter(
    (r) => activeRoleCodes.has(r.code) || assignments.some((a) => a.roleId === r.id)
  )

  for (const role of candidateRoles) {
    const rule = role.permissions.find((p) => p.resource === resourceKey)
    if (!rule) continue

    // Check if the specific action is permitted
    if (!rule.actions[action]) continue

    // Validate scope constraint
    const scope = rule.scope

    if (scope === 'all') {
      return true
    }

    if (scope === 'campus') {
      if (!context?.campusId) return true
      const matchingAssignment = assignments.find((a) => a.roleId === role.id || a.roleCode === role.code)
      if (!matchingAssignment || !matchingAssignment.campusId || matchingAssignment.campusId === context.campusId) {
        return true
      }
    }

    if (scope === 'department') {
      if (!context?.departmentId) return true
      const matchingAssignment = assignments.find((a) => a.roleId === role.id || a.roleCode === role.code)
      if (!matchingAssignment || !matchingAssignment.departmentId || matchingAssignment.departmentId === context.departmentId) {
        return true
      }
    }

    if (scope === 'own_section') {
      if (!context?.sectionId) return true
      const matchingAssignment = assignments.find((a) => a.roleId === role.id || a.roleCode === role.code)
      if (!matchingAssignment || !matchingAssignment.sectionId || matchingAssignment.sectionId === context.sectionId) {
        return true
      }
    }

    if (scope === 'own_only') {
      if (!context?.ownerId && userId) return true
      if (context?.ownerId && userId && context.ownerId === userId) {
        return true
      }
    }
  }

  return false
}

export interface UseEMSPermissionResult {
  allowed: boolean
  scope: ScopeLevel | null
  isSuperAdmin: boolean
  roles: string[]
}

/**
 * React Hook for fine-grained EMS Permission checks in client components.
 */
export function useEMSPermission(
  resourceKey: ResourceDomain,
  action: PermissionAction = 'read',
  context?: EMSPermissionContext,
  customRoles?: EMSRole[]
): UseEMSPermissionResult {
  const { session } = useSchoolSession()

  return useMemo(() => {
    const roles = session?.roles ?? []
    const isSuperAdmin = roles.includes('SUPER_ADMIN') || (!roles.length && true)

    const userId = session?.staff_id ?? session?.student_id ?? null
    const userContext: EMSUserContext = {
      user_id: userId ?? undefined,
      id: userId ?? undefined,
      roles: session?.roles,
      noSchoolRole: !roles.length,
      assignments: session?.campus_id
        ? [
            {
              userId: userId ?? 0,
              roleId: roles[0] ?? 'GUEST',
              roleCode: roles[0] ?? 'GUEST',
              campusId: session.campus_id,
              sectionId: session.section_id,
              isActive: true,
            },
          ]
        : [],
    }

    const effectiveRoles = customRoles ?? SYSTEM_ROLE_TEMPLATES
    const allowed = hasPermission(userContext, resourceKey, action, context, effectiveRoles)

    // Find highest matching scope
    let matchedScope: ScopeLevel | null = null
    if (isSuperAdmin) {
      matchedScope = 'all'
    } else {
      for (const r of effectiveRoles) {
        if (roles.includes(r.code)) {
          const rule = r.permissions.find((p) => p.resource === resourceKey && p.actions[action])
          if (rule) {
            matchedScope = rule.scope
            break
          }
        }
      }
    }

    return {
      allowed,
      scope: matchedScope,
      isSuperAdmin,
      roles,
    }
  }, [session, resourceKey, action, context, customRoles])
}
