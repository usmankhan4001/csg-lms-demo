'use client'

/**
 * Badges — the first UI this module has ever had.
 *
 * `/dash/gamification` has been linked from BOTH sidebars (DashLeftMenu.tsx:781,
 * DashMobileMenu.tsx:348, each gated `canTeach`) while the route directory did
 * not exist, so every teacher who clicked it got a 404. Six endpoints in
 * `sms_gamification.py` were live, role-gated and unreachable.
 *
 * ON ZEROES HERE. This codebase's standing rule is that absence must never
 * render as zero, and this screen shows zeroes on purpose. XP and badge counts
 * are QUANTITIES: a student who has earned nothing genuinely has zero points,
 * the same way they have zero badges. That is unlike a RATE -- an attendance
 * figure of 0% for a school that never took a register is a fabrication,
 * because nobody measured. The distinction is whether a number was counted or
 * merely absent.
 *
 * What this screen will NOT claim is that an empty badge list means a
 * well-behaved school; it means nobody has defined a badge scheme.
 */

import { useState } from 'react'
import { Award, Trophy } from 'lucide-react'

import {
  DashPageShell,
  DataTable,
  SchoolDialog,
  SchoolField,
  SectionCard,
  StatusChip,
  LH_INPUT,
  LH_PRIMARY_BUTTON,
  LH_SECONDARY_BUTTON,
  type DataTableColumn,
  type DataTableState,
} from '@/components/widgets'
import { useApiResource } from '@/lib/api/useApiResource'
import { ApiError } from '@/lib/api/api-client'
import { listSchoolPeople, type SchoolPerson } from '@/modules/sms/campus/api'
import { awardBadge, createBadge, listBadges } from '@/modules/sms/gamification/api'
import { BADGE_CATEGORIES, type Badge } from '@/modules/sms/gamification/types'

export default function GamificationDashClient({
  org_id,
  orgslug,
}: {
  org_id: number
  orgslug: string
}) {
  void org_id
  void orgslug

  const [createOpen, setCreateOpen] = useState(false)
  const [awardOpen, setAwardOpen] = useState(false)

  const badges = useApiResource<Badge[]>(() => listBadges(), [])
  const rows = badges.data ?? []

  const tableState: DataTableState =
    badges.status === 'loading'
      ? 'loading'
      : badges.status === 'error'
        ? 'error'
        : rows.length === 0
          ? 'empty'
          : 'success'

  const columns: DataTableColumn<Badge>[] = [
    {
      key: 'name',
      header: 'Badge',
      render: (row) => (
        <div className="min-w-0">
          <div className="font-medium truncate">{row.name}</div>
          <div className="text-xs text-gray-500 truncate">{row.description}</div>
        </div>
      ),
    },
    {
      key: 'category',
      header: 'Category',
      render: (row) => <StatusChip label={row.category} tone="neutral" />,
    },
    {
      key: 'points',
      header: 'Points',
      render: (row) => <span className="tabular-nums">{row.points_reward}</span>,
    },
  ]

  return (
    <DashPageShell
      title="Gamification"
      description="Badges and points staff can award for academic work, attendance and behaviour."
      module="gamification"
      action={
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            id="gamification-award-badge"
            className={LH_SECONDARY_BUTTON}
            onClick={() => setAwardOpen(true)}
            disabled={rows.length === 0}
            title={rows.length === 0 ? 'Define a badge before awarding one' : undefined}
          >
            Award badge
          </button>
          <button
            type="button"
            id="gamification-create-badge"
            className={LH_PRIMARY_BUTTON}
            onClick={() => setCreateOpen(true)}
          >
            New badge
          </button>
        </div>
      }
    >
      <SectionCard
        title="Badges"
        description={
          badges.status === 'success' && rows.length > 0
            ? `${rows.length} defined`
            : undefined
        }
      >
        <DataTable<Badge>
          columns={columns}
          rows={rows}
          rowKey={(row) => row.id}
          state={tableState}
          error={badges.error}
          onRetry={badges.refetch}
          emptyIcon={Trophy}
          emptyTitle="No badges defined"
          // NOT "0 badges awarded". An empty scheme is a setup step nobody has
          // taken, not a record of a school that awards nothing.
          emptyDescription="Nobody has set up a badge scheme yet. Create a badge and staff can start awarding it."
        />
      </SectionCard>

      <CreateBadgeDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        onCreated={() => {
          setCreateOpen(false)
          badges.refetch()
        }}
      />

      <AwardBadgeDialog
        open={awardOpen}
        onOpenChange={setAwardOpen}
        badges={rows}
        onAwarded={() => setAwardOpen(false)}
      />
    </DashPageShell>
  )
}

function CreateBadgeDialog({
  open,
  onOpenChange,
  onCreated,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  onCreated: () => void
}) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [category, setCategory] = useState<string>(BADGE_CATEGORIES[0])
  const [points, setPoints] = useState('50')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      await createBadge({
        name: name.trim(),
        description: description.trim(),
        category,
        points_reward: Number(points) || 0,
      })
      setName('')
      setDescription('')
      setPoints('50')
      onCreated()
    } catch (err) {
      // Creating a badge is [SUPER_ADMIN, SCHOOL_ADMIN, TEACHER]. A 403 here is
      // an honest answer to a role that may view the scheme but not change it,
      // so it is shown rather than swallowed.
      setError(
        err instanceof ApiError
          ? err.kind === 'permission_denied'
            ? 'Your role can view badges but not create them.'
            : err.message
          : 'Could not create this badge.'
      )
    } finally {
      setSaving(false)
    }
  }

  return (
    <SchoolDialog
      open={open}
      onOpenChange={onOpenChange}
      title="New badge"
      description="Badges are defined once and then awarded to students by staff."
      onSubmit={submit}
      footer={
        <>
          <button
            type="button"
            id="gamification-create-cancel"
            className={LH_SECONDARY_BUTTON}
            onClick={() => onOpenChange(false)}
          >
            Cancel
          </button>
          <button
            type="submit"
            id="gamification-create-submit"
            className={LH_PRIMARY_BUTTON}
            disabled={saving || !name.trim() || !description.trim()}
          >
            {saving ? 'Creating…' : 'Create badge'}
          </button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <SchoolField id="badge-name" label="Name" required>
          <input
            id="badge-name"
            className={LH_INPUT}
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Consistent effort"
          />
        </SchoolField>

        <SchoolField id="badge-description" label="Description" required>
          <input
            id="badge-description"
            className={LH_INPUT}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Shown to the student when they receive it"
          />
        </SchoolField>

        <SchoolField id="badge-category" label="Category">
          <select
            id="badge-category"
            className={LH_INPUT}
            value={category}
            onChange={(e) => setCategory(e.target.value)}
          >
            {BADGE_CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </SchoolField>

        <SchoolField
          id="badge-points"
          label="Points awarded"
          help="Added to the student's total when this badge is given."
        >
          <input
            id="badge-points"
            type="number"
            min={0}
            className={LH_INPUT}
            value={points}
            onChange={(e) => setPoints(e.target.value)}
          />
        </SchoolField>

        {error ? <p className="text-sm text-red-600">{error}</p> : null}
      </div>
    </SchoolDialog>
  )
}

function AwardBadgeDialog({
  open,
  onOpenChange,
  badges,
  onAwarded,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  badges: Badge[]
  onAwarded: () => void
}) {
  const [badgeId, setBadgeId] = useState('')
  const [studentId, setStudentId] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState<string | null>(null)

  // A real picker, not a numeric id box. The exam seating screen shipped
  // asking an administrator to type a raw sitting id ("e.g. 4") because no
  // screen listed them; this avoids repeating that.
  const students = useApiResource<SchoolPerson[]>(() => listSchoolPeople('STUDENT'), [])

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setSaving(true)
    setError(null)
    setDone(null)
    try {
      await awardBadge({ user_id: Number(studentId), badge_id: Number(badgeId) })
      const badge = badges.find((b) => b.id === Number(badgeId))
      setDone(badge ? `${badge.name} awarded.` : 'Badge awarded.')
      setStudentId('')
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.kind === 'permission_denied'
            ? 'Your role cannot award badges.'
            : err.message
          : 'Could not award this badge.'
      )
    } finally {
      setSaving(false)
    }
  }

  return (
    <SchoolDialog
      open={open}
      onOpenChange={onOpenChange}
      title="Award a badge"
      description="The student's points total increases by the badge's reward."
      onSubmit={submit}
      footer={
        <>
          <button
            type="button"
            id="gamification-award-cancel"
            className={LH_SECONDARY_BUTTON}
            onClick={() => onOpenChange(false)}
          >
            Close
          </button>
          <button
            type="submit"
            id="gamification-award-submit"
            className={LH_PRIMARY_BUTTON}
            disabled={saving || !badgeId || !studentId}
          >
            {saving ? 'Awarding…' : 'Award badge'}
          </button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <SchoolField id="award-badge" label="Badge" required>
          <select
            id="award-badge"
            className={LH_INPUT}
            value={badgeId}
            onChange={(e) => setBadgeId(e.target.value)}
          >
            <option value="">Choose a badge…</option>
            {badges.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name} ({b.points_reward} pts)
              </option>
            ))}
          </select>
        </SchoolField>

        <SchoolField
          id="award-student"
          label="Student"
          required
          help={
            students.status === 'error'
              ? 'Student list unavailable — your role may not be permitted to read it.'
              : undefined
          }
        >
          <select
            id="award-student"
            className={LH_INPUT}
            value={studentId}
            onChange={(e) => setStudentId(e.target.value)}
            disabled={students.status === 'loading' || students.status === 'error'}
          >
            <option value="">
              {students.status === 'loading' ? 'Loading students…' : 'Choose a student…'}
            </option>
            {(students.data ?? []).map((p) => (
              <option key={p.user_id} value={p.user_id}>
                {p.name ?? `Student #${p.user_id}`}
              </option>
            ))}
          </select>
        </SchoolField>

        {done ? (
          <p className="flex items-center gap-2 text-sm text-emerald-700">
            <Award className="size-4" /> {done}
          </p>
        ) : null}
        {error ? <p className="text-sm text-red-600">{error}</p> : null}
      </div>
    </SchoolDialog>
  )
}
