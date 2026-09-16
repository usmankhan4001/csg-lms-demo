'use client'

/**
 * Creating the people a school runs on.
 *
 * `RoleManagementPanel` next door can only GRANT a role to somebody who
 * already has an account, and nothing in the product could create that
 * account: the only signup paths require the person themselves to choose a
 * password. For an online school that meant a new teacher could not be
 * onboarded without database access. This screen is where they are created.
 *
 * No password appears anywhere on this screen, by design. The backend stores
 * an unusable hash and the person sets their own through password reset, so
 * there is nothing to display, copy or email — and no shared default across a
 * cohort, which is the failure this avoids.
 */

import React, { useMemo, useState } from 'react'
import {
  AlertCircle,
  CheckCircle2,
  Download,
  MailWarning,
  RefreshCw,
  Send,
  UploadCloud,
  UserPlus,
  Users,
} from 'lucide-react'
import {
  DataTable,
  EmptyState,
  LH_INPUT,
  LH_PRIMARY_BUTTON,
  LH_SECONDARY_BUTTON,
  SchoolDialog,
  SchoolField,
  SectionCard,
  StatGrid,
  StatusChip,
} from '@/components/widgets'
import { useApiResource } from '@/lib/api/useApiResource'
import { useSchoolSession } from '@/lib/api/useSchoolSession'
import { listAcademicYears, listCampuses, listClassSections } from '@/modules/sms/campus/api'
import {
  bulkProvisionPeople,
  listSchoolDirectory,
  listSchoolInvites,
  provisionPerson,
  resendPendingInvites,
  resendSchoolInvite,
} from '../api'
import { CSV_TEMPLATE, parseProvisioningCsv, type CsvParseRow } from '../csv'
import type {
  BulkProvisionResult,
  DirectoryEntry,
  SchoolInvite,
  ProvisionPersonPayload,
  ProvisionableRole,
} from '../types'
import { DataExportToolbar } from '@/components/ems/DataExportToolbar'
import type { ExportColumn } from '@/lib/export/data-export'

const PROVISIONABLE_ROLES: { key: ProvisionableRole; label: string; desc: string }[] = [
  { key: 'TEACHER', label: 'Teacher', desc: 'Takes roll call, enters grades, hosts live classes' },
  { key: 'STUDENT', label: 'Student', desc: 'Attends classes, sees their timetable and results' },
  { key: 'PARENT', label: 'Parent / Guardian', desc: 'Sees their own children only' },
  { key: 'STAFF', label: 'Staff', desc: 'Back-office and operations' },
  { key: 'PSYCHOLOGIST', label: 'Counsellor', desc: 'Pastoral and counselling records' },
  { key: 'SCHOOL_ADMIN', label: 'School Admin', desc: 'Runs the school: settings, timetables, enrolment' },
]

type Banner = { type: 'success' | 'error'; text: string }

function roleLabel(role: string) {
  return PROVISIONABLE_ROLES.find((r) => r.key === role)?.label ?? role
}

export function PeopleProvisioningPanel({ orgId }: { orgId: number }) {
  const { session } = useSchoolSession()
  const [reloadKey, setReloadKey] = useState(0)
  const [banner, setBanner] = useState<Banner | null>(null)
  const [unassignedOnly, setUnassignedOnly] = useState(false)
  const [search, setSearch] = useState('')

  const campuses = useApiResource(() => listCampuses({ orgId, isActive: true }), [orgId], {
    isEmpty: (d) => d.length === 0,
  })
  const campusId = session?.campus_id ?? campuses.data?.[0]?.id

  const directory = useApiResource(
    () => listSchoolDirectory({ unassigned_only: unassignedOnly || undefined }),
    [unassignedOnly, reloadKey],
    { isEmpty: (d) => d.length === 0 }
  )

  // --- outstanding invitations ---------------------------------------------
  // The screen that answers "who have we created an account for who still
  // cannot get in?" -- which, before invitations existed, was everybody.
  const invites = useApiResource(() => listSchoolInvites(), [reloadKey], {
    isEmpty: (d) => d.length === 0,
  })
  const [resendingId, setResendingId] = useState<number | null>(null)
  const [resendingAll, setResendingAll] = useState(false)

  const outstanding = (invites.data ?? []).filter(
    (i) => i.status !== 'ACCEPTED' && i.status !== 'REVOKED'
  )

  async function handleResendOne(userId: number) {
    setResendingId(userId)
    try {
      const updated = await resendSchoolInvite(userId)
      setBanner(
        updated.status === 'PENDING'
          ? { type: 'success', text: `A fresh invitation is on its way to ${updated.subject_email}. The previous link no longer works.` }
          : {
              type: 'error',
              text: `Could not deliver to ${updated.subject_email}${
                updated.delivery_error ? ` — ${updated.delivery_error}` : ''
              }. Check the address is right.`,
            }
      )
      setReloadKey((k) => k + 1)
    } catch (err: any) {
      setBanner({ type: 'error', text: err?.message || 'Could not resend that invitation.' })
    } finally {
      setResendingId(null)
    }
  }

  async function handleResendAll() {
    setResendingAll(true)
    try {
      const result = await resendPendingInvites()
      setBanner({
        // Reported as two numbers, never one: "chased 50" would hide the three
        // addresses that still are not reachable.
        type: result.failed > 0 ? 'error' : 'success',
        text:
          result.failed > 0
            ? `${result.sent} invitation${result.sent === 1 ? '' : 's'} resent, ${result.failed} still could not be delivered.`
            : `${result.sent} invitation${result.sent === 1 ? '' : 's'} resent.`,
      })
      setReloadKey((k) => k + 1)
    } catch (err: any) {
      setBanner({ type: 'error', text: err?.message || 'Could not resend the outstanding invitations.' })
    } finally {
      setResendingAll(false)
    }
  }

  // --- single-person dialog -------------------------------------------------
  const [addOpen, setAddOpen] = useState(false)
  const [form, setForm] = useState<{
    role: ProvisionableRole
    email: string
    first_name: string
    last_name: string
    section_id: string
    academic_year_id: string
    roll_number: string
    child_student_id: string
    relationship: string
  }>({
    role: 'TEACHER',
    email: '',
    first_name: '',
    last_name: '',
    section_id: '',
    academic_year_id: '',
    roll_number: '',
    child_student_id: '',
    relationship: '',
  })
  const [submitting, setSubmitting] = useState(false)

  const years = useApiResource(() => listAcademicYears(campusId as number, true), [campusId], {
    skip: campusId === undefined,
    isEmpty: (d) => d.length === 0,
  })
  const sections = useApiResource(
    () => listClassSections(campusId as number, { isActive: true }),
    [campusId],
    { skip: campusId === undefined, isEmpty: (d) => d.length === 0 }
  )

  const students = useMemo(
    () => (directory.data ?? []).filter((e) => e.roles.includes('STUDENT')),
    [directory.data]
  )

  const set = <K extends keyof typeof form>(key: K, value: (typeof form)[K]) =>
    setForm((f) => ({ ...f, [key]: value }))

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitting(true)
    setBanner(null)
    try {
      const payload: ProvisionPersonPayload = {
        role: form.role,
        email: form.email.trim(),
        first_name: form.first_name.trim(),
        last_name: form.last_name.trim() || undefined,
        campus_id: campusId,
      }
      if (form.role === 'STUDENT' && form.section_id && form.academic_year_id) {
        payload.section_id = Number(form.section_id)
        payload.academic_year_id = Number(form.academic_year_id)
        payload.roll_number = form.roll_number.trim() || undefined
      }
      if (form.role === 'PARENT' && form.child_student_id) {
        payload.child_student_id = Number(form.child_student_id)
        payload.relationship = form.relationship.trim() || undefined
      }

      const result = await provisionPerson(payload)
      // Says what actually happened rather than always claiming a new account:
      // re-submitting an existing address attaches the role instead.
      // An account created whose invite bounced is NOT a success: that person
      // cannot sign in and nobody would know to chase them. Say so plainly
      // rather than reporting a green banner over a stranded family.
      const inviteOk = result.invite_status === 'PENDING'
      const inviteWithheld = result.invite_status === 'NOT_SENT'
      const madeAccount = result.created_user
        ? `Created ${result.email} as ${roleLabel(result.role)}.`
        : `${result.email} already had an account. ${
            result.created_role ? `Added the ${roleLabel(result.role)} role.` : 'They already had this role.'
          }`

      if (inviteOk) {
        setBanner({
          type: 'success',
          text: `${madeAccount} An invitation is on its way — they choose their own password from the link, so none was set for them.`,
        })
      } else if (inviteWithheld) {
        setBanner({
          type: 'success',
          text: `${madeAccount} No invitation was sent yet, so they cannot sign in until you send one.`,
        })
      } else {
        setBanner({
          type: 'error',
          text: `${madeAccount} But the invitation could not be sent${
            result.invite_error ? ` (${result.invite_error})` : ''
          }, so they cannot sign in yet. Resend it from “Not signed in yet” below.`,
        })
      }
      setAddOpen(false)
      setForm((f) => ({
        ...f,
        email: '',
        first_name: '',
        last_name: '',
        roll_number: '',
        child_student_id: '',
        relationship: '',
      }))
      setReloadKey((k) => k + 1)
    } catch (err: any) {
      setBanner({ type: 'error', text: err?.message || 'Could not create this account.' })
    } finally {
      setSubmitting(false)
    }
  }

  // --- bulk import ----------------------------------------------------------
  const [importOpen, setImportOpen] = useState(false)
  const [csvText, setCsvText] = useState('')
  const [importing, setImporting] = useState(false)
  const [importResult, setImportResult] = useState<BulkProvisionResult | null>(null)
  const [csvFatal, setCsvFatal] = useState<string | null>(null)
  const [clientRejects, setClientRejects] = useState<CsvParseRow[]>([])

  const handleImport = async (e: React.FormEvent) => {
    e.preventDefault()
    setCsvFatal(null)
    setImportResult(null)
    setClientRejects([])

    const parsed = parseProvisioningCsv(csvText, campusId)
    if (parsed.fatal) {
      setCsvFatal(parsed.fatal)
      return
    }
    const sendable = parsed.rows.filter((r) => r.payload)
    const rejected = parsed.rows.filter((r) => !r.payload)
    setClientRejects(rejected)

    if (sendable.length === 0) {
      setCsvFatal('Every row has a problem — nothing was sent. Fix the rows listed below and try again.')
      return
    }

    setImporting(true)
    try {
      const result = await bulkProvisionPeople(sendable.map((r) => r.payload!))
      // Remap the API's row indices (into what we SENT) back onto the
      // administrator's own line numbers, or "row 2 failed" would point at the
      // wrong line in their spreadsheet whenever an earlier row was rejected
      // here rather than server-side.
      setImportResult({
        ...result,
        results: result.results.map((r) => ({
          ...r,
          row: sendable[r.row]?.line ?? r.row,
        })),
      })
      setReloadKey((k) => k + 1)
    } catch (err: any) {
      setCsvFatal(err?.message || 'The import could not be sent.')
    } finally {
      setImporting(false)
    }
  }

  const entries = (directory.data ?? []).filter((e) => {
    if (!search.trim()) return true
    const q = search.toLowerCase()
    return (
      (e.name ?? '').toLowerCase().includes(q) ||
      (e.email ?? '').toLowerCase().includes(q) ||
      String(e.user_id).includes(q)
    )
  })

  const totalPeople = directory.data?.length ?? 0
  const withoutRole = (directory.data ?? []).filter((e) => e.roles.length === 0).length

  const peopleExportColumns: ExportColumn<DirectoryEntry>[] = useMemo(
    () => [
      { key: 'user_id', label: 'User ID', type: 'number' },
      { key: 'name', label: 'Name', type: 'text' },
      { key: 'email', label: 'Email', type: 'masked_pii', formatOptions: { piiType: 'email' } },
      {
        key: 'roles',
        label: 'Roles',
        type: 'text',
        accessor: (r) => (r.roles.length > 0 ? r.roles.map(roleLabel).join(', ') : 'No role'),
      },
      {
        key: 'status',
        label: 'Status',
        type: 'text',
        accessor: (r) => (r.roles.length === 0 ? 'Unassigned' : 'Active'),
      },
    ],
    []
  )

  return (
    <div className="space-y-6">
      {banner && (
        <div
          id="provisioning-banner"
          className={`flex items-start gap-3 p-4 rounded-xl text-sm font-medium ${
            banner.type === 'success'
              ? 'bg-emerald-500/10 text-emerald-700 border border-emerald-500/20'
              : 'bg-rose-500/10 text-rose-700 border border-rose-500/20'
          }`}
        >
          {banner.type === 'success' ? (
            <CheckCircle2 className="w-5 h-5 shrink-0 mt-0.5" />
          ) : (
            <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
          )}
          <span>{banner.text}</span>
        </div>
      )}

      <StatGrid
        columns={2}
        skeletonCount={2}
        state={directory.status === 'loading' ? 'loading' : 'success'}
        items={[
          { label: 'People at this school', value: String(totalPeople), icon: Users },
          {
            label: 'No role yet',
            value: String(withoutRole),
            icon: AlertCircle,
            tone: withoutRole > 0 ? 'caution' : 'neutral',
            hint: withoutRole > 0 ? 'These accounts exist but can do nothing' : undefined,
          },
        ]}
      />

      <SectionCard
        id="school-people"
        title="People"
        description="Everyone with an account at this school, and the roles they hold."
        icon={<Users className="size-4 text-gray-500" />}
        state={directory.status}
        error={directory.error}
        onRetry={directory.refetch}
        emptyTitle="Nobody here yet"
        emptyDescription="Create the first teacher or student account to get started."
        action={
          <div className="flex flex-wrap items-center gap-2">
            {entries.length > 0 && (
              <DataExportToolbar
                data={entries}
                columns={peopleExportColumns}
                filenamePrefix="school_people_directory"
                title="School People Directory"
                activeFilters={{ unassignedOnly, search }}
                classification="RESTRICTED"
              />
            )}
            <button
              id="people-refresh"
              type="button"
              onClick={() => setReloadKey((k) => k + 1)}
              className={`${LH_SECONDARY_BUTTON} gap-2`}
              title="Refresh"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
            <button
              id="people-import-open"
              type="button"
              onClick={() => setImportOpen(true)}
              className={`${LH_SECONDARY_BUTTON} gap-2`}
            >
              <UploadCloud className="w-4 h-4" />
              <span>Import a list</span>
            </button>
            <button
              id="people-add-open"
              type="button"
              onClick={() => setAddOpen(true)}
              className={`${LH_PRIMARY_BUTTON} gap-2`}
            >
              <UserPlus className="w-4 h-4" />
              <span>Add a person</span>
            </button>
          </div>
        }
      >
        <div className="flex flex-wrap items-center gap-3 mb-4">
          <input
            id="people-search"
            type="text"
            placeholder="Search by name, email or ID"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className={`${LH_INPUT} max-w-xs`}
          />
          <label className="flex items-center gap-2 text-sm text-gray-600">
            <input
              id="people-unassigned-only"
              type="checkbox"
              checked={unassignedOnly}
              onChange={(e) => setUnassignedOnly(e.target.checked)}
            />
            <span>Only people with no role</span>
          </label>
        </div>

        {entries.length === 0 && directory.status === 'success' ? (
          <EmptyState
            icon={Users}
            title="Nobody matches that"
            description="Clear the search, or the filter, to see everyone again."
          />
        ) : (
          <DataTable<DirectoryEntry>
            columns={[
              { key: 'name', header: 'Name', render: (r) => r.name || 'Unnamed' },
              { key: 'email', header: 'Email', render: (r) => r.email || '—' },
              {
                key: 'roles',
                header: 'Roles',
                render: (r) =>
                  r.roles.length === 0 ? (
                    // Not "Student", not blank: an account that can do nothing
                    // is a thing the administrator needs to see and act on.
                    <StatusChip tone="caution" label="No role yet" />
                  ) : (
                    <span className="flex flex-wrap gap-1">
                      {r.roles.map((role) => (
                        <StatusChip key={role} tone="positive" label={roleLabel(role)} />
                      ))}
                    </span>
                  ),
              },
              {
                key: 'campus',
                header: 'Campus',
                render: (r) => (r.campus_id ? `Campus #${r.campus_id}` : 'All campuses'),
              },
            ]}
            rows={entries}
            rowKey={(r) => r.user_id}
            state={directory.status}
            error={directory.error}
            onRetry={directory.refetch}
            totalLabel={`${entries.length} of ${totalPeople}`}
          />
        )}
      </SectionCard>

      {/* ---------------------------------------------------------------- */}
      {/* An account without a delivered invitation is an account nobody can
          use. This is where an administrator sees exactly who that is, on the
          day -- rather than discovering it in September when a parent says
          they never got in. */}
      <SectionCard
        id="school-invites"
        title="Not signed in yet"
        description="People with an account who still have an outstanding invitation."
        icon={<MailWarning className="size-4 text-gray-500" />}
        state={invites.status}
        error={invites.error}
        onRetry={invites.refetch}
        emptyTitle="Everyone is in"
        emptyDescription="Every invitation that has been sent has been accepted."
        action={
          outstanding.length > 0 ? (
            <button
              type="button"
              id="invites-resend-all"
              onClick={handleResendAll}
              disabled={resendingAll}
              className={`${LH_SECONDARY_BUTTON} gap-2`}
            >
              <Send className="w-4 h-4" />
              <span>{resendingAll ? 'Resending…' : `Resend all ${outstanding.length}`}</span>
            </button>
          ) : null
        }
      >
        {outstanding.length === 0 && invites.status === 'success' ? (
          <EmptyState
            icon={CheckCircle2}
            title="Everyone is in"
            description="Every invitation that has been sent has been accepted."
          />
        ) : (
          <DataTable<SchoolInvite>
            columns={[
              { key: 'subject_email', header: 'Email', render: (r) => r.subject_email },
              {
                key: 'subject_role',
                header: 'Role',
                render: (r) => <StatusChip tone="neutral" label={roleLabel(r.subject_role)} />,
              },
              {
                key: 'status',
                header: 'Invitation',
                render: (r) => {
                  if (r.status === 'PENDING') {
                    return <StatusChip tone="caution" label="Sent, not accepted" />
                  }
                  if (r.status === 'NOT_SENT') {
                    return <StatusChip tone="caution" label="Not sent yet" />
                  }
                  // DELIVERY_FAILED and UNKNOWN both mean "do not assume this
                  // person received anything". Shown as problems, never as
                  // quietly-pending.
                  return (
                    <span className="flex flex-col gap-0.5">
                      <StatusChip
                        tone="critical"
                        label={r.status === 'UNKNOWN' ? 'Delivery unconfirmed' : 'Delivery failed'}
                      />
                      {r.delivery_error && (
                        <span className="text-xs text-rose-700">{r.delivery_error}</span>
                      )}
                    </span>
                  )
                },
              },
              {
                key: 'last_sent_at',
                header: 'Last sent',
                render: (r) =>
                  // Never sent is not "today", and not blank.
                  r.last_sent_at ? new Date(r.last_sent_at).toLocaleDateString() : '—',
              },
              {
                key: 'sent_count',
                header: 'Times sent',
                render: (r) => String(r.sent_count ?? 0),
              },
              {
                key: 'resend',
                header: '',
                render: (r) => (
                  <button
                    type="button"
                    id={`invite-resend-${r.subject_user_id}`}
                    onClick={() => handleResendOne(r.subject_user_id)}
                    disabled={resendingId === r.subject_user_id}
                    className={`${LH_SECONDARY_BUTTON} gap-2`}
                  >
                    <RefreshCw className="w-3.5 h-3.5" />
                    <span>{resendingId === r.subject_user_id ? 'Sending…' : 'Resend'}</span>
                  </button>
                ),
              },
            ]}
            rows={outstanding}
            rowKey={(r) => r.id}
          />
        )}
      </SectionCard>

      {/* ---------------------------------------------------------------- */}
      <SchoolDialog
        open={addOpen}
        onOpenChange={setAddOpen}
        title="Add a person"
        description="Creates their account and grants the role together. No password is set — they choose their own the first time they sign in."
      >
        <form onSubmit={handleAdd} className="space-y-4">
          <SchoolField id="prov-role" label="Role" help="What this person will be able to do.">
            <select
              id="prov-role"
              value={form.role}
              onChange={(e) => set('role', e.target.value as ProvisionableRole)}
              className={LH_INPUT}
            >
              {PROVISIONABLE_ROLES.map((r) => (
                <option key={r.key} value={r.key}>
                  {r.label} — {r.desc}
                </option>
              ))}
            </select>
          </SchoolField>

          <SchoolField id="prov-email" label="Email" help="How they sign in, and where their password-setup link goes.">
            <input
              id="prov-email"
              type="email"
              required
              value={form.email}
              onChange={(e) => set('email', e.target.value)}
              placeholder="name@example.com"
              className={LH_INPUT}
            />
          </SchoolField>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <SchoolField id="prov-first" label="First name">
              <input
                id="prov-first"
                required
                value={form.first_name}
                onChange={(e) => set('first_name', e.target.value)}
                className={LH_INPUT}
              />
            </SchoolField>
            <SchoolField id="prov-last" label="Last name">
              <input
                id="prov-last"
                value={form.last_name}
                onChange={(e) => set('last_name', e.target.value)}
                className={LH_INPUT}
              />
            </SchoolField>
          </div>

          {form.role === 'STUDENT' && (
            <div className="rounded-xl border border-gray-200 p-4 space-y-4">
              <p className="text-xs text-gray-500">
                Place them in a class now. A student who is not enrolled will not appear in
                attendance, the gradebook or fees.
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <SchoolField id="prov-section" label="Class section">
                  <select
                    id="prov-section"
                    value={form.section_id}
                    onChange={(e) => set('section_id', e.target.value)}
                    className={LH_INPUT}
                  >
                    <option value="">Not yet</option>
                    {(sections.data ?? []).map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.grade_level} {s.section_name}
                      </option>
                    ))}
                  </select>
                </SchoolField>
                <SchoolField id="prov-year" label="Academic year">
                  <select
                    id="prov-year"
                    value={form.academic_year_id}
                    onChange={(e) => set('academic_year_id', e.target.value)}
                    className={LH_INPUT}
                  >
                    <option value="">Not yet</option>
                    {(years.data ?? []).map((y) => (
                      <option key={y.id} value={y.id}>
                        {y.name}
                      </option>
                    ))}
                  </select>
                </SchoolField>
              </div>
              <SchoolField id="prov-roll" label="Roll number" help="Optional.">
                <input
                  id="prov-roll"
                  value={form.roll_number}
                  onChange={(e) => set('roll_number', e.target.value)}
                  className={LH_INPUT}
                />
              </SchoolField>
              {Boolean(form.section_id) !== Boolean(form.academic_year_id) && (
                <p className="text-xs text-rose-600">
                  Pick both a section and a year, or neither — one without the other cannot place
                  the student.
                </p>
              )}
            </div>
          )}

          {form.role === 'PARENT' && (
            <div className="rounded-xl border border-gray-200 p-4 space-y-4">
              <p className="text-xs text-gray-500">
                Link them to a child now. A parent account with no child linked can see nothing at
                all.
              </p>
              <SchoolField id="prov-child" label="Child">
                <select
                  id="prov-child"
                  value={form.child_student_id}
                  onChange={(e) => set('child_student_id', e.target.value)}
                  className={LH_INPUT}
                >
                  <option value="">Not yet</option>
                  {students.map((s) => (
                    <option key={s.user_id} value={s.user_id}>
                      {s.name || s.email || `#${s.user_id}`}
                    </option>
                  ))}
                </select>
              </SchoolField>
              <SchoolField id="prov-relationship" label="Relationship" help="Optional, e.g. mother.">
                <input
                  id="prov-relationship"
                  value={form.relationship}
                  onChange={(e) => set('relationship', e.target.value)}
                  className={LH_INPUT}
                />
              </SchoolField>
            </div>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              id="prov-cancel"
              onClick={() => setAddOpen(false)}
              className={LH_SECONDARY_BUTTON}
              disabled={submitting}
            >
              Cancel
            </button>
            <button type="submit" id="prov-submit" className={LH_PRIMARY_BUTTON} disabled={submitting}>
              {submitting ? 'Creating…' : 'Create account'}
            </button>
          </div>
        </form>
      </SchoolDialog>

      {/* ---------------------------------------------------------------- */}
      <SchoolDialog
        open={importOpen}
        onOpenChange={setImportOpen}
        title="Import a list of people"
        description="Paste a CSV. Every row is reported back individually, so a row that fails names itself rather than hiding in a total."
      >
        <form onSubmit={handleImport} className="space-y-4">
          <SchoolField
            id="csv-text"
            label="CSV"
            help="First line is the header. role, email and first_name are required; the rest are optional."
          >
            <textarea
              id="csv-text"
              value={csvText}
              onChange={(e) => setCsvText(e.target.value)}
              rows={8}
              spellCheck={false}
              placeholder={CSV_TEMPLATE}
              className={`${LH_INPUT} font-mono text-xs`}
            />
          </SchoolField>

          <button
            type="button"
            id="csv-template"
            onClick={() => setCsvText(CSV_TEMPLATE)}
            className={`${LH_SECONDARY_BUTTON} gap-2`}
          >
            <Download className="w-4 h-4" />
            <span>Fill in the template</span>
          </button>

          {csvFatal && (
            <p id="csv-fatal" className="text-sm text-rose-600">
              {csvFatal}
            </p>
          )}

          {clientRejects.length > 0 && (
            <div className="rounded-xl border border-amber-300 bg-amber-50 p-3">
              <p className="text-xs font-semibold text-amber-800 mb-2">
                {clientRejects.length} row{clientRejects.length === 1 ? '' : 's'} not sent:
              </p>
              <ul className="space-y-1 text-xs text-amber-900">
                {clientRejects.map((r) => (
                  <li key={r.line}>
                    <span className="font-mono">Line {r.line}</span> — {r.error}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {importResult && (
            <div id="csv-result" className="rounded-xl border border-gray-200 p-3 space-y-2">
              <p className="text-sm font-semibold text-gray-800">
                {importResult.created} created, {importResult.reused} already existed,{' '}
                {importResult.failed} failed.
              </p>
              {/* Accounts and invitations are counted separately on purpose.
                  "50 created" while three invitations bounced is not fifty
                  successes, and the difference is what an administrator has to
                  act on. */}
              <p
                className={`text-sm font-semibold ${
                  importResult.invites_failed > 0 ? 'text-rose-700' : 'text-gray-800'
                }`}
              >
                {importResult.invites_sent} invitation
                {importResult.invites_sent === 1 ? '' : 's'} sent
                {importResult.invites_failed > 0
                  ? `, ${importResult.invites_failed} could not be delivered — those people cannot sign in yet.`
                  : '.'}
              </p>
              <ul className="space-y-1 text-xs">
                {importResult.results.map((r) => (
                  <li
                    key={`${r.row}-${r.email}`}
                    className={r.status === 'failed' ? 'text-rose-700' : 'text-gray-600'}
                  >
                    <span className="font-mono">Line {r.row}</span>{' '}
                    <span className="font-medium">{r.email || '—'}</span>{' '}
                    {r.status === 'failed' ? `— ${r.error}` : `— ${r.status}`}
                    {r.status !== 'failed' && r.invite_status !== 'PENDING' && (
                      <span className="text-rose-700">
                        {' '}
                        · invitation {r.invite_status === 'NOT_SENT' ? 'not sent' : 'failed'}
                        {r.invite_error ? ` (${r.invite_error})` : ''}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              id="csv-close"
              onClick={() => setImportOpen(false)}
              className={LH_SECONDARY_BUTTON}
              disabled={importing}
            >
              Close
            </button>
            <button type="submit" id="csv-submit" className={LH_PRIMARY_BUTTON} disabled={importing}>
              {importing ? 'Importing…' : 'Import'}
            </button>
          </div>
        </form>
      </SchoolDialog>
    </div>
  )
}
