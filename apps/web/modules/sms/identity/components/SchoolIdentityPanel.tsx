'use client'

/**
 * A person's SCHOOL identity, shown on their Learnhouse user record.
 *
 * Before this existed, an SMS "student" was an integer `user.id` in
 * `SMSUserRole` and Learnhouse's user management knew nothing about it —
 * same `user` table, no shared UI, and no way at all to grant a school role
 * except raw SQL. This closes that: you make someone a Teacher where you
 * already manage them, not in a separate window.
 *
 * Deliberately NOT a new destination — it renders inside the existing
 * per-user modal on the Users tab, next to the analytics dossier.
 */

import { useCallback, useMemo, useState } from 'react'
import { GraduationCap, Link2, Trash2, UserCog } from 'lucide-react'
import { DataTable, EmptyState, SectionCard, StatusChip } from '@/components/widgets'
import { ApiError } from '@/lib/api/api-client'
import { useApiResource } from '@/lib/api/useApiResource'
import { listCampuses } from '@/modules/sms/campus/api'
import {
  assignSchoolRole,
  linkGuardian,
  listGuardianLinks,
  listSchoolRoles,
  revokeSchoolRole,
  unlinkGuardian,
} from '../api'
import { SCHOOL_ROLES, SCHOOL_ROLE_LABELS, type SchoolRole } from '../types'

export interface SchoolIdentityPanelProps {
  userId: number
  orgId: number
  /** For the heading, so an admin can see who they're editing. */
  userLabel?: string
  /** False for non-managers: the panel stays readable but read-only. */
  canManage?: boolean
}

const ROLE_TONE: Partial<Record<SchoolRole, 'positive' | 'caution' | 'info' | 'neutral'>> = {
  SUPER_ADMIN: 'caution',
  SCHOOL_ADMIN: 'caution',
  TEACHER: 'positive',
  STUDENT: 'info',
  PARENT: 'info',
}

function errorText(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.kind === 'permission_denied') return 'You need school-admin access to change this.'
    if (err.status === 409) return 'That link already exists.'
    if (err.kind === 'not_found') return 'That user could not be found.'
    return err.message
  }
  return 'Something went wrong. Try again.'
}

export function SchoolIdentityPanel({ userId, orgId, userLabel, canManage = true }: SchoolIdentityPanelProps) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [newRole, setNewRole] = useState<SchoolRole>('STUDENT')
  const [newCampusId, setNewCampusId] = useState<string>('')
  const [linkStudentId, setLinkStudentId] = useState<string>('')
  const [linkRelationship, setLinkRelationship] = useState<string>('')

  const roles = useApiResource(
    () => listSchoolRoles({ userId, orgId }),
    [userId, orgId],
    { isEmpty: (d) => d.filter((r) => r.is_active).length === 0 }
  )

  // Revoked grants stay in the table (soft delete) — filter to what's live.
  const activeRoles = useMemo(() => (roles.data ?? []).filter((r) => r.is_active), [roles.data])
  const isParent = activeRoles.some((r) => r.role === 'PARENT')
  const isStudent = activeRoles.some((r) => r.role === 'STUDENT')

  const campuses = useApiResource(() => listCampuses({ orgId, isActive: true }), [orgId], {
    isEmpty: (d) => d.length === 0,
  })

  // A parent's links are their children; a student's are their guardians.
  const guardianLinks = useApiResource(
    () => (isParent ? listGuardianLinks({ guardianUserId: userId }) : listGuardianLinks({ studentId: userId })),
    [userId, isParent],
    { skip: !isParent && !isStudent, isEmpty: (d) => d.length === 0 }
  )

  const refreshAll = useCallback(() => {
    roles.refetch()
    guardianLinks.refetch()
  }, [roles, guardianLinks])

  const handleAssign = useCallback(async () => {
    setBusy(true)
    setError(null)
    try {
      await assignSchoolRole({
        user_id: userId,
        org_id: orgId,
        role: newRole,
        campus_id: newCampusId ? Number(newCampusId) : null,
      })
      refreshAll()
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(false)
    }
  }, [userId, orgId, newRole, newCampusId, refreshAll])

  const handleRevoke = useCallback(
    async (roleId: number) => {
      setBusy(true)
      setError(null)
      try {
        await revokeSchoolRole(roleId)
        refreshAll()
      } catch (err) {
        setError(errorText(err))
      } finally {
        setBusy(false)
      }
    },
    [refreshAll]
  )

  const handleLink = useCallback(async () => {
    const targetId = Number(linkStudentId)
    if (!Number.isInteger(targetId) || targetId <= 0) {
      setError('Enter a valid user ID.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      await linkGuardian(
        isParent
          ? { guardian_user_id: userId, student_id: targetId, relationship: linkRelationship || null }
          : { guardian_user_id: targetId, student_id: userId, relationship: linkRelationship || null }
      )
      setLinkStudentId('')
      setLinkRelationship('')
      guardianLinks.refetch()
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(false)
    }
  }, [linkStudentId, linkRelationship, isParent, userId, guardianLinks])

  const handleUnlink = useCallback(
    async (linkId: number) => {
      setBusy(true)
      setError(null)
      try {
        await unlinkGuardian(linkId)
        guardianLinks.refetch()
      } catch (err) {
        setError(errorText(err))
      } finally {
        setBusy(false)
      }
    },
    [guardianLinks]
  )

  const campusName = useCallback(
    (id: number | null) => (id === null ? 'All campuses' : campuses.data?.find((c) => c.id === id)?.name ?? `Campus #${id}`),
    [campuses.data]
  )

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h3 className="text-base font-bold text-gray-800">School identity</h3>
        <p className="text-sm text-gray-500">
          {userLabel
            ? `What ${userLabel} is at school — separate from their Learnhouse role.`
            : 'What this person is at school — separate from their Learnhouse role.'}
        </p>
      </div>

      {error && (
        <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">
          {error}
        </p>
      )}

      {/* Controls live OUTSIDE SectionCard on purpose: SectionCard renders
          children only when state === 'success', so a person with no roles
          yet would otherwise lose the very form needed to give them one. */}
      {canManage && (
        <div className="flex flex-wrap items-end gap-3 rounded-xl bg-gray-50 p-4">
          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-medium text-gray-500">School role</span>
            <select
              id="school-identity-role"
              className="px-3 py-2 bg-white nice-shadow rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-black focus:ring-offset-2 border-0"
              value={newRole}
              onChange={(e) => setNewRole(e.target.value as SchoolRole)}
            >
              {SCHOOL_ROLES.map((r) => (
                <option key={r} value={r}>
                  {SCHOOL_ROLE_LABELS[r]}
                </option>
              ))}
            </select>
          </label>

          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-medium text-gray-500">Campus</span>
            <select
              id="school-identity-campus"
              className="px-3 py-2 bg-white nice-shadow rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-black focus:ring-offset-2 border-0"
              value={newCampusId}
              onChange={(e) => setNewCampusId(e.target.value)}
            >
              <option value="">All campuses</option>
              {(campuses.data ?? []).map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>

          <button
            type="button"
            onClick={handleAssign}
            disabled={busy}
            className="inline-flex h-9 items-center gap-1.5 rounded-md bg-foreground px-3 text-sm font-medium text-background transition-opacity disabled:opacity-50"
          >
            <UserCog className="size-4" />
            {busy ? 'Saving…' : 'Grant role'}
          </button>
        </div>
      )}

      <SectionCard
        title="School roles"
        icon={<GraduationCap className="size-4 text-gray-500" />}
        state={roles.status}
        error={roles.error}
        onRetry={roles.refetch}
        emptyTitle="No school role yet"
        emptyDescription={
          canManage
            ? 'This person is a Learnhouse user but not yet part of the school. Grant a role above.'
            : 'This person is a Learnhouse user but not yet part of the school.'
        }
      >
        <DataTable
          rows={activeRoles}
          rowKey={(row) => row.id}
          state="success"
          columns={[
            {
              key: 'role',
              header: 'Role',
              render: (r) => <StatusChip label={SCHOOL_ROLE_LABELS[r.role]} tone={ROLE_TONE[r.role] ?? 'neutral'} />,
            },
            { key: 'campus', header: 'Campus', render: (r) => campusName(r.campus_id) },
            ...(canManage
              ? [
                  {
                    key: 'actions',
                    header: '',
                    align: 'right' as const,
                    render: (r: (typeof activeRoles)[number]) => (
                      <button
                        type="button"
                        onClick={() => handleRevoke(r.id)}
                        disabled={busy}
                        className="inline-flex items-center gap-1 text-xs text-gray-500 transition-colors hover:text-rose-600 disabled:opacity-50"
                      >
                        <Trash2 className="size-3.5" />
                        Revoke
                      </button>
                    ),
                  },
                ]
              : []),
          ]}
        />
      </SectionCard>

      {(isParent || isStudent) && (
        <>
          {canManage && (
            <div className="flex flex-wrap items-end gap-3 rounded-xl bg-gray-50 p-4">
              <label className="flex flex-col gap-1.5">
                <span className="text-xs font-medium text-gray-500">
                  {isParent ? "Child's user ID" : "Guardian's user ID"}
                </span>
                <input
                  id="school-identity-link-id"
                  type="number"
                  min={1}
                  className="w-40 px-3 py-2 bg-white nice-shadow rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-black focus:ring-offset-2 border-0"
                  value={linkStudentId}
                  onChange={(e) => setLinkStudentId(e.target.value)}
                  placeholder="e.g. 42"
                />
              </label>
              <label className="flex flex-col gap-1.5">
                <span className="text-xs font-medium text-gray-500">Relationship</span>
                <input
                  id="school-identity-link-rel"
                  type="text"
                  className="w-40 px-3 py-2 bg-white nice-shadow rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-black focus:ring-offset-2 border-0"
                  value={linkRelationship}
                  onChange={(e) => setLinkRelationship(e.target.value)}
                  placeholder="Mother, Father…"
                />
              </label>
              <button
                type="button"
                onClick={handleLink}
                disabled={busy}
                className="inline-flex h-9 items-center gap-1.5 rounded-md bg-foreground px-3 text-sm font-medium text-background transition-opacity disabled:opacity-50"
              >
                <Link2 className="size-4" />
                {busy ? 'Saving…' : 'Link'}
              </button>
            </div>
          )}

          <SectionCard
            title={isParent ? 'Children' : 'Guardians'}
            icon={<Link2 className="size-4 text-gray-500" />}
            state={guardianLinks.status}
            error={guardianLinks.error}
            onRetry={guardianLinks.refetch}
            emptyTitle={isParent ? 'No children linked' : 'No guardians linked'}
            emptyDescription={
              isParent
                ? "Link a child so this parent can see their attendance, grades and fees."
                : "Link a guardian so they can see this student's attendance, grades and fees."
            }
          >
            <DataTable
              rows={guardianLinks.data ?? []}
              rowKey={(row) => row.id}
              state="success"
              columns={[
                {
                  key: 'person',
                  header: isParent ? 'Child' : 'Guardian',
                  // The API returns ids only — no embedded name. Showing the
                  // id is honest; inventing a name would not be.
                  render: (r) => `User #${isParent ? r.student_id : r.guardian_user_id}`,
                },
                { key: 'rel', header: 'Relationship', render: (r) => r.relationship || '—' },
                {
                  key: 'primary',
                  header: 'Primary contact',
                  render: (r) => (r.is_primary_contact ? <StatusChip label="Primary" tone="info" /> : '—'),
                },
                ...(canManage
                  ? [
                      {
                        key: 'actions',
                        header: '',
                        align: 'right' as const,
                        render: (r: { id: number }) => (
                          <button
                            type="button"
                            onClick={() => handleUnlink(r.id)}
                            disabled={busy}
                            className="inline-flex items-center gap-1 text-xs text-gray-500 transition-colors hover:text-rose-600 disabled:opacity-50"
                          >
                            <Trash2 className="size-3.5" />
                            Unlink
                          </button>
                        ),
                      },
                    ]
                  : []),
              ]}
            />
          </SectionCard>
        </>
      )}

      {campuses.status === 'empty' && (
        <EmptyState
          tone="caution"
          title="No campuses exist yet"
          description="Roles can still be granted org-wide, but campus-scoped roles need a campus first."
        />
      )}
    </div>
  )
}

export default SchoolIdentityPanel
