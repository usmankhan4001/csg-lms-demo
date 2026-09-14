'use client'

/**
 * One live class: its recording policy, its coursework, and how to join it.
 *
 * Every host control on this page is gated on `can_host`, which the server
 * computes for the calling user (`live_classes.py` `_to_detail_read`). That is
 * deliberate: re-deriving "may this person host" from roles in the browser
 * would eventually disagree with the server, and the disagreement would show
 * up as buttons that 403 rather than buttons that are absent.
 *
 * Recording is presented as TWO separate decisions because the backend treats
 * them as two: whether the class is recorded at all, and whether students may
 * watch it back. A teacher may reasonably record a lesson for their own review
 * and never publish it.
 */

import { useState } from 'react'
import { Video, Paperclip, ArrowLeft } from '@phosphor-icons/react'
import {
  DashPageShell,
  DataTable,
  SectionCard,
  StatusChip,
  EmptyState,
  LH_PRIMARY_BUTTON,
  LH_SECONDARY_BUTTON,
} from '@/components/widgets'
import { ApiError } from '@/lib/api/api-client'
import { useApiResource } from '@/lib/api/useApiResource'
import {
  getLiveClass,
  setLiveClassRecording,
  shareLiveClassRecording,
  startLiveClass,
  cancelLiveClass,
} from '@/modules/sms/live-class/api'
import {
  describeClassStatus,
  describeRecording,
  formatDuration,
  formatWhen,
  isJoinable,
} from '@/modules/sms/live-class/presentation'

interface LiveClassDetailClientProps {
  classId: number
  orgslug: string
}

export default function LiveClassDetailClient({ classId, orgslug }: LiveClassDetailClientProps) {
  const [actionError, setActionError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const cls = useApiResource(() => getLiveClass(classId), [classId])
  const data = cls.data

  async function run(fn: () => Promise<unknown>) {
    setBusy(true)
    setActionError(null)
    try {
      await fn()
      cls.refetch()
    } catch (err) {
      setActionError(
        err instanceof ApiError
          ? err.kind === 'permission_denied'
            ? 'Only this class’s host or a school admin can change it.'
            : err.message
          : 'That did not work. Try again.'
      )
    } finally {
      setBusy(false)
    }
  }

  async function handleStart() {
    setActionError(null)
    try {
      const res = await startLiveClass(classId)
      window.location.href = `/live/${encodeURIComponent(res.session.room_name)}`
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : 'Could not start the class.')
    }
  }

  const rec = data?.recording
  const recDesc = rec ? describeRecording(rec.status) : null
  const statusDesc = data ? describeClassStatus(data.status) : null

  return (
    <DashPageShell
      // No student or class identifier in the title: titles land in browser
      // history and screenshots.
      title={data?.title ?? 'Live class'}
      description={data ? formatWhen(data.start_time) : undefined}
      action={
        <a href={`/orgs/${orgslug}/dash/live-classes`} className={LH_SECONDARY_BUTTON} id="live-class-back">
          <ArrowLeft className="size-4" /> <span>All classes</span>
        </a>
      }
    >
      <SectionCard
        title="This class"
        icon={<Video className="size-4 text-gray-500" />}
        state={cls.status}
        error={cls.error}
        onRetry={cls.refetch}
        emptyTitle="Class not found"
        emptyDescription="It may have been removed, or you may not have access to it."
      >
        {data && statusDesc && (
          <div className="flex flex-col gap-4">
            {actionError && (
              <p className="text-sm text-rose-600" role="alert">
                {actionError}
              </p>
            )}

            <div className="flex flex-wrap items-center gap-3">
              <StatusChip label={statusDesc.label} tone={statusDesc.tone} />
              <span className="text-sm text-gray-500">Room: {data.room_name}</span>
            </div>

            {data.status === 'CANCELLED' && (
              <p className="text-sm text-gray-600">
                {/* An absent reason is absent, not an invented one. */}
                Cancelled{data.cancelled_reason ? `: ${data.cancelled_reason}` : ' — no reason was recorded.'}
              </p>
            )}

            {data.description && <p className="text-sm text-gray-600">{data.description}</p>}

            {data.can_host && (
              <div className="flex flex-wrap items-center gap-2">
                {isJoinable(data.status) && (
                  <button type="button" id="live-class-detail-start" className={LH_PRIMARY_BUTTON} onClick={handleStart}>
                    <span>{data.status === 'LIVE' ? 'Rejoin class' : 'Start class'}</span>
                  </button>
                )}
                {data.status === 'SCHEDULED' && (
                  <button
                    type="button"
                    id="live-class-detail-cancel"
                    className={LH_SECONDARY_BUTTON}
                    disabled={busy}
                    onClick={() => run(() => cancelLiveClass(classId))}
                  >
                    <span>Cancel class</span>
                  </button>
                )}
              </div>
            )}
          </div>
        )}
      </SectionCard>

      {data && rec && recDesc && (
        <SectionCard title="Recording" icon={<Video className="size-4 text-gray-500" />}>
          <div className="flex flex-col gap-4">
            <div className="flex flex-wrap items-center gap-3">
              <StatusChip label={recDesc.label} tone={recDesc.tone} />
              {rec.shared_with_students ? (
                <StatusChip label="Shared with students" tone="positive" />
              ) : (
                <StatusChip label="Not shared" tone="neutral" />
              )}
            </div>

            {/* The server's own explanation, verbatim. UNAVAILABLE is a
                configuration gap, not a failure, and the wording must not
                send a teacher chasing a fault that does not exist. */}
            {recDesc.hint && <p className="text-sm text-gray-600">{recDesc.hint}</p>}
            {rec.note && <p className="text-sm text-gray-500">{rec.note}</p>}

            <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
              <div>
                <dt className="text-xs text-gray-500">Started</dt>
                <dd>{formatWhen(rec.started_at)}</dd>
              </div>
              <div>
                <dt className="text-xs text-gray-500">Completed</dt>
                <dd>{formatWhen(rec.completed_at)}</dd>
              </div>
              <div>
                <dt className="text-xs text-gray-500">Duration</dt>
                {/* Null is "Not measured", never 0m. */}
                <dd>{formatDuration(rec.duration_seconds)}</dd>
              </div>
              <div>
                <dt className="text-xs text-gray-500">File</dt>
                <dd>
                  {rec.url ? (
                    <a className="underline" href={rec.url} id="live-class-recording-file">
                      Open
                    </a>
                  ) : (
                    'None yet'
                  )}
                </dd>
              </div>
            </dl>

            {data.can_host && (
              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  id="live-class-recording-toggle"
                  className={LH_SECONDARY_BUTTON}
                  disabled={busy || rec.status === 'UNAVAILABLE'}
                  title={
                    rec.status === 'UNAVAILABLE'
                      ? 'Storage is not configured on this deployment, so recording cannot be enabled.'
                      : undefined
                  }
                  onClick={() => run(() => setLiveClassRecording(classId, !rec.enabled))}
                >
                  <span>{rec.enabled ? 'Turn recording off' : 'Turn recording on'}</span>
                </button>

                <button
                  type="button"
                  id="live-class-recording-share"
                  className={LH_SECONDARY_BUTTON}
                  disabled={busy}
                  onClick={() => run(() => shareLiveClassRecording(classId, !rec.shared_with_students))}
                >
                  <span>
                    {rec.shared_with_students ? 'Stop sharing with students' : 'Share with students'}
                  </span>
                </button>
              </div>
            )}
          </div>
        </SectionCard>
      )}

      {data && (
        <SectionCard title="Coursework" icon={<Paperclip className="size-4 text-gray-500" />}>
          {data.coursework.length === 0 ? (
            <EmptyState
              title="Nothing attached"
              description="No coursework has been attached to this class. That is not the same as none being set — it means nobody has attached any here."
            />
          ) : (
            <DataTable
              rows={data.coursework}
              rowKey={(r) => r.id}
              state="success"
              columns={[
                { key: 'activity', header: 'Activity', render: (r) => `Activity #${r.activity_id}` },
                { key: 'note', header: 'Note', render: (r) => r.note ?? '—' },
                { key: 'added', header: 'Attached', render: (r) => formatWhen(r.created_at) },
              ]}
            />
          )}
        </SectionCard>
      )}
    </DashPageShell>
  )
}
