'use client'

import React, { useState } from 'react'
import {
  Shield,
  UserCheck,
  UserPlus,
  Users,
  Trash2,
  Search,
  Filter,
  AlertCircle,
  CheckCircle2,
  RefreshCw,
} from 'lucide-react'
import {
  DashPageShell,
  LH_INPUT,
  LH_PRIMARY_BUTTON,
  LH_SECONDARY_BUTTON,
  SchoolDialog,
  SchoolField,
  SectionCard,
  StatusChip,
} from '@/components/widgets'
import { useApiResource } from '@/lib/api/useApiResource'
import { useSchoolSession } from '@/lib/api/useSchoolSession'
import {
  assignSchoolRole,
  listGuardianLinks,
  listSchoolPeople,
  listSchoolRoles,
  revokeSchoolRole,
} from '../api'
import type { SchoolPerson, SchoolRoleType, SMSUserRoleRecord } from '../types'

const ALL_ROLES: { key: SchoolRoleType; label: string; desc: string }[] = [
  { key: 'TEACHER', label: 'Teacher', desc: 'Can take roll call, enter grades, host live classes' },
  { key: 'STUDENT', label: 'Student', desc: 'Can attend classes, view timetable, take assignments' },
  { key: 'PARENT', label: 'Parent / Guardian', desc: 'Can view children grades, attendance, and pay fees' },
  { key: 'SCHOOL_ADMIN', label: 'School Admin', desc: 'Manages school settings, timetables, and enrollments' },
  { key: 'STAFF', label: 'Staff Member', desc: 'Operational and administrative school staff' },
  { key: 'PSYCHOLOGIST', label: 'Counselor / Psychologist', desc: 'Access to student pastoral and counseling notes' },
  { key: 'SUPER_ADMIN', label: 'Super Admin', desc: 'Full cross-organization platform control' },
]

export function RoleManagementPanel({ orgId }: { orgId: number }) {
  const { session } = useSchoolSession()
  const [selectedRole, setSelectedRole] = useState<SchoolRoleType>('TEACHER')
  const [searchQuery, setSearchQuery] = useState('')
  const [reloadKey, setReloadKey] = useState(0)

  // Dialog State
  const [isAssignOpen, setIsAssignOpen] = useState(false)
  const [targetUserId, setTargetUserId] = useState<string>('')
  const [assignRoleType, setAssignRoleType] = useState<SchoolRoleType>('TEACHER')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [actionMessage, setActionMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  // Fetch users for selected role
  const peopleResource = useApiResource(
    () => listSchoolPeople(selectedRole, session?.campus_id ?? undefined),
    [selectedRole, session?.campus_id, reloadKey]
  )

  const people = peopleResource.data ?? []
  const filteredPeople = people.filter(
    (p) =>
      (p.name && p.name.toLowerCase().includes(searchQuery.toLowerCase())) ||
      (p.email && p.email.toLowerCase().includes(searchQuery.toLowerCase())) ||
      String(p.user_id).includes(searchQuery)
  )

  const handleAssign = async (e: React.FormEvent) => {
    e.preventDefault()
    const uid = parseInt(targetUserId.trim(), 10)
    if (isNaN(uid) || uid <= 0) {
      setActionMessage({ type: 'error', text: 'Please enter a valid numeric User ID' })
      return
    }

    setIsSubmitting(true)
    setActionMessage(null)
    try {
      await assignSchoolRole({
        user_id: uid,
        org_id: orgId,
        campus_id: session?.campus_id ?? undefined,
        role: assignRoleType,
      })
      setActionMessage({ type: 'success', text: `Successfully granted ${assignRoleType} role to User #${uid}` })
      setIsAssignOpen(false)
      setTargetUserId('')
      setReloadKey((k) => k + 1)
    } catch (err: any) {
      setActionMessage({ type: 'error', text: err?.message || 'Failed to assign role. Ensure user exists.' })
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="space-y-6">
      {actionMessage && (
        <div
          className={`flex items-center gap-3 p-4 rounded-xl text-sm font-medium ${
            actionMessage.type === 'success'
              ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
              : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
          }`}
        >
          {actionMessage.type === 'success' ? (
            <CheckCircle2 className="w-5 h-5 flex-shrink-0" />
          ) : (
            <AlertCircle className="w-5 h-5 flex-shrink-0" />
          )}
          <span>{actionMessage.text}</span>
        </div>
      )}

      {/* Role Selector Tabs */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2">
        {ALL_ROLES.map((r) => (
          <button
            key={r.key}
            onClick={() => setSelectedRole(r.key)}
            className={`flex flex-col items-start p-3 rounded-xl border text-left transition-all ${
              selectedRole === r.key
                ? 'bg-primary/10 border-primary text-primary shadow-sm ring-1 ring-primary/20'
                : 'bg-card/50 border-border/40 hover:bg-muted/40 text-muted-foreground'
            }`}
          >
            <span className="text-xs font-semibold">{r.label}</span>
            <span className="text-[10px] text-muted-foreground line-clamp-1 mt-0.5">{r.key}</span>
          </button>
        ))}
      </div>

      {/* Action Header & Search */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="relative w-full sm:w-80">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            placeholder={`Search ${selectedRole.toLowerCase()}s by name, email, or ID...`}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className={`${LH_INPUT} pl-9 h-10`}
          />
        </div>

        <div className="flex items-center gap-2 w-full sm:w-auto">
          <button
            onClick={() => setReloadKey((k) => k + 1)}
            className={`${LH_SECONDARY_BUTTON} gap-2 h-10 px-3`}
            title="Refresh list"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
          <button
            onClick={() => {
              setAssignRoleType(selectedRole)
              setIsAssignOpen(true)
            }}
            className={`${LH_PRIMARY_BUTTON} gap-2 h-10 px-4 w-full sm:w-auto`}
          >
            <UserPlus className="w-4 h-4" />
            <span>Assign {ALL_ROLES.find((r) => r.key === selectedRole)?.label ?? 'Role'}</span>
          </button>
        </div>
      </div>

      {/* People Table */}
      <SectionCard
        title={`${ALL_ROLES.find((r) => r.key === selectedRole)?.label} Directory`}
        description={`Active users assigned with ${selectedRole} permissions in this organization.`}
      >
        {peopleResource.status === 'loading' ? (
          <div className="py-12 text-center text-muted-foreground flex flex-col items-center gap-2">
            <RefreshCw className="w-6 h-6 animate-spin text-primary" />
            <span className="text-sm">Loading {selectedRole.toLowerCase()}s...</span>
          </div>
        ) : filteredPeople.length === 0 ? (
          <div className="py-12 text-center text-muted-foreground flex flex-col items-center gap-2">
            <Users className="w-8 h-8 opacity-40" />
            <span className="text-sm font-medium">No {selectedRole.toLowerCase()}s found.</span>
            <span className="text-xs opacity-75">Click "Assign Role" to grant this role to a user.</span>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-border/40 text-xs text-muted-foreground uppercase font-medium">
                <tr>
                  <th className="py-3 px-4">User ID</th>
                  <th className="py-3 px-4">Name</th>
                  <th className="py-3 px-4">Email</th>
                  <th className="py-3 px-4">Role</th>
                  <th className="py-3 px-4">Campus</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/20">
                {filteredPeople.map((person) => (
                  <tr key={person.user_id} className="hover:bg-muted/30 transition-colors">
                    <td className="py-3 px-4 font-mono text-xs text-muted-foreground">#{person.user_id}</td>
                    <td className="py-3 px-4 font-medium text-foreground">{person.name || 'Unnamed'}</td>
                    <td className="py-3 px-4 text-muted-foreground">{person.email || '-'}</td>
                    <td className="py-3 px-4">
                      <StatusChip tone="positive" label={person.role} />
                    </td>
                    <td className="py-3 px-4 text-muted-foreground">
                      {person.campus_id ? `Campus #${person.campus_id}` : 'All Campuses'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </SectionCard>

      {/* Assign Role Dialog */}
      <SchoolDialog
        open={isAssignOpen}
        onOpenChange={setIsAssignOpen}
        title="Assign School Role"
        description="Grant specialized school permissions (Teacher, Student, Parent, Admin) to an existing user."
      >
        <form onSubmit={handleAssign} className="space-y-4">
          <SchoolField id="assign-user-id" label="User ID" help="The numeric ID of the user account.">
            <input
              type="number"
              required
              placeholder="e.g. 104"
              value={targetUserId}
              onChange={(e) => setTargetUserId(e.target.value)}
              className={LH_INPUT}
            />
          </SchoolField>

          <SchoolField id="assign-role" label="Role" help="The school role to assign.">
            <select
              value={assignRoleType}
              onChange={(e) => setAssignRoleType(e.target.value as SchoolRoleType)}
              className={LH_INPUT}
            >
              {ALL_ROLES.map((r) => (
                <option key={r.key} value={r.key}>
                  {r.label} ({r.key})
                </option>
              ))}
            </select>
          </SchoolField>

          <div className="flex justify-end gap-2 pt-4">
            <button
              type="button"
              onClick={() => setIsAssignOpen(false)}
              className={LH_SECONDARY_BUTTON}
              disabled={isSubmitting}
            >
              Cancel
            </button>
            <button type="submit" className={LH_PRIMARY_BUTTON} disabled={isSubmitting}>
              {isSubmitting ? 'Assigning...' : 'Confirm Assignment'}
            </button>
          </div>
        </form>
      </SchoolDialog>
    </div>
  )
}
