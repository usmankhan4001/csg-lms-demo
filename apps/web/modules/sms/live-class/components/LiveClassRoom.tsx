'use client'

/**
 * Real WebRTC video classroom, built on `@livekit/components-react`'s
 * pre-built `VideoConference` (tiles, mic/camera/screen-share controls,
 * participant list, and a chat panel over LiveKit's own data channel --
 * all real, not the hand-rolled demo UI this replaces). Server-verified
 * attendance is recorded automatically by LiveKit's own webhooks
 * (`src/routers/live_class_webhooks.py`) as soon as this component's
 * WebRTC connection actually joins the room -- nothing here needs to log
 * attendance itself.
 *
 * NOT YET BUILT (flagged, not silently skipped): a shared whiteboard.
 * This project already has Hocuspocus/Yjs collaboration infrastructure for
 * course content; wiring a whiteboard surface into a live class would
 * reuse that, but is a separate, sizable piece of work left for later.
 */

import '@livekit/components-styles'
import { useRouter } from 'next/navigation'
import { useEffect, useState } from 'react'
import { LiveKitRoom, VideoConference } from '@livekit/components-react'
import { Loader2, ShieldAlert } from 'lucide-react'
import { ApiError } from '@/lib/api/api-client'
import { EmptyState } from '@/components/widgets'
import { getParticipantToken } from '../api'

interface LiveClassRoomProps {
  roomName: string
  participantId: string
  participantName: string
  isTeacher: boolean
  /** Where to send the user once they leave/disconnect. */
  onLeaveHref: string
}

type ConnectState = { status: 'connecting' } | { status: 'ready'; token: string; livekitUrl: string } | { status: 'error'; message: string }

export function LiveClassRoom({ roomName, participantId, participantName, isTeacher, onLeaveHref }: LiveClassRoomProps) {
  const router = useRouter()
  const [state, setState] = useState<ConnectState>({ status: 'connecting' })

  useEffect(() => {
    let cancelled = false
    setState({ status: 'connecting' })

    getParticipantToken(roomName, {
      participant_id: participantId,
      participant_name: participantName,
      is_teacher: isTeacher,
    })
      .then((res) => {
        if (cancelled) return
        setState({ status: 'ready', token: res.token, livekitUrl: res.livekit_url })
      })
      .catch((err: unknown) => {
        if (cancelled) return
        const message =
          err instanceof ApiError
            ? err.kind === 'not_found'
              ? 'This live class has ended or does not exist.'
              : err.message
            : 'Could not connect to the live class.'
        setState({ status: 'error', message })
      })

    return () => {
      cancelled = true
    }
  }, [roomName, participantId, participantName, isTeacher])

  if (state.status === 'connecting') {
    return (
      <div className="flex h-screen items-center justify-center bg-neutral-950">
        <div className="flex flex-col items-center gap-3 text-neutral-400">
          <Loader2 className="size-6 animate-spin" />
          <p className="text-sm">Joining live class…</p>
        </div>
      </div>
    )
  }

  if (state.status === 'error') {
    return (
      <div className="flex h-screen items-center justify-center bg-neutral-950">
        <EmptyState
          icon={ShieldAlert}
          tone="critical"
          title="Couldn't join this live class"
          description={state.message}
          action={{ label: 'Back to dashboard', href: onLeaveHref }}
        />
      </div>
    )
  }

  return (
    <LiveKitRoom
      token={state.token}
      serverUrl={state.livekitUrl}
      connect
      video
      audio
      data-lk-theme="default"
      style={{ height: '100vh' }}
      onDisconnected={() => router.push(onLeaveHref)}
    >
      <VideoConference />
    </LiveKitRoom>
  )
}
