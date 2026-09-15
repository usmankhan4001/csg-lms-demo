'use client'

import React, { useState, useEffect, useMemo } from 'react'
import {
  Shield,
  Search,
  CheckSquare,
  Square,
  Info,
  Layers,
  Copy,
  Sliders,
  CheckCircle2,
  AlertCircle,
  X,
  Plus,
} from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog'
import {
  LH_INPUT,
  LH_LABEL,
  LH_PRIMARY_BUTTON,
  LH_SECONDARY_BUTTON,
  StatusChip,
} from '@/components/widgets'
import {
  EMSRole,
  EMSPermissionRule,
  PermissionAction,
  ScopeLevel,
  RESOURCE_DOMAINS,
  SCOPE_DEFINITIONS,
  SYSTEM_ROLE_TEMPLATES,
  ResourceDomain,
} from '@/lib/ems-permissions'

export interface RoleEditorDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  role?: EMSRole | null
  existingRoles?: EMSRole[]
  onSave: (role: EMSRole) => void
  isClone?: boolean
}

const ACTION_COLUMNS: { key: PermissionAction; label: string; tooltip: string }[] = [
  { key: 'read', label: 'Read', tooltip: 'View and query records' },
  { key: 'create', label: 'Create', tooltip: 'Create new records' },
  { key: 'update', label: 'Update', tooltip: 'Modify existing records' },
  { key: 'delete', label: 'Delete', tooltip: 'Permanently remove records' },
  { key: 'approve', label: 'Approve', tooltip: 'Authorize workflows and approvals' },
  { key: 'export', label: 'Export', tooltip: 'Download CSV / Excel / PDF reports' },
]

export function RoleEditorDialog({
  open,
  onOpenChange,
  role,
  existingRoles = SYSTEM_ROLE_TEMPLATES,
  onSave,
  isClone = false,
}: RoleEditorDialogProps) {
  const isEditing = Boolean(role && !isClone)

  const [name, setName] = useState('')
  const [code, setCode] = useState('')
  const [description, setDescription] = useState('')
  const [inheritsFrom, setInheritsFrom] = useState<string>('')
  const [filterDomain, setFilterDomain] = useState('')
  const [selectedCategory, setSelectedCategory] = useState<string>('all')
  const [rules, setRules] = useState<Record<string, EMSPermissionRule>>({})
  const [error, setError] = useState<string | null>(null)

  // Initialize form state when opened or role changes
  useEffect(() => {
    if (open) {
      setError(null)
      if (role) {
        setName(isClone ? `${role.name || ''} (Copy)` : (role.name || ''))
        setCode(isClone ? `${role.code || role.slug || 'CUSTOM'}_COPY` : (role.code || role.slug || 'CUSTOM'))
        setDescription(role.description || '')
        setInheritsFrom(role.inheritsFrom || '')

        // Populate rules map
        const initialRules: Record<string, EMSPermissionRule> = {}
        // Default all resource domains
        RESOURCE_DOMAINS.forEach((domain) => {
          const existing = (role.permissions || []).find((p) => p.resource === domain.key)
          if (existing) {
            initialRules[domain.key] = {
              resource: domain.key,
              actions: { ...existing.actions },
              scope: existing.scope || 'campus',
            }
          } else {
            initialRules[domain.key] = {
              resource: domain.key,
              actions: { read: false, create: false, update: false, delete: false, approve: false, export: false },
              scope: 'campus',
            }
          }
        })
        setRules(initialRules)
      } else {
        // Create new role defaults
        setName('')
        setCode('')
        setDescription('')
        setInheritsFrom('')
        const initialRules: Record<string, EMSPermissionRule> = {}
        RESOURCE_DOMAINS.forEach((domain) => {
          initialRules[domain.key] = {
            resource: domain.key,
            actions: { read: false, create: false, update: false, delete: false, approve: false, export: false },
            scope: 'campus',
          }
        })
        setRules(initialRules)
      }
    }
  }, [open, role, isClone])

  // Handle Inherits From change: copy permissions from selected role
  const handleInheritChange = (baseRoleId: string) => {
    setInheritsFrom(baseRoleId)
    if (!baseRoleId) return

    const baseRole = existingRoles.find((r) => r.id === baseRoleId || r.code === baseRoleId)
    if (!baseRole) return

    setRules((prev) => {
      const next = { ...prev }
      baseRole.permissions.forEach((perm) => {
        next[perm.resource] = {
          resource: perm.resource,
          actions: { ...perm.actions },
          scope: perm.scope,
        }
      })
      return next
    })
  }

  // Toggle individual permission checkbox
  const toggleAction = (resourceKey: ResourceDomain, action: PermissionAction) => {
    setRules((prev) => {
      const current = prev[resourceKey] || {
        resource: resourceKey,
        actions: {},
        scope: 'campus',
      }
      return {
        ...prev,
        [resourceKey]: {
          ...current,
          actions: {
            ...current.actions,
            [action]: !current.actions[action],
          },
        },
      }
    })
  }

  // Change scope level for domain
  const changeScope = (resourceKey: ResourceDomain, scope: ScopeLevel) => {
    setRules((prev) => {
      const current = prev[resourceKey] || {
        resource: resourceKey,
        actions: {},
        scope: 'campus',
      }
      return {
        ...prev,
        [resourceKey]: {
          ...current,
          scope,
        },
      }
    })
  }

  // Toggle entire row (all actions on/off for a resource)
  const toggleAllActionsForRow = (resourceKey: ResourceDomain) => {
    setRules((prev) => {
      const current = prev[resourceKey]
      const hasAny = ACTION_COLUMNS.some((col) => current?.actions[col.key])
      const nextValue = !hasAny

      return {
        ...prev,
        [resourceKey]: {
          resource: resourceKey,
          scope: current?.scope ?? 'campus',
          actions: {
            read: nextValue,
            create: nextValue,
            update: nextValue,
            delete: nextValue,
            approve: nextValue,
            export: nextValue,
          },
        },
      }
    })
  }

  // Bulk actions across all filtered/all domains
  const handleBulkAction = (type: 'all_read' | 'all_full' | 'reset_all' | 'scope_all_campus') => {
    setRules((prev) => {
      const next = { ...prev }
      RESOURCE_DOMAINS.forEach((domain) => {
        const cur = next[domain.key] || { resource: domain.key, actions: {}, scope: 'campus' }
        if (type === 'all_read') {
          next[domain.key] = { ...cur, actions: { ...cur.actions, read: true } }
        } else if (type === 'all_full') {
          next[domain.key] = {
            ...cur,
            actions: { read: true, create: true, update: true, delete: true, approve: true, export: true },
          }
        } else if (type === 'reset_all') {
          next[domain.key] = {
            ...cur,
            actions: { read: false, create: false, update: false, delete: false, approve: false, export: false },
          }
        } else if (type === 'scope_all_campus') {
          next[domain.key] = { ...cur, scope: 'campus' }
        }
      })
      return next
    })
  }

  // Categories list
  const categories = useMemo(() => {
    const cats = new Set<string>()
    RESOURCE_DOMAINS.forEach((d) => cats.add(d.category))
    return Array.from(cats)
  }, [])

  // Filtered domains
  const filteredDomains = useMemo(() => {
    return RESOURCE_DOMAINS.filter((d) => {
      const matchesSearch =
        d.label.toLowerCase().includes(filterDomain.toLowerCase()) ||
        d.key.toLowerCase().includes(filterDomain.toLowerCase()) ||
        d.description.toLowerCase().includes(filterDomain.toLowerCase())

      const matchesCat = selectedCategory === 'all' || d.category === selectedCategory
      return matchesSearch && matchesCat
    })
  }, [filterDomain, selectedCategory])

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) {
      setError('Role name is required.')
      return
    }
    if (!code.trim()) {
      setError('Role code identifier is required.')
      return
    }

    const cleanedCode = code
      .trim()
      .toUpperCase()
      .replace(/[^A-Z0-9_]/g, '_')

    const permissionList: EMSPermissionRule[] = Object.values(rules).filter(
      (rule) =>
        ACTION_COLUMNS.some((col) => rule.actions[col.key]) || rule.scope !== 'campus'
    )

    const savedRole: EMSRole = {
      id: isEditing && role ? role.id : `custom-${cleanedCode.toLowerCase()}-${Date.now()}`,
      name: name.trim(),
      code: cleanedCode,
      description: description.trim(),
      isSystem: false,
      inheritsFrom: inheritsFrom || undefined,
      permissions: permissionList,
      updated_at: new Date().toISOString(),
      created_at: role?.created_at || new Date().toISOString(),
    }

    onSave(savedRole)
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-5xl max-h-[92vh] flex flex-col p-0 gap-0 overflow-hidden bg-background">
        <DialogHeader className="p-6 pb-4 border-b border-border/60 bg-muted/20">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-xl bg-primary/10 text-primary border border-primary/20">
                <Shield className="w-5 h-5" />
              </div>
              <div>
                <DialogTitle className="text-xl font-bold">
                  {isEditing ? `Edit Role: ${role?.name}` : isClone ? `Clone Role: ${role?.name}` : 'Create Custom EMS Role'}
                </DialogTitle>
                <DialogDescription className="text-sm text-muted-foreground mt-0.5">
                  Configure granular resource permissions and scope boundaries in the permission matrix.
                </DialogDescription>
              </div>
            </div>
          </div>
        </DialogHeader>

        {error && (
          <div className="mx-6 mt-4 flex items-center gap-2 p-3 rounded-lg bg-rose-500/10 text-rose-500 border border-rose-500/20 text-xs font-medium">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSave} className="flex-1 flex flex-col overflow-hidden">
          <div className="flex-1 overflow-y-auto px-6 py-4 space-y-6">
            {/* Top Metadata Grid */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 p-4 rounded-xl border border-border/50 bg-card/40">
              <div>
                <label className={`${LH_LABEL} text-xs`}>Role Name *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Department Head, Senior Bursar"
                  value={name}
                  onChange={(e) => {
                    setName(e.target.value)
                    if (!isEditing && !code) {
                      setCode(
                        e.target.value
                          .toUpperCase()
                          .replace(/[^A-Z0-9_]/g, '_')
                      )
                    }
                  }}
                  className={`${LH_INPUT} mt-1 h-9 text-sm`}
                />
              </div>

              <div>
                <label className={`${LH_LABEL} text-xs`}>Role Code Identifier *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. DEPT_HEAD"
                  value={code}
                  onChange={(e) => setCode(e.target.value.toUpperCase().replace(/[^A-Z0-9_]/g, '_'))}
                  className={`${LH_INPUT} mt-1 h-9 text-sm font-mono`}
                  disabled={isEditing && role?.isSystem}
                />
              </div>

              <div>
                <label className={`${LH_LABEL} text-xs`}>Inherit Base Permissions From</label>
                <select
                  value={inheritsFrom}
                  onChange={(e) => handleInheritChange(e.target.value)}
                  className={`${LH_INPUT} mt-1 h-9 text-sm`}
                >
                  <option value="">-- Standalone (No Inheritance) --</option>
                  {existingRoles.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.name} ({r.code}) {r.isSystem ? '[System]' : ''}
                    </option>
                  ))}
                </select>
              </div>

              <div className="md:col-span-3">
                <label className={`${LH_LABEL} text-xs`}>Description</label>
                <input
                  type="text"
                  placeholder="Briefly describe responsibilities and domain constraints for this role"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  className={`${LH_INPUT} mt-1 h-9 text-sm`}
                />
              </div>
            </div>

            {/* Permission Matrix Header & Quick Toolbar */}
            <div className="space-y-3">
              <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
                <div>
                  <h3 className="text-sm font-semibold flex items-center gap-2">
                    <Sliders className="w-4 h-4 text-primary" />
                    Permission Matrix & Scope Constraints
                  </h3>
                  <p className="text-xs text-muted-foreground">
                    Define Read/Write/Approve privileges and hierarchical data scope for each resource domain.
                  </p>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    onClick={() => handleBulkAction('all_read')}
                    className="text-xs px-2.5 py-1 rounded-md border border-border/70 hover:bg-muted/60 text-muted-foreground hover:text-foreground font-medium transition-colors"
                  >
                    Grant All Read
                  </button>
                  <button
                    type="button"
                    onClick={() => handleBulkAction('all_full')}
                    className="text-xs px-2.5 py-1 rounded-md border border-primary/30 bg-primary/5 hover:bg-primary/10 text-primary font-medium transition-colors"
                  >
                    Grant Full Access
                  </button>
                  <button
                    type="button"
                    onClick={() => handleBulkAction('reset_all')}
                    className="text-xs px-2.5 py-1 rounded-md border border-border/70 hover:bg-muted/60 text-muted-foreground hover:text-foreground font-medium transition-colors"
                  >
                    Revoke All
                  </button>
                </div>
              </div>

              {/* Filters Bar */}
              <div className="flex flex-col sm:flex-row items-center gap-2 pt-1">
                <div className="relative flex-1 w-full">
                  <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                  <input
                    type="text"
                    placeholder="Filter resource domains (e.g. attendance, fees, exams)..."
                    value={filterDomain}
                    onChange={(e) => setFilterDomain(e.target.value)}
                    className={`${LH_INPUT} pl-8 h-8 text-xs`}
                  />
                  {filterDomain && (
                    <button
                      type="button"
                      onClick={() => setFilterDomain('')}
                      className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  )}
                </div>

                <div className="flex items-center gap-1 overflow-x-auto w-full sm:w-auto pb-1 sm:pb-0">
                  <button
                    type="button"
                    onClick={() => setSelectedCategory('all')}
                    className={`text-xs px-2.5 py-1 rounded-md whitespace-nowrap transition-colors ${
                      selectedCategory === 'all'
                        ? 'bg-primary text-primary-foreground font-semibold shadow-xs'
                        : 'bg-muted/50 text-muted-foreground hover:bg-muted font-normal'
                    }`}
                  >
                    All Modules
                  </button>
                  {categories.map((cat) => (
                    <button
                      key={cat}
                      type="button"
                      onClick={() => setSelectedCategory(cat)}
                      className={`text-xs px-2.5 py-1 rounded-md whitespace-nowrap transition-colors ${
                        selectedCategory === cat
                          ? 'bg-primary text-primary-foreground font-semibold shadow-xs'
                          : 'bg-muted/50 text-muted-foreground hover:bg-muted font-normal'
                      }`}
                    >
                      {cat}
                    </button>
                  ))}
                </div>
              </div>

              {/* ERPNext Style Matrix Table */}
              <div className="border border-border/60 rounded-xl overflow-hidden shadow-xs bg-card">
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs border-collapse">
                    <thead className="bg-muted/60 border-b border-border/60 text-muted-foreground uppercase font-semibold text-[11px] tracking-wider sticky top-0 z-10 backdrop-blur-sm">
                      <tr>
                        <th className="py-2.5 px-4 min-w-[200px]">Resource Domain</th>
                        {ACTION_COLUMNS.map((col) => (
                          <th key={col.key} className="py-2.5 px-2 text-center min-w-[68px]" title={col.tooltip}>
                            {col.label}
                          </th>
                        ))}
                        <th className="py-2.5 px-3 min-w-[150px]">Data Scope Level</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/30">
                      {filteredDomains.map((domain) => {
                        const rule = rules[domain.key] || {
                          resource: domain.key,
                          actions: {},
                          scope: 'campus',
                        }
                        const hasAnyChecked = ACTION_COLUMNS.some((col) => rule.actions[col.key])

                        return (
                          <tr
                            key={domain.key}
                            className={`hover:bg-muted/30 transition-colors ${
                              hasAnyChecked ? 'bg-primary/[0.02]' : ''
                            }`}
                          >
                            {/* Resource Title & Row Toggle */}
                            <td className="py-2.5 px-4">
                              <div className="flex items-start gap-2">
                                <button
                                  type="button"
                                  onClick={() => toggleAllActionsForRow(domain.key)}
                                  className="mt-0.5 text-muted-foreground hover:text-primary transition-colors"
                                  title="Toggle all actions for this domain"
                                >
                                  {hasAnyChecked ? (
                                    <CheckSquare className="w-3.5 h-3.5 text-primary" />
                                  ) : (
                                    <Square className="w-3.5 h-3.5" />
                                  )}
                                </button>
                                <div>
                                  <div className="flex items-center gap-1.5">
                                    <span className="font-semibold text-foreground">{domain.label}</span>
                                    <span className="text-[10px] px-1.5 py-0.2 rounded bg-muted text-muted-foreground font-mono">
                                      {domain.key}
                                    </span>
                                  </div>
                                  <p className="text-[11px] text-muted-foreground line-clamp-1 mt-0.5">
                                    {domain.description}
                                  </p>
                                </div>
                              </div>
                            </td>

                            {/* Action Checkboxes */}
                            {ACTION_COLUMNS.map((col) => {
                              const checked = Boolean(rule.actions[col.key])
                              return (
                                <td key={col.key} className="py-2.5 px-2 text-center">
                                  <label className="inline-flex items-center justify-center p-1 rounded hover:bg-muted/60 cursor-pointer">
                                    <input
                                      type="checkbox"
                                      checked={checked}
                                      onChange={() => toggleAction(domain.key, col.key)}
                                      className="w-4 h-4 rounded border-border/80 text-primary focus:ring-primary/30 accent-primary cursor-pointer"
                                    />
                                  </label>
                                </td>
                              )
                            })}

                            {/* Scope Level Selector */}
                            <td className="py-2.5 px-3">
                              <select
                                value={rule.scope}
                                onChange={(e) => changeScope(domain.key, e.target.value as ScopeLevel)}
                                disabled={!hasAnyChecked}
                                className={`w-full text-xs h-7 rounded border border-border/60 bg-background px-2 py-0.5 focus:outline-none focus:ring-1 focus:ring-primary ${
                                  !hasAnyChecked ? 'opacity-40 cursor-not-allowed' : 'text-foreground'
                                }`}
                              >
                                {SCOPE_DEFINITIONS.map((s) => (
                                  <option key={s.level} value={s.level}>
                                    {s.label}
                                  </option>
                                ))}
                              </select>
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </div>

          <DialogFooter className="p-4 px-6 border-t border-border/60 bg-muted/10 flex items-center justify-between sm:justify-between">
            <div className="text-xs text-muted-foreground flex items-center gap-1.5">
              <Info className="w-3.5 h-3.5" />
              <span>Permissions are enforced at both frontend router and API service layers.</span>
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => onOpenChange(false)}
                className={`${LH_SECONDARY_BUTTON} h-9 px-4 text-xs`}
              >
                Cancel
              </button>
              <button
                type="submit"
                className={`${LH_PRIMARY_BUTTON} h-9 px-5 text-xs font-semibold`}
              >
                {isEditing ? 'Save Changes' : 'Create Role'}
              </button>
            </div>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
