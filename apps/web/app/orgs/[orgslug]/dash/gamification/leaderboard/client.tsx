'use client'

/**
 * Leaderboard, student profile and manual point awards.
 *
 * The profile endpoint is `GET /profile/{user_id}` and takes a raw numeric id.
 * Rather than give an administrator a box to type one into, a leaderboard row
 * IS the discovery surface — clicking a student opens their profile. The exam
 * seating screen shipped with `placeholder="e.g. 4"` for exactly this reason
 * (the endpoint listing sittings was never wired), and that is the mistake
 * being avoided here.
 *
 * A LEADERBOARD IS NOT NEUTRAL. Ranking children by points publicly is a
 * pedagogical choice a school should make deliberately, not one a dashboard
 * makes for it by existing. The module sits behind its own feature toggle, so
 * a school that does not want this can switch it off — that is the mechanism,
 * and it is why this screen does not, for instance, surface a "bottom of the
 * class" view.
 */

import { useState } from 'react'
import { Medal, Sparkles } from 'lucide-react'

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
import {
  addPoints,
  getGamificationProfile,
  getLeaderboard,
} from '@/modules/sms/gamification/api'
import type {
  LeaderboardEntry,
  StudentGamificationProfile,
} from '@/modules/sms/gamification/types'

export default function LeaderboardDashClient({
  org_id,
  orgslug,
}: {
  org_id: number
  orgslug: string
}) {
  void org_id
  void orgslug

  const [pointsOpen, setPointsOpen] = useState(false)
  const [profileFor, setProfileFor] = useState<LeaderboardEntry | null>(null)

  const board = useApiResource<LeaderboardEntry[]>(() => getLeaderboard(), [])
  const rows = board.data ?? []

  const tableState: DataTableState =
    board.status === 'loading'
      ? 'loading'
      : board.status === 'error'
        ? 'error'
        : rows.length === 0
          ? 'empty'
          : 'success'

  const columns: DataTableColumn<LeaderboardEntry>[] = [
    {
      key: 'rank',
      header: '#',
      render: (row) => <span className="tabular-nums text-gray-500">{row.rank}</span>,
    },
    {
      key: 'name',
      header: 'Student',
      render: (row) => (
        <button
          type="button"
          className="text-left font-medium hover:underline"
          onClick={() => setProfileFor(row)}
        >
          {row.name}
        </button>
      ),
    },
    {
      key: 'xp',
      header: 'Points',
      render: (row) => <span className="tabular-nums">{row.total_xp}</span>,
    },
    {
      key: 'level',
      header: 'Level',
      render: (row) => <StatusChip label={`Level ${row.level}`} tone="info" />,
    },
    {
      key: 'streak',
      header: 'Streak',
      render: (row) =>
        row.current_streak_days > 0 ? (
          <span className="tabular-nums">{row.current_streak_days} days</span>
        ) : (
          <span className="text-xs text-gray-500">None running</span>
        ),
    },
    {
      key: 'badges',
      header: 'Badges',
      render: (row) => <span className="tabular-nums">{row.badges_count}</span>,
    },
  ]

  return (
    <DashPageShell
      title="Leaderboard"
      description="Points, levels and streaks. Only students who have earned points appear."
      module="gamification"
      action={
        <button
          type="button"
          id="gamification-add-points"
          className={LH_PRIMARY_BUTTON}
          onClick={() => setPointsOpen(true)}
        >
          Add points
        </button>
      }
    >
      <SectionCard
        title="Standings"
        description={
          board.status === 'success' && rows.length > 0
            ? `${rows.length} students have earned points`
            : undefined
        }
      >
        <DataTable<LeaderboardEntry>
          columns={columns}
          rows={rows}
          rowKey={(row) => row.user_id}
          state={tableState}
          error={board.error}
          onRetry={board.refetch}
          emptyIcon={Medal}
          emptyTitle="Nobody has earned points yet"
          // Deliberately explicit that this lists PARTICIPANTS, not the school.
          // An empty board means no points have been awarded, not that students
          // scored zero -- and a student absent from this table has no record
          // here at all, which is different from being last.
          emptyDescription="This table lists students who have been awarded points. It is empty because none have been awarded yet, not because students scored nothing."
        />
      </SectionCard>

      <AddPointsDialog
        open={pointsOpen}
        onOpenChange={setPointsOpen}
        onAdded={() => {
          setPointsOpen(false)
          board.refetch()
        }}
      />

      <ProfileDialog entry={profileFor} onClose={() => setProfileFor(null)} />
    </DashPageShell>
  )
}

function ProfileDialog({
  entry,
  onClose,
}: {
  entry: LeaderboardEntry | null
  onClose: () => void
}) {
  const profile = useApiResource<StudentGamificationProfile>(
    () => getGamificationProfile(entry?.user_id ?? 0),
    [entry?.user_id],
    { skip: entry === null }
  )

  const data = profile.data

  return (
    <SchoolDialog
      open={entry !== null}
      onOpenChange={(open) => {
        if (!open) onClose()
      }}
      title={entry?.name ?? 'Student'}
      description="Points, streaks and badges earned."
      footer={
        <button
          type="button"
          id="gamification-profile-close"
          className={LH_SECONDARY_BUTTON}
          onClick={onClose}
        >
          Close
        </button>
      }
    >
      {profile.status === 'loading' ? (
        <p className="text-sm text-gray-500">Loading…</p>
      ) : profile.status === 'error' ? (
        <p className="text-sm text-red-600">
          {profile.error?.message ?? 'Could not load this profile.'}
        </p>
      ) : data ? (
        <div className="flex flex-col gap-4">
          <dl className="grid grid-cols-2 gap-3 text-sm">
            <div>
              <dt className="text-gray-500">Points</dt>
              <dd className="tabular-nums font-medium">{data.total_xp}</dd>
            </div>
            <div>
              <dt className="text-gray-500">Level</dt>
              <dd className="tabular-nums font-medium">{data.level}</dd>
            </div>
            <div>
              <dt className="text-gray-500">Current streak</dt>
              <dd className="tabular-nums font-medium">
                {data.current_streak_days > 0
                  ? `${data.current_streak_days} days`
                  : 'None running'}
              </dd>
            </div>
            <div>
              <dt className="text-gray-500">Longest streak</dt>
              <dd className="tabular-nums font-medium">
                {data.longest_streak_days > 0
                  ? `${data.longest_streak_days} days`
                  : 'None recorded'}
              </dd>
            </div>
          </dl>

          <div>
            <p className="mb-2 text-sm font-medium">Badges</p>
            {data.badges.length === 0 ? (
              <p className="text-sm text-gray-500">
                No badges awarded to this student yet.
              </p>
            ) : (
              <ul className="flex flex-wrap gap-2">
                {data.badges.map((b) => (
                  <li key={b.id}>
                    <StatusChip label={b.name} tone="positive" />
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      ) : null}
    </SchoolDialog>
  )
}

function AddPointsDialog({
  open,
  onOpenChange,
  onAdded,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  onAdded: () => void
}) {
  const [studentId, setStudentId] = useState('')
  const [points, setPoints] = useState('10')
  const [reason, setReason] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const students = useApiResource<SchoolPerson[]>(() => listSchoolPeople('STUDENT'), [])

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      await addPoints({
        user_id: Number(studentId),
        points: Number(points) || 0,
        reason: reason.trim(),
      })
      setReason('')
      onAdded()
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.kind === 'permission_denied'
            ? 'Your role cannot award points.'
            : err.message
          : 'Could not add points.'
      )
    } finally {
      setSaving(false)
    }
  }

  return (
    <SchoolDialog
      open={open}
      onOpenChange={onOpenChange}
      title="Add points"
      description="Recorded against the student with the reason you give."
      onSubmit={submit}
      footer={
        <>
          <button
            type="button"
            id="gamification-points-cancel"
            className={LH_SECONDARY_BUTTON}
            onClick={() => onOpenChange(false)}
          >
            Cancel
          </button>
          <button
            type="submit"
            id="gamification-points-submit"
            className={LH_PRIMARY_BUTTON}
            disabled={saving || !studentId || !reason.trim()}
          >
            {saving ? 'Adding…' : 'Add points'}
          </button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <SchoolField id="points-student" label="Student" required>
          <select
            id="points-student"
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

        <SchoolField id="points-amount" label="Points" required>
          <input
            id="points-amount"
            type="number"
            className={LH_INPUT}
            value={points}
            onChange={(e) => setPoints(e.target.value)}
          />
        </SchoolField>

        <SchoolField
          id="points-reason"
          label="Reason"
          required
          help="Stored with the award. Write what a parent could reasonably be shown."
        >
          <input
            id="points-reason"
            className={LH_INPUT}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Helped a classmate through a difficult topic"
          />
        </SchoolField>

        {error ? (
          <p className="flex items-center gap-2 text-sm text-red-600">
            <Sparkles className="size-4" /> {error}
          </p>
        ) : null}
      </div>
    </SchoolDialog>
  )
}
