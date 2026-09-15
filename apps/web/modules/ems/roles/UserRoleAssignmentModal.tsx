'use client'

import React, { useState } from 'react'
import {
  UserCheck,
  UserPlus,
  Shield,
  Building2,
  BookOpen,
  Calendar,
  Layers,
  CheckCircle2,
  AlertCircle,
  HelpCircle,
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
  EMSUserRoleAssignment,
  SYSTEM_ROLE_TEMPLATES,
} from '@/lib/ems-permissions'

export interface UserRoleAssignmentModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  roles?: EMSRole[]
  preselectedRoleId?: string
  orgId: number
  onAssign?: (assignment: EMSUserRoleAssignment) => Promise<void> | void
}

const SAMPLE_DEPARTMENTS = [
  'Mathematics & Statistics',
  'Sciences (Physics / Chemistry / Biology)',
  'Humanities & Languages',
  'Computer Science & Robotics',
  'Arts, Music & Drama',
  'Physical Education & Athletics',
  'Administration & Finance',
  'Pastoral Care & Counseling',
]

export function UserRoleAssignmentModal({
  open,
  onOpenChange,
  roles = SYSTEM_ROLE_TEMPLATES,
  preselectedRoleId,
  orgId,
  onAssign,
}: UserRoleAssignmentModalProps) {
  const [userId, setUserId] = useState('')
  const [userName, setUserName] = useState('')
  const [userEmail, setUserEmail] = useState('')
  const [selectedRoleId, setSelectedRoleId] = useState(preselectedRoleId || roles[0]?.id || 'sys-teacher')
  
  // Scope Constraints
  const [hasCampusConstraint, setHasCampusConstraint] = useState(false)
  const [campusId, setCampusId] = useState<string>('1')
  
  const [hasDepartmentConstraint, setHasDepartmentConstraint] = useState(false)
  const [departmentName, setDepartmentName] = useState(SAMPLE_DEPARTMENTS[0])
  
  const [hasSectionConstraint, setHasSectionConstraint] = useState(false)
  const [sectionId, setSectionId] = useState('')
  const [sectionName, setSectionName] = useState('')

  const [expiresAt, setExpiresAt] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)

  const selectedRole = roles.find((r) => r.id === selectedRoleId || r.code === selectedRoleId)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setSuccessMessage(null)

    const numericUserId = parseInt(userId.trim(), 10)
    if (isNaN(numericUserId) || numericUserId <= 0) {
      setError('Please enter a valid numeric User ID.')
      return
    }

    if (!selectedRole) {
      setError('Please select a valid role.')
      return
    }

    setIsSubmitting(true)
    try {
      const assignment: EMSUserRoleAssignment = {
        id: `asgn-${Date.now()}`,
        userId: numericUserId,
        userName: userName.trim() || undefined,
        userEmail: userEmail.trim() || undefined,
        roleId: selectedRole.id,
        roleCode: selectedRole.code,
        roleName: selectedRole.name,
        campusId: hasCampusConstraint ? parseInt(campusId, 10) || null : null,
        campusName: hasCampusConstraint ? `Campus #${campusId}` : undefined,
        departmentId: hasDepartmentConstraint ? departmentName : null,
        departmentName: hasDepartmentConstraint ? departmentName : undefined,
        sectionId: hasSectionConstraint && sectionId ? parseInt(sectionId, 10) || null : null,
        sectionName: hasSectionConstraint ? sectionName || `Section #${sectionId}` : undefined,
        assignedAt: new Date().toISOString(),
        expiresAt: expiresAt || null,
        isActive: true,
      }

      if (onAssign) {
        await onAssign(assignment)
      }

      setSuccessMessage(`Role "${selectedRole.name}" successfully assigned to User #${numericUserId}.`)
      setTimeout(() => {
        onOpenChange(false)
        setSuccessMessage(null)
        setUserId('')
        setUserName('')
        setUserEmail('')
      }, 1200)
    } catch (err: any) {
      setError(err?.message || 'Failed to assign role constraint.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl p-0 gap-0 overflow-hidden bg-background">
        <DialogHeader className="p-6 pb-4 border-b border-border/60 bg-muted/20">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-primary/10 text-primary border border-primary/20">
              <UserPlus className="w-5 h-5" />
            </div>
            <div>
              <DialogTitle className="text-lg font-bold">Assign Role with Scope Constraints</DialogTitle>
              <DialogDescription className="text-xs text-muted-foreground mt-0.5">
                Grant system templates or custom EMS roles restricted by Campus, Department, or Class Section.
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        {error && (
          <div className="mx-6 mt-4 flex items-center gap-2 p-3 rounded-lg bg-rose-500/10 text-rose-500 border border-rose-500/20 text-xs font-medium">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {successMessage && (
          <div className="mx-6 mt-4 flex items-center gap-2 p-3 rounded-lg bg-emerald-500/10 text-emerald-500 border border-emerald-500/20 text-xs font-medium">
            <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
            <span>{successMessage}</span>
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="p-6 space-y-5 max-h-[70vh] overflow-y-auto">
            {/* User Target Fields */}
            <div className="space-y-3">
              <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                <UserCheck className="w-3.5 h-3.5" />
                Target User
              </h4>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div className="sm:col-span-1">
                  <label className={`${LH_LABEL} text-xs`}>User ID *</label>
                  <input
                    type="number"
                    required
                    placeholder="e.g. 102"
                    value={userId}
                    onChange={(e) => setUserId(e.target.value)}
                    className={`${LH_INPUT} mt-1 h-9 text-xs`}
                  />
                </div>
                <div className="sm:col-span-1">
                  <label className={`${LH_LABEL} text-xs`}>Name (Optional)</label>
                  <input
                    type="text"
                    placeholder="e.g. Dr. Jane Smith"
                    value={userName}
                    onChange={(e) => setUserName(e.target.value)}
                    className={`${LH_INPUT} mt-1 h-9 text-xs`}
                  />
                </div>
                <div className="sm:col-span-1">
                  <label className={`${LH_LABEL} text-xs`}>Email (Optional)</label>
                  <input
                    type="email"
                    placeholder="user@school.edu"
                    value={userEmail}
                    onChange={(e) => setUserEmail(e.target.value)}
                    className={`${LH_INPUT} mt-1 h-9 text-xs`}
                  />
                </div>
              </div>
            </div>

            {/* Role Selection */}
            <div className="space-y-2">
              <label className={`${LH_LABEL} text-xs flex items-center gap-1.5`}>
                <Shield className="w-3.5 h-3.5 text-primary" />
                Select EMS Role *
              </label>
              <select
                value={selectedRoleId}
                onChange={(e) => setSelectedRoleId(e.target.value)}
                className={`${LH_INPUT} h-9 text-xs`}
              >
                {roles.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.name} ({r.code}) {r.isSystem ? '[System Template]' : '[Custom]'}
                  </option>
                ))}
              </select>
              {selectedRole && (
                <p className="text-[11px] text-muted-foreground bg-muted/30 p-2 rounded-md border border-border/40">
                  {selectedRole.description}
                </p>
              )}
            </div>

            {/* Granular Scope Constraints */}
            <div className="space-y-3 pt-2 border-t border-border/40">
              <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                <Layers className="w-3.5 h-3.5" />
                Organizational Scope Constraints
              </h4>

              {/* Campus Constraint */}
              <div className="p-3 rounded-lg border border-border/50 bg-card/40 space-y-2">
                <label className="flex items-center justify-between cursor-pointer">
                  <span className="text-xs font-medium text-foreground flex items-center gap-1.5">
                    <Building2 className="w-3.5 h-3.5 text-muted-foreground" />
                    Restrict to Specific Campus
                  </span>
                  <input
                    type="checkbox"
                    checked={hasCampusConstraint}
                    onChange={(e) => setHasCampusConstraint(e.target.checked)}
                    className="w-4 h-4 rounded border-border/80 text-primary focus:ring-primary/30 accent-primary"
                  />
                </label>
                {hasCampusConstraint && (
                  <div className="pt-2">
                    <label className={`${LH_LABEL} text-[11px]`}>Campus ID / Branch</label>
                    <input
                      type="number"
                      placeholder="e.g. 1 (Main Campus)"
                      value={campusId}
                      onChange={(e) => setCampusId(e.target.value)}
                      className={`${LH_INPUT} mt-1 h-8 text-xs`}
                    />
                  </div>
                )}
              </div>

              {/* Department Constraint */}
              <div className="p-3 rounded-lg border border-border/50 bg-card/40 space-y-2">
                <label className="flex items-center justify-between cursor-pointer">
                  <span className="text-xs font-medium text-foreground flex items-center gap-1.5">
                    <Layers className="w-3.5 h-3.5 text-muted-foreground" />
                    Restrict to Academic Department / Faculty
                  </span>
                  <input
                    type="checkbox"
                    checked={hasDepartmentConstraint}
                    onChange={(e) => setHasDepartmentConstraint(e.target.checked)}
                    className="w-4 h-4 rounded border-border/80 text-primary focus:ring-primary/30 accent-primary"
                  />
                </label>
                {hasDepartmentConstraint && (
                  <div className="pt-2">
                    <label className={`${LH_LABEL} text-[11px]`}>Department</label>
                    <select
                      value={departmentName}
                      onChange={(e) => setDepartmentName(e.target.value)}
                      className={`${LH_INPUT} mt-1 h-8 text-xs`}
                    >
                      {SAMPLE_DEPARTMENTS.map((dept) => (
                        <option key={dept} value={dept}>
                          {dept}
                        </option>
                      ))}
                    </select>
                  </div>
                )}
              </div>

              {/* Section Constraint */}
              <div className="p-3 rounded-lg border border-border/50 bg-card/40 space-y-2">
                <label className="flex items-center justify-between cursor-pointer">
                  <span className="text-xs font-medium text-foreground flex items-center gap-1.5">
                    <BookOpen className="w-3.5 h-3.5 text-muted-foreground" />
                    Restrict to Class Section
                  </span>
                  <input
                    type="checkbox"
                    checked={hasSectionConstraint}
                    onChange={(e) => setHasSectionConstraint(e.target.checked)}
                    className="w-4 h-4 rounded border-border/80 text-primary focus:ring-primary/30 accent-primary"
                  />
                </label>
                {hasSectionConstraint && (
                  <div className="grid grid-cols-2 gap-2 pt-2">
                    <div>
                      <label className={`${LH_LABEL} text-[11px]`}>Section ID</label>
                      <input
                        type="number"
                        placeholder="e.g. 101"
                        value={sectionId}
                        onChange={(e) => setSectionId(e.target.value)}
                        className={`${LH_INPUT} mt-1 h-8 text-xs`}
                      />
                    </div>
                    <div>
                      <label className={`${LH_LABEL} text-[11px]`}>Section Name (e.g. 10-A)</label>
                      <input
                        type="text"
                        placeholder="e.g. Grade 10 - Section A"
                        value={sectionName}
                        onChange={(e) => setSectionName(e.target.value)}
                        className={`${LH_INPUT} mt-1 h-8 text-xs`}
                      />
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Expiry Date (Optional) */}
            <div className="space-y-1 pt-1">
              <label className={`${LH_LABEL} text-xs flex items-center gap-1.5`}>
                <Calendar className="w-3.5 h-3.5 text-muted-foreground" />
                Assignment Expiration Date (Optional)
              </label>
              <input
                type="date"
                value={expiresAt}
                onChange={(e) => setExpiresAt(e.target.value)}
                className={`${LH_INPUT} h-9 text-xs`}
              />
              <p className="text-[10px] text-muted-foreground">
                Leave blank for permanent assignment until manually revoked.
              </p>
            </div>
          </div>

          <DialogFooter className="p-4 px-6 border-t border-border/60 bg-muted/10 flex items-center justify-end gap-2">
            <button
              type="button"
              onClick={() => onOpenChange(false)}
              className={`${LH_SECONDARY_BUTTON} h-9 px-4 text-xs`}
              disabled={isSubmitting}
            >
              Cancel
            </button>
            <button
              type="submit"
              className={`${LH_PRIMARY_BUTTON} h-9 px-5 text-xs font-semibold`}
              disabled={isSubmitting}
            >
              {isSubmitting ? 'Assigning...' : 'Confirm Assignment'}
            </button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
