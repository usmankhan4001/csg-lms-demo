'use client'

/**
 * The holds queue.
 *
 * A hold queues for a TITLE, never a specific copy: `LibraryBook` tracks
 * `total_copies`/`available_copies` as counters with no per-copy row, so the
 * library knows it holds three copies and how many are out, but not WHICH copy
 * a loan refers to. This screen therefore never promises a particular copy.
 *
 * READY IS NOT FULFILLED, and the distinction drives the whole desk workflow:
 * READY means a copy is set aside and the reader has not walked in yet.
 * Without it a librarian cannot tell "waiting for a copy" from "waiting for
 * the reader", which are different problems with different remedies — chase
 * the shelf, or chase the person.
 *
 * `queue_position` is derived from `reserved_at` server-side rather than
 * stored, so a cancellation cannot silently reorder the queue.
 */

import { useMemo, useState } from 'react'
import { BookMarked, Clock, Inbox } from 'lucide-react'
import {
  DashPageShell,
  DataTable,
  LH_INPUT,
  LH_PRIMARY_BUTTON,
  LH_SECONDARY_BUTTON,
  SectionCard,
  StatGrid,
  StatusChip,
} from '@/components/widgets'
import { ApiError } from '@/lib/api/api-client'
import { useApiResource } from '@/lib/api/useApiResource'
import { useSchoolSession } from '@/lib/api/useSchoolSession'
import {
  closeReservation,
  expireStaleHolds,
  listBooks,
  listReservations,
  markReservationReady,
} from '@/modules/sms/library/api'
import type {
  ReservationStatus,
  ReservationWithPosition,
} from '@/modules/sms/library/types'

interface Props {
  org_id: number
  orgslug: string
}

const STATUSES: ReservationStatus[] = [
  'WAITING',
  'READY',
  'FULFILLED',
  'CANCELLED',
  'EXPIRED',
]

const STATUS_TONE: Record<ReservationStatus, 'neutral' | 'positive' | 'caution'> = {
  WAITING: 'neutral',
  READY: 'caution', // needs someone to act: collect it or let it lapse
  FULFILLED: 'positive',
  CANCELLED: 'neutral',
  EXPIRED: 'neutral',
}

function formatDateTime(value: string | null): string {
  if (!value) return '—'
  const d = new Date(value)
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleString()
}

/** 0 = held at the desk, -1 = closed. Neither is a queue place, so neither is
 *  rendered as one. */
function positionLabel(position: number, status: ReservationStatus): string {
  if (status === 'READY' || position === 0) return 'At the desk'
  if (position < 0) return '—'
  return `#${position}`
}

export default function ReservationsClient({ org_id }: Props) {
  const { session } = useSchoolSession()
  const campusId = session?.campus_id ?? undefined

  const [statusFilter, setStatusFilter] = useState<ReservationStatus | ''>('WAITING')
  const [busyId, setBusyId] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [expiredCount, setExpiredCount] = useState<number | null>(null)

  const books = useApiResource(() => listBooks({}), [], {
    isEmpty: (d) => d.length === 0,
  })

  const reservations = useApiResource(
    () =>
      listReservations({
        reservationStatus: statusFilter || undefined,
        campusId,
      }),
    [statusFilter, campusId],
    { isEmpty: (d) => d.length === 0 }
  )

  const bookTitle = useMemo(() => {
    const map = new Map<number, string>()
    for (const b of books.data ?? []) map.set(b.id, b.title)
    return map
  }, [books.data])

  const rows = reservations.data ?? []
  const counts = useMemo(
    () => ({
      waiting: rows.filter((r) => r.status === 'WAITING').length,
      ready: rows.filter((r) => r.status === 'READY').length,
    }),
    [rows]
  )

  async function act(
    id: number,
    fn: () => Promise<unknown>,
    fallback: string
  ) {
    setBusyId(id)
    setError(null)
    try {
      await fn()
      reservations.refetch()
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.kind === 'permission_denied'
            ? 'You need librarian access to manage holds.'
            : err.message
          : fallback
      )
    } finally {
      setBusyId(null)
    }
  }

  async function handleExpireStale() {
    setError(null)
    setExpiredCount(null)
    try {
      const released = await expireStaleHolds()
      // An empty list is a real answer — nothing was stale — and saying so
      // stops a librarian pressing it again wondering if it worked.
      setExpiredCount(released.length)
      reservations.refetch()
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : 'Could not release stale holds.'
      )
    }
  }

  return (
    <DashPageShell
      module="school-library"
      title="Holds"
      description="The reservation queue. A hold is for a title, not a particular copy."
    >
      <StatGrid
        state={reservations.status === 'loading' ? 'loading' : 'success'}
        columns={2}
        items={[
          { label: 'Waiting', value: counts.waiting, icon: Clock, tone: 'neutral' },
          {
            label: 'Ready to collect',
            value: counts.ready,
            icon: BookMarked,
            tone: counts.ready > 0 ? 'caution' : 'neutral',
          },
        ]}
      />

      <SectionCard title="Filter">
        <div className="flex flex-wrap items-end gap-4">
          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-medium text-gray-500">Status</span>
            <select
              id="holds-status"
              className={LH_INPUT}
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as ReservationStatus | '')}
            >
              <option value="">Any status</option>
              {STATUSES.map((s) => (
                <option key={s} value={s}>
                  {s.charAt(0) + s.slice(1).toLowerCase()}
                </option>
              ))}
            </select>
          </label>

          <button
            type="button"
            id="holds-expire-stale"
            className={LH_SECONDARY_BUTTON}
            onClick={handleExpireStale}
          >
            Release uncollected holds
          </button>
        </div>

        {expiredCount !== null && (
          <p className="mt-3 text-sm text-gray-600">
            {expiredCount === 0
              ? 'Nothing was stale — no holds were released.'
              : `${expiredCount} uncollected hold${expiredCount === 1 ? '' : 's'} released back to the queue.`}
          </p>
        )}

        {error && <p className="mt-3 text-sm text-rose-600">{error}</p>}
      </SectionCard>

      <SectionCard
        title="Queue"
        state={reservations.status}
        error={reservations.error}
        onRetry={reservations.refetch}
        emptyTitle="No holds"
        emptyDescription="When every copy of a title is out, readers can queue for it here."
      >
        <DataTable
          rows={rows}
          rowKey={(r) => r.id}
          state="success"
          totalLabel={`${rows.length} hold${rows.length === 1 ? '' : 's'}`}
          columns={[
            {
              key: 'position',
              header: 'Place',
              render: (r) => positionLabel(r.queue_position, r.status),
            },
            {
              key: 'book',
              header: 'Title',
              render: (r) => bookTitle.get(r.book_id) ?? `Book #${r.book_id}`,
            },
            { key: 'reader', header: 'Reader', render: (r) => `User #${r.user_id}` },
            {
              key: 'status',
              header: 'Status',
              render: (r) => (
                <StatusChip
                  label={r.status.charAt(0) + r.status.slice(1).toLowerCase()}
                  tone={STATUS_TONE[r.status]}
                />
              ),
            },
            {
              key: 'reserved',
              header: 'Reserved',
              render: (r) => formatDateTime(r.reserved_at),
            },
            {
              key: 'expires',
              header: 'Held until',
              // Only meaningful once a copy is set aside.
              render: (r) => (r.status === 'READY' ? formatDateTime(r.expires_at) : '—'),
            },
            {
              key: 'actions',
              header: '',
              align: 'right',
              render: (r) => (
                <div className="flex justify-end gap-2">
                  {r.status === 'WAITING' && (
                    <button
                      type="button"
                      id={`hold-ready-${r.id}`}
                      disabled={busyId === r.id}
                      className={LH_SECONDARY_BUTTON}
                      onClick={() =>
                        act(r.id, () => markReservationReady(r.id), 'Could not set aside.')
                      }
                    >
                      Set aside
                    </button>
                  )}
                  {r.status === 'READY' && (
                    <button
                      type="button"
                      id={`hold-fulfil-${r.id}`}
                      disabled={busyId === r.id}
                      className={LH_PRIMARY_BUTTON}
                      onClick={() =>
                        act(
                          r.id,
                          () => closeReservation(r.id, 'FULFILLED'),
                          'Could not close.'
                        )
                      }
                    >
                      Collected
                    </button>
                  )}
                  {(r.status === 'WAITING' || r.status === 'READY') && (
                    <button
                      type="button"
                      id={`hold-cancel-${r.id}`}
                      disabled={busyId === r.id}
                      className={LH_SECONDARY_BUTTON}
                      onClick={() =>
                        act(
                          r.id,
                          () => closeReservation(r.id, 'CANCELLED'),
                          'Could not cancel.'
                        )
                      }
                    >
                      Cancel
                    </button>
                  )}
                </div>
              ),
            },
          ]}
        />
      </SectionCard>
    </DashPageShell>
  )
}
