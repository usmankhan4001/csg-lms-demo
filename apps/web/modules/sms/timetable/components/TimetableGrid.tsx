'use client'

/**
 * Visual weekly timetable: rows = periods, columns = days, each cell showing
 * the scheduled course/teacher/room, with clashing slots flagged inline.
 *
 * Scope note -- drag-and-drop rescheduling is deliberately NOT implemented.
 * `sms_timetable.py` exposes only `POST /schedules` (create) and
 * `POST /check-clashes`; there is no update/reschedule endpoint, so a
 * draggable grid would have nothing real to persist to and would be a UI that
 * silently loses the teacher's change. Adding drag-drop needs a backend
 * PATCH /schedules/{id} first.
 *
 * The clash highlighting here is computed CLIENT-SIDE from the slots already
 * fetched, so it only ever flags conflicts visible within the current view
 * (e.g. one teacher's own week). It is a display aid, not an authority: the
 * real, cross-timetable validation lives server-side in
 * `services/sms/timetable.py` and runs on write via `enforce_no_clash`.
 */

import { useMemo } from 'react'
import { AlertTriangle, CalendarDays } from 'lucide-react'
import { EmptyState, SectionCard } from '@/components/widgets'
import type { ApiError } from '@/lib/api/api-client'
import type { SectionCardState } from '@/components/widgets'
import { DAY_ORDER } from '../api'
import type { TimetableSlotDetail } from '../types'

/** Monday–Friday by default; weekend columns appear only if actually scheduled. */
const WEEKDAYS = DAY_ORDER.slice(0, 5)

export interface TimetableGridProps {
  slots: TimetableSlotDetail[]
  state?: SectionCardState
  error?: ApiError | null
  onRetry?: () => void
  title?: string
  description?: string
}

interface ClashInfo {
  teacher: boolean
  room: boolean
}

/**
 * Flags slots that collide within the fetched set: same day + same period with
 * either the same teacher or the same room.
 */
function computeClashes(slots: TimetableSlotDetail[]): Record<number, ClashInfo> {
  const result: Record<number, ClashInfo> = {}
  const groups = new Map<string, TimetableSlotDetail[]>()

  for (const slot of slots) {
    const key = `${slot.day_of_week?.toUpperCase()}|${slot.period_id}`
    const list = groups.get(key)
    if (list) list.push(slot)
    else groups.set(key, [slot])
  }

  for (const group of groups.values()) {
    if (group.length < 2) continue
    for (const slot of group) {
      const teacher = group.some((o) => o.id !== slot.id && o.teacher_id === slot.teacher_id)
      const room = group.some(
        (o) => o.id !== slot.id && !!slot.room_number && o.room_number === slot.room_number
      )
      if (teacher || room) result[slot.id] = { teacher, room }
    }
  }

  return result
}

export function TimetableGrid({
  slots,
  state = 'success',
  error,
  onRetry,
  title = 'Weekly Timetable',
  description,
}: TimetableGridProps) {
  const clashes = useMemo(() => computeClashes(slots), [slots])

  // Periods actually in use, ordered by period_number when available.
  const periods = useMemo(() => {
    const map = new Map<number, { id: number; number: number | null; start?: string | null; end?: string | null }>()
    for (const s of slots) {
      if (!map.has(s.period_id)) {
        map.set(s.period_id, {
          id: s.period_id,
          number: s.period_number ?? null,
          start: s.start_time,
          end: s.end_time,
        })
      }
    }
    return [...map.values()].sort((a, b) => (a.number ?? a.id) - (b.number ?? b.id))
  }, [slots])

  // Show weekend columns only when something is scheduled on them.
  const days = useMemo(() => {
    const used = new Set(slots.map((s) => s.day_of_week?.toUpperCase()))
    return DAY_ORDER.filter((d) => WEEKDAYS.includes(d) || used.has(d))
  }, [slots])

  const byCell = useMemo(() => {
    const map = new Map<string, TimetableSlotDetail[]>()
    for (const s of slots) {
      const key = `${s.day_of_week?.toUpperCase()}|${s.period_id}`
      const list = map.get(key)
      if (list) list.push(s)
      else map.set(key, [s])
    }
    return map
  }, [slots])

  const clashCount = Object.keys(clashes).length

  return (
    <SectionCard
      id="timetable-grid"
      title={title}
      description={description}
      icon={<CalendarDays className="size-4 text-muted-foreground" />}
      state={state}
      error={error}
      onRetry={onRetry}
      bodyClassName="p-0"
      action={
        clashCount > 0 ? (
          <span className="flex items-center gap-1.5 text-xs font-medium text-destructive">
            <AlertTriangle className="size-3.5" />
            {clashCount} clashing slot{clashCount === 1 ? '' : 's'}
          </span>
        ) : undefined
      }
    >
      {periods.length === 0 ? (
        <EmptyState
          title="Nothing scheduled"
          description="No timetable slots exist for this term yet."
        />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="bg-muted/50">
                <th className="w-28 px-3 py-2 text-start font-medium text-muted-foreground">Period</th>
                {days.map((d) => (
                  <th key={d} className="px-3 py-2 text-start font-medium text-muted-foreground">
                    {d.charAt(0) + d.slice(1).toLowerCase()}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {periods.map((p) => (
                <tr key={p.id} className="border-t border-border align-top">
                  <td className="px-3 py-2 whitespace-nowrap">
                    <div className="font-medium">P{p.number ?? p.id}</div>
                    {p.start && p.end && (
                      <div className="text-[11px] text-muted-foreground">
                        {p.start}–{p.end}
                      </div>
                    )}
                  </td>
                  {days.map((d) => {
                    const cell = byCell.get(`${d}|${p.id}`) ?? []
                    return (
                      <td key={d} className="px-2 py-1.5">
                        {cell.length === 0 ? (
                          <span className="text-xs text-muted-foreground/50">—</span>
                        ) : (
                          <div className="space-y-1">
                            {cell.map((s) => {
                              const clash = clashes[s.id]
                              return (
                                <div
                                  key={s.id}
                                  className={
                                    clash
                                      ? 'rounded-md border border-destructive/50 bg-destructive/10 px-2 py-1'
                                      : 'rounded-md border border-border bg-card px-2 py-1'
                                  }
                                >
                                  <div className="text-xs font-medium">Course #{s.course_id}</div>
                                  <div className="text-[11px] text-muted-foreground">
                                    Staff #{s.teacher_id}
                                    {s.room_number ? ` · Room ${s.room_number}` : ''}
                                  </div>
                                  {clash && (
                                    <div className="mt-0.5 flex items-center gap-1 text-[11px] font-medium text-destructive">
                                      <AlertTriangle className="size-3" />
                                      {clash.teacher && clash.room
                                        ? 'Teacher & room clash'
                                        : clash.teacher
                                          ? 'Teacher double-booked'
                                          : 'Room double-booked'}
                                    </div>
                                  )}
                                </div>
                              )
                            })}
                          </div>
                        )}
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </SectionCard>
  )
}
