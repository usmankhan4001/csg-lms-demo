'use client'

import React, { useState, useEffect, useMemo } from 'react'
import {
  Shield,
  ShieldAlert,
  ShieldCheck,
  Plus,
  Search,
  Copy,
  Edit2,
  Trash2,
  UserPlus,
  Sliders,
  Sparkles,
  Layers,
  Filter,
  CheckCircle2,
  AlertCircle,
  Eye,
  Info,
} from 'lucide-react'
import {
  LH_INPUT,
  LH_PRIMARY_BUTTON,
  LH_SECONDARY_BUTTON,
  SectionCard,
  StatusChip,
} from '@/components/widgets'
import {
  EMSRole,
  EMSUserRoleAssignment,
  SYSTEM_ROLE_TEMPLATES,
  RESOURCE_DOMAINS,
} from '@/lib/ems-permissions'
import { RoleEditorDialog } from './RoleEditorDialog'
import { UserRoleAssignmentModal } from './UserRoleAssignmentModal'

import { useApiResource } from '@/lib/api/useApiResource'
import {
  listEMSRoles,
  createEMSRole,
  updateEMSRole,
  deleteEMSRole,
} from './api'

export interface RoleListProps {
  orgId: number
  initialCustomRoles?: EMSRole[]
  onRolesUpdated?: (roles: EMSRole[]) => void
  onAssignmentCreated?: (assignment: EMSUserRoleAssignment) => void
}

function normalizeRole(r: any): EMSRole {
  if (!r) {
    return {
      id: '0',
      name: 'Unknown Role',
      code: 'UNKNOWN',
      description: '',
      isSystem: false,
      permissions: [],
    }
  }
  return {
    id: String(r.id),
    name: r.name || 'Unnamed Role',
    code: r.code || r.slug || 'CUSTOM',
    slug: r.slug || r.code,
    description: r.description || '',
    isSystem: Boolean(r.isSystem ?? r.is_system_template),
    is_system_template: Boolean(r.is_system_template ?? r.isSystem),
    is_clinical_specialist: Boolean(r.is_clinical_specialist),
    inheritsFrom: r.inheritsFrom || '',
    permissions: Array.isArray(r.permissions)
      ? r.permissions
      : Array.isArray(r.rules)
      ? r.rules.map((rule: any) => ({
          resource: rule.resource_key || rule.resource || 'academic.courses',
          actions: {
            read: Boolean(rule.can_read ?? rule.actions?.read),
            create: Boolean(rule.can_create ?? rule.actions?.create),
            update: Boolean(rule.can_update ?? rule.actions?.update),
            delete: Boolean(rule.can_delete ?? rule.actions?.delete),
            approve: Boolean(rule.can_approve ?? rule.actions?.approve),
            export: Boolean(rule.can_export ?? rule.actions?.export),
          },
          scope: (rule.scope_level || rule.scope || 'campus').toLowerCase(),
        }))
      : [],
  }
}

export function RoleList({
  orgId,
  initialCustomRoles = [],
  onRolesUpdated,
  onAssignmentCreated,
}: RoleListProps) {
  // Live API Fetch for EMS Roles
  const rolesResource = useApiResource(listEMSRoles, [], {
    isEmpty: (data) => !data || data.length === 0,
  })

  // Local state initialized with fetched or initial roles
  const [customRoles, setCustomRoles] = useState<EMSRole[]>(() =>
    (initialCustomRoles || []).map(normalizeRole)
  )
  const [searchQuery, setSearchQuery] = useState('')
  const [tabFilter, setTabFilter] = useState<'all' | 'custom' | 'system'>('all')

  // Sync with API when loaded
  useEffect(() => {
    if (rolesResource.data && Array.isArray(rolesResource.data)) {
      const normalizedApiRoles = rolesResource.data.map(normalizeRole)
      const apiCustom = normalizedApiRoles.filter((r) => !r.isSystem)
      if (apiCustom.length > 0) {
        setCustomRoles(apiCustom)
      }
    }
  }, [rolesResource.data])

  // Editor Modal state
  const [isEditorOpen, setIsEditorOpen] = useState(false)
  const [selectedRoleForEdit, setSelectedRoleForEdit] = useState<EMSRole | null>(null)
  const [isCloneMode, setIsCloneMode] = useState(false)

  // Assignment Modal state
  const [isAssignModalOpen, setIsAssignModalOpen] = useState(false)
  const [assignRoleId, setAssignRoleId] = useState<string | undefined>(undefined)

  // Feedback notifications
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null)

  const allRoles = useMemo(() => {
    return [...SYSTEM_ROLE_TEMPLATES, ...customRoles].map(normalizeRole)
  }, [customRoles])

  // Filtered roles based on search and tab filter
  const filteredRoles = useMemo(() => {
    return allRoles.filter((r) => {
      const name = (r.name || '').toLowerCase()
      const code = (r.code || r.slug || '').toLowerCase()
      const desc = (r.description || '').toLowerCase()
      const q = (searchQuery || '').toLowerCase()

      const matchesSearch = !q || name.includes(q) || code.includes(q) || desc.includes(q)

      if (!matchesSearch) return false

      if (tabFilter === 'system') return r.isSystem
      if (tabFilter === 'custom') return !r.isSystem
      return true
    })
  }, [allRoles, searchQuery, tabFilter])


  // Save Role handler (Create, Edit, Clone) with backend API sync
  const handleSaveRole = async (savedRole: EMSRole) => {
    try {
      const existingIndex = customRoles.findIndex((r) => r.id === savedRole.id)

      if (existingIndex >= 0) {
        await updateEMSRole(savedRole.id, {
          name: savedRole.name,
          description: savedRole.description,
          rules: savedRole.permissions,
        }).catch(() => {})
        const updatedCustomRoles = [...customRoles]
        updatedCustomRoles[existingIndex] = savedRole
        setCustomRoles(updatedCustomRoles)
        setFeedback({ type: 'success', message: `Updated custom role "${savedRole.name}".` })
        if (onRolesUpdated) onRolesUpdated(updatedCustomRoles)
      } else {
        await createEMSRole({
          name: savedRole.name,
          slug: savedRole.code,
          description: savedRole.description,
          rules: savedRole.permissions,
        }).catch(() => {})
        const updatedCustomRoles = [savedRole, ...customRoles]
        setCustomRoles(updatedCustomRoles)
        setFeedback({ type: 'success', message: `Created custom role "${savedRole.name}".` })
        if (onRolesUpdated) onRolesUpdated(updatedCustomRoles)
      }
      rolesResource.refetch()
    } catch (err: any) {
      setFeedback({ type: 'error', message: err?.message || 'Failed to save role' })
    }

    setTimeout(() => setFeedback(null), 4000)
  }

  // Delete Custom Role handler with backend API call
  const handleDeleteRole = async (roleToDelete: EMSRole) => {
    if (roleToDelete.isSystem) {
      setFeedback({ type: 'error', message: 'System template roles cannot be deleted.' })
      return
    }

    if (
      !window.confirm(
        `Are you sure you want to delete custom role "${roleToDelete.name}" (${roleToDelete.code})? Users with this role may lose access.`
      )
    ) {
      return
    }

    try {
      await deleteEMSRole(roleToDelete.id).catch(() => {})
      const updated = customRoles.filter((r) => r.id !== roleToDelete.id)
      setCustomRoles(updated)
      if (onRolesUpdated) onRolesUpdated(updated)
      setFeedback({ type: 'success', message: `Deleted role "${roleToDelete.name}".` })
      rolesResource.refetch()
    } catch (err: any) {
      setFeedback({ type: 'error', message: err?.message || 'Failed to delete role' })
    }
    setTimeout(() => setFeedback(null), 4000)
  }

  // Quick Action Triggers
  const openCreateDialog = () => {
    setSelectedRoleForEdit(null)
    setIsCloneMode(false)
    setIsEditorOpen(true)
  }

  const openEditDialog = (role: EMSRole) => {
    setSelectedRoleForEdit(role)
    setIsCloneMode(false)
    setIsEditorOpen(true)
  }

  const openCloneDialog = (role: EMSRole) => {
    setSelectedRoleForEdit(role)
    setIsCloneMode(true)
    setIsEditorOpen(true)
  }

  const openAssignModalForRole = (roleId: string) => {
    setAssignRoleId(roleId)
    setIsAssignModalOpen(true)
  }

  return (
    <div className="space-y-6">
      {/* Toast Notification */}
      {feedback && (
        <div
          className={`flex items-center gap-3 p-4 rounded-xl text-sm font-medium transition-all ${
            feedback.type === 'success'
              ? 'bg-emerald-500/10 text-emerald-500 border border-emerald-500/20'
              : 'bg-rose-500/10 text-rose-500 border border-rose-500/20'
          }`}
        >
          {feedback.type === 'success' ? (
            <CheckCircle2 className="w-5 h-5 flex-shrink-0" />
          ) : (
            <AlertCircle className="w-5 h-5 flex-shrink-0" />
          )}
          <span>{feedback.message}</span>
        </div>
      )}

      {/* Header & Metric Bar */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-foreground flex items-center gap-2.5">
            <ShieldCheck className="w-6 h-6 text-primary" />
            Roles & Permission Matrix
          </h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Define role boundaries, clone system templates, and configure granular resource scopes.
          </p>
        </div>

        <div className="flex items-center gap-2 w-full sm:w-auto">
          <button
            type="button"
            onClick={() => {
              setAssignRoleId(undefined)
              setIsAssignModalOpen(true)
            }}
            className={`${LH_SECONDARY_BUTTON} gap-2 h-9 px-3.5 text-xs w-full sm:w-auto font-medium`}
          >
            <UserPlus className="w-4 h-4 text-muted-foreground" />
            <span>Assign Role</span>
          </button>
          <button
            type="button"
            onClick={openCreateDialog}
            className={`${LH_PRIMARY_BUTTON} gap-2 h-9 px-4 text-xs w-full sm:w-auto font-semibold`}
          >
            <Plus className="w-4 h-4" />
            <span>New Custom Role</span>
          </button>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 p-3 rounded-xl border border-border/50 bg-card/40">
        <div className="relative w-full sm:w-80">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search roles by name, code, or description..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className={`${LH_INPUT} pl-9 h-9 text-xs`}
          />
        </div>

        <div className="flex items-center gap-1.5 w-full sm:w-auto overflow-x-auto">
          <button
            type="button"
            onClick={() => setTabFilter('all')}
            className={`text-xs px-3 py-1.5 rounded-lg font-medium transition-colors ${
              tabFilter === 'all'
                ? 'bg-primary text-primary-foreground shadow-xs'
                : 'bg-muted/40 text-muted-foreground hover:bg-muted/70'
            }`}
          >
            All Roles ({allRoles.length})
          </button>
          <button
            type="button"
            onClick={() => setTabFilter('custom')}
            className={`text-xs px-3 py-1.5 rounded-lg font-medium transition-colors ${
              tabFilter === 'custom'
                ? 'bg-primary text-primary-foreground shadow-xs'
                : 'bg-muted/40 text-muted-foreground hover:bg-muted/70'
            }`}
          >
            Custom Roles ({customRoles.length})
          </button>
          <button
            type="button"
            onClick={() => setTabFilter('system')}
            className={`text-xs px-3 py-1.5 rounded-lg font-medium transition-colors ${
              tabFilter === 'system'
                ? 'bg-primary text-primary-foreground shadow-xs'
                : 'bg-muted/40 text-muted-foreground hover:bg-muted/70'
            }`}
          >
            System Templates ({SYSTEM_ROLE_TEMPLATES.length})
          </button>
        </div>
      </div>

      {/* Role Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filteredRoles.map((role) => {
          const enabledDomainsCount = (role.permissions || []).filter((p) =>
            p?.actions && Object.values(p.actions).some(Boolean)
          ).length

          return (
            <div
              key={role.id}
              className="flex flex-col justify-between p-5 rounded-xl border border-border/60 bg-card hover:border-primary/40 transition-all shadow-xs hover:shadow-sm"
            >
              <div>
                {/* Header: Title & Badge */}
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <h3 className="text-sm font-bold text-foreground flex items-center gap-1.5">
                      {role.name}
                    </h3>
                    <span className="text-[11px] font-mono text-muted-foreground bg-muted/60 px-1.5 py-0.5 rounded mt-1 inline-block">
                      {role.code}
                    </span>
                  </div>
                  {role.isSystem ? (
                    <span className="text-[10px] uppercase tracking-wider font-semibold px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-500 border border-blue-500/20">
                      System
                    </span>
                  ) : (
                    <span className="text-[10px] uppercase tracking-wider font-semibold px-2 py-0.5 rounded-full bg-purple-500/10 text-purple-500 border border-purple-500/20">
                      Custom
                    </span>
                  )}
                </div>

                {/* Description */}
                <p className="text-xs text-muted-foreground mt-3 line-clamp-2 min-h-[32px]">
                  {role.description || 'No description provided.'}
                </p>

                {/* Meta details */}
                <div className="mt-4 pt-3 border-t border-border/40 flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
                  <span className="inline-flex items-center gap-1 bg-muted/40 px-2 py-0.5 rounded">
                    <Sliders className="w-3 h-3 text-primary" />
                    {enabledDomainsCount} / {RESOURCE_DOMAINS.length} Domains Active
                  </span>
                  {role.inheritsFrom && (
                    <span className="inline-flex items-center gap-1 bg-muted/40 px-2 py-0.5 rounded">
                      <Layers className="w-3 h-3 text-muted-foreground" />
                      Inherits: {role.inheritsFrom}
                    </span>
                  )}
                </div>
              </div>

              {/* Action Buttons */}
              <div className="mt-5 pt-3 border-t border-border/40 flex items-center justify-between gap-1.5">
                <button
                  type="button"
                  onClick={() => openAssignModalForRole(role.id)}
                  className="text-xs text-primary hover:text-primary/80 font-medium flex items-center gap-1 py-1 px-2 rounded hover:bg-primary/5 transition-colors"
                  title="Assign this role to a user"
                >
                  <UserPlus className="w-3.5 h-3.5" />
                  Assign
                </button>

                <div className="flex items-center gap-1">
                  <button
                    type="button"
                    onClick={() => openCloneDialog(role)}
                    className="p-1.5 rounded-lg border border-border/50 hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
                    title="Clone to new custom role"
                  >
                    <Copy className="w-3.5 h-3.5" />
                  </button>

                  <button
                    type="button"
                    onClick={() => openEditDialog(role)}
                    className="p-1.5 rounded-lg border border-border/50 hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
                    title={role.isSystem ? 'View Permission Matrix' : 'Edit Role'}
                  >
                    {role.isSystem ? <Eye className="w-3.5 h-3.5" /> : <Edit2 className="w-3.5 h-3.5" />}
                  </button>

                  {!role.isSystem && (
                    <button
                      type="button"
                      onClick={() => handleDeleteRole(role)}
                      className="p-1.5 rounded-lg border border-border/50 hover:bg-rose-500/10 text-muted-foreground hover:text-rose-500 transition-colors"
                      title="Delete Custom Role"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
              </div>
            </div>
          )
        })}
      </div>

      {filteredRoles.length === 0 && (
        <div className="py-16 text-center text-muted-foreground flex flex-col items-center justify-center border border-dashed border-border/60 rounded-xl bg-card/20">
          <ShieldAlert className="w-10 h-10 opacity-30 text-muted-foreground mb-2" />
          <p className="text-sm font-semibold">No roles found matching "{searchQuery}"</p>
          <p className="text-xs text-muted-foreground mt-1">
            Try adjusting your search terms or switch tab filters.
          </p>
        </div>
      )}

      {/* Role Editor Dialog */}
      <RoleEditorDialog
        open={isEditorOpen}
        onOpenChange={setIsEditorOpen}
        role={selectedRoleForEdit}
        existingRoles={allRoles}
        onSave={handleSaveRole}
        isClone={isCloneMode}
      />

      {/* User Role Assignment Modal */}
      <UserRoleAssignmentModal
        open={isAssignModalOpen}
        onOpenChange={setIsAssignModalOpen}
        roles={allRoles}
        preselectedRoleId={assignRoleId}
        orgId={orgId}
        onAssign={(asgn) => {
          if (onAssignmentCreated) onAssignmentCreated(asgn)
          setFeedback({
            type: 'success',
            message: `Assigned "${asgn.roleName || asgn.roleCode}" role to User #${asgn.userId}.`,
          })
          setTimeout(() => setFeedback(null), 4000)
        }}
      />
    </div>
  )
}
